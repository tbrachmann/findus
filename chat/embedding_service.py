"""
Embedding generation service for grammar concepts.

This service generates vector embeddings for grammar concepts to enable
semantic similarity search and concept clustering.
"""

import asyncio
import hashlib
import logging
from typing import List, Dict, Any
from django.conf import settings
from google import genai

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and managing concept embeddings."""

    def __init__(self) -> None:
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = "text-embedding-004"  # Google's latest embedding model
        self.cache_timeout = 60 * 60 * 24 * 7  # 1 week

    def _get_cache_key(self, text: str, language: str = "en") -> str:
        """Generate cache key for embedding."""
        content = f"{text}:{language}:{self.model_name}"
        return f"embedding:{hashlib.md5(content.encode()).hexdigest()}"

    async def generate_embedding(self, text: str, language: str = "en") -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            language: Language code (en, es, de)

        Returns:
            List of float values representing the embedding vector
        """
        # cache_key = self._get_cache_key(text, language)

        # # Check cache first
        # cached_embedding = cache.get(cache_key)
        # if cached_embedding:
        #     return cached_embedding

        # Use Google's embedding model in a thread to avoid blocking
        response = await asyncio.to_thread(
            lambda: self.client.models.embed_content(
                model=self.model_name, contents=text
            )
        )

        embedding = response.embeddings[0].values

        # # Cache the result
        # cache.set(cache_key, embedding, self.cache_timeout)

        logger.info(
            f"Generated embedding for text: {text[:50]}... (dimension: {len(embedding)})"
        )
        return embedding

    async def generate_concept_embedding(
        self, concept_name: str, description: str, language: str = "en"
    ) -> List[float]:
        """
        Generate embedding for a grammar concept using its name and description.

        Args:
            concept_name: Name of the grammar concept
            description: Detailed description of the concept
            language: Language code

        Returns:
            Embedding vector for the concept
        """
        # Combine name and description for better embedding
        combined_text = f"{concept_name}: {description}"
        return await self.generate_embedding(combined_text, language)

    async def generate_batch_embeddings(
        self, texts: List[str], language: str = "en"
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed
            language: Language code

        Returns:
            List of embedding vectors
        """
        tasks = [self.generate_embedding(text, language) for text in texts]
        return await asyncio.gather(*tasks)

    async def update_concept_embeddings(
        self, concepts_queryset: Any = None, force_update: bool = False
    ) -> int:
        """
        Update embeddings for grammar concepts.

        Args:
            concepts_queryset: Optional queryset of concepts to update
            force_update: Whether to regenerate embeddings even if they exists

        Returns:
            Number of concepts updated
        """
        from .models import GrammarConcept

        if concepts_queryset is None:
            if force_update:
                concepts = GrammarConcept.objects.all()
            else:
                concepts = GrammarConcept.objects.filter(embedding__isnull=True)
        else:
            concepts = concepts_queryset

        updated_count = 0

        # Use async iteration - this is the proper way
        async for concept in concepts:
            if not force_update and concept.embedding:
                continue

            embedding = await self.generate_concept_embedding(
                concept_name=concept.name,
                description=concept.description,
                language=concept.language,
            )

            concept.embedding = embedding
            await concept.asave()  # This should work fine with pgvector
            updated_count += 1

            logger.info(f"Updated embedding for concept: {concept.name}")

        return updated_count

    def calculate_similarity(self, vector1: List[float], vector2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vector1: First vector
            vector2: Second vector

        Returns:
            Cosine similarity score between 0 and 1
        """
        import numpy as np

        v1 = np.array(vector1)
        v2 = np.array(vector2)

        # Calculate cosine similarity
        dot_product = np.dot(v1, v2)
        norms = np.linalg.norm(v1) * np.linalg.norm(v2)

        if norms == 0:
            return 0.0

        similarity = dot_product / norms

        # Normalize to 0-1 range
        return (similarity + 1) / 2

    async def find_similar_concepts(
        self,
        concept_name: str,
        concept_description: str,
        language: str = "en",
        limit: int = 5,
        threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Find concepts similar to the given concept using embeddings.

        Args:
            concept_name: Name of the concept to find similarities for
            concept_description: Description of the concept
            language: Language code
            limit: Maximum number of similar concepts to return
            threshold: Minimum similarity threshold

        Returns:
            List of similar concepts with similarity scores
        """
        from .models import GrammarConcept

        # Generate embedding for the query concept
        query_embedding = await self.generate_concept_embedding(
            concept_name, concept_description, language
        )

        # Use database vector search for efficiency
        similar_concepts = GrammarConcept.objects.similarity_search(
            vector_field='embedding',
            query_vector=query_embedding,
            limit=limit,
            threshold=threshold,
        ).filter(language=language)

        results = []
        for concept in similar_concepts:
            similarity = getattr(concept, 'similarity', 0.0)
            results.append(
                {
                    'concept': concept,
                    'similarity': similarity,
                    'name': concept.name,
                    'description': concept.description,
                    'cefr_level': concept.cefr_level,
                }
            )

        return results


# Global instance
embedding_service = EmbeddingService()
