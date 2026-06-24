"""Provenance-preserving document chunking."""

from dataclasses import dataclass
import hashlib

from app.knowledge.document_loader import DocumentType, KnowledgeDocument


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    text: str
    ticker: str
    document_type: DocumentType
    title: str
    source: str
    page_number: int
    chunk_index: int


class DocumentChunker:
    """Split page text into overlapping word windows with stable IDs."""

    def __init__(self, chunk_size: int = 250, overlap: int = 40) -> None:
        if chunk_size < 2:
            raise ValueError("chunk_size must be at least 2 words.")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be non-negative and smaller than chunk_size.")
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk(self, document: KnowledgeDocument) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        step = self._chunk_size - self._overlap
        chunk_index = 0
        for page in document.pages:
            words = page.text.split()
            for start in range(0, len(words), step):
                text = " ".join(words[start : start + self._chunk_size])
                if not text:
                    continue
                identity = "|".join(
                    (
                        document.ticker,
                        document.document_type.value,
                        document.source,
                        str(page.page_number),
                        str(chunk_index),
                        text,
                    )
                )
                chunks.append(
                    DocumentChunk(
                        id=hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                        text=text,
                        ticker=document.ticker,
                        document_type=document.document_type,
                        title=document.title,
                        source=document.source,
                        page_number=page.page_number,
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1
                if start + self._chunk_size >= len(words):
                    break
        return chunks
