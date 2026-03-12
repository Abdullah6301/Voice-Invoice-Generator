"""
Invoice Generator Vosk Model Download Script
Downloads the small English Vosk model for offline speech recognition.
"""

import os
import sys
import zipfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.config import settings

VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_DIR = Path(settings.VOSK_MODEL_PATH).parent


def download_vosk_model():
    """Download and extract the Vosk speech recognition model."""
    model_path = Path(settings.VOSK_MODEL_PATH)

    if model_path.exists():
        print(f"Vosk model already exists at: {model_path}")
        return

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = MODEL_DIR / "vosk-model.zip"

    print(f"Downloading Vosk model from: {VOSK_MODEL_URL}")
    print("This may take a few minutes...")

    try:
        urllib.request.urlretrieve(VOSK_MODEL_URL, str(zip_path))
        print("Download complete. Extracting...")

        with zipfile.ZipFile(str(zip_path), "r") as z:
            z.extractall(str(MODEL_DIR))

        # Remove zip file
        os.remove(str(zip_path))
        print(f"Vosk model ready at: {model_path}")

    except Exception as e:
        print(f"Error downloading model: {e}")
        print("You can manually download from: https://alphacephei.com/vosk/models")
        sys.exit(1)


if __name__ == "__main__":
    download_vosk_model()
