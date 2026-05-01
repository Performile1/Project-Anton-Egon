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
    
    def log_transcription(self, text: str, speaker_id: Optional[str] = None, timestamp: Optional[str] = None):
        """
        Log transcription entry
        
        Args:
            text: Transcribed text
            speaker_id: Speaker identifier (optional)
            timestamp: Timestamp (optional, defaults to now)
        """
        if not self.current_session_id or not self.session_data:
            logger.warning("No active session to log transcription")
            return
        
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        
        transcription_entry = {
            "text": text,
            "speaker_id": speaker_id,
            "timestamp": timestamp
        }
        
        self.session_data["transcriptions"].append(transcription_entry)
        
        # Check max limit
        if len(self.session_data["transcriptions"]) > self.config.max_transcriptions_per_session:
            logger.warning(f"Reached max transcriptions limit ({self.config.max_transcriptions_per_session})")
        
        # Auto-save if enabled
        if self.config.auto_save:
            self._save_transcriptions()
        
        logger.debug(f"Logged transcription: {text[:50]}...")
    
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
        
        logger.info(f"Ended shadow logging session: {self.current_session_id}")
        
        # Return summary
        session_summary = {
            "session_id": self.current_session_id,
            "platform": self.session_data["platform"],
            "title": self.session_data["title"],
            "start_time": self.session_data["start_time"],
            "end_time": self.session_data["end_time"],
            "transcription_count": len(self.session_data["transcriptions"]),
            "entity_count": len(self.session_data["entities"]),
            "participant_count": len(self.session_data["participants"]),
            "summary": summary
        }
        
        # Clear current session
        self.current_session_id = None
        self.session_data = None
        
        return session_summary
    
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
