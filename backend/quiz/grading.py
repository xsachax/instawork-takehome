"""Grading logic for each question type.

Kept separate from the views so the rules are easy to unit test.
"""

from decimal import Decimal, InvalidOperation
import re

from .models import QuestionType, TextMatchMode


def _normalize_text(value):
    """Lowercase, strip punctuation and collapse whitespace for fair matching."""
    if value is None:
        return ''
    value = str(value).lower().strip()
    value = re.sub(r'[^\w\s]', ' ', value)
    value = re.sub(r'\s+', ' ', value)
    return value.strip()


def grade_text(question, response):
    """Grade a free-response answer against the accepted answers/keywords."""
    accepted = [a for a in (question.text_answers or []) if str(a).strip()]
    if not accepted:
        # Nothing to match against -> cannot auto-grade positively.
        return False
    normalized_response = _normalize_text(response)
    if not normalized_response:
        return False

    normalized_accepted = [_normalize_text(a) for a in accepted]
    mode = question.text_match_mode or TextMatchMode.EXACT

    if mode == TextMatchMode.EXACT:
        return normalized_response in normalized_accepted
    if mode == TextMatchMode.CONTAINS_ALL:
        return all(kw and kw in normalized_response for kw in normalized_accepted)
    if mode == TextMatchMode.CONTAINS_ANY:
        return any(kw and kw in normalized_response for kw in normalized_accepted)
    return False


def grade_numerical(question, response):
    """Grade a numerical answer within the configured tolerance."""
    if question.numerical_answer is None or response is None:
        return False
    try:
        response_dec = Decimal(str(response))
    except (InvalidOperation, TypeError, ValueError):
        return False
    tolerance = question.numerical_tolerance or Decimal('0')
    return abs(response_dec - question.numerical_answer) <= tolerance


def grade_single(question, selected_ids):
    """Exactly the one correct choice must be selected."""
    correct = set(question.correct_choice_ids)
    selected = set(selected_ids or [])
    return len(selected) == 1 and selected == correct


def grade_multiple(question, selected_ids):
    """The selected set must exactly match the correct set (all-or-nothing)."""
    correct = set(question.correct_choice_ids)
    selected = set(selected_ids or [])
    return bool(correct) and selected == correct


def grade_image(question, has_image):
    """Image answers can't be verified by content automatically.

    We treat any uploaded image as meeting the requirement (correct) and flag it
    for optional staff review. Returns ``(is_correct, needs_review)``.
    """
    if has_image:
        return True, True
    return False, False


def grade_answer(question, *, text=None, numerical=None, selected_ids=None,
                 has_image=False):
    """Dispatch grading based on the question type.

    Returns a ``(is_correct, needs_review)`` tuple.
    """
    qtype = question.type
    if qtype == QuestionType.TEXT:
        return grade_text(question, text), True
    if qtype == QuestionType.NUMERICAL:
        return grade_numerical(question, numerical), False
    if qtype == QuestionType.SINGLE:
        return grade_single(question, selected_ids), False
    if qtype == QuestionType.MULTIPLE:
        return grade_multiple(question, selected_ids), False
    if qtype == QuestionType.IMAGE:
        return grade_image(question, has_image)
    return False, False
