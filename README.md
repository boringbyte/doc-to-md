# Doc-to-MD: RAG-Optimized PDF to Markdown Converter

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Doc-to-MD** is a powerful PDF to Markdown conversion pipeline specifically engineered for high-accuracy **RAG (Retrieval-Augmented Generation)** applications. It doesn't just extract text; it preserves document hierarchy, optimizes segmentation, and enriches content with semantic metadata — producing chunks that are ready for vector database ingestion.

---

## 🚀 Why Doc-to-MD?

Standard PDF-to-text converters often fail RAG systems by creating cross-boundary context pollution. Doc-to-MD solves this by being **structure-aware**:

- 🏗️ **Hierarchical Preservation**: Uses the PDF's Table of Contents (TOC) to fix markdown heading levels.
- 🧩 **Semantic Segmentation**: Splits documents at logical section boundaries rather than arbitrary character limits.
- 🏷️ **Metadata Enrichment**: Injects section paths, content types, page ranges, and semantic labels into every chunk.
- 🧹 **Intelligent Cleanup**: Strips PDF artifacts (footers, page numbers, dot leaders) and normalizes malformed lists/bullets.
- 📎 **Embedded PDF Support**: Automatically detects and converts PDF attachments within portfolio PDFs.
- ⚡ **Batch & Parallel Processing**: Process entire directories with multiprocessing support and intelligent skip-existing logic.

---

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/boringbyte/doc-to-md.git
cd doc-to-md

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .

# Or install dependencies directly
pip install -r requirements.txt
```

### Dependencies

| Package | Purpose |
|---------|---------|
| `pymupdf` | Core PDF parsing engine |
| `pymupdf4llm` (≥0.2.9) | LLM-focused markdown extraction |
| `pymupdf-layout` (≥1.26.6) | Layout analysis for structured extraction |

---

## 🛠️ Usage

### Quick Start

```python
from doc_to_md import DocToMd, quick_convert

# One-liner for simple use cases
result = quick_convert("document.pdf")

# Or use the full API
converter = DocToMd(chunk_size=2000, output_format="markdown")
output_path = converter.run("manual.pdf", "output/")
```

### Programmatic API

Doc-to-MD provides a clean, class-based API for easy integration into your RAG pipelines.

```python
from doc_to_md import DocToMd

# Initialize with custom configuration
converter = DocToMd(
    chunk_size=2000,          # Target chunk size in characters
    max_chunk_size=4000,      # Maximum allowed chunk size
    output_format="markdown", # "markdown", "json", or "markdown,json"
    include_frontmatter=True, # Add YAML frontmatter to chunks
    process_embedded=True,    # Extract embedded PDF attachments
)

# Convert a single PDF and save to file
output_path = converter.run("manual.pdf", "output/manual.md")

# Or convert and get the rich ConversionResult object
result = converter.convert("document.pdf")
print(f"Title: {result.metadata.title}")
print(f"Pages: {result.metadata.page_count}")
print(f"TOC items: {len(result.toc)}")
print(f"Tables found: {len(result.tables)}")
print(f"Chunks generated: {len(result.chunks)}")

# Access individual chunks
for chunk in result.chunks:
    print(f"  [{chunk.content_type.value}] {chunk.section_path} (pages {chunk.page_range})")
```

### Dual Output Format

Generate both Markdown and JSON output simultaneously:

```python
converter = DocToMd(output_format="markdown,json")

# Returns a list of paths [Path("output.md"), Path("output.json")]
paths = converter.run("document.pdf", "output/")
```

### Batch Processing

Process an entire directory of PDFs with optional parallelism:

```python
converter = DocToMd(output_format="markdown,json")

# Sequential processing
paths = converter.convert_directory("input_pdfs/", output_dir="output/")

# Parallel processing with 4 workers
paths = converter.convert_directory(
    "input_pdfs/",
    output_dir="output/",
    workers=4,
    limit=100,          # Process first 100 files only
    overwrite=False,    # Skip files that already have output (default)
)
```

### Skip Existing Files

By default, batch processing **skips files that already have output**. This is useful for resuming interrupted jobs or incrementally processing new files added to a directory.

```python
# First run: processes all 500 PDFs
converter.convert_directory("pdfs/", output_dir="output/")

# Second run: skips all 500 (nothing to do)
converter.convert_directory("pdfs/", output_dir="output/")

# Force re-process everything
converter.convert_directory("pdfs/", output_dir="output/", overwrite=True)
```

The skip check is **format-aware**: if you request `markdown,json`, a file is only skipped when *both* `.md` and `.json` outputs exist. If either is missing, the file is re-processed.

---

### Command Line Interface

Process files directly from your terminal.

#### `convert` — Single File

```bash
# Basic conversion
doc-to-md convert document.pdf -o output.md

# With custom chunking and JSON output
doc-to-md convert manual.pdf --chunk-size 1500 --format json -o output.json

# Dual format output
doc-to-md convert manual.pdf --format markdown,json -o output/

# Without YAML frontmatter
doc-to-md convert document.pdf --no-frontmatter

# Skip embedded PDF attachments
doc-to-md convert portfolio.pdf --no-embedded
```

#### `batch` — Directory Processing

```bash
# Process all PDFs in a directory
doc-to-md batch input_pdfs/ -o converted/

# Parallel processing with 4 workers, limit to 50 files
doc-to-md batch input_pdfs/ -o converted/ --workers 4 --limit 50

# Force overwrite existing output files
doc-to-md batch input_pdfs/ -o converted/ --overwrite

# Generate both markdown and JSON
doc-to-md batch input_pdfs/ -o converted/ --format markdown,json
```

#### `info` — PDF Inspection

```bash
# View PDF metadata and table of contents
doc-to-md info document.pdf
```

Example output:

```
[FILE] document.pdf
==================================================
Title:    User Guide v2.0
Author:   ACME Corp
Subject:  Product Documentation
Pages:    342
Created:  D:20241015120000
Modified: D:20241020153000

[TOC] Table of Contents (45 items)
--------------------------------------------------
Chapter 1: Introduction (p.1)
  Getting Started (p.3)
  System Requirements (p.5)
Chapter 2: Installation (p.12)
  ...
```

#### CLI Reference

| Command | Flag | Description |
|---------|------|-------------|
| `convert` | `input` | Path to input PDF file |
| | `-o, --output` | Output file/directory path |
| | `-f, --format` | Output format: `markdown`, `json`, or `markdown,json` |
| | `--chunk-size` | Target chunk size in characters (default: 2000) |
| | `--max-chunk-size` | Maximum chunk size in characters (default: 4000) |
| | `--no-frontmatter` | Disable YAML frontmatter in output |
| | `--no-embedded` | Skip processing embedded PDF attachments |
| `batch` | `input_dir` | Directory containing PDF files |
| | `-o, --output-dir` | Output directory (default: `input_dir/converted`) |
| | `-f, --format` | Output format(s) |
| | `-n, --limit` | Max number of files to process |
| | `-w, --workers` | Parallel workers (default: 1 = sequential) |
| | `--overwrite` | Overwrite existing files (default: skip) |
| | `--no-frontmatter` | Disable YAML frontmatter |
| | `--no-embedded` | Skip embedded PDF attachments |
| `info` | `input` | Path to PDF file to inspect |
| (global) | `-v, --verbose` | Enable debug-level logging |

---

## 🏗️ Architecture

The pipeline follows a structured extraction and enrichment flow:

```
                PDF File
                   │
                   ▼
┌──────────────────────────────────────┐
│  1. EXTRACTION (PyMuPDFConverter)    │
│  • Markdown text via pymupdf4llm     │
│  • TOC, metadata, tables in 1 open   │
│  • Embedded PDF detection            │
└──────────────────┬───────────────────┘
                   ▼
┌──────────────────────────────────────┐
│  2. POST-PROCESSING                  │
│  ┌─────────────────────────────────┐ │
│  │ Markdown Cleanup                │ │
│  │ • Remove page footers/numbers   │ │
│  │ • Fix broken sentences          │ │
│  │ • Normalize bullets & lists     │ │
│  │ • Remove redundant TOC pages    │ │
│  └─────────────────────────────────┘ │
│  ┌─────────────────────────────────┐ │
│  │ Heading Fixer                   │ │
│  │ • Align headings with PDF TOC   │ │
│  │ • Fix heading level hierarchy   │ │
│  └─────────────────────────────────┘ │
│  ┌─────────────────────────────────┐ │
│  │ Link / Code Block Fixers        │ │
│  │ • Repair broken markdown links  │ │
│  │ • Fix code block formatting     │ │
│  └─────────────────────────────────┘ │
│  ┌─────────────────────────────────┐ │
│  │ Whitespace Normalizer           │ │
│  │ • Consistent spacing throughout │ │
│  └─────────────────────────────────┘ │
└──────────────────┬───────────────────┘
                   ▼
┌──────────────────────────────────────┐
│  3. SEGMENTATION                     │
│  • Split at section boundaries       │
│  • Preserve tables & code blocks     │
│  • Respect chunk size limits         │
│  • Track page ranges per chunk       │
└──────────────────┬───────────────────┘
                   ▼
┌──────────────────────────────────────┐
│  4. METADATA ENRICHMENT              │
│  • Section paths & hierarchy         │
│  • Content type classification       │
│  • Semantic labels (auto-generated)  │
│  • Navigation context (prev/next)    │
└──────────────────┬───────────────────┘
                   ▼
  Output: .md (with frontmatter) and/or .json
```

### Module Structure

```
doc_to_md/
├── __init__.py                  # Public API exports
├── pipeline.py                  # DocToMd, PipelineConfig, ConversionPipeline
├── cli.py                       # Command-line interface
├── processing/
│   ├── models.py                # Data models (Chunk, Section, ConversionResult, etc.)
│   ├── converter_interface.py   # Abstract base class for PDF converters
│   └── pymupdf_converter.py     # PyMuPDF-based converter implementation
└── post_processing/
    ├── markdown_cleanup.py      # PDF artifact removal & formatting fixes
    ├── heading_fixer.py         # TOC-synchronized heading correction
    ├── link_fixer.py            # Broken link repair
    ├── code_block_fixer.py      # Code block formatting normalization
    ├── whitespace_normalizer.py # Whitespace consistency
    ├── toc_processor.py         # Table of Contents processing
    ├── segmenter.py             # Structure-aware content chunking
    └── metadata_enricher.py     # Semantic metadata injection
```

---

## ⚙️ Configuration

### PipelineConfig

All configuration is managed through the `PipelineConfig` dataclass. You can pass options directly as keyword arguments to `DocToMd()`:

```python
from doc_to_md import DocToMd

converter = DocToMd(
    # Segmentation
    chunk_size=2000,          # Target chunk size (chars)
    max_chunk_size=4000,      # Hard max chunk size (chars)

    # Output
    output_format="markdown", # "markdown", "json", or "markdown,json"
    include_frontmatter=True, # YAML frontmatter per chunk
    
    # Processing toggles
    extract_toc=True,         # Extract table of contents
    segment_content=True,     # Enable semantic chunking
    enrich_metadata=True,     # Add semantic labels & stats
    process_embedded=True,    # Convert embedded PDF attachments
    
    # Post-processing toggles
    run_cleanup=True,         # Markdown cleanup (footers, bullets, etc.)
    fix_headings=True,        # TOC-aligned heading correction
    fix_links=True,           # Repair broken markdown links
    fix_code_blocks=False,    # Code block formatting (can be aggressive)
    run_whitespace_norm=True, # Whitespace normalization
    
    # Performance
    workers=1,                # Parallel workers for batch (1 = sequential)
    overwrite=False,          # Skip existing output files in batch mode
)
```

### Advanced Configuration

For finer control, pass sub-configuration objects:

```python
from doc_to_md.pipeline import PipelineConfig
from doc_to_md.post_processing import SegmenterConfig
from doc_to_md.post_processing.markdown_cleanup import CleanupConfig

config = PipelineConfig(
    segmenter_config=SegmenterConfig(
        target_chunk_size=1500,
        max_chunk_size=3000,
        min_chunk_size=200,
        preserve_tables=True,       # Keep tables as atomic chunks
        preserve_code_blocks=True,  # Keep code blocks as atomic chunks
    ),
    cleanup_config=CleanupConfig(
        max_consecutive_blanks=1,
        remove_page_footers=True,
        remove_orphan_page_numbers=True,
        normalize_hr=True,
        fix_broken_sentences=True,
        cleanup_bold=True,
        trim_trailing_whitespace=True,
        remove_redundant_toc=True,
    ),
)

converter = DocToMd(config=config)
```

---

## 📄 Output Formats

### Markdown (with YAML Frontmatter)

Each chunk is wrapped in YAML frontmatter, making it ready for vector database ingestion:

```markdown
---
section_path: ["Chapter 3", "Configuration", "Network Settings"]
parent_section: "Configuration"
section_level: 3
page_start: 142
page_end: 145
page_range: "142-145"
content_type: prose
preceding_section: "Storage Settings"
following_section: "Security Settings"
has_tables: false
has_code_blocks: false
chunk_index: 45
---

## Network Settings

Configure the identity settings for multiple network interfaces...
```

### JSON

The JSON output contains the full `ConversionResult` including all chunks, metadata, TOC, and tables:

```json
{
  "markdown": "...",
  "toc": [
    {"level": 1, "title": "Chapter 1: Introduction", "page_number": 1},
    {"level": 2, "title": "Getting Started", "page_number": 3}
  ],
  "tables": [
    {"content": "|Col1|Col2|\n|---|---|\n|A|B|", "page_number": 0, "row_count": 2, "col_count": 2}
  ],
  "metadata": {
    "title": "User Guide",
    "author": "ACME Corp",
    "page_count": 342,
    "source_file": "manual.pdf"
  },
  "sections": [...],
  "chunks": [
    {
      "content": "## Network Settings\n\nConfigure the identity...",
      "section_path": ["Chapter 3", "Configuration", "Network Settings"],
      "parent_section": "Configuration",
      "section_level": 3,
      "page_start": 142,
      "page_end": 145,
      "page_range": "142-145",
      "content_type": "prose",
      "preceding_section": "Storage Settings",
      "following_section": "Security Settings",
      "has_tables": false,
      "has_code_blocks": false,
      "chunk_index": 45
    }
  ]
}
```

---

## 📎 Embedded PDF Support

Doc-to-MD automatically detects and converts PDF attachments found inside portfolio PDFs. This is common in enterprise documentation where multiple documents are bundled together.

```python
converter = DocToMd(process_embedded=True)  # Enabled by default

result = converter.convert("portfolio.pdf")

# Access embedded results
for embedded in result.embedded_results:
    print(f"Embedded: {embedded.metadata.source_file}")
    print(f"  Chunks: {len(embedded.chunks)}")
```

When saving to file, embedded PDF outputs are placed in a subdirectory named after the parent file:

```
output/
├── portfolio.md            # Parent document
├── portfolio.json          # Parent JSON (if requested)
└── portfolio_embedded/     # Embedded documents
    ├── user-guide.md
    ├── user-guide.json
    ├── admin-manual.md
    └── admin-manual.json
```

To disable embedded processing:

```python
converter = DocToMd(process_embedded=False)
# Or via CLI:
# doc-to-md convert portfolio.pdf --no-embedded
```

---

## 📊 Data Models

Doc-to-MD uses rich data models throughout the pipeline:

| Model                 | Description |
|-----------------------|-------------|
| `ConversionResult`    | Top-level result containing markdown, TOC, tables, metadata, sections, chunks, and embedded results |
| `DocumentMetadata`    | PDF metadata (title, author, subject, keywords, dates, page count, source file) |
| `TOCItem`             | Table of Contents entry (level, title, page number) |
| `TableData`           | Extracted table with content, dimensions, and page number |
| `Section`             | Document section with hierarchy, page range, and content types |
| `Chunk`               | RAG-optimized content chunk with full metadata context |
| `EmbeddedPDF`         | Embedded PDF attachment (name, filename, raw data) |
| `ContentType`         | Enum: `prose`, `table`, `list`, `code_block`, `heading`, `mixed` |

All models support `.to_dict()` for serialization, and `Chunk` additionally provides `.to_frontmatter()` and `.to_markdown()` methods.

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run a specific test file
python -m pytest tests/test_pipeline.py

# Run with coverage
python -m pytest --cov=doc_to_md
```

---

## 🗂️ Project Structure

```
doc-to-md/
├── doc_to_md/              # Main package
│   ├── __init__.py          # Public exports
│   ├── pipeline.py          # Core pipeline & DocToMd API
│   ├── cli.py               # CLI entry point
│   ├── processing/          # PDF extraction layer
│   └── post_processing/     # Cleanup, segmentation, enrichment
├── tests/                   # Test suite
├── pyproject.toml           # Project configuration
├── requirements.txt         # Pinned dependencies
├── LICENSE                  # MIT License
└── README.md                # This file
```

---

## 📜 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
