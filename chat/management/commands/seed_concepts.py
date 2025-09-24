"""
Management command to seed the database with grammar concepts for language learning.

This command populates the GrammarConcept model with fundamental grammar
concepts for English, Spanish, and German, organized by CEFR levels.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from chat.models import GrammarConcept


class Command(BaseCommand):
    help = "Seed the database with grammar concepts for language learning"

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing concepts before seeding',
        )
        parser.add_argument(
            '--language',
            type=str,
            choices=['en', 'es', 'de', 'all'],
            default='all',
            help='Language to seed (default: all)',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing grammar concepts...')
            GrammarConcept.objects.all().delete()

        language = options['language']

        with transaction.atomic():
            if language in ['en', 'all']:
                self._seed_english_concepts()
            if language in ['es', 'all']:
                self._seed_spanish_concepts()
            if language in ['de', 'all']:
                self._seed_german_concepts()

        total_concepts = GrammarConcept.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully seeded {total_concepts} grammar concepts!'
            )
        )

    def _create_concept(self, **kwargs):
        """Helper to create or get a grammar concept."""
        concept, created = GrammarConcept.objects.get_or_create(
            name=kwargs['name'], language=kwargs['language'], defaults=kwargs
        )
        if created:
            self.stdout.write(f"Created: {concept.name} ({concept.language})")
        return concept

    def _seed_english_concepts(self):
        """Seed English grammar concepts."""
        self.stdout.write('Seeding English grammar concepts...')

        # A1 Level Concepts
        concepts_a1 = [
            {
                'name': 'Present Simple - Be Verb',
                'description': 'Using "am/is/are" in present tense',
                'cefr_level': 'A1',
                'complexity_score': 1.0,
                'tags': ['verbs', 'be', 'present'],
                'example_sentences': [
                    'I am a student.',
                    'She is happy.',
                    'They are friends.',
                ],
                'common_errors': ['I am have...', 'She are...', 'They is...'],
            },
            {
                'name': 'Articles - A/An',
                'description': 'Using indefinite articles correctly',
                'cefr_level': 'A1',
                'complexity_score': 2.0,
                'tags': ['articles', 'indefinite'],
                'example_sentences': [
                    'I have a car.',
                    'She is an engineer.',
                    'This is a book.',
                ],
                'common_errors': ['I have an car.', 'She is a engineer.', 'A hour...'],
            },
            {
                'name': 'Plural Nouns',
                'description': 'Regular and irregular plural forms',
                'cefr_level': 'A1',
                'complexity_score': 2.5,
                'tags': ['nouns', 'plurals'],
                'example_sentences': [
                    'I have two cats.',
                    'The children are playing.',
                    'Three boxes on the table.',
                ],
                'common_errors': ['Two cat', 'Childs are playing', 'Three box'],
            },
        ]

        # A2 Level Concepts
        concepts_a2 = [
            {
                'name': 'Past Simple - Regular Verbs',
                'description': 'Past tense of regular verbs with -ed',
                'cefr_level': 'A2',
                'complexity_score': 3.0,
                'tags': ['verbs', 'past', 'regular'],
                'example_sentences': [
                    'I worked yesterday.',
                    'She visited her friend.',
                    'They played football.',
                ],
                'common_errors': [
                    'I work yesterday',
                    'She visit her friend',
                    'They play football',
                ],
            },
            {
                'name': 'Present Continuous',
                'description': 'Present progressive tense (am/is/are + -ing)',
                'cefr_level': 'A2',
                'complexity_score': 3.5,
                'tags': ['verbs', 'present', 'continuous'],
                'example_sentences': [
                    'I am reading a book.',
                    'She is cooking dinner.',
                    'They are studying.',
                ],
                'common_errors': [
                    'I reading a book',
                    'She cooking dinner',
                    'They are study',
                ],
            },
        ]

        # B1 Level Concepts
        concepts_b1 = [
            {
                'name': 'Present Perfect',
                'description': 'Present perfect tense (have/has + past participle)',
                'cefr_level': 'B1',
                'complexity_score': 5.0,
                'tags': ['verbs', 'present-perfect', 'tenses'],
                'example_sentences': [
                    'I have lived here for five years.',
                    'She has finished her homework.',
                    'They have never been to Paris.',
                ],
                'common_errors': [
                    'I have live here for five years',
                    'She has finish her homework',
                    'They have never go to Paris',
                ],
            },
            {
                'name': 'Conditional Sentences - First Type',
                'description': 'Real conditional sentences (if + present, will + base)',
                'cefr_level': 'B1',
                'complexity_score': 6.0,
                'tags': ['conditionals', 'future', 'if-clauses'],
                'example_sentences': [
                    'If it rains, I will stay home.',
                    'If you study hard, you will pass the exam.',
                    'I will call you if I have time.',
                ],
                'common_errors': [
                    'If it will rain, I will stay home',
                    'If you will study hard, you pass the exam',
                    'I call you if I will have time',
                ],
            },
        ]

        # Create all English concepts
        all_concepts = concepts_a1 + concepts_a2 + concepts_b1
        for concept_data in all_concepts:
            concept_data['language'] = 'en'
            self._create_concept(**concept_data)

    def _seed_spanish_concepts(self):
        """Seed Spanish grammar concepts."""
        self.stdout.write('Seeding Spanish grammar concepts...')

        concepts = [
            {
                'name': 'Ser vs Estar',
                'description': 'Distinguishing between permanent and temporary states',
                'cefr_level': 'A2',
                'complexity_score': 4.0,
                'tags': ['verbs', 'ser', 'estar', 'state'],
                'example_sentences': [
                    'Ella es doctora. (She is a doctor)',
                    'Ella está enferma. (She is sick)',
                    'El café es caliente. (Coffee is hot by nature)',
                ],
                'common_errors': [
                    'Ella está doctora',
                    'Ella es enferma',
                    'El café está caliente (when referring to temperature)',
                ],
            },
            {
                'name': 'Gender Agreement - Nouns and Adjectives',
                'description': 'Matching gender between nouns and adjectives',
                'cefr_level': 'A1',
                'complexity_score': 3.0,
                'tags': ['gender', 'nouns', 'adjectives'],
                'example_sentences': [
                    'La casa blanca (the white house)',
                    'El coche rojo (the red car)',
                    'Las flores bonitas (the beautiful flowers)',
                ],
                'common_errors': [
                    'La casa blanco',
                    'El coche roja',
                    'Las flores bonitos',
                ],
            },
            {
                'name': 'Subjunctive Mood - Present',
                'description': 'Using present subjunctive for doubt, emotion, desire',
                'cefr_level': 'B2',
                'complexity_score': 7.0,
                'tags': ['verbs', 'subjunctive', 'mood'],
                'example_sentences': [
                    'Espero que tengas un buen día.',
                    'Es importante que estudies.',
                    'Dudo que venga mañana.',
                ],
                'common_errors': [
                    'Espero que tienes un buen día',
                    'Es importante que estudias',
                    'Dudo que viene mañana',
                ],
            },
        ]

        for concept_data in concepts:
            concept_data['language'] = 'es'
            self._create_concept(**concept_data)

    def _seed_german_concepts(self):
        """Seed German grammar concepts."""
        self.stdout.write('Seeding German grammar concepts...')

        concepts = [
            {
                'name': 'Nominative Case',
                'description': 'Subject case for nouns and pronouns',
                'cefr_level': 'A1',
                'complexity_score': 2.5,
                'tags': ['cases', 'nominative', 'articles'],
                'example_sentences': [
                    'Der Mann ist groß. (The man is tall)',
                    'Die Frau liest. (The woman reads)',
                    'Das Kind spielt. (The child plays)',
                ],
                'common_errors': [
                    'Den Mann ist groß',
                    'Der Frau liest',
                    'Die Kind spielt',
                ],
            },
            {
                'name': 'Accusative Case',
                'description': 'Direct object case',
                'cefr_level': 'A2',
                'complexity_score': 4.0,
                'tags': ['cases', 'accusative', 'direct-object'],
                'example_sentences': [
                    'Ich sehe den Mann. (I see the man)',
                    'Er kauft das Buch. (He buys the book)',
                    'Sie kennt die Lehrerin. (She knows the teacher)',
                ],
                'common_errors': [
                    'Ich sehe der Mann',
                    'Er kauft der Buch',
                    'Sie kennt der Lehrerin',
                ],
            },
            {
                'name': 'Dative Case',
                'description': 'Indirect object case',
                'cefr_level': 'A2',
                'complexity_score': 5.0,
                'tags': ['cases', 'dative', 'indirect-object'],
                'example_sentences': [
                    'Ich gebe dem Mann das Buch. (I give the book to the man)',
                    'Sie hilft der Frau. (She helps the woman)',
                    'Das gehört dem Kind. (That belongs to the child)',
                ],
                'common_errors': [
                    'Ich gebe den Mann das Buch',
                    'Sie hilft die Frau',
                    'Das gehört das Kind',
                ],
            },
            {
                'name': 'Separable Verbs',
                'description': 'Verbs with separable prefixes',
                'cefr_level': 'B1',
                'complexity_score': 6.0,
                'tags': ['verbs', 'separable', 'prefixes'],
                'example_sentences': [
                    'Ich stehe um 7 Uhr auf. (I get up at 7 o\'clock)',
                    'Er ruft seine Mutter an. (He calls his mother)',
                    'Wir kaufen morgen ein. (We shop tomorrow)',
                ],
                'common_errors': [
                    'Ich aufstehe um 7 Uhr',
                    'Er anruft seine Mutter',
                    'Wir einkaufen morgen',
                ],
            },
        ]

        for concept_data in concepts:
            concept_data['language'] = 'de'
            self._create_concept(**concept_data)
