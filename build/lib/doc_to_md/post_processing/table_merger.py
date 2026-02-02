"""Table merger for combining tables split across PDF pages."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class TableMergerConfig:
    """Configuration for table merging."""
    # Maximum lines between table fragments to consider merging
    max_gap_lines: int = 5
    # Whether content between fragments must be empty or just whitespace/page numbers
    strict_gap_check: bool = False
    # Minimum column match ratio for tables to be considered same structure
    min_column_match: float = 0.8


class TableMerger:
    """Merges tables that span multiple PDF pages.
    
    When PDFs are converted, a single table spanning pages 5-6 becomes
    two separate tables in the markdown. This processor identifies and
    merges such fragments.
    
    Detection criteria:
    - Tables with same column count/headers
    - Separated by only page artifacts or empty lines
    - Second table has no header row (continuation)
    """
    
    def __init__(self, config: Optional[TableMergerConfig] = None):
        """Initialize the table merger.
        
        Args:
            config: Merge configuration options.
        """
        self.config = config or TableMergerConfig()
    
    def merge_tables(self, markdown: str) -> str:
        """Find and merge split tables in markdown.
        
        Args:
            markdown: The markdown content.
            
        Returns:
            Markdown with merged tables.
        """
        # Find all tables
        tables = self._find_tables(markdown)
        
        if len(tables) < 2:
            return markdown
        
        # Identify merge candidates
        merges = self._identify_merge_candidates(tables, markdown)
        
        # Apply merges (in reverse order to preserve positions)
        result = markdown
        for merge in reversed(merges):
            result = self._apply_merge(result, merge)
        
        return result
    
    def _find_tables(self, markdown: str) -> list[dict]:
        """Find all markdown tables with their positions and metadata.
        
        Args:
            markdown: The markdown content.
            
        Returns:
            List of table info dicts.
        """
        tables = []
        
        # Pattern for markdown table (header, separator, rows)
        table_pattern = re.compile(
            r'(\|[^\n]+\|\n\|[-:\| ]+\|\n(?:\|[^\n]+\|\n)*)',
            re.MULTILINE
        )
        
        for match in table_pattern.finditer(markdown):
            table_text = match.group(1)
            rows = table_text.strip().split('\n')
            
            # Parse header
            header = rows[0] if rows else ''
            header_cols = [c.strip() for c in header.split('|') if c.strip()]
            
            tables.append({
                'start': match.start(),
                'end': match.end(),
                'text': table_text,
                'header': header,
                'header_cols': header_cols,
                'col_count': len(header_cols),
                'row_count': len(rows) - 2,  # Exclude header and separator
                'rows': rows[2:] if len(rows) > 2 else []  # Data rows only
            })
        
        return tables
    
    def _identify_merge_candidates(
        self,
        tables: list[dict],
        markdown: str
    ) -> list[dict]:
        """Identify pairs of tables that should be merged.
        
        Args:
            tables: List of table info dicts.
            markdown: Full markdown content.
            
        Returns:
            List of merge operations to perform.
        """
        merges = []
        skip_indices = set()
        
        for i in range(len(tables) - 1):
            if i in skip_indices:
                continue
                
            table1 = tables[i]
            table2 = tables[i + 1]
            
            # Check if tables could be a continuation
            if self._should_merge(table1, table2, markdown):
                merges.append({
                    'first_table': table1,
                    'second_table': table2,
                    'first_end': table1['end'],
                    'second_start': table2['start'],
                    'second_end': table2['end']
                })
                skip_indices.add(i + 1)
        
        return merges
    
    def _should_merge(
        self,
        table1: dict,
        table2: dict,
        markdown: str
    ) -> bool:
        """Determine if two tables should be merged.
        
        Args:
            table1: First table info.
            table2: Second table info.
            markdown: Full markdown content.
            
        Returns:
            True if tables should be merged.
        """
        # Must have same column count
        if table1['col_count'] != table2['col_count']:
            return False
        
        # Check the gap between tables
        gap = markdown[table1['end']:table2['start']]
        
        if not self._is_valid_gap(gap):
            return False
        
        # Check if second table looks like a continuation
        # (has same structure, might have repeated header or no meaningful header)
        if self._is_continuation_table(table1, table2):
            return True
        
        return False
    
    def _is_valid_gap(self, gap: str) -> bool:
        """Check if the gap between tables is acceptable for merging.
        
        Valid gaps contain only:
        - Whitespace
        - Page numbers (bold or plain)
        - Page header/footer artifacts
        
        Args:
            gap: The text between two tables.
            
        Returns:
            True if gap is valid for merging.
        """
        # Remove common page artifacts
        cleaned = gap
        
        # Remove page footers like "**Title** **23**"
        cleaned = re.sub(r'\*\*[^*]+\*\*\s*\*\*\d+\*\*', '', cleaned)
        # Remove standalone page numbers
        cleaned = re.sub(r'\*\*\d+\*\*', '', cleaned)
        cleaned = re.sub(r'^\d+$', '', cleaned, flags=re.MULTILINE)
        # Remove empty bold
        cleaned = re.sub(r'\*\*\s*\*\*', '', cleaned)
        
        # Check if remaining content is just whitespace
        if not cleaned.strip():
            return True
        
        # Check line count
        lines = [l for l in cleaned.split('\n') if l.strip()]
        if len(lines) <= self.config.max_gap_lines:
            if self.config.strict_gap_check:
                return False
            return True
        
        return False
    
    def _is_continuation_table(
        self,
        table1: dict,
        table2: dict
    ) -> bool:
        """Check if second table is a continuation of first.
        
        Continuation tables often have:
        - Same column structure
        - Header that matches or is "(continued)" style
        - Or header that looks like data (no real header)
        
        Args:
            table1: First table.
            table2: Second table.
            
        Returns:
            True if table2 appears to continue table1.
        """
        # Same column headers = likely continuation with repeated header
        if table1['header_cols'] == table2['header_cols']:
            return True
        
        # Check for continuation markers
        header_text = ' '.join(table2['header_cols']).lower()
        continuation_markers = ['continued', 'cont.', '(cont)', '...']
        if any(marker in header_text for marker in continuation_markers):
            return True
        
        # Check if headers look similar (same number, similar content)
        if table1['col_count'] == table2['col_count']:
            # Compare header similarity
            matches = 0
            for h1, h2 in zip(table1['header_cols'], table2['header_cols']):
                if h1.lower() == h2.lower():
                    matches += 1
            
            ratio = matches / table1['col_count'] if table1['col_count'] > 0 else 0
            if ratio >= self.config.min_column_match:
                return True
        
        return False
    
    def _apply_merge(self, markdown: str, merge: dict) -> str:
        """Apply a table merge operation.
        
        Args:
            markdown: Current markdown content.
            merge: Merge operation dict.
            
        Returns:
            Markdown with merge applied.
        """
        table1 = merge['first_table']
        table2 = merge['second_table']
        
        # Get the rows from second table (skip header and separator)
        rows_to_add = table2['rows']
        
        # Check if second table's header matches first (repeated header)
        if table1['header_cols'] == table2['header_cols']:
            # Skip the repeated header - just use data rows
            pass
        else:
            # Include the "header" as it might be data
            rows_to_add = table2['text'].strip().split('\n')
            # Skip only the separator row (index 1)
            if len(rows_to_add) > 2:
                rows_to_add = [rows_to_add[0]] + rows_to_add[2:]
            else:
                rows_to_add = []
        
        # Build merged table
        merged_rows = '\n'.join(rows_to_add)
        
        # Insert rows at end of first table, remove second table
        first_table_end = merge['first_end']
        second_table_start = merge['second_start']
        second_table_end = merge['second_end']
        
        # Construct new markdown:
        # - Content before first table end
        # - Additional rows from second table
        # - Content after second table
        
        if merged_rows:
            new_markdown = (
                markdown[:first_table_end - 1] +  # Before, without trailing newline
                '\n' + merged_rows +  # New rows
                markdown[second_table_end:]  # After second table
            )
        else:
            # No rows to add, just remove the second table
            new_markdown = (
                markdown[:second_table_start] +
                markdown[second_table_end:]
            )
        
        return new_markdown
    
    def get_table_statistics(self, markdown: str) -> dict:
        """Get statistics about tables in markdown.
        
        Args:
            markdown: The markdown content.
            
        Returns:
            Dict with table statistics.
        """
        tables = self._find_tables(markdown)
        
        stats = {
            "total_tables": len(tables),
            "potential_merges": 0,
            "tables_by_column_count": {}
        }
        
        # Count by column
        for table in tables:
            col_count = table['col_count']
            stats["tables_by_column_count"][col_count] = \
                stats["tables_by_column_count"].get(col_count, 0) + 1
        
        # Count potential merges
        for i in range(len(tables) - 1):
            if self._should_merge(tables[i], tables[i + 1], markdown):
                stats["potential_merges"] += 1
        
        return stats
