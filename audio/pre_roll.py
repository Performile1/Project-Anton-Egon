#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Audio Pre-roll
Pre-rendered filler audio clips for instant response while LLM processes.
Plays "Ja, precis", "Hmm, bra fråga" etc. to fill the gap before the real answer.
"""

import sys
import asyncio
import random
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class PreRollCategory(Enum):
    """Categories of pre-roll audio clips"""
    ACKNOWLEDGMENT = "acknowledgment"    # "Ja, precis", "Jag förstår"
    THINKING = "thinking"                # "Hmm, bra fråga...", "Låt mig se..."
    TRANSITION = "transition"            # "Okej, så...", "Ja, alltså..."
    CONFIRMATION = "confirmation"        # "Absolut", "Exakt"
    EMPATHY = "empathy"                  # "Jag hör vad du säger", "Det förstår jag"


class PreRollClip(BaseModel):
    """A pre-roll audio clip definition"""
    clip_id: str
    category: PreRollCategory
    text: str = Field(description="What the clip says")
    duration_ms: int = Field(description="Clip duration in milliseconds")
    audio_path: Optional[str] = Field(None, description="Path to pre-rendered audio file")
    suitable_for_intents: List[str] = Field(default_factory=list, description="Intents this clip works well with")


class AudioPreRollConfig(BaseModel):
    """Configuration for Audio Pre-roll"""
    enabled: bool = Field(default=True, description="Enable audio pre-roll")
    clips_dir: str = Field(default="audio/pre_roll_clips", description="Directory for pre-rendered clips")
    max_preroll_duration_ms: int = Field(default=1500, description="Max pre-roll duration before real answer")
    cooldown_seconds: float = Field(default=10.0, description="Min time between using same category")
    prefer_intent_matched: bool = Field(default=True, description="Prefer clips matched to detected intent")


# Pre-defined clip library (text definitions - audio files generated separately)
CLIP_LIBRARY = [
    # Acknowledgment
    PreRollClip(clip_id="ack_01", category=PreRollCategory.ACKNOWLEDGMENT,
                text="Ja, precis.", duration_ms=600,
                suitable_for_intents=["confirmation", "price_inquiry"]),
    PreRollClip(clip_id="ack_02", category=PreRollCategory.ACKNOWLEDGMENT,
                text="Jag förstår.", duration_ms=700,
                suitable_for_intents=["objection", "opinion_request"]),
    PreRollClip(clip_id="ack_03", category=PreRollCategory.ACKNOWLEDGMENT,
                text="Absolut.", duration_ms=500,
                suitable_for_intents=["confirmation"]),
    PreRollClip(clip_id="ack_04", category=PreRollCategory.ACKNOWLEDGMENT,
                text="Mm, exakt.", duration_ms=600,
                suitable_for_intents=["confirmation", "technical_question"]),
    
    # Thinking
    PreRollClip(clip_id="think_01", category=PreRollCategory.THINKING,
                text="Hmm, bra fråga...", duration_ms=900,
                suitable_for_intents=["budget_question", "opinion_request"]),
    PreRollClip(clip_id="think_02", category=PreRollCategory.THINKING,
                text="Låt mig se här...", duration_ms=800,
                suitable_for_intents=["price_inquiry", "history_recall"]),
    PreRollClip(clip_id="think_03", category=PreRollCategory.THINKING,
                text="Bra att du tar upp det.", duration_ms=900,
                suitable_for_intents=["objection", "timeline_question"]),
    PreRollClip(clip_id="think_04", category=PreRollCategory.THINKING,
                text="Ja, det ska jag kolla...", duration_ms=1000,
                suitable_for_intents=["technical_question", "history_recall"]),
    
    # Transition
    PreRollClip(clip_id="trans_01", category=PreRollCategory.TRANSITION,
                text="Okej, så...", duration_ms=600,
                suitable_for_intents=["price_inquiry", "budget_question"]),
    PreRollClip(clip_id="trans_02", category=PreRollCategory.TRANSITION,
                text="Ja, alltså...", duration_ms=600,
                suitable_for_intents=["opinion_request", "timeline_question"]),
    PreRollClip(clip_id="trans_03", category=PreRollCategory.TRANSITION,
                text="Om jag minns rätt...", duration_ms=800,
                suitable_for_intents=["history_recall"]),
    
    # Confirmation
    PreRollClip(clip_id="conf_01", category=PreRollCategory.CONFIRMATION,
                text="Absolut, det stämmer.", duration_ms=800,
                suitable_for_intents=["confirmation"]),
    PreRollClip(clip_id="conf_02", category=PreRollCategory.CONFIRMATION,
                text="Ja, precis så.", duration_ms=700,
                suitable_for_intents=["confirmation"]),
    
    # Empathy
    PreRollClip(clip_id="emp_01", category=PreRollCategory.EMPATHY,
                text="Jag hör vad du säger.", duration_ms=900,
                suitable_for_intents=["objection"]),
    PreRollClip(clip_id="emp_02", category=PreRollCategory.EMPATHY,
                text="Det förstår jag helt och hållet.", duration_ms=1100,
                suitable_for_intents=["objection", "opinion_request"]),
]


class AudioPreRoll:
    """
    Audio Pre-roll Manager
    Provides instant filler audio while the LLM generates the real response.
    Selects appropriate clips based on detected intent and context.
    """
    
    def __init__(self, config: AudioPreRollConfig):
        """
        Initialize Audio Pre-roll
        
        Args:
            config: Pre-roll configuration
        """
        self.config = config
        
        # Clip library
        self.clips = {clip.clip_id: clip for clip in CLIP_LIBRARY}
        
        # Cooldown tracking
        self.last_used: Dict[str, datetime] = {}
        
        # Clips directory
        self.clips_dir = Path(config.clips_dir)
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        
        # Check for pre-rendered audio files
        self._scan_audio_files()
        
        logger.info(f"Audio Pre-roll initialized ({len(self.clips)} clips)")
    
    def _scan_audio_files(self):
        """Scan for pre-rendered audio files and link to clips"""
        for clip_id, clip in self.clips.items():
            # Look for audio file matching clip_id
            for ext in [".wav", ".mp3", ".ogg"]:
                audio_file = self.clips_dir / f"{clip_id}{ext}"
                if audio_file.exists():
                    clip.audio_path = str(audio_file)
                    break
    
    def select_clip(
        self,
        intent: Optional[str] = None,
        category: Optional[PreRollCategory] = None,
        max_duration_ms: Optional[int] = None
    ) -> Optional[PreRollClip]:
        """
        Select an appropriate pre-roll clip
        
        Args:
            intent: Detected intent (from Speculative Ingest)
            category: Preferred category
            max_duration_ms: Maximum clip duration
        
        Returns:
            Selected clip or None
        """
        if not self.config.enabled:
            return None
        
        max_dur = max_duration_ms or self.config.max_preroll_duration_ms
        candidates = []
        
        for clip in self.clips.values():
            # Filter by duration
            if clip.duration_ms > max_dur:
                continue
            
            # Filter by category if specified
            if category and clip.category != category:
                continue
            
            # Check cooldown
            if clip.category.value in self.last_used:
                elapsed = (datetime.now(timezone.utc) - self.last_used[clip.category.value]).total_seconds()
                if elapsed < self.config.cooldown_seconds:
                    continue
            
            # Score by intent match
            score = 1.0
            if intent and self.config.prefer_intent_matched:
                if intent in clip.suitable_for_intents:
                    score = 3.0  # Strong preference for intent-matched clips
                else:
                    score = 0.5
            
            candidates.append((clip, score))
        
        if not candidates:
            return None
        
        # Weighted random selection
        total_score = sum(s for _, s in candidates)
        r = random.uniform(0, total_score)
        cumulative = 0
        
        for clip, score in candidates:
            cumulative += score
            if r <= cumulative:
                # Record usage
                self.last_used[clip.category.value] = datetime.now(timezone.utc)
                return clip
        
        return candidates[0][0]
    
    def get_clip_text(self, intent: Optional[str] = None) -> Optional[str]:
        """
        Get pre-roll text for TTS generation
        
        Args:
            intent: Detected intent
        
        Returns:
            Pre-roll text or None
        """
        clip = self.select_clip(intent=intent)
        if clip:
            return clip.text
        return None
    
    def get_clip_audio_path(self, intent: Optional[str] = None) -> Optional[str]:
        """
        Get path to pre-rendered audio clip
        
        Args:
            intent: Detected intent
        
        Returns:
            Audio file path or None (if no pre-rendered file exists)
        """
        clip = self.select_clip(intent=intent)
        if clip and clip.audio_path:
            return clip.audio_path
        return None
    
    async def generate_preroll_clips(self, tts_fn: Callable):
        """
        Generate all pre-roll audio clips using TTS.
        Call once to pre-render all clips.
        
        Args:
            tts_fn: Async TTS function(text) → audio_bytes
        """
        logger.info("Generating pre-roll audio clips...")
        
        for clip_id, clip in self.clips.items():
            if clip.audio_path and Path(clip.audio_path).exists():
                continue  # Already exists
            
            try:
                audio_bytes = await tts_fn(clip.text)
                
                if audio_bytes:
                    audio_path = self.clips_dir / f"{clip_id}.wav"
                    with open(audio_path, 'wb') as f:
                        f.write(audio_bytes)
                    
                    clip.audio_path = str(audio_path)
                    logger.info(f"Generated: {clip_id} → '{clip.text}'")
            
            except Exception as e:
                logger.error(f"Failed to generate {clip_id}: {e}")
        
        logger.info("Pre-roll clip generation complete")
    
    def get_all_clips(self) -> List[Dict[str, Any]]:
        """
        Get all clips with their status
        
        Returns:
            List of clip info
        """
        return [
            {
                "clip_id": clip.clip_id,
                "category": clip.category.value,
                "text": clip.text,
                "duration_ms": clip.duration_ms,
                "has_audio": clip.audio_path is not None,
                "intents": clip.suitable_for_intents
            }
            for clip in self.clips.values()
        ]
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get pre-roll status
        
        Returns:
            Status dictionary
        """
        total = len(self.clips)
        with_audio = sum(1 for c in self.clips.values() if c.audio_path)
        
        return {
            "enabled": self.config.enabled,
            "total_clips": total,
            "clips_with_audio": with_audio,
            "clips_dir": str(self.clips_dir),
            "categories": list(set(c.category.value for c in self.clips.values()))
        }


def main():
    """Test the Audio Pre-roll"""
    from loguru import logger
    
    logger.add("logs/pre_roll_{time}.log", rotation="10 MB")
    
    # Create pre-roll manager
    config = AudioPreRollConfig()
    preroll = AudioPreRoll(config)
    
    # Test: Select clip for different intents
    test_intents = [
        "price_inquiry",
        "budget_question",
        "objection",
        "history_recall",
        "confirmation",
        None  # No intent
    ]
    
    for intent in test_intents:
        clip = preroll.select_clip(intent=intent)
        if clip:
            logger.info(f"Intent '{intent}' → '{clip.text}' ({clip.duration_ms}ms)")
        else:
            logger.info(f"Intent '{intent}' → No clip available")
    
    # Get all clips
    all_clips = preroll.get_all_clips()
    logger.info(f"Total clips: {len(all_clips)}")
    
    # Get status
    status = preroll.get_status()
    logger.info(f"Pre-roll status: {status}")
    
    logger.info("Audio Pre-roll test complete")


if __name__ == "__main__":
    main()
