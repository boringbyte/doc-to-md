"""Code block fixer for markdown content."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class CodeBlockFixerConfig:
    """Configuration for code block fixing."""
    # Detect and wrap inline code
    wrap_inline_code: bool = True
    # Detect and wrap code blocks
    wrap_code_blocks: bool = True
    # Keywords that indicate code
    code_indicators: tuple = (
        'function', 'def ', 'class ', 'import ', 'from ',
        'var ', 'let ', 'const ', 'public ', 'private ',
        'return ', 'if (', 'for (', 'while (', '<?php',
        '#!/', 'sudo ', 'apt-get', 'npm ', 'pip ',
        'racadm ', 'ipmitool ', 'curl ', 'wget '
    )


class CodeBlockFixer:
    """Detects and properly formats code in markdown.
    
    PDFs often contain code samples that aren't properly
    wrapped in code blocks. This processor:
    - Detects code-like content
    - Wraps in appropriate fenced blocks
    - Detects the language where possible
    """
    
    def __init__(self, config: Optional[CodeBlockFixerConfig] = None):
        """Initialize the code block fixer.
        
        Args:
            config: Configuration options.
        """
        self.config = config or CodeBlockFixerConfig()
    
    def fix_code_blocks(self, markdown: str) -> str:
        """Fix code block formatting in markdown.
        
        Args:
            markdown: The markdown content.
            
        Returns:
            Markdown with fixed code blocks.
        """
        result = markdown
        
        if self.config.wrap_inline_code:
            result = self._fix_inline_code(result)
        
        if self.config.wrap_code_blocks:
            result = self._detect_and_wrap_code_blocks(result)
        
        return result
    
    def _fix_inline_code(self, markdown: str) -> str:
        """Fix inline code formatting.
        
        Detects things like command line options, paths, and
        variable names that should be wrapped in backticks.
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with fixed inline code.
        """
        result = markdown
        
        # Wrap command-line arguments: --option, -flag
        result = re.sub(
            r'(?<!\`)\s(-{1,2}[a-zA-Z][a-zA-Z0-9\-_=]+)(?!\`)',
            r' `\1`',
            result
        )
        
        # Wrap file paths: /path/to/file, C:\path\to\file
        result = re.sub(
            r'(?<!\`)((?:/[a-zA-Z0-9_\-\.]+)+)(?!\`)',
            r'`\1`',
            result
        )
        
        # Wrap environment variables: $VAR, ${VAR}
        result = re.sub(
            r'(?<!\`)(\$\{?[A-Z_][A-Z0-9_]*\}?)(?!\`)',
            r'`\1`',
            result
        )
        
        return result
    
    def _detect_and_wrap_code_blocks(self, markdown: str) -> str:
        """Detect code-like content and wrap in fenced blocks.
        
        Args:
            markdown: Input markdown.
            
        Returns:
            Markdown with detected code wrapped.
        """
        lines = markdown.split('\n')
        result_lines = []
        in_code_block = False
        code_buffer = []
        detected_lang = ''
        
        for i, line in enumerate(lines):
            # Check if already in a fenced block
            if line.strip().startswith('```'):
                if in_code_block:
                    # End of existing block
                    in_code_block = False
                else:
                    # Start of existing block
                    in_code_block = True
                result_lines.append(line)
                continue
            
            if in_code_block:
                result_lines.append(line)
                continue
            
            # Detect if this line looks like code
            if self._looks_like_code(line):
                if not code_buffer:
                    # Start new code block
                    detected_lang = self._detect_language(line)
                code_buffer.append(line)
            else:
                if code_buffer:
                    # End of code block, flush buffer
                    if len(code_buffer) >= 2:  # Only wrap if 2+ lines
                        result_lines.append(f'```{detected_lang}')
                        result_lines.extend(code_buffer)
                        result_lines.append('```')
                    else:
                        result_lines.extend(code_buffer)
                    code_buffer = []
                    detected_lang = ''
                
                result_lines.append(line)
        
        # Flush any remaining buffer
        if code_buffer:
            if len(code_buffer) >= 2:
                result_lines.append(f'```{detected_lang}')
                result_lines.extend(code_buffer)
                result_lines.append('```')
            else:
                result_lines.extend(code_buffer)
        
        return '\n'.join(result_lines)
    
    def _looks_like_code(self, line: str) -> bool:
        """Check if a line looks like code.
        
        Args:
            line: The line to check.
            
        Returns:
            True if line appears to be code.
        """
        stripped = line.strip()
        
        if not stripped:
            return False
        
        # Skip markdown elements
        if stripped.startswith('#'):
            return False
        if stripped.startswith('|') or stripped.startswith('-'):
            return False
        if stripped.startswith('>'):
            return False
        if stripped.startswith('*') or stripped.startswith('+'):
            return False
        
        # Check for code indicators
        for indicator in self.config.code_indicators:
            if indicator in stripped.lower():
                return True
        
        # Check for command-prompt patterns
        if re.match(r'^[\$#>]\s+\w+', stripped):
            return True
        
        # Check for assignment patterns
        if re.search(r'\w+\s*=\s*["\'\d\[]', stripped):
            return True
        
        return False
    
    def _detect_language(self, line: str) -> str:
        """Detect the programming language from a line.
        
        Args:
            line: The line to analyze.
            
        Returns:
            Language identifier or empty string.
        """
        stripped = line.strip().lower()
        
        # Shell commands
        if re.match(r'^[\$#]\s+', stripped):
            return 'bash'
        if any(cmd in stripped for cmd in ['racadm', 'ipmitool']):
            return 'bash'
        if any(cmd in stripped for cmd in ['apt-get', 'yum', 'dnf', 'pip']):
            return 'bash'
        
        # Python
        if 'def ' in stripped or 'import ' in stripped:
            return 'python'
        
        # PowerShell
        if stripped.startswith('ps>') or 'get-' in stripped:
            return 'powershell'
        
        # JavaScript
        if any(kw in stripped for kw in ['const ', 'let ', 'var ', 'function']):
            return 'javascript'
        
        return ''
