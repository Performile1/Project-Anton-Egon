#!/usr/bin/env python3
"""
Project Anton Egon - Project Initialization Script
Creates the directory structure and basic configuration files
"""

import os
import sys
from pathlib import Path


def print_section(title):
    """Print a section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def create_directory_structure():
    """Create the project directory structure"""
    print_section("CREATING DIRECTORY STRUCTURE")
    
    directories = [
        "core",
        "audio",
        "vision",
        "video",
        "integration",
        "ui",
        "memory/meeting",
        "memory/context",
        "memory/chroma_db",
        "memory/mood",
        "vault/internal",
        "vault/client",
        "vault/general",
        "assets/video/outfits",
        "assets/video/backgrounds",
        "assets/audio/fillers",
        "config",
        "logs",
        "models",
        "credentials",
    ]
    
    for directory in directories:
        dir_path = Path(directory)
        if not dir_path.exists():
            dir_path.mkdir(parents=True)
            print(f"✅ Created: {directory}")
        else:
            print(f"✓ Exists: {directory}")


def create_requirements_txt():
    """Create requirements.txt"""
    print_section("CREATING REQUIREMENTS.TXT")
    
    requirements = """# Project Anton Egon - Dependencies

# Core
python-dotenv==1.0.0
loguru==0.7.2
pydantic==2.5.3
pyyaml==6.0.1

# Phase 1: Foundation & Data Ingestion
llama-cpp-python==0.2.57
chromadb==0.4.22
sentence-transformers==2.2.2
pypdf==3.17.4
python-docx==1.1.0
openpyxl==3.1.2

# Phase 2: Audio & Vision
openai-whisper==20231117
pyaudio==0.2.14
opencv-python==4.9.0.80
ultralytics==8.1.0
deepface==0.0.79
mss==9.0.1
torch==2.1.0
torchvision==0.16.0

# Phase 3: Cognitive Logic
# No additional dependencies (uses existing)

# Phase 4: Synthesis & Wardrobe
edge-tts==6.1.9
# pyvirtualcam==0.6.0  # Optional: for OBS virtual camera (Linux/Mac)
# pyvirtualcam-win==0.6.0  # Optional: for OBS virtual camera (Windows)

# Phase 5: Integration & Fail-safe
keyboard==0.13.5

# Calendar Integration
msal==1.24.0
google-api-python-client==2.108.0
google-auth-httplib2==0.1.1
google-auth-oauthlib==1.1.0
pytz==2024.1

# Web Dashboard
fastapi==0.109.0
uvicorn==0.27.0
websockets==12.0
"""
    
    req_path = Path("requirements.txt")
    with open(req_path, "w") as f:
        f.write(requirements)
    
    print(f"✅ Created: requirements.txt")


def create_env_example():
    """Create .env.example file"""
    print_section("CREATING .ENV.EXAMPLE")
    
    env_example = """# Project Anton Egon - Environment Variables
# Copy this file to .env and fill in your values

# Calendar Integration (Microsoft Graph API)
MICROSOFT_GRAPH_CLIENT_ID=your_client_id
MICROSOFT_GRAPH_CLIENT_SECRET=your_client_secret
MICROSOFT_GRAPH_TENANT_ID=your_tenant_id

# Calendar Integration (Google Calendar API)
GOOGLE_CALENDAR_CREDENTIALS_PATH=credentials/google_calendar.json

# Model Paths
LLM_MODEL_PATH=models/llama-3-8b-instruct-q4_k_m.gguf
VOICE_MODEL_PATH=models/voice_model.pth

# GPU Configuration
N_GPU_LAYERS=-1
CUDA_VISIBLE_DEVICES=0

# Logging
LOG_LEVEL=INFO
"""
    
    env_path = Path(".env.example")
    with open(env_path, "w") as f:
        f.write(env_example)
    
    print(f"✅ Created: .env.example")


def create_gitignore():
    """Create .gitignore file"""
    print_section("CREATING .GITIGNORE")
    
    gitignore = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
ENV/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Project specific
.env
models/*.gguf
credentials/*.json
memory/chroma_db/
logs/*.log
*.mp4
*.mp3
*.wav
*.avi

# OS
.DS_Store
Thumbs.db
"""
    
    gitignore_path = Path(".gitignore")
    with open(gitignore_path, "w") as f:
        f.write(gitignore)
    
    print(f"✅ Created: .gitignore")


def create_config_yaml():
    """Create config.yaml file"""
    print_section("CREATING CONFIG.YAML")
    
    config_yaml = """# Project Anton Egon - Configuration
# Mood settings and rendering choices

project:
  name: "Anton Egon"
  version: "1.0.0"
  phase: "1"

# Mood Engine Configuration
mood:
  default_mood: "neutral"
  decay_rate: 0.1
  decay_interval_hours: 2
  keep_history_days: 30
  max_history_entries: 100
  enable_quick_logging: true

# Rendering Configuration
rendering:
  mode: "auto"  # auto, local_full, cloud_power, hybrid_placeholder
  local_full:
    enable_gpu: true
    target_fps: 30
    resolution: "1080p"
  cloud_power:
    server_url: "ws://localhost:8080"
    timeout: 30
  hybrid_placeholder:
    enable_gpu: false
    target_fps: 20
    resolution: "720p"

# Visual Mood Sync
visual_mood:
  enabled: true
  smile_intensity:
    neutral: 0.5
    happy: 0.8
    irritated: 0.1

# Platform
platform:
  default: "teams"
  supported: ["teams", "google_meet", "zoom", "webex", "slack"]

# Calendar
calendar:
  enable_microsoft_graph: false
  enable_google_calendar: false
  timezone: "Europe/Stockholm"

# Logging
logging:
  level: "INFO"
  log_dir: "logs"
  rotation: "10 MB"
"""
    
    config_path = Path("config/config.yaml")
    with open(config_path, "w") as f:
        f.write(config_yaml)
    
    print(f"✅ Created: config/config.yaml")


def create_config_template():
    """Create config/settings.json template"""
    print_section("CREATING CONFIG TEMPLATE")
    
    config_template = """{
  "project": "Anton Egon",
  "version": "1.0.0",
  "phase": "1",
  
  "llm": {
    "model_path": "models/llama-3-8b-instruct-q4_k_m.gguf",
    "n_ctx": 2048,
    "n_gpu_layers": -1,
    "verbose": false
  },
  
  "embeddings": {
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "dimension": 384
  },
  
  "chromadb": {
    "persist_directory": "memory/chroma_db",
    "collection_prefix": "anton_egon"
  },
  
  "vault": {
    "base_dir": "vault",
    "categories": ["internal", "client", "general"],
    "supported_formats": [".pdf", ".docx", ".xlsx", ".xls"]
  },
  
  "ingestion": {
    "chunk_size": 500,
    "chunk_overlap": 50
  },
  
  "orchestrator": {
    "loop_interval": 0.1,
    "enable_audio": true,
    "enable_vision": true,
    "enable_emotion": true,
    "enable_rag": true,
    "target_fps": 20,
    "platform": "teams",
    "enable_calendar_sync": false,
    "calendar_timezone": "Europe/Stockholm",
    "calendar_check_interval": 15
  },
  
  "calendar": {
    "enable_microsoft_graph": false,
    "enable_google_calendar": false,
    "timezone": "Europe/Stockholm",
    "check_interval_minutes": 15,
    "look_ahead_hours": 24
  },
  
  "logging": {
    "level": "INFO",
    "log_dir": "logs",
    "rotation": "10 MB",
    "retention": "30 days"
  }
}
"""
    
    config_dir = Path("config")
    if not config_dir.exists():
        config_dir.mkdir(parents=True)
    
    config_path = config_dir / "settings.json"
    with open(config_path, "w") as f:
        f.write(config_template)
    
    print(f"✅ Created: config/settings.json")


def create_readme():
    """Create README.md"""
    print_section("CREATING README.MD")
    
    readme = """# Project Anton Egon

AI Agent for autonomous participation in Teams meetings with audio, video, and cognitive capabilities.

## Quick Start

1. Initialize project structure:
   ```bash
   python init_project.py
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Download models:
   ```bash
   python download_models.py
   ```

4. Setup calendar integration (optional):
   ```bash
   python setup_calendar.py
   ```

5. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

## Project Structure

```
Project Anton Egon/
├── core/           # Core orchestrator and decision engine
├── audio/          # Audio processing (listener, synthesizer)
├── vision/         # Vision processing (detector, name reader)
├── video/          # Video processing (animator, wardrobe)
├── integration/    # External integrations (calendar, OBS)
├── ui/             # User interfaces (dashboard)
├── memory/         # Memory storage (context, meeting)
├── vault/          # Knowledge vault (documents)
├── assets/         # Media assets (videos, audio)
├── config/         # Configuration files
├── logs/           # Log files
└── models/         # AI models
```

## Phases

- **Phase 1:** Foundation & Data Ingestion
- **Phase 2:** Sensory Layer (Audio, Vision, OCR)
- **Phase 3:** Cognitive Logic & Guardrails
- **Phase 4:** Synthesis & Wardrobe
- **Phase 5:** Integration & Fail-safe

## License

MIT License
"""
    
    readme_path = Path("README.md")
    with open(readme_path, "w") as f:
        f.write(readme)
    
    print(f"✅ Created: README.md")


def main():
    """Main initialization function"""
    print("\n" + "="*80)
    print("  ANTON EGON - PROJECT INITIALIZATION")
    print("="*80)
    print("\nThis script will create the project structure and configuration files.")
    print("Existing files will not be overwritten.\n")
    
    input("Press Enter to continue...")
    
    # Create directory structure
    create_directory_structure()
    
    # Create configuration files
    create_requirements_txt()
    create_env_example()
    create_gitignore()
    create_config_yaml()
    create_config_template()
    create_readme()
    
    print_section("INITIALIZATION COMPLETE")
    print("""
    ✅ Project structure created successfully!
    
    Next steps:
    1. Install dependencies: pip install -r requirements.txt
    2. Download models: python download_models.py
    3. Setup calendar: python setup_calendar.py (optional)
    4. Configure .env file
    5. Start development!
    
    For more information, see README.md
    """)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInitialization cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error during initialization: {e}")
        sys.exit(1)
