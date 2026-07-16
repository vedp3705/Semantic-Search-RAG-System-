import os
from dotenv import load_dotenv

load_dotenv()

BOX_ACCESS_TOKEN          = os.getenv("BOX_ACCESS_TOKEN")
BOX_TRANSCRIPT_FOLDER_ID  = os.getenv("BOX_TRANSCRIPT_FOLDER_ID")

BOX_TRANSCRIPT_ID  = os.getenv("BOX_TRANSCRIPT_ID", "transcript")
BOX_LESSON_DATE    = os.getenv("BOX_LESSON_DATE",   "unknown")
BOX_TEACHER_CODE   = os.getenv("BOX_TEACHER_CODE",  "unknown")

CHROMA_PATH        = os.getenv("CHROMA_PATH", "./data/chroma_db")
CHROMA_COLLECTION  = "transcripts"
EMBED_MODEL        = os.getenv("EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
