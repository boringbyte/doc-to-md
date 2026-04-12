import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from doc_to_md.pipeline import DocToMd, PipelineConfig
from doc_to_md.processing.models import ConversionResult, DocumentMetadata, TOCItem

def test_doctomd_initialization():
    # Test direct config
    pipe = DocToMd(chunk_size=3000, output_format="json")
    assert pipe.config.segmenter_config.target_chunk_size == 3000
    assert pipe.config.output_format == "json"
    
    # Test object config
    config = PipelineConfig(run_cleanup=False)
    pipe = DocToMd(config=config)
    assert pipe.config.run_cleanup is False

@patch("doc_to_md.pipeline.PyMuPDFConverter")
def test_pipeline_flow(mock_converter_class):
    # Setup mock converter
    mock_converter = MagicMock()
    mock_converter_class.return_value = mock_converter
    
    # Mock conversion result
    mock_result = ConversionResult(
        markdown="# Test\nContent with dots..... 1",
        toc=[TOCItem(level=1, title="Test", page_number=1)],
        metadata=DocumentMetadata(title="Test Doc")
    )
    mock_converter.convert.return_value = mock_result
    
    # Run pipeline
    pipe = DocToMd(segment_content=False) # Disable segmentation for simple test
    result = pipe.convert("dummy.pdf")
    
    # Verify stages were called (implicitly via cleanup and heading fixer logic)
    # The output should have the dot leader removed and heading possibly fixed
    assert "# Test" in result.markdown
    assert "dots....." not in result.markdown
    assert "# Test" in result.markdown

@patch("doc_to_md.pipeline.DocToMd.convert")
def test_run_method(mock_convert, tmp_path):
    # Setup mock result
    mock_result = MagicMock()
    mock_result.markdown = "Processed content"
    mock_result.chunks = []
    mock_result.metadata = DocumentMetadata()
    mock_convert.return_value = mock_result
    
    output_file = tmp_path / "output.md"
    
    pipe = DocToMd()
    pipe.run("input.pdf", output_file)
    
    # Verify file was written
    assert output_file.exists()
    # By default, should have NO frontmatter
    content = output_file.read_text(encoding='utf-8')
    assert "---" not in content
    assert "Processed content" in content

@patch("doc_to_md.pipeline.DocToMd.convert")
def test_run_multiple_formats(mock_convert, tmp_path):
    # Setup mock result with real object
    mock_result = ConversionResult(
        markdown="Processed content",
        chunks=[],
        metadata=DocumentMetadata()
    )
    mock_convert.return_value = mock_result
    
    input_file = tmp_path / "input.pdf"
    
    pipe = DocToMd()
    # Test as list
    results = pipe.run(input_file, output_format=["markdown", "json"])
    
    assert isinstance(results, list)
    assert len(results) == 2
    assert (tmp_path / "input.md").exists()
    assert (tmp_path / "input.json").exists()
    
    # Test as comma-separated string
    results_str = pipe.run(input_file, output_format="markdown,json")
    assert isinstance(results_str, list)
    assert len(results_str) == 2


def test_metadata_keywords_handling():
    # Test dictionary conversion in models.py
    meta = DocumentMetadata(keywords="rag, pdf, markdown")
    d = meta.to_dict()
    assert d["keywords"] == ["rag", "pdf", "markdown"]
    
    # Test None handling
    meta_none = DocumentMetadata(keywords=None)
    assert meta_none.to_dict()["keywords"] == []
    
    # Test frontmatter generation in metadata_enricher.py
    from doc_to_md.post_processing.metadata_enricher import generate_markdown_output
    from doc_to_md.processing.models import Chunk, ContentType
    
    chunk = Chunk(
        content="Test",
        section_path=["A"],
        section_level=1,
        page_start=1,
        page_end=1,
        page_range="1",
        parent_section=None,
        content_type=ContentType.PROSE
    )
    # Test default: No chunk-level metadata AND no doc-level frontmatter
    output = generate_markdown_output([chunk], document_metadata=meta, include_frontmatter=False)
    
    assert 'keywords: "rag, pdf, markdown"' not in output
    assert 'page_start: 1' not in output
    assert '---' not in output
    
    # Test explicitly enabled
    output_enriched = generate_markdown_output(
        [chunk], 
        document_metadata=meta, 
        include_frontmatter=True,
        include_chunk_metadata=True
    )
    assert 'keywords: "rag, pdf, markdown"' in output_enriched
    assert 'page_start: 1' in output_enriched
    assert output_enriched.startswith("---")


@patch("doc_to_md.pipeline.DocToMd.convert")
def test_run_with_directory_output(mock_convert, tmp_path):
    """Test that run() correctly handles a directory as output_path."""
    mock_result = ConversionResult(
        markdown="Processed content",
        chunks=[],
        metadata=DocumentMetadata()
    )
    mock_convert.return_value = mock_result
    
    input_file = tmp_path / "my_document.pdf"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    pipe = DocToMd()
    result = pipe.run(input_file, output_dir)
    
    # Should create file named after input inside the output directory
    assert result == output_dir / "my_document.md"
    assert result.exists()
    assert "Processed content" in result.read_text(encoding='utf-8')


@patch("doc_to_md.pipeline.DocToMd.convert")
def test_convert_directory_with_limit(mock_convert, tmp_path):
    """Test convert_directory respects the limit parameter."""
    mock_result = ConversionResult(
        markdown="Content",
        chunks=[],
        metadata=DocumentMetadata()
    )
    mock_convert.return_value = mock_result
    
    # Create 5 dummy PDF files
    for i in range(5):
        (tmp_path / f"doc{i}.pdf").write_bytes(b"dummy")
    
    output_dir = tmp_path / "output"
    pipe = DocToMd()
    
    # Process only 2
    results = pipe.convert_directory(tmp_path, output_dir=output_dir, limit=2)
    assert len(results) == 2
    
    # Process all
    # Since doc0 and doc1 already exist, they will be skipped if overwrite=False (default)
    # So we set overwrite=True to get all 5 again, or just expect 5 if we want to bypass skip
    results_all = pipe.convert_directory(tmp_path, output_dir=output_dir, overwrite=True)
    assert len(results_all) == 5


@patch("doc_to_md.pipeline.DocToMd.convert")
def test_convert_directory_with_output_format(mock_convert, tmp_path):
    """Test convert_directory with output_format override."""
    mock_result = ConversionResult(
        markdown="Content",
        chunks=[],
        metadata=DocumentMetadata()
    )
    mock_convert.return_value = mock_result
    
    (tmp_path / "test.pdf").write_bytes(b"dummy")
    output_dir = tmp_path / "output"
    
    pipe = DocToMd()
    results = pipe.convert_directory(
        tmp_path, output_dir=output_dir, output_format="json", limit=1
    )
    
    assert len(results) == 1
    assert results[0].suffix == ".json"
    assert results[0].exists()


@patch("doc_to_md.pipeline.DocToMd._convert_directory_parallel")
def test_convert_directory_with_workers(mock_parallel, tmp_path):
    """Test convert_directory with workers > 1 dispatches to parallel method."""
    mock_parallel.return_value = [tmp_path / "doc0.md", tmp_path / "doc1.md"]
    
    # Create 3 dummy PDF files
    for i in range(3):
        (tmp_path / f"doc{i}.pdf").write_bytes(b"dummy")
    
    output_dir = tmp_path / "output"
    pipe = DocToMd()
    
    # workers > 1 should call _convert_directory_parallel
    # We set overwrite=True to ensure it doesn't skip if run multiple times (though here it's first run)
    results = pipe.convert_directory(tmp_path, output_dir=output_dir, workers=2, overwrite=True)
    assert mock_parallel.called
    assert len(results) == 2  # returns what mock returned
    
    # Verify it was called with the right args
    call_args = mock_parallel.call_args
    assert len(call_args[0][0]) == 3  # 3 pdf files
    assert call_args[0][1] == output_dir  # output_dir
    assert call_args[0][3] == 2  # num_workers


@patch("doc_to_md.pipeline.DocToMd.run")
def test_convert_directory_skip_existing(mock_run, tmp_path):
    """Test convert_directory skips files that already exist when overwrite=False."""
    # Create input and output dirs
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    # Create 2 input PDF files
    (input_dir / "doc1.pdf").write_bytes(b"pdf1")
    (input_dir / "doc2.pdf").write_bytes(b"pdf2")
    
    # Pretend doc1.md already exists in output
    (output_dir / "doc1.md").write_text("existing")
    
    pipe = DocToMd(overwrite=False)
    
    # Run conversion
    # Only doc2.pdf should be processed because doc1.md exists
    mock_run.side_effect = lambda path, out, output_format=None: out / (path.stem + ".md")
    
    results = pipe.convert_directory(input_dir, output_dir=output_dir)
    
    assert len(results) == 1
    assert "doc2" in str(results[0])
    assert mock_run.call_count == 1
    
    # Verify doc1 was skipped
    processed_files = [args[0].name for args, _ in mock_run.call_args_list]
    assert "doc1.pdf" not in processed_files
    assert "doc2.pdf" in processed_files
    
    # Now try with overwrite=True
    mock_run.reset_mock()
    mock_run.side_effect = lambda path, out, output_format=None: out / (path.stem + ".md")
    results = pipe.convert_directory(input_dir, output_dir=output_dir, overwrite=True)
    assert len(results) == 2
    assert mock_run.call_count == 2


