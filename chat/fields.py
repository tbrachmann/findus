"""
Custom Django fields for vector operations with pgvector.

This module provides Django field types for storing and querying vector embeddings
using PostgreSQL's pgvector extension.
"""

from django.db import models
from django.core.exceptions import ValidationError
from typing import Any, Optional, List
import json


class VectorField(models.Field):
    """
    A Django field for storing vector embeddings using pgvector.

    Stores vector data as a PostgreSQL vector type for efficient similarity search.
    """

    def __init__(self, dimensions: int = 768, *args: Any, **kwargs: Any) -> None:
        self.dimensions = dimensions
        super().__init__(*args, **kwargs)

    def deconstruct(self) -> tuple[str, str, tuple[Any, ...], dict[str, Any]]:
        """Return field configuration for migrations."""
        name, path, args, kwargs = super().deconstruct()
        kwargs['dimensions'] = self.dimensions
        return name, path, args, kwargs

    def db_type(self, connection: Any) -> str:
        """Return the PostgreSQL column type."""
        return f'vector({self.dimensions})'

    def from_db_value(
        self, value: Any, expression: Any, connection: Any
    ) -> Optional[List[float]]:
        """Convert database value to Python value."""
        if value is None:
            return None

        # pgvector returns vectors as strings like '[1.0,2.0,3.0]'
        if isinstance(value, str):
            # Remove brackets and split by comma
            if value.startswith('[') and value.endswith(']'):
                value = value[1:-1]
            return [float(x.strip()) for x in value.split(',') if x.strip()]

        # If already a list, return as-is
        if isinstance(value, list):
            return [float(x) for x in value]

        return None

    def to_python(self, value: Any) -> Optional[List[float]]:
        """Convert value to Python representation."""
        if value is None:
            return None

        if isinstance(value, list):
            return [float(x) for x in value]

        if isinstance(value, str):
            # Handle JSON string representation
            if value.startswith('[') and value.endswith(']'):
                try:
                    parsed = json.loads(value)
                    return [float(x) for x in parsed]
                except (json.JSONDecodeError, ValueError):
                    # Try pgvector format '[1.0,2.0,3.0]'
                    value = value[1:-1]
                    return [float(x.strip()) for x in value.split(',') if x.strip()]

        raise ValidationError(f'Invalid vector format: {value}')

    def get_prep_value(self, value: Any) -> Optional[str]:
        """Prepare value for database storage."""
        if value is None:
            return None

        if isinstance(value, list):
            # Validate dimensions
            if len(value) != self.dimensions:
                raise ValidationError(
                    f'Vector must have exactly {self.dimensions} dimensions, got {len(value)}'
                )

            # Convert to pgvector format
            return '[' + ','.join(str(float(x)) for x in value) + ']'

        raise ValidationError(
            f'Vector field expects a list of numbers, got {type(value)}'
        )

    def validate(self, value: Any, model_instance: Any) -> None:
        """Validate the field value."""
        super().validate(value, model_instance)

        if value is not None:
            if not isinstance(value, list):
                raise ValidationError('Vector must be a list of numbers')

            if len(value) != self.dimensions:
                raise ValidationError(
                    f'Vector must have exactly {self.dimensions} dimensions, got {len(value)}'
                )

            # Check that all values are numeric
            try:
                [float(x) for x in value]
            except (ValueError, TypeError):
                raise ValidationError('All vector values must be numeric')

    def get_internal_type(self) -> str:
        """Return the internal field type name."""
        return 'VectorField'


class VectorSearchMixin:
    """
    Mixin providing vector similarity search methods for model managers.
    """

    def similarity_search(
        self,
        vector_field: str,
        query_vector: List[float],
        limit: int = 10,
        threshold: float = 0.0,
    ) -> models.QuerySet:
        """
        Perform cosine similarity search on vector field.

        Args:
            vector_field: Name of the vector field to search
            query_vector: Vector to search for
            limit: Maximum number of results
            threshold: Minimum similarity threshold (0-1)

        Returns:
            QuerySet ordered by similarity (highest first)
        """
        # Format query vector for pgvector
        vector_str = '[' + ','.join(str(float(x)) for x in query_vector) + ']'

        queryset = self.extra(
            select={'similarity': f'1 - ({vector_field} <=> %s)'},
            select_params=[vector_str],
            where=[f'1 - ({vector_field} <=> %s) >= %s'],
            params=[vector_str, threshold],
            order_by=['-similarity'],
        )

        return queryset[:limit]

    def nearest_neighbors(
        self, vector_field: str, query_vector: List[float], k: int = 5
    ) -> models.QuerySet:
        """
        Find k nearest neighbors using L2 distance.

        Args:
            vector_field: Name of the vector field to search
            query_vector: Vector to search for
            k: Number of neighbors to return

        Returns:
            QuerySet ordered by distance (closest first)
        """
        # Format query vector for pgvector
        vector_str = '[' + ','.join(str(float(x)) for x in query_vector) + ']'

        return self.extra(
            select={'distance': f'{vector_field} <-> %s'},
            select_params=[vector_str],
            order_by=['distance'],
        )[:k]


class VectorManager(models.Manager, VectorSearchMixin):
    """Manager with vector search capabilities."""

    pass
