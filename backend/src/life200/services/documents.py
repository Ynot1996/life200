"""Turn the Markdown drafts into Word files, and read text out of an uploaded CV."""

import io
import re

from docx import Document
from pypdf import PdfReader

_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")


def markdown_to_docx(markdown: str) -> bytes:
    doc = Document()
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)", line)
        bullet = re.match(r"^\s*[-*•]\s+(.*)", line)
        if heading:
            doc.add_heading(_plain(heading.group(2)), level=len(heading.group(1)))
        elif bullet:
            _add_runs(doc.add_paragraph(style="List Bullet"), bullet.group(1))
        else:
            _add_runs(doc.add_paragraph(), line)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _plain(text: str) -> str:
    return _BOLD.sub(lambda m: m.group(1) or m.group(2), text).replace("*", "")


def _add_runs(paragraph, text: str) -> None:  # type: ignore[no-untyped-def]
    pos = 0
    for m in _BOLD.finditer(text):
        paragraph.add_run(text[pos : m.start()].replace("*", ""))
        paragraph.add_run(m.group(1) or m.group(2)).bold = True
        pos = m.end()
    paragraph.add_run(text[pos:].replace("*", ""))


def read_cv(filename: str, data: bytes) -> str:
    """Text of an uploaded PDF, Word or text file."""
    name = filename.casefold()
    if name.endswith(".pdf"):
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
    if name.endswith(".docx"):
        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    return data.decode("utf-8", errors="replace")
