#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Persistent Mood Engine
Tracks emotional baseline across meetings and events
"""

import json
import sys
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class MoodLevel(Enum):
    """Mood levels with associated parameters"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    IRRITATED = "irritated"
    STRESSED = "stressed"
    TIRED = "tired"
    FOCUSED = "focused"
    RELAXED = "relaxed"


# Mood parameters affecting behavior
MOOD_PARAMETERS = {
    MoodLevel.NEUTRAL: {
        "warmth": 0.5,        # Friendliness (0.0-1.0)
        "brevity": 0.5,       # Conciseness (0.0-1.0)
        "formality": 0.5,     # Professionalism (0.0-1.0)
        "enthusiasm": 0.5,    # Energy level (0.0-1.0)
        "patience": 0.5       # Tolerance for interruptions (0.0-1.0)
    },
    MoodLevel.HAPPY: {
        "warmth": 0.9,
        "brevity": 0.4,
        "formality": 0.3,
        "enthusiasm": 0.8,
        "patience": 0.8
    },
    MoodLevel.IRRITATED: {
        "warmth": 0.1,
        "brevity": 0.9,
        "formality": 0.8,
        "enthusiasm": 0.2,
        "patience": 0.2
    },
    MoodLevel.STRESSED: {
        "warmth": 0.3,
        "brevity": 0.8,
        "formality": 0.7,
        "enthusiasm": 0.4,
        "patience": 0.3
    },
    MoodLevel.TIRED: {
        "warmth": 0.4,
        "brevity": 0.7,
        "formality": 0.5,
        "enthusiasm": 0.3,
        "patience": 0.4
    },
    MoodLevel.FOCUSED: {
        "warmth": 0.5,
        "brevity": 0.8,
        "formality": 0.7,
        "enthusiasm": 0.6,
        "patience": 0.6
    },
    MoodLevel.RELAXED: {
        "warmth": 0.8,
        "brevity": 0.3,
        "formality": 0.2,
        "enthusiasm": 0.5,
        "patience": 0.9
    }
}


class MoodEvent:
    """A mood-changing event"""
    def __init__(self, mood: MoodLevel, description: str, timestamp: datetime = None):
        self.mood = mood
        self.description = description
        self.timestamp = timestamp or datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mood": self.mood.value,
            "description": self.description,
            "timestamp": self.timestamp.isoformat()
        }


class MoodEngine:
    """
    Persistent mood tracking engine
    Tracks emotional baseline with decay function
    """
    
    def __init__(self, config_path: str = "memory/mood/current_mood.json"):
        self.config_path = Path(config_path)
        self.current_mood = MoodLevel.NEUTRAL
        self.mood_history: list[MoodEvent] = []
        self.last_update: datetime = None
        self.decay_rate = 0.1  # How fast mood decays to neutral (0.0-1.0)
        self.decay_interval_hours = 2  # How often to apply decay
        
        self._load_mood_state()
    
    def _load_mood_state(self):
        """Load mood state from file"""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_mood_state()
            return
        
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
            
            self.current_mood = MoodLevel(data.get("current_mood", "neutral"))
            self.last_update = datetime.fromisoformat(data.get("last_update", datetime.now().isoformat()))
            
            # Load history
            history_data = data.get("mood_history", [])
            self.mood_history = [
                MoodEvent(
                    MoodLevel(event["mood"]),
                    event["description"],
                    datetime.fromisoformat(event["timestamp"])
                )
                for event in history_data
            ]
            
            # Apply decay if needed
            self._apply_decay()
            
        except Exception as e:
            logger.error(f"Error loading mood state: {e}")
            self.current_mood = MoodLevel.NEUTRAL
    
    def _save_mood_state(self):
        """Save mood state to file"""
        data = {
            "current_mood": self.current_mood.value,
            "last_update": self.last_update.isoformat() if self.last_update else datetime.now().isoformat(),
            "mood_history": [event.to_dict() for event in self.mood_history[-50:]]  # Keep last 50 events
        }
        
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.debug(f"Mood state saved: {self.current_mood.value}")
    
    def _apply_decay(self):
        """Apply decay function to gradually return to neutral"""
        if self.current_mood == MoodLevel.NEUTRAL:
            return
        
        if self.last_update is None:
            return
        
        hours_since_update = (datetime.now() - self.last_update).total_seconds() / 3600
        
        if hours_since_update >= self.decay_interval_hours:
            # Apply decay
            decay_steps = int(hours_since_update / self.decay_interval_hours)
            
            # Gradually move towards neutral
            if self.current_mood in [MoodLevel.IRRITATED, MoodLevel.STRESSED]:
                # Negative moods decay to neutral
                self.current_mood = MoodLevel.NEUTRAL
                logger.info(f"Mood decayed to neutral after {hours_since_update:.1f} hours")
            elif self.current_mood == MoodLevel.HAPPY:
                # Happy mood also decays
                self.current_mood = MoodLevel.NEUTRAL
                logger.info(f"Mood decayed to neutral after {hours_since_update:.1f} hours")
            
            self.last_update = datetime.now()
            self._save_mood_state()
    
    def set_mood(self, mood: MoodLevel, description: str = ""):
        """
        Set current mood with event logging
        
        Args:
            mood: New mood level
            description: Reason for mood change
        """
        event = MoodEvent(mood, description)
        self.mood_history.append(event)
        self.current_mood = mood
        self.last_update = datetime.now()
        
        self._save_mood_state()
        logger.info(f"Mood set to {mood.value}: {description}")
    
    def get_current_mood(self) -> MoodLevel:
        """Get current mood with decay applied"""
        self._apply_decay()
        return self.current_mood
    
    def get_mood_parameters(self) -> Dict[str, float]:
        """Get current mood parameters"""
        return MOOD_PARAMETERS.get(self.current_mood, MOOD_PARAMETERS[MoodLevel.NEUTRAL]).copy()
    
    def get_prompt_injection(self) -> str:
        """
        Generate prompt injection based on current mood
        
        Returns:
            Tone modifier string for LLM
        """
        params = self.get_mood_parameters()
        mood = self.current_mood
        
        if mood == MoodLevel.NEUTRAL:
            return "Maintain a balanced, professional tone."
        
        elif mood == MoodLevel.HAPPY:
            return "Be warm and friendly. Show enthusiasm. Engage in light conversation when appropriate."
        
        elif mood == MoodLevel.IRRITATED:
            return "Be concise and direct. Avoid small talk. Be professional but maintain distance. Get to the point quickly."
        
        elif mood == MoodLevel.STRESSED:
            return "Be efficient and focused. Minimize distractions. Keep responses brief but helpful."
        
        elif mood == MoodLevel.TIRED:
            return "Be gentle and patient. Avoid complex explanations. Keep things simple and straightforward."
        
        elif mood == MoodLevel.FOCUSED:
            return "Be precise and goal-oriented. Minimize interruptions. Stay on topic."
        
        elif mood == MoodLevel.RELAXED:
            return "Be warm and approachable. Take time to build rapport. Be conversational."
        
        return "Maintain a balanced, professional tone."
    
    def get_visual_mood_adjustment(self) -> Dict[str, float]:
        """
        Get visual mood adjustment for LivePortrait
        Returns expression parameters based on mood
        
        Returns:
            Dictionary with expression adjustments
        """
        params = self.get_mood_parameters()
        mood = self.current_mood
        
        adjustments = {
            "smile_intensity": 0.5,      # 0.0-1.0
            "eye_openness": 0.5,         # 0.0-1.0
            "brow_tension": 0.5,         # 0.0-1.0
            "head_tilt": 0.0             # -1.0 to 1.0
        }
        
        if mood == MoodLevel.HAPPY:
            adjustments["smile_intensity"] = 0.8
            adjustments["eye_openness"] = 0.6
            adjustments["brow_tension"] = 0.2
            adjustments["head_tilt"] = 0.1
        
        elif mood == MoodLevel.IRRITATED:
            adjustments["smile_intensity"] = 0.1
            adjustments["eye_openness"] = 0.4
            adjustments["brow_tension"] = 0.8
            adjustments["head_tilt"] = -0.1
        
        elif mood == MoodLevel.STRESSED:
            adjustments["smile_intensity"] = 0.2
            adjustments["eye_openness"] = 0.6
            adjustments["brow_tension"] = 0.7
            adjustments["head_tilt"] = 0.0
        
        elif mood == MoodLevel.TIRED:
            adjustments["smile_intensity"] = 0.3
            adjustments["eye_openness"] = 0.4
            adjustments["brow_tension"] = 0.3
            adjustments["head_tilt"] = 0.0
        
        elif mood == MoodLevel.FOCUSED:
            adjustments["smile_intensity"] = 0.4
            adjustments["eye_openness"] = 0.7
            adjustments["brow_tension"] = 0.5
            adjustments["head_tilt"] = 0.0
        
        elif mood == MoodLevel.RELAXED:
            adjustments["smile_intensity"] = 0.6
            adjustments["eye_openness"] = 0.5
            adjustments["brow_tension"] = 0.3
            adjustments["head_tilt"] = 0.05
        
        return adjustments
    
    def get_status(self) -> Dict[str, Any]:
        """Get mood engine status"""
        return {
            "current_mood": self.current_mood.value,
            "parameters": self.get_mood_parameters(),
            "prompt_injection": self.get_prompt_injection(),
            "visual_adjustments": self.get_visual_mood_adjustment(),
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "history_count": len(self.mood_history)
        }
    
    def quick_log(self, mood_description: str):
        """
        Quick mood logging from natural language
        Parses description and sets mood
        
        Args:
            mood_description: Natural language description (e.g., "I'm stressed")
        """
        description_lower = mood_description.lower()
        
        if any(word in description_lower for word in ["argry", "irritated", "annoyed", "frustrated"]):
            self.set_mood(MoodLevel.IRRITATED, mood_description)
        elif any(word in description_lower for word in ["stress", "stressed", "pressure", "overwhelmed"]):
            self.set_mood(MoodLevel.STRESSED, mood_description)
        elif any(word in description_lower for word in ["happy", "good", "great", "excited", "joy"]):
            self.set_mood(MoodLevel.HAPPY, mood_description)
        elif any(word in description_lower for word in ["tired", "exhausted", "sleepy", "fatigue"]):
            self.set_mood(MoodLevel.TIRED, mood_description)
        elif any(word in description_lower for word in ["focus", "focused", "concentrate", "work"]):
            self.set_mood(MoodLevel.FOCUSED, mood_description)
        elif any(word in description_lower for word in ["relax", "relaxed", "calm", "chill"]):
            self.set_mood(MoodLevel.RELAXED, mood_description)
        else:
            self.set_mood(MoodLevel.NEUTRAL, mood_description)


def main():
    """Test mood engine"""
    from loguru import logger
    
    logger.add("logs/mood_engine_{time}.log", rotation="10 MB")
    
    # Create mood engine
    engine = MoodEngine()
    
    # Test mood setting
    engine.set_mood(MoodLevel.HAPPY, "Had a great morning")
    logger.info(f"Current mood: {engine.get_current_mood()}")
    logger.info(f"Parameters: {engine.get_mood_parameters()}")
    logger.info(f"Prompt injection: {engine.get_prompt_injection()}")
    logger.info(f"Visual adjustments: {engine.get_visual_mood_adjustment()}")
    
    # Test quick log
    engine.quick_log("I'm stressed about the deadline")
    logger.info(f"After quick log: {engine.get_current_mood()}")
    
    # Get status
    status = engine.get_status()
    logger.info(f"Status: {status}")
    
    logger.info("Mood engine test complete")


if __name__ == "__main__":
    main()
