# Which Python Files to Run - Quick Guide

## Immediate Setup (One-time)

### 1. Project Initialization
```bash
python init_project.py
```
**Purpose:** Create directory structure and configuration files
**Status:** Run once at project start

### 2. System Capability Detection
```bash
python core/system_check.py
```
**Purpose:** Detect GPU, VRAM, CPU, RAM, network latency
**Output:** `config/system_config.yaml` with recommended render mode
**Status:** Run once, or when hardware changes

### 3. Model Downloads
```bash
python download_models.py
```
**Purpose:** Download Llama-3-8B (4.9 GB) and Whisper-turbo (374 MB)
**Output:** Models in `models/` directory
**Status:** Run once, or when models need update

### 4. Calendar Setup (Optional)
```bash
python setup_calendar.py
```
**Purpose:** Interactive setup for Microsoft Graph and Google Calendar API
**Output:** API credentials in `.env` file
**Status:** Run once, or when credentials change

---

## Core System Files (Main Operation)

### 5. Orchestrator (Main System)
```bash
python core/orchestrator.py
```
**Purpose:** Main event loop that runs the entire Anton Egon system
**Components:** Audio, Vision, Decision Engine, Video, Calendar, Mood
**Status:** Run to start the full system

### 6. Web Dashboard (Alternative UI)
```bash
python ui/web_dashboard.py
```
**Purpose:** Modern web-based dashboard for monitoring
**URL:** http://127.0.0.1:8000
**Status:** Run instead of orchestrator for web UI

---

## Testing & Development

### 7. Individual Component Tests

**Test Audio Listener:**
```bash
python audio/listener.py
```

**Test Vision Detector:**
```bash
python vision/detector.py
```

**Test Calendar Sync:**
```bash
python core/calendar_sync.py
```

**Test Mood Engine:**
```bash
python core/mood_engine.py
```

**Test System Check:**
```bash
python core/system_check.py
```

---

## Data Ingestion (RAG Pipeline)

### 8. Document Ingestion
```bash
python ingest.py
```
**Purpose:** Ingest PDF/DOCX/XLS files into ChromaDB
**Usage:** Add documents to `/vault/` directory, then run
**Status:** Run when adding new documents

### 9. Memory Management
```bash
python manage.py
```
**Purpose:** CLI tool for managing ChromaDB memory
**Commands:** list, purge, stats
**Status:** Run to manage stored documents

---

## Recording & Assets

### 10. Voice Recording Script
**File:** `VOICE_RECORDING_SCRIPT.md`
**Purpose:** Guide for recording voice samples
**Status:** Read and follow for voice recording (manual process)

### 11. Video Recording Guide
**File:** `RECORDING_GUIDE.md`
**Purpose:** Guide for recording outfit videos
**Status:** Read and follow for video recording (manual process)

---

## Recommended Startup Sequence

### First Time Setup (Run in order):
1. `python init_project.py`
2. `python core/system_check.py`
3. `python download_models.py`
4. `python setup_calendar.py` (optional)
5. `python ingest.py` (if you have documents to add)

### Daily Operation:
1. `python core/orchestrator.py` (for full system)
   OR
   `python ui/web_dashboard.py` (for web UI)

---

## Summary

**Essential Files to Run:**
- `init_project.py` - One-time setup
- `core/system_check.py` - One-time hardware detection
- `download_models.py` - One-time model download
- `core/orchestrator.py` - Main system (run daily)

**Optional Files:**
- `setup_calendar.py` - Calendar integration
- `ingest.py` - Document ingestion
- `ui/web_dashboard.py` - Alternative UI
- `manage.py` - Memory management

**Manual Processes:**
- Voice recording (follow `VOICE_RECORDING_SCRIPT.md`)
- Video recording (follow `RECORDING_GUIDE.md`)
