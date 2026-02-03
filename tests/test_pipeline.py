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
    assert output_file.read_text(encoding='utf-8') == "Processed content"
