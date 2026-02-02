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
    TableProcessor,
    TableProcessorConfig,
    TOCProcessor,
    generate_markdown_output,
)
from .post_processing.markdown_cleanup import MarkdownCleanup, CleanupConfig
from .post_processing.heading_fixer import HeadingFixer, HeadingFixerConfig
from .post_processing.table_merger import TableMerger, TableMergerConfig
from .post_processing.link_fixer import LinkFixer, LinkFixerConfig
from .post_processing.code_block_fixer import CodeBlockFixer, CodeBlockFixerConfig
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
    
    # Table processing settings
    table_config: TableProcessorConfig = field(default_factory=TableProcessorConfig)
    
    # Metadata enrichment settings
    metadata_config: MetadataEnricherConfig = field(default_factory=MetadataEnricherConfig)
    
    # Post-processing settings
    cleanup_config: CleanupConfig = field(default_factory=CleanupConfig)
    heading_fixer_config: HeadingFixerConfig = field(default_factory=HeadingFixerConfig)
    table_merger_config: TableMergerConfig = field(default_factory=TableMergerConfig)
    link_fixer_config: LinkFixerConfig = field(default_factory=LinkFixerConfig)
    code_block_config: CodeBlockFixerConfig = field(default_factory=CodeBlockFixerConfig)
    
    # Output settings
    include_frontmatter: bool = True
    output_format: str = "markdown"  # "markdown" or "json"
    
    # Processing flags
    extract_toc: bool = True
    process_tables: bool = True
    segment_content: bool = True
    enrich_metadata: bool = True
    
    # Post-processing flags (NEW)
    run_cleanup: bool = True
    fix_headings: bool = True
    merge_tables: bool = True
    fix_links: bool = True
    fix_code_blocks: bool = False  # Off by default, can be too aggressive


class ConversionPipeline:
    """Orchestrates the PDF to Markdown conversion process.
    
    Pipeline stages:
    1. PDF Conversion - Extract raw markdown, TOC, tables
    2. TOC Processing - Build hierarchical section structure
    3. Table Processing - Validate and enrich tables
    4. Content Segmentation - Split into RAG-optimized chunks
    5. Metadata Enrichment - Add labels and statistics
    6. Output Generation - Produce final markdown
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        """Initialize the pipeline.
        
        Args:
            config: Pipeline configuration.
        """
        self.config = config or PipelineConfig()
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
            toc_processor = TOCProcessor(result.toc)
            # TOC is already in result, processor is for section lookups
        
        # Stage 3: Table Processing
        if self.config.process_tables and result.tables:
            logger.info("Stage 3: Processing tables")
            table_processor = TableProcessor(self.config.table_config)
            result.markdown, result.tables = table_processor.process_tables(
                result.markdown, result.tables
            )
        
        # Stages 4 and 5 moved to the end to ensure they process cleaned content
        
        # === POST-PROCESSING STAGES ===
        
        # Stage 6: Merge split tables
        if self.config.merge_tables:
            logger.info("Stage 6: Merging split tables")
            table_merger = TableMerger(self.config.table_merger_config)
            result.markdown = table_merger.merge_tables(result.markdown)
        
        # Stage 7: Fix heading levels using TOC
        if self.config.fix_headings and result.toc:
            logger.info("Stage 7: Fixing heading levels from TOC")
            heading_fixer = HeadingFixer(result.toc, self.config.heading_fixer_config)
            result.markdown = heading_fixer.fix_headings(result.markdown)
        
        # Stage 8: Fix links
        if self.config.fix_links:
            logger.info("Stage 8: Fixing links")
            link_fixer = LinkFixer(self.config.link_fixer_config)
            result.markdown = link_fixer.fix_links(result.markdown)
        
        # Stage 9: Fix code blocks (optional, can be aggressive)
        if self.config.fix_code_blocks:
            logger.info("Stage 9: Fixing code blocks")
            code_fixer = CodeBlockFixer(self.config.code_block_config)
            result.markdown = code_fixer.fix_code_blocks(result.markdown)
        
        # Stage 10: Cleanup (whitespace normalization, page artifacts)
        # Run this last to clean up any artifacts from previous stages
        if self.config.run_cleanup:
            logger.info("Stage 10: Cleaning up markdown")
            cleanup = MarkdownCleanup(self.config.cleanup_config)
            result.markdown = cleanup.clean(result.markdown)

        # Stage 11 (Formerly 4): Content Segmentation
        # Moved after cleanup to ensure chunks contain clean text
        if self.config.segment_content:
            logger.info("Stage 11: Segmenting content")
            toc_processor = TOCProcessor(result.toc) if result.toc else None
            segmenter = StructureAwareSegmenter(
                toc_processor=toc_processor,
                config=self.config.segmenter_config
            )
            result.chunks = segmenter.segment(result.markdown)
            logger.info(f"Created {len(result.chunks)} chunks")
        
        # Stage 12 (Formerly 5): Metadata Enrichment
        if self.config.enrich_metadata and result.chunks:
            logger.info("Stage 12: Enriching metadata")
            enricher = MetadataEnricher(
                document_metadata=result.metadata,
                config=self.config.metadata_config
            )
            result.chunks = enricher.enrich_chunks(result.chunks)
        
        logger.info("Conversion complete")
        return result
    
    def convert_to_file(
        self,
        pdf_path: Union[str, Path],
        output_path: Union[str, Path],
        output_format: Optional[str] = None
    ) -> Path:
        """Convert PDF and save to file.
        
        Args:
            pdf_path: Path to input PDF.
            output_path: Path for output file.
            output_format: Override output format (markdown/json).
            
        Returns:
            Path to created output file.
        """
        result = self.convert(pdf_path)
        output_path = Path(output_path)
        output_format = output_format or self.config.output_format
        
        if output_format == "json":
            output_path = output_path.with_suffix('.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result.to_dict(), f, indent=2)
        else:
            output_path = output_path.with_suffix('.md')
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
        """Convert all PDFs in a directory.
        
        Args:
            input_dir: Directory containing PDFs.
            output_dir: Directory for output files.
            pattern: Glob pattern for PDF files.
            
        Returns:
            List of created output paths.
        """
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_paths = []
        for pdf_file in input_dir.glob(pattern):
            output_name = pdf_file.stem
            output_path = output_dir / output_name
            try:
                result_path = self.convert_to_file(pdf_file, output_path)
                output_paths.append(result_path)
            except Exception as e:
                logger.error(f"Failed to convert {pdf_file}: {e}")
        
        return output_paths


def quick_convert(pdf_path: Union[str, Path]) -> str:
    """Quick conversion function for simple use cases.
    
    Args:
        pdf_path: Path to PDF file.
        
    Returns:
        Converted markdown string.
    """
    pipeline = ConversionPipeline()
    result = pipeline.convert(pdf_path)
    
    if result.chunks:
        return generate_markdown_output(result.chunks, result.metadata)
    return result.markdown
