"""Serializers for the quiz API.

Three flavours of question serialization are provided:

* ``QuestionSerializer`` — full admin representation with nested choices, used
  for the question bank CRUD. Contains the correct answers and runs validation.
* ``PlayerQuestionSerializer`` — what a player sees while taking a quiz. It never
  leaks correct answers.
* Review serializers — expose the player's answer alongside the correct answer
  for the results/review screen.
"""

from rest_framework import serializers

from .models import (
    Answer,
    Attempt,
    AttemptQuestion,
    Choice,
    Difficulty,
    Question,
    QuestionType,
)


# ---------------------------------------------------------------------------
# Admin (question bank) serializers
# ---------------------------------------------------------------------------
class ChoiceSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Choice
        fields = ['id', 'text', 'is_correct', 'order']


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, required=False)

    class Meta:
        model = Question
        fields = [
            'id', 'type', 'prompt', 'category', 'difficulty',
            'numerical_answer', 'numerical_tolerance',
            'text_answers', 'text_match_mode', 'image_requirement',
            'choices', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        # Merge incoming data with the existing instance for partial updates.
        qtype = attrs.get('type', getattr(self.instance, 'type', None))
        choices = attrs.get('choices')
        if choices is None and self.instance is not None:
            choices = ChoiceSerializer(self.instance.choices.all(), many=True).data

        errors = {}

        if qtype in (QuestionType.SINGLE, QuestionType.MULTIPLE):
            choices = choices or []
            if len(choices) < 2:
                errors['choices'] = 'Provide at least two choices.'
            else:
                correct = [c for c in choices if c.get('is_correct')]
                if qtype == QuestionType.SINGLE and len(correct) != 1:
                    errors['choices'] = 'Single-choice questions need exactly one correct choice.'
                if qtype == QuestionType.MULTIPLE and len(correct) < 1:
                    errors['choices'] = 'Multiple-choice questions need at least one correct choice.'

        elif qtype == QuestionType.NUMERICAL:
            answer = attrs.get('numerical_answer',
                               getattr(self.instance, 'numerical_answer', None))
            if answer is None:
                errors['numerical_answer'] = 'Numerical questions require a correct answer.'

        elif qtype == QuestionType.TEXT:
            answers = attrs.get('text_answers',
                                getattr(self.instance, 'text_answers', None)) or []
            answers = [a for a in answers if str(a).strip()]
            if not answers:
                errors['text_answers'] = 'Text questions require at least one accepted answer.'

        elif qtype == QuestionType.IMAGE:
            requirement = attrs.get('image_requirement',
                                    getattr(self.instance, 'image_requirement', '')) or ''
            if not requirement.strip():
                errors['image_requirement'] = 'Image questions require a requirement description.'

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def _sync_choices(self, question, choices_data):
        if choices_data is None:
            return
        keep_ids = []
        for index, choice in enumerate(choices_data):
            choice_id = choice.get('id')
            payload = {
                'text': choice.get('text', ''),
                'is_correct': choice.get('is_correct', False),
                'order': choice.get('order', index),
            }
            if choice_id and question.choices.filter(id=choice_id).exists():
                question.choices.filter(id=choice_id).update(**payload)
                keep_ids.append(choice_id)
            else:
                created = question.choices.create(**payload)
                keep_ids.append(created.id)
        # Remove choices that were dropped in an update.
        question.choices.exclude(id__in=keep_ids).delete()

    def create(self, validated_data):
        choices_data = validated_data.pop('choices', [])
        question = Question.objects.create(**validated_data)
        self._sync_choices(question, choices_data)
        return question

    def update(self, instance, validated_data):
        choices_data = validated_data.pop('choices', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        self._sync_choices(instance, choices_data)
        return instance


# ---------------------------------------------------------------------------
# Player-facing serializers (never leak correct answers)
# ---------------------------------------------------------------------------
class PlayerChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'text']


class PlayerQuestionSerializer(serializers.ModelSerializer):
    choices = PlayerChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'type', 'prompt', 'category', 'difficulty',
                  'image_requirement', 'choices']


class AttemptQuestionPlayerSerializer(serializers.ModelSerializer):
    question = PlayerQuestionSerializer(read_only=True)

    class Meta:
        model = AttemptQuestion
        fields = ['id', 'order', 'question']


class AttemptSerializer(serializers.ModelSerializer):
    """Summary of an attempt (used in history lists)."""

    class Meta:
        model = Attempt
        fields = ['id', 'player', 'created_at', 'submitted_at', 'score', 'total']


class AttemptStartSerializer(serializers.ModelSerializer):
    questions = AttemptQuestionPlayerSerializer(
        source='attempt_questions', many=True, read_only=True
    )

    class Meta:
        model = Attempt
        fields = ['id', 'player', 'created_at', 'total', 'questions']


# ---------------------------------------------------------------------------
# Review serializers (results screen — expose correct answers)
# ---------------------------------------------------------------------------
class ReviewChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'text', 'is_correct']


class ReviewQuestionSerializer(serializers.ModelSerializer):
    choices = ReviewChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'type', 'prompt', 'category', 'difficulty',
                  'numerical_answer', 'numerical_tolerance', 'text_answers',
                  'text_match_mode', 'image_requirement', 'choices']


class ReviewAnswerSerializer(serializers.ModelSerializer):
    selected_choice_ids = serializers.PrimaryKeyRelatedField(
        source='selected_choices', many=True, read_only=True
    )
    image_response = serializers.ImageField(read_only=True)

    class Meta:
        model = Answer
        fields = ['text_response', 'numerical_response', 'selected_choice_ids',
                  'image_response', 'is_correct', 'needs_review']


class ReviewAttemptQuestionSerializer(serializers.ModelSerializer):
    question = ReviewQuestionSerializer(read_only=True)
    answer = ReviewAnswerSerializer(read_only=True)

    class Meta:
        model = AttemptQuestion
        fields = ['id', 'order', 'question', 'answer']


class AttemptReviewSerializer(serializers.ModelSerializer):
    questions = ReviewAttemptQuestionSerializer(
        source='attempt_questions', many=True, read_only=True
    )

    class Meta:
        model = Attempt
        fields = ['id', 'player', 'created_at', 'submitted_at', 'score',
                  'total', 'questions']
