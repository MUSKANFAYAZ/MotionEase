import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path


MODEL_NAME = "vosk-model-small-en-us-0.15"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
MODEL_DIR = MODELS_DIR / MODEL_NAME


def download_model():
    if MODEL_DIR.is_dir():
        print(f"Vosk model already installed: {MODEL_DIR}")
        return

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=MODELS_DIR) as temporary_dir:
        archive_path = Path(temporary_dir) / f"{MODEL_NAME}.zip"
        request = urllib.request.Request(
            MODEL_URL,
            headers={"User-Agent": "MotionEase offline ASR model setup"},
        )
        print(f"Downloading {MODEL_URL}")
        with urllib.request.urlopen(request, timeout=60) as response:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            with archive_path.open("wb") as archive:
                while chunk := response.read(1024 * 1024):
                    archive.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        print(
                            f"\rDownloaded {downloaded / total:.0%}",
                            end="",
                            flush=True,
                        )
        print()

        staging_dir = Path(temporary_dir) / "extracted"
        staging_dir.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            root = staging_dir.resolve()
            for entry in archive.infolist():
                destination = (staging_dir / entry.filename).resolve()
                if os.path.commonpath((str(root), str(destination))) != str(root):
                    raise ValueError(f"Unsafe path in model archive: {entry.filename}")
            archive.extractall(staging_dir)

        extracted_model = staging_dir / MODEL_NAME
        if not (extracted_model / "conf").is_dir():
            raise RuntimeError("Downloaded archive does not contain a valid Vosk model")
        shutil.move(str(extracted_model), str(MODEL_DIR))
        print(f"Installed Vosk model: {MODEL_DIR}")


if __name__ == "__main__":
    download_model()
