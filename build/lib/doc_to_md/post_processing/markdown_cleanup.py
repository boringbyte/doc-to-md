"""Markdown cleanup post-processor for normalizing whitespace and formatting."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class CleanupConfig:
    """Configuration for markdown cleanup."""
    # Maximum consecutive blank lines allowed
    max_consecutive_blanks: int = 1
    # Remove page number footers (e.g., "**Contents** **5**")
    remove_page_footers: bool = True
    # Remove orphan page numbers (e.g., standalone "**23**")
    remove_orphan_page_numbers: bool = True
    # Normalize horizontal rules
    normalize_hr: bool = True
    # Fix broken sentences across lines
    fix_broken_sentences: bool = True
    # Remove excessive bold formatting
    cleanup_bold: bool = True
    # Trim trailing whitespace
    trim_trailing_whitespace: bool = True


class MarkdownCleanup:
    """Cleans up and normalizes markdown formatting.
    
    Handles:
    - Excessive blank lines
    - Page number artifacts from PDF
    - Trailing whitespace
    - Broken sentences
    - Orphaned formatting
    """
    
    def __init__(self, config: Optional[CleanupConfig] = None):
        """Initialize the cleanup processor.
        
        Args:
            config: Cleanup configuration options.
        """
        self.config = config or CleanupConfig()
    
    def clean(self, markdown: str) -> str:
        """Run all cleanup steps on markdown content.
        
        Args:
            markdown: The markdown content to clean.
            
        Returns:
            Cleaned markdown content.
        """
        result = markdown
        
        # Step 1: Remove page footers (e.g., "**Contents** **5**")
        if self.config.remove_page_footers:
            result = self._remove_page_footers(result)
        
        # Step 2: Remove orphan page numbers
        if self.config.remove_orphan_page_numbers:
            result = self._remove_orphan_page_numbers(result)
        
        # Step 3: Fix broken sentences
        if self.config.fix_broken_sentences:
            result = self._fix_broken_sentences(result)
        
        # Step 4: Clean up excessive bold
        if self.config.cleanup_bold:
            result = self._cleanup_bold(result)
        
        # Step 5: Normalize horizontal rules
        if self.config.normalize_hr:
            result = self._normalize_hr(result)
        
        # Step 6: Trim trailing whitespace
        if self.config.trim_trailing_whitespace:
            result = self._trim_trailing_whitespace(result)
        
        # Step 7: Normalize blank lines (do this last)
        result = self._normalize_blank_lines(result)
        
        return result
    
    def _normalize_blank_lines(self, markdown: str) -> str:
        """Reduce consecutive blank lines to configured maximum.
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with normalized blank lines.
        """
        max_blanks = self.config.max_consecutive_blanks
        
        # Replace 3+ newlines with 2 (one blank line)
        # \n\n = one blank line, \n\n\n = two blank lines, etc.
        pattern = r'\n{' + str(max_blanks + 2) + r',}'
        replacement = '\n' * (max_blanks + 1)
        
        result = re.sub(pattern, replacement, markdown)
        
        # Also handle lines with only whitespace
        result = re.sub(r'\n[ \t]+\n', '\n\n', result)
        
        # Remove blank lines at start of document
        result = result.lstrip('\n')
        
        # Ensure single newline at end
        result = result.rstrip() + '\n'
        
        return result
    
    def _remove_page_footers(self, markdown: str) -> str:
        """Remove page number footers from PDF conversion.
        
        Matches patterns like:
        - "**Contents** **5**"
        - "**Overview of iDRAC** **23**"
        - "**12** **Contents**"
        - "**24** **Overview of iDRAC**"
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with page footers removed.
        """
        result = markdown
        
        # Normalize line endings first to simplify regex
        result = result.replace('\r\n', '\n').replace('\r', '\n')
        
        # Pattern 1: **Title/Section** **PageNum** on its own line
        # Example: **Contents** **5**
        result = re.sub(
            r'^\s*\*\*[^*\n]+?\*\*\s+\*\*\d{1,4}\*\*\s*$',
            '',
            result,
            flags=re.MULTILINE
        )
        
        # Pattern 2: **PageNum** **Title/Section** on its own line
        # Example: **24** **Overview of iDRAC**
        result = re.sub(
            r'^\s*\*\*\d{1,4}\*\*\s+\*\*[^*\n]+?\*\*\s*$',
            '',
            result,
            flags=re.MULTILINE
        )
        
        # Pattern 3: Just bold page numbers on their own line
        # Example: **23**
        result = re.sub(
            r'^\s*\*\*\d{1,4}\*\*\s*$',
            '',
            result,
            flags=re.MULTILINE
        )
        
        # Pattern 4: Common footer patterns (both orders)
        # This catches headers/footers with common section names
        common_sections = [
            'Contents', 'Overview of iDRAC', 'Logging in to iDRAC',
            'Setting up managed system', 'Configuring iDRAC',
            'Managing logs', 'Troubleshooting'
        ]
        for section in common_sections:
            # Section name then number
            pattern = rf'^\s*\*\*{re.escape(section)}\*\*\s+\*\*\d{{1,4}}\*\*\s*$'
            result = re.sub(pattern, '', result, flags=re.MULTILINE | re.IGNORECASE)
            # Number then section name
            pattern = rf'^\s*\*\*\d{{1,4}}\*\*\s+\*\*{re.escape(section)}\*\*\s*$'
            result = re.sub(pattern, '', result, flags=re.MULTILINE | re.IGNORECASE)
        
        return result
    
    def _remove_orphan_page_numbers(self, markdown: str) -> str:
        """Remove standalone page numbers that aren't part of content.
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with orphan page numbers removed.
        """
        # Remove lines that are just a number (page number)
        result = re.sub(r'^\d{1,4}\s*$', '', markdown, flags=re.MULTILINE)
        
        return result
    
    def _fix_broken_sentences(self, markdown: str) -> str:
        """Fix sentences broken across lines by PDF extraction.
        
        Joins lines where a sentence continues but was split by PDF layout.
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with fixed sentences.
        """
        lines = markdown.split('\n')
        result_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Skip empty lines, headings, list items, tables, code blocks
            if (not line.strip() or 
                line.strip().startswith('#') or
                line.strip().startswith('-') or
                line.strip().startswith('*') and not line.strip().startswith('**') or
                line.strip().startswith('|') or
                line.strip().startswith('```') or
                line.strip().startswith('>')):
                result_lines.append(line)
                i += 1
                continue
            
            # Check if line ends mid-sentence (no terminal punctuation)
            # and next line continues the sentence
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                
                # Skip if next line is empty or special
                if (next_line and 
                    not next_line.startswith('#') and
                    not next_line.startswith('-') and
                    not next_line.startswith('|') and
                    not next_line.startswith('```') and
                    not next_line.startswith('>')):
                    
                    # If current line ends with hyphen (word break), join
                    if line.rstrip().endswith('-') and next_line[0].islower():
                        # Remove hyphen and join
                        line = line.rstrip()[:-1] + next_line
                        lines[i + 1] = ''  # Clear the joined line
            
            result_lines.append(line)
            i += 1
        
        return '\n'.join(result_lines)
    
    def _cleanup_bold(self, markdown: str) -> str:
        """Clean up excessive or malformed bold formatting.
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with cleaned bold formatting.
        """
        # Remove bold from entire lines that are just bold
        # (often page headers/footers)
        result = markdown
        
        # Fix double-bolded text: ****text**** -> **text**  
        result = re.sub(r'\*{4,}([^*]+)\*{4,}', r'**\1**', result)
        
        # Remove bold from very short standalone bold text that looks like artifacts
        # But be careful not to remove legitimate bold text
        
        return result
    
    def _normalize_hr(self, markdown: str) -> str:
        """Normalize horizontal rules to consistent format.
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with normalized horizontal rules.
        """
        # Normalize various HR formats to ---
        result = re.sub(r'^[\-_\*]{3,}\s*$', '---', markdown, flags=re.MULTILINE)
        return result
    
    def _trim_trailing_whitespace(self, markdown: str) -> str:
        """Remove trailing whitespace from each line.
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with trimmed lines.
        """
        lines = markdown.split('\n')
        trimmed = [line.rstrip() for line in lines]
        return '\n'.join(trimmed)
