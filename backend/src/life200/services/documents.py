"""Turn the Markdown drafts into Word files, and read text out of uploaded documents."""

import html
import io
import re
import zipfile
from dataclasses import dataclass

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


# Formats read locally. Images and scanned PDFs have no text layer, so the AI reads them.
TEXT_TYPES = ["pdf", "docx", "odt", "rtf", "txt", "md", "html", "htm"]
IMAGE_TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
ALL_TYPES = [*TEXT_TYPES, *IMAGE_TYPES]
MIN_TEXT = 200  # fewer characters than this from a PDF means it is probably a scan


class UnsupportedDocumentError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DocumentText:
    text: str  # what we could read locally ("" for images and scans)
    needs_ai_reading: bool  # True: send the file itself to the AI to transcribe
    mime: str


def read_document(filename: str, data: bytes) -> DocumentText:
    ext = filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""
    if ext in IMAGE_TYPES:
        return DocumentText("", True, IMAGE_TYPES[ext])
    if ext == "pdf":
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
        return DocumentText(text, len(text.strip()) < MIN_TEXT, "application/pdf")
    if ext == "docx":
        return DocumentText(_docx_text(data), False, "text/plain")
    if ext == "odt":
        return DocumentText(_odt_text(data), False, "text/plain")
    if ext == "rtf":
        return DocumentText(_rtf_text(data.decode("latin-1")), False, "text/plain")
    if ext in ("html", "htm"):
        return DocumentText(_html_text(data.decode("utf-8", errors="replace")), False, "text/plain")
    if ext in ("txt", "md"):
        return DocumentText(data.decode("utf-8", errors="replace"), False, "text/plain")
    raise UnsupportedDocumentError(
        f"cannot read .{ext or '?'} files; use PDF, Word, OpenDocument, RTF, text or an image"
    )


def read_cv(filename: str, data: bytes) -> str:
    """Text of a document (kept for callers that only need text)."""
    return read_document(filename, data).text


def _docx_text(data: bytes) -> str:
    """Paragraphs and table cells in document order (many CV templates use tables)."""
    doc = Document(io.BytesIO(data))
    lines: list[str] = []
    for block in doc.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            lines.append("".join(t.text or "" for t in block.iter() if t.tag.endswith("}t")))
        elif tag == "tbl":
            for row in block.iter():
                if row.tag.endswith("}tr"):
                    cells = [
                        "".join(t.text or "" for t in cell.iter() if t.tag.endswith("}t"))
                        for cell in row
                        if cell.tag.endswith("}tc")
                    ]
                    lines.append(" | ".join(c for c in cells if c.strip()))
    return "\n".join(line for line in lines if line.strip())


def _odt_text(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("content.xml").decode("utf-8")
    xml = re.sub(r"</text:(p|h)>|<text:line-break/>", "\n", xml)
    return html.unescape(re.sub(r"<[^>]+>", "", xml))


def _rtf_text(rtf: str) -> str:
    rtf = re.sub(r"\\par[d]?\b", "\n", rtf)
    rtf = re.sub(r"\\'([0-9a-f]{2})", lambda m: bytes.fromhex(m.group(1)).decode("latin-1"), rtf)
    rtf = re.sub(r"\\[a-z]+-?\d* ?|[{}]", "", rtf)
    return "\n".join(line.strip() for line in rtf.splitlines() if line.strip())


def _html_text(page: str) -> str:
    page = re.sub(r"(?is)<(script|style).*?</\1>", "", page)
    page = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6]|tr)>", "\n", page)
    return html.unescape(re.sub(r"<[^>]+>", "", page))
