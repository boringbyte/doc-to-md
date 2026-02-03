# Doc-to-MD: RAG-Optimized PDF to Markdown Converter

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Doc-to-MD** is a powerful PDF to Markdown conversion pipeline specifically engineered for high-accuracy **RAG (Retrieval-Augmented Generation)** applications. It doesn't just extract text; it preserves document hierarchy, optimizes segmentation, and enriches content with semantic metadata.

---

## 🚀 Why Doc-to-MD?

Standard PDF-to-text converters often fail RAG systems by creating cross-boundary context pollution. Doc-to-MD solves this by being **structure-aware**:

- 🏗️ **Hierarchical Preservation**: Uses the PDF's Table of Contents (TOC) to fix markdown heading levels.
- 🧩 **Semantic Segmentation**: Splits documents at logical section boundaries rather than arbitrary character limits.
- 🏷️ **Metadata Enrichment**: Injects section paths, content types, and semantic labels into every chunk.
- 🧹 **Intelligent Cleanup**: Strips PDF artifacts (footers, page numbers, dots leaders) and normalizes malformed lists/bullets.

---

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/boringbyte/doc-to-md.git
cd doc-to-md

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## 🛠️ Usage

### Programmatic API (Recommended)

Doc-to-MD provides a clean, class-based API for easy integration into your RAG pipelines.

```python
from doc_to_md import DocToMd

# Initialize with custom configuration
converter = DocToMd(
    chunk_size=2000,
    max_chunk_size=4000,
    output_format="markdown",
    include_frontmatter=True
)

# Convert a single PDF and save to file
output_path = converter.run("manual.pdf", "output.md")

# Or convert and get the rich ConversionResult object
result = converter.convert("document.pdf")
print(f"Extracted {len(result.chunks)} RAG-optimized chunks!")
```

### Command Line Interface

Process files directly from your terminal.

```bash
# Convert a single file
python -m doc_to_md.cli convert document.pdf -o output.md

# Convert with custom chunking
python -m doc_to_md.cli convert manual.pdf --chunk-size 1500 --format json

# Batch process an entire directory
python -m doc_to_md.cli batch input_pdfs/ -o converted_output/

# View PDF metadata and TOC structure
python -m doc_to_md.cli info document.pdf
```

---

## 🏗️ Architecture

The pipeline follows a structured extraction and enrichment flow:

1.  **Extraction**: Built on `pymupdf4llm` for high-quality raw data.
2.  **TOC Alignment**: Synchronizes markdown headings with the official document hierarchy.
3.  **Cleanup**: Removes redundant physical TOC pages, redundant headers, and normalize dots/bullets.
4.  **Segmentation**: Chunks content based on section boundaries to prevent semantic bleeding.
5.  **Enrichment**: Adds section paths (e.g., `Chapter 1 > Setup > Hardware`) to YAML frontmatter.

---

## 📄 Output Format

Each chunk is wrapped in YAML frontmatter, making it perfectly ready for vector database ingestion:

```markdown
---
section_path: ["Chapter 3", "Configuration", "Network Settings"]
section_level: 3
page_number: 142
content_type: prose
chunk_index: 45
word_count: 215
semantic_labels: ["configuration", "reference"]
---

## Network Settings
Configure the identity settings for multiple network interfaces...
```

---

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.
