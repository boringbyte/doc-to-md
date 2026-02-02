import re

# Test strings from the file
lines = [
    "**4** **Contents**",
    "**Contents** **5**",
    "**6** **Contents**",
    "**Contents** **7**",
    "**8** **Contents**"
]

common_sections = [
    'Contents', 'Overview of iDRAC', 'Logging in to iDRAC',
    'Setting up managed system', 'Configuring iDRAC',
    'Managing logs', 'Troubleshooting'
]

print("Testing regex patterns...")

for line in lines:
    print(f"\nTesting line: '{line}'")
    matched = False
    
    # Test Pattern 1: **Title** **Number**
    if re.match(r'^\s*\*\*[^*\\n]+?\*\*\s+\*\*\d{1,4}\*\*\s*$', line):
        print("  - Matched Pattern 1 (Generic)")
        matched = True
        
    # Test Pattern 2: **Number** **Title**
    if re.match(r'^\s*\*\*\d{1,4}\*\*\s+\*\*[^*\\n]+?\*\*\s*$', line):
        print("  - Matched Pattern 2 (Generic)")
        matched = True

    # Test Pattern 4: specific common sections
    for section in common_sections:
        # Section name then number
        # Note: In the actual code I used \** for some reason, but here I'll test strict **
        pattern1 = rf'^\s*\*\*{re.escape(section)}\*\*\s+\*\*\d{{1,4}}\*\*\s*$'
        
        if re.match(pattern1, line, re.IGNORECASE):
            print(f"  - Matched Pattern 4 (Specific - {section} first)")
            matched = True
            
        # Number then section name
        pattern2 = rf'^\s*\*\*\d{{1,4}}\*\*\s+\*\*{re.escape(section)}\*\*\s*$'
        if re.match(pattern2, line, re.IGNORECASE):
            print(f"  - Matched Pattern 4 (Specific - Number first)")
            matched = True

    if not matched:
        print("  - NO MATCH FOUND")

# Also checking the file content for invisible characters
with open('output/idrac9-user-s-guide.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the footer lines in actual content
print("\nScanning file content for exact matches:")
for line in content.split('\n'):
    line = line.strip()
    if "**Contents**" in line and len(line) < 30 and any(c.isdigit() for c in line):
        print(f"Found line in file: '{line}' (Length: {len(line)})")
        print(f"Hex: {line.encode('utf-8').hex()}")
        
        # Test against the cleanup function logic using the actual line
        result = line
        # Logic from markdown_cleanup.py
        result = re.sub(
            r'^\s*\*\*[^*\\n]+?\*\*\s+\*\*\d{1,4}\*\*\s*$',
            'REMOVED_GENERIC_1',
            result
        )
        result = re.sub(
            r'^\s*\*\*\d{1,4}\*\*\s+\*\*[^*\\n]+?\*\*\s*$',
            'REMOVED_GENERIC_2',
            result
        )
        print(f"  -> Cleanup result: '{result}'")

# Search for the Chapter 1 heading
print("\nSearching for Chapter 1 heading:")
matches = re.finditer(r'^.*Overview of iDRAC.*$', content, re.MULTILINE)
for i, match in enumerate(matches):
    print(f"Match {i+1}: '{match.group(0)}' (Line start: {content[:match.start()].count('\n') + 1})")

