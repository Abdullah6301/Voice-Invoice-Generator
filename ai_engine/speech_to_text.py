"""
Invoice Generator Speech-to-Text Engine
Supports Vosk (offline) for converting voice audio to text.
"""

import json
import wave
import os
from pathlib import Path
from loguru import logger
from backend.config import settings


class SpeechToTextEngine:
    """
    Converts audio input to text using Vosk (offline).
    Supports WAV audio files (16kHz, mono, 16-bit).
    """

    def __init__(self):
        self.model = None
        self.engine = settings.STT_ENGINE
        logger.info(f"STT Engine configured: {self.engine}")

    def _load_vosk_model(self):
        """Load the Vosk model for offline speech recognition."""
        if self.model is not None:
            return

        try:
            from vosk import Model, SetLogLevel
            SetLogLevel(-1)  # Suppress Vosk logs

            model_path = settings.VOSK_MODEL_PATH
            if not Path(model_path).exists():
                logger.warning(
                    f"Vosk model not found at {model_path}. "
                    "Run 'python scripts/download_vosk_model.py' to download it."
                )
                return

            self.model = Model(model_path)
            logger.info("Vosk model loaded successfully")
        except ImportError:
            logger.error("Vosk not installed. Run: pip install vosk")
        except Exception as e:
            logger.error(f"Failed to load Vosk model: {e}")

    def transcribe_audio_file(self, audio_path: str) -> str:
        """
        Transcribe an audio file to text.

        Args:
            audio_path: Path to a WAV file (16kHz, mono, 16-bit PCM)

        Returns:
            Transcribed text string
        """
        if not Path(audio_path).exists():
            logger.error(f"Audio file not found: {audio_path}")
            return ""

        if self.engine == "vosk":
            return self._transcribe_vosk(audio_path)
        else:
            logger.error(f"Unknown STT engine: {self.engine}")
            return ""

    def _transcribe_vosk(self, audio_path: str) -> str:
        """Transcribe using Vosk offline model."""
        self._load_vosk_model()
        if self.model is None:
            logger.error("Vosk model not loaded, cannot transcribe")
            return ""

        try:
            from vosk import KaldiRecognizer

            wf = wave.open(audio_path, "rb")

            if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
                logger.error("Audio must be mono 16-bit WAV")
                return ""

            sample_rate = wf.getframerate()
            recognizer = KaldiRecognizer(self.model, sample_rate)
            recognizer.SetWords(True)

            results = []
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    if result.get("text"):
                        results.append(result["text"])

            # Get final result
            final = json.loads(recognizer.FinalResult())
            if final.get("text"):
                results.append(final["text"])

            wf.close()
            text = " ".join(results).strip()
            logger.info(f"Vosk transcription: '{text}'")
            return text

        except Exception as e:
            logger.error(f"Vosk transcription error: {e}")
            return ""

    def transcribe_text_input(self, text: str) -> str:
        """
        Pass-through for text input (simulates voice input for testing).
        Used when voice is not available or for API text commands.
        """
        logger.info(f"Text input received: '{text}'")
        return text.strip()


# Global STT instance
stt_engine = SpeechToTextEngine()
