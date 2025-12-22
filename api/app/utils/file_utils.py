import os
import re
import shutil
import json
import logging
import codecs
from typing import List, Dict, Any, Tuple
from pathlib import Path
from ..config.settings import DATA_DIR, VECTOR_STORES_DIR, VIDEOS_DIR
# LangChain splitters moved in newer versions; support both paths
try:
    from langchain_text_splitters import (
        RecursiveCharacterTextSplitter,
        MarkdownHeaderTextSplitter,
        TokenTextSplitter,
    )
except ImportError:  # fallback for older langchain versions
    from langchain.text_splitter import (
        RecursiveCharacterTextSplitter,
        MarkdownHeaderTextSplitter,
        TokenTextSplitter,
    )
import pdfplumber
import io
import pandas as pd
import nltk
from nltk.tokenize import sent_tokenize, PunktSentenceTokenizer
import unicodedata
import tempfile, io, logging, subprocess, shutil
import pdfplumber, pytesseract
from PIL import Image
from pdfminer.high_level import extract_text as pdfminer_extract
import fitz  # PyMuPDF
from .text_utils import get_chunk_metadata, looks_like_table, extract_headers
from langchain.schema import Document as LC_Document
from docx import Document as DocxDocument

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(DATA_DIR, 'extraction.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Try to import optional dependencies with fallbacks
try:
    import tabula.io as tabula
    TABULA_AVAILABLE = True
except ImportError:
    TABULA_AVAILABLE = False
    logger.warning("tabula-py not available. Table extraction will be limited.")

try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False
    logger.warning("camelot-py not available. Advanced table extraction will be limited.")

try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    logger.warning("PyPDF2 not available. PDF extraction will be limited.")

class NLTKManager:
    """Manages NLTK resources and tokenization"""
    _initialized = False
    _tokenizer = None
    
    @classmethod
    def initialize(cls):
        """Initialize NLTK resources"""
        if cls._initialized:
            return
            
        try:
            # Download punkt if not present
            nltk.download('punkt', quiet=True)
            
            # Set up NLTK data path
            nltk_data_path = os.path.join(os.path.expanduser('~'), 'nltk_data')
            if not os.path.exists(nltk_data_path):
                os.makedirs(nltk_data_path)
            nltk.data.path.append(nltk_data_path)
            
            # Create a custom tokenizer instead of loading from file
            cls._tokenizer = PunktSentenceTokenizer()
            cls._initialized = True
            logger.info("NLTK resources initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize NLTK resources: {str(e)}")
            raise
    
    @classmethod
    def tokenize_sentences(cls, text: str) -> List[str]:
        """Tokenize text into sentences with fallback"""
        if not cls._initialized:
            cls.initialize()
            
        try:
            if cls._tokenizer:
                # Train the tokenizer on the text if needed
                cls._tokenizer.train(text)
                return cls._tokenizer.tokenize(text)
            else:
                raise ValueError("Tokenizer not initialized")
        except Exception as e:
            logger.warning(f"NLTK tokenization failed, using fallback: {str(e)}")
            # Fallback: Split by common sentence endings while preserving special characters
            sentences = []
            # Split by sentence endings while preserving abbreviations
            parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
            for part in parts:
                if part.strip():
                    # Further split by other sentence endings if needed
                    subparts = re.split(r'(?<=[.!?])\s+', part)
                    sentences.extend(p.strip() for p in subparts if p.strip())
            return sentences

# Initialize NLTK resources
try:
    NLTKManager.initialize()
except Exception as e:
    logger.warning(f"Initial NLTK initialization failed, will try again when needed: {str(e)}")

def sanitize_filename(name: str) -> str:
    """Remove or replace invalid characters for Windows folders"""
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def ensure_dir(dir_path: str) -> str:
    """Make sure directory exists, create if not, with improved error handling"""
    if not dir_path:
        raise ValueError("Directory path cannot be empty")
    
    try:
        dir_path = os.path.abspath(dir_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            print(f"Created directory: {dir_path}")
        
        # Verify the directory is writeable
        testfile_path = os.path.join(dir_path, f"test_write_{os.urandom(4).hex()}.tmp")
        try:
            with open(testfile_path, 'w') as f:
                f.write('test')
            os.remove(testfile_path)
        except Exception as write_error:
            print(f"Warning: Directory {dir_path} exists but may not be writeable: {str(write_error)}")
        
        return dir_path
    except Exception as e:
        print(f"Error creating directory {dir_path}: {str(e)}")
        raise ValueError(f"Failed to create directory {dir_path}: {str(e)}")

def save_json(data: Any, filepath: str) -> None:
    """Save data to a JSON file"""
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved data to {filepath}")
    except Exception as e:
        print(f"Error saving data to {filepath}: {str(e)}")
        raise

def load_json(filepath: str) -> Any:
    """Load data from a JSON file"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading data from {filepath}: {str(e)}")
    return None

def get_file_size(filepath: str) -> str:
    """Get human-readable file size"""
    size_bytes = os.path.getsize(filepath)
    return f"{size_bytes / 1024:.1f} KB"

def is_valid_file_type(filename: str, allowed_extensions: set) -> bool:
    """Check if file has an allowed extension"""
    return os.path.splitext(filename)[1].lower() in allowed_extensions

def get_relative_path(filepath: str, base_dir: str) -> str:
    """Get path relative to base directory"""
    return os.path.relpath(filepath, base_dir)

def delete_empty_parents(filepath: str, stop_at: str) -> None:
    """Recursively delete empty parent directories up to stop_at"""
    parent = os.path.dirname(filepath)
    while parent != stop_at and os.path.isdir(parent) and not os.listdir(parent):
        os.rmdir(parent)
        print(f"Deleted empty folder: {parent}")
        parent = os.path.dirname(parent)

def normalize_superscripts(text: str) -> str:
    """Convert numbers to proper superscripts"""
    superscript_map = str.maketrans("0123456789+-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻")
    return text.translate(superscript_map)

def clean_text(text: str) -> str:
    """Enhanced cleaning with scientific notation preservation"""
    if not text:
        return ""
    
    # Preserve chemical formulas and ions
    text = re.sub(
        r'([A-Z][a-z]?)([0-9⁰¹²³⁴⁵⁶⁷⁸⁹\+−⁻⁺]*)', 
        lambda m: m.group(1) + normalize_superscripts(m.group(2)),
        text
    )
    
    # Preserve measurement units
    unit_patterns = [
        (r'(\d+)\s*(mmol|mEq|mg|g|ml|L)\s*[⁻-]?[¹1]?', r'\1 \2'),
        (r'(\d+)\s*([°º]C|%|mM|μM)', r'\1\2'),
        (r'(\d+)\s*-\s*(\d+)\s*(mmol|mEq)/L', r'\1-\2 \3/L')
    ]
    
    for pattern, replacement in unit_patterns:
        text = re.sub(pattern, replacement, text)
    
    # Normalize whitespace while preserving structure
    text = re.sub(r'(?<!\n)\s+(?!\n)', ' ', text)  # Single spaces
    text = re.sub(r'\n\s+\n', '\n\n', text)  # Paragraph breaks
    
    return text.strip()

def log_text_comparison(original_text: str, extracted_text: str, page_num: int = None):
    """Log comparison between original and extracted text with proper encoding"""
    if not original_text or not extracted_text:
        return
    
    try:
        # Normalize both texts for comparison while preserving special characters
        def normalize_text(text):
            # Preserve chemical formulas and medical notations
            text = re.sub(r'([A-Z][a-z]?)(\d+)?', r'\1\2', text)
            text = re.sub(r'([A-Z][a-z]?)([+-])(\d+)?', r'\1\2\3', text)
            return re.sub(r'\s+', ' ', text.lower().strip())
        
        orig_norm = normalize_text(original_text)
        extr_norm = normalize_text(extracted_text)
        
        # Find missing content
        missing_content = []
        orig_words = set(orig_norm.split())
        extr_words = set(extr_norm.split())
        missing_words = orig_words - extr_words
        
        if missing_words:
            # Find context around missing words
            for word in missing_words:
                # Find the sentence containing the missing word in original text
                sentences = re.split(r'[.!?]', original_text)
                for sentence in sentences:
                    if word.lower() in sentence.lower():
                        missing_content.append(sentence.strip())
                        break
            
            page_info = f"Page {page_num}" if page_num is not None else "Document"
            logger.warning(f"\n{'='*50}\nMissing content in {page_info}:")
            for content in missing_content:
                try:
                    logger.warning(f"Missing: {content}")
                except UnicodeEncodeError:
                    # Fallback for logging special characters
                    logger.warning(f"Missing content (contains special characters): {content.encode('ascii', 'replace').decode()}")
            
            logger.warning(f"Total missing words: {len(missing_words)}")
            try:
                logger.warning(f"Missing words: {', '.join(missing_words)}")
            except UnicodeEncodeError:
                # Fallback for logging special characters
                logger.warning("Missing words (contains special characters)")
            logger.warning('='*50)
    except Exception as e:
        logger.error(f"Error in text comparison: {str(e)}")

def extract_tables_from_page(page) -> List[str]:
    """Extract tables from a PDF page with improved error handling"""
    try:
        tables = []
        # Extract tables using tabula-py
        df_list = tabula.read_pdf(
            page,
            pages='all',
            multiple_tables=True,
            guess=True,
            lattice=True,
            stream=True,
            pandas_options={'header': None}
        )
        
        for df in df_list:
            try:
                if df is not None and not df.empty:
                    # Convert DataFrame to list of lists
                    table_data = df.fillna('').values.tolist()
                    # Convert to markdown
                    table_md = convert_table_to_markdown(table_data)
                    if table_md:
                        tables.append(table_md)
            except Exception as e:
                logger.warning(f"Error processing table: {str(e)}")
                continue
                
        return tables
        
    except Exception as e:
        logger.error(f"Error extracting tables from page: {str(e)}")
        return []

def convert_table_to_markdown(table: List[List[str]]) -> str:
    """Convert a table to markdown format with better error handling"""
    try:
        # Validate table structure
        if not table or not isinstance(table, list):
            logger.warning("Invalid table structure: empty or not a list")
            return ""
            
        # Filter out empty rows and ensure all rows are lists
        table = [row for row in table if isinstance(row, list) and any(str(cell).strip() for cell in row if cell is not None)]
        if not table:
            logger.warning("No valid rows in table")
            return ""
            
        # Ensure all rows have the same number of columns
        max_cols = max(len(row) for row in table)
        table = [row + [''] * (max_cols - len(row)) for row in table]
        
        # Create header separator
        header_sep = ['---'] * max_cols
        
        # Convert to markdown with proper escaping
        markdown_rows = []
        for i, row in enumerate(table):
            # Clean and escape cell content
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cell = ''
                cell_str = str(cell).strip()
                # Escape special characters and normalize whitespace
                cell_str = (cell_str.replace('|', '\\|')
                           .replace('\n', ' ')
                           .replace('\r', '')
                           .replace('\t', ' ')
                           .replace('  ', ' '))
                cleaned_row.append(cell_str)
            
            # Only add row if it has content
            if any(cell for cell in cleaned_row):
                markdown_rows.append('| ' + ' | '.join(cleaned_row) + ' |')
                
                # Add header separator after first row
                if i == 0:
                    markdown_rows.append('|' + '|'.join(header_sep) + '|')
        
        if not markdown_rows:
            logger.warning("No valid content in table")
            return ""
            
        return '\n'.join(markdown_rows)
        
    except Exception as e:
        logger.error(f"Error converting table to markdown: {str(e)}")
        return ""

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF with improved error handling and table preservation"""
    try:
        # Open PDF with fallback options
        if PYPDF2_AVAILABLE:
            try:
                pdf = PdfReader(pdf_path)
                if not pdf.pages:
                    raise ValueError("PDF has no pages")
                total_pages = len(pdf.pages)
                logger.info(f"Total pages in document: {total_pages}")
                
                all_text = []
                for i, page in enumerate(pdf.pages, 1):
                    try:
                        logger.info(f"\nProcessing page {i}/{total_pages}")
                        
                        # Extract tables first using tabula-py if available
                        if TABULA_AVAILABLE:
                            try:
                                tables = tabula.read_pdf(
                                    pdf_path,
                                    pages=i,
                                    multiple_tables=True,
                                    guess=True,
                                    lattice=True,
                                    stream=True,
                                    pandas_options={'header': None}
                                )
                                for table_idx, table in enumerate(tables, 1):
                                    if not table.empty:
                                        # Clean and validate table data
                                        table_data = table.fillna('').values.tolist()
                                        if any(any(cell for cell in row) for row in table_data):
                                            table_md = convert_table_to_markdown(table_data)
                                            if table_md:
                                                all_text.append(f"\n=== Tables from Page {i} ===\nTable {table_idx}:\n{table_md}\n")
                                                logger.info(f"Extracted table {table_idx} from page {i}")
                            except Exception as table_error:
                                logger.warning(f"Table extraction failed on page {i}: {str(table_error)}")
                        else:
                            logger.info("Tabula not available, skipping table extraction")
                        
                        # Extract text from page
                        text = page.extract_text()
                        if text:
                            # Clean and normalize text while preserving structure
                            text = clean_text(text)
                            if text.strip():
                                all_text.append(f"\n=== Page {i} Content ===\n{text}\n")
                                logger.info(f"Processed page {i} with {len(text)} characters")
                        
                    except Exception as e:
                        logger.error(f"Error processing page {i}: {str(e)}")
                        continue
                
                if not all_text:
                    logger.error("No text extracted from PDF")
                    return ""
                
                final_text = "\n".join(all_text)
                logger.info(f"Total extracted text length: {len(final_text)} characters")
                return final_text
                
            except Exception as e:
                logger.error(f"Error opening PDF with PyPDF2: {str(e)}")
                # Fallback to pdfplumber
                return extract_text_with_pdfplumber(pdf_path)
        else:
            logger.warning("PyPDF2 not available, using pdfplumber fallback")
            return extract_text_with_pdfplumber(pdf_path)
            
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")

def extract_text_with_pdfplumber(pdf_path: str) -> str:
    """Fallback PDF extraction using pdfplumber"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                raise ValueError("PDF has no pages")
            total_pages = len(pdf.pages)
            logger.info(f"Total pages in document: {total_pages}")
            
            all_text = []
            for i, page in enumerate(pdf.pages, 1):
                try:
                    logger.info(f"\nProcessing page {i}/{total_pages}")
                    
                    # Extract tables first using tabula-py if available
                    if TABULA_AVAILABLE:
                        try:
                            tables = tabula.read_pdf(
                                pdf_path,
                                pages=i,
                                multiple_tables=True,
                                guess=True,
                                lattice=True,
                                stream=True,
                                pandas_options={'header': None}
                            )
                            for table_idx, table in enumerate(tables, 1):
                                if not table.empty:
                                    # Clean and validate table data
                                    table_data = table.fillna('').values.tolist()
                                    if any(any(cell for cell in row) for row in table_data):
                                        table_md = convert_table_to_markdown(table_data)
                                        if table_md:
                                            all_text.append(f"\n=== Tables from Page {i} ===\nTable {table_idx}:\n{table_md}\n")
                                            logger.info(f"Extracted table {table_idx} from page {i}")
                        except Exception as table_error:
                            logger.warning(f"Table extraction failed on page {i}: {str(table_error)}")
                    else:
                        logger.info("Tabula not available, skipping table extraction")
                    
                    # Extract text from page
                    text = page.extract_text()
                    if text:
                        # Clean and normalize text while preserving structure
                        text = clean_text(text)
                        if text.strip():
                            all_text.append(f"\n=== Page {i} Content ===\n{text}\n")
                            logger.info(f"Processed page {i} with {len(text)} characters")
                    
                except Exception as e:
                    logger.error(f"Error processing page {i}: {str(e)}")
                    continue
            
            if not all_text:
                logger.error("No text extracted from PDF")
                return ""
            
            final_text = "\n".join(all_text)
            logger.info(f"Total extracted text length: {len(final_text)} characters")
            return final_text
            
    except Exception as e:
        logger.error(f"Error in pdfplumber extraction: {str(e)}")
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")

def create_chunk(components: List[Tuple[str, str]]) -> Dict:
    """Create a structured chunk with metadata"""
    headers = [c[1] for c in components if c[0] == 'header']
    texts = [c[1] for c in components if c[0] == 'text']
    
    return {
        'text': ' '.join(texts),
        'headers': headers,
        'type': 'medical',
        'length': sum(len(t) for t in texts)
    }

def validate_content_coverage(original_text: str, chunks: List[Dict]) -> Dict:
    """Validate content coverage between original text and chunks"""
    try:
        # Extract all meaningful segments from original
        original_segments = set()
        for sentence in NLTKManager.tokenize_sentences(original_text):
            clean = clean_text(sentence)
            if len(clean) > 25:  # Only meaningful segments
                original_segments.add(clean)
        
        # Extract all chunk segments
        chunk_segments = set()
        for chunk in chunks:
            chunk_text = chunk.get('text', '')
            for sentence in NLTKManager.tokenize_sentences(chunk_text):
                clean = clean_text(sentence)
                if len(clean) > 25:
                    chunk_segments.add(clean)
        
        # Calculate metrics
        missing = original_segments - chunk_segments
        coverage = len(chunk_segments) / len(original_segments) if original_segments else 0
        
        # Group missing content by type
        missing_by_type = {
            'tables': [],
            'measurements': [],
            'definitions': [],
            'other': []
        }
        
        for segment in missing:
            if '|' in segment or 'Table' in segment:
                missing_by_type['tables'].append(segment)
            elif re.search(r'\d+\.?\d*\s*(mmol|mEq|%|mg)', segment):
                missing_by_type['measurements'].append(segment)
            elif re.search(r'(Definition|Role|Function):', segment):
                missing_by_type['definitions'].append(segment)
            else:
                missing_by_type['other'].append(segment)
        
        return {
            'total_original': len(original_segments),
            'total_chunked': len(chunk_segments),
            'coverage_percent': round(coverage * 100, 2),
            'missing_count': len(missing),
            'missing_by_type': {k: len(v) for k, v in missing_by_type.items()},
            'sample_missing': {k: v[:3] for k, v in missing_by_type.items()}
        }
    except Exception as e:
        logger.error(f"Error in content validation: {str(e)}")
        return {
            'total_original': 0,
            'total_chunked': 0,
            'coverage_percent': 0,
            'missing_count': 0,
            'missing_by_type': {},
            'sample_missing': {}
        }

def build_splitter(chunk_size: int = 1000, chunk_overlap: int = 200):
    """
    Build an adaptive text splitter that:
    1. First tries to respect markdown structure
    2. Falls back to recursive character splitting
    3. Uses token splitting as a last resort
    """
    # 1st pass: honour markdown bullet & header boundaries
    md_splitter = MarkdownHeaderTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        headers_to_split_on=[
            ("#", "h1"), ("##", "h2"), ("###", "h3"),
            ("- ", "bullet"), ("• ", "bullet")
        ]
    )
    
    # 2nd pass: fallback for anything still > chunk_size
    rc_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ".", "!", "?", ";", ":", " ", ""]
    )
    
    # 3rd pass: protect against pathological long tokens
    tk_splitter = TokenTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    def splitter(text: str):
        """Adaptive text splitting with fallbacks"""
        for chunk in md_splitter.split_text(text):
            if len(chunk) <= chunk_size:
                yield chunk
            else:
                for sub in rc_splitter.split_text(chunk):
                    if len(sub) <= chunk_size:
                        yield sub
                    else:
                        yield from tk_splitter.split_text(sub)

    return splitter

def process_pdf_to_chunks(text_or_path: str, chunk_size: int = 800, chunk_overlap: int = 100) -> List[Dict]:
    """Enhanced semantic chunking for medical/scientific content with improved table and header handling"""
    logger.info(f"\n{'='*50}\nStarting chunking process")
    logger.info(f"Chunk size: {chunk_size}, Overlap: {chunk_overlap}")
    
    try:
        # Handle both file paths and pre-extracted text
        if os.path.exists(text_or_path):
            logger.info(f"Processing PDF file: {text_or_path}")
            raw_text = extract_text_from_pdf(text_or_path)
        else:
            logger.info("Processing pre-extracted text")
            raw_text = text_or_path
            
        if not raw_text:
            logger.error("No text to process")
            return []
        
        logger.info(f"Raw text length before chunking: {len(raw_text)} characters")
        
        # Use adaptive splitter
        splitter = build_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        raw_chunks = list(splitter(raw_text))
        
        if not raw_chunks:
            logger.error("No chunks generated from document")
            return []
            
        # Process chunks with enhanced metadata
        chunks = []
        MIN_CHUNK_SIZE = 100  # Minimum chunk size to keep
        
        # First pass: process all chunks with metadata
        for chunk_text in raw_chunks:
            # Get enhanced metadata
            metadata = get_chunk_metadata(chunk_text, text_or_path)
            
            # Log detection results
            if metadata["is_table"]:
                logger.info(f"Detected table chunk of size {len(chunk_text)}")
                logger.debug(f"Table preview: {chunk_text[:200]}...")
            
            if metadata["has_header"]:
                logger.info(f"Found headers in chunk: {metadata['headers']}")
            
            chunks.append({
                'text': chunk_text,
                **metadata
            })
        
        # Second pass: filter small chunks and merge if possible
        filtered_chunks = []
        current_chunk = None
        
        for chunk in chunks:
            if len(chunk['text']) < MIN_CHUNK_SIZE:
                logger.debug(f"Skipping small chunk of size {len(chunk['text'])}")
                # Try to merge with previous chunk if it exists
                if current_chunk:
                    current_chunk['text'] += "\n" + chunk['text']
                    current_chunk['length'] = len(current_chunk['text'])
                    # Update metadata if needed
                    if not current_chunk['has_header'] and chunk['has_header']:
                        current_chunk.update({
                            'has_header': True,
                            'headers': chunk['headers'],
                            'semantic_header': chunk['semantic_header']
                        })
                    logger.debug(f"Merged small chunk into previous chunk")
                continue
            
            if current_chunk:
                filtered_chunks.append(current_chunk)
            current_chunk = chunk
        
        # Add the last chunk if it exists
        if current_chunk:
            filtered_chunks.append(current_chunk)
        
        # Update chunks list
        chunks = filtered_chunks
        
        # Validate content coverage
        validation = validate_content_coverage(raw_text, chunks)
        logger.info(f"\nContent Coverage Analysis:")
        logger.info(f"Coverage: {validation['coverage_percent']}%")
        logger.info(f"Total segments: {validation['total_original']}")
        logger.info(f"Chunked segments: {validation['total_chunked']}")
        
        if validation['missing_count'] > 0:
            logger.warning(f"\nMissing Content Analysis:")
            logger.warning(f"Missing segments: {validation['missing_count']}")
            for content_type, count in validation['missing_by_type'].items():
                if count > 0:
                    logger.warning(f"Missing {content_type}: {count}")
                    for sample in validation['sample_missing'][content_type]:
                        logger.warning(f"Sample missing {content_type}: {sample[:200]}...")
        
        # Log final statistics
        total_chars = sum(chunk['length'] for chunk in chunks)
        logger.info(f"\nChunking complete:")
        logger.info(f"Total chunks created: {len(chunks)}")
        logger.info(f"Total characters in chunks: {total_chars}")
        logger.info(f"Average chunk size: {total_chars/len(chunks) if chunks else 0:.2f} characters")
        
        # Log metadata statistics
        table_chunks = sum(1 for c in chunks if c['is_table'])
        header_chunks = sum(1 for c in chunks if c['has_header'])
        logger.info(f"\nMetadata Statistics:")
        logger.info(f"Table chunks: {table_chunks}")
        logger.info(f"Chunks with headers: {header_chunks}")
        
        # Log chunk details for verification
        logger.info("\nChunk Details:")
        for i, chunk in enumerate(chunks):
            logger.info(f"\nChunk {i}:")
            logger.info(f"Length: {chunk['length']}")
            logger.info(f"Type: {chunk['chunk_type']}")
            logger.info(f"Has header: {chunk['has_header']}")
            if chunk['has_header']:
                logger.info(f"Headers: {chunk['headers']}")
            logger.info(f"Preview: {chunk['text'][:100]}...")
        
        return chunks
        
    except Exception as e:
        logger.error(f"Error in chunking process: {str(e)}")
        raise ValueError(f"Failed to process document into chunks: {str(e)}")

# Glyph map for Symbol font characters
_GLYPH_MAP = {
    '\uF0B8': '±', '\uF06E': 'μ',  # common Symbol-encoded glyphs
    '\uF0B1': '°', '\uF0D8': 'β',  '\uF0E5': 'π',
}

def _fix_glyphs(s: str) -> str:
    """Replace Symbol-encoded private-use glyphs with Unicode equivalents."""
    return ''.join(_GLYPH_MAP.get(ch, ch) for ch in s)

def extract_text_from_pdf_fitz(path: str) -> str:
    """
    Improved PDF text extraction using configurable extractors:
    1. Primary: pdfplumber or PyPDF2 (configurable)
    2. Fallback: Alternative extractor if primary fails
    3. Final fallback: PyMuPDF for problematic PDFs
    Returns one clean Unicode string ready for chunking.
    """
    from ..config.settings import PDF_EXTRACTION_CONFIG
    
    config = PDF_EXTRACTION_CONFIG
    primary_extractor = config["primary_extractor"]
    fallback_threshold = config["fallback_threshold"]
    enable_tables = config["enable_table_extraction"]
    log_details = config["log_extraction_details"]
    max_size_mb = config["max_file_size_mb"]
    
    if log_details:
        logger.info(f"[PDF-EXTRACT] Using {primary_extractor} as primary extractor")
    
    try:
        # Validate PDF file first
        file_size = os.path.getsize(path)
        if file_size == 0:
            raise ValueError("PDF file is empty")
        
        file_size_mb = file_size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            raise ValueError(f"PDF file too large: {file_size_mb:.1f}MB (max: {max_size_mb}MB)")
        
        if log_details:
            logger.info(f"[PDF-EXTRACT] Processing PDF: {os.path.basename(path)} ({file_size_mb:.1f}MB)")
        
        # Reduce logging noise from PDF libraries
        import logging
        pdfplumber_logger = logging.getLogger('pdfplumber')
        pdfplumber_logger.setLevel(logging.WARNING)
        pdfminer_logger = logging.getLogger('pdfminer')
        pdfminer_logger.setLevel(logging.WARNING)
        
        # Primary extraction based on configuration
        primary_pages: List[str] = []
        total_pages = 0
        
        if primary_extractor == "pdfplumber":
            # Use pdfplumber as primary (better for tables and complex layouts)
            with pdfplumber.open(path) as pdf:
                total_pages = len(pdf.pages)
                if log_details:
                    logger.info(f"[PDF-EXTRACT] Total pages: {total_pages}")
                
                for i, page in enumerate(pdf.pages, 1):
                    try:
                        # Extract text with better tolerance for layout
                        text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
                        
                        # Extract tables if enabled
                        tables_text = ""
                        if enable_tables:
                            try:
                                for table in page.extract_tables():
                                    if table:
                                        # Convert table to tab-separated format
                                        table_rows = []
                                        for row in table:
                                            if row and any(cell for cell in row):
                                                # Clean and join cells
                                                clean_row = [str(cell).strip() if cell else "" for cell in row]
                                                table_rows.append("\t".join(clean_row))
                                        if table_rows:
                                            tables_text += "\n" + "\n".join(table_rows) + "\n"
                            except Exception as table_error:
                                if log_details:
                                    logger.debug(f"[PDF-EXTRACT] Table extraction failed on page {i}: {str(table_error)}")
                        
                        # Combine text and tables
                        page_text = _fix_glyphs(text + tables_text)
                        primary_pages.append(page_text)
                        
                        # Log progress for large documents
                        if total_pages > 10 and i % 10 == 0 and log_details:
                            logger.info(f"[PDF-EXTRACT] Processed {i}/{total_pages} pages")
                            
                    except Exception as page_error:
                        if log_details:
                            logger.warning(f"[PDF-EXTRACT] Error processing page {i}: {str(page_error)}")
                        primary_pages.append("")
        
        else:
            # Use PyPDF2 as primary (faster but less accurate)
            with open(path, "rb") as fh:
                reader = PdfReader(fh)
                total_pages = len(reader.pages)
                if log_details:
                    logger.info(f"[PDF-EXTRACT] Total pages: {total_pages}")
                
                for i, page in enumerate(reader.pages, 1):
                    try:
                        txt = page.extract_text() or ""
                        primary_pages.append(_fix_glyphs(txt))
                        
                        # Log progress for large documents
                        if total_pages > 10 and i % 10 == 0 and log_details:
                            logger.info(f"[PDF-EXTRACT] Processed {i}/{total_pages} pages")
                            
                    except Exception as page_error:
                        if log_details:
                            logger.warning(f"[PDF-EXTRACT] Error processing page {i}: {str(page_error)}")
                        primary_pages.append("")
        
        primary_text = "\n<<<PAGE_BREAK>>>\n".join(primary_pages)
        primary_len = len(primary_text)
        avg_chars_per_page = primary_len / max(total_pages, 1)
        
        if log_details:
            logger.info(f"[PDF-EXTRACT] Primary extraction: {primary_len} chars total, {avg_chars_per_page:.1f} chars/page avg")
        
        # Only use fallback if primary extraction extracted very little text
        if primary_len == 0 or avg_chars_per_page < fallback_threshold:
            fallback_extractor = "pypdf2" if primary_extractor == "pdfplumber" else "pdfplumber"
            if log_details:
                logger.info(f"[PDF-EXTRACT] Low text extraction ({avg_chars_per_page:.1f} chars/page) - trying {fallback_extractor} fallback")
            
            try:
                fallback_pages: List[str] = []
                
                if fallback_extractor == "pdfplumber":
                    with pdfplumber.open(path) as pdf:
                        for p in pdf.pages:
                            t = p.extract_text(x_tolerance=1, y_tolerance=3) or ""
                            if enable_tables:
                                try:
                                    for tbl in p.extract_tables():
                                        t += "\n" + "\n".join(["\t".join(r) for r in tbl if r])
                                except Exception:
                                    pass
                            fallback_pages.append(_fix_glyphs(t))
                else:
                    with open(path, "rb") as fh:
                        reader = PdfReader(fh)
                        for page in reader.pages:
                            txt = page.extract_text() or ""
                            fallback_pages.append(_fix_glyphs(txt))
                
                fallback_text = "\n<<<PAGE_BREAK>>>\n".join(fallback_pages)
                fallback_len = len(fallback_text)
                fallback_avg = fallback_len / max(total_pages, 1)
                
                if log_details:
                    logger.info(f"[PDF-EXTRACT] {fallback_extractor} fallback: {fallback_len} chars total, {fallback_avg:.1f} chars/page avg")
                
                # Use whichever extraction method gave more text
                if fallback_len > primary_len:
                    if log_details:
                        logger.info(f"[PDF-EXTRACT] Using {fallback_extractor} result (better coverage)")
                    return fallback_text
                else:
                    if log_details:
                        logger.info(f"[PDF-EXTRACT] Keeping {primary_extractor} result (better coverage)")
                    
            except Exception as fallback_error:
                if log_details:
                    logger.warning(f"[PDF-EXTRACT] {fallback_extractor} fallback failed: {str(fallback_error)}")
        
        # If we have reasonable text, return it
        if primary_len > 0:
            if log_details:
                logger.info(f"[PDF-EXTRACT] Extraction completed successfully: {primary_len} chars")
            return primary_text
        
        # Final fallback to PyMuPDF for problematic PDFs
        if log_details:
            logger.warning(f"[PDF-EXTRACT] Both {primary_extractor} and {fallback_extractor} failed - trying PyMuPDF")
        try:
            text_parts = []
            with fitz.open(path) as doc:
                for page in doc:
                    txt = page.get_text("text")
                    text_parts.append(txt.replace("\u00A0", " "))
            final_text = "\n".join(text_parts)
            if log_details:
                logger.info(f"[PDF-EXTRACT] PyMuPDF fallback successful: {len(final_text)} chars")
            return final_text
        except Exception as e2:
            logger.error(f"[PDF-EXTRACT] All extraction methods failed: {str(e2)}")
            raise ValueError(f"Failed to extract text from PDF: {str(e2)}")

    except Exception as e:
        logger.error(f"[PDF-EXTRACT] Error in PDF extraction: {str(e)}")
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")

def auto_chunk_text(
        text: str,
        max_chunk_size: int = 1200,
        chunk_overlap: int = 200
) -> list[str]:
    """
    Greedy paragraph-based splitter that:
    • never discards small blocks (tables / formulas often look short)
    • yields overlapping chunks to avoid boundary truncation
    """
    # 1. normalise newlines, keep empty-line paragraph breaks
    paragraphs = [p.strip() for p in text.splitlines()]
    # remove consecutive blanks but keep single blank ⇒ paragraph boundary
    clean_paragraphs = []
    for p in paragraphs:
        if p or (clean_paragraphs and clean_paragraphs[-1]):   # collapse >1 blank
            clean_paragraphs.append(p)

    chunks, buff = [], ""
    for para in clean_paragraphs:
        candidate = f"{buff}\n{para}".strip() if buff else para
        if len(candidate) <= max_chunk_size:
            buff = candidate
            continue

        # flush current buffer
        if buff:
            chunks.append(buff)
        # paragraph itself longer than chunk? split hard
        while len(para) > max_chunk_size:
            chunks.append(para[:max_chunk_size])
            para = para[max_chunk_size - chunk_overlap:]
        buff = para

    if buff:
        chunks.append(buff)

    # final sanity: remove dupes that can happen on overlap logic
    dedup = []
    for c in chunks:
        if not dedup or c != dedup[-1]:
            dedup.append(c)
    return dedup

def is_heading(run_or_paragraph) -> bool:
    """Enhanced header detection for DOCX paragraph objects.
    
    Detects headers based on:
    1. Word styles (Heading1, Heading2, etc.)
    2. Text formatting (ALL CAPS short lines)
    3. Common header patterns
    """
    if isinstance(run_or_paragraph, str):
        return is_heading_text(run_or_paragraph)
        
    text = run_or_paragraph.text.strip()
    if not text:
        return False
        
    # Check Word styles
    style = getattr(run_or_paragraph, "style", None)
    if style and style.name.startswith("Heading"):
        return True
        
    return is_heading_text(text)

def is_heading_text(text: str) -> bool:
    """Detect if a string looks like a heading based on content patterns.
    
    Args:
        text: The text to check
        
    Returns:
        bool: True if the text matches heading patterns
    """
    if not text or not isinstance(text, str):
        return False
        
    text = text.strip()
    if not text:
        return False
        
    # Check text formatting
    if text.isupper() and len(text.split()) < 12:
        return True
        
    # Check common header patterns
    header_patterns = [
        r"^(Chapter|Section|Unit|Topic|Table|Figure|\d+\.)",  # Common prefixes
        r"^[A-Z0-9\s\-]{8,}$",  # ALL CAPS with numbers/dashes
        r"^[IVX]+\.",  # Roman numerals
        r"^\d+\.\d+",  # Numbered sections (1.1, 2.3, etc.)
    ]
    
    return any(re.match(pattern, text, re.IGNORECASE) for pattern in header_patterns)

def extract_text_from_docx_python_docx(path: str) -> str:
    """
    Extracts paragraphs *and* tables from a DOCX file.
    • paragraphs       → text as-is
    • tables           → Markdown pipe rows, each cell trimmed
    • list bullets (*) → keep bullet character for header detection
    """
    doc = DocxDocument(path)
    parts = []

    for block in doc.element.body:
        if block.tag.endswith('tbl'):           # it's a table
            tbl = block
            for row in tbl.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr'):
                cells = []
                for cell in row.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc'):
                    txt = ''.join(t.text or '' for t in cell.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
                    cells.append(txt.strip().replace('|', '\\|'))
                if cells:
                    parts.append('| ' + ' | '.join(cells) + ' |')
            parts.append('\n')  # blank line after each table
        else:                                   # it's a paragraph
            texts = block.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
            para = ''.join(t.text or '' for t in texts).strip()
            if para:
                parts.append(para)
    return '\n'.join(parts)


