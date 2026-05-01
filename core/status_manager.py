#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Status Manager
Tracks and manages agent status across components
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from collections import deque
from enum import Enum

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class StatusManager:
    """
    Manages real-time status updates for the agent
    Updates live_status.json with current state
    """
    
    def __init__(
        self,
        status_file: Path = Path("live_status.json"),
        history_size: int = 100
    ):
        """
        Initialize status manager
        
        Args:
            status_file: Path to status JSON file
            history_size: Number of historical entries to keep
        """
        self.status_file = status_file
        self.history_size = history_size
        
        # Current state
        self.current_state = {
            "active_speaker": None,
            "detected_emotion": "Neutral",
            "last_mentioned_keyword": None,
            "transcription": "",
            "detected_names": [],
            "num_faces": 0,
            "agent_state": "IDLE",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # History for tracking changes
        self.history = deque(maxlen=history_size)
        
        logger.info(f"StatusManager initialized with file: {status_file}")
        
        # Create initial status file
        self._write_status()
    
    def _write_status(self):
        """Write current status to file"""
        try:
            status_data = {
                "current": self.current_state,
                "history": list(self.history),
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Failed to write status file: {e}")
    
    def update_transcription(self, text: str, speaker: Optional[str] = None):
        """Update transcription and active speaker"""
        self.current_state["transcription"] = text
        if speaker:
            self.current_state["active_speaker"] = speaker
        
        # Extract keywords (simple implementation)
        keywords = self._extract_keywords(text)
        if keywords:
            self.current_state["last_mentioned_keyword"] = keywords[0]
        
        self._write_status()
        logger.debug(f"Updated transcription: {text[:50]}...")
    
    def update_emotion(self, emotion: str, confidence: float = 0.0):
        """Update detected emotion"""
        self.current_state["detected_emotion"] = emotion
        
        # Add confidence if available
        if confidence > 0:
            self.current_state["emotion_confidence"] = confidence
        
        self._write_status()
        logger.debug(f"Updated emotion: {emotion}")
    
    def update_faces(self, num_faces: int, emotions: list = None):
        """Update face detection results"""
        self.current_state["num_faces"] = num_faces
        if emotions:
            self.current_state["face_emotions"] = emotions
        
        self._write_status()
        logger.debug(f"Updated faces: {num_faces}")
    
    def update_names(self, names: list):
        """Update detected names"""
        self.current_state["detected_names"] = names
        
        self._write_status()
        logger.debug(f"Updated names: {names}")
    
    def update_agent_state(self, state: str):
        """Update agent state"""
        self.current_state["agent_state"] = state
        
        self._write_status()
        logger.debug(f"Updated agent state: {state}")
    
    def _extract_keywords(self, text: str) -> list:
        """Extract keywords from text (simple implementation)"""
        # Common business/meeting keywords
        business_keywords = [
            "offert", "pris", "budget", "deadline", "projekt", "möte",
            "kund", "leverans", "kontrakt", "avtal", "tidsplan",
            "quote", "price", "budget", "deadline", "project", "meeting",
            "client", "delivery", "contract", "agreement", "timeline"
        ]
        
        text_lower = text.lower()
        found_keywords = []
        
        for keyword in business_keywords:
            if keyword.lower() in text_lower:
                found_keywords.append(keyword)
        
        return found_keywords
    
    def add_to_history(self, event_type: str, data: Dict[str, Any]):
        """Add event to history"""
        history_entry = {
            "event_type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self.history.append(history_entry)
        self._write_status()
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current status"""
        return self.current_state.copy()
    
    def get_history(self, event_type: Optional[str] = None) -> list:
        """Get history, optionally filtered by event type"""
        if event_type:
            return [h for h in self.history if h["event_type"] == event_type]
        return list(self.history)
    
    def reset(self):
        """Reset status to initial state"""
        self.current_state = {
            "active_speaker": None,
            "detected_emotion": "Neutral",
            "last_mentioned_keyword": None,
            "transcription": "",
            "detected_names": [],
            "num_faces": 0,
            "agent_state": "IDLE",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.history.clear()
        self._write_status()
        logger.info("Status reset to initial state")


# Global status manager instance
_status_manager = None


def get_status_manager() -> StatusManager:
    """Get global status manager instance"""
    global _status_manager
    if _status_manager is None:
        _status_manager = StatusManager()
    return _status_manager


async def main():
    """Test the status manager"""
    from loguru import logger
    
    logger.add("logs/status_manager_{time}.log", rotation="10 MB")
    
    # Create status manager
    manager = StatusManager()
    
    # Test updates
    manager.update_agent_state("LISTENING")
    await asyncio.sleep(0.5)
    
    manager.update_transcription("Hej, vad tror du om offerten?", speaker="Lasse")
    await asyncio.sleep(0.5)
    
    manager.update_emotion("Thinking", 0.8)
    await asyncio.sleep(0.5)
    
    manager.update_faces(2, ["Neutral", "Happy"])
    await asyncio.sleep(0.5)
    
    manager.update_names(["Lasse", "Anna"])
    await asyncio.sleep(0.5)
    
    # Add to history
    manager.add_to_history("transcription", {"text": "Hej, vad tror du om offerten?"})
    manager.add_to_history("emotion", {"emotion": "Thinking", "confidence": 0.8})
    
    # Print current status
    logger.info(f"Current status: {json.dumps(manager.get_current_status(), indent=2)}")
    
    # Print history
    logger.info(f"History: {json.dumps(manager.get_history(), indent=2)}")
    
    logger.info("Status manager test complete")


if __name__ == "__main__":
    asyncio.run(main())
