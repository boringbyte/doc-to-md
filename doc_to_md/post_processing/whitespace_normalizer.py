"""Whitespace normalization post-processor for collapsing excessive newlines."""

import logging
import re
from dataclasses import dataclass
from typing import Optional


logger = logging.getLogger(__name__)


@dataclass
class WhitespaceConfig:
    """Configuration for whitespace normalization."""
    # Maximum consecutive blank lines allowed
    max_consecutive_blanks: int = 1


class WhitespaceNormalizer:
    """Collapses excessive newlines in markdown content."""
    
    def __init__(self, config: Optional[WhitespaceConfig] = None):
        """Initialize the normalizer.
        
        Args:
            config: Whitespace configuration options.
        """
        self.config = config or WhitespaceConfig()
        
    def normalize(self, markdown: str) -> str:
        """Collapse 3+ newlines into 2 (one blank line).
        
        Args:
            markdown: Input markdown content.
            
        Returns:
            Markdown with normalized whitespace.
        """
        if not markdown:
            return ""
            
        result = markdown
        
        # Replace 3+ newlines with 2 newlines
        # This collapses any sequence of 3 or more \n characters (possibly with whitespace between them)
        # into exactly two \n characters.
        result = re.sub(r'\n([ \t]*\n){2,}', '\n\n', result)
        
        # Ensure single newline at end
        result = result.rstrip() + '\n'
        
        return result
