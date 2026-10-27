"""Local file extraction. Files are read locally and are never uploaded to a cloud API."""
from pathlib import Path
import base64

TEXT_EXTS={'.txt','.md','.py','.js','.ts','.tsx','.jsx','.html','.css','.json','.xml','.yaml','.yml','.toml','.ini','.cfg','.log','.csv','.sql','.c','.cpp','.h','.hpp','.java','.rs','.go','.sh','.bat','.ps1','.tex'}
MAX_TEXT_CHARS=90_000

def extract_file(path: str) -> tuple[str, list[str]]:
    p=Path(path); ext=p.suffix.lower()
    if not p.exists(): raise FileNotFoundError(path)
    if ext in TEXT_EXTS:
        text=p.read_text(encoding='utf-8',errors='replace')[:MAX_TEXT_CHARS]
        return f"[FILE: {p.name}]\n{text}", []
    if ext=='.pdf':
        from pypdf import PdfReader
        reader=PdfReader(str(p)); chunks=[]
        for i,page in enumerate(reader.pages[:100]):
            chunks.append(f"[Page {i+1}]\n{page.extract_text() or ''}")
        return f"[PDF: {p.name}]\n"+'\n\n'.join(chunks)[:MAX_TEXT_CHARS], []
    if ext=='.docx':
        from docx import Document
        doc=Document(str(p)); lines=[x.text for x in doc.paragraphs if x.text.strip()]
        for table in doc.tables:
            for row in table.rows: lines.append(' | '.join(cell.text for cell in row.cells))
        return f"[DOCX: {p.name}]\n"+'\n'.join(lines)[:MAX_TEXT_CHARS], []
    if ext in {'.png','.jpg','.jpeg','.webp','.bmp'}:
        data=base64.b64encode(p.read_bytes()).decode('ascii')
        return f"[IMAGE ATTACHED: {p.name}] Please inspect the attached image.", [data]
    raise ValueError(f"Unsupported file type: {ext}. Supported: text/code, PDF, DOCX and common images.")
