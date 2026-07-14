from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import hashlib
import subprocess
import time


SUPPORTED_LANGUAGES = {
    "hi": "Hindi",
    "bn": "Bengali",
    "te": "Telugu",
    "mr": "Marathi",
    "ta": "Tamil",
    "kn": "Kannada",
    "gu": "Gujarati",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "ur": "Urdu",
    "ne": "Nepali",
    "or": "Odia",
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
    @abstractmethod
    def synthesize(self, text: str, language: str, output_path: str) -> TTSResult:
        ...


class MockTTSBackend(TTSBackend):
    def synthesize(self, text: str, language: str, output_path: str) -> TTSResult:
        if language not in SUPPORTED_LANGUAGES:
            return TTSResult(success=False, error=f"Unsupported language: {language}")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"[MOCK AUDIO PLACEHOLDER]\nlanguage={language}\ntext={text}\n")
        word_count = max(len(text.split()), 1)
        duration_estimate = round((word_count / 150) * 60, 1)
        return TTSResult(success=True, audio_path=output_path, language=language,
                          duration_estimate_sec=duration_estimate)


class CartesiaBackend(TTSBackend):
    _CARTESIA_LANGUAGES = {"hi", "ta", "te", "bn", "gu", "kn", "ml", "mr", "pa", "en"}

    def __init__(self, api_key: str, voice_id: Optional[str] = None):
        self.api_key = api_key
        self.voice_id = voice_id

    def synthesize(self, text: str, language: str, output_path: str) -> TTSResult:
        if language not in self._CARTESIA_LANGUAGES:
            return TTSResult(success=False,
                error=f"Cartesia does not support '{language}'. Supported: "
                      f"{sorted(self._CARTESIA_LANGUAGES)}.")
        if not self.voice_id:
            return TTSResult(success=False,
                error="No voice_id set. Pass CartesiaBackend(api_key=..., voice_id=...).")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        wav_path = str(Path(output_path).with_suffix(".wav"))

        try:
            import requests
            response = requests.post(
                "https://api.cartesia.ai/tts/bytes",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Cartesia-Version": "2025-04-16",
                    "Content-Type": "application/json",
                },
                json={
                    "model_id": "sonic-3.5",
                    "transcript": text,
                    "voice": {"mode": "id", "id": self.voice_id},
                    "output_format": {
                        "container": "wav",
                        "encoding": "pcm_s16le",
                        "sample_rate": 22050,
                    },
                    "language": language,
                },
                timeout=30,
            )
            if response.status_code >= 400:
                return TTSResult(success=False,
                    error=f"Cartesia API returned {response.status_code}: {response.text}")
            with open(wav_path, "wb") as f:
                f.write(response.content)
        except ImportError:
            return TTSResult(success=False, error="requests is not installed. Run: pip install requests")
        except Exception as e:
            return TTSResult(success=False, error=f"Cartesia API call failed: {e}")

        if not Path(wav_path).exists() or Path(wav_path).stat().st_size == 0:
            return TTSResult(success=False, error="Cartesia produced no audio output.")

        word_count = max(len(text.split()), 1)
        duration_estimate = round((word_count / 150) * 60, 1)
        return TTSResult(success=True, audio_path=wav_path, language=language,
                          duration_estimate_sec=duration_estimate)


class GTTSBackend(TTSBackend):
    _LANG_MAP = {
        "hi": "hi", "bn": "bn", "te": "te", "mr": "mr", "ta": "ta",
        "kn": "kn", "gu": "gu", "ml": "ml", "pa": "pa", "ur": "ur",
        "ne": "ne", "en": "en",
    }

    def synthesize(self, text: str, language: str, output_path: str) -> TTSResult:
        if language not in SUPPORTED_LANGUAGES:
            return TTSResult(success=False, error=f"Unsupported language: {language}")
        lang_code = self._LANG_MAP.get(language)
        if not lang_code:
            return TTSResult(success=False,
                error=f"No gTTS language mapped for '{language}'. Available: {list(self._LANG_MAP.keys())}")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        mp3_path = str(Path(output_path).with_suffix(".mp3"))

        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang=lang_code)
            tts.save(mp3_path)
        except ImportError:
            return TTSResult(success=False, error="gTTS is not installed. Run: pip install gtts --break-system-packages")
        except Exception as e:
            return TTSResult(success=False, error=f"gTTS failed (check internet connection): {e}")

        if not Path(mp3_path).exists() or Path(mp3_path).stat().st_size == 0:
            return TTSResult(success=False, error="gTTS produced no audio output.")

        word_count = max(len(text.split()), 1)
        duration_estimate = round((word_count / 150) * 60, 1)
        return TTSResult(success=True, audio_path=mp3_path, language=language,
                          duration_estimate_sec=duration_estimate)


class EspeakBackend(TTSBackend):
    _VOICE_MAP = {"hi": "hi", "kn": "kn", "mr": "mr", "en": "en"}

    def synthesize(self, text: str, language: str, output_path: str) -> TTSResult:
        if language not in SUPPORTED_LANGUAGES:
            return TTSResult(success=False, error=f"Unsupported language: {language}")
        voice = self._VOICE_MAP.get(language)
        if not voice:
            return TTSResult(success=False,
                error=f"No espeak-ng voice mapped for '{language}'. Available: {list(self._VOICE_MAP.keys())}")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        wav_path = str(Path(output_path).with_suffix(".wav"))

        try:
            subprocess.run(["espeak-ng", "-v", voice, "-w", wav_path, text],
                            check=True, capture_output=True, timeout=30)
        except FileNotFoundError:
            return TTSResult(success=False, error="espeak-ng is not installed.")
        except subprocess.CalledProcessError as e:
            return TTSResult(success=False, error=f"espeak-ng failed: {e.stderr.decode()}")
        except subprocess.TimeoutExpired:
            return TTSResult(success=False, error="espeak-ng timed out.")

        if not Path(wav_path).exists() or Path(wav_path).stat().st_size == 0:
            return TTSResult(success=False, error="espeak-ng produced no audio output.")

        word_count = max(len(text.split()), 1)
        duration_estimate = round((word_count / 150) * 60, 1)
        return TTSResult(success=True, audio_path=wav_path, language=language,
                          duration_estimate_sec=duration_estimate)


class IndicTTSBackend(TTSBackend):
    def __init__(self, model_endpoint: Optional[str] = None):
        self.model_endpoint = model_endpoint

    def synthesize(self, text: str, language: str, output_path: str) -> TTSResult:
        raise NotImplementedError("Wire this up to AI4Bharat Indic-TTS once deployed.")


class TTSService:
    def __init__(self, backend: TTSBackend = None, output_dir: str = "tts_output"):
        self.backend = backend or MockTTSBackend()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict = {}

    def _cache_key(self, text: str, language: str) -> str:
        raw = f"{language}:{text}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]

    def synthesize_reply(self, text: str, language: str = "en") -> TTSResult:
        cache_key = self._cache_key(text, language)
        if cache_key in self._cache:
            return self._cache[cache_key]
        output_path = str(self.output_dir / cache_key)
        result = self.backend.synthesize(text, language, output_path)
        if result.success:
            transcript_path = self.output_dir / f"{cache_key}.txt"
            with open(transcript_path, "w", encoding="utf-8") as f:
                f.write(f"language: {language}\naudio_file: {Path(result.audio_path).name}\n\ntext:\n{text}\n")
            self._cache[cache_key] = result
        return result


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()

    cartesia_key = os.environ.get("CARTESIA_API_KEY")
    cartesia_voice = os.environ.get("CARTESIA_VOICE_ID")

    if cartesia_key and cartesia_voice:
        print(f"Using CartesiaBackend (voice_id={cartesia_voice})\n")
        backend = CartesiaBackend(api_key=cartesia_key, voice_id=cartesia_voice)
    else:
        print("CARTESIA_API_KEY / CARTESIA_VOICE_ID not set -- using GTTSBackend instead.\n")
        backend = GTTSBackend()

    service = TTSService(backend=backend, output_dir="tts_output")

    test_cases = [
        {"label": "Hindi (hi) — refer_now: breathing distress",
         "text": "Bachche ki saans bahut tez chal rahi hai aur chest andar ki taraf khinch rahi hai. Yeh gambhir ho sakta hai — turant ASHA worker ya najdeeki aspatal jaayein.",
         "language": "hi"},
        {"label": "Tamil (ta) — monitor_recheck: mild fever",
         "text": "Kuzhandhaikku sannikkil kaachal irukku, aanaal paal kudikirathu, saris moochu vidugirathu. Veetil kavanithu paarungal, aanaal rendu naalil marupadiyum sari illa endraal ASHA workeridam sollungal.",
         "language": "ta"},
        {"label": "Telugu (te) — reassure: normal newborn jaundice",
         "text": "Ee pasividi mukham meeda konchem pasupu rangu kanabadatam sadharananga jarigedi, chinta pettukovaddu. Idi rendu vaaralalo tanantaanuga thagguthundi, kaani chetulu kaallaku kuda vyapisthe ventane ASHA workarunni sampradinchandi.",
         "language": "te"},
        {"label": "Bengali (bn) — refer_now: convulsions (emergency)",
         "text": "Shishur shorire jhaanka ba khichuni hocche. Eta ekta jaruri obostha — ekhoni ASHA workerke daakun othoba sobcheye kachhakachhi hospital e jaan.",
         "language": "bn"},
        {"label": "Gujarati (gu) — monitor_recheck: feeding attachment issue",
         "text": "Baalak stanpaan karti vakhate barabar pakadi nathi shakato, ane divas ma aath vaar karta ochu doodh pi rahyo chhe. Sthiti sudharva paddhati batavo ane be divas pachi punah tapaas karo.",
         "language": "gu"},
        {"label": "Kannada (kn) — reassure: cluster feeding is normal",
         "text": "Maguvu ee vaaravella jaasti bari haalu kudiyuttide anta ninage anisabahudu, adu saamaanya belavaniya bhaagavagide, chinte beda. Adare maguvu aduva reethi badalada haage kanistiddare mattu shakti kadime aagiddare ASHA workerannu samparkisi.",
         "language": "kn"},
        {"label": "Malayalam (ml) — refer_now: not feeding + cold body",
         "text": "Kunju thire paal kudikkunnilla, kayyum kaalum thanuthu poyirikkunnu. Ithu gurutharamaya avastha aakaam — udane ASHA workere vilikkuka allenkil aduthulla aashupathriyil pokuka.",
         "language": "ml"},
        {"label": "Marathi (mr) — refer_now: bulging fontanelle + grunting",
         "text": "Baalachya dokyaavarchi magchi jaaga phugleli disat aahe ani te shwaas ghetana ghurghur aavaj kaadhtay. He khup gambhir asu shakte — tvarit ASHA karyakartila bhetun ya javalchya rugnalayat gheun ja.",
         "language": "mr"},
        {"label": "Punjabi (pa) — reassure: normal jaundice explanation",
         "text": "Bacche de chehre te thodi peeli rangat aam gal hai ate aksar do hafteyan wich khud thik ho jaandi hai, ghabrao na. Je haath ja pair vi peele ho jaan tan turant ASHA worker nu dasso.",
         "language": "pa"},
        {"label": "English (en) — refer_now: very low birth weight",
         "text": "The baby's weight is dangerously low for their age and they are having difficulty staying warm. This needs urgent hospital care — please refer immediately and keep the baby warm via skin-to-skin contact on the way.",
         "language": "en"},
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