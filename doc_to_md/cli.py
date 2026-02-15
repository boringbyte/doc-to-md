"""Command-line interface for doc-to-md converter."""

import argparse
import logging
import sys
from pathlib import Path

from .pipeline import DocToMd, ConversionPipeline, PipelineConfig
from .post_processing import SegmenterConfig


logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def cmd_convert(args: argparse.Namespace) -> int:
    """Handle the convert command."""
    pdf_path = Path(args.input)
    
    if not pdf_path.exists():
        logger.error(f"Error: File not found: {pdf_path}")
        return 1
    
    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = pdf_path.with_suffix('.md')
    
    # Configure pipeline using simplified API
    pipeline = DocToMd(
        chunk_size=args.chunk_size,
        max_chunk_size=args.max_chunk_size,
        output_format=args.format,
        include_frontmatter=not args.no_frontmatter,
        process_embedded=not args.no_embedded,
    )
    
    try:
        result = pipeline.run(pdf_path, output_path)
        if isinstance(result, list):
            paths = ", ".join([p.name for p in result])
            logger.info(f"[OK] Converted: {pdf_path.name} -> [{paths}]")
        else:
            logger.info(f"[OK] Converted: {pdf_path.name} -> {result.name}")
        return 0
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_batch(args: argparse.Namespace) -> int:
    """Handle the batch command for directory processing."""
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir) if args.output_dir else None
    
    if not input_dir.exists():
        logger.error(f"Error: Directory not found: {input_dir}")
        return 1
    
    # Configure pipeline using simplified API
    pipeline = DocToMd(
        output_format=args.format,
        include_frontmatter=not args.no_frontmatter,
        process_embedded=not args.no_embedded,
    )
    
    limit = getattr(args, 'limit', None)
    workers = getattr(args, 'workers', None)
    output_paths = pipeline.convert_directory(
        input_dir,
        output_dir=output_dir,
        limit=limit,
        workers=workers
    )
    
    if not output_paths:
        return 1
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Handle the info command to show PDF metadata."""
    from .processing import PyMuPDFConverter
    
    pdf_path = Path(args.input)
    
    if not pdf_path.exists():
        logger.error(f"Error: File not found: {pdf_path}")
        return 1
    
    converter = PyMuPDFConverter()
    
    # Get metadata
    metadata = converter.get_metadata(pdf_path)
    logger.info(f"\n[FILE] {pdf_path.name}")
    logger.info("=" * 50)
    logger.info(f"Title:    {metadata.title or 'N/A'}")
    logger.info(f"Author:   {metadata.author or 'N/A'}")
    logger.info(f"Subject:  {metadata.subject or 'N/A'}")
    logger.info(f"Pages:    {metadata.page_count}")
    logger.info(f"Created:  {metadata.creation_date or 'N/A'}")
    logger.info(f"Modified: {metadata.modification_date or 'N/A'}")
    
    # Get TOC
    toc = converter.get_toc(pdf_path)
    if toc:
        logger.info(f"\n[TOC] Table of Contents ({len(toc)} items)")
        logger.info("-" * 50)
        for item in toc[:20]:  # Show first 20
            indent = "  " * (item.level - 1)
            logger.info(f"{indent}{item.title} (p.{item.page_number})")
        if len(toc) > 20:
            logger.info(f"  ... and {len(toc) - 20} more items")
    else:
        logger.info("\n[!] No table of contents found in PDF")
    
    return 0


def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog='doc-to-md',
        description='Convert PDF documents to RAG-optimized Markdown'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Convert command
    convert_parser = subparsers.add_parser(
        'convert',
        help='Convert a single PDF file'
    )
    convert_parser.add_argument(
        'input',
        help='Path to input PDF file'
    )
    convert_parser.add_argument(
        '-o', '--output',
        help='Output file path (default: same as input with .md extension)'
    )
    convert_parser.add_argument(
        '-f', '--format',
        default='markdown',
        help='Output format(s), e.g., "markdown", "json", or "markdown,json" (default: markdown)'
    )
    convert_parser.add_argument(
        '--chunk-size',
        type=int,
        default=2000,
        help='Target chunk size in characters (default: 2000)'
    )
    convert_parser.add_argument(
        '--max-chunk-size',
        type=int,
        default=4000,
        help='Maximum chunk size in characters (default: 4000)'
    )
    convert_parser.add_argument(
        '--no-frontmatter',
        action='store_true',
        help='Disable YAML frontmatter in output'
    )
    convert_parser.add_argument(
        '--no-embedded',
        action='store_true',
        help='Skip processing embedded PDF attachments'
    )
    convert_parser.set_defaults(func=cmd_convert)
    
    # Batch command
    batch_parser = subparsers.add_parser(
        'batch',
        help='Convert all PDFs in a directory'
    )
    batch_parser.add_argument(
        'input_dir',
        help='Directory containing PDF files'
    )
    batch_parser.add_argument(
        '-o', '--output-dir',
        help='Output directory (default: input_dir/converted)'
    )
    batch_parser.add_argument(
        '-f', '--format',
        default='markdown',
        help='Output format(s), e.g., "markdown", "json", or "markdown,json" (default: markdown)'
    )
    batch_parser.add_argument(
        '--no-frontmatter',
        action='store_true',
        help='Disable YAML frontmatter in output'
    )
    batch_parser.add_argument(
        '--no-embedded',
        action='store_true',
        help='Skip processing embedded PDF attachments'
    )
    batch_parser.add_argument(
        '--limit', '-n',
        type=int,
        default=None,
        help='Max number of PDF files to process (default: all)'
    )
    batch_parser.add_argument(
        '--workers', '-w',
        type=int,
        default=None,
        help='Number of parallel workers for processing (default: 1 = sequential)'
    )
    batch_parser.set_defaults(func=cmd_batch)
    
    # Info command
    info_parser = subparsers.add_parser(
        'info',
        help='Show PDF metadata and table of contents'
    )
    info_parser.add_argument(
        'input',
        help='Path to PDF file'
    )
    info_parser.set_defaults(func=cmd_info)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    setup_logging(args.verbose)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
