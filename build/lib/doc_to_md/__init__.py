"""Doc-to-MD: PDF to Markdown conversion for RAG applications."""

from .pipeline import ConversionPipeline, PipelineConfig, quick_convert
from .processing import (
    Chunk,
    ContentType,
    ConversionResult,
    DocumentMetadata,
    PDFConverterBase,
    PyMuPDFConverter,
    Section,
    TableData,
    TOCItem,
)

__version__ = "0.1.0"

__all__ = [
    # Pipeline
    "ConversionPipeline",
    "PipelineConfig",
    "quick_convert",
    # Models
    "ConversionResult",
    "DocumentMetadata",
    "TOCItem",
    "TableData",
    "Section",
    "Chunk",
    "ContentType",
    # Converters
    "PDFConverterBase",
    "PyMuPDFConverter",
]
