from pydantic import BaseModel
from typing import Optional


class SearchRequest(BaseModel):
    query: str
    n_results: int = 8
    filter_speaker_role:         Optional[str]  = None
    filter_transcript_id:        Optional[str]  = None
    filter_lesson_date:          Optional[str]  = None
    filter_has_action:           Optional[bool] = None
    filter_has_pointing:         Optional[bool] = None
    filter_has_representational: Optional[bool] = None
    filter_has_writing:          Optional[bool] = None
    group_by_episode:            bool           = False


class TranscriptChunk(BaseModel):
    chunk_id:             str
    speaker_code:         str
    speaker_role:         str
    timestamp:            str
    text:                 str
    text_es:              Optional[str] = None
    text_en:              Optional[str] = None
    display_text:         str
    transcript_id:        str
    lesson_date:          str
    has_inaudible:        bool = False
    has_action:           bool = False
    has_pointing:         bool = False
    has_representational: bool = False
    has_writing:          bool = False
    gesture_types:        list[str] = []
    round1_codes:         list[str] = []
    action_notes:         Optional[str] = None
    preceding_speaker:    Optional[str] = None
    preceding_text:       Optional[str] = None
    similarity_score:     float


class EpisodeTurn(BaseModel):
    speaker_code:     str
    speaker_role:     str
    text:             str
    similarity_score: float


class EpisodeResult(BaseModel):
    transcript_id: str
    timestamp:     str
    best_score:    float
    turns:         list[EpisodeTurn]


class SearchResponse(BaseModel):
    query:          str
    expanded_query: Optional[str]        = None
    warning:        Optional[str]        = None   # surfaced when filter fallback fires
    results:        list[TranscriptChunk]
    episodes:       list[EpisodeResult]
