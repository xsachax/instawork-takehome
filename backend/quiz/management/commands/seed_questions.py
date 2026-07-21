"""Populate the question bank with a varied set of sample questions.

Run with::

    python manage.py seed_questions            # add sample questions
    python manage.py seed_questions --flush     # wipe questions first

Covers all five question types (text, single, multiple, numerical, image) across
a range of categories and difficulties.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from quiz.models import Choice, Question, QuestionType, Difficulty, TextMatchMode


QUESTIONS = [
    # ----- Single choice -----
    {
        'type': QuestionType.SINGLE, 'category': 'Geography', 'difficulty': Difficulty.EASY,
        'prompt': 'What is the capital of France?',
        'choices': [('Paris', True), ('London', False), ('Berlin', False), ('Madrid', False)],
    },
    {
        'type': QuestionType.SINGLE, 'category': 'Science', 'difficulty': Difficulty.EASY,
        'prompt': 'Which planet is known as the Red Planet?',
        'choices': [('Venus', False), ('Mars', True), ('Jupiter', False), ('Saturn', False)],
    },
    {
        'type': QuestionType.SINGLE, 'category': 'Programming', 'difficulty': Difficulty.MEDIUM,
        'prompt': 'Which keyword defines a function in Python?',
        'choices': [('func', False), ('def', True), ('function', False), ('lambda', False)],
    },
    {
        'type': QuestionType.SINGLE, 'category': 'History', 'difficulty': Difficulty.MEDIUM,
        'prompt': 'In which year did World War II end?',
        'choices': [('1943', False), ('1945', True), ('1948', False), ('1950', False)],
    },
    {
        'type': QuestionType.SINGLE, 'category': 'Science', 'difficulty': Difficulty.HARD,
        'prompt': 'What is the chemical symbol for gold?',
        'choices': [('Go', False), ('Gd', False), ('Au', True), ('Ag', False)],
    },

    # ----- Multiple choice -----
    {
        'type': QuestionType.MULTIPLE, 'category': 'Programming', 'difficulty': Difficulty.MEDIUM,
        'prompt': 'Which of the following are Python data types? (select all that apply)',
        'choices': [('list', True), ('tuple', True), ('array', False), ('dict', True)],
    },
    {
        'type': QuestionType.MULTIPLE, 'category': 'Geography', 'difficulty': Difficulty.MEDIUM,
        'prompt': 'Which of these countries are in Europe?',
        'choices': [('Portugal', True), ('Brazil', False), ('Norway', True), ('Egypt', False)],
    },
    {
        'type': QuestionType.MULTIPLE, 'category': 'Science', 'difficulty': Difficulty.HARD,
        'prompt': 'Which of the following are noble gases?',
        'choices': [('Helium', True), ('Oxygen', False), ('Neon', True), ('Argon', True)],
    },
    {
        'type': QuestionType.MULTIPLE, 'category': 'Web', 'difficulty': Difficulty.EASY,
        'prompt': 'Which of these are front-end JavaScript frameworks/libraries?',
        'choices': [('React', True), ('Django', False), ('Vue', True), ('Svelte', True)],
    },

    # ----- Numerical -----
    {
        'type': QuestionType.NUMERICAL, 'category': 'Math', 'difficulty': Difficulty.EASY,
        'prompt': 'What is 7 x 8?',
        'numerical_answer': 56, 'numerical_tolerance': 0,
    },
    {
        'type': QuestionType.NUMERICAL, 'category': 'Math', 'difficulty': Difficulty.EASY,
        'prompt': 'How many sides does a hexagon have?',
        'numerical_answer': 6, 'numerical_tolerance': 0,
    },
    {
        'type': QuestionType.NUMERICAL, 'category': 'Math', 'difficulty': Difficulty.MEDIUM,
        'prompt': 'What is the value of pi rounded to two decimal places?',
        'numerical_answer': 3.14, 'numerical_tolerance': 0.01,
    },
    {
        'type': QuestionType.NUMERICAL, 'category': 'Science', 'difficulty': Difficulty.MEDIUM,
        'prompt': 'At what temperature (in degrees Celsius) does water boil at sea level?',
        'numerical_answer': 100, 'numerical_tolerance': 0,
    },
    {
        'type': QuestionType.NUMERICAL, 'category': 'Math', 'difficulty': Difficulty.HARD,
        'prompt': 'What is the square root of 144?',
        'numerical_answer': 12, 'numerical_tolerance': 0,
    },

    # ----- Text -----
    {
        'type': QuestionType.TEXT, 'category': 'Geography', 'difficulty': Difficulty.EASY,
        'prompt': 'What is the largest ocean on Earth?',
        'text_answers': ['Pacific', 'Pacific Ocean'], 'text_match_mode': TextMatchMode.EXACT,
    },
    {
        'type': QuestionType.TEXT, 'category': 'Programming', 'difficulty': Difficulty.MEDIUM,
        'prompt': 'What does HTML stand for?',
        'text_answers': ['HyperText Markup Language', 'Hyper Text Markup Language'],
        'text_match_mode': TextMatchMode.EXACT,
    },
    {
        'type': QuestionType.TEXT, 'category': 'Science', 'difficulty': Difficulty.MEDIUM,
        'prompt': 'Name the process by which plants make their food (one word).',
        'text_answers': ['photosynthesis'], 'text_match_mode': TextMatchMode.EXACT,
    },
    {
        'type': QuestionType.TEXT, 'category': 'General', 'difficulty': Difficulty.HARD,
        'prompt': 'In one sentence, explain what an API is. (must mention "interface")',
        'text_answers': ['interface'], 'text_match_mode': TextMatchMode.CONTAINS_ANY,
    },
    {
        'type': QuestionType.TEXT, 'category': 'History', 'difficulty': Difficulty.EASY,
        'prompt': 'Who was the first President of the United States?',
        'text_answers': ['George Washington', 'Washington'],
        'text_match_mode': TextMatchMode.EXACT,
    },

    # ----- Image upload -----
    {
        'type': QuestionType.IMAGE, 'category': 'Practical', 'difficulty': Difficulty.EASY,
        'prompt': 'Upload a photo of your handwritten name.',
        'image_requirement': 'An image showing your name written by hand.',
    },
    {
        'type': QuestionType.IMAGE, 'category': 'Practical', 'difficulty': Difficulty.MEDIUM,
        'prompt': 'Upload a screenshot of a "Hello, World!" program running.',
        'image_requirement': 'A screenshot where the text "Hello, World!" is visible in the output.',
    },
    {
        'type': QuestionType.IMAGE, 'category': 'Practical', 'difficulty': Difficulty.EASY,
        'prompt': 'Upload a picture of something blue.',
        'image_requirement': 'A photo whose main subject is predominantly blue.',
    },
]


class Command(BaseCommand):
    help = 'Seed the question bank with sample questions covering all types.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush', action='store_true',
            help='Delete all existing questions before seeding.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['flush']:
            deleted, _ = Question.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted existing questions ({deleted} rows).'))

        created = 0
        for data in QUESTIONS:
            choices = data.pop('choices', None)
            question = Question.objects.create(**data)
            if choices:
                for order, (text, is_correct) in enumerate(choices):
                    Choice.objects.create(
                        question=question, text=text, is_correct=is_correct, order=order
                    )
            created += 1

        by_type = {}
        for q in Question.objects.all():
            by_type[q.type] = by_type.get(q.type, 0) + 1

        self.stdout.write(self.style.SUCCESS(f'Seeded {created} questions.'))
        for qtype, count in sorted(by_type.items()):
            self.stdout.write(f'  {qtype}: {count}')
