from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import hashlib
import time


SUPPORTED_LANGUAGES = {
    "hi": "Hindi",
    "or": "Odia",
    "kn": "Kannada",
    "bho": "Bhojpuri",
    "en": "English",
}


@dataclass
class TTSResult:
    success: bool
    audio_path: Optional[str] = None
    language: str = "en"
    duration_estimate_sec: Optional[float] = None
    error: Optional[str] = None


class TTSBackend(ABC):
    """Common interface so any real TTS provider can be dropped in
    without changing synthesize_reply()."""

    @abstractmethod
    def synthesize(self, text: str, language: str, output_path: str) -> TTSResult:
        ...


class MockTTSBackend(TTSBackend):
    """
    Offline stand-in used for development/testing before a real TTS
    model is wired in. Writes a small placeholder file (not real audio)
    so the rest of the pipeline — file paths, playback wiring in the
    web demo — can be built and tested end-to-end right now.
    """

    def synthesize(self, text: str, language: str, output_path: str) -> TTSResult:
        if language not in SUPPORTED_LANGUAGES:
            return TTSResult(success=False, error=f"Unsupported language: {language}")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"[MOCK AUDIO PLACEHOLDER]\nlanguage={language}\ntext={text}\n")

        # crude estimate: ~150 words/minute average speech rate
        word_count = max(len(text.split()), 1)
        duration_estimate = round((word_count / 150) * 60, 1)

        return TTSResult(
            success=True,
            audio_path=output_path,
            language=language,
            duration_estimate_sec=duration_estimate,
        )


class IndicTTSBackend(TTSBackend):
    """
    Placeholder for the real backend. Fill in once AI4Bharat Indic-TTS
    (or another provider) is actually running/hosted — the method
    signature is already the contract the rest of the pipeline expects.
    """

    def __init__(self, model_endpoint: Optional[str] = None):
        self.model_endpoint = model_endpoint

    def synthesize(self, text: str, language: str, output_path: str) -> TTSResult:
        raise NotImplementedError(
            "Wire this up to the AI4Bharat Indic-TTS model/API once it's "
            "deployed. Until then, use MockTTSBackend for development."
        )


class TTSService:
    """
    Entry point the Escalation Agent (or the web demo backend) calls.
    Handles caching so repeated identical replies (common — templates
    repeat a lot) don't get re-synthesized every time.
    """

    def __init__(self, backend: TTSBackend = None, output_dir: str = "tts_output"):
        self.backend = backend or MockTTSBackend()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict = {}

    def _cache_key(self, text: str, language: str) -> str:
        raw = f"{language}:{text}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    def synthesize_reply(self, text: str, language: str = "en") -> TTSResult:
        """Main function the Escalation Agent's output plugs into:
        escalation_output.reply_text -> synthesize_reply(...) -> audio."""
        cache_key = self._cache_key(text, language)
        if cache_key in self._cache:
            return self._cache[cache_key]

        output_path = str(self.output_dir / f"{cache_key}.txt")  # .wav once real backend is in
        result = self.backend.synthesize(text, language, output_path)

        if result.success:
            self._cache[cache_key] = result
        return result


# ---------------------------------------------------------------------------
# Manual test harness — feeds the actual reply text from the Escalation
# Agent's Case 1 and Case 2 outputs through the mock backend, so the two
# files are already proven to connect end-to-end.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    service = TTSService(backend=MockTTSBackend(), output_dir="tts_output")

    test_cases = [
        {
            "label": "CASE 1 — refer_now reply",
            "text": (
                "This could be serious (possible serious bacterial infection "
                "or very severe disease). Please take the baby to your ASHA "
                "worker or the nearest health facility right now — do not "
                "wait for the next scheduled visit."
            ),
            "language": "hi",
        },
        {
            "label": "CASE 2 — monitor_recheck reply",
            "text": (
                "This looks like something to keep an eye on (jaundice). "
                "Advise home care. Tell caregiver to return immediately if "
                "palms/soles turn yellow."
            ),
            "language": "kn",
        },
        {
            "label": "CASE 3 — same text again (should hit cache)",
            "text": (
                "This could be serious (possible serious bacterial infection "
                "or very severe disease). Please take the baby to your ASHA "
                "worker or the nearest health facility right now — do not "
                "wait for the next scheduled visit."
            ),
            "language": "hi",
        },
    ]

    for case in test_cases:
        print("=" * 70)
        print(case["label"])
        print("=" * 70)
        start = time.time()
        result = service.synthesize_reply(case["text"], case["language"])
        elapsed = round((time.time() - start) * 1000, 2)
        print(f"success={result.success}  path={result.audio_path}  "
              f"est_duration={result.duration_estimate_sec}s  took={elapsed}ms\n")