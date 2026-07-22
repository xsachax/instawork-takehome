"""Data models for the quiz platform.

A ``Question`` belongs to a question bank and may be one of five types. Choice
based questions (single/multiple choice) own a set of ``Choice`` rows. Numerical
and text questions store their expected answer directly on the question. Image
upload questions store a free-text requirement that the uploaded image must meet.

When a player starts a quiz an ``Attempt`` is created together with a frozen set
of ``AttemptQuestion`` rows (a snapshot of the randomly selected questions). Each
answer the player submits is stored as an ``Answer`` linked to its
``AttemptQuestion``.
"""

from django.db import models


class QuestionType(models.TextChoices):
    TEXT = 'text', 'Text (free response)'
    SINGLE = 'single', 'Single choice'
    MULTIPLE = 'multiple', 'Multiple choice'
    NUMERICAL = 'numerical', 'Numerical input'
    IMAGE = 'image', 'Image upload'


class Difficulty(models.TextChoices):
    EASY = 'easy', 'Easy'
    MEDIUM = 'medium', 'Medium'
    HARD = 'hard', 'Hard'


class TextMatchMode(models.TextChoices):
    """How a free-response text answer is graded."""

    EXACT = 'exact', 'Exact (normalized) match'
    CONTAINS_ALL = 'contains_all', 'Answer contains all keywords'
    CONTAINS_ANY = 'contains_any', 'Answer contains any keyword'


class Question(models.Model):
    type = models.CharField(max_length=16, choices=QuestionType.choices)
    prompt = models.TextField()
    category = models.CharField(max_length=100, blank=True, default='General')
    difficulty = models.CharField(
        max_length=8, choices=Difficulty.choices, default=Difficulty.EASY
    )

    # Numerical questions.
    numerical_answer = models.DecimalField(
        max_digits=20, decimal_places=6, null=True, blank=True
    )
    numerical_tolerance = models.DecimalField(
        max_digits=20, decimal_places=6, null=True, blank=True, default=0
    )

    # Text questions. ``text_answers`` is a list of accepted answers / keywords.
    text_answers = models.JSONField(default=list, blank=True)
    text_match_mode = models.CharField(
        max_length=16,
        choices=TextMatchMode.choices,
        default=TextMatchMode.EXACT,
        blank=True,
    )

    # Image-upload questions. The requirement describes what a correct image
    # should contain; it is shown to the player and to staff who review answers.
    image_requirement = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_type_display()}] {self.prompt[:60]}'

    @property
    def correct_choice_ids(self):
        return list(
            self.choices.filter(is_correct=True).values_list('id', flat=True)
        )


class Choice(models.Model):
    question = models.ForeignKey(
        Question, related_name='choices', on_delete=models.CASCADE
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.text


class Attempt(models.Model):
    """One quiz run by a player, identified by a free-text username."""

    player = models.CharField(max_length=150, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.player} - {self.score}/{self.total}'

    @property
    def is_submitted(self):
        return self.submitted_at is not None

    def recompute_score(self):
        """Recalculate and persist the score from the current answers.

        Used after a staff member overrides an auto-graded answer (e.g. an image
        or free-text response) so the stored score stays consistent.
        """
        score = sum(
            1
            for aq in self.attempt_questions.all()
            if getattr(aq, 'answer', None) and aq.answer.is_correct
        )
        if score != self.score:
            self.score = score
            self.save(update_fields=['score'])
        return score


class AttemptQuestion(models.Model):
    """A frozen snapshot linking an attempt to one of its served questions."""

    attempt = models.ForeignKey(
        Attempt, related_name='attempt_questions', on_delete=models.CASCADE
    )
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        unique_together = [('attempt', 'question')]

    def __str__(self):
        return f'Attempt {self.attempt_id} - Q{self.question_id}'


class Answer(models.Model):
    attempt_question = models.OneToOneField(
        AttemptQuestion, related_name='answer', on_delete=models.CASCADE
    )

    # Response payloads (only the field relevant to the question type is used).
    text_response = models.TextField(blank=True, default='')
    numerical_response = models.DecimalField(
        max_digits=20, decimal_places=6, null=True, blank=True
    )
    selected_choices = models.ManyToManyField(Choice, blank=True)
    image_response = models.ImageField(upload_to='answers/', null=True, blank=True)

    is_correct = models.BooleanField(default=False)
    needs_review = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Answer for {self.attempt_question}'
