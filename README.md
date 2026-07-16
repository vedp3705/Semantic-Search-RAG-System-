# Classroom Transcript RAG

Semantic search over bilingual classroom transcripts and gesture annotation spreadsheets. Researchers describe what they're looking for in plain English and get back ranked moments from across all sessions, pulling simultaneously from speech, gesture type, and pedagogical coding data.

Built for an education research lab studying embodied mathematics teaching. The corpus is bilingual (English/Spanish) teacher–student transcripts paired with manually-coded gesture and pedagogical action spreadsheets stored in Box.

---

## What it does

Instead of ctrl+F through a 35-minute transcript, a researcher types something like:

> *"teacher using a hand gesture to make decomposition tangible"*

and gets back the five most relevant moments from every session in the corpus — each showing the spoken text, gesture type, pedagogical code, and action note, deduplicated so results span different classroom episodes rather than flooding from a single minute of class.

Queries work across language. An English query finds Spanish utterances and vice versa because the embedding model handles cross-lingual retrieval natively.

---

## Architecture

```
Box (cloud)
  └── Data/
      └── 30Sept2025_AS/
          ├── transcript.docx   ← speaker turns, bilingual, Key: section defines roles
          └── actions.xlsx      ← gesture annotations + pedagogical codes by timestamp

Ingestion (one-shot per session)
  ├── box_client.py    discovers session folders, fetches files into memory (no disk writes)
  ├── docx_parser.py   reads Key: block → dynamic speaker role map + lesson date
  │                    parses turns + inline Spanish/English translation pairs
  ├── xlsx_parser.py   parses timestamp ranges, gesture types, Round 1/2 codes, notes
  ├── joiner.py        joins actions → turns by timestamp overlap
  │                    embed_text = [speech] [context window] [action synonym expansion]
  └── ingest.py        orchestrates, upserts to ChromaDB, safe to re-run

ChromaDB (local, file-persisted, cosine similarity)

Query (per search)
  ├── search.py        query expansion → embed → retrieve → deduplicate → episode group
  └── FastAPI          POST /search, GET /debug/fields

index.html             single-file frontend, no build step
```

---

## Stack

| | |
|---|---|
| Embeddings | `paraphrase-multilingual-MiniLM-L12-v2` via sentence-transformers |
| Vector store | ChromaDB, local file-persisted |
| Document source | Box SDK Gen (developer token auth) |
| API | FastAPI + Pydantic v2 |
| Parsing | python-docx + openpyxl |
| Frontend | Vanilla HTML/CSS/JS |

No LLM in the query path. Pure vector similarity + metadata filtering keeps latency under 300ms and cost at zero per query.
<!-- 
---

## Setup

```bash
pip install -r requirements.txt

cp .env.example .env
# fill in BOX_ACCESS_TOKEN and BOX_TRANSCRIPT_FOLDER_ID

python ingestion/ingest.py

uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# frontend
python -m http.server 3000
# open localhost:3000/index.html
```

--- -->

## Box folder structure

For a single session the flat layout works:

```
Data/
  transcript.docx
  actions.xlsx
```

For multiple sessions use subfolders — the folder name becomes the session ID and is parsed for date and teacher code automatically:

```
Data/
  30Sept2025_AS/
    transcript.docx
    actions.xlsx
  07Oct2025_KB/
    transcript.docx
    actions.xlsx
```

To ingest one session without touching the others:

```bash
python ingestion/ingest.py 30Sept2025_AS
```

---

## API

**POST /search**

```json
{
  "query": "teacher pointing while asking a question",
  "n_results": 8,
  "filter_speaker_role": "focal_teacher",
  "filter_has_action": true,
  "filter_has_pointing": true,
  "filter_has_representational": false,
  "filter_has_writing": false,
  "group_by_episode": false
}
```

`group_by_episode: true` returns conversational episodes — all turns within a timestamp block grouped together — instead of flat individual chunks.

The response includes `expanded_query` (shows what synonym expansion added to your query) and `warning` (fires when a filter falls back gracefully because the DB was built without that field).

**GET /debug/fields**

Returns the metadata fields stored in the current DB build and a `has_boolean_gesture_fields` flag. Run this after re-indexing to confirm the schema is correct before testing filters.

---

## Design notes

**Why speaker-turn chunking instead of fixed windows**
The natural semantic unit here is a single speaker turn. Sliding window chunking breaks utterances mid-sentence and destroys speaker identity — both are critical for research queries like "focal teacher redirecting student." Short turns under 10 words are merged forward with the next turn from the same speaker to avoid embedding single-word responses as standalone chunks.

**Why speech-first embed ordering**
Early builds put the action metadata prefix before the speech text. A 30-turn timestamp block would all get identical vectors because the shared action prefix dominated the embedding — making the entire episode score identically and flooding results. Putting speech first lets each turn's content shape its own vector distinctively. Action tags follow as a short suffix.

**Why synonym expansion at both index and query time**
Pedagogical codes like "MLR more approachable" are opaque jargon to any embedding model. A query for "making math accessible" would score poorly against chunks tagged MLR without it. The synonym map appended to each chunk's `embed_text` at index time bridges this from the corpus side. Query expansion does the same from the user side — "showing with hands" becomes "showing with hands representational gestures iconic embodied" before embedding.

**Why boolean flags instead of string contains filtering**
ChromaDB's metadata API supports `$eq`, `$ne`, `$in`, `$nin`, and comparators — there is no `$contains`. Storing gesture types as a comma-separated string and attempting substring matching silently returns empty. The fix is to materialise `has_pointing`, `has_representational`, and `has_writing` as individual booleans at index time and filter with `$eq: true`.

**Why dynamic role parsing instead of a hardcoded dict**
Student initials change every class. A hardcoded `SPEAKER_ROLES` dict breaks the moment you add a new session with different students. Every transcript already defines its own cast in the `Key:` block at the top. The parser reads that block and builds the role map at parse time — no config changes needed between sessions.

**Why deduplication over MMR**
Maximal Marginal Relevance requires tuning a similarity threshold and adds a second ranking pass. The simpler approach: after scoring, keep only the highest-scoring chunk per `(transcript_id, timestamp)` pair. This guarantees diversity across episodes without the complexity and is easier to reason about when debugging retrieval.

---

## Repo structure

```
├── config.py
├── .env.example
├── requirements.txt
├── index.html
│
├── ingestion/
│   ├── box_client.py
│   ├── docx_parser.py
│   ├── xlsx_parser.py
│   ├── joiner.py
│   └── ingest.py
│
├── embeddings/
│   └── embedder.py
│
├── vectorstore/
│   └── chroma_store.py
│
├── api/
│   ├── main.py
│   ├── models.py
│   └── search.py
│
└── data/
    └── chroma_db/     ← gitignore this
```
