#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Passive Observation Module (Data Harvester)
Learns from user interactions in meetings (Teams, Meet, WhatsApp, Discord)
Saves training data for LoRA fine-tuning
"""

import sys
import os
import json
import asyncio
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import deque
from enum import Enum
import threading

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class HarvestMode(Enum):
    """Harvesting modes"""
    AUDIO_SHADOWING = "audio_shadowing"  # Save user's speech patterns
    VISUAL_SHADOWING = "visual_shadowing"  # Save user's facial expressions
    FULL_LEARNING = "full_learning"  # Both audio and visual
    PASSIVE_ONLY = "passive_only"  # Only context tags, no raw data


class HarvestConfig(BaseModel):
    """Configuration for data harvester"""
    training_data_dir: str = Field(default="vault/training_data", description="Directory for training data")
    max_video_clip_duration: float = Field(default=5.0, description="Max video clip duration in seconds")
    min_audio_length: float = Field(default=2.0, description="Min audio length to save in seconds")
    save_other_parties: bool = Field(default=False, description="Save other parties' data (privacy risk)")
    auto_start_on_platform: bool = Field(default=True, description="Auto-start when platform detected")
    sentiment_threshold: float = Field(default=0.6, description="Confidence threshold for sentiment detection")
    max_storage_gb: float = Field(default=10.0, description="Max storage in GB")


class DataHarvester:
    """
    Passive Observation Module
    Learns from user interactions in meetings
    Saves training data for LoRA fine-tuning
    """
    
    def __init__(self, config: HarvestConfig):
        """
        Initialize data harvester
        
        Args:
            config: Harvest configuration
        """
        self.config = config
        
        # State
        self.running = False
        self.current_mode = HarvestMode.PASSIVE_ONLY
        self.current_platform: Optional[str] = None
        self.session_id: Optional[str] = None
        
        # Data storage
        self.training_data_dir = Path(config.training_data_dir)
        self.training_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Buffers
        self.audio_buffer = deque(maxlen=1000)
        self.video_buffer = deque(maxlen=1000)
        self.transcription_buffer = deque(maxlen=1000)
        
        # Context tracking
        self.current_context: Optional[Dict[str, Any]] = None
        self.user_speaking = False
        self.last_sentiment = "neutral"
        
        # Statistics
        self.stats = {
            "sessions_count": 0,
            "audio_clips_saved": 0,
            "video_clips_saved": 0,
            "transcriptions_saved": 0,
            "storage_used_mb": 0.0
        }
        
        logger.info(f"Data Harvester initialized (mode: {self.current_mode.value})")
    
    def start_session(self, platform: str, mode: HarvestMode = HarvestMode.FULL_LEARNING):
        """
        Start a new harvesting session
        
        Args:
            platform: Platform name (teams, meet, whatsapp, discord)
            mode: Harvesting mode
        """
        self.session_id = f"{platform}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.current_platform = platform
        self.current_mode = mode
        self.current_context = {
            "platform": platform,
            "session_id": self.session_id,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "mode": mode.value
        }
        
        # Create session directory
        session_dir = self.training_data_dir / self.session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Started harvesting session: {self.session_id} (platform: {platform}, mode: {mode.value})")
    
    def stop_session(self):
        """Stop current harvesting session"""
        if not self.session_id:
            return
        
        # Save session metadata
        session_dir = self.training_data_dir / self.session_id
        metadata_file = session_dir / "session_metadata.json"
        
        self.current_context["end_time"] = datetime.now(timezone.utc).isoformat()
        self.current_context["stats"] = self.stats
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.current_context, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Stopped harvesting session: {self.session_id}")
        self.session_id = None
        self.current_context = None
    
    def set_speaking_state(self, is_user_speaking: bool):
        """
        Update user speaking state
        
        Args:
            is_user_speaking: True if user is currently speaking
        """
        self.user_speaking = is_user_speaking
        
        if is_user_speaking and self.current_mode in [HarvestMode.AUDIO_SHADOWING, HarvestMode.FULL_LEARNING]:
            logger.debug("User speaking - ready to harvest audio")
    
    def set_sentiment(self, sentiment: str):
        """
        Update current sentiment
        
        Args:
            sentiment: Sentiment label (neutral, happy, sad, angry, etc.)
        """
        self.last_sentiment = sentiment
        
        if self.current_mode in [HarvestMode.VISUAL_SHADOWING, HarvestMode.FULL_LEARNING]:
            logger.debug(f"Sentiment updated: {sentiment} - ready to harvest video")
    
    def harvest_audio(self, audio_data: bytes, speaker: str = "user"):
        """
        Harvest audio data
        
        Args:
            audio_data: Audio data bytes
            speaker: Speaker identifier (user, other)
        """
        if not self.session_id or self.current_mode == HarvestMode.PASSIVE_ONLY:
            return
        
        # Privacy check: only save user's audio if configured
        if speaker != "user" and not self.config.save_other_parties:
            logger.debug("Skipping other party audio (privacy)")
            return
        
        # Check storage limit
        if self._check_storage_limit():
            logger.warning("Storage limit reached, stopping audio harvest")
            return
        
        # Save audio clip
        session_dir = self.training_data_dir / self.session_id
        audio_dir = session_dir / "audio"
        audio_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        audio_file = audio_dir / f"{speaker}_{timestamp}.wav"
        
        with open(audio_file, 'wb') as f:
            f.write(audio_data)
        
        # Save metadata
        metadata = {
            "speaker": speaker,
            "timestamp": timestamp,
            "sentiment": self.last_sentiment if speaker == "user" else None,
            "duration": len(audio_data) / 44100  # Assuming 44.1kHz
        }
        
        metadata_file = audio_dir / f"{speaker}_{timestamp}.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        self.stats["audio_clips_saved"] += 1
        self.stats["storage_used_mb"] += len(audio_data) / (1024 * 1024)
        
        logger.debug(f"Saved audio clip: {audio_file.name}")
    
    def harvest_video(self, frame_data: bytes, sentiment: str = "neutral"):
        """
        Harvest video frame/clip
        
        Args:
            frame_data: Video frame data bytes
            sentiment: Sentiment label
        """
        if not self.session_id or self.current_mode == HarvestMode.PASSIVE_ONLY:
            return
        
        # Check storage limit
        if self._check_storage_limit():
            logger.warning("Storage limit reached, stopping video harvest")
            return
        
        # Save video clip
        session_dir = self.training_data_dir / self.session_id
        video_dir = session_dir / "video"
        video_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        video_file = video_dir / f"{sentiment}_{timestamp}.mp4"
        
        with open(video_file, 'wb') as f:
            f.write(frame_data)
        
        # Save metadata
        metadata = {
            "sentiment": sentiment,
            "timestamp": timestamp,
            "context": self.current_context
        }
        
        metadata_file = video_dir / f"{sentiment}_{timestamp}.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        self.stats["video_clips_saved"] += 1
        self.stats["storage_used_mb"] += len(frame_data) / (1024 * 1024)
        
        logger.debug(f"Saved video clip: {video_file.name}")
    
    def harvest_transcription(self, transcription: str, speaker: str = "user"):
        """
        Harvest transcription text
        
        Args:
            transcription: Transcribed text
            speaker: Speaker identifier
        """
        if not self.session_id:
            return
        
        # Save transcription
        session_dir = self.training_data_dir / self.session_id
        transcript_dir = session_dir / "transcriptions"
        transcript_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        transcript_file = transcript_dir / f"{speaker}_{timestamp}.txt"
        
        with open(transcript_file, 'w', encoding='utf-8') as f:
            f.write(transcription)
        
        # Save metadata
        metadata = {
            "speaker": speaker,
            "timestamp": timestamp,
            "sentiment": self.last_sentiment if speaker == "user" else None,
            "context": self.current_context
        }
        
        metadata_file = transcript_dir / f"{speaker}_{timestamp}.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        self.stats["transcriptions_saved"] += 1
        
        logger.debug(f"Saved transcription: {transcript_file.name}")
    
    def save_context_tag(self, context_type: str, context_data: Dict[str, Any]):
        """
        Save context tag (e.g., "Customer asked about pricing")
        
        Args:
            context_type: Type of context (question, objection, agreement, etc.)
            context_data: Context data
        """
        if not self.session_id:
            return
        
        # Save context tag
        session_dir = self.training_data_dir / self.session_id
        context_dir = session_dir / "context"
        context_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        context_file = context_dir / f"{context_type}_{timestamp}.json"
        
        context_data["timestamp"] = timestamp
        context_data["session_id"] = self.session_id
        
        with open(context_file, 'w', encoding='utf-8') as f:
            json.dump(context_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved context tag: {context_type}")
    
    def _check_storage_limit(self) -> bool:
        """
        Check if storage limit has been reached
        
        Returns:
            True if limit reached
        """
        storage_used_gb = self.stats["storage_used_mb"] / 1024
        return storage_used_gb >= self.config.max_storage_gb
    
    def get_training_data_summary(self) -> Dict[str, Any]:
        """
        Get summary of collected training data
        
        Returns:
            Summary dictionary
        """
        total_sessions = len([d for d in self.training_data_dir.iterdir() if d.is_dir()])
        
        return {
            "total_sessions": total_sessions,
            "current_session": self.session_id,
            "current_platform": self.current_platform,
            "current_mode": self.current_mode.value,
            "stats": self.stats,
            "storage_used_gb": self.stats["storage_used_mb"] / 1024,
            "storage_limit_gb": self.config.max_storage_gb,
            "training_data_dir": str(self.training_data_dir)
        }
    
    def get_session_list(self) -> List[Dict[str, Any]]:
        """
        Get list of all harvesting sessions
        
        Returns:
            List of session metadata
        """
        sessions = []
        
        for session_dir in self.training_data_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            metadata_file = session_dir / "session_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                sessions.append(metadata)
        
        return sorted(sessions, key=lambda x: x.get("start_time", ""))
    
    def cleanup_old_sessions(self, keep_days: int = 30):
        """
        Delete sessions older than specified days
        
        Args:
            keep_days: Number of days to keep
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=keep_days)
        deleted_count = 0
        
        for session_dir in self.training_data_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            metadata_file = session_dir / "session_metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                start_time = datetime.fromisoformat(metadata.get("start_time", ""))
                if start_time < cutoff_date:
                    # Delete session directory
                    import shutil
                    shutil.rmtree(session_dir)
                    deleted_count += 1
                    logger.info(f"Deleted old session: {session_dir.name}")
        
        logger.info(f"Cleanup complete: {deleted_count} sessions deleted")


async def main():
    """Test the data harvester"""
    from loguru import logger
    
    logger.add("logs/harvester_{time}.log", rotation="10 MB")
    
    # Create harvester
    config = HarvestConfig()
    harvester = DataHarvester(config)
    
    # Test session
    harvester.start_session("teams", HarvestMode.FULL_LEARNING)
    
    # Test audio harvest
    test_audio = b"fake_audio_data" * 1000
    harvester.harvest_audio(test_audio, speaker="user")
    
    # Test transcription harvest
    harvester.harvest_transcription("Det här är ett test.", speaker="user")
    
    # Test context tag
    harvester.save_context_tag("question", {"text": "Vad kostar det?"})
    
    # Get summary
    summary = harvester.get_training_data_summary()
    logger.info(f"Training data summary: {summary}")
    
    # Stop session
    harvester.stop_session()
    
    # Get session list
    sessions = harvester.get_session_list()
    logger.info(f"Sessions: {len(sessions)}")
    
    logger.info("Data harvester test complete")


if __name__ == "__main__":
    asyncio.run(main())
