"""Link and reference fixer for markdown content."""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass
class LinkFixerConfig:
    """Configuration for link fixing."""
    # Fix broken URLs split across lines
    fix_broken_urls: bool = True
    # Normalize URL case for hostnames
    normalize_url_case: bool = True
    # Remove tracking parameters from URLs
    remove_tracking_params: bool = False
    # Convert relative URLs to absolute (requires base_url)
    base_url: Optional[str] = None


class LinkFixer:
    """Fixes and normalizes links in markdown.
    
    Common PDF conversion issues with links:
    - URLs split across lines
    - Uppercase hostnames
    - Broken markdown link syntax
    - Missing protocols
    """
    
    def __init__(self, config: Optional[LinkFixerConfig] = None):
        """Initialize the link fixer.
        
        Args:
            config: Configuration options.
        """
        self.config = config or LinkFixerConfig()
    
    def fix_links(self, markdown: str) -> str:
        """Fix all link issues in markdown.
        
        Args:
            markdown: The markdown content.
            
        Returns:
            Markdown with fixed links.
        """
        result = markdown
        
        if self.config.fix_broken_urls:
            result = self._fix_broken_urls(result)
        
        if self.config.normalize_url_case:
            result = self._normalize_url_case(result)
        
        result = self._fix_markdown_links(result)
        
        return result
    
    def _fix_broken_urls(self, markdown: str) -> str:
        """Fix URLs that were split across lines.
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with joined URLs.
        """
        # Pattern: URL at end of line followed by continuation
        # [text](http://example.
        # com/path)
        
        lines = markdown.split('\n')
        result_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # Check for broken markdown link
            if i + 1 < len(lines):
                # Pattern: ends with partial URL in link
                if re.search(r'\[[^\]]+\]\([^)]+$', line):
                    next_line = lines[i + 1].strip()
                    # Next line continues the URL
                    if re.match(r'^[a-zA-Z0-9/\-_.?=&%#]+\)', next_line):
                        line = line + next_line
                        i += 1
            
            result_lines.append(line)
            i += 1
        
        return '\n'.join(result_lines)
    
    def _normalize_url_case(self, markdown: str) -> str:
        """Normalize URL hostnames to lowercase.
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with normalized URLs.
        """
        def normalize_url(match):
            url = match.group(1)
            try:
                parsed = urlparse(url)
                if parsed.netloc:
                    # Lowercase the hostname only
                    normalized = url.replace(
                        parsed.netloc,
                        parsed.netloc.lower(),
                        1
                    )
                    return f']({normalized})'
            except Exception:
                pass
            return match.group(0)
        
        # Find markdown links and normalize
        result = re.sub(r'\]\((https?://[^)]+)\)', normalize_url, markdown)
        
        return result
    
    def _fix_markdown_links(self, markdown: str) -> str:
        """Fix common markdown link syntax issues.
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with fixed link syntax.
        """
        result = markdown
        
        # Fix spaces in link syntax: [ text ](url) -> [text](url)
        result = re.sub(r'\[\s+([^\]]+?)\s+\]', r'[\1]', result)
        
        # Fix double brackets: [[text]](url) -> [text](url)
        result = re.sub(r'\[\[([^\]]+)\]\](\([^)]+\))', r'[\1]\2', result)
        
        # Fix missing closing bracket: [text(url) -> [text](url)
        # Only if it looks like a valid URL
        result = re.sub(
            r'\[([^\]]+)\(https?://([^)]+)\)',
            r'[\1](https://\2)',
            result
        )
        
        return result
