"""Django admin registration for the question bank and attempt review.

Staff can override auto-graded answers (e.g. image uploads or free-text) here;
saving an answer or running the "Recompute score" action keeps the parent
attempt's score in sync.
"""

from django.contrib import admin

from .models import Answer, Attempt, AttemptQuestion, Choice, Question


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'type', 'category', 'difficulty', 'prompt')
    list_filter = ('type', 'difficulty', 'category')
    search_fields = ('prompt', 'category')
    inlines = [ChoiceInline]


class AttemptQuestionInline(admin.TabularInline):
    model = AttemptQuestion
    extra = 0


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ('id', 'player', 'score', 'total', 'created_at', 'submitted_at')
    list_filter = ('player',)
    inlines = [AttemptQuestionInline]
    actions = ['recompute_scores']

    @admin.action(description='Recompute score from current answers')
    def recompute_scores(self, request, queryset):
        for attempt in queryset:
            attempt.recompute_score()
        self.message_user(request, f'Recomputed {queryset.count()} attempt(s).')


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('id', 'attempt_question', 'is_correct', 'needs_review')
    list_filter = ('is_correct', 'needs_review')
    list_editable = ('is_correct',)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Keep the attempt score consistent after a manual override.
        obj.attempt_question.attempt.recompute_score()
