from pathlib import Path

from huggingface_hub import snapshot_download


MODEL_REPOSITORY = "Systran/faster-whisper-base.en"
MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "faster-whisper-base.en"
REQUIRED_FILES = (
    "config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.txt",
)


def download_model():
    if all((MODEL_DIR / filename).is_file() for filename in REQUIRED_FILES):
        print(f"Whisper model already installed: {MODEL_DIR}")
        return

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {MODEL_REPOSITORY} to {MODEL_DIR}")
    snapshot_download(
        repo_id=MODEL_REPOSITORY,
        local_dir=str(MODEL_DIR),
    )
    missing_files = [
        filename
        for filename in REQUIRED_FILES
        if not (MODEL_DIR / filename).is_file()
    ]
    if missing_files:
        raise RuntimeError(
            "Downloaded Whisper model is incomplete; missing: "
            + ", ".join(missing_files)
        )
    print(f"Installed Whisper model: {MODEL_DIR}")


if __name__ == "__main__":
    download_model()
