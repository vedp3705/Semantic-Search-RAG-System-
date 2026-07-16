from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.models import SearchRequest, SearchResponse
from api.search import search

app = FastAPI(title="Transcript RAG", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/search", response_model=SearchResponse)
def search_endpoint(req: SearchRequest):
    return search(req)


@app.get("/debug/fields")
def debug_fields():
    from vectorstore.chroma_store import get_collection
    col = get_collection()
    result = col.get(limit=10, include=["metadatas"])
    if not result["metadatas"]:
        return {"error": "No chunks found in DB"}
    sample = result["metadatas"][0]
    all_keys = set()
    for m in result["metadatas"]:
        all_keys.update(m.keys())
    return {
        "total_chunks": col.count(),
        "fields_present": sorted(all_keys),
        "sample_chunk": sample,
        "has_boolean_gesture_fields": all(
            k in all_keys for k in ["has_pointing", "has_representational", "has_writing"]
        ),
    }
