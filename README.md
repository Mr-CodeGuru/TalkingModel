# 🤖 TalkingModel

An **offline AI voice and text assistant** powered by [llama.cpp](https://github.com/ggerganov/llama.cpp) and [Vosk](https://alphacephei.com/vosk/).  
Runs entirely on your local machine — no cloud, no API keys, no internet required after first-run setup.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)](#)
[![Models on HF](https://img.shields.io/badge/Models-Hugging%20Face-orange?logo=huggingface)](https://huggingface.co/MrDevCoder01/TalkingModel)

---

## ✨ Features

| Feature | Details |
|---|---|
| 🎤 Voice mode | Speak → Vosk STT → LLM → TTS response |
| ⌨️ Text mode | Type → LLM → terminal response |
| 🔌 Fully offline | All inference runs locally after model download |
| 🚀 Auto-download | Missing models are fetched automatically on first run |
| 📦 Cached | Models are downloaded once and reused |
| 🌍 Cross-platform | macOS · Linux · Windows |
| 🔧 Config-driven | Add new models in `config/models.yaml` — no code changes |

---

## 🏗️ Directory Structure

```
TalkingModel/
├── engine/                  # Core AI engine
│   └── cli.py               # Unified master app (Menu + Chat + Commands)
│
├── utils/                   # Utilities
│   ├── model_manager.py     # HF download + local cache system
│   ├── paths.py             # Single source of truth for all paths
│   └── startup_check.py    # Pre-flight environment validation
│
├── config/
│   └── models.yaml          # Declarative model registry (add models here)
│
├── scripts/
│   ├── launch.sh            # Master launch script (Mac/Linux)
│   ├── launch.bat           # Master launch script (Windows)
│   └── test_tts.py          # TTS smoke test
│
├── models/                  # ← gitignored, auto-populated on first run
│   ├── gguf/                # GGUF LLM model files
│   └── vosk/                # Vosk STT model directories
│
├── logs/                    # ← gitignored, conversation history
│   └── record.txt
│
├── .env.example             # Environment variable template
├── requirements.txt         # Python dependencies
└── pyproject.toml           # Project metadata
```

> **Note:** The `models/` and `logs/` directories are gitignored.  
> They are created automatically and populated on first run.

---

## 🚀 Quick Start

To get started with TalkingModel, simply copy and paste the following "One-Liner" command into your terminal. This will clone the repository and initiate the smart setup.

```bash
git clone https://github.com/Mr-CodeGuru/TalkingModel.git && cd TalkingModel && bash scripts/launch.sh
```

### What happens next?
1. **Trust Prompt**: The script will ask if you trust the folder and wish to proceed with installation.
2. **Automatic Environment**: It builds a Python virtual environment and installs dependencies automatically.
3. **Global Command (Optional)**: It will ask if you want to create a global `tm` command so you can launch the app by just typing `tm` from anywhere!
4. **Model Downloads**: Finally, it lets you select Text or Voice mode, and starts downloading the models with clean progress indicators.

---

## 🧠 Model Management

### How models are stored

Models are stored in your local `models/` directory (gitignored) and downloaded automatically from:

| Model type | Source |
|---|---|
| GGUF LLM | [Hugging Face — MrDevCoder01/TalkingModel](https://huggingface.co/MrDevCoder01/TalkingModel) |
| Vosk STT (small) | [alphacephei.com](https://alphacephei.com/vosk/models) — direct download |
| Vosk STT (large) | [Hugging Face — MrDevCoder01/TalkingModel](https://huggingface.co/MrDevCoder01/TalkingModel) |

### Default models

| Model | Size | Quality |
|---|---|---|
| `TM-1B-Q80.gguf` | ~1.2 GB | High (Q8_0 quantization) |
| `vosk-model-small-en-us-0.15` | ~40 MB | Good (fast, English) |

### Adding new models

Edit `config/models.yaml` — no Python changes needed:

```yaml
models:
  llm:
    - id: MyNewModel-7B
      label: "My Model 7B (Q4_K_M)"
      filename: my-model-7b-q4.gguf
      hf_repo: MrDevCoder01/TalkingModel
      hf_path: gguf/my-model-7b-q4.gguf
      size_gb: 4.1
      default: false

  vosk:
    - id: small-fr
      label: "French Small (~39 MB)"
      dirname: vosk-model-small-fr-0.22
      url: https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip
      size_mb: 39
      default: false
```

The launcher will discover and list new models automatically.

### Using a private HuggingFace repo

If your models are in a private HF repository, create a `.env` file:

```bash
cp .env.example .env
# Edit .env and set:
HF_TOKEN=hf_your_token_here
```

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and adjust as needed:

```env
HF_REPO_ID=MrDevCoder01/TalkingModel   # HuggingFace repo ID
HF_TOKEN=                               # Leave blank for public repos
DEFAULT_LLM_MODEL=TM-1B-Q80.gguf       # Default LLM filename
DEFAULT_VOSK_MODEL=small                # "small" or "large"
MODELS_DIR=./models                     # Where to cache models
LOG_DIR=./logs                          # Where to write conversation logs
```

---

## 🔧 Manual Usage

You can bypass the launcher and invoke the engine directly:

**Text mode:**
```bash
source .venv/bin/activate
python engine/launcher.py
```

**Force text mode directly:**
```bash
python engine/main.py --llm_path models/gguf/TM-1B-Q80.gguf --text
```

**Force voice mode directly:**
```bash
python engine/main.py \
  --llm_path models/gguf/TM-1B-Q80.gguf \
  --vosk_path models/vosk/vosk-model-small-en-us-0.15
```

**Run startup checks only:**
```bash
python utils/startup_check.py
```

**List all configured models and cache status:**
```python
python -c "from utils.model_manager import list_available_models; import pprint; pprint.pprint(list_available_models())"
```

---

## 🛠️ Troubleshooting

### ❌ "No .gguf models found"

The LLM model wasn't downloaded yet. Run:
```bash
bash scripts/setup.sh
```
Or manually download:
```python
python -c "from utils.model_manager import ensure_gguf_model; ensure_gguf_model()"
```

### ❌ "No vosk-model-* directories found"

The Vosk STT model wasn't downloaded. Run:
```python
python -c "from utils.model_manager import ensure_vosk_model; ensure_vosk_model()"
```

### ❌ Download fails with 401/403 (authentication error)

The HuggingFace model may be private. Set `HF_TOKEN` in your `.env` file:
```env
HF_TOKEN=hf_your_personal_access_token
```
Get a token at: https://huggingface.co/settings/tokens

### ❌ `llama_cpp` import fails or crashes

`llama-cpp-python` may need to be compiled for your hardware. Try:
```bash
pip uninstall llama-cpp-python -y
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python  # macOS Metal
# or
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python   # NVIDIA CUDA
```

### ❌ TTS not working on macOS

Test with:
```bash
python scripts/test_tts.py
```
The engine uses the native macOS `say` command (always works). `pyttsx3` is only a fallback for non-macOS systems.

### ❌ "PortAudioError: No Default Input Device Available"

No microphone is detected. Either:
- Connect a microphone and retry
- Use **Text mode** instead (no microphone required)

### ❌ Python version error

Verify your Python version:
```bash
python3 --version   # must be 3.9 or higher
```
Update at: https://python.org/downloads

---

## 🗂️ Uploading Models to Hugging Face

To enable automatic downloads you need to upload the model files to your HF repo.

### Install the HF CLI
```bash
pip install huggingface-hub
huggingface-cli login
```

### Upload GGUF model
```bash
huggingface-cli upload MrDevCoder01/TalkingModel \
  ./TM-GGUF/TM-1B-Q80.gguf \
  gguf/TM-1B-Q80.gguf
```

### Upload Vosk model (zipped)
```bash
# Zip the large model first
zip -r vosk-model-en-us-0.22.zip TM-Engine/ENGINE/vosk-model-en-us-0.22/

huggingface-cli upload MrDevCoder01/TalkingModel \
  ./vosk-model-en-us-0.22.zip \
  vosk/vosk-model-en-us-0.22.zip
```

After uploading, users can set `DEFAULT_VOSK_MODEL=large` in their `.env` to download the high-accuracy model.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

To add support for a new model, simply add an entry to `config/models.yaml` — no Python changes required.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- [llama.cpp](https://github.com/ggerganov/llama.cpp) — blazing-fast local LLM inference
- [Vosk](https://alphacephei.com/vosk/) — offline speech recognition
- [Hugging Face Hub](https://huggingface.co/) — model hosting and distribution
