"""
Advanced similarity search service for grammar concepts.

This service provides sophisticated vector similarity search capabilities
including hybrid search, concept clustering, and personalized recommendations.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import timedelta
from django.db.models import QuerySet, Q, Avg, Count
from django.contrib.auth.models import User
from django.utils import timezone
from .models import GrammarConcept, ConceptMastery, LanguageProfile, ErrorPattern
from .embedding_service import embedding_service

logger = logging.getLogger(__name__)


class ConceptSimilarityService:
    """Service for advanced concept similarity search and recommendations."""

    def __init__(self) -> None:
        self.default_threshold = 0.5
        self.high_threshold = 0.7
        self.low_threshold = 0.3

    def find_similar_concepts(
        self,
        query_text: str,
        language: str = "en",
        user: Optional[User] = None,
        cefr_level: Optional[str] = None,
        limit: int = 10,
        include_mastery_info: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Find concepts similar to query text using hybrid search.

        Combines vector similarity with metadata filtering and user context.
        """
        results = []

        try:
            # Generate embedding for query
            import asyncio

            query_embedding = asyncio.run(
                embedding_service.generate_embedding(query_text, language)
            )

            # Base query with vector similarity
            concepts = GrammarConcept.objects.similarity_search(
                vector_field='embedding',
                query_vector=query_embedding,
                limit=limit * 2,  # Get more to filter
                threshold=self.default_threshold,
            ).filter(language=language)

            # Apply CEFR level filter if specified
            if cefr_level:
                concepts = concepts.filter(cefr_level=cefr_level)

            # Process results with additional context
            for concept in concepts[:limit]:
                result = {
                    'concept': concept,
                    'similarity': getattr(concept, 'similarity', 0.0),
                    'name': concept.name,
                    'description': concept.description,
                    'cefr_level': concept.cefr_level,
                    'complexity_score': concept.complexity_score,
                    'tags': concept.tags,
                }

                # Add user-specific mastery information
                if user and include_mastery_info:
                    mastery = ConceptMastery.objects.filter(
                        user=user, concept=concept
                    ).first()

                    result['mastery_info'] = {
                        'mastered': mastery.is_mastered() if mastery else False,
                        'mastery_score': mastery.mastery_score if mastery else 0.0,
                        'attempts': mastery.attempts_count if mastery else 0,
                        'needs_review': mastery.needs_review() if mastery else True,
                        'last_practiced': mastery.last_practiced if mastery else None,
                    }

                results.append(result)

        except Exception as e:
            logger.error(f"Error in similarity search: {e}")
            # Fallback to text-based search
            concepts = GrammarConcept.objects.filter(
                Q(name__icontains=query_text) | Q(description__icontains=query_text),
                language=language,
            )
            if cefr_level:
                concepts = concepts.filter(cefr_level=cefr_level)

            results = [
                {
                    'concept': concept,
                    'similarity': 0.5,  # Default similarity
                    'name': concept.name,
                    'description': concept.description,
                    'cefr_level': concept.cefr_level,
                }
                for concept in concepts[:limit]
            ]

        return results

    def get_personalized_practice_concepts(
        self,
        user: User,
        language: str,
        limit: int = 5,
        focus_areas: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get personalized concept recommendations using multiple signals.
        """
        language_profile = LanguageProfile.objects.filter(
            user=user, target_language=language
        ).first()

        if not language_profile:
            return []

        recommendations: List[Dict[str, Any]] = []

        # 1. Spaced repetition concepts (highest priority)
        self._add_spaced_repetition_concepts(
            recommendations, user, language, limit // 3
        )

        # 2. Error-driven recommendations
        self._add_error_driven_concepts(recommendations, user, language, limit // 3)

        # 3. Progressive difficulty concepts
        self._add_progressive_concepts(recommendations, language_profile, limit // 3)

        # 4. Focus area concepts if specified
        if focus_areas:
            self._add_focus_area_concepts(
                recommendations, language, focus_areas, limit // 4
            )

        # Remove duplicates and limit results
        seen_ids = set()
        unique_recommendations = []
        for rec in recommendations:
            concept_id = rec['concept'].id
            if concept_id not in seen_ids:
                seen_ids.add(concept_id)
                unique_recommendations.append(rec)

        return unique_recommendations[:limit]

    def _add_spaced_repetition_concepts(
        self,
        recommendations: List[Dict[str, Any]],
        user: User,
        language: str,
        limit: int,
    ) -> None:
        """Add concepts due for spaced repetition review."""
        due_masteries = (
            ConceptMastery.objects.filter(
                user=user, concept__language=language, next_review__lte=timezone.now()
            )
            .select_related('concept')
            .order_by('next_review')[:limit]
        )

        for mastery in due_masteries:
            recommendations.append(
                {
                    'concept': mastery.concept,
                    'reason': 'spaced_repetition',
                    'priority': 'high',
                    'mastery_score': mastery.mastery_score,
                    'days_since_review': (
                        timezone.now().date() - mastery.next_review.date()
                    ).days,
                }
            )

    def _add_error_driven_concepts(
        self,
        recommendations: List[Dict[str, Any]],
        user: User,
        language: str,
        limit: int,
    ) -> None:
        """Add concepts related to recent errors."""
        recent_errors = ErrorPattern.objects.filter(
            user=user,
            is_resolved=False,
            frequency__gte=2,
            last_seen__gte=timezone.now() - timedelta(days=7),
        ).order_by('-frequency')[:3]

        for error in recent_errors:
            related_concepts = error.related_concepts.filter(language=language)[
                : limit // 3
            ]

            for concept in related_concepts:
                # Check if user has low mastery for this concept
                mastery = ConceptMastery.objects.filter(
                    user=user, concept=concept
                ).first()

                mastery_score = mastery.mastery_score if mastery else 0.0
                if mastery_score < 0.7:  # Focus on concepts with room for improvement
                    recommendations.append(
                        {
                            'concept': concept,
                            'reason': 'error_pattern',
                            'priority': 'high',
                            'error_type': error.get_error_type_display(),
                            'error_frequency': error.frequency,
                            'mastery_score': mastery_score,
                        }
                    )

    def _add_progressive_concepts(
        self,
        recommendations: List[Dict[str, Any]],
        language_profile: LanguageProfile,
        limit: int,
    ) -> None:
        """Add concepts for progressive difficulty increase."""
        current_level = language_profile.current_level
        next_level = language_profile.get_next_level()

        # Get concepts at current level with low mastery
        current_level_concepts = GrammarConcept.objects.filter(
            language=language_profile.target_language, cefr_level=current_level
        )

        for concept in current_level_concepts[: limit // 2]:
            mastery = ConceptMastery.objects.filter(
                user=language_profile.user, concept=concept
            ).first()

            if not mastery or mastery.mastery_score < 0.8:
                recommendations.append(
                    {
                        'concept': concept,
                        'reason': 'level_mastery',
                        'priority': 'medium',
                        'target_level': current_level,
                        'mastery_score': mastery.mastery_score if mastery else 0.0,
                    }
                )

        # Add some next level concepts if user is ready
        if (
            language_profile.is_ready_for_next_level(threshold=0.7)
            and next_level != current_level
        ):
            next_level_concepts = GrammarConcept.objects.filter(
                language=language_profile.target_language, cefr_level=next_level
            )[: limit // 2]

            for concept in next_level_concepts:
                recommendations.append(
                    {
                        'concept': concept,
                        'reason': 'level_progression',
                        'priority': 'medium',
                        'target_level': next_level,
                    }
                )

    def _add_focus_area_concepts(
        self,
        recommendations: List[Dict[str, Any]],
        language: str,
        focus_areas: List[str],
        limit: int,
    ) -> None:
        """Add concepts related to specific focus areas."""
        for area in focus_areas:
            # Search for concepts with matching tags or names
            concepts = GrammarConcept.objects.filter(
                Q(tags__contains=[area]) | Q(name__icontains=area), language=language
            )[: limit // len(focus_areas)]

            for concept in concepts:
                recommendations.append(
                    {
                        'concept': concept,
                        'reason': 'focus_area',
                        'priority': 'medium',
                        'focus_area': area,
                    }
                )

    def cluster_concepts_by_similarity(
        self,
        concepts: QuerySet[GrammarConcept],
        min_cluster_size: int = 2,
        similarity_threshold: float = 0.6,
    ) -> Dict[str, List[GrammarConcept]]:
        """
        Group concepts into clusters based on vector similarity.

        Uses a simple clustering approach based on similarity thresholds.
        """
        clusters = {}
        processed_ids = set()

        # Convert QuerySet to list to avoid slicing issues
        concepts_list = list(concepts)
        concept_ids = {c.id for c in concepts_list}

        for concept in concepts_list:
            if concept.id in processed_ids or not concept.embedding:
                continue

            # Find similar concepts and filter to only include ones from our input set
            similar_concepts_qs = concept.find_similar_concepts(
                limit=10, threshold=similarity_threshold
            )

            # Filter to only concepts in our input set
            similar_concepts = [
                c
                for c in similar_concepts_qs
                if c.id in concept_ids and c.id not in processed_ids
            ]

            cluster_concepts = [concept]
            cluster_concepts.extend(similar_concepts)

            if len(cluster_concepts) >= min_cluster_size:
                cluster_name = (
                    f"cluster_{concept.cefr_level}_"
                    f"{concept.name.lower().replace(' ', '_')}"
                )
                clusters[cluster_name] = cluster_concepts

                # Mark as processed
                for c in cluster_concepts:
                    processed_ids.add(c.id)

        return clusters

    def get_concept_learning_difficulty(
        self, concept: GrammarConcept, user: Optional[User] = None
    ) -> Dict[str, Any]:
        """
        Analyze the learning difficulty of a concept for a user.
        """
        difficulty_analysis = {
            'base_complexity': concept.complexity_score,
            'cefr_level': concept.cefr_level,
            'prerequisite_count': concept.prerequisite_concepts.count(),
            'community_difficulty': None,
            'personalized_difficulty': None,
        }

        # Community difficulty based on average mastery scores
        community_stats = ConceptMastery.objects.filter(concept=concept).aggregate(
            avg_mastery=Avg('mastery_score'),
            avg_attempts=Avg('attempts_count'),
            learner_count=Count('user', distinct=True),
        )

        if community_stats['learner_count'] and community_stats['learner_count'] > 5:
            # Lower average mastery = higher difficulty
            community_difficulty = 1.0 - (community_stats['avg_mastery'] or 0.0)
            difficulty_analysis['community_difficulty'] = community_difficulty
            difficulty_analysis['community_stats'] = community_stats

        # Personalized difficulty for specific user
        if user:
            mastery = ConceptMastery.objects.filter(user=user, concept=concept).first()

            if mastery:
                # Factor in user's success rate and number of attempts
                success_rate = mastery.get_success_rate() / 100.0
                attempt_factor = min(
                    1.0, mastery.attempts_count / 10.0
                )  # Normalize attempts

                # Higher attempts with low success = high personal difficulty
                personal_difficulty = (1.0 - success_rate) * attempt_factor
                difficulty_analysis['personalized_difficulty'] = personal_difficulty
                difficulty_analysis['user_stats'] = {
                    'mastery_score': mastery.mastery_score,
                    'success_rate': success_rate,
                    'attempts': mastery.attempts_count,
                }

        return difficulty_analysis


# Global instance
similarity_service = ConceptSimilarityService()
