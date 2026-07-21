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
        """Start a new attempt with N random, non-repeating questions."""
        player = (request.data.get('player') or '').strip()
        if not player:
            return Response(
                {'player': 'A player name is required to start a quiz.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        count = settings.QUIZ_QUESTION_COUNT
        question_ids = list(
            Question.objects.values_list('id', flat=True).order_by('?')[:count]
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

                is_correct, needs_review = grade_answer(
                    question,
                    text=payload.get('text'),
                    numerical=payload.get('numerical'),
                    selected_ids=valid_ids,
                    has_image=bool(image_file),
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
