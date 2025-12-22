import re
from typing import List, Optional

# Table detection patterns
TABLE_PAT = re.compile(r'(\|\s)|(\t)', re.MULTILINE)
ALIGNED_COLUMNS_PAT = re.compile(r'^[\w\s]+\s{2,}[\w\s]+\s*$', re.MULTILINE)
TABLE_STRUCTURE_PAT = re.compile(r'^[\w\s]+\s+[\w\s]+\s*$', re.MULTILINE)

# Header detection patterns
HEADER_PATTERNS = [
    r'^[A-Z][A-Za-z\s]{3,}$',  # Title case with min length
    r'^\d+\.\s+[A-Z]',         # Numbered sections
    r'^[A-Z\s]{4,}$',          # All caps headers
    r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$',  # Title case words
    r'^(?:[A-Za-z0-9 ,\-]{4,60})$'  # Mixed case with reasonable length
]

def looks_like_table(text: str) -> bool:
    """
    Enhanced table detection that looks for:
    1. Pipe characters or tabs
    2. Aligned columns
    3. Table-like structure
    4. Consistent row patterns
    """
    if not text or len(text.strip().split('\n')) < 2:
        return False
        
    lines = text.strip().split('\n')
    
    # Check for pipe characters or tabs
    if TABLE_PAT.search(text):
        return True
        
    # Check for aligned columns
    has_aligned_columns = False
    for i in range(len(lines)-2):
        window = lines[i:i+3]
        if len(window) < 3:
            continue
        # Check if lines have similar number of words
        word_counts = [len(line.split()) for line in window]
        if len(set(word_counts)) == 1 and word_counts[0] >= 2:
            has_aligned_columns = True
            break
            
    if has_aligned_columns:
        return True
        
    # Check for table-like structure
    if any(TABLE_STRUCTURE_PAT.match(line) for line in lines[:3]):
        return True
        
    # Check for consistent row patterns
    if len(lines) >= 3:
        first_line_words = len(lines[0].split())
        if all(len(line.split()) == first_line_words for line in lines[1:3]):
            return True
            
    return False

def is_heading_text(text: str) -> bool:
    """
    Enhanced header detection that checks multiple patterns:
    1. Title case with minimum length
    2. Numbered sections
    3. All caps headers
    4. Title case words
    5. Mixed case with reasonable length
    """
    if not text:
        return False
        
    text = text.strip()
    
    # Check all header patterns
    for pattern in HEADER_PATTERNS:
        if re.match(pattern, text):
            return True
            
    # Additional checks for common header indicators
    if text.endswith(':') and len(text) > 3:
        return True
        
    # Check for common header prefixes
    header_prefixes = ['Chapter', 'Section', 'Unit', 'Topic', 'Table', 'Figure']
    if any(text.startswith(prefix) for prefix in header_prefixes):
        return True
        
    return False

def get_chunk_metadata(chunk_text: str, source: str) -> dict:
    """
    Generate enhanced metadata for a chunk including improved table and header detection.
    """
    # Extract headers
    headers = []
    lines = chunk_text.strip().split('\n')
    if lines:
        first_line = lines[0].strip()
        if is_heading_text(first_line):
            headers.append(first_line)
            
    # Check for table
    is_table = looks_like_table(chunk_text)
    
    # Log detection results for debugging
    if is_table:
        print(f"[DEBUG] Detected table in chunk: {chunk_text[:100]}...")
    if headers:
        print(f"[DEBUG] Found headers: {headers}")
        
    return {
        "source": source,
        "is_table": is_table,
        "chunk_type": "table" if is_table else "text",
        "has_header": bool(headers),
        "headers": headers or [],
        "semantic_header": headers[0] if headers else None,
        "is_semantic": bool(headers),
        "length": len(chunk_text)
    }

def extract_headers(text: str) -> List[str]:
    """
    Extract all lines from the text that look like headers using is_heading_text.
    """
    if not text:
        return []
    lines = text.splitlines()
    return [line.strip() for line in lines if is_heading_text(line.strip())] 