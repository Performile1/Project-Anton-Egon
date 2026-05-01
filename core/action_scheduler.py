#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Action Scheduler
Schedules natural timing for agent actions
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from enum import Enum
import random
import sys

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from pydantic import BaseModel, Field


class ActionType(Enum):
    """Types of human actions"""
    DRINK_WATER = "drink_water"
    CHECK_PHONE = "check_phone"
    ADJUST_GLASSES = "adjust_glasses"
    SCRATCH_HEAD = "scratch_head"
    LOOK_NOTES = "look_notes"
    STRETCH = "stretch"
    CLEAR_THROAT = "clear_throat"
    NOD = "nod"
    SMILE = "smile"
    THINKING_POSE = "thinking_pose"


class ActionConfig(BaseModel):
    """Configuration for action scheduler"""
    min_silence_seconds: float = Field(default=5.0, description="Min silence before action")
    max_silence_seconds: float = Field(default=15.0, description="Max silence before action")
    action_probability: float = Field(default=0.3, description="Probability of action during silence")
    complex_question_bonus: float = Field(default=0.5, description="Bonus for complex questions")
    meeting_start_greeting: bool = Field(default=True, description="Greet late joiners at meeting start")


class HumanAction(BaseModel):
    """Represents a human action"""
    action_type: ActionType
    description: str
    duration_seconds: float
    video_trigger: Optional[str] = None
    audio_trigger: Optional[str] = None


class ActionScheduler:
    """
    Schedules human-like behaviors (wildcards)
    Randomly inserts actions based on context
    """
    
    def __init__(self, config: ActionConfig):
        """Initialize action scheduler"""
        self.config = config
        
        # Action library
        self.actions = self._build_action_library()
        
        # State
        self.last_action_time = None
        self.silence_start_time = None
        self.is_silent = False
        self.meeting_started = False
        self.greeted_participants = set()
        
        logger.info("Action Scheduler initialized")
    
    def _build_action_library(self) -> Dict[ActionType, HumanAction]:
        """Build library of human actions"""
        return {
            ActionType.DRINK_WATER: HumanAction(
                action_type=ActionType.DRINK_WATER,
                description="Drinking water from glass",
                duration_seconds=3.0,
                video_trigger="drink_water",
                audio_trigger="sip_sound"
            ),
            ActionType.CHECK_PHONE: HumanAction(
                action_type=ActionType.CHECK_PHONE,
                description="Quick glance at phone",
                duration_seconds=2.0,
                video_trigger="check_phone",
                audio_trigger=None
            ),
            ActionType.ADJUST_GLASSES: HumanAction(
                action_type=ActionType.ADJUST_GLASSES,
                description="Adjusting glasses",
                duration_seconds=1.5,
                video_trigger="adjust_glasses",
                audio_trigger=None
            ),
            ActionType.SCRATCH_HEAD: HumanAction(
                action_type=ActionType.SCRATCH_HEAD,
                description="Scratching head thoughtfully",
                duration_seconds=2.0,
                video_trigger="scratch_head",
                audio_trigger=None
            ),
            ActionType.LOOK_NOTES: HumanAction(
                action_type=ActionType.LOOK_NOTES,
                description="Looking at notes",
                duration_seconds=3.0,
                video_trigger="look_notes",
                audio_trigger="paper_rustle"
            ),
            ActionType.STRETCH: HumanAction(
                action_type=ActionType.STRETCH,
                description="Subtle stretch",
                duration_seconds=2.0,
                video_trigger="stretch",
                audio_trigger=None
            ),
            ActionType.CLEAR_THROAT: HumanAction(
                action_type=ActionType.CLEAR_THROAT,
                description="Clearing throat",
                duration_seconds=1.0,
                video_trigger=None,
                audio_trigger="clear_throat"
            ),
            ActionType.NOD: HumanAction(
                action_type=ActionType.NOD,
                description="Nodding in agreement",
                duration_seconds=1.0,
                video_trigger="nod",
                audio_trigger=None
            ),
            ActionType.SMILE: HumanAction(
                action_type=ActionType.SMILE,
                description="Subtle smile",
                duration_seconds=2.0,
                video_trigger="smile",
                audio_trigger=None
            ),
            ActionType.THINKING_POSE: HumanAction(
                action_type=ActionType.THINKING_POSE,
                description="Hand on chin, thinking",
                duration_seconds=3.0,
                video_trigger="thinking_pose",
                audio_trigger=None
            )
        }
    
    def on_silence_start(self):
        """Handle silence start"""
        self.silence_start_time = datetime.now(timezone.utc)
        self.is_silent = True
        logger.debug("Silence started")
    
    def on_silence_end(self):
        """Handle silence end"""
        self.silence_start_time = None
        self.is_silent = False
        logger.debug("Silence ended")
    
    def on_complex_question(self) -> Optional[HumanAction]:
        """
        Trigger action for complex questions
        Gives agent 5-10 seconds extra thinking time
        """
        # Prefer drink water or thinking pose for complex questions
        preferred_actions = [
            ActionType.DRINK_WATER,
            ActionType.THINKING_POSE,
            ActionType.LOOK_NOTES
        ]
        
        action = random.choice(preferred_actions)
        return self.actions[action]
    
    def on_long_silence(self) -> Optional[HumanAction]:
        """
        Trigger action during long silence
        """
        if not self.is_silent or not self.silence_start_time:
            return None
        
        silence_duration = (datetime.now(timezone.utc) - self.silence_start_time).total_seconds()
        
        # Check if silence is long enough
        if silence_duration < self.config.min_silence_seconds:
            return None
        
        # Check if silence is too long (avoid too many actions)
        if silence_duration > self.config.max_silence_seconds:
            return None
        
        # Random chance to trigger action
        if random.random() < self.config.action_probability:
            # Choose random action (excluding clear_throat for silence)
            available_actions = [
                ActionType.CHECK_PHONE,
                ActionType.ADJUST_GLASSES,
                ActionType.SCRATCH_HEAD,
                ActionType.LOOK_NOTES,
                ActionType.STRETCH,
                ActionType.NOD,
                ActionType.SMILE
            ]
            action = random.choice(available_actions)
            return self.actions[action]
        
        return None
    
    def on_meeting_start(self, participant_name: str) -> Optional[str]:
        """
        Greet late joiners at meeting start
        """
        if not self.config.meeting_start_greeting:
            return None
        
        if participant_name in self.greeted_participants:
            return None
        
        self.greeted_participants.add(participant_name)
        
        greetings = [
            f"Hej {participant_name}, trevligt att se dig!",
            f"Välkommen {participant_name}!",
            f"Hej {participant_name}!"
        ]
        
        return random.choice(greetings)
    
    def on_agreement(self) -> Optional[HumanAction]:
        """Trigger subtle agreement action"""
        agreement_actions = [
            ActionType.NOD,
            ActionType.SMILE
        ]
        action = random.choice(agreement_actions)
        return self.actions[action]
    
    def on_thinking(self) -> Optional[HumanAction]:
        """Trigger thinking action"""
        thinking_actions = [
            ActionType.THINKING_POSE,
            ActionType.LOOK_NOTES,
            ActionType.SCRATCH_HEAD
        ]
        action = random.choice(thinking_actions)
        return self.actions[action]
    
    def get_random_action(self, exclude: Optional[List[ActionType]] = None) -> Optional[HumanAction]:
        """Get a random action (excluding specified types)"""
        exclude = exclude or []
        
        available_actions = [a for a in ActionType if a not in exclude]
        if not available_actions:
            return None
        
        action = random.choice(available_actions)
        return self.actions[action]
    
    def should_trigger_action(self, context: Dict[str, Any]) -> Optional[HumanAction]:
        """
        Decide if an action should be triggered based on context
        
        Args:
            context: Current context (emotion, transcription, etc.)
        
        Returns:
            HumanAction if action should be triggered, None otherwise
        """
        # Check for complex question
        if context.get("is_complex_question", False):
            if random.random() < self.config.complex_question_bonus:
                return self.on_complex_question()
        
        # Check for long silence
        if self.is_silent:
            action = self.on_long_silence()
            if action:
                return action
        
        # Check for agreement context
        if context.get("emotion", "").lower() in ["happy", "agreeable"]:
            if random.random() < 0.3:
                return self.on_agreement()
        
        # Check for thinking context
        if context.get("is_thinking", False):
            if random.random() < 0.4:
                return self.on_thinking()
        
        return None
    
    def execute_action(self, action: HumanAction, callback: Optional[Callable] = None):
        """
        Execute a human action
        
        Args:
            action: Action to execute
            callback: Optional callback for video/audio triggers
        """
        logger.info(f"Executing action: {action.action_type.value} - {action.description}")
        
        self.last_action_time = datetime.now(timezone.utc)
        
        # Call callback if provided (for Phase 4 integration)
        if callback:
            callback(action)
        
        # In Phase 4, this will trigger video/audio loops
        # For now, just log the action
    
    def get_action_summary(self) -> Dict[str, Any]:
        """Get summary of action scheduler state"""
        return {
            "is_silent": self.is_silent,
            "silence_duration": (datetime.now(timezone.utc) - self.silence_start_time).total_seconds() if self.silence_start_time else 0,
            "last_action": self.last_action_time.isoformat() if self.last_action_time else None,
            "greeted_participants": list(self.greeted_participants),
            "meeting_started": self.meeting_started,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test the action scheduler"""
    from loguru import logger
    
    logger.add("logs/action_scheduler_{time}.log", rotation="10 MB")
    
    # Create action scheduler
    config = ActionConfig()
    scheduler = ActionScheduler(config)
    
    # Test complex question
    action = scheduler.on_complex_question()
    logger.info(f"Complex question action: {action.action_type.value if action else None}")
    
    # Test silence
    scheduler.on_silence_start()
    await asyncio.sleep(6)  # Wait 6 seconds
    action = scheduler.on_long_silence()
    logger.info(f"Long silence action: {action.action_type.value if action else None}")
    
    # Test meeting greeting
    greeting = scheduler.on_meeting_start("Lasse")
    logger.info(f"Greeting: {greeting}")
    
    # Test random action
    action = scheduler.get_random_action()
    logger.info(f"Random action: {action.action_type.value if action else None}")
    
    # Test context-based trigger
    context = {
        "is_complex_question": True,
        "emotion": "Neutral",
        "is_thinking": False
    }
    action = scheduler.should_trigger_action(context)
    logger.info(f"Context action: {action.action_type.value if action else None}")
    
    logger.info(f"Action summary: {scheduler.get_action_summary()}")


if __name__ == "__main__":
    asyncio.run(main())
