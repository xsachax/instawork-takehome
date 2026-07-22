"""API views for the quiz platform."""

import json
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .grading import grade_answer
from . import judge as judge_module
from .models import Answer, Attempt, AttemptQuestion, Choice, Question, QuestionType
from .serializers import (
    AttemptReviewSerializer,
    AttemptSerializer,
    AttemptStartSerializer,
    QuestionSerializer,
)


class QuestionViewSet(viewsets.ModelViewSet):
    """CRUD for the question bank. Restricted to staff users."""

    queryset = Question.objects.prefetch_related('choices').all()
    serializer_class = QuestionSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        qtype = params.get('type')
        category = params.get('category')
        difficulty = params.get('difficulty')
        search = params.get('search')
        if qtype:
            qs = qs.filter(type=qtype)
        if category:
            qs = qs.filter(category__iexact=category)
        if difficulty:
            qs = qs.filter(difficulty=difficulty)
        if search:
            qs = qs.filter(prompt__icontains=search)
        return qs


class AttemptViewSet(viewsets.GenericViewSet):
    """Start quizzes, submit answers, and review results/history."""

    queryset = Attempt.objects.all()
    serializer_class = AttemptSerializer
    permission_classes = [AllowAny]

    def list(self, request):
        """History: previous attempts, optionally filtered by ``player``."""
        qs = Attempt.objects.all()
        player = request.query_params.get('player')
        if player:
            qs = qs.filter(player__iexact=player.strip())
        serializer = AttemptSerializer(qs, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """Full review of a single attempt (prompts, answers, correct answers).

        Correct answers are only exposed once the attempt has been submitted, so
        players can't peek at answers for an in-progress quiz.
        """
        attempt = self._get_attempt(pk)
        if attempt is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not attempt.is_submitted:
            return Response(AttemptStartSerializer(attempt).data)
        return Response(AttemptReviewSerializer(attempt).data)

    def create(self, request):
        """Start a new attempt with N random, non-repeating questions.

        An optional judge API key may be supplied (``judge_api_key``). When a
        key is present the random pool may include every question type; without
        a key the pool is restricted to deterministic types (single, multiple,
        numerical) so the player is never served a text/image question that
        can't be auto-graded. The key itself is only inspected here — it is
        never stored, logged, or attached to the attempt.
        """
        player = (request.data.get('player') or '').strip()
        if not player:
            return Response(
                {'player': 'A player name is required to start a quiz.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        judge_key = self._judge_key(request)

        count = settings.QUIZ_QUESTION_COUNT
        pool = Question.objects.all()
        if not judge_key:
            pool = pool.exclude(
                type__in=[QuestionType.TEXT, QuestionType.IMAGE]
            )
        question_ids = list(
            pool.values_list('id', flat=True).order_by('?')[:count]
        )
        if not question_ids:
            return Response(
                {'detail': 'The question bank is empty. Seed questions first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            attempt = Attempt.objects.create(player=player, total=len(question_ids))
            AttemptQuestion.objects.bulk_create([
                AttemptQuestion(attempt=attempt, question_id=qid, order=index)
                for index, qid in enumerate(question_ids)
            ])

        attempt = self._get_attempt(attempt.id)
        return Response(
            AttemptStartSerializer(attempt).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Grade and persist the player's answers for an attempt.

        Accepts ``multipart/form-data`` with an ``answers`` field (JSON string):

            [{"attempt_question_id": 1, "text": "...", "numerical": 42,
              "selected_choice_ids": [3, 4]}, ...]

        Image files are sent as separate fields named ``image_<attempt_question_id>``.
        """
        attempt = self._get_attempt(pk)
        if attempt is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if attempt.is_submitted:
            return Response(
                {'detail': 'This attempt has already been submitted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        answers_map = self._parse_answers(request)
        if answers_map is None:
            return Response(
                {'detail': 'Invalid answers payload; expected a JSON list.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Judge configuration is read from the request and held only in memory
        # for the duration of this call — never persisted or logged.
        judge_key = self._judge_key(request)
        judge_model = (request.data.get('judge_model') or '').strip() or None
        judge_base_url = (request.data.get('judge_base_url') or '').strip() or None

        score = 0
        with transaction.atomic():
            for aq in attempt.attempt_questions.select_related('question'):
                question = aq.question
                payload = answers_map.get(aq.id, {})
                image_file = request.FILES.get(f'image_{aq.id}')

                selected_ids = payload.get('selected_choice_ids') or []
                if question.type in (QuestionType.SINGLE, QuestionType.MULTIPLE):
                    # Only keep choice ids that actually belong to this question.
                    valid_ids = set(
                        question.choices.filter(id__in=selected_ids)
                        .values_list('id', flat=True)
                    )
                else:
                    valid_ids = set()

                is_correct, needs_review = self._grade(
                    question,
                    payload=payload,
                    valid_ids=valid_ids,
                    image_file=image_file,
                    judge_key=judge_key,
                    judge_model=judge_model,
                    judge_base_url=judge_base_url,
                )

                answer = Answer.objects.create(
                    attempt_question=aq,
                    text_response=payload.get('text') or '',
                    numerical_response=self._to_decimal(payload.get('numerical')),
                    is_correct=is_correct,
                    needs_review=needs_review,
                )
                if valid_ids:
                    answer.selected_choices.set(Choice.objects.filter(id__in=valid_ids))
                if image_file:
                    answer.image_response = image_file
                    answer.save(update_fields=['image_response'])

                if is_correct:
                    score += 1

            attempt.score = score
            attempt.submitted_at = timezone.now()
            attempt.save(update_fields=['score', 'submitted_at'])

        # Re-fetch so the prefetch cache includes the answers just created.
        attempt = self._get_attempt(attempt.id)
        return Response(AttemptReviewSerializer(attempt).data)

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _judge_key(request):
        """Return the per-request judge API key, if the client supplied one.

        The value is only read into a local variable and returned; it is never
        stored on the model, cached, or logged.
        """
        return (request.data.get('judge_api_key') or '').strip() or None

    @staticmethod
    def _grade(question, *, payload, valid_ids, image_file, judge_key,
               judge_model, judge_base_url):
        """Grade one answer, using the AI judge for text/image when possible.

        Deterministic types always use the exact rules in ``grading``. Text and
        image answers are sent to the judge only when a key is present and there
        is something to judge; a successful verdict sets ``needs_review=False``.
        On a missing key or any judge failure we fall back to the existing
        heuristic grading (which keeps ``needs_review=True``).
        """
        if judge_key:
            verdict = None
            if question.type == QuestionType.TEXT:
                verdict = judge_module.judge_text(
                    question, payload.get('text'),
                    api_key=judge_key, model=judge_model, base_url=judge_base_url,
                )
            elif question.type == QuestionType.IMAGE and image_file:
                data_url = judge_module.image_to_data_url(image_file)
                verdict = judge_module.judge_image(
                    question, data_url,
                    api_key=judge_key, model=judge_model, base_url=judge_base_url,
                )
            if verdict is not None:
                return bool(verdict['correct']), False

        return grade_answer(
            question,
            text=payload.get('text'),
            numerical=payload.get('numerical'),
            selected_ids=valid_ids,
            has_image=bool(image_file),
        )

    def _get_attempt(self, pk):
        return (
            Attempt.objects
            .prefetch_related(
                'attempt_questions__question__choices',
                'attempt_questions__answer__selected_choices',
            )
            .filter(pk=pk)
            .first()
        )

    @staticmethod
    def _parse_answers(request):
        raw = request.data.get('answers')
        if raw is None:
            return {}
        if isinstance(raw, (list, dict)):
            data = raw
        else:
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                return None
        if not isinstance(data, list):
            return None
        result = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            aq_id = item.get('attempt_question_id')
            if aq_id is not None:
                result[int(aq_id)] = item
        return result

    @staticmethod
    def _to_decimal(value):
        if value in (None, ''):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None


# ---------------------------------------------------------------------------
# Authentication (session-based) for the admin question bank
# ---------------------------------------------------------------------------
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get('username') or '').strip()
        password = request.data.get('password') or ''
        user = authenticate(request, username=username, password=password)
        if user is None or not user.is_staff:
            return Response(
                {'detail': 'Invalid credentials or not a staff account.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        login(request, user)
        return Response({'username': user.username, 'is_staff': user.is_staff})


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response({'detail': 'Logged out.'})


@api_view(['GET'])
@permission_classes([AllowAny])
def me_view(request):
    user = request.user
    if user.is_authenticated:
        return Response({'username': user.username, 'is_staff': user.is_staff})
    return Response({'username': None, 'is_staff': False})


@method_decorator(ensure_csrf_cookie, name='get')
class CsrfView(APIView):
    """Sets the ``csrftoken`` cookie so the SPA can send it on mutating calls."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'detail': 'CSRF cookie set.'})
