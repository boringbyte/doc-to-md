"""Metadata enricher for RAG-optimized chunk metadata."""

import re
from dataclasses import dataclass
from typing import Optional

from ..processing.models import Chunk, ContentType, DocumentMetadata


@dataclass
class MetadataEnricherConfig:
    """Configuration for metadata enrichment."""
    # Include document-level metadata in each chunk
    include_document_metadata: bool = True
    # Generate semantic labels based on content
    generate_semantic_labels: bool = True
    # Add word count to chunks
    add_word_count: bool = True


class MetadataEnricher:
    """Enriches chunks with additional metadata for RAG optimization.
    
    Features:
    - Adds document-level metadata to chunks
    - Generates semantic labels for filtering
    - Computes content statistics
    - Normalizes section paths
    """
    
    def __init__(
        self,
        document_metadata: Optional[DocumentMetadata] = None,
        config: Optional[MetadataEnricherConfig] = None
    ):
        """Initialize the metadata enricher.
        
        Args:
            document_metadata: Document-level metadata to propagate.
            config: Enrichment configuration.
        """
        self.document_metadata = document_metadata
        self.config = config or MetadataEnricherConfig()
    
    def enrich_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Enrich all chunks with additional metadata.
        
        Args:
            chunks: List of chunks to enrich.
            
        Returns:
            List of enriched chunks.
        """
        enriched = []
        
        for i, chunk in enumerate(chunks):
            enriched_chunk = self._enrich_single_chunk(chunk, i, len(chunks))
            enriched.append(enriched_chunk)
        
        return enriched
    
    def _enrich_single_chunk(
        self,
        chunk: Chunk,
        index: int,
        total_chunks: int
    ) -> Chunk:
        """Enrich a single chunk with metadata.
        
        Args:
            chunk: The chunk to enrich.
            index: Index of this chunk.
            total_chunks: Total number of chunks.
            
        Returns:
            Enriched chunk.
        """
        # Update chunk index
        chunk.chunk_index = index
        
        return chunk
    
    def generate_chunk_frontmatter(
        self,
        chunk: Chunk,
        include_document_info: bool = True
    ) -> str:
        """Generate YAML frontmatter for a chunk.
        
        Args:
            chunk: The chunk to generate frontmatter for.
            include_document_info: Whether to include document metadata.
            
        Returns:
            YAML frontmatter string.
        """
        lines = ["---"]
        
        # Section information
        lines.append(f"section_path: {chunk.section_path}")
        lines.append(f"section_level: {chunk.section_level}")
        
        # Navigation
        if chunk.preceding_section:
            lines.append(f'preceding_section: "{chunk.preceding_section}"')
        if chunk.following_section:
            lines.append(f'following_section: "{chunk.following_section}"')
        
        # Content metadata
        lines.append(f"content_type: {chunk.content_type.value}")
        lines.append(f"has_tables: {str(chunk.has_tables).lower()}")
        lines.append(f"has_code_blocks: {str(chunk.has_code_blocks).lower()}")
        
        # Position
        lines.append(f"chunk_index: {chunk.chunk_index}")
        lines.append(f"page_number: {chunk.page_number}")
        
        # Word count
        if self.config.add_word_count:
            word_count = len(chunk.content.split())
            lines.append(f"word_count: {word_count}")
        
        # Document metadata
        if include_document_info and self.document_metadata:
            if self.document_metadata.title:
                lines.append(f'document_title: "{self.document_metadata.title}"')
            if self.document_metadata.source_file:
                lines.append(f'source_file: "{self.document_metadata.source_file}"')
        
        # Semantic labels
        if self.config.generate_semantic_labels:
            labels = self._generate_semantic_labels(chunk)
            if labels:
                lines.append(f"semantic_labels: {labels}")
        
        lines.append("---")
        return "\n".join(lines)
    
    def _generate_semantic_labels(self, chunk: Chunk) -> list[str]:
        """Generate semantic labels for a chunk based on content analysis.
        
        Args:
            chunk: The chunk to analyze.
            
        Returns:
            List of semantic label strings.
        """
        labels = []
        content_lower = chunk.content.lower()
        
        # Section-based labels
        section_path_lower = [s.lower() for s in chunk.section_path]
        section_text = ' '.join(section_path_lower)
        
        # Common technical document patterns
        label_patterns = {
            "installation": ["install", "setup", "deploy", "configure"],
            "troubleshooting": ["troubleshoot", "error", "issue", "problem", "fix"],
            "configuration": ["config", "setting", "option", "parameter"],
            "reference": ["reference", "api", "command", "syntax"],
            "overview": ["overview", "introduction", "about", "summary"],
            "procedure": ["step", "procedure", "how to", "guide"],
            "specification": ["spec", "requirement", "dimension", "capacity"],
            "safety": ["warning", "caution", "safety", "danger"],
        }
        
        for label, patterns in label_patterns.items():
            if any(p in section_text or p in content_lower for p in patterns):
                labels.append(label)
        
        # Content type based labels
        if chunk.content_type == ContentType.TABLE:
            labels.append("tabular_data")
        if chunk.content_type == ContentType.CODE_BLOCK:
            labels.append("code_example")
        if chunk.content_type == ContentType.LIST:
            labels.append("enumerated")
        
        return labels


def generate_markdown_output(
    chunks: list[Chunk],
    document_metadata: Optional[DocumentMetadata] = None,
    include_frontmatter: bool = True
) -> str:
    """Generate final markdown output from chunks.
    
    Args:
        chunks: List of processed chunks.
        document_metadata: Optional document metadata.
        include_frontmatter: Whether to include YAML frontmatter.
        
    Returns:
        Complete markdown string.
    """
    enricher = MetadataEnricher(document_metadata)
    
    output_parts = []
    
    # Document-level frontmatter
    if include_frontmatter and document_metadata:
        doc_frontmatter = ["---"]
        if document_metadata.title:
            doc_frontmatter.append(f'title: "{document_metadata.title}"')
        if document_metadata.author:
            doc_frontmatter.append(f'author: "{document_metadata.author}"')
        if document_metadata.source_file:
            doc_frontmatter.append(f'source: "{document_metadata.source_file}"')
        doc_frontmatter.append(f"page_count: {document_metadata.page_count}")
        doc_frontmatter.append(f"chunk_count: {len(chunks)}")
        doc_frontmatter.append("---")
        output_parts.append("\n".join(doc_frontmatter))
        output_parts.append("")  # Blank line after frontmatter
    
    # Add each chunk
    current_section = []
    for chunk in chunks:
        # Track section changes for visual separation
        if chunk.section_path != current_section:
            if current_section:  # Not first section
                # We add an empty part which will become a blank line when joined
                output_parts.append("")
            current_section = chunk.section_path
        
        # Ensure chunk content is stripped of excessive newlines before adding
        content = chunk.content.strip()
        if content:
            output_parts.append(content)
    
    # Join parts with double newlines
    # Then run a final pass to ensure no triple newlines (though strip() helps)
    raw_markdown = "\n\n".join(output_parts)
    
    # Final cleanup of any accidental triple newlines created by the join
    return re.sub(r'\n([ \t]*\n){2,}', '\n\n', raw_markdown)
