"""Command-line interface for doc-to-md converter."""

import argparse
import logging
import sys
from pathlib import Path

from .pipeline import ConversionPipeline, PipelineConfig
from .post_processing import SegmenterConfig


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )


def cmd_convert(args: argparse.Namespace) -> int:
    """Handle the convert command."""
    pdf_path = Path(args.input)
    
    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}", file=sys.stderr)
        return 1
    
    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = pdf_path.with_suffix('.md')
    
    # Configure pipeline
    segmenter_config = SegmenterConfig(
        target_chunk_size=args.chunk_size,
        max_chunk_size=args.max_chunk_size,
    )
    
    config = PipelineConfig(
        segmenter_config=segmenter_config,
        output_format=args.format,
        include_frontmatter=not args.no_frontmatter,
    )
    
    pipeline = ConversionPipeline(config)
    
    try:
        result_path = pipeline.convert_to_file(pdf_path, output_path)
        print(f"[OK] Converted: {pdf_path.name} -> {result_path.name}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def cmd_batch(args: argparse.Namespace) -> int:
    """Handle the batch command for directory processing."""
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir) if args.output_dir else input_dir / "converted"
    
    if not input_dir.exists():
        print(f"Error: Directory not found: {input_dir}", file=sys.stderr)
        return 1
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    config = PipelineConfig(
        output_format=args.format,
        include_frontmatter=not args.no_frontmatter,
    )
    
    pipeline = ConversionPipeline(config)
    
    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {input_dir}")
        return 0
    
    print(f"Found {len(pdf_files)} PDF files")
    
    success_count = 0
    for pdf_file in pdf_files:
        output_path = output_dir / pdf_file.stem
        try:
            result_path = pipeline.convert_to_file(pdf_file, output_path)
            print(f"[OK] {pdf_file.name}")
            success_count += 1
        except Exception as e:
            print(f"[FAIL] {pdf_file.name}: {e}")
    
    print(f"\nConverted {success_count}/{len(pdf_files)} files")
    return 0 if success_count == len(pdf_files) else 1


def cmd_info(args: argparse.Namespace) -> int:
    """Handle the info command to show PDF metadata."""
    from .processing import PyMuPDFConverter
    
    pdf_path = Path(args.input)
    
    if not pdf_path.exists():
        print(f"Error: File not found: {pdf_path}", file=sys.stderr)
        return 1
    
    converter = PyMuPDFConverter()
    
    # Get metadata
    metadata = converter.get_metadata(pdf_path)
    print(f"\n[FILE] {pdf_path.name}")
    print("=" * 50)
    print(f"Title:    {metadata.title or 'N/A'}")
    print(f"Author:   {metadata.author or 'N/A'}")
    print(f"Subject:  {metadata.subject or 'N/A'}")
    print(f"Pages:    {metadata.page_count}")
    print(f"Created:  {metadata.creation_date or 'N/A'}")
    print(f"Modified: {metadata.modification_date or 'N/A'}")
    
    # Get TOC
    toc = converter.get_toc(pdf_path)
    if toc:
        print(f"\n[TOC] Table of Contents ({len(toc)} items)")
        print("-" * 50)
        for item in toc[:20]:  # Show first 20
            indent = "  " * (item.level - 1)
            print(f"{indent}{item.title} (p.{item.page_number})")
        if len(toc) > 20:
            print(f"  ... and {len(toc) - 20} more items")
    else:
        print("\n[!] No table of contents found in PDF")
    
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
        choices=['markdown', 'json'],
        default='markdown',
        help='Output format (default: markdown)'
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
        choices=['markdown', 'json'],
        default='markdown',
        help='Output format (default: markdown)'
    )
    batch_parser.add_argument(
        '--no-frontmatter',
        action='store_true',
        help='Disable YAML frontmatter in output'
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
