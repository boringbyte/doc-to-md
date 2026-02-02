
import re

file_path = "d:/Tools/AICode/doc-to-md/output/idrac9-user-s-guide.md"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the location of "# 1"
match = re.search(r'# 1\s*\n', content)
if match:
    start = match.start()
    end = start + 50 # Look ahead 50 chars
    snippet = content[start:end]
    print(f"Snippet found at {start}:")
    print(repr(snippet))
else:
    print("Could not find '# 1' followed by newline")

# Also checking regex match
pattern = r'^(#{1,6})\s+(\d+)[ \t]*\n\s*(?:#{1,6})\s+(.+)$'
check = re.search(pattern, content, flags=re.MULTILINE)
if check:
    print("Match FOUND!")
    print(check.groups())
else:
    print("Match NOT found with regex")
