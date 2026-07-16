from sentence_transformers import SentenceTransformer
import config

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(config.EMBED_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_model()
    return model.encode(texts, batch_size=64, show_progress_bar=True).tolist()


def embed_query(text: str) -> list[float]:
    model = get_model()
    return model.encode([text])[0].tolist()
