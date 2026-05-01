#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Context Buffer
Real-time context tracking for conversations
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from collections import deque
import json
import sys

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from pydantic import BaseModel, Field


class ContextEvent(BaseModel):
    """Represents a context event"""
    event_type: str = Field(description="Type of event (transcription, emotion, action, etc.)")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event data")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="Event timestamp")
    speaker: Optional[str] = Field(default=None, description="Speaker name if applicable")


class ContextConfig(BaseModel):
    """Configuration for context buffer"""
    window_minutes: int = Field(default=5, description="Context window in minutes")
    max_events: int = Field(default=1000, description="Maximum number of events to store")
    persist_to_disk: bool = Field(default=True, description="Persist context to disk")
    persist_path: str = Field(default="memory/context_buffer.json", description="Path to persist file")


class ContextBuffer:
    """
    Manages conversation context buffer
    Tracks last 5 minutes of conversation for quick reference
    """
    
    def __init__(self, config: ContextConfig):
        """Initialize context buffer"""
        self.config = config
        
        # Use deque for efficient sliding window
        self.events = deque(maxlen=config.max_events)
        
        # Load from disk if enabled
        if config.persist_to_disk:
            self.load_from_disk()
        
        logger.info(f"Context Buffer initialized with {len(self.events)} events")
    
    def add_event(self, event_type: str, data: Dict[str, Any], speaker: Optional[str] = None):
        """
        Add an event to the context buffer
        
        Args:
            event_type: Type of event
            data: Event data
            speaker: Speaker name if applicable
        """
        event = ContextEvent(
            event_type=event_type,
            data=data,
            speaker=speaker
        )
        
        self.events.append(event)
        
        # Trim events outside window
        self._trim_old_events()
        
        logger.debug(f"Added event: {event_type} from {speaker or 'unknown'}")
    
    def add_transcription(self, text: str, speaker: Optional[str] = None, confidence: float = 1.0):
        """Add transcription event"""
        self.add_event(
            event_type="transcription",
            data={"text": text, "confidence": confidence},
            speaker=speaker
        )
    
    def add_emotion(self, emotion: str, confidence: float = 1.0, speaker: Optional[str] = None):
        """Add emotion event"""
        self.add_event(
            event_type="emotion",
            data={"emotion": emotion, "confidence": confidence},
            speaker=speaker
        )
    
    def add_action(self, action_type: str, description: str):
        """Add agent action event"""
        self.add_event(
            event_type="action",
            data={"action_type": action_type, "description": description},
            speaker="Anton"
        )
    
    def add_name_detection(self, names: List[str]):
        """Add name detection event"""
        self.add_event(
            event_type="name_detection",
            data={"names": names},
            speaker=None
        )
    
    def add_guardrail_trigger(self, reason: str):
        """Add guardrail trigger event"""
        self.add_event(
            event_type="guardrail_trigger",
            data={"reason": reason},
            speaker="Anton"
        )
    
    def _trim_old_events(self):
        """Remove events outside the time window"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=self.config.window_minutes)
        
        # Remove events older than cutoff
        while self.events and datetime.fromisoformat(self.events[0].timestamp.replace("Z", "+00:00")) < cutoff_time:
            self.events.popleft()
    
    def get_recent_events(self, minutes: Optional[int] = None, event_type: Optional[str] = None) -> List[ContextEvent]:
        """
        Get recent events
        
        Args:
            minutes: Time window in minutes (defaults to config)
            event_type: Filter by event type
        
        Returns:
            List of events
        """
        window_minutes = minutes or self.config.window_minutes
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        
        filtered_events = []
        for event in self.events:
            event_time = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
            
            if event_time >= cutoff_time:
                if event_type is None or event.event_type == event_type:
                    filtered_events.append(event)
        
        return filtered_events
    
    def get_recent_transcriptions(self, minutes: int = 5) -> List[str]:
        """Get recent transcriptions"""
        events = self.get_recent_events(minutes=minutes, event_type="transcription")
        return [event.data.get("text", "") for event in events]
    
    def get_recent_emotions(self, minutes: int = 5) -> List[Dict[str, Any]]:
        """Get recent emotions"""
        events = self.get_recent_events(minutes=minutes, event_type="emotion")
        return [
            {"emotion": event.data.get("emotion"), "speaker": event.speaker}
            for event in events
        ]
    
    def get_conversation_summary(self, minutes: int = 5) -> Dict[str, Any]:
        """
        Get summary of recent conversation
        
        Args:
            minutes: Time window in minutes
        
        Returns:
            Conversation summary
        """
        events = self.get_recent_events(minutes=minutes)
        
        transcriptions = [e for e in events if e.event_type == "transcription"]
        emotions = [e for e in events if e.event_type == "emotion"]
        actions = [e for e in events if e.event_type == "action"]
        
        # Extract speakers
        speakers = set(e.speaker for e in transcriptions if e.speaker)
        
        # Count emotions
        emotion_counts = {}
        for e in emotions:
            emotion = e.data.get("emotion", "unknown")
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        
        # Dominant emotion
        dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1])[0] if emotion_counts else "neutral"
        
        return {
            "num_events": len(events),
            "num_transcriptions": len(transcriptions),
            "num_emotions": len(emotions),
            "num_actions": len(actions),
            "speakers": list(speakers),
            "dominant_emotion": dominant_emotion,
            "emotion_distribution": emotion_counts,
            "time_window_minutes": minutes,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def search_context(self, keyword: str, minutes: int = 5) -> List[ContextEvent]:
        """
        Search context for keyword
        
        Args:
            keyword: Keyword to search for
            minutes: Time window in minutes
        
        Returns:
            List of matching events
        """
        events = self.get_recent_events(minutes=minutes)
        keyword_lower = keyword.lower()
        
        matching_events = []
        for event in events:
            # Search in event data
            data_str = json.dumps(event.data).lower()
            if keyword_lower in data_str:
                matching_events.append(event)
        
        return matching_events
    
    def get_speaker_history(self, speaker: str, minutes: int = 5) -> List[ContextEvent]:
        """
        Get history for specific speaker
        
        Args:
            speaker: Speaker name
            minutes: Time window in minutes
        
        Returns:
            List of events from speaker
        """
        events = self.get_recent_events(minutes=minutes)
        return [e for e in events if e.speaker == speaker]
    
    def clear_old_context(self, minutes: int = 60):
        """
        Clear context older than specified minutes
        
        Args:
            minutes: Minutes to keep
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        
        original_count = len(self.events)
        
        # Remove events older than cutoff
        self.events = deque(
            [e for e in self.events if datetime.fromisoformat(e.timestamp.replace("Z", "+00:00")) >= cutoff_time],
            maxlen=self.config.max_events
        )
        
        removed = original_count - len(self.events)
        logger.info(f"Cleared {removed} old events (kept {len(self.events)})")
    
    def persist_to_disk(self):
        """Persist context buffer to disk"""
        if not self.config.persist_to_disk:
            return
        
        try:
            persist_file = Path(self.config.persist_path)
            persist_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert events to dict
            events_dict = [event.dict() for event in self.events]
            
            with open(persist_file, 'w', encoding='utf-8') as f:
                json.dump(events_dict, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Persisted {len(self.events)} events to disk")
            
        except Exception as e:
            logger.error(f"Failed to persist context: {e}")
    
    def load_from_disk(self):
        """Load context buffer from disk"""
        try:
            persist_file = Path(self.config.persist_path)
            if not persist_file.exists():
                logger.info("No existing context file found")
                return
            
            with open(persist_file, 'r', encoding='utf-8') as f:
                events_dict = json.load(f)
            
            # Convert back to ContextEvent objects
            for event_dict in events_dict:
                event = ContextEvent(**event_dict)
                self.events.append(event)
            
            # Trim old events
            self._trim_old_events()
            
            logger.info(f"Loaded {len(self.events)} events from disk")
            
        except Exception as e:
            logger.error(f"Failed to load context from disk: {e}")
    
    def get_buffer_summary(self) -> Dict[str, Any]:
        """Get summary of buffer state"""
        return {
            "total_events": len(self.events),
            "window_minutes": self.config.window_minutes,
            "max_events": self.config.max_events,
            "persist_enabled": self.config.persist_to_disk,
            "oldest_event": self.events[0].timestamp if self.events else None,
            "newest_event": self.events[-1].timestamp if self.events else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test the context buffer"""
    from loguru import logger
    
    logger.add("logs/context_buffer_{time}.log", rotation="10 MB")
    
    # Create context buffer
    config = ContextConfig()
    buffer = ContextBuffer(config)
    
    # Add some test events
    buffer.add_transcription("Hej, hur är det?", speaker="Lasse")
    buffer.add_emotion("Happy", speaker="Lasse")
    buffer.add_transcription("Det är bra, tack!", speaker="Anton")
    buffer.add_action("nod", "Nodded in agreement")
    
    # Get recent transcriptions
    transcriptions = buffer.get_recent_transcriptions()
    logger.info(f"Recent transcriptions: {transcriptions}")
    
    # Get conversation summary
    summary = buffer.get_conversation_summary()
    logger.info(f"Conversation summary: {summary}")
    
    # Search context
    results = buffer.search_context("hej")
    logger.info(f"Search results for 'hej': {len(results)} events")
    
    # Get buffer summary
    buffer_summary = buffer.get_buffer_summary()
    logger.info(f"Buffer summary: {buffer_summary}")
    
    # Persist to disk
    buffer.persist_to_disk()


if __name__ == "__main__":
    asyncio.run(main())
