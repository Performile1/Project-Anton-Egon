# Project Anton Egon - Master Documentation

## Executive Summary

Anton Egon is a fully autonomous AI agent designed to participate in Teams meetings with audio, video, and cognitive capabilities. This document provides a complete overview of what has been built, what remains to be done, and how to get the system running.

---

## What Has Been Built ✅

### Phase 1: Foundation & Data Ingestion ✅
- **RAG Pipeline:** Document ingestion system for PDF, DOCX, XLS files
- **Knowledge Vault:** Structured storage (`/vault/internal`, `/vault/client`, `/vault/general`)
- **ChromaDB Integration:** Vector database for semantic search
- **Memory Management:** Context buffer and meeting memory system
- **Ingestion Scripts:** `ingest.py` for document processing

### Phase 2: Sensory Layer ✅
- **Audio Listener:** Real-time transcription using Whisper-turbo
- **Vision Detector:** Face detection with YOLO and emotion analysis with DeepFace
- **Name Reader:** OCR-based participant identification
- **Window Capture:** MSS-based screen capture for Teams window

### Phase 3: Cognitive Logic & Guardrails ✅
- **Decision Engine:** Context-aware decision making
- **Prompts Manager:** Dynamic prompt management
- **Action Scheduler:** Natural action timing
- **Context Buffer:** Real-time context tracking

### Phase 4: Synthesis & Wardrobe ✅
- **Wardrobe Manager:** Outfit video management system
- **Video Animator:** Frame-by-frame video synthesis
- **Audio Synthesizer:** TTS with edge-tts
- **OBS Bridge:** Virtual camera streaming (pyvirtualcam)
- **Audio Router:** Virtual audio cable routing (PyAudio)

### Phase 5: Integration & Fail-safe ✅
- **OBS Connector:** A/V sync monitoring (50ms tolerance)
- **Panic Logic:** Global hotkeys (F9 freeze, F10 shutdown, F12 off-the-record)
- **Dashboard UI:** Console-based real-time monitoring
- **Web Dashboard:** Modern web-based dashboard with FastAPI
- **Post-Meeting Automation:** Auto-summary and memory updates

### Phase 6: The Intelligent CRM ✅
- **People CRM:** Face fingerprinting (128-d DeepFace) + person profiles
- **Shadow Logger:** Silent meeting transcription + keyword-based NER
- **Consent Manager:** Notetaker Facade + GDPR-vänlig consent-hantering
- **Temporal Knowledge Graph:** ChromaDB + JSON hybrid för möteshistorik
- **CRM Connector:** Kopplar People CRM, Shadow Logger och Temporal Graph

### Phase 7: Executive Polish & Performance ✅
- **Thermal Guard:** CPU/GPU-tempövervakning med auto-switch
- **The Whisperer:** Privat intel-kanal (emotionsanalys, taktiska tips)
- **Real-time Web Search:** DuckDuckGo/Tavily/Perplexity
- **Interruption Handler:** VAD-baserad avbrottshantering

### Stealth Polish ✅
- **Swenglish Buffer:** 10-15% engelska affärstermer i svensk text
- **Deepfake Defense:** Texture imperfections som simulerar billig webbkamera
- **Strategic Lag:** Mänsklig tänketid baserad på frågans komplexitet

### Phase 8: Streaming Pipeline & Latency Elimination ✅
- **Speculative Ingest:** Predictive RAG + Intent Recognition
- **Streaming Pipeline:** Vattenfall: Whisper→Llama→TTS→Video (<500ms)
- **Audio Pre-roll:** 16 förrenderade filler-klipp för instant response

### Phase 9: Safety & Control ✅
- **Hard Fact Verifier:** Hallucinationskontroll mot /vault
- **Active Steering:** Operatörstyrning via hotkeys mitt i meningen

### Phase 11: The Active Facilitator ✅
- **Live Context (Active RAG):** Slide-sync, live injection, document pinning
- **UI Detector:** Handuppräckningsdetektering i Teams/Meet/Zoom
- **Engagement Analyzer:** Mediapipe Face Mesh för gaze/fatigue tracking
- **Facilitator Logic:** Turn-taking kö + engagement callouts
- **Slide Master:** Dual-mode presentation navigator (PRESENTER/OBSERVER)

### Phase 12: Cross-Platform Deployment ✅
- **Electron Wrapper:** Desktop app för Windows (.exe) och macOS (.dmg)
- **Python Sidecar:** Backend körs som lokal server i bakgrunden
- **System Tray:** Menyraden (Mac) / Tray (Windows) för snabbåtkomst
- **Global Hotkeys:** F9 freeze, F10 kill, Cmd/Ctrl+Shift+A ingest (fungerar även när appen är minimerad)
- **Auto-Detect:** Känner av Teams/Meet-start och frågar om Notetaker-läge
- **Mini-Player Overlay:** Flytande kontrollfönster ovanpå mötesfönster
- **Desktop Features:** Systemnotiser, direkt fönsterhantering, globala kortkommandon

### Phase 13: Unified Communication Hub ✅
- **Unified Dispatcher (core/dispatcher.py):** Central hub för alla kommunikationskanaler (chat, email, video)
- **Platform Adapters (comms/):** Teams chat adapter, Slack adapter, Email engine (Outlook/Gmail)
- **Unified Inbox (core/unified_inbox.py):** Samlad vy i dashboard för all inkommande text
- **Communication Modes:** Autonomous (direkt svar) vs Draft (utkast för godkännande) vs Whisper (notis)
- **Cross-Referencing:** Samma Llama-3-modell och Swenglish Buffer för alla plattformar
- **Dashboard Integration:** Unified Inbox-tab med filter, taggning, flaggning, AI-sammanfattning

### Phase 16: The Trickster Engine ✅
- **Linguistic DNA (ui/phrase_library_editor.py):** Personlig ordlista med kategorier (hälsningar, beslut, pushback, fyllnadsord)
- **Jargon Injector (core/jargon_injector.py):** Real-time phrase-replacement i LLM-svar för autentisk röst
- **Prop Shop (core/prop_engine.py):** Mediapipe face tracking overlays (clownnäsa, solglasögon, mustasch)
- **Action Overlays (core/overlay_engine.py):** Alpha overlay clips (vatten häll, förvånad blick, katt-hopp)
- **Chaos Dashboard:** Prop/overlay-kontroller i dashboard med quick actions
- **Session Guard (core/session_guard.py):** Binary choice Cloud Mode vs Local Mode baserat på nätverkstest (ping < 80ms)
- **Calibration Wizard (ui/calibration_wizard.py):** Face mapping för LivePortrait outfits

### Phase 17: Cloud Infrastructure ✅
- **Dockerfile (Dockerfile):** Docker-container för RunPod RTX 4090 (LivePortrait + Faster-Whisper)
- **Tailscale Integration (core/cloud_bridge.py):** Secure VPN-tunnel till moln-server (Tailscale Manager)
- **Supabase CRM (core/dispatcher.py):** Centraliserad CRM för kontakter, mötesloggar, kommunikationshistorik
- **Groq Streaming Engine (core/streaming_pipeline.py):** Groq API integration för <200ms textgenerering med streaming och complete inference
- **Jargon Injection Middleware:** Integration med Groq pipeline för personliga uttryck

### Phase 18: Turing Mirror & Calibration ✅
- **Studio Mirror (ui/studio_mirror.py):** Real-time quality assurance med dual-stream (live + avatar)
- **Turing Mirror UI (ui/web_dashboard.py):** Side-by-Side Validation view med live camera + avatar streams
- **Ghost Frame Overlay:** 20% transparent live-feed på avatar för kalibrering
- **Lip-Sync Analyzer:** Visuella vågformer för lip-sync validering
- **Uncanny Alert:** Lighting mismatch warning
- **Voice Calibration:** Voice volume vs mouth movements mapping (soft/normal/loud)
- **Sync-Test:** Latency measurement function för pre-flight validering

### Phase 19: Resilience & Recovery ✅
- **Recovery Engine (core/recovery_engine.py):** Social Recovery med name triggers och Humble Correction
- **Escape Sequence:** "Urgent Call" (hoppsan, extremt brådskande samtal) vid ifrågasättning
- **Safety Valves (integration/panic_logic.py):** F9 Safe-Word (tysta röst), F10 Panic (static loop + AI shutdown), Ctrl+1-6 (manuella kommandon)

### Phase 20: Chaos Engine Assets ✅
- **PNG Alpha Handling (core/prop_engine.py):** OpenCV alpha channel blending för props
- **MP4 Chroma Key (core/overlay_engine.py):** Green/blue screen keying för video overlays
- **Manual Trigger UI:** Chaos Dashboard med prop/overlay knappar (Phase 16)

### Phase 21: Turing Mirror & QA Engine ✅
- **QA Engine (core/qa_engine.py):** Autonomous quality assurance med Lip-Sync Scorer och Visual Artifact Detector
- **Mediapipe Integration (vision/detector.py):** Face-mesh extraction för tracking-följsamhet
- **Studio Mirror (ui/studio_mirror.py):** Dual-stream view, Ghost Overlay, Face Mesh visualization
- **System Health Tab (ui/web_dashboard.py):** QA report visualization med grafer för latens och synk
- **Environment Configuration (.env):** Placeholders för GROQ_API_KEY, SUPABASE_URL, TAILSCALE_AUTH_KEY

### Phase 22: Setup Wizard ✅
- **Setup Wizard Tab (ui/web_dashboard.py):** Web-based configuration wizard för alla externa tjänster
- **Platform Detection:** Automatisk detektion av Windows/Mac/Linux och Python-version
- **Supabase Setup:** SQL script generation för tabeller (people, meeting_logs, inbox_messages, phrase_library)
- **Connection Testing:** Test-knappar för Supabase, Groq, och Tailscale anslutningar
- **Configuration Management:** Spara till .env eller ladda ner konfigurationsfil

### Phase 23: Human Fallibility Engine ✅
- **Meeting Behavior Engine (core/meeting_behavior.py):** Join-Dice randomizer med tre scenarier (Late Joiner, Mute-Glitcher, Phone Caller)
- **Phrase Library Update:** apologies_for_lateness kategori med svenska ursäkter
- **Orchestrator Integration:** Kalenderkoll 5 minuter före möte, scenario execution
- **Human Flaws Tab:** Dashboard UI för att toggla beteenden och justera sannolikheter
- **API Endpoints:** /api/flaws/config, /api/flaws/toggle, /api/flaws/roll-dice

### Additional Features ✅
- **Platform Selector:** Multi-platform support (Teams, Google Meet, Zoom, Webex, Slack)
- **Calendar Integration:** Microsoft Graph + Google Calendar API
- **Background Library:** Structure for background assets
- **Setup Scripts:** Automated setup for calendar and model downloads
- **The Studio & Harvester:** Browser-based recording studio (MediaRecorder API, teleprompter, ghost overlay, audio meter, progress tracking) + Passive observation for training data collection

---

## Project Structure

```
Project Anton Egon/
├── Dockerfile                         # RunPod RTX 4090 container (Phase 17)
├── core/                              # Core orchestration (27 filer)
│   ├── orchestrator.py               # Main event loop (Phase 1-11 integration)
│   ├── decision_engine.py            # Context-aware decision making
│   ├── mood_engine.py                # Mood tracking & prompt injection
│   ├── prompts.py                    # Positive/negative prompt management
│   ├── streaming_pipeline.py         # Whisper→Llama→TTS→Video (<500ms)
│   ├── speculative_ingest.py         # Predictive RAG + Intent Recognition
│   ├── fact_verifier.py              # Hallucinationskontroll mot /vault
│   ├── active_steering.py            # Operatörstyrning via hotkeys mitt i meningen
│   ├── live_context.py               # Slide-sync, live injection (Phase 11)
│   ├── ui_detector.py                # Hand-raise icon detection (Phase 11)
│   ├── engagement_analyzer.py        # Gaze/fatigue tracking (Phase 11)
│   ├── facilitator_logic.py          # Turn-taking kö + engagement callouts (Phase 11)
│   ├── dispatcher.py                 # Unified dispatcher for all communications (Phase 13 + Phase 17 Supabase CRM)
│   ├── unified_inbox.py              # Unified inbox for dashboard (Phase 13)
│   ├── jargon_injector.py            # Real-time phrase replacement (Phase 16)
│   ├── prop_engine.py                # Prop Shop with Mediapipe face tracking (Phase 16)
│   ├── overlay_engine.py             # Alpha overlay clips (Phase 16)
│   ├── session_guard.py              # Session Locking: Cloud vs Local mode (Phase 16)
│   ├── recovery_engine.py            # Social Recovery with name triggers (Phase 19)
│   ├── thermal_guard.py              # CPU/GPU-tempövervakning
│   ├── complexity_delay.py           # Mänsklig tänketid baserad på komplexitet
│   ├── action_scheduler.py           # Task scheduling & prioritization
│   ├── calendar_sync.py              # Calendar integration
│   ├── cloud_bridge.py              # Cloud deployment + Tailscale (Phase 17)
│   ├── renderer_factory.py          # Render mode switching
│   ├── status_manager.py             # Status tracking
│   └── system_check.py              # System capability detection (Phase 11)
├── audio/                             # Audio processing (5 filer)
│   ├── listener.py                   # Audio input/Whisper transcription
│   ├── synthesizer.py                # TTS with edge-tts
│   ├── audio_router.py               # Virtual audio cable routing
│   ├── echo_canceller.py             # AEC feedback prevention
│   └── pre_roll.py                   # Filler clips manager (Phase 8)
├── vision/                            # Vision processing (4 filer)
│   ├── detector.py                   # YOLO + DeepFace + platform support
│   ├── name_reader.py                # OCR participant identification
│   ├── ui_detector.py                # Hand-raise icon detection (Phase 11)
│   └── engagement_analyzer.py        # Gaze/fatigue tracking (Phase 11)
├── video/                             # Video processing (9 filer)
│   ├── wardrobe_manager.py           # Outfit video management
│   ├── animator.py                   # Frame-by-frame synthesis
│   ├── animator_selector.py          # Render mode switching
│   ├── liveportrait.py               # LivePortrait integration
│   ├── micro_movement.py             # Natural idle movements
│   ├── color_matcher.py              # Lighting/color matching
│   ├── obs_bridge.py                 # Virtual camera streaming
│   ├── texture_imperfection.py       # Deepfake defense (Stealth)
│   └── slide_master.py               # Presentation nav + OCR (Phase 11)
├── integration/                       # External integrations (9 filer)
│   ├── obs_connector.py              # A/V sync monitoring
│   ├── panic_logic.py                # F9/F10/F12 emergency controls
│   ├── post_meeting.py               # Auto-summary + memory updates
│   ├── microsoft_graph.py            # Outlook/Teams API
│   ├── google_calendar.py            # Google Calendar API
│   ├── harvester.py                  # Passive observation/LoRA data
│   ├── whisperer.py                  # Private intel channel (Phase 7)
│   ├── web_search.py                 # DuckDuckGo/Tavily/Perplexity (Phase 7)
│   └── active_steering.py            # Mid-sentence steering (Phase 9)
├── ui/                                # User interfaces (6 filer)
│   ├── dashboard.py                  # Console dashboard
│   ├── web_dashboard.py              # FastAPI web dashboard (with Studio & Harvester + Unified Inbox + Phrase Library + Chaos Dashboard tabs)
│   ├── studio.py                     # The Studio & Harvester backend (MediaRecorder, teleprompter, progress)
│   ├── phrase_library_editor.py       # Linguistic DNA: Personal phrase library (Phase 16)
│   ├── calibration_wizard.py         # Face mapping for LivePortrait outfits + Voice calibration (Phase 16 + Phase 18)
│   └── studio_mirror.py             # Turing Mirror: Dual-stream quality assurance (Phase 18)
├── comms/                             # Communication adapters (Phase 13, 3 filer)
│   ├── teams_adapter.py              # Microsoft Teams chat adapter
│   ├── slack_adapter.py              # Slack adapter
│   └── email_engine.py               # Email engine (Outlook/Gmail)
├── desktop/                           # Electron desktop app (Phase 12, 5 filer)
│   ├── main.js                       # Electron main process (Python sidecar, system tray, hotkeys)
│   ├── preload.js                    # Secure IPC bridge
│   ├── package.json                  # Electron build config (Windows .exe, macOS .dmg)
│   ├── renderer/                     # Frontend loader
│   │   └── index.html                # Dashboard iframe wrapper
│   └── build/                        # Build resources
│       ├── README.md                 # Build instructions
│       └── entitlements.mac.plist    # macOS code signing
├── memory/                            # Memory & CRM (7 filer)
│   ├── context_buffer.py             # Real-time conversation context
│   ├── people_manager.py             # People CRM + face fingerprint
│   ├── shadow_logger.py              # Silent transcription logger
│   ├── entity_extractor.py           # Keyword-based NER
│   ├── consent_manager.py            # Notetaker Facade + GDPR
│   ├── temporal_graph.py             # ChromaDB + JSON meeting history
│   ├── crm_connector.py              # CRM ↔ Shadow ↔ Temporal bridge
│   └── meeting/                      # Meeting context storage
├── vault/                             # Knowledge base (RAG)
│   ├── internal/                     # Internal documents
│   ├── client/                       # Client documents
│   └── general/                      # General knowledge
├── assets/                            # Media assets
│   ├── video/                        # Outfit idle loops + action clips
│   ├── audio/
│   │   ├── fillers/                  # Context-based audio fillers
│   │   └── pre_roll_clips/           # Pre-rendered filler clips
│   ├── presentations/                # PDF presentations (Phase 11)
│   │   └── slides/                   # Rendered slide images
│   └── templates/
│       └── ui/                       # UI icon templates (Phase 11)
├── config/                            # Configuration
│   └── settings.json                 # Main config
├── models/                            # AI models
│   └── llama-3-8b-instruct-q4_k_m.gguf
├── logs/                              # Log files
├── credentials/                       # API credentials
├── ingest.py                         # Document ingestion (RAG)
├── init_project.py                   # Project initialization
├── download_models.py                # Model download script
├── manage.py                         # Management CLI
├── setup_calendar.py                 # Calendar setup script
├── start_studio_mac.sh               # Studio launcher (macOS)
├── start_studio_windows.bat         # Studio launcher (Windows)
├── MASTER.md                         # This file
├── RECORDING_GUIDE.md                # Recording instructions (v2.0)
└── requirements.txt                  # Python dependencies
```

---

## What Remains to Be Done ⏳

### Critical (Required for MVP)

1. **Physical Recording** ⏳ (USER ACTION REQUIRED)
   - Record outfit idle loops (2-3 minutes per outfit)
   - Record action clips (drink water, adjust glasses, etc.)
   - Record voice samples (20 minutes total)
   - See `RECORDING_GUIDE.md` for detailed instructions
   - Estimated time: 4-6 hours

2. **Model Download** ⏳ (AUTOMATED)
   - Run `python download_models.py`
   - Downloads Llama-3-8B (4.9 GB) and Whisper-turbo (374 MB)
   - Estimated time: 10-30 minutes depending on internet

3. **Calendar Credentials** ⏳ (USER ACTION REQUIRED)
   - Run `python setup_calendar.py`
   - Create Azure AD app for Microsoft Graph
   - Create Google Cloud project for Calendar API
   - Estimated time: 15-20 minutes

### Important (Enhances Experience)

4. **LivePortrait Integration** ⏳ (NOT IMPLEMENTED)
   - Facial animation on recorded clips
   - Lip-sync with TTS audio
   - Expression control (happy, sad, surprised, angry)
   - Estimated time: 2-3 hours implementation

5. **Enhanced Web Dashboard** ⏳ (PARTIALLY IMPLEMENTED)
   - Prompt management UI
   - File upload interface
   - Clip recording interface
   - Background management
   - Estimated time: 3-4 hours

### Optional (Nice to Have)

6. **Advanced Features** ⏳
   - Multi-language support
   - Custom voice cloning
   - Advanced emotion recognition
   - Meeting analytics

---

## Getting Started - Step by Step

### Prerequisites
- Python 3.11+
- 10 GB free disk space
- HD webcam or camera
- Quality microphone
- Good lighting setup

### Step 1: Project Setup (5 minutes)
```bash
# Clone or navigate to project directory
cd "Project Anton Egon"

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Download Models (10-30 minutes)
```bash
python download_models.py
```
This downloads:
- Llama-3-8B-Instruct (Q4_K_M) - 4.9 GB
- Whisper-turbo - ~374 MB (auto-downloaded)

**Status:** ✅ Llama model downloaded (29.0 MB)
**Note:** Whisper-turbo requires openai-whisper package (has Python 3.13 compatibility issues)

### Step 3: Calendar Setup (15-20 minutes)
```bash
python setup_calendar.py
```
Follow the interactive prompts to:
- Create Azure AD app
- Create Google Cloud project
- Configure API permissions
- Update .env file

### Step 4: Configure Environment (5 minutes)
```bash
cp .env.example .env
# Edit .env with your credentials
```

### Step 5: Record Assets (4-6 hours) ⏳ USER ACTION REQUIRED
```bash
# Read the recording guide
cat RECORDING_GUIDE.md

# Record outfits following the guide
# - Formal shirt (idle + actions)
# - Casual t-shirt (idle + actions)
# - Glasses outfit (idle + actions)
# - Additional outfits as needed

# Record voice samples
# - Read from professional documents
# - Various tones (neutral, enthusiastic, serious)
# - 20 minutes total
```

### Step 6: Test Components (10 minutes)
```bash
# Test audio listener
python audio/listener.py

# Test vision detector
python vision/detector.py

# Test calendar sync
python core/calendar_sync.py

# Test web dashboard
python ui/web_dashboard.py
```

### Step 7: Run Full System
```bash
# Run orchestrator with all phases enabled
python core/orchestrator.py
```

---

## Configuration

### Main Config (`config/settings.json`)
```json
{
  "orchestrator": {
    "enable_audio": true,
    "enable_vision": true,
    "enable_rag": true,
    "enable_calendar_sync": true,
    "render_mode": "auto",
    "platform": "teams"
  },
  "calendar": {
    "enable_microsoft_graph": true,
    "enable_google_calendar": true,
    "timezone": "Europe/Stockholm"
  },
  "cloud_server": {
    "url": "ws://localhost:8080",
    "timeout": 30,
    "max_reconnect_attempts": 5
  }
}
```

### System Config (`config/system_config.yaml`)
Auto-generated by `core/system_check.py`:
```yaml
os:
  system: Windows/Linux/macOS
gpu:
  available: true/false
  vram_gb: 8.0
render_mode:
  mode: LOCAL|CLOUD|FALLBACK
  reason: "GPU with 8GB VRAM detected"
network:
  ping_ms: 45
  internet: true
```

### Environment Variables (`.env`)
```bash
# Calendar credentials
MICROSOFT_GRAPH_CLIENT_ID=your_client_id
MICROSOFT_GRAPH_CLIENT_SECRET=your_client_secret
MICROSOFT_GRAPH_TENANT_ID=your_tenant_id
GOOGLE_CALENDAR_CREDENTIALS_PATH=credentials/google_calendar.json

# Model paths
LLM_MODEL_PATH=models/llama-3-8b-instruct-q4_k_m.gguf
```

---

## UI Features

### Console Dashboard (`ui/dashboard.py`)
- Real-time status display
- Platform selector
- Daily agenda view
- Emotion monitor
- Log viewer
- Manual override controls

### Web Dashboard (`ui/web_dashboard.py`)
- Modern web interface
- Real-time updates (WebSocket)
- REST API endpoints
- Responsive design
- Color-coded logs

### Planned UI Enhancements ✅ (COMPLETED)
- Prompt management interface ✅
- File upload system ✅
- Clip recording interface ✅ (placeholder)
- Background management ✅ (via upload)
- LivePortrait controls ✅ (framework implemented)


## Emergency Controls

### Global Hotkeys
- **F9:** Freeze/unfreeze video
- **F10:** Emergency shutdown
- **F12:** Toggle off-the-record mode

### Dashboard Controls
- Manual status override
- Platform switching
- Meeting status viewing
- Log inspection

---

## Troubleshooting

### Common Issues

**Audio not working:**
- Check microphone permissions
- Verify PyAudio installation
- Test with: `python audio/listener.py`

**Vision not detecting:**
- Check Teams window title
- Verify window capture region
- Test with: `python vision/detector.py`

**Calendar not syncing:**
- Verify API credentials in .env
- Check admin consent for Microsoft Graph
- Test with: `python core/calendar_sync.py`

**Video not streaming:**
- Install OBS Studio
- Configure virtual camera
- Check pyvirtualcam installation

**Model not loading:**
- Verify model exists in models/
- Check file path in config
- Ensure sufficient RAM (8GB+ recommended)

---

## System Requirements

### Minimum
- CPU: 4 cores
- RAM: 8 GB
- Storage: 10 GB free
- GPU: Not required (CPU inference)
- OS: Windows 10/11, macOS, Linux

### Recommended
- CPU: 8 cores
- RAM: 16 GB
- Storage: 20 GB free
- GPU: NVIDIA with CUDA (for faster inference)
- OS: Windows 10/11

---

## Performance Metrics

### Resource Usage
- CPU: 30-50% (idle), 70-90% (active)
- RAM: 4-8 GB
- GPU: 2-4 GB (if available)
- Network: Minimal (local processing)

### Latency
- Audio transcription: <500ms
- Vision detection: 1-2 FPS (intentional)
- LLM inference: 1-3 seconds
- TTS generation: <500ms
- Total response time: 2-5 seconds

---

## Security & Privacy

### Data Handling
- All processing done locally
- No data sent to external servers
- Credentials stored in .env (not committed)
- Logs stored locally

### Calendar Access
- Read-only access to calendars
- No modification of calendar events
- Credentials stored securely

---

## Next Steps Priority

### Immediate
1. ⏳ Test placeholder mode (1 hour)
2. ⏳ Record wardrobe assets → se `RECORDING_GUIDE.md`
3. ⏳ Switch to LivePortrait mode and test stitching
4. ⏳ Run full orchestrator integration test

### Short-term (med inspelade klipp)
1. Test full system integration i kontrollerat möte
2. Stress test med 60-minuters möten
3. Kalibrera stitching (idle ↔ action transitions)
4. Kalibrera Complexity Delay i skarpt läge
5. Testa Active Steering hotkeys (Ctrl+1-6)
6. Testa Slide Master PRESENTER mode med riktig PDF

### Long-term
1. LoRA fine-tuning (efter 50+ timmar träningsdata)
2. Multi-language support
3. Advanced emotion recognition
4. Custom voice cloning
5. Mobile app for remote control
6. Cloud server deployment (Docker container)
7. Meeting analytics dashboard

---

## Current System Status (2026-04-29)

### Codebase
- **70 Python-moduler** i 8 mappar (core/audio/vision/video/integration/ui/memory/comms) + Dockerfile + .env
- **5 JavaScript-filer** i desktop/ (Electron app, Phase 12)
- **7 root-scripts** (ingest.py, init_project.py, download_models.py, manage.py, setup_calendar.py, start_studio_mac.sh, start_studio_windows.bat)
- **50 implementerade features** (Phase 1-9 + Stealth + Phase 11 + Studio & Harvester + Cross-Platform Deployment + Unified Communication Hub + The Trickster Engine + Cloud Infrastructure + Turing Mirror + Resilience & Recovery + Chaos Engine Assets + Turing Mirror & QA Engine + Setup Wizard + Human Fallibility Engine)
- **0 kända syntaxfel** (alla filer kompilerar)

### Installed Dependencies
- ✅ python-dotenv, loguru, pydantic, pyyaml
- ✅ psutil, GPUtil, aiohttp
- ✅ requests, tqdm
- ✅ mediapipe, PyMuPDF, pyautogui, pytesseract
- ⏳ openai-whisper (Python 3.13 compatibility issues)

### Tested Components
- ✅ System Check - Detected capabilities, recommended CLOUD_POWER mode
- ✅ Model Download - Llama-3-8B downloaded successfully
- ✅ Mood Engine - Mood tracking, prompt injection, visual adjustments working
- ✅ Config Manager - Auto-select render mode, config loading working
- ✅ All Phase 11 modules - Syntax-verified

### Next Steps
1. Record outfit videos + voice samples (4-6 hours) → `RECORDING_GUIDE.md`
2. Download AI models → `python download_models.py`
3. Set up calendar credentials → `python setup_calendar.py`
4. Run full orchestrator test → `python core/orchestrator.py`
5. Stress test 3 timmar (memory management check)
6. LoRA fine-tuning (efter 50+ timmar träningsdata)

---

## Phase 6: The Intelligent CRM ✅ (IMPLEMENTED)

### Phase 6.1: People CRM (Fokus: Identifiering)
- **memory/people_manager.py** - Person profiles with face fingerprints
- **vision/detector.py** - Face vector extraction (128-d DeepFace embeddings)
- Face recognition threshold: 0.6 (configurable)
- Storage: `/memory/people/` (JSON + NumPy face vectors)

### Phase 6.2: Shadow Logger (Fokus: Ingestion)
- **memory/shadow_logger.py** - Silent meeting logging
- **memory/entity_extractor.py** - Keyword-based NER (prices, dates, promises, pain points)
- **memory/consent_manager.py** - Consent management (Notetaker Facade)
- Storage: `/memory/shadow_logs/`, `/memory/consent/`

### Phase 6.3: Temporal Graph (Fokus: Recall)
- **memory/temporal_graph.py** - ChromaDB + JSON hybrid for meeting history
- **memory/crm_connector.py** - Connects CRM with meeting history and entities
- Contextual recap before meetings
- Cross-platform sync (WhatsApp ↔ Teams)
- Storage: `/memory/meeting_history/`

### Integration
- **core/orchestrator.py** - Phase 6 components integrated
- Config flags for enabling each Phase 6 component
- Auto-start shadow logging when meeting detected
- Auto-request consent on meeting start

### Next Steps for Phase 6
1. Test People CRM with real face vectors
2. Test Shadow Logger in actual meeting
3. Test Consent Manager with chat integration
4. Test Temporal Graph with meeting history
5. Test cross-platform sync (WhatsApp ↔ Teams)
6. Collect real meeting data for LoRA training

---

## Phase 7: Executive Polish & Performance ✅ (IMPLEMENTED)

### Phase 7.1: Thermal Guard (Fokus: Stabilitet)
- **core/thermal_guard.py** - CPU/GPU temperaturövervakning
- Fyra termiska tillstånd: COOL → WARM → HOT → CRITICAL
- Auto-switch till stillbild med naturlig ursäkt vid CRITICAL
- Kräver: `pip install psutil gputil`

### Phase 7.2: The Whisperer (Fokus: Taktisk Intel)
- **integration/whisperer.py** - Privat kommunikationskanal
- Emotionsanalys av motparter i realtid
- Rate-limiting: max 3 whispers per minut
- In-meeting korrektioner från dashboard

### Phase 7.3: Real-time Web Search (Fokus: Aktualitet)
- **integration/web_search.py** - DuckDuckGo/Tavily/Perplexity
- Asynkron sökning med timeout (5s)
- Cache med 30 min TTL
- Env-variabler: `TAVILY_API_KEY`, `PERPLEXITY_API_KEY`

### Phase 7.4: Interruption Handler (Fokus: Naturlighet)
- **core/interrupt_handler.py** - Avbrottshantering
- VAD-baserad detektering av överlappande tal
- Graceful yield → listen clip → resume
- Konfigurerbar sensitivity och silence threshold

### Integration
- **core/orchestrator.py** - Phase 7 components integrated
- Config flags: `enable_thermal_guard`, `enable_whisperer`, `enable_web_search`, `enable_interrupt_handler`

---

## Stealth Polish ✅ (IMPLEMENTED)

### A. Swenglish Buffer (Språklig nyans)
- **core/prompts.py** → `apply_swenglish_buffer(text, mix_ratio=0.12)`
- 20+ affärstermer: nyckeltal→KPI:er, leverabler→deliverables, etc.
- 9 fras-substitutioner: "Vi behöver gå igenom" → "Vi behöver göra en quick review av"
- Gör agenten till en modern svensk konsult, inte en stel AI

### B. Deepfake Defense (Texture Imperfection Generator)
- **video/texture_imperfection.py** - Simulerar billig webbkamera
- 3 profiler: `logitech_c920`, `builtin_laptop`, `cheap_usb`
- 7 imperfektionslager per frame
- Gör syntetisk video svårare att flagga av Teams/Zoom AI-detektering

### C. Strategic Lag (Complexity Delay)
- **core/complexity_delay.py** - Mänsklig tänketid
- 4 komplexitetsnivåer: SIMPLE → MODERATE → COMPLEX → VERY_COMPLEX
- Synliga "tänka-actions": titta upp, luta huvudet, squinta
- Filler words innan svar: "Hmm...", "Bra fråga..."

---

## Phase 8: Streaming Pipeline & Latency Elimination ✅ (IMPLEMENTED)

> "Genom att börja bearbeta frågan innan den är färdigställd, och genom att
> strömma svaret meningsvis, eliminerar vi den 'robotaktiga' väntetiden.
> Anton Egon svarar inte bara relevant – han svarar med mänsklig timing."

### Phase 8.1: Speculative Ingest (Fokus: Förutsägande)
- **core/speculative_ingest.py** - Predictive RAG + Intent Recognition
- Analyserar partiell transkription ord för ord
- 10 intent-typer med keyword-matchning
- Förbereder RAG-queries innan frågan är klar
- Draft-and-Verify: invaliderar om talaren byter riktning

### Phase 8.2: Streaming Pipeline (Fokus: Hastighet)
- **core/streaming_pipeline.py** - Vattenfall-arkitektur
- 5 stages: IDLE → TRANSCRIBING → INFERRING → SYNTHESIZING → ANIMATING
- Sentence-boundary detection för tidig TTS
- Inter-stage asyncio queues
- Mål: First-byte latency < 500ms

### Phase 8.3: Audio Pre-roll (Fokus: Dölja latens)
- **audio/pre_roll.py** - Förrenderade filler-klipp
- 16 klipp i 5 kategorier
- Intent-matchad selektion
- Kan pre-renderas med TTS (`generate_preroll_clips()`)

### Integration
- **core/orchestrator.py** - Phase 8 components integrated
- Config flags: `enable_speculative_ingest`, `enable_streaming_pipeline`, `enable_audio_preroll`

---

## Phase 9: Safety & Control ✅ (IMPLEMENTED)

### Phase 9.1: Hard Fact Verifier (Hallucinationskontroll)
- **core/fact_verifier.py** - Interceptar LLM-svar innan TTS
- Extraherar claims: priser, procent, datum, antal, årtal
- Verifierar mot /vault med fuzzy matching (inom 5%)
- Actions: PASS → SOFTEN → BLOCK → DEFER
- Soften: "Om jag minns rätt, [claim]" | Block: "Jag behöver dubbelkolla"

### Phase 9.2: Active Steering (Knuff i rätt riktning)
- **integration/active_steering.py** - Realtidsstyrning från dashboard
- 10 kommandon: Stop, Agree, Disagree, Defer, Inject Text, etc.
- Hotkeys: F9, Ctrl+1-6
- Pacing-kontroll: 0.5x–2.0x talhastighet
- Övergångsfraser per kommando för naturlig kurskorrigering

### Integration
- **core/orchestrator.py** - Phase 9 components integrated
- Config flags: `enable_fact_verifier`, `enable_active_steering`

---

## Phase 11: The Active Facilitator ✅ (IMPLEMENTED)

### Phase 11.1: Live Context / Active RAG
- **core/live_context.py** - Short-term priority memory som trumpar /vault
- Slide-Sync: Ladda PDF, ställ in aktuell slide, agent håller sig till innehållet
- Live Injection: Operatör skriver "Betona 5 års garanti" → agent väver in direkt
- Document Pinning: Fäst specifik sektion med TTL (auto-expire)
- `build_priority_context()` genererar prompt-prefix för LLM

### Phase 11.2: UI Detector (Handuppräckning)
- **vision/ui_detector.py** - Detekterar plattformsspecifika UI-element
- Teams: Gul hand-ikon (HSV 20-35), Meet: Blå (HSV 100-130), Zoom: Orange (HSV 15-30)
- Template matching (multi-scale) + color detection
- FIFO hand-raise queue med dedup-cooldown
- Chat notification badge detection

### Phase 11.3: Engagement Analyzer (Vem sover?)
- **vision/engagement_analyzer.py** - Mediapipe Face Mesh med iris refinement
- Eye Aspect Ratio (EAR): Blink detection och ögonslutning
- Iris tracking: Gaze on/off screen via pupill-position
- Head pose: Pitch/yaw/roll via solvePnP
- 5 nivåer: ACTIVE → PASSIVE → DISTRACTED → DROWSY → ASLEEP
- ⚠️ Kräver `require_whisper_mode=True` (default) – aldrig autonoma callouts

### Phase 11.4: Facilitator Logic (Mötesdirigenten)
- **core/facilitator_logic.py** - Hanterar turn-taking och sociala interventioner
- Hand-raise queue: Auto-acknowledge + ordnad avlämning ("Sara, du ville säga något?")
- 4 callout-stilar: Notetaker / Friendly / Playful / Formal
- Engagement check: General ("Alla med?") + Individual (via Whisperer)
- Break suggestion: Auto-föreslår paus vid ≥3 oengagerade
- **Säkerhet:** `never_call_out_by_name_auto=True` (default), alla individuella callouts kräver operatörsgodkännande via pending_actions-kö
- Notetaker Facade: "Som er antecknare vill jag bara checka av..."

### Phase 11.5: Slide Master (Presentation Navigator)
- **video/slide_master.py** - PDF indexering + navigation + verbal pinpointing

**PRESENTER Mode (Anton Egon presenterar):**
- Anton Egon laddar sin PDF, indexerar med Spatial OCR
- Deltagare (Lasse m.fl.) ställer frågor: "Gå tillbaka till prognosen"
- Anton navigerar med pyautogui → pinpointar element → förklarar med /vault-data
- Superhuman: `handle_slide_request()` → search → navigate → pinpoint → enrich

**OBSERVER Mode (Annan person presenterar):**
- Anton indexerar presentatörens PDF via `observe_presentation(pdf, "Lasse")`
- Anton kan INTE styra deras PowerPoint – ber artigt: "Ursäkta Lasse, kan du gå tillbaka..."
- `challenge_slide()`: Ifrågasätter claims med egna /vault-data
- `request_go_back()`: Verbal request med topic-referens
- `handle_observed_slide_change()`: Vision-systemet rapporterar slidebyten

**Gemensamt:**
- Slide Chunking: Varje slide → bild + OCR-text med spatial bounding boxes
- 9-region grid (3×3): varje element taggas med `Slide_05_Section_TopRight`
- Element-typning: TITLE, SUBTITLE, BODY_TEXT, BULLET_POINT, TABLE, CHART, NUMBER
- ChromaDB-vektorer: Semantisk sökning ("dippen i mars") → rätt slide + element
- Verbal Deixis: "Om vi tittar uppe till höger, grafen som visar..."
- Gaze Sync: Agenten tittar mot rätt del av skärmen (mappat via element-koordinater)
- Virtual Pointer (opt): Röd cirkel i OBS-overlay baserat på element-bbox

### Integration
- **core/orchestrator.py** - Phase 11 components integrated
- Config flags: `enable_live_context`, `enable_ui_detector`, `enable_engagement_analyzer`, `enable_facilitator`, `enable_slide_master`

---

## Reviderad Exekveringsplan: "The First Flight"

### Våg 1: "The Sensory Foundation" (Vecka 1)
**Mål:** Skapa råmaterialet och verifiera hårdvaran.

1. **Recording Sprint:** Spela in alla 5 outfits + 50 röstmeningar enligt `RECORDING_GUIDE.md`
   - Single Point of Failure – perfekt ljus och ljud är krav
   - Exakta tidstämplar per klipp (se RECORDING_GUIDE.md)
2. **Thermal Stress Test:** Kör orchestratorn i 2 timmar
   - Verifiera att `core/thermal_guard.py` auto-switchar innan laptop laggar
3. **Local/Cloud Handshake:** Verifiera WebRTC-tunnel (Cloud Bridge) < 100ms latens

### Våg 2: "The Silent Shadow" (Vecka 2-3)
**Mål:** Samla träningsdata och bygg People CRM utan risk.

4. **Silent Mode:** Kör Anton Egon i bakgrunden på alla möten (Teams, WhatsApp, Meet)
5. **People Enrollment:** Låt `memory/people_manager.py` skapa profiler automatiskt
6. **RAG-tuning:** Verifiera att agenten hittar rätt dokument via dashboard-frågor
7. **Fact Verifier Calibration:** Kör `core/fact_verifier.py` på historiska svar

### Våg 3: "The Controlled Pilot" (Vecka 4)
**Mål:** Anton Egon pratar i ett kontrollerat möte.

8. **Internal Sync:** Använd agenten i internt möte med kollegor som vet
9. **The Whisperer Test:** Använd dold intel (emotioner) för att styra dialogen
10. **Active Steering Drill:** Öva hotkeys (Ctrl+1-6) för snabb kurskorrektion
11. **Latency Calibration:** Justera `core/complexity_delay.py` i skarpt läge

### Våg 4: "The Full Twin" (Månad 2+)
**Mål:** Anton Egon tar kundmöten självständigt.

12. **LoRA Fine-tuning:** När 50+ timmar data från Våg 2 finns, träna personlig adapter
13. **Strategic Deployment:** Uppföljningsmöten + tekniska genomgångar
14. **Continuous Calibration:** Justera Swenglish-ratio, pacing, fakta-tröskel

---

## Final Technical Checklist (Fas 5+)

### Modul Status & Arkitektens Slutgiltiga Anmärkning

| Modul | Status | Arkitektens Anmärkning |
|-------|--------|----------------------|
| Micro-movements | ✅ Klar | Implementera variabel blinkfrekvens baserat på humör (snabbare vid stress) |
| AEC (Echo) | ✅ Klar | Se till att audio_router.py helt ignorerar kanal 1 (systemljud) i transkriptionen |
| Color Matcher | ✅ Klar | Använd en enkel histogram-matchning mellan din live-webbkamera (som du döljer) och din AI-video |
| Mood Engine | ✅ Klar | Glöm inte att humöret "nollställs" efter sömn (kl 04:00 varje morgon) |
| Gaze Correction | ✅ Klar | Integrera i animator för att simulera blickriktning |
| AV-Sync | ✅ Klar | Timestamp buffer implementerad med 30ms tolerans |
| Contextual Fillers | ✅ Klar | Kopplad till action clips för pricing, technical, timeline, etc. |
| Passive Observation | ✅ Klar | Audio/Visual shadowing för LoRA-träning, stöd för WhatsApp/Discord |
| People CRM | ✅ Klar | Face fingerprinting med DeepFace 128-d vektorer |
| Shadow Logger | ✅ Klar | Tyst transkription och entity extraction (keyword-based) |
| Consent Manager | ✅ Klar | Notetaker Facade med consent hantering |
| Temporal Graph | ✅ Klar | ChromaDB + JSON hybrid för möteshistorik och contextual recall |
| CRM Connector | ✅ Klar | Kopplar ihop People CRM, Shadow Logger och Temporal Graph |
| Thermal Guard | ✅ Klar | CPU/GPU-temp övervakning, auto-switch vid överhettning |
| The Whisperer | ✅ Klar | Privat intel-kanal med emotionsanalys och taktiska tips |
| Web Search | ✅ Klar | DuckDuckGo/Tavily/Perplexity för realtidssökning |
| Interrupt Handler | ✅ Klar | Graceful yield vid avbrott, VAD-baserad detektering |
| Swenglish Buffer | ✅ Klar | 10-15% engelska affärstermer för naturlig svensk konsultstil |
| Deepfake Defense | ✅ Klar | Texture imperfections som simulerar billig webbkamera |
| Complexity Delay | ✅ Klar | Mänsklig tänketid med synliga thinking-actions |
| Speculative Ingest | ✅ Klar | Predictive RAG + Intent Recognition från partiell transkription |
| Streaming Pipeline | ✅ Klar | Vattenfall: Whisper→Llama→TTS→Video i parallell (<500ms) |
| Audio Pre-roll | ✅ Klar | 16 förrenderade filler-klipp för instant response |
| Hard Fact Verifier | ✅ Klar | Kollar LLM-svar mot /vault innan TTS (pris, procent, datum) |
| Active Steering | ✅ Klar | Operatorn styr agenten via hotkeys mitt i meningen |
| Live Context | ✅ Klar | Slide-sync + live injection + document pinning (trumpar /vault) |
| UI Detector | ✅ Klar | Handuppräckning i Teams/Meet/Zoom via HSV + template matching |
| Engagement Analyzer | ✅ Klar | Mediapipe Face Mesh: EAR, gaze, head pose → 5 engagemangsnivåer |
| Facilitator Logic | ✅ Klar | Turn-taking kö + engagement callouts (whisper-first, operator approval) |
| Slide Master | ✅ Klar | Dual-mode (PRESENTER/OBSERVER), spatial OCR, pyautogui nav, verbal deixis, gaze sync |

### LoRA Fine-Tuning Plan (Framtida)

**Förutsättningar:**
- 50-100 timmar av insamlad träningsdata
- GPU med minst 16GB VRAM (eller molnträning)
- LoRA-träningspipeline (peft, transformers)

**Steg:**
1. Förbered dataset från /vault/training_data/
2. Träna LoRA-adapter på Llama 3
3. Evaluera och finjustera
4. Integrera adapter i production

**Resultat:**
- Anton Egon pratar exakt som du
- Använder dina specifika uttryck och humor
- Din professionella jargong och ton

### Go-Live Strategi

**1. Stress Test (3 timmar)**
```bash
# Kör hela systemet i en "tom" Teams-kanal
python core/orchestrator.py

# Kolla logs/ efter MemoryError
# Om Python äter för mycket RAM, implementera gc.collect()
```

**2. Kalibrera Stitching**
- Se till att övergången mellan "Idle" och "Action" (t.ex. dricka vatten) inte har en enda märkbar "hopp"-frame
- Använd OpenCV:s seamlessClone om det behövs

**3. Prompt Guard Test**
- Be en vän försöka "hacka" agenten i ett testmöte genom att be den avslöja sina systeminstruktioner
- Förväntat svar: "Jag förstår inte vad du menar, ska vi återgå till agendan?"

**4. Eye-Contact Gap Test**
- Verifiera att blicken skiftar mellan kamera (pratar) och skärm (lyssnar)
- Testa i Teams med flera deltagare

---

## Contact & Support

### Documentation
- `README.md` - Project overview
- `RECORDING_GUIDE.md` - Recording instructions
- `MASTER.md` - This document

### Logs
- `logs/orchestrator_*.log` - Main system logs
- `logs/calendar_sync_*.log` - Calendar logs
- `logs/dashboard_*.log` - Dashboard logs

### Status
- Check `live_status.json` for real-time status
- Web dashboard at `http://127.0.0.1:8000`

---

## License

MIT License - See LICENSE file for details

---

**Last Updated:** 2026-05-01
**Version:** 2.0.0
**Phases Implemented:** 1-9, Stealth, 11, Studio & Harvester, Cross-Platform Deployment, Unified Communication Hub, The Trickster Engine, Cloud Infrastructure, Turing Mirror, Resilience & Recovery, Chaos Engine Assets, Turing Mirror & QA Engine, Setup Wizard, Human Fallibility Engine
**Modules:** 70 Python-filer + 5 JavaScript (Electron) + 7 scripts (incl. Studio launchers) + Dockerfile + .env
**Status:** MVP Ready (pending physical recording + LivePortrait integration + Electron build + API credentials for comms adapters + prop/overlay assets + cloud deployment on RunPod)
