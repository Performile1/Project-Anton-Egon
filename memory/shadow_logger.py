#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Phase 6.2: Shadow Logger
Silent meeting logging with continuous transcription and entity extraction
"""

import sys
import json
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

# Sprint 4: Supabase integration
try:
    from integration.supabase_client import supabase_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# GDPR Auto-Redact
import re


class AutoRedact:
    """
    GDPR-compliant PII masking for meeting logs
    Automatically redacts sensitive information before storage
    """
    
    # Patterns for PII detection
    PATTERNS = {
        'credit_card': r'\b(?:\d[ -]*?){13,16}\b',  # Credit card numbers
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',  # SSN format
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email addresses
        'phone': r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b',  # Phone numbers
        'password': r'\b(password|pass|pwd)\s*[:=]\s*\S+',  # Password patterns
        'api_key': r'\b(api[_-]?key|secret|token)\s*[:=]\s*[A-Za-z0-9_-]{20,}\b',  # API keys
        'ip_address': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',  # IP addresses
    }
    
    def __init__(self, enabled: bool = True):
        """
        Initialize Auto-Redact
        
        Args:
            enabled: Whether redaction is enabled
        """
        self.enabled = enabled
        self.redaction_counts = {key: 0 for key in self.PATTERNS.keys()}
        
        logger.info(f"Auto-Redact initialized (enabled: {enabled})")
    
    def redact_text(self, text: str) -> str:
        """
        Redact PII from text
        
        Args:
            text: Input text
        
        Returns:
            Redacted text
        """
        if not self.enabled:
            return text
        
        redacted = text
        
        for pattern_type, pattern in self.PATTERNS.items():
            matches = re.findall(pattern, redacted, re.IGNORECASE)
            if matches:
                self.redaction_counts[pattern_type] += len(matches)
                # Replace with placeholder
                if pattern_type == 'email':
                    redacted = re.sub(pattern, '[REDACTED_EMAIL]', redacted, flags=re.IGNORECASE)
                elif pattern_type == 'credit_card':
                    redacted = re.sub(pattern, '[REDACTED_CARD]', redacted, flags=re.IGNORECASE)
                elif pattern_type == 'ssn':
                    redacted = re.sub(pattern, '[REDACTED_SSN]', redacted, flags=re.IGNORECASE)
                elif pattern_type == 'phone':
                    redacted = re.sub(pattern, '[REDACTED_PHONE]', redacted, flags=re.IGNORECASE)
                elif pattern_type == 'password':
                    redacted = re.sub(pattern, '[REDACTED_PASSWORD]', redacted, flags=re.IGNORECASE)
                elif pattern_type == 'api_key':
                    redacted = re.sub(pattern, '[REDACTED_API_KEY]', redacted, flags=re.IGNORECASE)
                elif pattern_type == 'ip_address':
                    redacted = re.sub(pattern, '[REDACTED_IP]', redacted, flags=re.IGNORECASE)
        
        return redacted
    
    def redact_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact PII from dictionary values
        
        Args:
            data: Input dictionary
        
        Returns:
            Redacted dictionary
        """
        if not self.enabled:
            return data
        
        redacted = {}
        for key, value in data.items():
            if isinstance(value, str):
                redacted[key] = self.redact_text(value)
            elif isinstance(value, dict):
                redacted[key] = self.redact_dict(value)
            elif isinstance(value, list):
                redacted[key] = [self.redact_text(item) if isinstance(item, str) else item for item in value]
            else:
                redacted[key] = value
        
        return redacted
    
    def get_redaction_stats(self) -> Dict[str, int]:
        """
        Get redaction statistics
        
        Returns:
            Dictionary with redaction counts per PII type
        """
        return self.redaction_counts.copy()
    
    def reset_stats(self):
        """Reset redaction statistics"""
        self.redaction_counts = {key: 0 for key in self.PATTERNS.keys()}


# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class ShadowLoggerConfig(BaseModel):
    """Configuration for Shadow Logger"""
    logs_dir: str = Field(default="memory/shadow_logs", description="Directory for shadow logs")
    auto_save: bool = Field(default=True, description="Auto-save logs after each entry")
    max_transcriptions_per_session: int = Field(default=1000, description="Max transcriptions per session")
    enable_auto_redact: bool = Field(default=True, description="Enable GDPR Auto-Redact")


class ShadowLogger:
    """
    Shadow Logger for silent meeting logging
    Logs transcriptions, entities, and participants without interrupting the meeting
    """
    
    def __init__(self, config: ShadowLoggerConfig):
        """
        Initialize Shadow Logger
        
        Args:
            config: Shadow Logger configuration
        """
        self.config = config
        
        # Directory structure
        self.logs_dir = Path(config.logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Current session
        self.current_session_id: Optional[str] = None
        self.session_data: Optional[Dict[str, Any]] = None
        
        # GDPR Auto-Redact
        self.auto_redact = AutoRedact(enabled=config.enable_auto_redact)
        
        logger.info("Shadow Logger initialized")
    
    def start_session(self, platform: str, title: Optional[str] = None) -> str:
        """
        Start a new logging session
        
        Args:
            platform: Platform name (teams, meet, whatsapp, discord)
            title: Meeting title (optional)
        
        Returns:
            Session ID
        """
        session_id = f"{platform}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Create session directory
        session_dir = self.logs_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize session data
        self.session_data = {
            "session_id": session_id,
            "platform": platform,
            "title": title,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": None,
            "transcriptions": [],
            "entities": [],
            "participants": [],
            "summary": None
        }
        
        self.current_session_id = session_id
        
        logger.info(f"Started shadow logging session: {session_id}")
        
        return session_id
    
    def log_transcription(self, text: str, speaker_id: Optional[str] = None, timestamp: Optional[str] = None, vvad_data: Optional[Dict[str, Any]] = None):
        """
        Log transcription entry with V-VAD speaker attribution
        
        Args:
            text: Transcribed text
            speaker_id: Speaker identifier (optional)
            timestamp: Timestamp (optional, defaults to now)
            vvad_data: Visual Voice Activity Detection data (lip movement, active speaker)
        """
        if not self.current_session_id or not self.session_data:
            logger.warning("No active session to log transcription")
            return
        
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        
        # GDPR: Redact PII from transcription before storage
        redacted_text = self.auto_redact.redact_text(text)
        
        transcription_entry = {
            "text": redacted_text,
            "speaker_id": speaker_id,
            "timestamp": timestamp,
            # Sprint 4: V-VAD speaker attribution
            "vvad_speaker": vvad_data.get("active_speaker_idx") if vvad_data else None,
            "lip_movement_score": vvad_data.get("movement_score") if vvad_data else None,
            "confidence": vvad_data.get("confidence") if vvad_data else None
        }
        
        self.session_data["transcriptions"].append(transcription_entry)
        
        # Check max limit
        if len(self.session_data["transcriptions"]) > self.config.max_transcriptions_per_session:
            logger.warning(f"Reached max transcriptions limit ({self.config.max_transcriptions_per_session})")
        
        # Auto-save if enabled
        if self.config.auto_save:
            self._save_transcriptions()
        
        logger.debug(f"Logged transcription: {redacted_text[:50]}...")
    
    def log_entities(self, entities: List[Dict[str, Any]]):
        """
        Log extracted entities
        
        Args:
            entities: List of entity dictionaries
        """
        if not self.current_session_id or not self.session_data:
            logger.warning("No active session to log entities")
            return
        
        for entity in entities:
            entity_entry = {
                "type": entity.get("type"),
                "text": entity.get("text"),
                "value": entity.get("value"),
                "context": entity.get("context"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            self.session_data["entities"].append(entity_entry)
        
        # Auto-save if enabled
        if self.config.auto_save:
            self._save_entities()
        
        logger.debug(f"Logged {len(entities)} entities")
    
    def log_participant(self, person_id: str, name: str, join_time: Optional[str] = None):
        """
        Log participant
        
        Args:
            person_id: Person ID
            name: Person name
            join_time: Join time (optional, defaults to now)
        """
        if not self.current_session_id or not self.session_data:
            logger.warning("No active session to log participant")
            return
        
        if join_time is None:
            join_time = datetime.now(timezone.utc).isoformat()
        
        # Check if participant already logged
        for participant in self.session_data["participants"]:
            if participant["person_id"] == person_id:
                logger.debug(f"Participant already logged: {name}")
                return
        
        participant_entry = {
            "person_id": person_id,
            "name": name,
            "join_time": join_time,
            "leave_time": None
        }
        
        self.session_data["participants"].append(participant_entry)
        
        # Auto-save if enabled
        if self.config.auto_save:
            self._save_participants()
        
        logger.info(f"Logged participant: {name}")
    
    def log_participant_leave(self, person_id: str, leave_time: Optional[str] = None):
        """
        Log participant leaving
        
        Args:
            person_id: Person ID
            leave_time: Leave time (optional, defaults to now)
        """
        if not self.current_session_id or not self.session_data:
            logger.warning("No active session to log participant leave")
            return
        
        if leave_time is None:
            leave_time = datetime.now(timezone.utc).isoformat()
        
        # Find participant and update leave time
        for participant in self.session_data["participants"]:
            if participant["person_id"] == person_id:
                participant["leave_time"] = leave_time
                logger.debug(f"Logged participant leave: {person_id}")
                return
        
        logger.warning(f"Participant not found: {person_id}")
    
    def end_session(self) -> Optional[Dict[str, Any]]:
        """
        End current session and generate summary
        
        Returns:
            Session summary
        """
        if not self.current_session_id or not self.session_data:
            logger.warning("No active session to end")
            return None
        
        # Update end time
        self.session_data["end_time"] = datetime.now(timezone.utc).isoformat()
        
        # Generate summary
        summary = self._generate_summary()
        self.session_data["summary"] = summary
        
        # Save all session data
        self._save_session_data()
        
        # Sprint 4: Sync to Supabase
        if SUPABASE_AVAILABLE and supabase_client.is_connected():
            self._sync_session_to_supabase()
        
        logger.info(f"Ended shadow logging session: {self.current_session_id}")
        
        session_summary = self.session_data.copy()
        self.current_session_id = None
        self.session_data = None
        
        return session_summary
    
    # ═══════════════════════════════════════════════════════════════
    # SPRINT 4: SUPABASE SYNC WITH V-VAD SPEAKER ATTRIBUTION
    # ═══════════════════════════════════════════════════════════════
    async def _sync_session_to_supabase(self):
        """Sync session data to Supabase with V-VAD speaker attribution"""
        if not SUPABASE_AVAILABLE or not supabase_client.is_connected():
            return
        
        try:
            # Create meeting log
            meeting_data = {
                "platform": self.session_data["platform"],
                "meeting_id": self.session_data["session_id"],
                "title": self.session_data["title"],
                "participants": self.session_data["participants"],
                "start_time": self.session_data["start_time"],
                "end_time": self.session_data["end_time"],
                "transcript": "\n".join([t["text"] for t in self.session_data["transcriptions"]]),
                "entities_extracted": {
                    "entities": self.session_data["entities"],
                    # Sprint 4: Include V-VAD speaker attribution
                    "vvad_attribution": [t.get("vvad_speaker") for t in self.session_data["transcriptions"]]
                }
            }
            
            await supabase_client.create_meeting_log(meeting_data)
            logger.info(f"Synced session to Supabase: {self.session_data['session_id']}")
        except Exception as e:
            logger.error(f"Error syncing session to Supabase: {e}")
    
    def _generate_summary(self) -> Dict[str, Any]:
        """
        Generate session summary
        
        Returns:
            Summary dictionary
        """
        if not self.session_data:
            return {}
        
        transcriptions = self.session_data["transcriptions"]
        entities = self.session_data["entities"]
        participants = self.session_data["participants"]
        
        # Calculate duration
        start_time = datetime.fromisoformat(self.session_data["start_time"])
        end_time = datetime.fromisoformat(self.session_data["end_time"])
        duration_seconds = (end_time - start_time).total_seconds()
        duration_minutes = duration_seconds / 60
        
        # Extract key points from entities
        promises = [e for e in entities if e.get("type") == "promise"]
        prices = [e for e in entities if e.get("type") == "price"]
        pain_points = [e for e in entities if e.get("type") == "pain_point"]
        
        summary = {
            "duration_minutes": round(duration_minutes, 2),
            "participant_names": [p["name"] for p in participants],
            "promise_count": len(promises),
            "price_count": len(prices),
            "pain_point_count": len(pain_points),
            "key_promises": [p.get("context") for p in promises[:5]],
            "key_prices": [p.get("value") for p in prices[:5]],
            "key_pain_points": [p.get("context") for p in pain_points[:5]]
        }
        
        return summary
    
    def _save_transcriptions(self):
        """Save transcriptions to disk"""
        if not self.current_session_id:
            return
        
        session_dir = self.logs_dir / self.current_session_id
        transcriptions_file = session_dir / "transcriptions.json"
        
        with open(transcriptions_file, 'w', encoding='utf-8') as f:
            json.dump(self.session_data["transcriptions"], f, indent=2, ensure_ascii=False)
    
    def _save_entities(self):
        """Save entities to disk"""
        if not self.current_session_id:
            return
        
        session_dir = self.logs_dir / self.current_session_id
        entities_file = session_dir / "entities.json"
        
        with open(entities_file, 'w', encoding='utf-8') as f:
            json.dump(self.session_data["entities"], f, indent=2, ensure_ascii=False)
    
    def _save_participants(self):
        """Save participants to disk"""
        if not self.current_session_id:
            return
        
        session_dir = self.logs_dir / self.current_session_id
        participants_file = session_dir / "participants.json"
        
        with open(participants_file, 'w', encoding='utf-8') as f:
            json.dump(self.session_data["participants"], f, indent=2, ensure_ascii=False)
    
    def _save_session_data(self):
        """Save complete session data to disk"""
        if not self.current_session_id:
            return
        
        session_dir = self.logs_dir / self.current_session_id
        session_file = session_dir / "session.json"
        
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(self.session_data, f, indent=2, ensure_ascii=False)
    
    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session summary
        
        Args:
            session_id: Session ID
        
        Returns:
            Session summary or None
        """
        session_dir = self.logs_dir / session_id
        session_file = session_dir / "session.json"
        
        if not session_file.exists():
            logger.warning(f"Session not found: {session_id}")
            return None
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            return session_data
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None
    
    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all sessions
        
        Returns:
            List of session summaries
        """
        sessions = []
        
        for session_dir in self.logs_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            session_file = session_dir / "session.json"
            if session_file.exists():
                try:
                    with open(session_file, 'r', encoding='utf-8') as f:
                        session_data = json.load(f)
                    sessions.append(session_data)
                except Exception as e:
                    logger.error(f"Failed to load session {session_dir.name}: {e}")
        
        # Sort by start time (newest first)
        sessions.sort(key=lambda x: x.get("start_time", ""), reverse=True)
        
        return sessions
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get logger status
        
        Returns:
            Status dictionary
        """
        return {
            "current_session_id": self.current_session_id,
            "is_active": self.current_session_id is not None,
            "logs_dir": str(self.logs_dir),
            "total_sessions": len(list(self.logs_dir.iterdir())) if self.logs_dir.exists() else 0
        }


def main():
    """Test the Shadow Logger"""
    from loguru import logger
    
    logger.add("logs/shadow_logger_{time}.log", rotation="10 MB")
    
    # Create logger
    config = ShadowLoggerConfig()
    logger_instance = ShadowLogger(config)
    
    # Start session
    session_id = logger_instance.start_session("teams", "Kundmöte")
    
    # Log transcriptions
    logger_instance.log_transcription("Hej, hur mår du?", speaker_id="user_1")
    logger_instance.log_transcription("Tack, bra! Du?", speaker_id="user_2")
    logger_instance.log_transcription("Jag skickar offerten på måndag.", speaker_id="user_1")
    
    # Log entities
    entities = [
        {"type": "promise", "text": "Jag skickar offerten på måndag.", "context": "skickar offert"}
    ]
    logger_instance.log_entities(entities)
    
    # Log participant
    logger_instance.log_participant("person_1", "Lasse Larsson")
    
    # End session
    summary = logger_instance.end_session()
    
    logger.info(f"Session summary: {summary}")
    
    # Get all sessions
    sessions = logger_instance.get_all_sessions()
    logger.info(f"Total sessions: {len(sessions)}")
    
    logger.info("Shadow Logger test complete")


if __name__ == "__main__":
    main()
