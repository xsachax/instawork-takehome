"""Tests for the quiz platform: grading, validation, and the attempt flow."""

import base64
import io
import json
from unittest import mock
from decimal import Decimal

import requests
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from PIL import Image

from quiz.grading import (
    grade_multiple,
    grade_numerical,
    grade_single,
    grade_text,
)
from quiz.models import (
    Choice,
    Difficulty,
    Question,
    QuestionType,
    TextMatchMode,
)
from quiz import judge
from quiz.judge import JudgeVerdict


def make_choice_question(qtype, options):
    q = Question.objects.create(type=qtype, prompt='Q', category='Test',
                                difficulty=Difficulty.EASY)
    for i, (text, correct) in enumerate(options):
        Choice.objects.create(question=q, text=text, is_correct=correct, order=i)
    return q


def make_image_upload(name='test.png'):
    buffer = io.BytesIO()
    Image.new('RGB', (10, 10), 'blue').save(buffer, format='PNG')
    buffer.seek(0)
    buffer.name = name
    return buffer


class GradingUnitTests(TestCase):
    def test_single_choice_exact(self):
        q = make_choice_question(QuestionType.SINGLE,
                                 [('A', True), ('B', False), ('C', False)])
        correct_id = q.choices.get(text='A').id
        wrong_id = q.choices.get(text='B').id
        self.assertTrue(grade_single(q, [correct_id]))
        self.assertFalse(grade_single(q, [wrong_id]))
        self.assertFalse(grade_single(q, [correct_id, wrong_id]))
        self.assertFalse(grade_single(q, []))

    def test_multiple_choice_all_or_nothing(self):
        q = make_choice_question(QuestionType.MULTIPLE,
                                 [('A', True), ('B', True), ('C', False)])
        a = q.choices.get(text='A').id
        b = q.choices.get(text='B').id
        c = q.choices.get(text='C').id
        self.assertTrue(grade_multiple(q, [a, b]))
        self.assertFalse(grade_multiple(q, [a]))          # partial
        self.assertFalse(grade_multiple(q, [a, b, c]))    # extra wrong
        self.assertFalse(grade_multiple(q, []))

    def test_numerical_tolerance(self):
        q = Question.objects.create(type=QuestionType.NUMERICAL, prompt='pi',
                                    numerical_answer=Decimal('3.14'),
                                    numerical_tolerance=Decimal('0.01'))
        self.assertTrue(grade_numerical(q, '3.14'))
        self.assertTrue(grade_numerical(q, 3.15))
        self.assertFalse(grade_numerical(q, 3.2))
        self.assertFalse(grade_numerical(q, 'not a number'))

    def test_text_exact_normalized(self):
        q = Question.objects.create(type=QuestionType.TEXT, prompt='ocean',
                                    text_answers=['Pacific', 'Pacific Ocean'],
                                    text_match_mode=TextMatchMode.EXACT)
        self.assertTrue(grade_text(q, 'pacific'))
        self.assertTrue(grade_text(q, '  Pacific!! '))
        self.assertFalse(grade_text(q, 'Atlantic'))
        self.assertFalse(grade_text(q, ''))

    def test_text_contains_any(self):
        q = Question.objects.create(type=QuestionType.TEXT, prompt='api',
                                    text_answers=['interface'],
                                    text_match_mode=TextMatchMode.CONTAINS_ANY)
        self.assertTrue(grade_text(q, 'It is an interface between systems'))
        self.assertFalse(grade_text(q, 'a way to call code'))


class QuestionValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user('admin', password='pass12345',
                                               is_staff=True)
        self.client.force_authenticate(self.staff)

    def test_single_choice_requires_exactly_one_correct(self):
        payload = {
            'type': 'single', 'prompt': 'Pick one', 'category': 'X',
            'difficulty': 'easy',
            'choices': [
                {'text': 'A', 'is_correct': True},
                {'text': 'B', 'is_correct': True},
            ],
        }
        res = self.client.post('/api/questions/', payload, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('choices', res.data)

    def test_multiple_choice_requires_at_least_one_correct(self):
        payload = {
            'type': 'multiple', 'prompt': 'Pick some', 'difficulty': 'easy',
            'choices': [
                {'text': 'A', 'is_correct': False},
                {'text': 'B', 'is_correct': False},
            ],
        }
        res = self.client.post('/api/questions/', payload, format='json')
        self.assertEqual(res.status_code, 400)

    def test_numerical_requires_answer(self):
        res = self.client.post('/api/questions/',
                               {'type': 'numerical', 'prompt': '2+2'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('numerical_answer', res.data)

    def test_text_requires_answer(self):
        res = self.client.post('/api/questions/',
                               {'type': 'text', 'prompt': 'name'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_image_requires_requirement(self):
        res = self.client.post('/api/questions/',
                               {'type': 'image', 'prompt': 'upload'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_valid_single_choice_creates(self):
        payload = {
            'type': 'single', 'prompt': 'Pick one', 'difficulty': 'easy',
            'choices': [
                {'text': 'A', 'is_correct': True},
                {'text': 'B', 'is_correct': False},
            ],
        }
        res = self.client.post('/api/questions/', payload, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(len(res.data['choices']), 2)

    def test_update_replaces_choices(self):
        create = self.client.post('/api/questions/', {
            'type': 'single', 'prompt': 'Pick one', 'difficulty': 'easy',
            'choices': [
                {'text': 'A', 'is_correct': True},
                {'text': 'B', 'is_correct': False},
            ],
        }, format='json')
        qid = create.data['id']
        res = self.client.put(f'/api/questions/{qid}/', {
            'type': 'single', 'prompt': 'Pick one (edited)', 'difficulty': 'medium',
            'choices': [
                {'text': 'X', 'is_correct': False},
                {'text': 'Y', 'is_correct': True},
            ],
        }, format='json')
        self.assertEqual(res.status_code, 200)
        texts = sorted(c['text'] for c in res.data['choices'])
        self.assertEqual(texts, ['X', 'Y'])


class QuestionPermissionTests(TestCase):
    def test_anonymous_cannot_manage_questions(self):
        client = APIClient()
        self.assertEqual(client.get('/api/questions/').status_code, 403)
        res = client.post('/api/questions/', {'type': 'text', 'prompt': 'x'},
                          format='json')
        self.assertEqual(res.status_code, 403)


class AttemptFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # A small bank with known answers across several types.
        self.single = make_choice_question(QuestionType.SINGLE,
                                            [('Right', True), ('Wrong', False)])
        self.multiple = make_choice_question(
            QuestionType.MULTIPLE, [('A', True), ('B', True), ('C', False)])
        self.numerical = Question.objects.create(
            type=QuestionType.NUMERICAL, prompt='2+2',
            numerical_answer=Decimal('4'), numerical_tolerance=Decimal('0'))
        self.single_extra = make_choice_question(
            QuestionType.SINGLE, [('Yes', True), ('No', False)])
        self.numerical_extra = Question.objects.create(
            type=QuestionType.NUMERICAL, prompt='3+3',
            numerical_answer=Decimal('6'), numerical_tolerance=Decimal('0'))
        self.text = Question.objects.create(
            type=QuestionType.TEXT, prompt='ocean', text_answers=['Pacific'],
            text_match_mode=TextMatchMode.EXACT)
        self.image = Question.objects.create(
            type=QuestionType.IMAGE, prompt='upload',
            image_requirement='any image')

    def _start(self, player='alice'):
        res = self.client.post('/api/attempts/', {'player': player}, format='json')
        self.assertEqual(res.status_code, 201)
        return res.data

    def test_start_requires_player(self):
        res = self.client.post('/api/attempts/', {}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_start_returns_questions_without_answers(self):
        data = self._start()
        self.assertEqual(data['total'], 5)
        self.assertEqual(len(data['questions']), 5)
        # No correct-answer fields leak to the player.
        for aq in data['questions']:
            q = aq['question']
            self.assertNotIn('numerical_answer', q)
            self.assertNotIn('text_answers', q)
            for choice in q['choices']:
                self.assertNotIn('is_correct', choice)

    def test_questions_do_not_repeat_within_attempt(self):
        data = self._start()
        qids = [aq['question']['id'] for aq in data['questions']]
        self.assertEqual(len(qids), len(set(qids)))

    def test_start_without_judge_key_excludes_text_and_image(self):
        data = self._start()
        types = {aq['question']['type'] for aq in data['questions']}
        self.assertTrue(types <= {
            QuestionType.SINGLE,
            QuestionType.MULTIPLE,
            QuestionType.NUMERICAL,
        })
        self.assertNotIn(QuestionType.TEXT, types)
        self.assertNotIn(QuestionType.IMAGE, types)

    def _answer_for(self, aq, correct=True):
        q = aq['question']
        entry = {'attempt_question_id': aq['id']}
        if q['type'] == 'single':
            ids = [c['id'] for c in q['choices']]
            entry['selected_choice_ids'] = [ids[0] if correct else ids[-1]]
        elif q['type'] == 'multiple':
            ids = [c['id'] for c in q['choices']]
            entry['selected_choice_ids'] = ids[:2] if correct else ids[:1]
        elif q['type'] == 'numerical':
            if correct:
                entry['numerical'] = 4 if q['id'] == self.numerical.id else 6
            else:
                entry['numerical'] = 99
        elif q['type'] == 'text':
            entry['text'] = 'Pacific' if correct else 'Atlantic'
        return entry

    def test_full_correct_submission_scores_max(self):
        data = self._start()
        attempt_id = data['id']
        answers = []
        files = {}
        for aq in data['questions']:
            if aq['question']['type'] == 'image':
                files[f'image_{aq["id"]}'] = make_image_upload()
                answers.append({'attempt_question_id': aq['id']})
            else:
                answers.append(self._answer_for(aq, correct=True))
        payload = {'answers': json.dumps(answers)}
        payload.update(files)
        res = self.client.post(f'/api/attempts/{attempt_id}/submit/', payload,
                               format='multipart')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['score'], 5)
        self.assertEqual(res.data['total'], 5)
        for aq in res.data['questions']:
            self.assertTrue(aq['answer']['is_correct'])

    def test_wrong_answers_score_zero(self):
        data = self._start()
        attempt_id = data['id']
        answers = []
        for aq in data['questions']:
            if aq['question']['type'] == 'image':
                # No image uploaded -> incorrect.
                answers.append({'attempt_question_id': aq['id']})
            else:
                answers.append(self._answer_for(aq, correct=False))
        res = self.client.post(f'/api/attempts/{attempt_id}/submit/',
                               {'answers': json.dumps(answers)}, format='multipart')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['score'], 0)

    def test_cannot_submit_twice(self):
        data = self._start()
        attempt_id = data['id']
        answers = [{'attempt_question_id': aq['id']} for aq in data['questions']]
        first = self.client.post(f'/api/attempts/{attempt_id}/submit/',
                                 {'answers': json.dumps(answers)}, format='multipart')
        self.assertEqual(first.status_code, 200)
        second = self.client.post(f'/api/attempts/{attempt_id}/submit/',
                                  {'answers': json.dumps(answers)}, format='multipart')
        self.assertEqual(second.status_code, 400)

    def test_history_lists_player_attempts(self):
        self._start('bob')
        self._start('bob')
        self._start('carol')
        res = self.client.get('/api/attempts/?player=bob')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 2)

    def test_review_exposes_correct_answers(self):
        data = self._start()
        attempt_id = data['id']
        answers = [{'attempt_question_id': aq['id']} for aq in data['questions']]
        self.client.post(f'/api/attempts/{attempt_id}/submit/',
                         {'answers': json.dumps(answers)}, format='multipart')
        res = self.client.get(f'/api/attempts/{attempt_id}/')
        self.assertEqual(res.status_code, 200)
        for aq in res.data['questions']:
            self.assertIn('answer', aq)
            self.assertIn(aq['question']['type'], dict(QuestionType.choices))

    def test_in_progress_attempt_does_not_leak_answers(self):
        data = self._start()
        res = self.client.get(f'/api/attempts/{data["id"]}/')
        self.assertEqual(res.status_code, 200)
        # Not yet submitted: no answer/correct-answer fields exposed.
        for aq in res.data['questions']:
            self.assertNotIn('answer', aq)
            self.assertNotIn('text_answers', aq['question'])
            for choice in aq['question']['choices']:
                self.assertNotIn('is_correct', choice)


class JudgeAttemptTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @override_settings(QUIZ_QUESTION_COUNT=2)
    def test_start_with_judge_key_permits_text_and_image(self):
        Question.objects.create(
            type=QuestionType.TEXT, prompt='ocean', text_answers=['Pacific'])
        Question.objects.create(
            type=QuestionType.IMAGE, prompt='upload',
            image_requirement='a blue object')

        res = self.client.post('/api/attempts/', {
            'player': 'alice',
            'judge_api_key': 'sk-test',
        }, format='json')

        self.assertEqual(res.status_code, 201)
        types = {aq['question']['type'] for aq in res.data['questions']}
        self.assertEqual(types, {QuestionType.TEXT, QuestionType.IMAGE})
        self.assertNotIn('sk-test', json.dumps(res.data))

    def _start_single_question_attempt(self, question):
        res = self.client.post('/api/attempts/', {
            'player': 'alice',
            'judge_api_key': 'sk-test',
        }, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['questions'][0]['question']['id'], question.id)
        return res.data

    @override_settings(QUIZ_QUESTION_COUNT=1)
    @mock.patch('quiz.judge._call_chat_completion')
    def test_submit_with_judge_key_marks_text_correct(self, mock_chat):
        mock_chat.return_value = '{"correct": true, "reason": "matches"}'
        question = Question.objects.create(
            type=QuestionType.TEXT, prompt='ocean', text_answers=['Pacific'])
        data = self._start_single_question_attempt(question)
        aq = data['questions'][0]

        res = self.client.post(f'/api/attempts/{data["id"]}/submit/', {
            'answers': json.dumps([{
                'attempt_question_id': aq['id'],
                'text': 'Atlantic',
            }]),
            'judge_api_key': 'sk-test',
        }, format='multipart')

        self.assertEqual(res.status_code, 200)
        answer = res.data['questions'][0]['answer']
        self.assertTrue(answer['is_correct'])
        self.assertFalse(answer['needs_review'])
        self.assertEqual(res.data['score'], 1)
        self.assertNotIn('sk-test', json.dumps(res.data))
        mock_chat.assert_called_once()

    @override_settings(QUIZ_QUESTION_COUNT=1)
    @mock.patch('quiz.judge._call_chat_completion')
    def test_submit_with_judge_key_marks_text_incorrect(self, mock_chat):
        mock_chat.return_value = '{"correct": false, "reason": "too vague"}'
        question = Question.objects.create(
            type=QuestionType.TEXT, prompt='ocean', text_answers=['Pacific'])
        data = self._start_single_question_attempt(question)
        aq = data['questions'][0]

        res = self.client.post(f'/api/attempts/{data["id"]}/submit/', {
            'answers': json.dumps([{
                'attempt_question_id': aq['id'],
                'text': 'Pacific',
            }]),
            'judge_api_key': 'sk-test',
        }, format='multipart')

        self.assertEqual(res.status_code, 200)
        answer = res.data['questions'][0]['answer']
        self.assertFalse(answer['is_correct'])
        self.assertFalse(answer['needs_review'])
        self.assertEqual(res.data['score'], 0)
        mock_chat.assert_called_once()

    @override_settings(QUIZ_QUESTION_COUNT=1)
    @mock.patch('quiz.judge._call_chat_completion')
    def test_submit_with_judge_key_marks_image_from_verdict(self, mock_chat):
        mock_chat.return_value = '{"correct": false, "reason": "not visible"}'
        question = Question.objects.create(
            type=QuestionType.IMAGE, prompt='upload',
            image_requirement='a blue object')
        data = self._start_single_question_attempt(question)
        aq = data['questions'][0]

        res = self.client.post(f'/api/attempts/{data["id"]}/submit/', {
            'answers': json.dumps([{'attempt_question_id': aq['id']}]),
            f'image_{aq["id"]}': make_image_upload(),
            'judge_api_key': 'sk-test',
        }, format='multipart')

        self.assertEqual(res.status_code, 200)
        answer = res.data['questions'][0]['answer']
        self.assertFalse(answer['is_correct'])
        self.assertFalse(answer['needs_review'])
        self.assertEqual(res.data['score'], 0)
        mock_chat.assert_called_once()

    @override_settings(QUIZ_QUESTION_COUNT=1)
    @mock.patch('quiz.judge._call_chat_completion')
    def test_submit_without_judge_key_falls_back_to_review(self, mock_chat):
        question = Question.objects.create(
            type=QuestionType.TEXT, prompt='ocean', text_answers=['Pacific'],
            text_match_mode=TextMatchMode.EXACT)
        data = self._start_single_question_attempt(question)
        aq = data['questions'][0]

        res = self.client.post(f'/api/attempts/{data["id"]}/submit/', {
            'answers': json.dumps([{
                'attempt_question_id': aq['id'],
                'text': 'Pacific',
            }]),
        }, format='multipart')

        self.assertEqual(res.status_code, 200)
        answer = res.data['questions'][0]['answer']
        self.assertTrue(answer['is_correct'])
        self.assertTrue(answer['needs_review'])
        mock_chat.assert_not_called()

    @override_settings(QUIZ_QUESTION_COUNT=1)
    @mock.patch('quiz.judge._call_chat_completion')
    def test_submit_with_judge_key_marks_image_correct(self, mock_chat):
        mock_chat.return_value = '{"correct": true, "reason": "matches"}'
        question = Question.objects.create(
            type=QuestionType.IMAGE, prompt='upload',
            image_requirement='a blue object')
        data = self._start_single_question_attempt(question)
        aq = data['questions'][0]

        res = self.client.post(f'/api/attempts/{data["id"]}/submit/', {
            'answers': json.dumps([{'attempt_question_id': aq['id']}]),
            f'image_{aq["id"]}': make_image_upload(),
            'judge_api_key': 'sk-test',
        }, format='multipart')

        self.assertEqual(res.status_code, 200)
        answer = res.data['questions'][0]['answer']
        self.assertTrue(answer['is_correct'])
        self.assertFalse(answer['needs_review'])
        self.assertEqual(res.data['score'], 1)
        mock_chat.assert_called_once()

    @override_settings(QUIZ_QUESTION_COUNT=1)
    @mock.patch('quiz.judge._call_chat_completion')
    def test_submit_with_judge_key_falls_back_when_judge_errors(self, mock_chat):
        # A None result stands in for a network error, timeout, or unparseable
        # response: the request should not fail; grading falls back to the
        # heuristic and flags the answer for review.
        mock_chat.return_value = None
        question = Question.objects.create(
            type=QuestionType.TEXT, prompt='ocean', text_answers=['Pacific'],
            text_match_mode=TextMatchMode.EXACT)
        data = self._start_single_question_attempt(question)
        aq = data['questions'][0]

        res = self.client.post(f'/api/attempts/{data["id"]}/submit/', {
            'answers': json.dumps([{
                'attempt_question_id': aq['id'],
                'text': 'Pacific',
            }]),
            'judge_api_key': 'sk-test',
        }, format='multipart')

        self.assertEqual(res.status_code, 200)
        answer = res.data['questions'][0]['answer']
        self.assertTrue(answer['is_correct'])
        self.assertTrue(answer['needs_review'])
        mock_chat.assert_called_once()


class RandomnessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        for i in range(20):
            Question.objects.create(type=QuestionType.NUMERICAL, prompt=f'Q{i}',
                                    numerical_answer=i)

    def test_attempts_are_independently_randomized(self):
        r1 = self.client.post('/api/attempts/', {'player': 'x'}, format='json')
        r2 = self.client.post('/api/attempts/', {'player': 'x'}, format='json')
        ids1 = [aq['question']['id'] for aq in r1.data['questions']]
        ids2 = [aq['question']['id'] for aq in r2.data['questions']]
        self.assertEqual(len(ids1), 5)
        # With 20 questions, two 5-question draws being identical is very unlikely.
        self.assertNotEqual(ids1, ids2)


class AuthEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User.objects.create_user('staffer', password='pass12345', is_staff=True)
        User.objects.create_user('plain', password='pass12345', is_staff=False)

    def test_login_requires_staff(self):
        res = self.client.post('/api/auth/login/',
                               {'username': 'plain', 'password': 'pass12345'},
                               format='json')
        self.assertEqual(res.status_code, 401)

    def test_login_rejects_bad_password(self):
        res = self.client.post('/api/auth/login/',
                               {'username': 'staffer', 'password': 'wrong'},
                               format='json')
        self.assertEqual(res.status_code, 401)

    def test_login_and_me_and_logout(self):
        login = self.client.post('/api/auth/login/',
                                 {'username': 'staffer', 'password': 'pass12345'},
                                 format='json')
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.data['is_staff'])

        me = self.client.get('/api/auth/me/')
        self.assertEqual(me.data['username'], 'staffer')

        self.client.post('/api/auth/logout/')
        me_after = self.client.get('/api/auth/me/')
        self.assertIsNone(me_after.data['username'])


class QuestionCrudTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        staff = User.objects.create_user('admin', password='pass12345',
                                          is_staff=True)
        self.client.force_authenticate(staff)

    def test_delete_question(self):
        create = self.client.post('/api/questions/', {
            'type': 'text', 'prompt': 'to delete', 'text_answers': ['x'],
        }, format='json')
        qid = create.data['id']
        res = self.client.delete(f'/api/questions/{qid}/')
        self.assertEqual(res.status_code, 204)
        self.assertEqual(Question.objects.filter(id=qid).count(), 0)

    def test_filter_by_type(self):
        self.client.post('/api/questions/', {
            'type': 'text', 'prompt': 'a', 'text_answers': ['x'],
        }, format='json')
        self.client.post('/api/questions/', {
            'type': 'numerical', 'prompt': 'b', 'numerical_answer': 1,
        }, format='json')
        res = self.client.get('/api/questions/?type=numerical')
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['type'], 'numerical')


class ScoreOverrideTests(TestCase):
    def test_recompute_score_after_manual_override(self):
        from quiz.models import Answer, Attempt, AttemptQuestion

        question = Question.objects.create(
            type=QuestionType.IMAGE, prompt='upload',
            image_requirement='any image')
        attempt = Attempt.objects.create(player='eve', total=1,
                                         submitted_at='2026-01-01T00:00:00Z')
        aq = AttemptQuestion.objects.create(attempt=attempt, question=question)
        answer = Answer.objects.create(attempt_question=aq, is_correct=True,
                                       needs_review=True)
        attempt.recompute_score()
        attempt.refresh_from_db()
        self.assertEqual(attempt.score, 1)

        # Staff overrides the image answer as incorrect.
        answer.is_correct = False
        answer.save(update_fields=['is_correct'])
        attempt.recompute_score()
        attempt.refresh_from_db()
        self.assertEqual(attempt.score, 0)


class JudgeUnitTests(TestCase):
    """Unit coverage for the judge module internals (no network)."""

    def test_parse_verdict_handles_plain_json(self):
        verdict = judge._parse_judge_content('{"correct": true, "reason": "ok"}')
        self.assertIsInstance(verdict, JudgeVerdict)
        self.assertTrue(verdict.correct)
        self.assertEqual(verdict.reason, 'ok')

    def test_parse_verdict_extracts_embedded_json(self):
        verdict = judge._parse_judge_content(
            'Sure: {"correct": false, "reason": "nope"} — done')
        self.assertIsInstance(verdict, JudgeVerdict)
        self.assertFalse(verdict.correct)

    def test_parse_verdict_rejects_garbage(self):
        self.assertIsNone(judge._parse_judge_content('not json at all'))
        self.assertIsNone(judge._parse_judge_content(None))

    def test_image_to_data_url_roundtrip(self):
        data_url = judge._image_to_data_url(make_image_upload())
        self.assertTrue(data_url.startswith('data:image/png;base64,'))
        encoded = data_url.split(',', 1)[1]
        self.assertTrue(base64.b64decode(encoded).startswith(b'\x89PNG'))

    def test_call_chat_completion_returns_none_on_request_error(self):
        with mock.patch('quiz.judge.requests.post',
                        side_effect=requests.RequestException('boom')):
            result = judge._call_chat_completion(
                api_key='sk-test', base_url=None, model=None, messages=[])
        self.assertIsNone(result)
