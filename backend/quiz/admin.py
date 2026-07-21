"""Django admin registration for the question bank."""

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


admin.site.register(Answer)
