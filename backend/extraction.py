"""Bounded, page-aware PDF/DOCX/TXT extraction. No model downloads."""
from io import BytesIO
from pathlib import Path
import zipfile
from pypdf import PdfReader
from docx import Document
from docx.text.paragraph import Paragraph

MAX_BYTES = 10 * 1024 * 1024
MAX_CHARS = 200_000
MAX_CHUNKS = 400
ALLOWED = {'.pdf', '.docx', '.txt'}


def extract(data: bytes, filename: str) -> list[dict]:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED:
        raise ValueError('Upload a PDF, Word .docx, or UTF-8 .txt file.')
    if not data or len(data) > MAX_BYTES:
        raise ValueError('Use a non-empty file no larger than 10 MB.')
    pages = []
    if ext == '.pdf':
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(''):
            raise ValueError('Password-protected PDFs are not supported.')
        if len(reader.pages) > 100:
            raise ValueError('Split PDFs longer than 100 pages.')
        for n, page in enumerate(reader.pages, 1):
            text = (page.extract_text() or '').strip()
            if not text:
                raise ValueError(f'Page {n} needs OCR. Upload a text-based PDF; scanned pages are not supported yet.')
            pages.append((n, text))
            if sum(len(t) for _, t in pages) > MAX_CHARS:
                raise ValueError('Split documents containing more than 200,000 characters.')
    elif ext == '.docx':
        with zipfile.ZipFile(BytesIO(data)) as archive:
            files = archive.infolist()
            if len(files) > 2048 or sum(f.file_size for f in files) > 32 * 1024 * 1024:
                raise ValueError('The Word document is too large after decompression.')
            if 'word/document.xml' not in archive.namelist():
                raise ValueError('Invalid Word document.')
        doc = Document(BytesIO(data))
        parts = []
        for block in doc.iter_inner_content():
            if isinstance(block, Paragraph):
                parts.append(block.text)
            else:
                parts.extend(' | '.join(cell.text for cell in row.cells) for row in block.rows)
        pages = [(0, '\n'.join(parts))]
    else:
        pages = [(0, data.decode('utf-8-sig'))]
    if sum(len(t) for _, t in pages) > MAX_CHARS:
        raise ValueError('Split documents containing more than 200,000 characters.')
    chunks = []
    for page, text in pages:
        text = text.replace('\x00', '').strip()
        start = 0
        while start < len(text):
            end = min(start + 1200, len(text))
            chunks.append({'page_number': page, 'content': text[start:end]})
            if len(chunks) > MAX_CHUNKS:
                raise ValueError('Split this document into smaller files.')
            if end == len(text):
                break
            start = end - 150
    if not chunks:
        raise ValueError('No readable text found in this document.')
    return chunks
