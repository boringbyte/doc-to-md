"""PDF converter implementation using pymupdf4llm."""

import logging
import re
from pathlib import Path
from typing import Union

import pymupdf.layout
import pymupdf
import pymupdf4llm

from .converter_interface import PDFConverterBase
from .models import (
    ConversionResult,
    DocumentMetadata,
    EmbeddedPDF,
    TableData,
    TOCItem,
)

logger = logging.getLogger(__name__)

class PyMuPDFConverter(PDFConverterBase):
    """PDF to Markdown converter using pymupdf4llm.
    
    This converter leverages PyMuPDF's LLM-focused extraction capabilities
    for high-quality markdown conversion with TOC and table support.
    """
    
    @property
    def name(self) -> str:
        return "pymupdf4llm"
    
    def convert(self, pdf_path: Union[str, Path]) -> ConversionResult:
        """Convert PDF to markdown with full metadata extraction.
        
        Opens the PDF once and extracts markdown, TOC, and metadata
        in a single session for optimal performance.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            ConversionResult with markdown, TOC, tables, and metadata.
        """
        path = Path(pdf_path)
        
        # Extract markdown via pymupdf4llm (opens/closes internally)
        md_text = pymupdf4llm.to_markdown(
            str(path),
            page_chunks=False,
            write_images=False,
            header=False,
            footer=False,
        )
        
        # Single open for TOC + metadata (instead of 2 separate opens)
        doc = pymupdf.open(str(path))
        try:
            toc = self._extract_toc_from_doc(doc)
            metadata = self._extract_metadata_from_doc(doc, path)
        finally:
            doc.close()
        
        # Extract tables from markdown (no file I/O needed)
        tables = self._extract_tables_from_markdown(md_text)
        
        return ConversionResult(
            markdown=md_text,
            toc=toc,
            tables=tables,
            metadata=metadata,
        )
    
    # --- Internal extraction methods (operate on an already-opened doc) ---
    
    @staticmethod
    def _extract_toc_from_doc(doc: pymupdf.Document) -> list[TOCItem]:
        """Extract TOC from an already-opened PyMuPDF document."""
        raw_toc = doc.get_toc()
        return [
            TOCItem(level=item[0], title=item[1].strip(), page_number=item[2])
            for item in raw_toc
        ]
    
    @staticmethod
    def _extract_metadata_from_doc(doc: pymupdf.Document, path: Path) -> DocumentMetadata:
        """Extract metadata from an already-opened PyMuPDF document."""
        meta = doc.metadata or {}
        return DocumentMetadata(
            title=meta.get("title") or None,
            author=meta.get("author") or None,
            subject=meta.get("subject") or None,
            keywords=meta.get("keywords") or None,
            creation_date=meta.get("creationDate") or None,
            modification_date=meta.get("modDate") or None,
            page_count=doc.page_count,
            source_file=str(path)
        )
    
    # --- Public convenience methods (open file themselves, backward compat) ---

    def get_toc(self, pdf_path: Union[str, Path]) -> list[TOCItem]:
        """Extract table of contents from PDF.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            List of TOCItem with level, title, and page number.
        """
        path = Path(pdf_path)
        doc = pymupdf.open(str(path))
        try:
            return self._extract_toc_from_doc(doc)
        finally:
            doc.close()
    
    def get_metadata(self, pdf_path: Union[str, Path]) -> DocumentMetadata:
        """Extract document metadata from PDF.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            DocumentMetadata with available information.
        """
        path = Path(pdf_path)
        doc = pymupdf.open(str(path))
        try:
            return self._extract_metadata_from_doc(doc, path)
        finally:
            doc.close()
    
    def _extract_tables_from_markdown(self, markdown: str) -> list[TableData]:
        """Extract tables from markdown content.
        
        Identifies markdown tables and extracts them with metadata.
        
        Args:
            markdown: The markdown content to parse.
            
        Returns:
            List of TableData objects.
        """
        tables = []
        
        table_pattern = re.compile(
            r'(\|[^\n]+\|\n\|[-:\| ]+\|\n(?:\|[^\n]+\|\n)*)',
            re.MULTILINE
        )
        
        for match in table_pattern.finditer(markdown):
            table_content = match.group(1).strip()
            rows = table_content.split('\n')
            
            if rows:
                col_count = len([c for c in rows[0].split('|') if c.strip()])
                row_count = len(rows) - 1  # Exclude separator row
                
                tables.append(TableData(
                    content=table_content,
                    page_number=0,
                    row_count=row_count,
                    col_count=col_count
                ))
        
        return tables

    def extract_embedded_pdfs(self, pdf_path: Union[str, Path]) -> list[EmbeddedPDF]:
        """Extract embedded PDF attachments from a PDF in a single open.
        
        Combines the check + extraction into one file open for performance.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            List of EmbeddedPDF objects (empty if none found).
        """
        path = Path(pdf_path)
        doc = pymupdf.open(str(path))
        embedded = []
        try:
            if doc.embfile_count() == 0:
                return embedded
            for name in doc.embfile_names():
                if not name.lower().endswith(".pdf"):
                    continue
                try:
                    data = doc.embfile_get(name)
                except Exception as e:
                    logger.warning(f"Could not extract embedded file '{name}': {e}")
                    continue
                clean_name = self._clean_embedded_filename(name)
                embedded.append(EmbeddedPDF(
                    name=name,
                    filename=clean_name,
                    data=data
                ))
            return embedded
        finally:
            doc.close()

    def has_embedded_pdfs(self, pdf_path: Union[str, Path]) -> bool:
        """Check if a PDF contains embedded PDF attachments."""
        path = Path(pdf_path)
        doc = pymupdf.open(str(path))
        try:
            if doc.embfile_count() == 0:
                return False
            return any(name.lower().endswith(".pdf") for name in doc.embfile_names())
        finally:
            doc.close()

    def get_embedded_pdfs(self, pdf_path: Union[str, Path]) -> list[EmbeddedPDF]:
        """Extract embedded PDF attachments (backward compat wrapper)."""
        return self.extract_embedded_pdfs(pdf_path)


    @staticmethod
    def _clean_embedded_filename(filename: str) -> str:
        """Clean an embedded file name for use as an output filename.
        
        Removes portfolio prefix tags like '<0>', '<1>' and sanitizes.
        """
        # Remove leading tags like '<0>', '<1>', '<2>'
        cleaned = re.sub(r'^<\d+>', '', filename).strip()
        # Remove .pdf extension (we'll add proper extension later)
        if cleaned.lower().endswith('.pdf'):
            cleaned = cleaned[:-4]
        # Sanitize for filesystem: replace special chars with hyphens
        cleaned = re.sub(r'[^\w\s.-]', '', cleaned)
        cleaned = re.sub(r'\s+', '-', cleaned)
        # Lowercase and trim
        cleaned = cleaned.lower().strip('-')
        return cleaned
