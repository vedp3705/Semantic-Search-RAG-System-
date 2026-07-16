import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from ingestion.box_client     import list_sessions, fetch_file_bytes
from ingestion.docx_parser    import parse_docx
from ingestion.xlsx_parser    import parse_xlsx
from ingestion.joiner         import join_and_chunk
from embeddings.embedder      import embed_texts
from vectorstore.chroma_store import upsert_chunks, delete_by_transcript


def ingest_session(session: dict):
    sid = session["session_id"]
    print(f"\n{'─'*60}")
    print(f"  Session  : {sid}")

  
    all_turns = []
    effective_date = session["lesson_date"]  

    for f in session["docx_files"]:
        print(f"  [DOCX]   {f['name']}")
        raw = fetch_file_bytes(f["id"])
        turns = parse_docx(raw, sid, session["lesson_date"])
        if turns:
            effective_date = turns[0]["lesson_date"]  
        print(f"           {len(turns)} turns  |  date: {effective_date}")
        all_turns.extend(turns)

    if not all_turns:
        print("  ✗ No turns parsed — skipping session")
        return 0

  
    roster = {}
    for t in all_turns:
        roster.setdefault(t["speaker_code"], t["speaker_role"])
    print(f"  Speakers : {dict(sorted(roster.items()))}")

    
    all_actions = []
    for f in session["xlsx_files"]:
        print(f"  [XLSX]   {f['name']}")
        raw = fetch_file_bytes(f["id"])
        actions = parse_xlsx(raw, sid, effective_date)
        print(f"           {len(actions)} action rows")
        all_actions.extend(actions)

    if not all_actions:
        print("  ⚠  No action spreadsheet — speech-only chunks")

    # ── Join + chunk ───────────────────────────────────────────────────────────
    chunks = join_and_chunk(all_turns, all_actions)
    print(f"  Chunks   : {len(chunks)} total")
    print(f"             {sum(1 for c in chunks if c['has_action'])} with gesture data")
    print(f"             {sum(1 for c in chunks if c['text_en'])} bilingual")

    if not chunks:
        print("  ✗ No chunks — skipping")
        return 0

    # Delete stale chunks for this session, then upsert fresh
    delete_by_transcript(sid)
    embeddings = embed_texts([c["embed_text"] for c in chunks])
    upsert_chunks(chunks, embeddings)
    print(f"  ✓ {len(chunks)} chunks stored")
    return len(chunks)


def ingest_all(filter_session_id: str | None = None):
    sessions = list_sessions(config.BOX_TRANSCRIPT_FOLDER_ID)

    if filter_session_id:
        sessions = [s for s in sessions if s["session_id"] == filter_session_id]
        if not sessions:
            print(f"No session found with ID '{filter_session_id}'")
            sys.exit(1)

    print(f"Found {len(sessions)} session(s) in Box")

    total = 0
    for session in sessions:
        total += ingest_session(session)

    print(f"\n{'═'*60}")
    print(f"Done. {total} total chunks across {len(sessions)} session(s).")


if __name__ == "__main__":
    ingest_all(sys.argv[1] if len(sys.argv) > 1 else None)
