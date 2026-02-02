"""Data models for PDF to Markdown conversion."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class ContentType(Enum):
    """Type of content in a chunk."""
    PROSE = "prose"
    TABLE = "table"
    LIST = "list"
    CODE_BLOCK = "code_block"
    HEADING = "heading"
    MIXED = "mixed"


@dataclass
class TOCItem:
    """Represents an item in the Table of Contents."""
    level: int
    title: str
    page_number: int
    
    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "title": self.title,
            "page_number": self.page_number
        }


@dataclass
class TableData:
    """Represents an extracted table."""
    content: str  # Markdown formatted table
    page_number: int
    caption: Optional[str] = None
    row_count: int = 0
    col_count: int = 0
    
    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "page_number": self.page_number,
            "caption": self.caption,
            "row_count": self.row_count,
            "col_count": self.col_count
        }


@dataclass 
class DocumentMetadata:
    """Metadata extracted from the PDF document."""
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None
    page_count: int = 0
    source_file: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "author": self.author,
            "subject": self.subject,
            "creation_date": self.creation_date,
            "modification_date": self.modification_date,
            "page_count": self.page_count,
            "source_file": self.source_file
        }


@dataclass
class Section:
    """Represents a document section with hierarchy."""
    title: str
    level: int
    content: str
    page_start: int
    page_end: int
    path: list[str] = field(default_factory=list)  # Hierarchy path
    subsections: list["Section"] = field(default_factory=list)
    content_types: list[ContentType] = field(default_factory=list)
    
    @property
    def full_path(self) -> str:
        """Get the full section path as string."""
        return " > ".join(self.path + [self.title])
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "level": self.level,
            "content": self.content,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "path": self.path,
            "full_path": self.full_path,
            "content_types": [ct.value for ct in self.content_types],
            "subsections": [s.to_dict() for s in self.subsections]
        }


@dataclass
class Chunk:
    """A content chunk optimized for RAG retrieval."""
    content: str
    section_path: list[str]
    section_level: int
    page_number: int
    content_type: ContentType
    preceding_section: Optional[str] = None
    following_section: Optional[str] = None
    has_tables: bool = False
    has_code_blocks: bool = False
    chunk_index: int = 0
    
    def to_frontmatter(self) -> str:
        """Generate YAML frontmatter for markdown output."""
        lines = ["---"]
        lines.append(f"section_path: {self.section_path}")
        lines.append(f"section_level: {self.section_level}")
        lines.append(f"page_number: {self.page_number}")
        lines.append(f"content_type: {self.content_type.value}")
        if self.preceding_section:
            lines.append(f"preceding_section: \"{self.preceding_section}\"")
        if self.following_section:
            lines.append(f"following_section: \"{self.following_section}\"")
        lines.append(f"has_tables: {str(self.has_tables).lower()}")
        lines.append(f"has_code_blocks: {str(self.has_code_blocks).lower()}")
        lines.append(f"chunk_index: {self.chunk_index}")
        lines.append("---")
        return "\n".join(lines)
    
    def to_markdown(self) -> str:
        """Generate full markdown with frontmatter."""
        return f"{self.to_frontmatter()}\n\n{self.content}"
    
    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "section_path": self.section_path,
            "section_level": self.section_level,
            "page_number": self.page_number,
            "content_type": self.content_type.value,
            "preceding_section": self.preceding_section,
            "following_section": self.following_section,
            "has_tables": self.has_tables,
            "has_code_blocks": self.has_code_blocks,
            "chunk_index": self.chunk_index
        }


@dataclass
class ConversionResult:
    """Result of PDF to Markdown conversion."""
    markdown: str
    toc: list[TOCItem] = field(default_factory=list)
    tables: list[TableData] = field(default_factory=list)
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    sections: list[Section] = field(default_factory=list)
    chunks: list[Chunk] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "markdown": self.markdown,
            "toc": [t.to_dict() for t in self.toc],
            "tables": [t.to_dict() for t in self.tables],
            "metadata": self.metadata.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
            "chunks": [c.to_dict() for c in self.chunks]
        }
