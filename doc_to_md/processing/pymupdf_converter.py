"""PDF converter implementation using pymupdf4llm."""

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
    TableData,
    TOCItem,
)


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
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            ConversionResult with markdown, TOC, tables, and metadata.
        """
        path = Path(pdf_path)
        
        # Extract markdown with page chunks for metadata
        md_text = pymupdf4llm.to_markdown(
            str(path),
            page_chunks=False,  # Get full document first
            write_images=False,  # Don't extract images for now
            header=False,
            footer=False,
        )
        
        # Extract TOC
        toc = self.get_toc(path)
        
        # Extract metadata  
        metadata = self.get_metadata(path)
        metadata.source_file = str(path)
        
        # Extract tables (we'll identify them from the markdown)
        tables = self._extract_tables_from_markdown(md_text)
        
        return ConversionResult(
            markdown=md_text,
            toc=toc,
            tables=tables,
            metadata=metadata,
        )
    
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
            raw_toc = doc.get_toc()
            toc_items = []
            
            for item in raw_toc:
                level, title, page = item[0], item[1], item[2]
                toc_items.append(TOCItem(
                    level=level,
                    title=title.strip(),
                    page_number=page
                ))
            
            return toc_items
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
            meta = doc.metadata or {}
            
            return DocumentMetadata(
                title=meta.get("title") or None,
                author=meta.get("author") or None,
                subject=meta.get("subject") or None,
                creation_date=meta.get("creationDate") or None,
                modification_date=meta.get("modDate") or None,
                page_count=doc.page_count,
                source_file=str(path)
            )
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
        
        # Regex pattern to match markdown tables
        # A table starts with a header row, then a separator row with dashes/pipes
        table_pattern = re.compile(
            r'(\|[^\n]+\|\n\|[-:\| ]+\|\n(?:\|[^\n]+\|\n)*)',
            re.MULTILINE
        )
        
        for match in table_pattern.finditer(markdown):
            table_content = match.group(1).strip()
            rows = table_content.split('\n')
            
            # Count columns from header row
            if rows:
                col_count = len([c for c in rows[0].split('|') if c.strip()])
                row_count = len(rows) - 1  # Exclude separator row
                
                tables.append(TableData(
                    content=table_content,
                    page_number=0,  # Would need page tracking for accuracy
                    row_count=row_count,
                    col_count=col_count
                ))
        
        return tables
