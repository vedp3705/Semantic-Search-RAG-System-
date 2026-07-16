
import re
from embeddings.embedder      import embed_query
from vectorstore.chroma_store import query as chroma_query
from api.models               import SearchRequest, SearchResponse, TranscriptChunk, EpisodeResult, EpisodeTurn

_EXPANSION: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\bshow\w*\b.{0,40}\b(hands?|fingers?)\b', re.I),
     "representational gestures iconic embodied"),
    (re.compile(r'\b(hands?|fingers?)\b.{0,40}\bshow\w*\b', re.I),
     "representational gestures iconic embodied"),
    (re.compile(r'\b(demonstrat|model\w+|mimic|act\s+out|embodi)\w*\b', re.I),
     "representational gestures iconic embodied"),
    (re.compile(r'\b(hand\s+motion|gesture\w*|chopp|cut\s+gesture)\b', re.I),
     "representational gestures"),
    (re.compile(r'\bpoint\w*\b', re.I),
     "pointing gestures deictic finger directing"),
    (re.compile(r'\b(writ\w+\s+gesture|inscrib|trac\w+\s+on)\b', re.I),
     "writing gestures inscribing"),
    (re.compile(r'\b(access\w+|approachab\w+|scaffold\w*)\b', re.I),
     "MLR more approachable language routine accessible"),
    (re.compile(r'\b(ground\w*|anchor|concrete|physical\s+object)\b', re.I),
     "ground math grounding concrete"),
    (re.compile(r'\b(elicit\w*|participat\w*|contribut\w*|invite\w*)\b', re.I),
     "students contributions eliciting participation"),
    (re.compile(r'\b(multipl\w+|more\s+than\s+one|several|combined?)\s+gesture\b', re.I),
     "combination representational pointing multiple gestures"),
    (re.compile(r'\b(explain\w*|reason\w*|justif\w*)\b', re.I),
     "student explaining reasoning procedural"),
]


def expand_query(query: str) -> str | None:
    additions = []
    for pattern, expansion in _EXPANSION:
        if pattern.search(query) and expansion not in additions:
            additions.append(expansion)
    if additions:
        return query + " " + " ".join(dict.fromkeys(additions))
    return None



def _parse_pipe(val: str) -> list[str]:
    if not val:
        return []
    return [v.strip() for v in val.split("|") if v.strip()]


def _make_chunk(chunk_id: str, meta: dict, distance: float) -> TranscriptChunk:
    return TranscriptChunk(
        chunk_id=            chunk_id,
        speaker_code=        meta["speaker_code"],
        speaker_role=        meta["speaker_role"],
        timestamp=           meta["timestamp"],
        text=                meta.get("text", ""),
        text_es=             meta.get("text_es") or None,
        text_en=             meta.get("text_en") or None,
        display_text=        meta.get("text_en") or meta.get("text") or "",
        transcript_id=       meta["transcript_id"],
        lesson_date=         meta["lesson_date"],
        has_inaudible=       bool(meta.get("has_inaudible", False)),
        has_action=          bool(meta.get("has_action", False)),
        has_pointing=        bool(meta.get("has_pointing", False)),
        has_representational=bool(meta.get("has_representational", False)),
        has_writing=         bool(meta.get("has_writing", False)),
        gesture_types=       _parse_pipe(meta.get("gesture_types", "")),
        round1_codes=        _parse_pipe(meta.get("round1_codes", "")),
        action_notes=        meta.get("action_notes") or None,
        preceding_speaker=   meta.get("preceding_speaker") or None,
        preceding_text=      meta.get("preceding_text") or None,
        similarity_score=    round(1 - distance, 4),
    )


def _deduplicate(chunks: list[TranscriptChunk]) -> list[TranscriptChunk]:
    seen: set[tuple] = set()
    out = []
    for c in chunks:
        key = (c.transcript_id, c.timestamp)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def _group_episodes(chunks: list[TranscriptChunk]) -> list[EpisodeResult]:
    buckets: dict[tuple, list[TranscriptChunk]] = {}
    for c in chunks:
        key = (c.transcript_id, c.timestamp)
        buckets.setdefault(key, []).append(c)

    episodes = []
    for (tid, ts), items in buckets.items():
        items.sort(key=lambda c: c.similarity_score, reverse=True)
        best = items[0].similarity_score
        threshold = best * 0.85
        relevant = [c for c in items if c.similarity_score >= threshold][:10]
        episodes.append(EpisodeResult(
            transcript_id=tid,
            timestamp=ts,
            best_score=best,
            turns=[EpisodeTurn(
                speaker_code=c.speaker_code,
                speaker_role=c.speaker_role,
                text=c.display_text or c.text,
                similarity_score=c.similarity_score,
            ) for c in relevant],
        ))

    return sorted(episodes, key=lambda e: e.best_score, reverse=True)


def _run_query(embedding, n_results: int, where: dict | None) -> dict:
    return chroma_query(embedding, n_results=n_results, where=where)


def search(req: SearchRequest) -> SearchResponse:
    expanded = expand_query(req.query)
    query_text = expanded if expanded else req.query
    embedding = embed_query(query_text)

    filters = []
    if req.filter_speaker_role:
        filters.append({"speaker_role":  {"$eq": req.filter_speaker_role}})
    if req.filter_transcript_id:
        filters.append({"transcript_id": {"$eq": req.filter_transcript_id}})
    if req.filter_lesson_date:
        filters.append({"lesson_date":   {"$eq": req.filter_lesson_date}})
    if req.filter_has_action is not None:
        filters.append({"has_action":    {"$eq": req.filter_has_action}})
    if req.filter_has_pointing is not None:
        filters.append({"has_pointing":  {"$eq": req.filter_has_pointing}})
    if req.filter_has_representational is not None:
        filters.append({"has_representational": {"$eq": req.filter_has_representational}})
    if req.filter_has_writing is not None:
        filters.append({"has_writing":   {"$eq": req.filter_has_writing}})

    where = None
    if len(filters) == 1:
        where = filters[0]
    elif len(filters) > 1:
        where = {"$and": filters}

    fetch_n = req.n_results * 8
    warning = None

    try:
        raw = _run_query(embedding, fetch_n, where)
        if not raw["ids"][0] and where and any(
            k in str(where) for k in ["has_pointing", "has_representational", "has_writing"]
        ):
            raw = _run_query(embedding, fetch_n, None)
            warning = ("Gesture type filter had no matches — the DB may need "
                       "to be rebuilt with the latest chroma_store.py. "
                       "Showing unfiltered results.")
    except Exception as e:
        raw = _run_query(embedding, fetch_n, None)
        warning = f"Filter error ({e}); showing unfiltered results."

    all_chunks = sorted([
        _make_chunk(raw["ids"][0][i], raw["metadatas"][0][i], raw["distances"][0][i])
        for i in range(len(raw["ids"][0]))
    ], key=lambda c: c.similarity_score, reverse=True)

    if req.group_by_episode:
        episodes = _group_episodes(all_chunks)[:req.n_results]
        return SearchResponse(
            query=req.query,
            expanded_query=expanded,
            warning=warning,
            results=[],
            episodes=episodes,
        )

    deduped = _deduplicate(all_chunks)[:req.n_results]
    return SearchResponse(
        query=req.query,
        expanded_query=expanded,
        warning=warning,
        results=deduped,
        episodes=[],
    )
