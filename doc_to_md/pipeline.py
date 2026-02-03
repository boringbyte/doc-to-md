"""Main conversion pipeline orchestrating PDF to Markdown conversion."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from .post_processing import (
    MetadataEnricher,
    MetadataEnricherConfig,
    SegmenterConfig,
    StructureAwareSegmenter,
    TOCProcessor,
    generate_markdown_output,
)
from .post_processing.markdown_cleanup import MarkdownCleanup, CleanupConfig
from .post_processing.heading_fixer import HeadingFixer, HeadingFixerConfig
from .post_processing.link_fixer import LinkFixer, LinkFixerConfig
from .post_processing.code_block_fixer import CodeBlockFixer, CodeBlockFixerConfig
from .post_processing.whitespace_normalizer import WhitespaceNormalizer, WhitespaceConfig
from .processing import (
    Chunk,
    ConversionResult,
    PDFConverterBase,
    PyMuPDFConverter,
)


logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the conversion pipeline."""
    # Converter backend (default: pymupdf4llm)
    converter: str = "pymupdf"
    
    # Segmentation settings
    segmenter_config: SegmenterConfig = field(default_factory=SegmenterConfig)
    
    # Metadata enrichment settings
    metadata_config: MetadataEnricherConfig = field(default_factory=MetadataEnricherConfig)
    
    # Post-processing settings
    cleanup_config: CleanupConfig = field(default_factory=CleanupConfig)
    heading_fixer_config: HeadingFixerConfig = field(default_factory=HeadingFixerConfig)
    link_fixer_config: LinkFixerConfig = field(default_factory=LinkFixerConfig)
    code_block_config: CodeBlockFixerConfig = field(default_factory=CodeBlockFixerConfig)
    whitespace_config: WhitespaceConfig = field(default_factory=WhitespaceConfig)
    
    # Output settings
    include_frontmatter: bool = True
    output_format: str = "markdown"  # "markdown" or "json"
    
    # Processing flags
    extract_toc: bool = True
    segment_content: bool = True
    enrich_metadata: bool = True
    
    # Post-processing flags
    run_cleanup: bool = True
    fix_headings: bool = True
    fix_links: bool = True
    fix_code_blocks: bool = False  # Off by default, can be too aggressive
    run_whitespace_norm: bool = True


class DocToMd:
    """Simplified entry point for PDF to Markdown conversion.
    
    This class can be initialized with all configuration options and then
    run on input files/directories.
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None, **kwargs):
        """Initialize with config or individual options.
        
        Args:
            config: Optional PipelineConfig object.
            **kwargs: Direct configuration options (e.g., segment_content=True, chunk_size=3000).
        """
        if config:
            self.config = config
        else:
            # Handle flattened segmenter config if provided
            segmenter_args = {}
            if 'chunk_size' in kwargs:
                segmenter_args['target_chunk_size'] = kwargs.pop('chunk_size')
            if 'max_chunk_size' in kwargs:
                segmenter_args['max_chunk_size'] = kwargs.pop('max_chunk_size')
            
            if segmenter_args:
                kwargs['segmenter_config'] = SegmenterConfig(**segmenter_args)
            
            self.config = PipelineConfig(**kwargs)
            
        self._converter: Optional[PDFConverterBase] = None
    
    @property
    def converter(self) -> PDFConverterBase:
        """Get or create the PDF converter."""
        if self._converter is None:
            if self.config.converter == "pymupdf":
                self._converter = PyMuPDFConverter()
            else:
                raise ValueError(f"Unknown converter: {self.config.converter}")
        return self._converter
    
    def convert(self, pdf_path: Union[str, Path]) -> ConversionResult:
        """Run the full conversion pipeline.
        
        Args:
            pdf_path: Path to the PDF file.
            
        Returns:
            ConversionResult with all extracted data.
        """
        path = Path(pdf_path)
        logger.info(f"Starting conversion of {path.name}")
        
        # Stage 1: PDF Conversion
        logger.info("Stage 1: Converting PDF to markdown")
        result = self.converter.convert(path)
        
        # Stage 2: TOC Processing
        if self.config.extract_toc and result.toc:
            logger.info("Stage 2: Processing table of contents")
            # This just verifies the TOC can be processed
            TOCProcessor(result.toc)
        
        # === MARKDOWN CLEANUP PROCESSING STAGES ===
        
        # Stage 3: Fix heading levels using TOC
        if self.config.fix_headings and result.toc:
            logger.info("Stage 3: Fixing heading levels from TOC")
            heading_fixer = HeadingFixer(result.toc, self.config.heading_fixer_config)
            result.markdown = heading_fixer.fix_headings(result.markdown)
        
        # Stage 4: Fix links
        if self.config.fix_links:
            logger.info("Stage 4: Fixing links")
            link_fixer = LinkFixer(self.config.link_fixer_config)
            result.markdown = link_fixer.fix_links(result.markdown)
        
        # Stage 5: Fix code blocks (optional, can be aggressive)
        if self.config.fix_code_blocks:
            logger.info("Stage 5: Fixing code blocks")
            code_fixer = CodeBlockFixer(self.config.code_block_config)
            result.markdown = code_fixer.fix_code_blocks(result.markdown)
        
        # Stage 6: Cleanup (whitespace normalization, page artifacts)
        if self.config.run_cleanup:
            logger.info("Stage 6: Cleaning up markdown")
            cleanup = MarkdownCleanup(self.config.cleanup_config)
            result.markdown = cleanup.clean(result.markdown)
 
        # Stage 7: Whitespace Normalization
        if self.config.run_whitespace_norm:
            logger.info("Stage 7: Normalizing whitespace")
            whitespace_norm = WhitespaceNormalizer(self.config.whitespace_config)
            result.markdown = whitespace_norm.normalize(result.markdown)
 
        # === POST MARKDOWN PROCESSING STAGES ===
 
        # Stage 8: Content Segmentation
        if self.config.segment_content:
            logger.info("Stage 8: Segmenting content")
            toc_processor = TOCProcessor(result.toc) if result.toc else None
            segmenter = StructureAwareSegmenter(
                toc_processor=toc_processor,
                config=self.config.segmenter_config
            )
            result.chunks = segmenter.segment(result.markdown)
            logger.info(f"Created {len(result.chunks)} chunks")
        
        # Stage 9: Metadata Enrichment
        if self.config.enrich_metadata and result.chunks:
            logger.info("Stage 9: Enriching metadata")
            enricher = MetadataEnricher(
                document_metadata=result.metadata,
                config=self.config.metadata_config
            )
            result.chunks = enricher.enrich_chunks(result.chunks)
        
        logger.info("Conversion complete")
        return result
    
    def run(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        output_format: Optional[str] = None
    ) -> Path:
        """High-level run method that saves result to file.
        
        Args:
            input_path: Path to input PDF.
            output_path: Optional output path.
            output_format: Optional format override (markdown/json).
            
        Returns:
            Path to the created file.
        """
        input_path = Path(input_path)
        output_format = output_format or self.config.output_format
        
        if output_path:
            output_path = Path(output_path)
        else:
            suffix = '.json' if output_format == 'json' else '.md'
            output_path = input_path.with_suffix(suffix)
            
        return self.convert_to_file(input_path, output_path, output_format)

    def convert_to_file(
        self,
        pdf_path: Union[str, Path],
        output_path: Union[str, Path],
        output_format: Optional[str] = None
    ) -> Path:
        """Internal helper to convert and write to specific file."""
        result = self.convert(pdf_path)
        output_path = Path(output_path)
        output_format = output_format or self.config.output_format
        
        if output_format == "json":
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        else:
            markdown = generate_markdown_output(
                result.chunks if result.chunks else [],
                result.metadata,
                include_frontmatter=self.config.include_frontmatter
            )
            # If no chunks, use raw markdown
            if not result.chunks:
                markdown = result.markdown
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
        
        logger.info(f"Output saved to {output_path}")
        return output_path
    
    def convert_directory(
        self,
        input_dir: Union[str, Path],
        output_dir: Union[str, Path],
        pattern: str = "*.pdf"
    ) -> list[Path]:
        """Convert all PDFs in a directory."""
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_paths = []
        for pdf_file in input_dir.glob(pattern):
            output_name = pdf_file.stem
            output_path = output_dir / output_name
            try:
                result_path = self.run(pdf_file, output_path)
                output_paths.append(result_path)
            except Exception as e:
                logger.error(f"Failed to convert {pdf_file}: {e}")
        
        return output_paths


# Alias for backward compatibility
ConversionPipeline = DocToMd


def quick_convert(pdf_path: Union[str, Path]) -> str:
    """Quick conversion function for simple use cases."""
    pipeline = DocToMd()
    result = pipeline.convert(pdf_path)
    
    if result.chunks:
        return generate_markdown_output(result.chunks, result.metadata)
    return result.markdown
