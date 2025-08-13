"""
Core module initialization with auto-discovery for registry pattern.

This module ensures that all extractors and normalizers are registered
when the core module is imported.
"""

# Import all extractors to trigger registration
from app.core.extractors import hackernews  # noqa: F401

# Import all normalizers to trigger registration
from app.core.normalizers import base, content  # noqa: F401

# Import registry for convenience
from app.core.registry import (  # noqa: F401
    get_extractor,
    get_normalizer,
    list_registered_extractors,
    list_registered_normalizers,
)
