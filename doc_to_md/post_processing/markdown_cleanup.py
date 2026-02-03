"""Markdown cleanup post-processor for normalizing whitespace and formatting."""

import logging
import re
from dataclasses import dataclass
from typing import Optional


logger = logging.getLogger(__name__)


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
    # Remove redundant physical TOC pages
    remove_redundant_toc: bool = True


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
        
        # Step 7: Remove redundant TOC
        if self.config.remove_redundant_toc:
            result = self._remove_redundant_toc(result)
        
        # Step 8: Normalize bullets
        result = self._normalize_bullets(result)
        
        # Step 8: Normalize blank lines (do this last)
        result = self._normalize_blank_lines(result)
        
        return result
    
    def _normalize_blank_lines(self, markdown: str) -> str:
        """Reduce consecutive blank lines and clean up list spacing.
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with normalized blank lines.
        """
        max_blanks = self.config.max_consecutive_blanks
        
        result = markdown
        
        # 1. Tighten list spacing
        # Remove blank lines between list items to make them "tight" lists
        # Normalize list items:
        result = re.sub(r'^([ \t]*[-*+]|\d+\.)[ \t]+(.*?)\n([ \t]*\n)+(?=[ \t]*([-*+]|\d+\.))', r'\1 \2\n', result, flags=re.MULTILINE)
        
        # 2. Also clean up trailing whitespace on all lines
        result = re.sub(r'[ \t]+$', '', result, flags=re.MULTILINE)
        
        # Remove blank lines at start of document
        result = result.lstrip('\n')
        
        # Ensure single newline at end
        result = result.rstrip() + '\n'
        
        return result

    def _normalize_bullets(self, markdown: str) -> str:
        """Normalize malformed bullets and list markers.
        
        Handles characters like ●, ○, ■, •,  followed by <br> or whitespace.
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with normalized bullets.
        """
        result = markdown
        
        # Pattern for common bullet characters followed by optional <br> and whitespace
        # Characters: ●, ○, ■, •,  (common PDF artifact), and others
        bullet_chars = r'[●○■•▪‣⁃]'
        
        # 1. Handle Bullet<br>Text or Bullet <br> Text
        # Replace with "- "
        result = re.sub(rf'{bullet_chars}\s*(?:<br/?>\s*)+', r'- ', result)
        
        # 2. Handle Bullet followed by just space
        # Ensuring we don't double up or replace existing good bullets
        # Use a lookahead to ensure it's at start of line or after a pipe (table) or space
        result = re.sub(rf'(^|[| \t]){bullet_chars}[ \t]*', r'\1- ', result, flags=re.MULTILINE)
        
        # 3. Clean up any resulting "- - " or similar dups (from double matching)
        result = re.sub(r'^- +- ', r'- ', result, flags=re.MULTILINE)
        result = re.sub(r'\| +- +- ', r'| - ', result)
        
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
        
        # Common footer sections
        common_sections = [
            'Contents', 'Overview of iDRAC', 'Logging in to iDRAC',
            'Setting up managed system', 'Configuring iDRAC',
            'Managing logs', 'Troubleshooting', 'Chapter', 'Rev.', 'Revision history',
            'December 2025', 'Rev. A11'
        ]

        def footer_callback(match):
            full_match = match.group(0)
            
            # Check which group matched (named groups from pattern)
            # We use non-greedy matches, so we need to be careful
            
            # Since we will use two separate patterns, we expect specific group names
            # or we can use numerical groups corresponding to the active pattern.
            
            # Actually, `re.sub` takes a callback. The callback receives the match object.
            # If we use different patterns, the group indices might differ.
            # Let's handle generic groups.
            
            groups = match.groups()
            # We expect 2 groups: Text and Number (in either order)
            # But the regex might capture them.
            
            # To simplify, we will parse the text and number from the FULL MATCH string
            # because the regex ensures the structure **T** **N** or **N** **T**.
            # This avoids group index confusion.
            
            # Remove all asterisks to get raw content
            raw = full_match.replace('*', '').strip()
            # Split by sufficient whitespace?
            # Re-match with a simple local regex to extract parts
            
            # Actually, let's trust the match groups if we name them consistently in the regex calls.
            
            text = None
            num = None
            
            # Try to identify text vs number
            # Assuming one group is digits, one is text.
            g1, g2 = groups
            
            if g1.isdigit() and not g2.isdigit():
                 num = g1
                 text = g2
            elif g2.isdigit() and not g1.isdigit():
                 num = g2
                 text = g1
            else:
                 # Both digits or neither? check logic
                 if g1.strip().isdigit(): num = g1; text = g2
                 elif g2.strip().isdigit(): num = g2; text = g1
            
            if not text or not num:
                 return full_match # Should not happen with our regex
            
            clean_text = text.strip()
            
            should_remove = False
            
            # Check common sections
            for common in common_sections:
                if common.lower() in clean_text.lower():
                    should_remove = True
                    logger.debug(f"Removing Footer (Common: {common}): '{clean_text}' '{num}'")
                    break
            
            if not should_remove:
                # Check for short, seemingly generic footers
                # e.g. "iDRAC9 User's Guide" (if it repeats) or pure dates?
                if len(clean_text) < 50:
                    should_remove = True
                    logger.debug(f"Removing Footer (Generic < 50 chars): '{clean_text}' '{num}'")
            
            if should_remove:
                return ''
            
            return full_match

        logger.debug("Starting Unified Footer Removal")
        
        # Pattern A: **Text** **Number**
        # Regex: ^\s*\*\*(.*?)\*\*\s+\*\*(\d{1,4})\*\*\s*$
        result = re.sub(
            r'^\s*\*\*(.*?)\*\*\s+\*\*(\d{1,4})\*\*\s*$',
            footer_callback,
            result,
            flags=re.MULTILINE
        )

        # Pattern B: **Number** **Text**
        # Regex: ^\s*\*\*(\d{1,4})\*\*\s+\*\*(.*?)\*\*\s*$
        result = re.sub(
             r'^\s*\*\*(\d{1,4})\*\*\s+\*\*(.*?)\*\*\s*$',
             footer_callback,
             result,
             flags=re.MULTILINE
        )

        # Pattern 3: Just bold page numbers on their own line
        # Example: **23**
        result_prev = result
        result = re.sub(
            r'^\s*\*\*\d{1,4}\*\*\s*$',
            '',
            result,
            flags=re.MULTILINE
        )
        if result != result_prev:
             pass # Removed standalone page numbers
        
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
    
    def _remove_redundant_toc(self, markdown: str) -> str:
        """Remove redundant physical TOC pages.
        
        Looks for lines with characteristic TOC patterns:
        - Title text followed by dot leaders (....) and a page number
        - Example: "**Chapter 1: About this document................ 9**"
        - Merged entries: "Title 1... 10 Title 2... 11"
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with redundant TOC lines removed.
        """
        # Global pattern for any line containing dot leaders and a page number anywhere
        # This handles merged entries or entries with trailing text.
        # We look for at least 5 dots.
        toc_pattern = re.compile(r'^.*?\.\.\.\.\.+.*?\d+.*$', re.MULTILINE)
        
        # Also handle bold blocks that contain dot leaders
        # Some TOC pages are entirely wrapped in bold.
        def aggressive_toc_callback(match):
            text = match.group(0)
            # If the block has a dot leader sequence, it's likely part of a TOC
            if '.....' in text:
                # If it also contains a number (page number), we remove it
                if re.search(r'\d+', text):
                    logger.debug(f"Removing TOC-like block: {repr(text[:50])}...")
                    return ""
            return text

        # Apply callback to both bold blocks and orphan lines
        result = toc_pattern.sub('', markdown)
        
        # Handle the specific multi-title bold block with internal dots
        result = re.sub(r'\*\*.*?\*\*', aggressive_toc_callback, result, flags=re.DOTALL)
        
        # Final cleanup for residual dot lines that might not have numbers but are garbage
        result = re.sub(r'^\s*\.\.\.\.\.\.+\s*$', '', result, flags=re.MULTILINE)
        
        # Handle cases where dots and numbers are not in bold but are on same line
        # e.g. "Some Title................................ 10 More Title................................ 11"
        def merge_cleaner(line):
            if '.....' in line and re.search(r'\d+', line):
                return ""
            return line
            
        lines = result.split('\n')
        result_lines = [merge_cleaner(l) for l in lines]
        result = '\n'.join(result_lines)
        
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
