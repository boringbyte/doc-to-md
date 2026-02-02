"""Heading fixer that uses TOC to correct heading levels in markdown."""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

from ..processing.models import TOCItem


@dataclass 
class HeadingFixerConfig:
    """Configuration for heading level correction."""
    # Minimum similarity ratio for TOC matching (0-1)
    min_match_ratio: float = 0.8
    # Whether to remove bold from headings
    remove_bold_from_headings: bool = True
    # Whether to add missing headings from TOC
    add_missing_headings: bool = False


class HeadingFixer:
    """Fixes markdown heading levels based on PDF Table of Contents.
    
    The PDF converter often assigns incorrect heading levels because
    it infers them from font sizes. The TOC provides the true hierarchy.
    
    Features:
    - Maps markdown headings to TOC entries
    - Corrects heading levels based on TOC
    - Removes bold formatting from headings
    - Handles fuzzy matching for slight text variations
    """
    
    def __init__(
        self,
        toc: list[TOCItem],
        config: Optional[HeadingFixerConfig] = None
    ):
        """Initialize the heading fixer.
        
        Args:
            toc: List of TOC items from PDF extraction.
            config: Configuration options.
        """
        self.toc = toc
        self.config = config or HeadingFixerConfig()
        self._toc_map = self._build_toc_map()
    
    def _build_toc_map(self) -> dict[str, int]:
        """Build a map of normalized TOC titles to their levels.
        
        Returns:
            Dict mapping normalized title -> level.
        """
        toc_map = {}
        for item in self.toc:
            normalized = self._normalize_title(item.title)
            toc_map[normalized] = item.level
        return toc_map
    
    def _normalize_title(self, title: str) -> str:
        """Normalize a title for matching.
        
        Args:
            title: The title to normalize.
            
        Returns:
            Normalized title string.
        """
        # Remove bold markers
        title = re.sub(r'\*+', '', title)
        # Remove extra whitespace
        title = ' '.join(title.split())
        # Convert to lowercase for matching
        title = title.lower().strip()
        return title
    
    def _find_toc_level(self, heading_text: str) -> Optional[int]:
        """Find the TOC level for a heading.
        
        Args:
            heading_text: The heading text to look up.
            
        Returns:
            The TOC level (1-6) or None if not found.
        """
        normalized = self._normalize_title(heading_text)
        
        # Exact match first
        if normalized in self._toc_map:
            return self._toc_map[normalized]
        
        # Fuzzy match for slight variations
        best_match = None
        best_ratio = 0
        
        for toc_title, level in self._toc_map.items():
            ratio = SequenceMatcher(None, normalized, toc_title).ratio()
            if ratio > best_ratio and ratio >= self.config.min_match_ratio:
                best_ratio = ratio
                best_match = level
        
        return best_match
    
    def fix_headings(self, markdown: str) -> str:
        """Fix heading levels in markdown based on TOC.
        
        Args:
            markdown: The markdown content.
            
        Returns:
            Markdown with corrected heading levels.
        """
        lines = markdown.split('\n')
        result_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            # Check if this is a heading
            heading_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            # Check if this is a bold line that might be a heading
            bold_match = re.match(r'^\s*\*\*([^*]+)\*\*\s*$', line)
            
            clean_text = ""
            current_hashes = ""
            is_modified = False
            
            if heading_match:
                current_hashes = heading_match.group(1)
                heading_text = heading_match.group(2)
                clean_text = heading_text
                
                # Clean up the heading text
                if self.config.remove_bold_from_headings:
                    clean_text = re.sub(r'\*+([^*]+)\*+', r'\1', clean_text)
                    clean_text = clean_text.strip()
                
                # Look up the correct level in TOC
                toc_level = self._find_toc_level(heading_text)
                
                if toc_level is not None:
                    # Use TOC level
                    new_hashes = '#' * toc_level
                    line = f"{new_hashes} {clean_text}"
                    is_modified = True
                elif self.config.remove_bold_from_headings:
                    # Keep original level but clean text
                    line = f"{current_hashes} {clean_text}"
            
            elif bold_match:
                # Potential heading disguised as bold text
                text = bold_match.group(1).strip()
                toc_level = self._find_toc_level(text)
                
                if toc_level is not None:
                    # Promote bold text to heading
                    new_hashes = '#' * toc_level
                    line = f"{new_hashes} {text}"
            
            result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    def get_heading_statistics(self, markdown: str) -> dict:
        """Analyze headings in the markdown and compare to TOC.
        
        Args:
            markdown: The markdown content.
            
        Returns:
            Dict with statistics about heading matches.
        """
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        
        stats = {
            "total_headings": 0,
            "matched_to_toc": 0,
            "level_corrections": 0,
            "unmatched": []
        }
        
        for match in heading_pattern.finditer(markdown):
            stats["total_headings"] += 1
            current_level = len(match.group(1))
            heading_text = match.group(2)
            
            toc_level = self._find_toc_level(heading_text)
            
            if toc_level is not None:
                stats["matched_to_toc"] += 1
                if toc_level != current_level:
                    stats["level_corrections"] += 1
            else:
                # Only track first 10 unmatched
                if len(stats["unmatched"]) < 10:
                    stats["unmatched"].append(heading_text[:50])
        
        return stats


def create_heading_hierarchy(toc: list[TOCItem]) -> dict:
    """Create a hierarchical structure from flat TOC.
    
    Args:
        toc: Flat list of TOC items.
        
    Returns:
        Nested dict representing the TOC hierarchy.
    """
    root = {"children": [], "level": 0, "title": "root"}
    stack = [root]
    
    for item in toc:
        node = {
            "title": item.title,
            "level": item.level,
            "page": item.page_number,
            "children": []
        }
        
        # Pop stack until we find parent
        while stack and stack[-1]["level"] >= item.level:
            stack.pop()
        
        # Add as child of current top
        if stack:
            stack[-1]["children"].append(node)
        
        stack.append(node)
    
    return root
