"""Post-processing module for PDF to Markdown conversion."""

from .metadata_enricher import (
    MetadataEnricher,
    MetadataEnricherConfig,
    generate_markdown_output,
)
from .segmenter import SegmenterConfig, StructureAwareSegmenter
from .table_processor import TableProcessor, TableProcessorConfig
from .toc_processor import TOCProcessor, infer_toc_from_markdown

__all__ = [
    "TOCProcessor",
    "infer_toc_from_markdown",
    "StructureAwareSegmenter",
    "SegmenterConfig",
    "TableProcessor",
    "TableProcessorConfig",
    "MetadataEnricher",
    "MetadataEnricherConfig",
    "generate_markdown_output",
]
