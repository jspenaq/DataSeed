"""
Registry pattern implementation for extractors and normalizers.

This module provides a centralized registry system that follows the Open/Closed Principle,
allowing new extractors and normalizers to be added without modifying existing factory code.
"""

from typing import Any

# Global registries for extractors and normalizers
extractor_registry: dict[str, type[Any]] = {}
normalizer_registry: dict[str, type[Any]] = {}


def register_extractor(name: str):
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

    def decorator(cls: type[Any]):
        extractor_registry[name] = cls
        return cls

    return decorator


def register_normalizer(name: str):
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

    def decorator(cls: type[Any]):
        normalizer_registry[name] = cls
        return cls

    return decorator


def get_extractor_class(name: str) -> type[Any]:
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


def get_normalizer_class(name: str) -> type[Any]:
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
def get_extractor(source_name: str, config) -> Any:
    """
    Factory function to get an extractor instance for a source.

    Args:
        source_name: Name of the data source
        config: ExtractorConfig instance for the extractor

    Returns:
        Configured extractor instance

    Raises:
        KeyError: If extractor is not found in registry
    """
    extractor_class = get_extractor_class(source_name.lower())
    return extractor_class(config)


def get_normalizer(source_name: str, source_id: int) -> Any:
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
        except KeyError:
            raise KeyError(f"No normalizer found for source '{source_name}' and no generic normalizer available")
