# Knowledge Layer (Documents and Retrieval)

## Lifecycle

1. **Acquire:** multipart upload (`POST /api/documents`) or SEC EDGAR import
   (`POST /api/documents/import-sec`).
2. **Validate:** size is enforced while streaming (15 MB uploads, 20 MB
   filings). The type is decided by content (`%PDF-` magic bytes), not the
   extension. Empty, binary-as-text, encrypted, or oversized (>600 pages)
   inputs are rejected. Duplicates (same SHA-256 per user) return 409.
3. **Parse:** `pypdf` page by page (1-based page numbers kept); UTF-8 text;
   HTML via the stdlib parser with scripts/styles stripped, split into
   3,000-word pseudo-pages. Scanned PDFs without a text layer are reported as
   unreadable. ARGUS does not perform OCR.
4. **Chunk:** 180-word windows with 30-word overlap that never cross pages.
   Chunk ids are a hash of owner, document, page, position, and text
   (idempotent re-ingestion).
5. **Embed:** local ONNX all-MiniLM-L6-v2 via Chroma (free, about 80 MB
   downloaded once). ARGUS downloads the model itself
   (`app/knowledge/model_cache.py`): resumable Range requests, long timeouts,
   retries, SHA-256 verification, and safe extraction. It runs in a background
   thread at startup, or manually with `python -m app.knowledge.model_cache`.
   Chroma's own downloader (short timeout, no resume) is never used: until the
   model is present, embedding fails fast with `embedding_model_unavailable`,
   and `/api/system/status` reports the download progress.
   `ARGUS_EMBEDDING_PROVIDER=hash` is a no-download, purely lexical alternative
   for tests and slow networks. Each provider has its own Chroma collection
   (`argus_knowledge_minilm` or `argus_knowledge_hash256`), because vectors from
   different models are not comparable. Switching providers therefore requires
   re-uploading documents.
6. **Index:** ChromaDB persistent collection with metadata `owner_id`,
   `document_id`, `ticker`, `document_type`, `title`, `source`, `page_number`,
   `chunk_index`, `published_on`.
7. **Retrieve:** dense top-`k×5` filtered by `owner_id` (and ticker, type, and
   ready document ids) inside Chroma, then reranked as
   `0.75 · cosine + 0.25 · keyword coverage`. Near-duplicates are removed, at most
   two chunks are kept per document, and results below `min_score` (0.15) are
   dropped, so weak matches become "insufficient evidence" rather than fake support.
8. **Cite:** each passage becomes a `D` evidence item with document id, page,
   chunk id, and score. `GET /api/documents/{id}/file` serves the original
   (PDFs open at `#page=N`), with `Content-Security-Policy: sandbox`.

## Why these choices

* **ChromaDB** was already in the project, runs embedded with no server, and
  supports metadata filters. A dedicated vector database would add operations
  cost without a measured need.
* **Hybrid rerank instead of a cross-encoder:** keyword coverage fixes the
  common dense-retrieval miss on exact financial terms (e.g. "export controls")
  at near-zero cost. A cross-encoder reranker would be the next step if an
  evaluation showed a need.
* **Small chunks** keep citations precise. Page boundaries are never crossed,
  so every citation resolves to exactly one page.

## Consistency with the relational database

The `documents` row is the authority. Upload: row `processing` → parse (failure
deletes the row, 422) → store the file → index → row `ready`. If storing or
indexing fails, partial chunks, the file, and the row are all removed (503), so
retrying is a plain re-upload rather than a "duplicate" error. Delete: chunks first, then the
row and the file; if Chroma is unavailable the row is kept so the delete can be
retried.

## Security

Document text is untrusted. It is stored and quoted, never executed or
followed. Source URLs are recorded as provenance only, and ARGUS never fetches
user-supplied URLs (no SSRF surface). SEC requests go only to fixed SEC hosts,
with accession numbers and document names validated against strict patterns.
