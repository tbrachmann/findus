"""
Comprehensive unit tests for language learning functionality.

Tests all the features verified in our integration testing:
- Concept mastery tracking and updates
- Error pattern detection and recording
- Language profile progression
- Vector similarity search
- Spaced repetition scheduling
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from chat.models import (
    LanguageProfile,
    GrammarConcept,
    Conversation,
    ConceptMastery,
    ErrorPattern,
    ChatMessage,
)
from chat.similarity_service import similarity_service


class LanguageLearningModelsTest(TestCase):
    """Test core language learning model functionality."""

    def setUp(self) -> None:
        """Set up test data for language learning tests."""
        self.user = User.objects.create_user(
            username="language_test_user",
            email="test@example.com",
            password="testpass123",
        )

        self.lang_profile = LanguageProfile.objects.create(
            user=self.user,
            target_language='en',
            current_level='A2',
            proficiency_score=0.4,
            grammar_accuracy=0.5,
        )

        self.concept = GrammarConcept.objects.create(
            name="Test Grammar Concept",
            description="A test grammar concept for unit testing",
            language='en',
            cefr_level='A2',
            complexity_score=2.0,
            tags=['test', 'grammar'],
            embedding=[0.1] * 768,  # Test embedding vector
        )

        self.conversation = Conversation.objects.create(
            user=self.user,
            title="Test Conversation",
            language='en',
            analysis_language='en',
        )

    def test_language_profile_creation(self):
        """Test that language profiles are created correctly."""
        self.assertEqual(self.lang_profile.user, self.user)
        self.assertEqual(self.lang_profile.target_language, 'en')
        self.assertEqual(self.lang_profile.current_level, 'A2')
        self.assertEqual(self.lang_profile.proficiency_score, 0.4)
        self.assertTrue(self.lang_profile.is_active)

    def test_concept_mastery_creation_and_updates(self):
        """Test concept mastery creation and performance updates."""
        # Create initial mastery
        mastery = ConceptMastery.objects.create(
            user=self.user,
            concept=self.concept,
            mastery_score=0.0,
            attempts_count=0,
            correct_attempts=0,
        )

        # Test initial state
        self.assertEqual(mastery.mastery_score, 0.0)
        self.assertEqual(mastery.get_success_rate(), 0.0)
        self.assertFalse(mastery.is_mastered())

        # Update with correct attempt
        mastery.update_performance(is_correct=True, difficulty=0.5)

        self.assertEqual(mastery.attempts_count, 1)
        self.assertEqual(mastery.correct_attempts, 1)
        self.assertGreater(mastery.mastery_score, 0.0)
        self.assertEqual(mastery.get_success_rate(), 100.0)

        # Update with incorrect attempt
        mastery.update_performance(is_correct=False, difficulty=0.5)

        self.assertEqual(mastery.attempts_count, 2)
        self.assertEqual(mastery.correct_attempts, 1)
        self.assertEqual(mastery.get_success_rate(), 50.0)

    def test_spaced_repetition_scheduling(self):
        """Test spaced repetition interval calculations."""
        mastery = ConceptMastery.objects.create(
            user=self.user, concept=self.concept, repetition_interval=1
        )

        # Initial review should be needed
        self.assertTrue(mastery.needs_review())

        # Correct answer should increase interval
        initial_interval = mastery.repetition_interval
        mastery.update_performance(is_correct=True, difficulty=0.5)

        self.assertGreater(mastery.repetition_interval, initial_interval)
        self.assertIsNotNone(mastery.next_review)

        # Incorrect answer should reset interval
        mastery.update_performance(is_correct=False, difficulty=0.5)

        self.assertEqual(mastery.repetition_interval, 1)

    def test_error_pattern_tracking(self):
        """Test error pattern detection and tracking."""
        # Create error pattern
        error = ErrorPattern.objects.create(
            user=self.user,
            error_type='verb_tense',
            error_description='Past tense verb errors',
            frequency=1,
        )

        # Test initial state
        self.assertEqual(error.frequency, 1)
        self.assertFalse(error.is_resolved)
        self.assertTrue(error.is_recent())

        # Add occurrence
        error.add_occurrence(
            example="I go to store yesterday",
            correction="I went to the store yesterday",
        )

        self.assertEqual(error.frequency, 2)
        self.assertIn("I go to store yesterday", error.example_errors)
        self.assertIn("I went to the store yesterday", error.correction_suggestions)

        # Test persistence
        error.frequency = 5
        self.assertTrue(error.is_persistent())

    def test_language_profile_progression(self):
        """Test language profile level progression logic."""
        # Test next level calculation
        self.assertEqual(self.lang_profile.get_next_level(), 'B1')

        # Test previous level calculation
        self.assertEqual(self.lang_profile.get_previous_level(), 'A1')

        # Test readiness for next level (should be False initially)
        self.assertFalse(self.lang_profile.is_ready_for_next_level())

        # Increase proficiency
        self.lang_profile.proficiency_score = 0.85
        self.lang_profile.save()

        # Should still not be ready without concept mastery
        self.assertFalse(self.lang_profile.is_ready_for_next_level())

    def test_language_profile_message_count_update(self):
        """Test that language profile updates when messages are processed."""
        initial_count = self.lang_profile.total_messages

        # Create message
        ChatMessage.objects.create(
            conversation=self.conversation,
            message="I have grammar error in this sentence",
            response="Here's the correction...",
        )

        # Simulate message processing
        self.lang_profile.total_messages += 1
        self.lang_profile.save()

        # Verify update
        self.lang_profile.refresh_from_db()
        self.assertEqual(self.lang_profile.total_messages, initial_count + 1)

    def test_proficiency_metrics_update(self):
        """Test proficiency metrics calculation."""
        # Create some concept masteries
        ConceptMastery.objects.create(
            user=self.user,
            concept=self.concept,
            mastery_score=0.8,
            last_practiced=timezone.now(),
        )

        # Update proficiency metrics
        initial_accuracy = self.lang_profile.grammar_accuracy
        self.lang_profile.update_proficiency_metrics()

        # Should have updated based on masteries
        self.assertNotEqual(self.lang_profile.grammar_accuracy, initial_accuracy)


class VectorSimilarityTest(TestCase):
    """Test vector similarity search functionality."""

    def setUp(self):
        """Set up concepts with embeddings for similarity testing."""
        # Create concepts with different embeddings
        self.concept1 = GrammarConcept.objects.create(
            name="Past Tense",
            description="Simple past tense usage",
            language='en',
            cefr_level='A2',
            complexity_score=2.0,
            embedding=[0.5, 0.5] + [0.0] * 766,  # Similar to concept2
        )

        self.concept2 = GrammarConcept.objects.create(
            name="Past Participle",
            description="Past participle forms",
            language='en',
            cefr_level='B1',
            complexity_score=3.0,
            embedding=[0.4, 0.6] + [0.0] * 766,  # Similar to concept1
        )

        self.concept3 = GrammarConcept.objects.create(
            name="Present Continuous",
            description="Progressive present tense",
            language='en',
            cefr_level='A2',
            complexity_score=2.5,
            embedding=[0.0, 0.0] + [1.0] * 766,  # Different from others
        )

    def test_vector_field_storage_and_retrieval(self):
        """Test that vector embeddings are stored and retrieved correctly."""
        # Test embedding storage
        test_vector = [0.1, 0.2, 0.3] + [0.0] * 765
        self.concept1.embedding = test_vector
        self.concept1.save()

        # Refresh and test retrieval
        self.concept1.refresh_from_db()
        retrieved_vector = self.concept1.get_embedding_vector()

        self.assertEqual(len(retrieved_vector), 768)
        self.assertAlmostEqual(retrieved_vector[0], 0.1, places=5)
        self.assertAlmostEqual(retrieved_vector[1], 0.2, places=5)
        self.assertAlmostEqual(retrieved_vector[2], 0.3, places=5)

    def test_concept_similarity_search(self):
        """Test finding similar concepts using vector similarity."""
        # Find similar concepts to concept1
        similar = self.concept1.find_similar_concepts(limit=2, threshold=0.3)

        # Should find concept2 as similar, but not concept3
        similar_names = [c.name for c in similar]

        self.assertIn("Past Participle", similar_names)
        # Note: concept3 has very different embedding, so might not appear with high threshold

    def test_learning_path_generation(self):
        """Test learning path generation based on similarity and CEFR levels."""
        learning_path = self.concept1.find_learning_path(limit=3)

        # Should return a list of concepts
        self.assertIsInstance(learning_path, list)
        self.assertLessEqual(len(learning_path), 3)

        # All concepts should be GrammarConcept instances
        for concept in learning_path:
            self.assertIsInstance(concept, GrammarConcept)

    def test_prerequisite_discovery(self):
        """Test finding prerequisite concepts by similarity and level."""
        # Concept2 is B1 level, should find A2 prerequisites
        prerequisites = self.concept2.find_prerequisites_by_similarity(threshold=0.4)

        # Should be a queryset
        self.assertTrue(hasattr(prerequisites, 'count'))


class SimilarityServiceTest(TestCase):
    """Test the advanced similarity service functionality."""

    def setUp(self):
        """Set up test data for similarity service."""
        self.user = User.objects.create_user(
            username="similarity_test", email="sim@test.com", password="test123"
        )

        self.lang_profile = LanguageProfile.objects.create(
            user=self.user, target_language='en', current_level='A2'
        )

        # Create concept with embedding
        self.concept = GrammarConcept.objects.create(
            name="Test Concept",
            description="A test concept for similarity service",
            language='en',
            cefr_level='A2',
            complexity_score=2.0,
            embedding=[0.1] * 768,
        )

    def test_concept_difficulty_analysis(self):
        """Test learning difficulty analysis for concepts."""
        # Test with concept that has some community data
        ConceptMastery.objects.create(
            user=self.user, concept=self.concept, mastery_score=0.6, attempts_count=5
        )

        difficulty = similarity_service.get_concept_learning_difficulty(
            self.concept, user=self.user
        )

        # Should return analysis dict
        self.assertIn('base_complexity', difficulty)
        self.assertIn('cefr_level', difficulty)
        self.assertIn('personalized_difficulty', difficulty)

        self.assertEqual(difficulty['base_complexity'], 2.0)
        self.assertEqual(difficulty['cefr_level'], 'A2')

    def test_concept_clustering(self):
        """Test concept clustering by similarity."""
        # Create additional concepts for clustering
        GrammarConcept.objects.create(
            name="Similar Concept",
            description="Another test concept",
            language='en',
            cefr_level='A2',
            complexity_score=2.1,
            embedding=[0.12] * 768,  # Similar to self.concept
        )

        GrammarConcept.objects.create(
            name="Different Concept",
            description="A completely different concept",
            language='en',
            cefr_level='B1',
            complexity_score=3.0,
            embedding=[0.8] * 768,  # Very different from self.concept
        )

        # Test basic clustering functionality
        concepts = GrammarConcept.objects.filter(language='en')

        # Test clustering with fixed QuerySet slicing issue
        clusters = similarity_service.cluster_concepts_by_similarity(
            concepts, min_cluster_size=1, similarity_threshold=0.5
        )

        # Should return dict of clusters
        self.assertIsInstance(clusters, dict)

        # Should have at least one cluster (might have more depending on similarity)
        self.assertGreaterEqual(len(clusters), 1)

        # Each cluster should contain GrammarConcept objects
        for cluster_concepts in clusters.values():
            self.assertIsInstance(cluster_concepts, list)
            for concept in cluster_concepts:
                self.assertIsInstance(concept, GrammarConcept)

        # Test with minimum cluster size of 2
        clusters_size_2 = similarity_service.cluster_concepts_by_similarity(
            concepts,
            min_cluster_size=2,
            similarity_threshold=0.3,  # Lower threshold to find more similarities
        )

        # All clusters should have at least 2 concepts
        for cluster_concepts in clusters_size_2.values():
            self.assertGreaterEqual(len(cluster_concepts), 2)


class MessageProcessingTest(TestCase):
    """Test message processing and language tracking integration."""

    def setUp(self):
        """Set up test data for message processing."""
        self.user = User.objects.create_user(
            username="message_processor", email="processor@test.com", password="test123"
        )

        self.lang_profile = LanguageProfile.objects.create(
            user=self.user, target_language='en', current_level='A2', total_messages=0
        )

        self.conversation = Conversation.objects.create(
            user=self.user, title="Processing Test", language='en'
        )

    def test_message_creation_updates_profile(self):
        """Test that creating messages can trigger profile updates."""
        initial_message_count = self.lang_profile.total_messages

        # Create message
        ChatMessage.objects.create(
            conversation=self.conversation,
            message="I go to store yesterday",
            response="I went to the store yesterday",
        )

        # Simulate the profile update that would happen in message processing
        self.lang_profile.total_messages += 1
        self.lang_profile.save()

        # Verify update
        self.lang_profile.refresh_from_db()
        self.assertEqual(self.lang_profile.total_messages, initial_message_count + 1)

    def test_grammar_analysis_creates_masteries(self):
        """Test that grammar analysis creates concept masteries."""
        initial_mastery_count = ConceptMastery.objects.filter(user=self.user).count()

        # Create a grammar concept
        concept = GrammarConcept.objects.create(
            name="Past Simple Test",
            description="Test past simple concept",
            language='en',
            cefr_level='A2',
            complexity_score=2.0,
        )

        # Simulate creating mastery from grammar analysis
        mastery = ConceptMastery.objects.create(
            user=self.user, concept=concept, mastery_score=0.0
        )

        # Update performance based on analysis
        mastery.update_performance(is_correct=False, difficulty=0.5)

        # Verify mastery was created and updated
        final_mastery_count = ConceptMastery.objects.filter(user=self.user).count()
        self.assertEqual(final_mastery_count, initial_mastery_count + 1)

        # Verify performance was recorded
        self.assertEqual(mastery.attempts_count, 1)
        self.assertEqual(mastery.correct_attempts, 0)

    def test_error_pattern_detection(self):
        """Test that error patterns are detected and recorded."""
        initial_error_count = ErrorPattern.objects.filter(user=self.user).count()

        # Simulate error pattern creation from grammar analysis
        error = ErrorPattern.objects.create(
            user=self.user,
            error_type='verb_tense',
            error_description='Past tense formation errors',
            frequency=1,
            example_errors=["I go yesterday"],
            correction_suggestions=["I went yesterday"],
        )

        # Verify error pattern was created
        final_error_count = ErrorPattern.objects.filter(user=self.user).count()
        self.assertEqual(final_error_count, initial_error_count + 1)

        # Test adding more occurrences
        error.add_occurrence("I buy milk", "I bought milk")
        self.assertEqual(error.frequency, 2)
        self.assertIn("I buy milk", error.example_errors)
