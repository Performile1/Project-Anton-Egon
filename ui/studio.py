#!/usr/bin/env python3
"""
Project Anton Egon - The Studio & Harvester
Browser-based recording studio for wardrobe assets, voice calibration,
and passive meeting observation for training data collection.

Architecture:
  - FastAPI routes mounted into web_dashboard.py
  - MediaRecorder API (browser) → WebSocket binary → server saves to disk
  - Teleprompter serves sentences from RECORDING_GUIDE.md
  - Ghost overlay sends previous clip frame for alignment
  - Harvester interfaces with integration/harvester.py for passive observation
"""

import asyncio
import sys
import json
import wave
import struct
import time
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from loguru import logger

# Fix Windows encoding
if sys.platform == 'win32':
    import _io
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ─── Constants from RECORDING_GUIDE.md ──────────────────────────

TARGET_FPS = 20
TARGET_RESOLUTION = (1280, 720)
TARGET_AUDIO_SAMPLE_RATE = 48000
TARGET_AUDIO_BIT_DEPTH = 16
TARGET_AUDIO_CHANNELS = 1
AUDIO_PEAK_DB = -3.0


# ─── Data Models ────────────────────────────────────────────────

class RecordingType(Enum):
    """Types of recording sessions"""
    WARDROBE_IDLE = "wardrobe_idle"
    WARDROBE_ACTION = "wardrobe_action"
    VOICE_SENTENCE = "voice_sentence"
    VOICE_PREROLL = "voice_preroll"
    # Double Capture (Safety: Record each outfit in two versions)
    WARDROBE_PROFESSIONAL = "wardrobe_professional"  # Professional talking (for voice model)
    WARDROBE_SILENT_IDLE = "wardrobe_silent_idle"  # Silent idle (natural movements, looking at screen, blinking, adjusting mic)


class OutfitID(Enum):
    """Outfit identifiers matching wardrobe_manager.py"""
    SHIRT_01 = "outfit_shirt_01"
    SHIRT_02 = "outfit_shirt_02"
    TSHIRT = "outfit_tshirt"
    GLASSES = "outfit_glasses"
    CASUAL = "outfit_casual"


class ActionClipType(Enum):
    """Action clip types matching RECORDING_GUIDE.md"""
    DRINK_WATER = "drink_water"
    CHECK_NOTES = "check_notes"
    NOD_AGREE = "nod_agree"
    THINK_LOOK_UP = "think_look_up"
    LEAN_FORWARD = "lean_forward"
    ADJUST_GLASSES = "adjust_glasses"
    WAVE_HELLO = "wave_hello"


class EmotionType(Enum):
    """Voice emotion categories"""
    NEUTRAL = "neutral"
    ENTHUSIASTIC = "enthusiastic"
    SERIOUS = "serious"
    QUESTIONING = "questioning"
    EMPATHETIC = "empathetic"


class HarvesterMode(Enum):
    """Harvester operation modes"""
    MY_VOICE_ONLY = "my_voice_only"
    CUSTOMER_PROFILES = "customer_profiles"
    FULL_SHADOW = "full_shadow"


# ─── Teleprompter sentences (from RECORDING_GUIDE.md) ──────────

VOICE_SENTENCES = {
    EmotionType.NEUTRAL: [
        "Hej, välkommen till mötet.",
        "Låt oss gå igenom agendan.",
        "Baserat på vår senaste analys ser det lovande ut.",
        "Vi har identifierat tre huvudområden att fokusera på.",
        "Jag skickar en sammanfattning efter mötet.",
        "Om vi tittar på tidplanen...",
        "Det stämmer, vi ligger i fas.",
        "Har ni fått ta del av underlaget?",
        "Vi fortsätter enligt plan.",
        "Tack för den uppdateringen.",
        "Jag noterar det och återkommer.",
        "Absolut, det kan vi ordna.",
        "Vi behöver säkerställa att alla parter är med.",
        "Låt mig kolla det snabbt.",
        "Perfekt, då kör vi på det.",
    ],
    EmotionType.ENTHUSIASTIC: [
        "Det här är riktigt bra resultat!",
        "Fantastiskt, vi har överträffat målen!",
        "Jag är imponerad av teamets arbete.",
        "Det är precis den lösningen vi behöver!",
        "Vilken bra idé, vi kör på det!",
        "Det här kommer göra stor skillnad!",
        "Spot on, exakt rätt approach!",
        "Vi är on track och det ser jättebra ut!",
        "Det var den bästa pitchen jag hört!",
        "Grattis till teamet, riktigt starkt!",
    ],
    EmotionType.SERIOUS: [
        "Vi behöver adressera det här omgående.",
        "Tyvärr visar siffrorna en nedåtgående trend.",
        "Det är viktigt att vi agerar nu.",
        "Jag vill vara transparent med utmaningarna.",
        "Vi har ett gap i budgeten som behöver åtgärdas.",
        "Deadlinen är inte förhandlingsbar.",
        "Det finns risker som vi inte kan ignorera.",
        "Vi behöver ta ett steg tillbaka och utvärdera.",
        "Situationen kräver omedelbar uppmärksamhet.",
        "Jag vill inte skönmåla läget.",
    ],
    EmotionType.QUESTIONING: [
        "Hur ser ni på den tidplanen?",
        "Kan du utveckla det lite mer?",
        "Vad är er uppfattning om budgeten?",
        "Har ni testat den lösningen tidigare?",
        "Vilka alternativ har vi?",
        "Hur påverkar det er leverans?",
        "Vad menar du med det specifikt?",
        "Kan vi förtydliga scope:et?",
        "Finns det en backup-plan?",
        "Stämmer det att deadline är i juni?",
    ],
    EmotionType.EMPATHETIC: [
        "Jag förstår att det är en utmaning.",
        "Det är helt förståeligt att ni känner så.",
        "Vi hittar en lösning tillsammans.",
        "Jag hör vad du säger och det är viktigt.",
        "Ta den tid ni behöver, vi är flexibla.",
    ],
}

PREROLL_CLIPS = [
    {"id": "ack_01", "category": "acknowledgment", "text": "Ja, precis.", "duration_s": 0.6},
    {"id": "ack_02", "category": "acknowledgment", "text": "Jag förstår.", "duration_s": 0.7},
    {"id": "ack_03", "category": "acknowledgment", "text": "Absolut.", "duration_s": 0.5},
    {"id": "ack_04", "category": "acknowledgment", "text": "Mm, exakt.", "duration_s": 0.6},
    {"id": "think_01", "category": "thinking", "text": "Hmm, bra fråga...", "duration_s": 0.9},
    {"id": "think_02", "category": "thinking", "text": "Låt mig se här...", "duration_s": 0.8},
    {"id": "think_03", "category": "thinking", "text": "Bra att du tar upp det.", "duration_s": 0.9},
    {"id": "think_04", "category": "thinking", "text": "Ja, det ska jag kolla...", "duration_s": 1.0},
    {"id": "trans_01", "category": "transition", "text": "Okej, så...", "duration_s": 0.6},
    {"id": "trans_02", "category": "transition", "text": "Ja, alltså...", "duration_s": 0.6},
    {"id": "trans_03", "category": "transition", "text": "Om jag minns rätt...", "duration_s": 0.8},
    {"id": "conf_01", "category": "confirmation", "text": "Absolut, det stämmer.", "duration_s": 0.8},
    {"id": "conf_02", "category": "confirmation", "text": "Ja, precis så.", "duration_s": 0.7},
    {"id": "emp_01", "category": "empathy", "text": "Jag hör vad du säger.", "duration_s": 0.9},
    {"id": "emp_02", "category": "empathy", "text": "Det förstår jag helt och hållet.", "duration_s": 1.1},
]

WARDROBE_CLIPS = [
    {"id": "idle", "name": "Idle Loop", "duration_s": 180, "description": "Sitt still, titta i kameran, naturliga mikrorörelser"},
    {"id": "drink_water", "name": "Dricka vatten", "duration_s": 8, "description": "Lyft glas, drick, ställ tillbaka"},
    {"id": "check_notes", "name": "Kolla anteckningar", "duration_s": 6, "description": "Titta ner, läs, titta upp igen"},
    {"id": "nod_agree", "name": "Nicka instämmande", "duration_s": 3, "description": "Två-tre nickar, ögonkontakt"},
    {"id": "think_look_up", "name": "Tänka (titta upp)", "duration_s": 4, "description": "Titta uppåt, tänk, titta tillbaka"},
    {"id": "lean_forward", "name": "Luta framåt (intresse)", "duration_s": 5, "description": "Luta framåt, intresserat uttryck"},
    {"id": "adjust_glasses", "name": "Justera glasögon", "duration_s": 3, "description": "Justera glasögon, bara outfit_glasses"},
    {"id": "wave_hello", "name": "Vinka hej", "duration_s": 3, "description": "Liten vinkning vid mötesstart"},
]


# ─── Configuration ──────────────────────────────────────────────

class StudioConfig(BaseModel):
    """Configuration for The Studio"""
    # Paths
    video_output_dir: str = Field(default="assets/video", description="Wardrobe video output")
    audio_output_dir: str = Field(default="assets/audio", description="Voice sample output")
    preroll_output_dir: str = Field(default="assets/audio/pre_roll_clips", description="Pre-roll clips output")
    ghost_overlay_dir: str = Field(default="assets/video/ghost_frames", description="Ghost overlay frames")
    
    # Recording specs
    target_fps: int = Field(default=20, description="Target FPS for video recording")
    target_width: int = Field(default=1280, description="Target video width")
    target_height: int = Field(default=720, description="Target video height")
    audio_sample_rate: int = Field(default=48000, description="Audio sample rate")
    
    # Quality thresholds
    min_audio_level_db: float = Field(default=-40.0, description="Minimum audio level (too quiet)")
    max_audio_level_db: float = Field(default=-1.0, description="Maximum audio level (clipping)")
    min_brightness: float = Field(default=0.2, description="Minimum frame brightness (0-1)")
    max_brightness: float = Field(default=0.85, description="Maximum frame brightness (0-1)")


# ─── Studio Backend ─────────────────────────────────────────────

class Studio:
    """
    The Studio & Harvester backend.
    
    Provides:
    1. Teleprompter data (sentences, progress)
    2. MediaRecorder WebSocket receiver (video + audio binary → disk)
    3. Ghost overlay frame serving
    4. Recording progress tracking
    5. Audio level analysis (clipping/peaking detection)
    6. Harvester platform management
    """
    
    def __init__(self, config: StudioConfig = None):
        self.config = config or StudioConfig()
        
        # Ensure output directories
        for d in [self.config.video_output_dir, self.config.audio_output_dir,
                  self.config.preroll_output_dir, self.config.ghost_overlay_dir]:
            Path(d).mkdir(parents=True, exist_ok=True)
        
        # Recording state
        self.is_recording = False
        self.current_recording_type: Optional[RecordingType] = None
        self.current_outfit: Optional[str] = None
        self.current_clip: Optional[str] = None
        self.recording_start_time: Optional[float] = None
        self._recording_ws: Optional[WebSocket] = None
        self._recording_file = None
        self._recording_path: Optional[str] = None
        
        # Progress tracking
        self.progress = self._load_progress()
        
        # Audio analysis
        self.current_audio_level_db: float = -60.0
        self.audio_is_clipping: bool = False
        self.brightness_ok: bool = True
        
        # Harvester state
        self.harvester_active: bool = False
        self.harvester_mode: HarvesterMode = HarvesterMode.MY_VOICE_ONLY
        self.harvester_platform: Optional[str] = None
        
        logger.info("Studio initialized")
    
    # ═══════════════════════════════════════════════════════════════
    # PROGRESS TRACKING
    # ═══════════════════════════════════════════════════════════════
    
    def _load_progress(self) -> Dict[str, Any]:
        """Load recording progress from disk"""
        progress_file = Path("assets/studio_progress.json")
        if progress_file.exists():
            try:
                return json.loads(progress_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        
        # Initialize fresh progress
        progress = {
            "video": {},   # outfit_id → {clip_id: True/False}
            "audio": {},   # emotion → {sentence_index: True/False}
            "preroll": {},  # clip_id → True/False
            "last_updated": None
        }
        
        # Initialize video progress per outfit
        for outfit in OutfitID:
            progress["video"][outfit.value] = {}
            for clip in WARDROBE_CLIPS:
                progress["video"][outfit.value][clip["id"]] = False
        
        # Initialize audio progress per emotion
        for emotion in EmotionType:
            progress["audio"][emotion.value] = {}
            sentences = VOICE_SENTENCES.get(emotion, [])
            for i in range(len(sentences)):
                progress["audio"][emotion.value][str(i)] = False
        
        # Initialize preroll progress
        for clip in PREROLL_CLIPS:
            progress["preroll"][clip["id"]] = False
        
        return progress
    
    def _save_progress(self):
        """Save recording progress to disk"""
        self.progress["last_updated"] = datetime.now(timezone.utc).isoformat()
        progress_file = Path("assets/studio_progress.json")
        progress_file.parent.mkdir(parents=True, exist_ok=True)
        progress_file.write_text(json.dumps(self.progress, indent=2, ensure_ascii=False), encoding="utf-8")
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get summary of recording progress"""
        # Video: count completed clips per outfit
        video_done = 0
        video_total = 0
        video_per_outfit = {}
        for outfit_id, clips in self.progress.get("video", {}).items():
            done = sum(1 for v in clips.values() if v)
            total = len(clips)
            video_done += done
            video_total += total
            video_per_outfit[outfit_id] = {"done": done, "total": total}
        
        # Audio: count completed sentences
        audio_done = 0
        audio_total = 0
        audio_per_emotion = {}
        for emotion, sentences in self.progress.get("audio", {}).items():
            done = sum(1 for v in sentences.values() if v)
            total = len(sentences)
            audio_done += done
            audio_total += total
            audio_per_emotion[emotion] = {"done": done, "total": total}
        
        # Preroll
        preroll_done = sum(1 for v in self.progress.get("preroll", {}).values() if v)
        preroll_total = len(PREROLL_CLIPS)
        
        return {
            "video": {"done": video_done, "total": video_total, "per_outfit": video_per_outfit},
            "audio": {"done": audio_done, "total": audio_total, "per_emotion": audio_per_emotion},
            "preroll": {"done": preroll_done, "total": preroll_total},
            "is_recording": self.is_recording,
            "current_recording": {
                "type": self.current_recording_type.value if self.current_recording_type else None,
                "outfit": self.current_outfit,
                "clip": self.current_clip,
                "elapsed_s": time.time() - self.recording_start_time if self.recording_start_time else 0,
            },
            "audio_level_db": self.current_audio_level_db,
            "audio_clipping": self.audio_is_clipping,
            "brightness_ok": self.brightness_ok,
        }
    
    # ═══════════════════════════════════════════════════════════════
    # TELEPROMPTER
    # ═══════════════════════════════════════════════════════════════
    
    def get_teleprompter_data(self, recording_type: str) -> Dict[str, Any]:
        """
        Get teleprompter data for a recording session.
        
        Args:
            recording_type: "voice_sentence", "voice_preroll", "wardrobe_idle", "wardrobe_action"
        """
        if recording_type == "voice_sentence":
            # Flatten all sentences with emotion tags
            sentences = []
            for emotion in EmotionType:
                for i, text in enumerate(VOICE_SENTENCES.get(emotion, [])):
                    done = self.progress.get("audio", {}).get(emotion.value, {}).get(str(i), False)
                    sentences.append({
                        "index": len(sentences),
                        "emotion": emotion.value,
                        "emotion_index": i,
                        "text": text,
                        "done": done,
                        "filename": f"{emotion.value}_sentence_{i+1:02d}.wav"
                    })
            return {"type": "voice_sentence", "items": sentences, "total": len(sentences)}
        
        elif recording_type == "voice_preroll":
            items = []
            for clip in PREROLL_CLIPS:
                done = self.progress.get("preroll", {}).get(clip["id"], False)
                items.append({
                    "id": clip["id"],
                    "category": clip["category"],
                    "text": clip["text"],
                    "duration_s": clip["duration_s"],
                    "done": done,
                    "filename": f"{clip['id']}.wav"
                })
            return {"type": "voice_preroll", "items": items, "total": len(items)}
        
        elif recording_type in ("wardrobe_idle", "wardrobe_action"):
            items = []
            for clip in WARDROBE_CLIPS:
                if recording_type == "wardrobe_idle" and clip["id"] != "idle":
                    continue
                if recording_type == "wardrobe_action" and clip["id"] == "idle":
                    continue
                items.append({
                    "id": clip["id"],
                    "name": clip["name"],
                    "duration_s": clip["duration_s"],
                    "description": clip["description"],
                })
            return {"type": recording_type, "items": items, "total": len(items)}
        
        return {"type": recording_type, "items": [], "total": 0}
    
    # ═══════════════════════════════════════════════════════════════
    # RECORDING (MediaRecorder → WebSocket → Disk)
    # ═══════════════════════════════════════════════════════════════
    
    def _get_output_path(self, recording_type: str, outfit: str = "", 
                         clip_id: str = "", emotion: str = "", 
                         sentence_index: int = 0) -> str:
        """Determine output file path based on recording type"""
        if recording_type in ("wardrobe_idle", "wardrobe_action"):
            filename = f"{outfit}_{clip_id}.mp4"
            return str(Path(self.config.video_output_dir) / outfit / filename)
        
        elif recording_type == "voice_sentence":
            filename = f"{emotion}_sentence_{sentence_index+1:02d}.wav"
            return str(Path(self.config.audio_output_dir) / "voice_samples" / filename)
        
        elif recording_type == "voice_preroll":
            filename = f"{clip_id}.wav"
            return str(Path(self.config.preroll_output_dir) / filename)
        
        return str(Path(self.config.audio_output_dir) / f"unknown_{int(time.time())}.bin")
    
    async def start_recording(self, recording_type: str, outfit: str = "",
                               clip_id: str = "", emotion: str = "",
                               sentence_index: int = 0) -> Dict[str, Any]:
        """
        Start a recording session. Browser will stream binary via WebSocket.
        
        Returns:
            Session info with output path and expected duration
        """
        if self.is_recording:
            return {"error": "Already recording", "status": "busy"}
        
        output_path = self._get_output_path(recording_type, outfit, clip_id, emotion, sentence_index)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.is_recording = True
        self.current_recording_type = RecordingType(recording_type)
        self.current_outfit = outfit
        self.current_clip = clip_id
        self.recording_start_time = time.time()
        self._recording_path = output_path
        
        # Open file for binary writing
        self._recording_file = open(output_path, 'wb')
        
        logger.info(f"Recording started: {recording_type} → {output_path}")
        
        # Find expected duration
        expected_duration = 0
        if recording_type in ("wardrobe_idle", "wardrobe_action"):
            for clip in WARDROBE_CLIPS:
                if clip["id"] == clip_id:
                    expected_duration = clip["duration_s"]
                    break
        elif recording_type == "voice_preroll":
            for clip in PREROLL_CLIPS:
                if clip["id"] == clip_id:
                    expected_duration = clip["duration_s"]
                    break
        elif recording_type == "voice_sentence":
            expected_duration = 5  # ~5s per sentence
        
        return {
            "status": "recording",
            "output_path": output_path,
            "expected_duration_s": expected_duration,
            "recording_type": recording_type,
        }
    
    async def stop_recording(self) -> Dict[str, Any]:
        """Stop current recording and finalize file"""
        if not self.is_recording:
            return {"error": "Not recording"}
        
        elapsed = time.time() - self.recording_start_time if self.recording_start_time else 0
        
        # Close file
        if self._recording_file:
            self._recording_file.close()
            self._recording_file = None
        
        output_path = self._recording_path
        file_size = Path(output_path).stat().st_size if output_path and Path(output_path).exists() else 0
        
        # Update progress
        self._mark_complete()
        
        # Reset state
        rec_type = self.current_recording_type
        self.is_recording = False
        self.current_recording_type = None
        self.recording_start_time = None
        self._recording_path = None
        
        logger.info(f"Recording stopped: {output_path} ({file_size} bytes, {elapsed:.1f}s)")
        
        return {
            "status": "saved",
            "output_path": output_path,
            "file_size": file_size,
            "duration_s": elapsed,
            "recording_type": rec_type.value if rec_type else None,
        }
    
    def _mark_complete(self):
        """Mark current recording as complete in progress tracker"""
        if not self.current_recording_type:
            return
        
        rt = self.current_recording_type.value
        
        if rt in ("wardrobe_idle", "wardrobe_action"):
            outfit = self.current_outfit or ""
            clip = self.current_clip or ""
            if outfit in self.progress.get("video", {}):
                self.progress["video"][outfit][clip] = True
        
        elif rt == "voice_preroll":
            clip = self.current_clip or ""
            self.progress["preroll"][clip] = True
        
        # voice_sentence marking is handled via explicit API call with emotion + index
        
        self._save_progress()
    
    def mark_sentence_complete(self, emotion: str, sentence_index: int):
        """Mark a voice sentence as complete"""
        if emotion in self.progress.get("audio", {}):
            self.progress["audio"][emotion][str(sentence_index)] = True
            self._save_progress()
    
    async def receive_recording_data(self, websocket: WebSocket):
        """Receive binary data from MediaRecorder via WebSocket"""
        try:
            while self.is_recording:
                data = await websocket.receive_bytes()
                if self._recording_file and data:
                    self._recording_file.write(data)
        except WebSocketDisconnect:
            logger.debug("Recording WebSocket disconnected")
        except Exception as e:
            logger.error(f"Recording data error: {e}")
        finally:
            if self.is_recording:
                await self.stop_recording()
    
    # ═══════════════════════════════════════════════════════════════
    # AUDIO LEVEL ANALYSIS
    # ═══════════════════════════════════════════════════════════════
    
    def analyze_audio_level(self, audio_data: bytes) -> Dict[str, Any]:
        """
        Analyze audio level from raw PCM data.
        Returns dB level and clipping status.
        """
        if len(audio_data) < 4:
            return {"level_db": -60.0, "clipping": False, "too_quiet": True}
        
        try:
            # Parse as 16-bit PCM
            n_samples = len(audio_data) // 2
            samples = struct.unpack(f'<{n_samples}h', audio_data[:n_samples * 2])
            
            import math
            
            # RMS level
            rms = (sum(s * s for s in samples) / n_samples) ** 0.5
            
            if rms < 1:
                level_db = -60.0
            else:
                level_db = 20 * math.log10(rms / 32768.0)
            
            # Peak level
            peak = max(abs(s) for s in samples) if samples else 0
            peak_db = 20 * math.log10(peak / 32768.0) if peak > 0 else -60.0
            
            clipping = peak_db > self.config.max_audio_level_db
            too_quiet = level_db < self.config.min_audio_level_db
            
            self.current_audio_level_db = level_db
            self.audio_is_clipping = clipping
            
            return {
                "level_db": round(level_db, 1),
                "peak_db": round(peak_db, 1),
                "clipping": clipping,
                "too_quiet": too_quiet,
                "ok": not clipping and not too_quiet
            }
        except Exception as e:
            return {"level_db": -60.0, "clipping": False, "too_quiet": True, "error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════
    # GHOST OVERLAY
    # ═══════════════════════════════════════════════════════════════
    
    def get_ghost_frame_path(self, outfit: str) -> Optional[str]:
        """
        Get path to ghost overlay frame for an outfit.
        Returns the first frame of the previous idle recording,
        used for visual alignment when recording new clips.
        """
        ghost_dir = Path(self.config.ghost_overlay_dir)
        ghost_file = ghost_dir / f"{outfit}_ghost.png"
        
        if ghost_file.exists():
            return str(ghost_file)
        
        # Try to extract from existing idle video
        idle_video = Path(self.config.video_output_dir) / outfit / f"{outfit}_idle.mp4"
        if idle_video.exists():
            try:
                import cv2
                cap = cv2.VideoCapture(str(idle_video))
                ret, frame = cap.read()
                cap.release()
                if ret:
                    cv2.imwrite(str(ghost_file), frame)
                    logger.info(f"Ghost frame extracted: {ghost_file}")
                    return str(ghost_file)
            except ImportError:
                logger.debug("OpenCV not available for ghost frame extraction")
        
        return None
    
    # ═══════════════════════════════════════════════════════════════
    # HARVESTER INTEGRATION
    # ═══════════════════════════════════════════════════════════════
    
    async def start_harvester(self, platform: str, mode: str) -> Dict[str, Any]:
        """Start passive observation/harvesting"""
        self.harvester_active = True
        self.harvester_platform = platform
        self.harvester_mode = HarvesterMode(mode)
        
        logger.info(f"Harvester started: {platform} ({mode})")
        
        return {
            "status": "active",
            "platform": platform,
            "mode": mode,
            "message": f"Harvesting from {platform} in {mode} mode"
        }
    
    async def stop_harvester(self) -> Dict[str, Any]:
        """Stop harvesting"""
        platform = self.harvester_platform
        self.harvester_active = False
        self.harvester_platform = None
        
        logger.info("Harvester stopped")
        
        return {
            "status": "stopped",
            "platform": platform,
        }
    
    def get_harvester_status(self) -> Dict[str, Any]:
        """Get harvester status"""
        return {
            "active": self.harvester_active,
            "platform": self.harvester_platform,
            "mode": self.harvester_mode.value if self.harvester_mode else None,
        }
    
    # ═══════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════
    
    def get_status(self) -> Dict[str, Any]:
        """Full studio status"""
        return {
            "progress": self.get_progress_summary(),
            "harvester": self.get_harvester_status(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# ─── FastAPI Router ─────────────────────────────────────────────

def create_studio_router(studio: Studio) -> APIRouter:
    """Create FastAPI router for Studio endpoints"""
    router = APIRouter(prefix="/api/studio", tags=["studio"])
    
    @router.get("/progress")
    async def get_progress():
        """Get recording progress summary"""
        return studio.get_progress_summary()
    
    @router.get("/teleprompter/{recording_type}")
    async def get_teleprompter(recording_type: str):
        """Get teleprompter data for a recording type"""
        return studio.get_teleprompter_data(recording_type)
    
    @router.post("/recording/start")
    async def start_recording(
        recording_type: str,
        outfit: str = "",
        clip_id: str = "",
        emotion: str = "",
        sentence_index: int = 0
    ):
        """Start a recording session"""
        return await studio.start_recording(recording_type, outfit, clip_id, emotion, sentence_index)
    
    @router.post("/recording/stop")
    async def stop_recording():
        """Stop current recording"""
        return await studio.stop_recording()
    
    @router.post("/recording/mark-sentence")
    async def mark_sentence(emotion: str, sentence_index: int):
        """Mark a voice sentence as complete"""
        studio.mark_sentence_complete(emotion, sentence_index)
        return {"status": "marked", "emotion": emotion, "index": sentence_index}
    
    @router.get("/ghost/{outfit}")
    async def get_ghost_frame(outfit: str):
        """Get ghost overlay frame for an outfit"""
        path = studio.get_ghost_frame_path(outfit)
        if path and Path(path).exists():
            return FileResponse(path, media_type="image/png")
        return JSONResponse(status_code=404, content={"error": "No ghost frame available"})
    
    @router.get("/outfits")
    async def get_outfits():
        """Get list of outfits with clip info"""
        outfits = []
        for outfit in OutfitID:
            clips = []
            for clip in WARDROBE_CLIPS:
                done = studio.progress.get("video", {}).get(outfit.value, {}).get(clip["id"], False)
                clips.append({**clip, "done": done})
            outfits.append({"id": outfit.value, "clips": clips})
        return outfits
    
    @router.get("/emotions")
    async def get_emotion_list():
        """Get emotion categories and sentence counts"""
        return {e.value: len(VOICE_SENTENCES.get(e, [])) for e in EmotionType}
    
    @router.post("/harvester/start")
    async def start_harvester(platform: str, mode: str = "my_voice_only"):
        """Start harvester"""
        return await studio.start_harvester(platform, mode)
    
    @router.post("/harvester/stop")
    async def stop_harvester():
        """Stop harvester"""
        return await studio.stop_harvester()
    
    @router.get("/harvester/status")
    async def harvester_status():
        """Get harvester status"""
        return studio.get_harvester_status()
    
    @router.get("/status")
    async def get_status():
        """Full studio status"""
        return studio.get_status()
    
    return router


# ─── WebSocket handler for MediaRecorder binary stream ──────────

async def studio_recording_websocket(websocket: WebSocket, studio: Studio):
    """WebSocket endpoint for receiving MediaRecorder binary data"""
    await websocket.accept()
    logger.info("Studio recording WebSocket connected")
    
    try:
        await studio.receive_recording_data(websocket)
    except Exception as e:
        logger.error(f"Studio WebSocket error: {e}")
    finally:
        if studio.is_recording:
            await studio.stop_recording()


# ─── Test ───────────────────────────────────────────────────────

async def main():
    """Test Studio backend"""
    studio = Studio()
    
    logger.info(f"Status: {json.dumps(studio.get_status(), indent=2, ensure_ascii=False)}")
    
    # Test teleprompter
    tp = studio.get_teleprompter_data("voice_sentence")
    logger.info(f"Voice sentences: {tp['total']} items")
    
    tp2 = studio.get_teleprompter_data("voice_preroll")
    logger.info(f"Pre-roll clips: {tp2['total']} items")
    
    # Test progress
    summary = studio.get_progress_summary()
    logger.info(f"Video: {summary['video']['done']}/{summary['video']['total']}")
    logger.info(f"Audio: {summary['audio']['done']}/{summary['audio']['total']}")
    logger.info(f"Pre-roll: {summary['preroll']['done']}/{summary['preroll']['total']}")


if __name__ == "__main__":
    asyncio.run(main())
