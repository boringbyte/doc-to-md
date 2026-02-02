
from doc_to_md.post_processing.heading_fixer import HeadingFixer, HeadingFixerConfig
from doc_to_md.processing.models import TOCItem
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)

def test_heading_fixer():
    # Mock TOC
    toc = [
        TOCItem(level=1, title='Overview of iDRAC', page_number=17),
        TOCItem(level=2, title='Contents', page_number=4)
    ]
    
    # Mock Markdown
    markdown = """
**Contents** **5**
### **Overview of iDRAC**
Some content...
**Overview of iDRAC**
Some other content...
"""
    
    config = HeadingFixerConfig(remove_bold_from_headings=True)
    fixer = HeadingFixer(toc, config)
    
    print("Original Markdown:")
    print(markdown)
    
    fixed_markdown = fixer.fix_headings(markdown)
    
    print("\nFixed Markdown:")
    print(fixed_markdown)
    
    # helper to check
    if "# Overview of iDRAC" in fixed_markdown:
        print("\nSUCCESS: Heading fixed to Level 1")
    else:
        print("\nFAILURE: Heading NOT fixed")
        
    if "# Contents" in fixed_markdown or "## Contents" in fixed_markdown:
        print("Contents heading check skipped (ambiguous in mock)")

    # Check the bold promotion logic I added
    if "# Overview of iDRAC" in fixed_markdown and "**Overview of iDRAC**" not in fixed_markdown.split('\n')[3]:
         print("SUCCESS: Bold text promoted to heading")

if __name__ == "__main__":
    test_heading_fixer()
