import re
import uuid

_CLEAN = re.compile(r'\[INA\]|\[.*?\]')

SPEAKER_ROLES = {
    "AS": "focal_teacher", "KB": "focal_teacher",
    "EV": "research_team",
    "AT": "non_focal_teacher", "CV": "non_focal_teacher",
    "EK": "student", "CH": "student", "KH": "student",
    "HC": "student", "GR": "student", "AD": "student",
    "AX": "student", "HL": "student", "BE": "student",
    "YE": "student", "YH": "student", "GA": "student",
    "UK": "unknown_student",
}

CODE_SYNONYMS = {
    "mlr more approachable":       "language routine making math accessible approachable multilingual",
    "ground math":                 "grounding mathematical concepts physical concrete objects",
    "students' contributions":     "eliciting amplifying building on student contributions ideas",
    "students\u2019 contributions":"eliciting amplifying building on student contributions ideas",
    "combination of a, b, and/or c": "multiple combined strategies gestures participation",
    "pointing gestures":           "pointing finger directing deictic gesture attention",
    "representational gestures":   "representational iconic hand motion embodied showing concept",
    "writing gestures":            "writing inscribing recording gesture marking",
}


def _synonyms_for(codes: list[str]) -> str:
    parts = []
    for c in codes:
        syn = CODE_SYNONYMS.get(c.lower().strip())
        if syn:
            parts.append(syn)
    return " ".join(parts)


def _clean(text: str) -> str:
    return _CLEAN.sub('', text or '').strip()


def _ts_to_secs(ts: str) -> int:
    try:
        m, s = ts.split(':')
        return int(m) * 60 + int(s)
    except Exception:
        return 0


def _is_noise(text: str) -> bool:
    cleaned = _clean(text)
    return len(cleaned.split()) <= 1


def join_and_chunk(
    turns: list[dict],
    actions: list[dict],
    context_window: int = 2,
    min_words: int = 10,
) -> list[dict]:


    ts_secs = [_ts_to_secs(t["timestamp"]) for t in turns]

    turn_windows = []
    for i in range(len(turns)):
        start = ts_secs[i]
        end = start + 30  # fallback
        for j in range(i + 1, len(turns)):
            if ts_secs[j] > start:
                end = ts_secs[j]
                break
        turn_windows.append((start, end))

   
    turn_actions: list[list[dict]] = [[] for _ in turns]
    for action in actions:
        a_start = action["start_secs"]
        a_end   = action["end_secs"]
        for i, (t_start, t_end) in enumerate(turn_windows):
            if a_start <= t_end and a_end >= t_start:
                turn_actions[i].append(action)

 
    chunks = []
    i = 0

    while i < len(turns):
        turn = turns[i]
        if _is_noise(turn["text"]):
            i += 1
            continue

        #   merge short same-speaker turns forward
        merged_texts   = [turn["text"]]
        merged_trans   = [turn["translation"]] if turn.get("translation") else []
        merged_actions = list(turn_actions[i])
        has_inaudible  = turn["has_inaudible"]
        end_i = i

        j = i + 1
        while j < len(turns):
            body = _clean(" ".join(merged_trans if merged_trans else merged_texts))
            if len(body.split()) >= min_words:
                break
            nxt = turns[j]
            if nxt["speaker_code"] != turn["speaker_code"] or _is_noise(nxt["text"]):
                break
            merged_texts.append(nxt["text"])
            if nxt.get("translation"):
                merged_trans.append(nxt["translation"])
            merged_actions.extend(turn_actions[j])
            has_inaudible = has_inaudible or nxt["has_inaudible"]
            end_i = j
            j += 1

        primary_text  = " | ".join(merged_texts)
        primary_trans = " | ".join(merged_trans) if merged_trans else None
        embed_body    = _clean(primary_trans if primary_trans else primary_text)

        
        seen = set()
        deduped = []
        for a in merged_actions:
            key = (a["start_secs"], tuple(sorted(a["gesture_types"])))
            if key not in seen:
                seen.add(key)
                deduped.append(a)

        all_gesture_types = list({g for a in deduped for g in a["gesture_types"]})
        all_round1_codes  = list({r for a in deduped for r in a["round1_codes"]})
        all_notes         = " // ".join(a["notes"] for a in deduped if a["notes"])

       
        ctx_parts = []
        for k in range(max(0, len(chunks) - context_window), len(chunks)):
            prev = chunks[k]
            pb = _clean(prev.get("text_en") or prev["text"])[:60]
            ctx_parts.append(f"{prev['speaker_code']}: {pb}")
        ctx_str = " | ".join(ctx_parts)

   
        embed_text = f"{turn['speaker_code']} ({SPEAKER_ROLES.get(turn['speaker_code'], 'unknown')}): {embed_body}"

        if ctx_str:
            embed_text += f" [context: {ctx_str}]"

    
        if deduped:
            action_synonyms = _synonyms_for(all_gesture_types + all_round1_codes)
         
            brief_note = deduped[0]["notes"][:80] if deduped[0]["notes"] else ""
            embed_text += f" [action: {action_synonyms}] [note: {brief_note}]"

        
        has_pointing        = any("pointing"        in g.lower() for g in all_gesture_types)
        has_representational= any("representational" in g.lower() for g in all_gesture_types)
        has_writing         = any("writing"          in g.lower() for g in all_gesture_types)

        chunk = {
            "chunk_id":            str(uuid.uuid4()),
            "speaker_code":        turn["speaker_code"],
            "speaker_role":        SPEAKER_ROLES.get(turn["speaker_code"], "unknown"),
            "timestamp":           turn["timestamp"],
            "text":                primary_text,
            "text_es":             primary_text if primary_trans else None,
            "text_en":             primary_trans,
            "embed_text":          embed_text,
            "transcript_id":       turn["transcript_id"],
            "lesson_date":         turn["lesson_date"],
            "has_inaudible":       has_inaudible,
            "has_action":          bool(deduped),
            "gesture_types":       "|".join(all_gesture_types),
            "round1_codes":        "|".join(all_round1_codes),
            "action_notes":        all_notes,
            "has_pointing":        has_pointing,
            "has_representational":has_representational,
            "has_writing":         has_writing,
            "preceding_speaker":   chunks[-1]["speaker_code"] if chunks else None,
            "preceding_text":      (_clean(chunks[-1].get("text_en") or chunks[-1]["text"])[:120]
                                    if chunks else None),
        }
        chunks.append(chunk)
        i = end_i + 1

    return chunks
