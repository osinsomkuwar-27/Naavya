"""
asr/transcribe.py
Owner: Soham

Speech-to-text for NeoTriage. Converts a mother's voice (WhatsApp voice
note or browser mic recording) into plain text, which then feeds into
agents/intake/intake_agent.py.

PoC backend: OpenAI Whisper (local, free, works offline once installed).
Extension path: swap in AI4Bharat's IndicWhisper/Conformer models for
better accuracy on Indian regional languages/dialects -- see
_load_model() for the swap point.

Design notes:
- Kept as a thin, swappable wrapper on purpose. transcribe() is the only
  function the rest of the pipeline should ever call -- webhook.py and
  routes/assess.py both depend only on this function signature, not on
  Whisper internals. That means swapping ASR backends later never
  touches calling code.
- Accepts either a file path or raw bytes, since WhatsApp gives you a
  downloaded file on disk, but a browser mic recording usually arrives
  as an in-memory blob/bytes over the API.
"""

import io
import os
import tempfile
from dataclasses import dataclass
from typing import Optional, Union

# Model is loaded lazily so importing this module doesn't force a slow
# model load (useful for tests / other agents importing shared types).
_MODEL = None
_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")


@dataclass
class TranscriptionResult:
    text: str
    language: Optional[str] = None
    confidence: Optional[float] = None  # avg logprob-derived, 0-1 rough proxy
    raw_backend: str = "whisper"


class TranscriptionError(Exception):
    pass


def _load_model():
    """Lazy-load Whisper so this module can be imported without the
    dependency being installed yet (e.g. during early scaffolding)."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    try:
        import whisper  # openai-whisper package
    except ImportError as e:
        raise TranscriptionError(
            "openai-whisper is not installed. Run: "
            "pip install openai-whisper --break-system-packages"
        ) from e

    _MODEL = whisper.load_model(_MODEL_SIZE)
    return _MODEL


def transcribe(
    audio: Union[str, bytes],
    language_hint: Optional[str] = None,
) -> TranscriptionResult:
    """
    Transcribe audio to text.

    Args:
        audio: either a filesystem path (str) to an audio file, or raw
            audio bytes (e.g. from a WhatsApp media download or a
            browser-recorded blob).
        language_hint: optional ISO code (e.g. "hi" for Hindi, "mr" for
            Marathi) if the caller already knows the target language --
            e.g. from the WhatsApp sender's registered locale, or a
            language picker on the web PoC. If None, Whisper
            auto-detects, which is slower and less reliable on
            dialect-heavy speech.

    Returns:
        TranscriptionResult with the transcribed text.

    Raises:
        TranscriptionError if transcription fails for any reason --
        callers (webhook.py, routes/assess.py) should catch this and
        return a graceful "please try again / speak clearly" voice
        prompt rather than crashing the request.
    """
    model = _load_model()
    tmp_path = None

    try:
        if isinstance(audio, bytes):
            # Whisper's CLI/model wrapper expects a file path, so write
            # bytes to a temp file first.
            tmp = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False)
            tmp.write(audio)
            tmp.close()
            tmp_path = tmp.name
            audio_path = tmp_path
        else:
            audio_path = audio

        options = {}
        if language_hint:
            options["language"] = language_hint

        result = model.transcribe(audio_path, **options)

        text = (result.get("text") or "").strip()
        if not text:
            raise TranscriptionError("Transcription returned empty text.")

        return TranscriptionResult(
            text=text,
            language=result.get("language"),
            raw_backend="whisper",
        )

    except TranscriptionError:
        raise
    except Exception as e:
        raise TranscriptionError(f"Transcription failed: {e}") from e

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    # Manual smoke test: point this at a sample clip before demo day.
    # python asr/transcribe.py path/to/sample_clip.ogg
    import sys

    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <path_to_audio_file> [language_hint]")
        sys.exit(1)

    path = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        out = transcribe(path, language_hint=lang)
        print(f"Detected language: {out.language}")
        print(f"Transcript: {out.text}")
    except TranscriptionError as e:
        print(f"ERROR: {e}")