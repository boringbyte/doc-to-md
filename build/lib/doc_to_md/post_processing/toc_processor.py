"""TOC processor for extracting and enriching document structure."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..processing.models import TOCItem, Section


@dataclass
class TOCNode:
    """A node in the hierarchical TOC tree."""
    item: TOCItem
    parent: Optional["TOCNode"] = None
    children: list["TOCNode"] = None
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
    
    @property
    def path(self) -> list[str]:
        """Get the full path from root to this node."""
        if self.parent is None:
            return []
        return self.parent.path + [self.parent.item.title]


class TOCProcessor:
    """Processes and enriches Table of Contents data.
    
    Builds hierarchical structure from flat TOC items and maps
    content to sections based on page ranges.
    """
    
    def __init__(self, toc_items: list[TOCItem]):
        """Initialize with TOC items.
        
        Args:
            toc_items: Flat list of TOC items from PDF extraction.
        """
        self.toc_items = toc_items
        self.root_nodes: list[TOCNode] = []
        self._build_tree()
    
    def _build_tree(self) -> None:
        """Build hierarchical tree from flat TOC list."""
        if not self.toc_items:
            return
        
        # Stack to track parent at each level
        stack: list[TOCNode] = []
        
        for item in self.toc_items:
            node = TOCNode(item=item)
            
            # Pop stack until we find the parent level
            while stack and stack[-1].item.level >= item.level:
                stack.pop()
            
            if stack:
                # This is a child of the top of stack
                node.parent = stack[-1]
                stack[-1].children.append(node)
            else:
                # This is a root node
                self.root_nodes.append(node)
            
            stack.append(node)
    
    def get_section_at_page(self, page_number: int) -> Optional[TOCNode]:
        """Find the deepest section containing a page number.
        
        Args:
            page_number: The page number to look up.
            
        Returns:
            The most specific TOCNode containing this page, or None.
        """
        def find_in_nodes(nodes: list[TOCNode], page: int) -> Optional[TOCNode]:
            result = None
            for i, node in enumerate(nodes):
                if node.item.page_number <= page:
                    # Check if next sibling starts after this page
                    if i + 1 < len(nodes) and nodes[i + 1].item.page_number <= page:
                        continue
                    result = node
                    # Check children for more specific match
                    child_result = find_in_nodes(node.children, page)
                    if child_result:
                        result = child_result
                    break
            return result
        
        return find_in_nodes(self.root_nodes, page_number)
    
    def get_section_path(self, page_number: int) -> list[str]:
        """Get the full section path for a page.
        
        Args:
            page_number: The page number to look up.
            
        Returns:
            List of section titles from root to deepest level.
        """
        node = self.get_section_at_page(page_number)
        if not node:
            return []
        return node.path + [node.item.title]
    
    def get_flat_sections(self) -> list[dict]:
        """Get flat list of all sections with their paths.
        
        Returns:
            List of dicts with section info including path.
        """
        sections = []
        
        def traverse(nodes: list[TOCNode], path: list[str]):
            for i, node in enumerate(nodes):
                # Determine page range
                page_end = None
                if i + 1 < len(nodes):
                    page_end = nodes[i + 1].item.page_number - 1
                
                sections.append({
                    "title": node.item.title,
                    "level": node.item.level,
                    "page_start": node.item.page_number,
                    "page_end": page_end,
                    "path": path.copy()
                })
                
                traverse(node.children, path + [node.item.title])
        
        traverse(self.root_nodes, [])
        return sections
    
    def get_sibling_sections(self, page_number: int) -> tuple[Optional[str], Optional[str]]:
        """Get preceding and following section titles for a page.
        
        Args:
            page_number: The page number to look up.
            
        Returns:
            Tuple of (preceding_section, following_section) titles.
        """
        flat = self.get_flat_sections()
        preceding = None
        following = None
        
        for i, section in enumerate(flat):
            if section["page_start"] <= page_number:
                if section["page_end"] is None or section["page_end"] >= page_number:
                    # Current section
                    if i > 0:
                        preceding = flat[i - 1]["title"]
                    if i + 1 < len(flat):
                        following = flat[i + 1]["title"]
                    break
                else:
                    preceding = section["title"]
            else:
                following = section["title"]
                break
        
        return preceding, following


def infer_toc_from_markdown(markdown: str) -> list[TOCItem]:
    """Infer TOC from markdown headings when PDF has no embedded TOC.
    
    Args:
        markdown: The markdown content to parse.
        
    Returns:
        List of TOCItem inferred from heading structure.
    """
    toc_items = []
    
    # Match markdown headings (# Heading)
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    
    for match in heading_pattern.finditer(markdown):
        level = len(match.group(1))
        title = match.group(2).strip()
        
        # We can't reliably determine page numbers from markdown
        # Use position as proxy (this is a limitation)
        toc_items.append(TOCItem(
            level=level,
            title=title,
            page_number=0  # Unknown from markdown alone
        ))
    
    return toc_items
