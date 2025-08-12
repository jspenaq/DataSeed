"""Data extractors for various sources."""

from app.core.extractors.base import BaseExtractor, ExtractorConfig, ExtractorProtocol, RawItem
from app.core.extractors.hackernews import HackerNewsExtractor

__all__ = [
    "BaseExtractor",
    "ExtractorConfig",
    "ExtractorProtocol",
    "RawItem",
    "HackerNewsExtractor",
]
