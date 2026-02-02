"""Table processor for validating and enhancing extracted tables."""

import re
from dataclasses import dataclass
from typing import Optional

from ..processing.models import TableData


@dataclass
class TableProcessorConfig:
    """Configuration for table processing."""
    # Minimum columns for a valid table
    min_columns: int = 2
    # Minimum rows (excluding header) for a valid table
    min_rows: int = 1
    # Add context from surrounding text
    add_context: bool = True
    # Maximum context characters before/after table
    context_chars: int = 200


class TableProcessor:
    """Processes and enhances extracted markdown tables.
    
    Features:
    - Validates table structure
    - Extracts captions from surrounding text
    - Cleans up malformed tables
    - Optionally converts to structured format
    """
    
    def __init__(self, config: Optional[TableProcessorConfig] = None):
        """Initialize the table processor.
        
        Args:
            config: Processing configuration.
        """
        self.config = config or TableProcessorConfig()
    
    def process_tables(
        self,
        markdown: str,
        tables: list[TableData]
    ) -> tuple[str, list[TableData]]:
        """Process all tables in markdown content.
        
        Args:
            markdown: The full markdown content.
            tables: List of extracted TableData objects.
            
        Returns:
            Tuple of (processed markdown, processed tables).
        """
        processed_tables = []
        
        for table in tables:
            processed = self._process_single_table(table, markdown)
            if processed:
                processed_tables.append(processed)
        
        return markdown, processed_tables
    
    def _process_single_table(
        self,
        table: TableData,
        full_markdown: str
    ) -> Optional[TableData]:
        """Process a single table.
        
        Args:
            table: The table to process.
            full_markdown: Full markdown for context extraction.
            
        Returns:
            Processed TableData or None if invalid.
        """
        # Validate table structure
        if not self._is_valid_table(table):
            return None
        
        # Extract caption if enabled
        caption = None
        if self.config.add_context:
            caption = self._extract_caption(table.content, full_markdown)
        
        # Clean up table content
        cleaned_content = self._clean_table(table.content)
        
        # Count rows and columns
        rows = cleaned_content.strip().split('\n')
        col_count = len([c for c in rows[0].split('|') if c.strip()]) if rows else 0
        row_count = len(rows) - 1 if len(rows) > 1 else 0  # Exclude separator
        
        return TableData(
            content=cleaned_content,
            page_number=table.page_number,
            caption=caption,
            row_count=row_count,
            col_count=col_count
        )
    
    def _is_valid_table(self, table: TableData) -> bool:
        """Check if a table is valid and worth keeping.
        
        Args:
            table: The table to validate.
            
        Returns:
            True if valid, False otherwise.
        """
        content = table.content.strip()
        rows = content.split('\n')
        
        if len(rows) < 2:  # Need at least header + separator
            return False
        
        # Check for valid separator row
        if not re.match(r'^\|[-:\s|]+\|$', rows[1]):
            return False
        
        # Check column count
        header_cols = len([c for c in rows[0].split('|') if c.strip()])
        if header_cols < self.config.min_columns:
            return False
        
        # Check row count
        data_rows = len(rows) - 2  # Exclude header and separator
        if data_rows < self.config.min_rows:
            return False
        
        return True
    
    def _extract_caption(self, table_content: str, full_markdown: str) -> Optional[str]:
        """Extract caption from text surrounding a table.
        
        Looks for "Table X:" patterns or bold text before the table.
        
        Args:
            table_content: The table's markdown content.
            full_markdown: The full document markdown.
            
        Returns:
            Caption string if found, None otherwise.
        """
        # Find table position in document
        table_pos = full_markdown.find(table_content)
        if table_pos == -1:
            return None
        
        # Look at text before table
        before_text = full_markdown[max(0, table_pos - self.config.context_chars):table_pos]
        
        # Look for "Table X:" pattern
        table_pattern = re.search(r'Table\s+\d+[.:]\s*([^\n]+)', before_text, re.IGNORECASE)
        if table_pattern:
            return table_pattern.group(0).strip()
        
        # Look for bold text that might be a caption
        bold_pattern = re.search(r'\*\*([^*]+)\*\*\s*$', before_text)
        if bold_pattern:
            return bold_pattern.group(1).strip()
        
        # Look for italic text
        italic_pattern = re.search(r'\*([^*]+)\*\s*$', before_text)
        if italic_pattern:
            return italic_pattern.group(1).strip()
        
        return None
    
    def _clean_table(self, content: str) -> str:
        """Clean up table formatting.
        
        Args:
            content: The table markdown.
            
        Returns:
            Cleaned table markdown.
        """
        lines = content.strip().split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Ensure proper pipe formatting
            line = line.strip()
            if not line.startswith('|'):
                line = '| ' + line
            if not line.endswith('|'):
                line = line + ' |'
            
            # Normalize whitespace around pipes
            line = re.sub(r'\|\s+', '| ', line)
            line = re.sub(r'\s+\|', ' |', line)
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def extract_tables_with_context(
        self,
        markdown: str
    ) -> list[dict]:
        """Extract all tables from markdown with surrounding context.
        
        Args:
            markdown: The markdown content.
            
        Returns:
            List of dicts with table content and context.
        """
        tables_with_context = []
        
        # Find all tables
        table_pattern = re.compile(
            r'(\|[^\n]+\|\n\|[-:\| ]+\|\n(?:\|[^\n]+\|\n)*)',
            re.MULTILINE
        )
        
        for match in table_pattern.finditer(markdown):
            table_content = match.group(1).strip()
            start_pos = match.start()
            end_pos = match.end()
            
            # Get context before
            context_before = markdown[max(0, start_pos - self.config.context_chars):start_pos]
            context_before = context_before.split('\n')[-3:]  # Last 3 lines
            
            # Get context after
            context_after = markdown[end_pos:min(len(markdown), end_pos + self.config.context_chars)]
            context_after = context_after.split('\n')[:3]  # First 3 lines
            
            # Try to extract caption
            caption = self._extract_caption(table_content, markdown)
            
            tables_with_context.append({
                "content": table_content,
                "caption": caption,
                "context_before": '\n'.join(context_before).strip(),
                "context_after": '\n'.join(context_after).strip(),
                "position": start_pos
            })
        
        return tables_with_context
