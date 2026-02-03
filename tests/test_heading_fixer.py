import pytest
from doc_to_md.post_processing.heading_fixer import HeadingFixer, HeadingFixerConfig
from doc_to_md.processing.models import TOCItem

def test_heading_normalization():
    toc = [
        TOCItem(level=1, title="Introduction", page_number=1),
        TOCItem(level=2, title="Background", page_number=2),
    ]
    fixer = HeadingFixer(toc, HeadingFixerConfig(bold_non_toc_headings=True))
    
    # Test matching heading
    assert fixer.fix_headings("## Introduction").strip() == "# Introduction"
    
    # Test non-matching heading (should be bolded)
    assert fixer.fix_headings("## Figure 1: Test").strip() == "**Figure 1: Test**"

def test_strict_prefix_matching():
    toc = [
        TOCItem(level=1, title="Installing the air shroud", page_number=44),
    ]
    # Configure with non-TOC bolding enabled
    fixer = HeadingFixer(toc, HeadingFixerConfig(bold_non_toc_headings=True))
    
    # "Figure 44. Installing the air shroud" should NOT match "Installing the air shroud"
    # and should be converted to bold.
    input_text = "### Figure 44. Installing the air shroud"
    result = fixer.fix_headings(input_text).strip()
    assert result == "**Figure 44. Installing the air shroud**"
    
    # Valid match should still work
    assert fixer.fix_headings("### Installing the air shroud").strip() == "# Installing the air shroud"

def test_heading_level_fix():
    toc = [
        TOCItem(level=3, title="Deep Section", page_number=10),
    ]
    fixer = HeadingFixer(toc, HeadingFixerConfig())
    
    # Should move from ## to ### based on TOC level
    assert fixer.fix_headings("## Deep Section").strip() == "### Deep Section"
