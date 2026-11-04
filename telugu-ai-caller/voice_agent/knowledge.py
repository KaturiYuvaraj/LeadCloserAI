"""
Knowledge base for live calls.

Sources, in order:
  1. the company profile (services, pricing, pitch) — already in the sales prompt,
  2. the AI employee's "knowledge_base" text from the employee builder,
  3. documents uploaded to that employee (PDF, Word, Excel, CSV, TXT, MD), stored as
     extracted text in employee.variables["knowledge_docs"].

Small knowledge bases go into the system prompt whole. Larger ones put the first
part in the prompt and, for every caller message, add the best-matching passages
next to it (simple word-overlap ranking: fast, no extra API call, no embeddings).
"""

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

PROMPT_CHARS = 8000             # knowledge placed directly in the system prompt
CHUNK_CHARS = 700
SNIPPET_CHARS = 1400            # per caller message, for knowledge beyond the prompt part
MAX_DOC_CHARS = 200_000
ALLOWED_SUFFIXES = {".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md"}

_WORD = re.compile(r"\w+", re.UNICODE)
_STOP = {"the", "and", "for", "you", "your", "are", "with", "what", "how", "can", "this", "that", "have",
         "our", "about", "will", "from", "does", "please", "tell", "much", "there"}


def extract_text(filename: str, data: bytes) -> str:
    """Plain text from an uploaded document. Raises ValueError for unsupported or unreadable files."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"Unsupported file type '{suffix}'. Use PDF, Word, Excel, CSV, TXT or MD.")
    try:
        if suffix == ".pdf":
            from pypdf import PdfReader
            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
        elif suffix == ".docx":
            import docx
            document = docx.Document(io.BytesIO(data))
            parts = [p.text for p in document.paragraphs]
            for table in document.tables:
                parts.extend(" | ".join(cell.text for cell in row.cells) for row in table.rows)
            text = "\n".join(parts)
        elif suffix == ".xlsx":
            from openpyxl import load_workbook
            book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            rows = []
            for sheet in book.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    cells = [str(c) for c in row if c not in (None, "")]
                    if cells:
                        rows.append(" | ".join(cells))
            text = "\n".join(rows)
        elif suffix == ".csv":
            reader = csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace")))
            text = "\n".join(" | ".join(c for c in row if c) for row in reader if any(row))
        else:
            text = data.decode("utf-8-sig", errors="replace")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Could not read {filename}: {e}") from e
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise ValueError(f"No text found in {filename} (scanned PDFs need OCR first).")
    return text[:MAX_DOC_CHARS]


def _tokens(text: str) -> set:
    return {w for w in (m.group(0).lower() for m in _WORD.finditer(text or "")) if len(w) > 2 and w not in _STOP}


def _chunks(text: str) -> List[str]:
    """Split on paragraphs, packing them into ~CHUNK_CHARS pieces."""
    out, current = [], ""
    for para in re.split(r"\n\s*\n|\n", text):
        para = para.strip()
        if not para:
            continue
        if current and len(current) + len(para) + 1 > CHUNK_CHARS:
            out.append(current)
            current = ""
        current = f"{current}\n{para}" if current else para
        while len(current) > CHUNK_CHARS * 2:
            out.append(current[:CHUNK_CHARS])
            current = current[CHUNK_CHARS:]
    if current:
        out.append(current)
    return out


@dataclass
class KnowledgeBase:
    sections: List[Dict[str, str]] = field(default_factory=list)  # {"title", "text"}

    @classmethod
    def for_employee(cls, employee: Optional[Dict[str, Any]], docs: Optional[List[Dict[str, Any]]] = None) -> "KnowledgeBase":
        sections = []
        if employee and (employee.get("knowledge_base") or "").strip():
            sections.append({"title": "Key facts", "text": employee["knowledge_base"].strip()})
        for doc in docs or []:
            if (doc.get("text") or "").strip():
                sections.append({"title": doc.get("name") or "Document", "text": doc["text"].strip()})
        return cls(sections)

    @property
    def full_text(self) -> str:
        return "\n\n".join(f"## {s['title']}\n{s['text']}" for s in self.sections)

    @property
    def is_empty(self) -> bool:
        return not self.sections

    def prompt_section(self) -> str:
        if self.is_empty:
            return ""
        text = self.full_text
        more = ""
        if len(text) > PROMPT_CHARS:
            text = text[:PROMPT_CHARS]
            more = "\n(More passages are added next to the customer's message when relevant.)"
        return (
            "\nCOMPANY KNOWLEDGE (answer factual questions only from this; if the answer is not here, "
            "say you will confirm with the team and send it on WhatsApp — never guess):\n"
            f"{text}{more}\n"
        )

    def _overflow_chunks(self) -> List[str]:
        if not hasattr(self, "_overflow"):
            text = self.full_text
            self._overflow = _chunks(text[PROMPT_CHARS:]) if len(text) > PROMPT_CHARS else []
            self._overflow_tokens = [_tokens(c) for c in self._overflow]
        return self._overflow

    def relevant(self, query: str, min_overlap: int = 2) -> Optional[str]:
        """Best passages beyond the prompt part for this caller message, or None."""
        chunks = self._overflow_chunks()
        if not chunks:
            return None
        q = _tokens(query)
        if not q:
            return None
        scored = sorted(((len(q & toks), i) for i, toks in enumerate(self._overflow_tokens)), reverse=True)
        picked, size = [], 0
        for score, i in scored:
            if score < min_overlap:
                break
            if size + len(chunks[i]) > SNIPPET_CHARS:
                continue
            picked.append(chunks[i])
            size += len(chunks[i])
        if not picked:
            return None
        return "Relevant company knowledge: " + " … ".join(p.replace("\n", " ") for p in picked)


# ----------------------------------------------------------------------------- storage

def _employee(session, employee_id: int):
    from models import Employee
    return session.get(Employee, employee_id)


def list_docs(employee_id: int, with_text: bool = False) -> Optional[List[Dict[str, Any]]]:
    """Documents uploaded to an AI employee (None if the employee does not exist)."""
    from core.db import SessionLocal
    session = SessionLocal()
    try:
        employee = _employee(session, employee_id)
        if not employee:
            return None
        docs = list((employee.variables or {}).get("knowledge_docs") or [])
        if with_text:
            return docs
        return [{"index": i, "name": d.get("name"), "chars": len(d.get("text") or ""), "added_at": d.get("added_at")}
                for i, d in enumerate(docs)]
    finally:
        session.close()


def add_doc(employee_id: int, name: str, text: str) -> Optional[Dict[str, Any]]:
    from datetime import datetime
    from core.db import SessionLocal
    session = SessionLocal()
    try:
        employee = _employee(session, employee_id)
        if not employee:
            return None
        variables = dict(employee.variables or {})
        docs = [d for d in (variables.get("knowledge_docs") or []) if d.get("name") != name]  # re-upload replaces
        docs.append({"name": name, "text": text, "added_at": datetime.now().isoformat(timespec="seconds")})
        variables["knowledge_docs"] = docs
        employee.variables = variables
        session.commit()
        return {"name": name, "chars": len(text), "documents": len(docs)}
    finally:
        session.close()


def delete_doc(employee_id: int, index: int) -> bool:
    from core.db import SessionLocal
    session = SessionLocal()
    try:
        employee = _employee(session, employee_id)
        if not employee:
            return False
        variables = dict(employee.variables or {})
        docs = list(variables.get("knowledge_docs") or [])
        if not 0 <= index < len(docs):
            return False
        docs.pop(index)
        variables["knowledge_docs"] = docs
        employee.variables = variables
        session.commit()
        return True
    finally:
        session.close()
