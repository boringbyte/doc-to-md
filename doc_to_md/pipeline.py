"""Main conversion pipeline orchestrating PDF to Markdown conversion."""

import json
import logging
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
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
    include_frontmatter: bool = False
    include_chunk_metadata: bool = False  # Toggle chunk-level metadata in markdown
    output_format: Union[str, list[str]] = "markdown"  # "markdown", "json", or list e.g. ["markdown", "json"]
    
    # Processing flags
    extract_toc: bool = True
    segment_content: bool = True
    enrich_metadata: bool = True
    process_embedded: bool = True  # Process embedded PDF attachments
    
    # Performance
    workers: int = 1  # Number of parallel workers for batch processing
    overwrite: bool = False  # If False (default), skip files that already have output
    
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
        
        # Stage 10: Process embedded PDFs (single open instead of has+get)
        if self.config.process_embedded and hasattr(self.converter, 'extract_embedded_pdfs'):
            embedded_pdfs = self.converter.extract_embedded_pdfs(path)
            if embedded_pdfs:
                logger.info(f"Found {len(embedded_pdfs)} embedded PDFs")
                for emb_pdf in embedded_pdfs:
                    try:
                        emb_result = self._convert_embedded_pdf(emb_pdf)
                        result.embedded_results.append(emb_result)
                        logger.info(f"  Converted embedded: {emb_pdf.filename}")
                    except Exception as e:
                        logger.error(f"  Failed to convert embedded '{emb_pdf.filename}': {e}")
        
        return result
    
    def _convert_embedded_pdf(self, embedded_pdf) -> ConversionResult:
        """Convert an embedded PDF by writing it to a temp file and running the pipeline."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(embedded_pdf.data)
            tmp_path = Path(tmp.name)
        
        try:
            # Create a sub-pipeline without embedded processing to avoid recursion
            sub_pipeline = DocToMd(config=PipelineConfig(
                converter=self.config.converter,
                segmenter_config=self.config.segmenter_config,
                metadata_config=self.config.metadata_config,
                cleanup_config=self.config.cleanup_config,
                heading_fixer_config=self.config.heading_fixer_config,
                link_fixer_config=self.config.link_fixer_config,
                code_block_config=self.config.code_block_config,
                whitespace_config=self.config.whitespace_config,
                include_frontmatter=self.config.include_frontmatter,
                include_chunk_metadata=self.config.include_chunk_metadata,
                output_format=self.config.output_format,
                extract_toc=self.config.extract_toc,
                segment_content=self.config.segment_content,
                enrich_metadata=self.config.enrich_metadata,
                process_embedded=False,  # Don't recurse
                run_cleanup=self.config.run_cleanup,
                fix_headings=self.config.fix_headings,
                fix_links=self.config.fix_links,
                fix_code_blocks=self.config.fix_code_blocks,
                run_whitespace_norm=self.config.run_whitespace_norm,
            ))
            result = sub_pipeline.convert(tmp_path)
            # Override source_file metadata with the embedded filename
            result.metadata.source_file = embedded_pdf.filename
            return result
        finally:
            tmp_path.unlink(missing_ok=True)
    
    def run(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        output_format: Optional[str] = None
    ) -> Path:
        """High-level run method that saves result to file.
        
        Args:
            input_path: Path to input PDF.
            output_path: Optional output path. Can be:
                - A file path (e.g., "output/result.md")
                - A directory path (e.g., "output/") — file is named after input
                - None — output is created next to the input file
            output_format: Optional format override ("markdown", "json", or "markdown,json").
            
        Returns:
            Path to the created file, or list of Paths if multiple formats.
        """
        input_path = Path(input_path)
        output_format = output_format or self.config.output_format
        
        logger.info(f"Started processing: {input_path.name}")
        start_time = time.time()
        
        # Handle multiple formats
        if isinstance(output_format, str) and ',' in output_format:
            output_format = [f.strip() for f in output_format.split(',')]
            
        if isinstance(output_format, list):
            results = []
            # Run conversion once
            result = self.convert(input_path)
            for fmt in output_format:
                current_output = self._resolve_output_path(input_path, output_path, fmt)
                results.append(self.convert_to_file(input_path, current_output, fmt, conversion_result=result))
            
            end_time = time.time()
            logger.info(f"Finished processing: {input_path.name} in {end_time - start_time:.2f}s")
            return results[0] if len(results) == 1 else results
        
        resolved_output = self._resolve_output_path(input_path, output_path, output_format)
        final_path = self.convert_to_file(input_path, resolved_output, output_format)
        
        end_time = time.time()
        logger.info(f"Finished processing: {input_path.name} in {end_time - start_time:.2f}s")
        return final_path
    
    @staticmethod
    def _resolve_output_path(
        input_path: Path,
        output_path: Optional[Union[str, Path]],
        output_format: str
    ) -> Path:
        """Resolve the output file path from input path, output path, and format."""
        suffix = '.json' if output_format == 'json' else '.md'
        
        if not output_path:
            return input_path.with_suffix(suffix)
        
        output_path = Path(output_path)
        if output_path.is_dir():
            output_path.mkdir(parents=True, exist_ok=True)
            return output_path / f"{input_path.stem}{suffix}"
        
        return output_path

    def convert_to_file(
        self,
        pdf_path: Union[str, Path],
        output_path: Union[str, Path],
        output_format: Optional[str] = None,
        conversion_result: Optional[ConversionResult] = None
    ) -> Path:
        """Internal helper to convert and write to specific file."""
        result = conversion_result or self.convert(pdf_path)
        output_path = Path(output_path)
        output_format = output_format or self.config.output_format
        
        # Save embedded PDF results first if they exist
        embedded_paths = []
        if result.embedded_results:
            embedded_paths = self._save_embedded_results(
                result.embedded_results,
                output_path,
                output_format
            )
        
        if output_format == "json":
            result_dict = result.to_dict(include_embedded=False)
            
            # Inject relative paths to embedded results into the parent JSON
            if embedded_paths and "embedded_documents" in result_dict:
                for i, emb_doc in enumerate(result_dict["embedded_documents"]):
                    if i < len(embedded_paths):
                        # Store relative path from the parent JSON file's directory
                        rel_path = embedded_paths[i].name
                        # If it's in a sub-dir (which it is), include the sub-dir name
                        sub_dir_name = output_path.stem
                        emb_doc["output_path"] = f"{sub_dir_name}/{rel_path}"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result_dict, f, indent=2, ensure_ascii=False)
        else:
            markdown = generate_markdown_output(
                result.chunks if result.chunks else [],
                result.metadata,
                include_frontmatter=self.config.include_frontmatter,
                include_chunk_metadata=self.config.include_chunk_metadata
            )
            # If no chunks, use raw markdown
            if not result.chunks:
                markdown = result.markdown
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
        
        logger.info(f"Output saved to {output_path}")
        return output_path
    
    def _save_embedded_results(
        self,
        embedded_results: list[ConversionResult],
        parent_output_path: Path,
        output_format: str
    ) -> list[Path]:
        """Save embedded PDF conversion results to a subdirectory."""
        # Create subdirectory named after parent file
        sub_dir = parent_output_path.parent / parent_output_path.stem
        sub_dir.mkdir(parents=True, exist_ok=True)
        
        saved_paths = []
        for emb_result in embedded_results:
            emb_name = emb_result.metadata.source_file or "embedded"
            suffix = '.json' if output_format == 'json' else '.md'
            emb_output_path = sub_dir / f"{emb_name}{suffix}"
            
            if output_format == "json":
                with open(emb_output_path, 'w', encoding='utf-8') as f:
                    json.dump(emb_result.to_dict(), f, indent=2, ensure_ascii=False)
            else:
                markdown = generate_markdown_output(
                    emb_result.chunks if emb_result.chunks else [],
                    emb_result.metadata,
                    include_frontmatter=self.config.include_frontmatter,
                    include_chunk_metadata=self.config.include_chunk_metadata
                )
                if not emb_result.chunks:
                    markdown = emb_result.markdown
                with open(emb_output_path, 'w', encoding='utf-8') as f:
                    f.write(markdown)
            
            logger.info(f"  Embedded output saved to {emb_output_path}")
            saved_paths.append(emb_output_path)
        
        return saved_paths
    
    def convert_directory(
        self,
        input_dir: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
        pattern: str = "*.pdf",
        limit: Optional[int] = None,
        output_format: Optional[str] = None,
        workers: Optional[int] = None,
        overwrite: Optional[bool] = None
    ) -> list[Path]:
        """Convert all PDFs in a directory.
        
        Args:
            input_dir: Directory containing PDF files.
            output_dir: Output directory (default: input_dir/converted).
            pattern: Glob pattern (default: "*.pdf").
            limit: Max number of files to process (default: None = all).
            output_format: Override output format (e.g. "markdown", "json", "markdown,json").
            workers: Number of parallel workers (default: from config, 1 = sequential).
            overwrite: Whether to overwrite existing files (default: from config, False).
            
        Returns:
            List of output file paths.
        """
        input_dir = Path(input_dir)
        if output_dir is None:
            output_dir = input_dir / "converted"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        pdf_files = sorted(input_dir.glob(pattern))
        total = len(pdf_files)
        
        if limit and limit > 0:
            pdf_files = pdf_files[:limit]
        
        should_overwrite = overwrite if overwrite is not None else self.config.overwrite
        skipped_files = []
        
        if not should_overwrite:
            to_process = []
            fmt = output_format or self.config.output_format
            
            # Normalize formats
            if isinstance(fmt, str):
                formats = [f.strip() for f in fmt.split(',')]
            elif isinstance(fmt, list):
                formats = fmt
            else:
                formats = [fmt]
            
            for pdf_file in pdf_files:
                all_exist = True
                for f in formats:
                    out_path = self._resolve_output_path(pdf_file, output_dir, f)
                    if not out_path.exists():
                        all_exist = False
                        break
                
                if all_exist:
                    skipped_files.append(pdf_file)
                else:
                    to_process.append(pdf_file)
            
            if skipped_files:
                logger.info(f"Skipping {len(skipped_files)} files as they already exist: {[f.name for f in skipped_files]}")
            pdf_files = to_process
            
        num_workers = workers or self.config.workers
        batch_start_time = time.time()
        
        if num_workers > 1 and len(pdf_files) > 1:
            output_paths = self._convert_directory_parallel(
                pdf_files, output_dir, output_format, num_workers
            )
        else:
            output_paths = self._convert_directory_sequential(
                pdf_files, output_dir, output_format
            )
            
        batch_end_time = time.time()
        duration = batch_end_time - batch_start_time
        logger.info(f"Batch processing completed: {len(output_paths)} files processed in {duration:.2f}s")
        if len(output_paths) < total:
            skipped = len(skipped_files) if not should_overwrite else 0
            logger.info(f"({total} files total: {len(output_paths)} processed, {skipped} skipped)")
        
        return output_paths
    
    def _convert_directory_sequential(
        self,
        pdf_files: list[Path],
        output_dir: Path,
        output_format: Optional[str] = None
    ) -> list[Path]:
        """Convert files sequentially (workers=1)."""
        count = len(pdf_files)
        logger.info(f"Processing {count} PDF files sequentially")
        
        output_paths = []
        for i, pdf_file in enumerate(pdf_files, 1):
            try:
                # Timing is now handled inside run()
                result_path = self.run(pdf_file, output_dir, output_format=output_format)
                output_paths.append(result_path)
            except Exception as e:
                logger.error(f"Failed {pdf_file.name}: {e}")
        
        return output_paths
    
    def _convert_directory_parallel(
        self,
        pdf_files: list[Path],
        output_dir: Path,
        output_format: Optional[str],
        num_workers: int
    ) -> list[Path]:
        """Convert files in parallel using ProcessPoolExecutor."""
        count = len(pdf_files)
        effective_workers = min(num_workers, count)
        logger.info(f"Processing {count} PDF files with {effective_workers} workers")
        
        # Build config kwargs for the worker (must be picklable)
        config_kwargs = {
            'output_format': self.config.output_format,
            'include_frontmatter': self.config.include_frontmatter,
            'process_embedded': self.config.process_embedded,
        }
        
        output_paths = []
        failed = 0
        
        with ProcessPoolExecutor(max_workers=effective_workers) as executor:
            future_to_file = {
                executor.submit(
                    _convert_single_file,
                    pdf_file,
                    output_dir,
                    output_format or self.config.output_format,
                    config_kwargs
                ): pdf_file
                for pdf_file in pdf_files
            }
            
            for future in as_completed(future_to_file):
                pdf_file = future_to_file[future]
                try:
                    result_path = future.result()
                    output_paths.append(result_path)
                except Exception as e:
                    failed += 1
                    logger.error(f"[FAIL] {pdf_file.name}: {e}")
        
        return output_paths


def _convert_single_file(
    pdf_path: Path,
    output_dir: Path,
    output_format: str,
    config_kwargs: dict
) -> Path:
    """Module-level function for multiprocessing (must be picklable).
    
    Creates a fresh DocToMd instance in the worker process and converts one file.
    """
    pipeline = DocToMd(**config_kwargs)
    return pipeline.run(pdf_path, output_dir, output_format=output_format)


# Alias for backward compatibility
ConversionPipeline = DocToMd


def quick_convert(pdf_path: Union[str, Path]) -> str:
    """Quick conversion function for simple use cases."""
    pipeline = DocToMd()
    result = pipeline.convert(pdf_path)
    
    if result.chunks:
        return generate_markdown_output(result.chunks, result.metadata)
    return result.markdown
