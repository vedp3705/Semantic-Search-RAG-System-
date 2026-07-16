import re
import io
import openpyxl


_TS_RANGE = re.compile(
    r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}[:\-]\d{2})'
)
_PAREN = re.compile(r'\(.*?\)')
_SPEAKER_FROM_NOTE = re.compile(r'^([A-Z]{2})\b')


def _to_secs(ts: str) -> int:
    ts = ts.strip().replace('-', ':')
    parts = ts.split(':')
    return int(parts[0]) * 60 + int(parts[1])


def parse_timestamp_range(raw: str) -> tuple[int, int] | tuple[None, None]:
    """
    Parse timestamp range strings into (start_secs, end_secs).
    Handles: '10:55-11:00', '22:28-22-30', '10:42 (3:42-3:44)', '24:03-24:03'
    """
    if not raw or str(raw).strip() in ('', 'nan', 'None'):
        return None, None

    raw = str(raw).strip()
    raw = _PAREN.sub('', raw).strip()
    raw = raw.replace('–', '-')
    raw = re.sub(r'(\d{1,2}:\d{2})-(\d{1,2})-(\d{2})', r'\1-\2:\3', raw)

    m = _TS_RANGE.search(raw)
    if m:
        return _to_secs(m.group(1)), _to_secs(m.group(2))

    single = re.search(r'\d{1,2}:\d{2}', raw)
    if single:
        s = _to_secs(single.group())
        return s, s + 3

    return None, None



def _extract_speaker(notes: str) -> str | None:
    """Best-effort: 'AS - two different stickies' → 'AS'"""
    if not notes:
        return None
    m = _SPEAKER_FROM_NOTE.match(notes.strip())
    return m.group(1) if m else None



_GESTURE_COLS = {"round 2 codes", "round2 codes", "gesture", "gestures"}
_R1_COLS      = {"round 1 codes", "round1 codes"}
_NOTE_COLS    = {"notes", "note"}
_TS_COLS      = {"time stamp", "timestamp", "time"}


def parse_xlsx(xlsx_bytes: bytes, transcript_id: str, lesson_date: str) -> list[dict]:
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    header_row_idx = 0
    col_map = {}   

    for ridx, row in enumerate(rows[:5]):
        row_lower = [str(c).lower().strip() if c else '' for c in row]
        if any('time' in c or 'round' in c or 'stamp' in c for c in row_lower):
            header_row_idx = ridx
            for cidx, cell in enumerate(row_lower):
                if any(k in cell for k in ['time', 'stamp']):
                    col_map.setdefault('timestamp', []).append(cidx)
                elif 'round 1' in cell or 'round1' in cell:
                    col_map.setdefault('round1', []).append(cidx)
                elif 'round 2' in cell or 'round2' in cell or 'gesture' in cell:
                    col_map.setdefault('gesture', []).append(cidx)
                elif 'note' in cell:
                    col_map.setdefault('notes', []).append(cidx)
            break

    ts_col    = col_map.get('timestamp', [0])[0]
    r1_cols   = col_map.get('round1',    [1])
    r2_cols   = col_map.get('gesture',   [2, 3, 4])
    note_cols = col_map.get('notes',     [5])

    actions = []
    for row in rows[header_row_idx + 1:]:
        raw_ts = row[ts_col] if ts_col < len(row) else None
        start_secs, end_secs = parse_timestamp_range(raw_ts)
        if start_secs is None:
            continue   

        def cell(col): return str(row[col]).strip() if col < len(row) and row[col] else ''

        round1_codes = [cell(c) for c in r1_cols if cell(c) and cell(c) != 'nan']
        gesture_types = [cell(c) for c in r2_cols if cell(c) and cell(c) != 'nan']
        notes = ' '.join(cell(c) for c in note_cols if cell(c) and cell(c) != 'nan')

        speaker = _extract_speaker(notes)

        actions.append({
            "start_secs":    start_secs,
            "end_secs":      end_secs,
            "round1_codes":  round1_codes,
            "gesture_types": gesture_types,
            "notes":         notes,
            "speaker_code":  speaker,
            "transcript_id": transcript_id,
            "lesson_date":   lesson_date,
        })

    return actions
