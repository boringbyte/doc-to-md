"""Structure-aware content segmenter for RAG-optimized chunking."""

import re
from dataclasses import dataclass
from typing import Optional

from ..processing.models import Chunk, ContentType, Section, TOCItem
from .toc_processor import TOCProcessor


@dataclass
class SegmenterConfig:
    """Configuration for the content segmenter."""
    # Target chunk size in characters (approximate, respects boundaries)
    target_chunk_size: int = 2000
    # Maximum chunk size before forced split
    max_chunk_size: int = 4000
    # Minimum chunk size (avoid tiny chunks)
    min_chunk_size: int = 200
    # Keep tables as single chunks regardless of size
    preserve_tables: bool = True
    # Keep code blocks as single chunks
    preserve_code_blocks: bool = True


class StructureAwareSegmenter:
    """Segments markdown content respecting document structure.
    
    Key features:
    - Splits at section boundaries, never mid-section when possible
    - Preserves tables and code blocks as atomic units
    - Enriches chunks with section path metadata
    - Handles oversized sections with semantic sub-splitting
    """
    
    def __init__(
        self,
        toc_processor: Optional[TOCProcessor] = None,
        config: Optional[SegmenterConfig] = None
    ):
        """Initialize the segmenter.
        
        Args:
            toc_processor: Optional TOC processor for section awareness.
            config: Segmentation configuration.
        """
        self.toc_processor = toc_processor
        self.config = config or SegmenterConfig()
    
    def segment(self, markdown: str) -> list[Chunk]:
        """Segment markdown content into RAG-optimized chunks.
        
        Args:
            markdown: The markdown content to segment.
            
        Returns:
            List of Chunk objects with metadata.
        """
        # First, split into top-level sections
        sections = self._split_by_headings(markdown)
        
        chunks: list[Chunk] = []
        chunk_index = 0
        
        for i, section in enumerate(sections):
            # Get neighboring section info
            preceding = sections[i - 1]["title"] if i > 0 else None
            following = sections[i + 1]["title"] if i + 1 < len(sections) else None
            
            # Process section content
            section_chunks = self._process_section(
                section["content"],
                section["title"],
                section["level"],
                section.get("path", []),
                preceding,
                following
            )
            
            for chunk in section_chunks:
                chunk.chunk_index = chunk_index
                chunks.append(chunk)
                chunk_index += 1
        
        return chunks
    
    def _split_by_headings(self, markdown: str) -> list[dict]:
        """Split markdown into sections by headings.
        
        Args:
            markdown: The markdown content.
            
        Returns:
            List of section dicts with title, level, content, path.
        """
        sections = []
        
        # Pattern to match markdown headings
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        
        matches = list(heading_pattern.finditer(markdown))
        
        if not matches:
            # No headings found, treat entire content as one section
            return [{
                "title": "Document",
                "level": 0,
                "content": markdown,
                "path": []
            }]
        
        # Build section path tracking
        path_stack: list[tuple[int, str]] = []  # (level, title)
        
        for i, match in enumerate(matches):
            level = len(match.group(1))
            title = match.group(2).strip()
            
            # Determine content end
            content_start = match.end()
            content_end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
            content = markdown[content_start:content_end].strip()
            
            # Update path stack
            while path_stack and path_stack[-1][0] >= level:
                path_stack.pop()
            
            path = [p[1] for p in path_stack]
            path_stack.append((level, title))
            
            sections.append({
                "title": title,
                "level": level,
                "content": f"{'#' * level} {title}\n\n{content}",
                "path": path
            })
        
        return sections
    
    def _process_section(
        self,
        content: str,
        title: str,
        level: int,
        path: list[str],
        preceding: Optional[str],
        following: Optional[str]
    ) -> list[Chunk]:
        """Process a section into one or more chunks.
        
        Args:
            content: Section content including heading.
            title: Section title.
            level: Heading level.
            path: Section hierarchy path.
            preceding: Title of preceding section.
            following: Title of following section.
            
        Returns:
            List of Chunk objects.
        """
        # Detect content types
        has_tables = bool(re.search(r'\|.+\|', content))
        has_code = bool(re.search(r'```[\s\S]*?```', content))
        
        # Determine primary content type
        content_type = self._detect_content_type(content)
        
        # If content is small enough, return as single chunk
        if len(content) <= self.config.max_chunk_size:
            return [Chunk(
                content=content,
                section_path=path + [title],
                section_level=level,
                page_number=0,  # Would need page info from converter
                content_type=content_type,
                preceding_section=preceding,
                following_section=following,
                has_tables=has_tables,
                has_code_blocks=has_code
            )]
        
        # Content too large, need to sub-split
        return self._split_large_section(
            content, title, level, path, preceding, following,
            has_tables, has_code
        )
    
    def _split_large_section(
        self,
        content: str,
        title: str,
        level: int,
        path: list[str],
        preceding: Optional[str],
        following: Optional[str],
        has_tables: bool,
        has_code: bool
    ) -> list[Chunk]:
        """Split an oversized section into multiple chunks.
        
        Preserves atomic elements (tables, code blocks) and splits
        at paragraph boundaries.
        """
        chunks = []
        
        # Extract and protect atomic elements
        protected_elements = []
        working_content = content
        
        # Protect tables
        if self.config.preserve_tables:
            table_pattern = re.compile(
                r'(\|[^\n]+\|\n\|[-:\| ]+\|\n(?:\|[^\n]+\|\n)*)',
                re.MULTILINE
            )
            for i, match in enumerate(table_pattern.finditer(content)):
                placeholder = f"__TABLE_{i}__"
                protected_elements.append((placeholder, match.group(1), ContentType.TABLE))
                working_content = working_content.replace(match.group(1), placeholder)
        
        # Protect code blocks
        if self.config.preserve_code_blocks:
            code_pattern = re.compile(r'```[\s\S]*?```')
            for i, match in enumerate(code_pattern.finditer(working_content)):
                placeholder = f"__CODE_{i}__"
                protected_elements.append((placeholder, match.group(0), ContentType.CODE_BLOCK))
                working_content = working_content.replace(match.group(0), placeholder)
        
        # Split by paragraphs
        paragraphs = re.split(r'\n\n+', working_content)
        
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para_size = len(para)
            
            # Check if this is a protected element
            is_protected = any(p[0] == para.strip() for p in protected_elements)
            
            if is_protected:
                # Flush current chunk if any
                if current_chunk:
                    chunk_content = '\n\n'.join(current_chunk)
                    chunk_content = self._restore_protected(chunk_content, protected_elements)
                    chunks.append(self._create_chunk(
                        chunk_content, title, level, path,
                        preceding, following, has_tables, has_code
                    ))
                    current_chunk = []
                    current_size = 0
                
                # Protected element as its own chunk
                protected_content = self._restore_protected(para, protected_elements)
                protected_type = next(
                    (p[2] for p in protected_elements if p[0] == para.strip()),
                    ContentType.PROSE
                )
                chunks.append(Chunk(
                    content=protected_content,
                    section_path=path + [title],
                    section_level=level,
                    page_number=0,
                    content_type=protected_type,
                    preceding_section=preceding,
                    following_section=following,
                    has_tables=protected_type == ContentType.TABLE,
                    has_code_blocks=protected_type == ContentType.CODE_BLOCK
                ))
                continue
            
            # Would adding this paragraph exceed target?
            if current_size + para_size > self.config.target_chunk_size and current_chunk:
                # Flush current chunk
                chunk_content = '\n\n'.join(current_chunk)
                chunk_content = self._restore_protected(chunk_content, protected_elements)
                chunks.append(self._create_chunk(
                    chunk_content, title, level, path,
                    preceding, following, has_tables, has_code
                ))
                current_chunk = []
                current_size = 0
            
            current_chunk.append(para)
            current_size += para_size
        
        # Flush remaining content
        if current_chunk:
            chunk_content = '\n\n'.join(current_chunk)
            chunk_content = self._restore_protected(chunk_content, protected_elements)
            chunks.append(self._create_chunk(
                chunk_content, title, level, path,
                preceding, following, has_tables, has_code
            ))
        
        return chunks
    
    def _restore_protected(
        self,
        content: str,
        protected_elements: list[tuple[str, str, ContentType]]
    ) -> str:
        """Restore protected elements in content."""
        for placeholder, original, _ in protected_elements:
            content = content.replace(placeholder, original)
        return content
    
    def _create_chunk(
        self,
        content: str,
        title: str,
        level: int,
        path: list[str],
        preceding: Optional[str],
        following: Optional[str],
        has_tables: bool,
        has_code: bool
    ) -> Chunk:
        """Create a Chunk object with proper metadata."""
        return Chunk(
            content=content,
            section_path=path + [title],
            section_level=level,
            page_number=0,
            content_type=self._detect_content_type(content),
            preceding_section=preceding,
            following_section=following,
            has_tables=has_tables,
            has_code_blocks=has_code
        )
    
    def _detect_content_type(self, content: str) -> ContentType:
        """Detect the primary content type of a text block."""
        # Check for tables
        if re.search(r'\|.+\|\n\|[-:\| ]+\|', content):
            return ContentType.TABLE
        
        # Check for code blocks
        if re.search(r'```[\s\S]*?```', content):
            return ContentType.CODE_BLOCK
        
        # Check for lists
        list_lines = len(re.findall(r'^[\s]*[-*+]\s', content, re.MULTILINE))
        list_lines += len(re.findall(r'^[\s]*\d+\.\s', content, re.MULTILINE))
        total_lines = content.count('\n') + 1
        
        if total_lines > 0 and list_lines / total_lines > 0.5:
            return ContentType.LIST
        
        # Check if it's just a heading
        if re.match(r'^#{1,6}\s+.+$', content.strip()) and '\n' not in content.strip():
            return ContentType.HEADING
        
        return ContentType.PROSE
