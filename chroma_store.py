import chromadb
import config

_collection = None


def get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=config.CHROMA_PATH)
        _collection = client.get_or_create_collection(
            name=config.CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _s(val) -> str:
    return str(val) if val is not None else ""


def upsert_chunks(chunks: list[dict], embeddings: list[list[float]]):
    col = get_collection()
    col.upsert(
        ids=[c["chunk_id"] for c in chunks],
        embeddings=embeddings,
        documents=[c["embed_text"] for c in chunks],
        metadatas=[
            {
                "speaker_code":         c["speaker_code"],
                "speaker_role":         c["speaker_role"],
                "timestamp":            c["timestamp"],
                "transcript_id":        c["transcript_id"],
                "lesson_date":          c["lesson_date"],
                "has_inaudible":        bool(c.get("has_inaudible", False)),
                "has_action":           bool(c.get("has_action", False)),
                # Individual boolean flags — reliable $eq filtering
                "has_pointing":         bool(c.get("has_pointing", False)),
                "has_representational": bool(c.get("has_representational", False)),
                "has_writing":          bool(c.get("has_writing", False)),
                # Pipe-delimited strings — deserialize with split("|")
                "gesture_types":        _s(c.get("gesture_types")),
                "round1_codes":         _s(c.get("round1_codes")),
                "action_notes":         _s(c.get("action_notes")),
                "text":                 _s(c.get("text")),
                "text_es":              _s(c.get("text_es")),
                "text_en":              _s(c.get("text_en")),
                "preceding_speaker":    _s(c.get("preceding_speaker")),
                "preceding_text":       _s(c.get("preceding_text")),
            }
            for c in chunks
        ],
    )


def query(
    embedding: list[float],
    n_results: int = 8,
    where: dict | None = None,
) -> dict:
    col = get_collection()
    kwargs = {
        "query_embeddings": [embedding],
        "n_results": n_results,
        "include": ["metadatas", "distances", "documents"],
    }
    if where:
        kwargs["where"] = where
    return col.query(**kwargs)


def delete_by_transcript(transcript_id: str):
    col = get_collection()
    col.delete(where={"transcript_id": {"$eq": transcript_id}})
