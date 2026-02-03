import pytest
from doc_to_md.post_processing.markdown_cleanup import MarkdownCleanup, CleanupConfig
from doc_to_md.post_processing.whitespace_normalizer import WhitespaceNormalizer, WhitespaceConfig

def test_dot_leader_removal():
    cleanup = MarkdownCleanup(CleanupConfig(remove_redundant_toc=True))
    
    # Test simple dot leader
    input_text = "Chapter 1: Introduction................ 1"
    assert cleanup.clean(input_text).strip() == ""
    
    # Test bold dot leader
    input_text = "**Chapter 2: Setup................ 5**"
    assert cleanup.clean(input_text).strip() == ""
    
    # Test merged entries
    input_text = "Title 1..... 10 Title 2..... 11"
    assert cleanup.clean(input_text).strip() == ""
    
    # Test complex bold block with dots
    input_text = "**Chapter 3: More Info................ 15 Chapter 4: Even More................ 16**"
    assert cleanup.clean(input_text).strip() == ""
    
    # Test 5 dots (minimum)
    input_text = "Title 5..... 50"
    assert cleanup.clean(input_text).strip() == ""
    
    # Test that normal text with 4 dots is NOT removed (threshold is 5)
    input_text = "This is a normal sentence with some dots.... but not a TOC."
    assert cleanup.clean(input_text).strip() == input_text

def test_footer_removal():
    cleanup = MarkdownCleanup(CleanupConfig(remove_page_footers=True))
    
    # Test bold footer pattern (Text then Number)
    input_text = "Something helpful\n**Contents** **45**"
    result = cleanup.clean(input_text)
    assert "**Contents** **45**" not in result
    
    # Test bold footer pattern (Number then Text)
    input_text = "**45** **Contents**\nSomething else"
    result = cleanup.clean(input_text)
    assert "**45** **Contents**" not in result
    
    # Test standalone bold page number
    input_text = "Some text\n**45**\nMore text"
    result = cleanup.clean(input_text)
    assert "**45**" not in result.split('\n')

def test_bullet_normalization():
    cleanup = MarkdownCleanup(CleanupConfig()) # Bullet normalization is on by default in clean() if implemented
    
    # Test common malformed bullets
    assert cleanup.clean("●<br> Item 1").strip() == "- Item 1"
    assert cleanup.clean("○<br> Item 2").strip() == "- Item 2"
    assert cleanup.clean("■<br> Item 3").strip() == "- Item 3"
    assert cleanup.clean("•<br> Item 4").strip() == "- Item 4"

def test_whitespace_normalization():
    normalizer = WhitespaceNormalizer(WhitespaceConfig())
    
    # Test collapsing 3+ newlines to 2
    input_text = "Line 1\n\n\nLine 2"
    assert normalizer.normalize(input_text).strip() == "Line 1\n\nLine 2"
    
    input_text = "Line 1\n\n\n\n\nLine 2"
    assert normalizer.normalize(input_text).strip() == "Line 1\n\nLine 2"
    
    # Test preserving 2 newlines
    input_text = "Line 1\n\nLine 2"
    assert normalizer.normalize(input_text).strip() == "Line 1\n\nLine 2"
