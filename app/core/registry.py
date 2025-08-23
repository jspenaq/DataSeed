"""
Registry pattern implementation for extractors and normalizers.

This module provides a centralized registry system that follows the Open/Closed Principle,
allowing new extractors and normalizers to be added without modifying existing factory code.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.extractors.base import BaseExtractor, ExtractorConfig
    from app.core.normalizers.base import BaseNormalizer

# Global registries for extractors and normalizers
extractor_registry: dict[str, type["BaseExtractor"]] = {}
normalizer_registry: dict[str, type["BaseNormalizer"]] = {}


def register_extractor(name: str) -> Callable[[type["BaseExtractor"]], type["BaseExtractor"]]:
    """
    Decorator to register an extractor class in the global registry.

    Args:
        name: Unique name for the extractor (e.g., "hackernews", "reddit")

    Returns:
        Decorator function that registers the class

    Example:
        @register_extractor("hackernews")
        class HackerNewsExtractor(BaseExtractor):
            pass
    """

    def decorator(cls: type["BaseExtractor"]) -> type["BaseExtractor"]:
        extractor_registry[name] = cls
        return cls

    return decorator


def register_normalizer(name: str) -> Callable[[type["BaseNormalizer"]], type["BaseNormalizer"]]:
    """
    Decorator to register a normalizer class in the global registry.

    Args:
        name: Unique name for the normalizer (e.g., "default", "hackernews")

    Returns:
        Decorator function that registers the class

    Example:
        @register_normalizer("default")
        class ContentNormalizer(BaseNormalizer):
            pass
    """

    def decorator(cls: type["BaseNormalizer"]) -> type["BaseNormalizer"]:
        normalizer_registry[name] = cls
        return cls

    return decorator


def get_extractor_class(name: str) -> type["BaseExtractor"]:
    """
    Get an extractor class from the registry.

    Args:
        name: Name of the extractor to retrieve

    Returns:
        Extractor class

    Raises:
        KeyError: If extractor is not found in registry
    """
    if name not in extractor_registry:
        raise KeyError(f"Extractor '{name}' not found in registry. Available: {list(extractor_registry.keys())}")

    return extractor_registry[name]


def get_normalizer_class(name: str) -> type["BaseNormalizer"]:
    """
    Get a normalizer class from the registry.

    Args:
        name: Name of the normalizer to retrieve

    Returns:
        Normalizer class

    Raises:
        KeyError: If normalizer is not found in registry
    """
    if name not in normalizer_registry:
        raise KeyError(f"Normalizer '{name}' not found in registry. Available: {list(normalizer_registry.keys())}")

    return normalizer_registry[name]


def list_registered_extractors() -> list[str]:
    """
    Get a list of all registered extractor names.

    Returns:
        List of registered extractor names
    """
    return list(extractor_registry.keys())


def list_registered_normalizers() -> list[str]:
    """
    Get a list of all registered normalizer names.

    Returns:
        List of registered normalizer names
    """
    return list(normalizer_registry.keys())


# Factory functions for convenience
def get_extractor(source_name: str, config: "ExtractorConfig", source_id: int) -> "BaseExtractor":
    """
    Factory function to get an extractor instance for a source.

    Args:
        source_name: Name of the data source
        config: ExtractorConfig instance for the extractor
        source_id: ID of the data source

    Returns:
        Configured extractor instance

    Raises:
        KeyError: If extractor is not found in registry
    """
    extractor_class = get_extractor_class(source_name.lower())
    return extractor_class(config, source_id=source_id)


def get_normalizer(source_name: str, source_id: int) -> "BaseNormalizer":
    """
    Factory function to get a normalizer instance for a source.

    Args:
        source_name: Name of the data source
        source_id: ID of the data source

    Returns:
        Configured normalizer instance
    """
    try:
        # Try to get source-specific normalizer first
        normalizer_class = get_normalizer_class(source_name.lower())
        return normalizer_class(source_id)
    except KeyError:
        # Fallback to generic normalizer if specific one not found
        try:
            normalizer_class = get_normalizer_class("generic")
            return normalizer_class(source_id)
        except KeyError as generic_err:
            raise KeyError(
                f"No normalizer found for source '{source_name}' and no generic normalizer available",
            ) from generic_err
