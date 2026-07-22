"""Tests for the quiz platform: grading, validation, and the attempt flow."""

import io
import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from PIL import Image

from quiz.grading import (
    grade_multiple,
    grade_numerical,
    grade_single,
    grade_text,
)
from quiz.models import (
    Answer,
    Attempt,
    AttemptQuestion,
    Choice,
    Difficulty,
    Question,
    QuestionType,
    TextMatchMode,
)


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
        self.text = Question.objects.create(
            type=QuestionType.TEXT, prompt='ocean', text_answers=['Pacific'],
            text_match_mode=TextMatchMode.EXACT)
        self.image = Question.objects.create(
            type=QuestionType.IMAGE, prompt='upload',
            image_requirement='any image')

    def _start(self, player='alice', judge_api_key='sk-test'):
        # A judge key is supplied so the full 5-type bank (including text and
        # image) is served; without a key the pool is deterministic-only.
        body = {'player': player}
        if judge_api_key:
            body['judge_api_key'] = judge_api_key
        res = self.client.post('/api/attempts/', body, format='json')
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
            entry['numerical'] = 4 if correct else 99
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


class RandomnessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        for i in range(20):
            Question.objects.create(type=QuestionType.TEXT, prompt=f'Q{i}',
                                    text_answers=['a'])

    def test_attempts_are_independently_randomized(self):
        # The bank here is all text questions, so a judge key is needed to
        # include them in the pool.
        body = {'player': 'x', 'judge_api_key': 'sk-test'}
        r1 = self.client.post('/api/attempts/', body, format='json')
        r2 = self.client.post('/api/attempts/', body, format='json')
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

class JudgeStartPoolTests(TestCase):
    """The presence of a judge API key controls which question types are drawn."""

    def setUp(self):
        self.client = APIClient()
        self.single = make_choice_question(
            QuestionType.SINGLE, [('Right', True), ('Wrong', False)])
        self.numerical = Question.objects.create(
            type=QuestionType.NUMERICAL, prompt='2+2',
            numerical_answer=Decimal('4'), numerical_tolerance=Decimal('0'))
        self.text = Question.objects.create(
            type=QuestionType.TEXT, prompt='Explain X',
            text_answers=['foo'], text_match_mode=TextMatchMode.EXACT)
        self.image = Question.objects.create(
            type=QuestionType.IMAGE, prompt='upload',
            image_requirement='a blue thing')

    def test_start_without_key_excludes_text_and_image(self):
        res = self.client.post('/api/attempts/', {'player': 'a'}, format='json')
        self.assertEqual(res.status_code, 201)
        types = {aq['question']['type'] for aq in res.data['questions']}
        self.assertNotIn('text', types)
        self.assertNotIn('image', types)
        # Only the two deterministic questions remain in the pool.
        self.assertEqual(res.data['total'], 2)

    def test_start_with_key_includes_text_and_image(self):
        res = self.client.post(
            '/api/attempts/',
            {'player': 'a', 'judge_api_key': 'sk-test'},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        types = {aq['question']['type'] for aq in res.data['questions']}
        self.assertIn('text', types)
        self.assertIn('image', types)
        self.assertEqual(res.data['total'], 4)


class JudgeSubmitTests(TestCase):
    """Submit-time grading of text/image answers via the (mocked) AI judge.

    The single network boundary ``quiz.judge._call_chat_completion`` is patched
    so no real HTTP request is ever made.
    """

    def setUp(self):
        self.client = APIClient()

    def _attempt_with(self, question):
        attempt = Attempt.objects.create(player='a', total=1)
        aq = AttemptQuestion.objects.create(
            attempt=attempt, question=question, order=0)
        return attempt, aq

    def _submit(self, attempt, extra):
        return self.client.post(
            f'/api/attempts/{attempt.id}/submit/', extra, format='multipart')

    def test_submit_with_key_marks_text_correct_from_verdict(self):
        q = Question.objects.create(
            type=QuestionType.TEXT, prompt='q', text_answers=['foo'],
            text_match_mode=TextMatchMode.EXACT)
        attempt, aq = self._attempt_with(q)
        # Response does NOT match the accepted answer, so the heuristic alone
        # would fail it; the judge's "correct" verdict must win.
        answers = [{'attempt_question_id': aq.id, 'text': 'a long explanation'}]
        with mock.patch(
            'quiz.judge._call_chat_completion',
            return_value='{"correct": true, "reason": "good"}',
        ) as called:
            res = self._submit(attempt, {
                'answers': json.dumps(answers), 'judge_api_key': 'sk-test'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(called.called)
        self.assertEqual(res.data['score'], 1)
        answer = res.data['questions'][0]['answer']
        self.assertTrue(answer['is_correct'])
        self.assertFalse(answer['needs_review'])

    def test_submit_with_key_marks_text_incorrect_from_verdict(self):
        q = Question.objects.create(
            type=QuestionType.TEXT, prompt='q', text_answers=['foo'],
            text_match_mode=TextMatchMode.EXACT)
        attempt, aq = self._attempt_with(q)
        # Response DOES match the accepted answer (heuristic would pass it), but
        # the judge's "incorrect" verdict must win.
        answers = [{'attempt_question_id': aq.id, 'text': 'foo'}]
        with mock.patch(
            'quiz.judge._call_chat_completion',
            return_value='{"correct": false, "reason": "off topic"}',
        ) as called:
            res = self._submit(attempt, {
                'answers': json.dumps(answers), 'judge_api_key': 'sk-test'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(called.called)
        self.assertEqual(res.data['score'], 0)
        answer = res.data['questions'][0]['answer']
        self.assertFalse(answer['is_correct'])
        self.assertFalse(answer['needs_review'])

    def test_submit_with_key_grades_image_from_verdict(self):
        q = Question.objects.create(
            type=QuestionType.IMAGE, prompt='q', image_requirement='blue')
        attempt, aq = self._attempt_with(q)
        answers = [{'attempt_question_id': aq.id}]
        # The heuristic would accept any uploaded image; the judge's "incorrect"
        # verdict must win and clear needs_review.
        with mock.patch(
            'quiz.judge._call_chat_completion',
            return_value='{"correct": false, "reason": "not blue"}',
        ) as called:
            res = self._submit(attempt, {
                'answers': json.dumps(answers),
                'judge_api_key': 'sk-test',
                f'image_{aq.id}': make_image_upload(),
            })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(called.called)
        self.assertEqual(res.data['score'], 0)
        answer = res.data['questions'][0]['answer']
        self.assertFalse(answer['is_correct'])
        self.assertFalse(answer['needs_review'])
        self.assertTrue(answer['image_response'])

    def test_submit_with_key_marks_image_correct_from_verdict(self):
        q = Question.objects.create(
            type=QuestionType.IMAGE, prompt='q', image_requirement='blue')
        attempt, aq = self._attempt_with(q)
        answers = [{'attempt_question_id': aq.id}]
        with mock.patch(
            'quiz.judge._call_chat_completion',
            return_value='{"correct": true, "reason": "blue enough"}',
        ):
            res = self._submit(attempt, {
                'answers': json.dumps(answers),
                'judge_api_key': 'sk-test',
                f'image_{aq.id}': make_image_upload(),
            })
        self.assertEqual(res.status_code, 200)
        answer = res.data['questions'][0]['answer']
        self.assertTrue(answer['is_correct'])
        self.assertFalse(answer['needs_review'])

    def test_submit_without_key_falls_back_to_heuristic(self):
        q = Question.objects.create(
            type=QuestionType.TEXT, prompt='q', text_answers=['foo'],
            text_match_mode=TextMatchMode.EXACT)
        attempt, aq = self._attempt_with(q)
        answers = [{'attempt_question_id': aq.id, 'text': 'foo'}]
        with mock.patch('quiz.judge._call_chat_completion') as called:
            res = self._submit(attempt, {'answers': json.dumps(answers)})
        self.assertEqual(res.status_code, 200)
        # No key -> the judge (and its HTTP boundary) is never invoked.
        self.assertFalse(called.called)
        answer = res.data['questions'][0]['answer']
        # Heuristic exact match still grades it and flags it for review.
        self.assertTrue(answer['is_correct'])
        self.assertTrue(answer['needs_review'])

    def test_submit_with_key_but_judge_error_falls_back(self):
        q = Question.objects.create(
            type=QuestionType.TEXT, prompt='q', text_answers=['foo'],
            text_match_mode=TextMatchMode.EXACT)
        attempt, aq = self._attempt_with(q)
        answers = [{'attempt_question_id': aq.id, 'text': 'foo'}]
        with mock.patch(
            'quiz.judge._call_chat_completion',
            side_effect=RuntimeError('network down'),
        ) as called:
            res = self._submit(attempt, {
                'answers': json.dumps(answers), 'judge_api_key': 'sk-test'})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(called.called)
        answer = res.data['questions'][0]['answer']
        # Judge failed -> heuristic grading with needs_review preserved.
        self.assertTrue(answer['is_correct'])
        self.assertTrue(answer['needs_review'])


class JudgeUnitTests(TestCase):
    """Unit tests for the judge module's parsing and encoding helpers."""

    def test_parse_verdict_handles_plain_json(self):
        from quiz import judge
        verdict = judge._parse_verdict('{"correct": true, "reason": "ok"}')
        self.assertEqual(verdict, {'correct': True, 'reason': 'ok'})

    def test_parse_verdict_extracts_embedded_json(self):
        from quiz import judge
        verdict = judge._parse_verdict('Sure! {"correct": false, "reason": "no"}')
        self.assertEqual(verdict['correct'], False)

    def test_parse_verdict_rejects_garbage(self):
        from quiz import judge
        self.assertIsNone(judge._parse_verdict('not json at all'))

    def test_judge_text_without_key_returns_none(self):
        from quiz import judge
        q = Question.objects.create(
            type=QuestionType.TEXT, prompt='q', text_answers=['foo'])
        self.assertIsNone(judge.judge_text(q, 'foo', api_key=None))

    def test_image_to_data_url_roundtrip(self):
        from quiz import judge
        upload = make_image_upload()
        data_url = judge.image_to_data_url(upload)
        self.assertTrue(data_url.startswith('data:'))
        self.assertIn(';base64,', data_url)
