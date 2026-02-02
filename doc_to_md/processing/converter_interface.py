"""Abstract base class for PDF converters.

This module defines the interface that all PDF converters must implement,
allowing for pluggable backends (pymupdf4llm, docling, VLM-based, etc.).
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from .models import ConversionResult, DocumentMetadata, TOCItem, TableData


class PDFConverterBase(ABC):
    """Abstract base class for PDF to Markdown converters.
    
    Implement this interface to add new conversion backends.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of this converter backend."""
        pass
    
    @abstractmethod
    def convert(self, pdf_path: Union[str, Path]) -> ConversionResult:
        """Convert a PDF file to markdown with metadata.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            ConversionResult containing markdown, TOC, tables, and metadata.
        """
        pass
    
    @abstractmethod
    def get_toc(self, pdf_path: Union[str, Path]) -> list[TOCItem]:
        """Extract table of contents from a PDF.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            List of TOCItem representing the document structure.
        """
        pass
    
    @abstractmethod
    def get_metadata(self, pdf_path: Union[str, Path]) -> DocumentMetadata:
        """Extract metadata from a PDF.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            DocumentMetadata with title, author, dates, etc.
        """
        pass
    
    def validate_pdf(self, pdf_path: Union[str, Path]) -> bool:
        """Check if a file is a valid, convertible PDF.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            True if the file can be converted, False otherwise.
        """
        path = Path(pdf_path)
        if not path.exists():
            return False
        if path.suffix.lower() != ".pdf":
            return False
        return True
