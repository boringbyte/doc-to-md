import sys

def get_pages_to_exclude(toc, page_count):
    """
    Returns a list of 0-based page numbers to exclude, based on TOC.
    toc is a list of [level, title, page_number (1-based)]
    """
    toc_start_page = None
    toc_end_page = None
    
    for i, item in enumerate(toc):
        level, title, page = item
        title_lower = title.strip().lower()
        
        if toc_start_page is None:
            if title_lower in ["table of contents", "contents"]:
                toc_start_page = page
                
                # Find the next item that has a > page number
                for j in range(i + 1, len(toc)):
                    if toc[j][2] > toc_start_page:
                        toc_end_page = toc[j][2]
                        break
                        
                # If no subsequent item has a higher page number, just exclude the start page
                if toc_end_page is None:
                    # Let's say we assume it's 1 page if it's the last item
                    # or if subsequent items point to the same page.
                    # Or maybe point to the end of the document? Usually there are items after TOC.
                    toc_end_page = toc_start_page + 1
                    
                break

    if toc_start_page is not None:
        print(f"Found TOC from page {toc_start_page} to {toc_end_page - 1} (1-based)")
        # Return 0-based indices to exclude
        return list(range(toc_start_page - 1, toc_end_page - 1))
    
    return []

# Dummy test 1
toc1 = [
    [1, "Cover", 1],
    [1, "Contents", 2],
    [1, "Chapter 1", 5],
    [2, "Section 1.1", 5],
    [1, "Chapter 2", 10]
]
exclude1 = get_pages_to_exclude(toc1, 10)
print(f"Test 1 Exclude: {exclude1}")
include1 = [p for p in range(10) if p not in exclude1]
print(f"Test 1 Include: {include1}")

# Dummy test 2: No TOC entry
toc2 = [
    [1, "Chapter 1", 1]
]
exclude2 = get_pages_to_exclude(toc2, 10)
print(f"Test 2 Exclude: {exclude2}")
