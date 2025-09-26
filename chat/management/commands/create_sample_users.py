"""
Management command to create sample users with language profiles for testing.

This command creates sample users with realistic language learning profiles
to demonstrate the multi-language support functionality.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from chat.models import UserProfile, LanguageProfile, GrammarConcept, ConceptMastery
from django.utils import timezone
from datetime import timedelta
import random


class Command(BaseCommand):
    help = "Create sample users with language profiles for testing"

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=3,
            help='Number of sample users to create (default: 3)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing sample users before creating new ones',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing sample users...')
            User.objects.filter(username__startswith='sample_user_').delete()

        count = options['count']

        with transaction.atomic():
            for i in range(count):
                self._create_sample_user(i + 1)

        total_users = User.objects.filter(username__startswith='sample_user_').count()
        total_profiles = LanguageProfile.objects.filter(
            user__username__startswith='sample_user_'
        ).count()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {total_users} sample users with {total_profiles} language profiles!'
            )
        )

    def _create_sample_user(self, user_number: int):
        """Create a sample user with realistic language profiles."""
        username = f'sample_user_{user_number}'

        # Create user
        user = User.objects.create_user(
            username=username,
            email=f'{username}@example.com',
            first_name=f'Sample',
            last_name=f'User {user_number}',
            password='testpass123',
        )

        # Create general user profile
        user_profile = UserProfile.objects.create(
            user=user,
            native_language='en',
            daily_goal_minutes=20,
            preferences={
                'notification_enabled': True,
                'difficulty_preference': 'adaptive',
                'feedback_style': 'detailed',
            },
        )

        self.stdout.write(f"Created user: {username}")

        # Create language profiles based on user pattern
        if user_number == 1:
            # Beginner Spanish learner
            self._create_language_profile(user, 'es', 'A1', 5, 2, 15)

        elif user_number == 2:
            # Intermediate German learner who also studies Spanish
            self._create_language_profile(user, 'de', 'B1', 45, 12, 89)
            self._create_language_profile(user, 'es', 'A2', 20, 6, 34)

        elif user_number == 3:
            # Advanced polyglot
            self._create_language_profile(user, 'es', 'B2', 120, 25, 180)
            self._create_language_profile(user, 'de', 'B1', 85, 18, 125)

        else:
            # Random profile for additional users
            languages = ['es', 'de']
            levels = ['A1', 'A2', 'B1', 'B2']

            for lang in random.sample(languages, random.randint(1, 2)):
                level = random.choice(levels)
                messages = random.randint(5, 150)
                practice_time = random.randint(messages * 2, messages * 5)

                self._create_language_profile(
                    user, lang, level, messages, practice_time
                )

    def _create_language_profile(
        self,
        user: User,
        language: str,
        level: str,
        total_messages: int,
        practice_time: int,
    ):
        """Create a language profile with realistic data."""

        # Calculate proficiency metrics based on level and activity
        level_scores = {
            'A1': (0.1, 0.3),
            'A2': (0.25, 0.45),
            'B1': (0.45, 0.65),
            'B2': (0.65, 0.85),
        }
        min_score, max_score = level_scores.get(level, (0.1, 0.3))
        proficiency_score = random.uniform(min_score, max_score)

        # Create the profile
        lang_profile = LanguageProfile.objects.create(
            user=user,
            target_language=language,
            current_level=level,
            total_messages=total_messages,
            total_practice_time=practice_time,
            last_activity=timezone.now() - timedelta(days=random.randint(0, 7)),
            proficiency_score=proficiency_score,
            confidence_level=random.uniform(0.6, 0.9),
            vocabulary_size=random.randint(100, 2000),
            grammar_accuracy=random.uniform(0.4, 0.9),
            fluency_score=random.uniform(0.3, 0.8),
            weak_areas=self._get_weak_areas(language, level),
            strong_areas=self._get_strong_areas(language, level),
            learning_goals=self._get_learning_goals(language, level),
            is_active=True,
        )

        # Create some concept masteries
        self._create_concept_masteries(user, language, level, total_messages)

        language_name = dict(
            LanguageProfile._meta.get_field('target_language').choices
        )[language]
        self.stdout.write(
            f"  → {language_name} profile: {level} level, {total_messages} messages"
        )

    def _create_concept_masteries(
        self, user: User, language: str, level: str, total_messages: int
    ):
        """Create realistic concept mastery data."""
        concepts = GrammarConcept.objects.filter(
            language=language, cefr_level__in=self._get_relevant_levels(level)
        )

        # Create masteries for a subset of concepts
        for concept in concepts[: min(len(concepts), total_messages // 5)]:
            # More practice for lower level concepts
            is_lower_level = concept.cefr_level < level
            attempts = random.randint(3, 15 if is_lower_level else 8)

            # Higher accuracy for concepts below current level
            if is_lower_level:
                success_rate = random.uniform(0.7, 0.95)
            else:
                success_rate = random.uniform(0.4, 0.8)

            correct_attempts = int(attempts * success_rate)

            ConceptMastery.objects.create(
                user=user,
                concept=concept,
                attempts_count=attempts,
                correct_attempts=correct_attempts,
                mastery_score=success_rate * random.uniform(0.8, 1.0),
                confidence_level=random.uniform(0.6, 0.9),
                last_practiced=timezone.now() - timedelta(days=random.randint(0, 14)),
                next_review=timezone.now() + timedelta(days=random.randint(1, 7)),
                ease_factor=random.uniform(2.0, 3.0),
                performance_history=[
                    {
                        'timestamp': (timezone.now() - timedelta(days=i)).isoformat(),
                        'correct': random.choice([True, False]),
                        'difficulty': random.uniform(0.2, 0.8),
                        'mastery_score': random.uniform(0.3, 0.9),
                        'success_rate': random.uniform(40.0, 90.0),
                    }
                    for i in range(min(5, attempts))
                ],
            )

    def _get_relevant_levels(self, current_level: str) -> list[str]:
        """Get CEFR levels relevant to current level."""
        level_order = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        try:
            current_index = level_order.index(current_level)
            # Include current level and one above
            return level_order[: current_index + 2]
        except ValueError:
            return ['A1', 'A2']

    def _get_weak_areas(self, language: str, level: str) -> list[str]:
        """Get typical weak areas for language and level."""
        weak_areas_map = {
            'es': {
                'A1': ['gender agreement', 'ser vs estar'],
                'A2': ['past tenses', 'subjunctive mood'],
                'B1': ['subjunctive mood', 'conditional sentences'],
                'B2': ['advanced subjunctive', 'complex tenses'],
            },
            'de': {
                'A1': ['case system', 'word order'],
                'A2': ['accusative case', 'dative case'],
                'B1': ['separable verbs', 'genitive case'],
                'B2': ['passive voice', 'complex sentence structure'],
            },
        }

        areas = weak_areas_map.get(language, {}).get(level, ['grammar', 'vocabulary'])
        return random.sample(areas, min(len(areas), random.randint(1, 3)))

    def _get_strong_areas(self, language: str, level: str) -> list[str]:
        """Get typical strong areas for language and level."""
        strong_areas_map = {
            'es': {
                'A1': ['pronunciation', 'basic vocabulary'],
                'A2': ['present tense', 'basic conversation'],
                'B1': ['reading comprehension', 'regular verbs'],
                'B2': ['complex vocabulary', 'writing skills'],
            },
            'de': {
                'A1': ['basic word order', 'pronunciation'],
                'A2': ['nominative case', 'basic vocabulary'],
                'B1': ['reading comprehension', 'modal verbs'],
                'B2': ['complex sentences', 'advanced vocabulary'],
            },
        }

        areas = strong_areas_map.get(language, {}).get(
            level, ['vocabulary', 'pronunciation']
        )
        return random.sample(areas, min(len(areas), random.randint(1, 2)))

    def _get_learning_goals(self, language: str, level: str) -> list[str]:
        """Get realistic learning goals for language and level."""
        goals_map = {
            'es': {
                'A1': ['Master basic conversations', 'Learn 500 common words'],
                'A2': ['Understand past tenses', 'Have simple discussions'],
                'B1': ['Watch Spanish movies', 'Write short essays'],
                'B2': ['Read Spanish literature', 'Discuss complex topics'],
            },
            'de': {
                'A1': ['Master German cases', 'Basic daily conversations'],
                'A2': ['Understand German news', 'Learn compound words'],
                'B1': ['Read German newspapers', 'Understand regional dialects'],
                'B2': ['Professional communication', 'Academic writing'],
            },
        }

        goals = goals_map.get(language, {}).get(
            level, ['Improve fluency', 'Expand vocabulary']
        )
        return random.sample(goals, min(len(goals), random.randint(1, 2)))
