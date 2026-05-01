#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Phase 7.2: The Whisperer
Private communication channel - sends real-time intel to user during meetings
Analyzes counterpart emotions, stress levels, and provides tactical suggestions
"""

import sys
import json
import asyncio
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timezone
from pathlib import Path
from collections import deque
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class WhisperType(Enum):
    """Types of whisper messages"""
    EMOTION_ALERT = "emotion_alert"        # "Lasse ser stressad ut"
    LIE_DETECTION = "lie_detection"        # "Röstanalys: möjlig osanning"
    TACTICAL_TIP = "tactical_tip"          # "Fråga om budgeten nu"
    REMINDER = "reminder"                  # "Glöm inte offerten"
    CONTEXT_RECALL = "context_recall"      # "Lasse nämnde detta förra mötet"
    CORRECTION = "correction"              # "Säg 15% inte 20%"
    WARNING = "warning"                    # "Du har pratat i 3 min utan paus"


class WhisperMessage(BaseModel):
    """A whisper message sent to the user"""
    whisper_id: str
    whisper_type: WhisperType
    message: str
    priority: int = Field(default=5, description="Priority 1-10 (10 = urgent)")
    source: Optional[str] = Field(None, description="Source of the whisper (emotion, context, etc.)")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    read: bool = Field(default=False, description="Has the user read this?")


class WhispererConfig(BaseModel):
    """Configuration for The Whisperer"""
    enable_emotion_alerts: bool = Field(default=True, description="Alert on significant emotion changes")
    enable_tactical_tips: bool = Field(default=True, description="Provide tactical meeting suggestions")
    enable_reminders: bool = Field(default=True, description="Send meeting reminders")
    enable_corrections: bool = Field(default=True, description="Allow in-meeting corrections")
    emotion_change_threshold: float = Field(default=0.3, description="Minimum emotion change to trigger alert")
    stress_threshold: float = Field(default=0.7, description="Stress level to trigger alert")
    max_whispers_per_minute: int = Field(default=3, description="Max whispers per minute to avoid spam")
    whisper_log_dir: str = Field(default="memory/whisper_logs", description="Directory for whisper logs")


class Whisperer:
    """
    The Whisperer - Private Intel Channel
    Sends real-time analysis and tactical suggestions to user during meetings
    """
    
    def __init__(self, config: WhispererConfig, on_whisper: Optional[Callable] = None):
        """
        Initialize The Whisperer
        
        Args:
            config: Whisperer configuration
            on_whisper: Callback when a whisper is sent (for dashboard/phone notification)
        """
        self.config = config
        self.on_whisper = on_whisper
        
        # State
        self.running = False
        self.current_meeting_id: Optional[str] = None
        
        # Whisper queue and history
        self.whisper_queue: deque = deque(maxlen=100)
        self.whisper_history: List[WhisperMessage] = []
        self._whisper_count = 0
        self._last_whisper_time: Optional[datetime] = None
        self._whisper_id_counter = 0
        
        # Emotion tracking per person
        self.emotion_state: Dict[str, Dict[str, Any]] = {}
        
        # User corrections queue
        self.corrections: deque = deque(maxlen=10)
        
        # Whisper log directory
        self.whisper_log_dir = Path(config.whisper_log_dir)
        self.whisper_log_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("The Whisperer initialized")
    
    def start_meeting(self, meeting_id: str):
        """
        Start whispering for a meeting
        
        Args:
            meeting_id: Meeting ID
        """
        self.current_meeting_id = meeting_id
        self.running = True
        self._whisper_count = 0
        self.whisper_history = []
        self.emotion_state = {}
        
        logger.info(f"Whisperer active for meeting: {meeting_id}")
    
    def stop_meeting(self):
        """Stop whispering and save log"""
        if self.current_meeting_id:
            self._save_whisper_log()
        
        self.running = False
        self.current_meeting_id = None
        
        logger.info("Whisperer stopped")
    
    def analyze_emotion(self, person_id: str, person_name: str, emotion: str, confidence: float):
        """
        Analyze emotion change for a person and generate whispers if needed
        
        Args:
            person_id: Person ID
            person_name: Person name
            emotion: Detected emotion
            confidence: Confidence score (0-1)
        """
        if not self.running or not self.config.enable_emotion_alerts:
            return
        
        # Track emotion state
        previous = self.emotion_state.get(person_id, {})
        previous_emotion = previous.get("emotion", "neutral")
        previous_confidence = previous.get("confidence", 0.0)
        
        # Update state
        self.emotion_state[person_id] = {
            "person_name": person_name,
            "emotion": emotion,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Check for significant emotion change
        emotion_change = abs(confidence - previous_confidence)
        
        if emotion != previous_emotion and emotion_change >= self.config.emotion_change_threshold:
            # Generate emotion alert
            if emotion in ["angry", "fear", "sad"] and confidence >= self.config.stress_threshold:
                message = f"⚠️ {person_name} visar tecken på stress ({emotion}, {confidence:.0%} konfidens)"
                self._send_whisper(WhisperType.EMOTION_ALERT, message, priority=8, source="emotion_analysis")
            
            elif emotion == "surprise" and confidence >= 0.6:
                message = f"👀 {person_name} verkar förvånad av något du sa"
                self._send_whisper(WhisperType.EMOTION_ALERT, message, priority=6, source="emotion_analysis")
            
            elif emotion == "happy" and confidence >= 0.7:
                message = f"✅ {person_name} verkar positiv - bra läge att föreslå nästa steg"
                self._send_whisper(WhisperType.TACTICAL_TIP, message, priority=5, source="emotion_analysis")
    
    def analyze_speech_pattern(self, person_name: str, speech_rate: float, pitch_variation: float):
        """
        Analyze speech patterns for potential deception indicators
        
        Args:
            person_name: Person name
            speech_rate: Speaking rate (words per minute)
            pitch_variation: Voice pitch variation
        """
        if not self.running:
            return
        
        # Simple heuristic: high pitch variation + fast speech = potential stress/deception
        if pitch_variation > 0.8 and speech_rate > 180:
            message = f"🔍 {person_name}: Röstanalys indikerar möjlig nervositet (hög tonvariation + snabbt tal)"
            self._send_whisper(WhisperType.LIE_DETECTION, message, priority=7, source="voice_analysis")
    
    def send_tactical_tip(self, tip: str, priority: int = 6):
        """
        Send a tactical tip to the user
        
        Args:
            tip: Tactical tip message
            priority: Priority level (1-10)
        """
        if not self.running:
            return
        
        self._send_whisper(WhisperType.TACTICAL_TIP, f"💡 {tip}", priority=priority, source="tactical")
    
    def send_reminder(self, reminder: str, priority: int = 5):
        """
        Send a reminder to the user
        
        Args:
            reminder: Reminder message
            priority: Priority level (1-10)
        """
        if not self.running:
            return
        
        self._send_whisper(WhisperType.REMINDER, f"📌 {reminder}", priority=priority, source="reminder")
    
    def send_context_recall(self, context: str, priority: int = 7):
        """
        Send context recall from previous meetings
        
        Args:
            context: Context information
            priority: Priority level (1-10)
        """
        if not self.running:
            return
        
        self._send_whisper(WhisperType.CONTEXT_RECALL, f"🧠 {context}", priority=priority, source="context_recall")
    
    def add_correction(self, correction: str):
        """
        Add a user correction to be injected into the agent's next response
        
        Args:
            correction: Correction text (e.g., "Säg 15% rabatt, inte 20%")
        """
        self.corrections.append({
            "text": correction,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "used": False
        })
        
        logger.info(f"Correction added: {correction}")
    
    def get_pending_correction(self) -> Optional[str]:
        """
        Get next pending correction
        
        Returns:
            Correction text or None
        """
        for correction in self.corrections:
            if not correction["used"]:
                correction["used"] = True
                return correction["text"]
        
        return None
    
    def send_warning(self, warning: str, priority: int = 8):
        """
        Send a warning to the user
        
        Args:
            warning: Warning message
            priority: Priority level (1-10)
        """
        if not self.running:
            return
        
        self._send_whisper(WhisperType.WARNING, f"⚠️ {warning}", priority=priority, source="warning")
    
    def _send_whisper(self, whisper_type: WhisperType, message: str, priority: int = 5, source: Optional[str] = None):
        """
        Send a whisper message
        
        Args:
            whisper_type: Type of whisper
            message: Whisper message
            priority: Priority level (1-10)
            source: Source of the whisper
        """
        # Rate limiting
        now = datetime.now(timezone.utc)
        if self._last_whisper_time:
            elapsed = (now - self._last_whisper_time).total_seconds()
            if elapsed < 60.0 / self.config.max_whispers_per_minute and priority < 9:
                logger.debug(f"Whisper rate-limited: {message[:50]}...")
                return
        
        self._whisper_id_counter += 1
        whisper = WhisperMessage(
            whisper_id=f"whisper_{self._whisper_id_counter}",
            whisper_type=whisper_type,
            message=message,
            priority=priority,
            source=source
        )
        
        # Add to queue and history
        self.whisper_queue.append(whisper)
        self.whisper_history.append(whisper)
        self._whisper_count += 1
        self._last_whisper_time = now
        
        # Trigger callback
        if self.on_whisper:
            self.on_whisper(whisper.dict())
        
        logger.info(f"Whisper [{whisper_type.value}]: {message}")
    
    def get_unread_whispers(self) -> List[WhisperMessage]:
        """
        Get all unread whispers
        
        Returns:
            List of unread whispers
        """
        unread = [w for w in self.whisper_history if not w.read]
        return sorted(unread, key=lambda w: w.priority, reverse=True)
    
    def mark_read(self, whisper_id: str):
        """
        Mark a whisper as read
        
        Args:
            whisper_id: Whisper ID
        """
        for whisper in self.whisper_history:
            if whisper.whisper_id == whisper_id:
                whisper.read = True
                return
    
    def _save_whisper_log(self):
        """Save whisper log for the meeting"""
        if not self.current_meeting_id:
            return
        
        log_file = self.whisper_log_dir / f"{self.current_meeting_id}_whispers.json"
        
        log_data = {
            "meeting_id": self.current_meeting_id,
            "total_whispers": len(self.whisper_history),
            "whispers": [w.dict() for w in self.whisper_history],
            "emotion_state": self.emotion_state
        }
        
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Whisper log saved: {log_file}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get whisperer status
        
        Returns:
            Status dictionary
        """
        return {
            "running": self.running,
            "current_meeting": self.current_meeting_id,
            "total_whispers": len(self.whisper_history),
            "unread_count": len([w for w in self.whisper_history if not w.read]),
            "pending_corrections": len([c for c in self.corrections if not c["used"]]),
            "tracked_persons": len(self.emotion_state)
        }


def main():
    """Test The Whisperer"""
    from loguru import logger
    
    logger.add("logs/whisperer_{time}.log", rotation="10 MB")
    
    def on_whisper(whisper_data):
        logger.info(f"📨 WHISPER: {whisper_data['message']}")
    
    # Create whisperer
    config = WhispererConfig()
    whisperer = Whisperer(config, on_whisper=on_whisper)
    
    # Start meeting
    whisperer.start_meeting("meeting_001")
    
    # Simulate emotion analysis
    whisperer.analyze_emotion("person_1", "Lasse", "angry", 0.85)
    whisperer.analyze_emotion("person_2", "Sara", "happy", 0.90)
    
    # Send tactical tip
    whisperer.send_tactical_tip("Fråga om budgeten nu medan Sara är positiv")
    
    # Send reminder
    whisperer.send_reminder("Glöm inte att nämna offerten för Q3")
    
    # Send context recall
    whisperer.send_context_recall("Lasse nämnde problem med ledtiderna förra mötet")
    
    # Add correction
    whisperer.add_correction("Säg 15% rabatt, inte 20%")
    
    # Get unread whispers
    unread = whisperer.get_unread_whispers()
    logger.info(f"Unread whispers: {len(unread)}")
    
    # Get status
    status = whisperer.get_status()
    logger.info(f"Whisperer status: {status}")
    
    # Stop meeting
    whisperer.stop_meeting()
    
    logger.info("Whisperer test complete")


if __name__ == "__main__":
    main()
