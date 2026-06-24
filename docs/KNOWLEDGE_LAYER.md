# ARGUS Knowledge Layer

## Purpose

The Knowledge Layer retrieves evidence from company disclosures so research
agents can combine quantitative behavior with management statements, risk
factors, operating context, and reported events. It is a retrieval subsystem,
not a chatbot and not a replacement for the Quant Engine.

## Architecture

```text
10-K / 10-Q / annual report / earnings call / investor presentation
    -> DocumentLoader
    -> DocumentChunker
    -> EmbeddingProvider
    -> ChromaVectorStore
    -> KnowledgeRetriever
    -> MarketAgent / RiskAgent / NewsAgent / StrategyAgent
    -> document insights + source citations
```

## Ingestion

`DocumentLoader.load_pdf` extracts text page by page with pypdf. Page numbers,
document type, ticker, title, and source are retained. Image-only PDFs are rejected
with an explicit OCR-required error rather than silently producing empty context.
Earnings-call transcripts and other text sources use `load_text`.

Supported document types are:

- `10-K`
- `10-Q`
- `annual_report`
- `earnings_call`
- `investor_presentation`

Example:

```python
import asyncio

from app.dependencies.knowledge import get_knowledge_retriever
from app.knowledge.document_loader import DocumentLoader, DocumentType

document = DocumentLoader().load_pdf(
    "documents/nvda-10k.pdf",
    ticker="NVDA",
    document_type=DocumentType.TEN_K,
    source="https://www.sec.gov/...",
)
asyncio.run(get_knowledge_retriever().ingest(document))
```

## Chunking

Documents are split into overlapping word windows. Overlap preserves context near
boundaries. Stable SHA-256 IDs make repeated ingestion idempotent through Chroma
upserts. Chunks never cross page boundaries, keeping citations meaningful.

## Embeddings

Production wiring uses Chroma's local ONNX MiniLM default embedding function.
The first semantic query may download its model. Tests inject a deterministic
hash embedding, so CI remains offline and repeatable. The embedding interface can
later accept a different local or hosted model without changing agents or Chroma.

## Vector storage

Chroma persists embeddings in the configured `argus_knowledge` collection. Every
record stores ticker, document type, title, source, page, and chunk index. Queries
are filtered by normalized ticker before evidence reaches an agent.

Environment settings use the `ARGUS_` prefix:

- `ARGUS_KNOWLEDGE_CHROMA_PATH`
- `ARGUS_KNOWLEDGE_COLLECTION_NAME`
- `ARGUS_KNOWLEDGE_CHUNK_SIZE`
- `ARGUS_KNOWLEDGE_CHUNK_OVERLAP`
- `ARGUS_KNOWLEDGE_RETRIEVAL_LIMIT`

## Agent integration

Each specialist asks a different retrieval question:

- Market: revenue, demand, performance, and guidance
- Risk: disclosed risk factors, regulation, competition, liquidity, supply chain
- News: earnings events, guidance, and outlook
- Strategy: advantages, opportunities, allocation, and strategic outlook

Agents use extractive snippets and return structured citations. Strategy still
depends on Market, Risk, and News outputs; retrieval does not bypass that graph.
When no documents exist, research continues with empty document context.

## Research response

`POST /research` retains existing summaries and scenarios and adds:

- `document_insights`: deduplicated retrieved excerpts
- `sources`: title, type, source, page, chunk ID, and similarity score

This keeps narrative output separate from auditable evidence.

## Limitations

- pypdf does not perform OCR for scanned documents.
- Retrieval relevance is not proof that a statement is current or correct.
- Tables and multi-column PDFs may extract imperfectly.
- Similarity score is ranking evidence, not confidence or truth probability.
- Filing access and licensing remain the caller's responsibility.
- This phase does not fetch SEC filings automatically; it ingests supplied files.

## Common mistakes

- Embedding an entire filing as one chunk
- Dropping page and source metadata
- Mixing documents from different tickers in retrieval
- Treating retrieval score as factual confidence
- Allowing agents to cite text that was not retrieved
- Hiding the no-document case by generating plausible context
- Re-ingesting with random IDs and creating duplicates
- Running blocking PDF or vector operations on the event loop

## Knowledge check

1. Why must chunks retain page-level provenance?
2. Why does overlap improve retrieval near chunk boundaries?
3. What is the difference between embedding similarity and factual confidence?
4. Why are stable chunk IDs important?
5. Why should RiskAgent and MarketAgent use different retrieval queries?
6. What should happen when a ticker has no indexed documents?
