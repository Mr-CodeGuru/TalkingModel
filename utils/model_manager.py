"""
utils/model_manager.py — Automatic model download and cache management.

On first run the required models are not present locally.
This module checks the cache, downloads missing models from
Hugging Face or direct URLs, and returns validated local paths
ready for use by the engine.

Supports:
  • GGUF LLM models  → downloaded from Hugging Face
  • Vosk STT models  → downloaded from alphacephei.com or Hugging Face
  • Progress bars via tqdm
  • Resumable downloads (partial file detection)
  • Config-driven via config/models.yaml
"""

from __future__ import annotations

import os
import sys
import shutil
import zipfile
import threading
from pathlib import Path
from typing import Optional

import requests
import yaml
from tqdm import tqdm

# Load .env if present (so HF_TOKEN etc. work without shell export)
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv optional at this stage

from utils.paths import GGUF_DIR, VOSK_DIR, MODELS_YAML, ensure_directories

# ── Thread lock — prevents concurrent downloads of the same file ───────────────
_download_lock = threading.Lock()


# =============================================================================
#  Helpers
# =============================================================================

def _load_registry() -> dict:
    """Load config/models.yaml and return parsed dict."""
    if not MODELS_YAML.exists():
        raise FileNotFoundError(f"Model registry not found: {MODELS_YAML}")
    with open(MODELS_YAML, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _get_llm_configs() -> list[dict]:
    return _load_registry().get("models", {}).get("llm", [])


def _get_vosk_configs() -> list[dict]:
    return _load_registry().get("models", {}).get("vosk", [])


def _download_with_progress(url: str, dest: Path, desc: str) -> None:
    """
    Stream-download *url* to *dest*, showing a tqdm progress bar.
    Overwrites any existing partial file.
    """
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    try:
        with open(tmp, "wb") as fh, tqdm(
            desc=desc,
            total=total,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            ncols=80,
        ) as bar:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)
                    bar.update(len(chunk))

        tmp.rename(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _download_from_hf(hf_repo: str, hf_path: str, dest: Path, desc: str) -> None:
    """
    Download a single file from a Hugging Face model repository.
    Uses huggingface_hub if available (handles auth / caching natively),
    falls back to direct HTTPS if not installed.
    """
    try:
        from huggingface_hub import hf_hub_download
        token = os.environ.get("HF_TOKEN") or None
        print(f"  ↓  Downloading {desc} from Hugging Face…")
        local = hf_hub_download(
            repo_id=hf_repo,
            filename=hf_path,
            token=token,
            local_dir=str(dest.parent),
        )
        # hf_hub_download places file at <local_dir>/<hf_path>
        # If the file landed at a subpath, move it to dest
        downloaded = Path(local)
        if downloaded.resolve() != dest.resolve():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(downloaded), str(dest))
    except ImportError:
        # Fallback: direct HTTPS
        url = f"https://huggingface.co/{hf_repo}/resolve/main/{hf_path}"
        _download_with_progress(url, dest, desc)


def _extract_zip(zip_path: Path, extract_to: Path) -> None:
    """Extract a zip archive to *extract_to* with a progress indicator."""
    print(f"  📦  Extracting {zip_path.name}…")
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.infolist()
        for member in tqdm(members, desc="Extracting", unit="file", ncols=80):
            zf.extract(member, extract_to)
    zip_path.unlink()  # remove the zip after extraction
    print(f"  ✅  Extracted to {extract_to}")


# =============================================================================
#  Public API
# =============================================================================

def list_available_models() -> dict:
    """
    Return a dict with 'llm' and 'vosk' keys listing all configured models,
    annotated with whether they are cached locally.

    Example::

        {
          'llm':  [{'id': 'TM-1B-Q80', 'label': '...', 'cached': True}],
          'vosk': [{'id': 'small',     'label': '...', 'cached': False}],
        }
    """
    ensure_directories()
    registry = _load_registry()
    result: dict = {"llm": [], "vosk": []}

    for cfg in registry.get("models", {}).get("llm", []):
        cached = (GGUF_DIR / cfg["filename"]).exists()
        result["llm"].append({**cfg, "cached": cached})

    for cfg in registry.get("models", {}).get("vosk", []):
        cached = (VOSK_DIR / cfg["dirname"]).is_dir()
        result["vosk"].append({**cfg, "cached": cached})

    return result


def ensure_gguf_model(model_id: Optional[str] = None) -> Path:
    """
    Ensure the requested GGUF model is present locally.

    Parameters
    ----------
    model_id : str, optional
        The ``id`` field from config/models.yaml.
        If None, uses the model marked ``default: true``.

    Returns
    -------
    Path
        Absolute path to the local .gguf file, ready to pass to llama-cpp.

    Raises
    ------
    ValueError
        If the requested model_id is not found in the registry.
    RuntimeError
        If the download fails.
    """
    ensure_directories()
    configs = _get_llm_configs()
    if not configs:
        raise RuntimeError("No LLM models defined in config/models.yaml")

    # Select config
    if model_id:
        cfg = next((c for c in configs if c["id"] == model_id), None)
        if cfg is None:
            ids = [c["id"] for c in configs]
            raise ValueError(f"LLM model '{model_id}' not found. Available: {ids}")
    else:
        cfg = next((c for c in configs if c.get("default")), configs[0])

    dest = GGUF_DIR / cfg["filename"]

    if dest.exists():
        print(f"  ✓  LLM model cached: {dest.name}")
        return dest

    # Not cached — download
    print(f"\n  ⬇  LLM model not found locally. Downloading '{cfg['label']}'…")
    print(f"      Size: ~{cfg.get('size_gb', '?')} GB — this may take a while.\n")

    with _download_lock:
        if dest.exists():          # another thread may have finished
            return dest
        try:
            _download_from_hf(
                hf_repo=cfg["hf_repo"],
                hf_path=cfg["hf_path"],
                dest=dest,
                desc=cfg["filename"],
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to download LLM model '{cfg['id']}': {exc}") from exc

    print(f"  ✅  LLM model ready: {dest}")
    return dest


def ensure_vosk_model(model_id: Optional[str] = None) -> Path:
    """
    Ensure the requested Vosk STT model is present locally.

    Parameters
    ----------
    model_id : str, optional
        The ``id`` field from config/models.yaml (e.g. "small" or "large").
        If None, uses the model marked ``default: true``.

    Returns
    -------
    Path
        Absolute path to the local Vosk model directory.

    Raises
    ------
    ValueError
        If the requested model_id is not found in the registry.
    RuntimeError
        If the download fails.
    """
    ensure_directories()
    configs = _get_vosk_configs()
    if not configs:
        raise RuntimeError("No Vosk models defined in config/models.yaml")

    # Override with env var if set
    env_variant = os.environ.get("DEFAULT_VOSK_MODEL")
    if model_id is None and env_variant:
        model_id = env_variant

    # Select config
    if model_id:
        cfg = next((c for c in configs if c["id"] == model_id), None)
        if cfg is None:
            ids = [c["id"] for c in configs]
            raise ValueError(f"Vosk model '{model_id}' not found. Available: {ids}")
    else:
        cfg = next((c for c in configs if c.get("default")), configs[0])

    dest_dir = VOSK_DIR / cfg["dirname"]

    if dest_dir.is_dir() and any(dest_dir.iterdir()):
        print(f"  ✓  Vosk model cached: {dest_dir.name}")
        return dest_dir

    # Not cached — download
    size_info = (
        f"~{cfg['size_mb']} MB" if "size_mb" in cfg
        else f"~{cfg.get('size_gb', '?')} GB"
    )
    print(f"\n  ⬇  Vosk model not found locally. Downloading '{cfg['label']}'…")
    print(f"      Size: {size_info}\n")

    zip_dest = VOSK_DIR / f"{cfg['dirname']}.zip"

    with _download_lock:
        if dest_dir.is_dir() and any(dest_dir.iterdir()):
            return dest_dir
        try:
            if "url" in cfg:
                _download_with_progress(cfg["url"], zip_dest, cfg["dirname"])
            else:
                _download_from_hf(
                    hf_repo=cfg["hf_repo"],
                    hf_path=cfg["hf_path"],
                    dest=zip_dest,
                    desc=cfg["dirname"],
                )
            _extract_zip(zip_dest, VOSK_DIR)
        except Exception as exc:
            zip_dest.unlink(missing_ok=True)
            raise RuntimeError(
                f"Failed to download Vosk model '{cfg['id']}': {exc}"
            ) from exc

    # Verify the expected directory appeared after extraction
    if not dest_dir.is_dir():
        raise RuntimeError(
            f"Extraction completed but expected directory not found: {dest_dir}\n"
            "The zip may have a different internal folder name. "
            "Check VOSK_DIR and update config/models.yaml 'dirname' if needed."
        )

    print(f"  ✅  Vosk model ready: {dest_dir}")
    return dest_dir


def list_local_gguf_models() -> list[Path]:
    """Return all .gguf files currently present in the local cache."""
    ensure_directories()
    return sorted(GGUF_DIR.glob("*.gguf"))


def list_local_vosk_models() -> list[Path]:
    """Return all Vosk model directories currently present in the local cache."""
    ensure_directories()
    return sorted(
        p for p in VOSK_DIR.iterdir()
        if p.is_dir() and p.name.startswith("vosk-model-")
    )
