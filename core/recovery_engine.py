#!/usr/bin/env python3
"""
Project Anton Egon - Recovery Engine
Social Recovery: Name triggers and Humble Correction logic
Phase 19: Resilience & Recovery - Escape sequences
"""

import asyncio
import re
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from loguru import logger


class RecoveryTrigger(Enum):
    """Recovery trigger types"""
    NAME_MENTION = "name_mention"  # User's name mentioned
    QUESTIONING = "questioning"  # "Är något fel?" / "Det där lät konstigt"
    HALLUCINATION = "hallucination"  # Agent hallucinating
    CONFUSION = "confusion"  # Agent confused
    AGGRESSION = "aggression"  # Aggressive tone detected


class RecoveryAction(Enum):
    """Recovery action types"""
    URGENT_CALL = "urgent_call"  # "Hoppsan, extremt brådskande samtal"
    HUMBLE_CORRECTION = "humble_correction"  # Correct previous statement
    PAUSE_AND_THINK = "pause_and_think"  # Pause before responding
    DEFER_TO_HUMAN = "defer_to_human"  # "Låt mig fråga min operatör"
    SILENCE = "silence"  # Stop speaking


@dataclass
class RecoveryContext:
    """Context for recovery action"""
    trigger: RecoveryTrigger
    detected_at: datetime
    recent_messages: List[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger": self.trigger.value,
            "detected_at": self.detected_at.isoformat(),
            "recent_messages": self.recent_messages,
            "confidence": self.confidence,
            "metadata": self.metadata
        }


class RecoveryEngine:
    """
    Recovery Engine
    Detects when agent is questioned or makes mistakes and initiates escape sequences
    """
    
    def __init__(self, user_name: str = "Anton"):
        """
        Initialize Recovery Engine
        
        Args:
            user_name: Name of the user (for name mention detection)
        """
        self.user_name = user_name.lower()
        self.is_active = False
        self.in_recovery = False
        self.recovery_context: Optional[RecoveryContext] = None
        self.message_history: List[str] = []
        self.max_history = 10
        
        # Trigger patterns
        self.trigger_patterns = {
            RecoveryTrigger.QUESTIONING: [
                r"är något fel",
                r"det där lät konstigt",
                r"vad sa du",
                r"kan du upprepa",
                r"jag förstår inte",
                r"menar du",
                r"är du säker"
            ],
            RecoveryTrigger.HALLUCINATION: [
                r"jag vet inte vad jag pratar om",
                r"det var fel",
                r"åh jag menade",
                r"ursäkta"
            ],
            RecoveryTrigger.AGGRESSION: [
                r"stopp",
                r"lägg av",
                r"var tyst"
            ]
        }
        
        # Name mention patterns
        self.name_patterns = [
            rf"\b{re.escape(user_name)}\b",
            r"\bdu\b",  # "du" (you) in Swedish context
            r"\bagenten\b"
        ]
        
        logger.info(f"Recovery Engine initialized (user: {user_name})")
    
    def activate(self):
        """Activate recovery engine"""
        self.is_active = True
        logger.info("Recovery Engine activated")
    
    def deactivate(self):
        """Deactivate recovery engine"""
        self.is_active = False
        logger.info("Recovery Engine deactivated")
    
    def add_message(self, message: str, is_agent: bool = True):
        """
        Add message to history
        
        Args:
            message: Message text
            is_agent: True if message is from agent, False if from user
        """
        self.message_history.append(message)
        if len(self.message_history) > self.max_history:
            self.message_history.pop(0)
        
        logger.debug(f"Added message to history (agent: {is_agent})")
    
    def detect_triggers(self, message: str, is_agent: bool = True) -> Optional[RecoveryTrigger]:
        """
        Detect recovery triggers in message
        
        Args:
            message: Message text
            is_agent: True if message is from agent, False if from user
        
        Returns:
            Detected trigger or None
        """
        if not self.is_active or self.in_recovery:
            return None
        
        message_lower = message.lower()
        
        # Check for name mention (only in user messages)
        if not is_agent:
            for pattern in self.name_patterns:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    logger.info(f"Name mention detected: {message[:50]}...")
                    return RecoveryTrigger.NAME_MENTION
        
        # Check for questioning triggers (only in user messages)
        if not is_agent:
            for pattern in self.trigger_patterns[RecoveryTrigger.QUESTIONING]:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    logger.info(f"Questioning trigger detected: {message[:50]}...")
                    return RecoveryTrigger.QUESTIONING
        
        # Check for hallucination triggers (only in agent messages)
        if is_agent:
            for pattern in self.trigger_patterns[RecoveryTrigger.HALLUCINATION]:
                if re.search(pattern, message_lower, re.IGNORECASE):
                    logger.info(f"Hallucination trigger detected: {message[:50]}...")
                    return RecoveryTrigger.HALLUCINATION
        
        return None
    
    def initiate_recovery(self, trigger: RecoveryTrigger) -> RecoveryAction:
        """
        Initiate recovery sequence based on trigger
        
        Args:
            trigger: Detected trigger
        
        Returns:
            Recovery action to take
        """
        if self.in_recovery:
            return RecoveryAction.SILENCE
        
        self.in_recovery = True
        self.recovery_context = RecoveryContext(
            trigger=trigger,
            detected_at=datetime.now(timezone.utc),
            recent_messages=self.message_history.copy(),
            confidence=0.8
        )
        
        # Determine action based on trigger
        if trigger == RecoveryTrigger.QUESTIONING:
            action = RecoveryAction.URGENT_CALL
        elif trigger == RecoveryTrigger.HALLUCINATION:
            action = RecoveryAction.HUMBLE_CORRECTION
        elif trigger == RecoveryTrigger.NAME_MENTION:
            action = RecoveryAction.PAUSE_AND_THINK
        else:
            action = RecoveryAction.DEFER_TO_HUMAN
        
        logger.info(f"Recovery initiated: {trigger.value} -> {action.value}")
        return action
    
    def get_urgent_call_response(self) -> str:
        """
        Get urgent call escape sequence response
        
        Returns:
            Response text
        """
        return "Hoppsan, ursäkta mig... jag har ett extremt brådskande samtal. Två sekunder bara!"
    
    def get_humble_correction(self, error_context: str) -> str:
        """
        Get humble correction response
        
        Args:
            error_context: Context of the error
        
        Returns:
            Correction text
        """
        return f"Förlåt, jag tror jag missförstod där. Låt mig omformulera. {error_context}"
    
    def complete_recovery(self):
        """Complete recovery sequence"""
        if not self.in_recovery:
            return
        
        self.in_recovery = False
        self.recovery_context = None
        logger.info("Recovery completed")
    
    def analyze_recent_context(self) -> Optional[Dict[str, Any]]:
        """
        Analyze recent message context for potential issues
        
        Returns:
            Analysis result or None
        """
        if len(self.message_history) < 2:
            return None
        
        # Check for contradictions
        recent = self.message_history[-3:]
        
        # Simple contradiction detection
        if "ja" in recent[-1].lower() and "nej" in recent[-2].lower():
            return {
                "issue": "contradiction",
                "messages": recent,
                "suggestion": "Clarify the contradiction"
            }
        
        return None
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """Get recovery engine status"""
        return {
            "is_active": self.is_active,
            "in_recovery": self.in_recovery,
            "recovery_context": self.recovery_context.to_dict() if self.recovery_context else None,
            "message_count": len(self.message_history)
        }


# Singleton instance
recovery_engine = RecoveryEngine()


async def main():
    """Test Recovery Engine"""
    logger.add("logs/recovery_engine_{time}.log", rotation="10 MB")
    
    # Activate engine
    recovery_engine.activate()
    
    # Test name mention
    recovery_engine.add_message("Anton, kan du hjälpa mig?", is_agent=False)
    trigger = recovery_engine.detect_triggers("Anton, kan du hjälpa mig?", is_agent=False)
    
    if trigger:
        action = recovery_engine.initiate_recovery(trigger)
        logger.info(f"Action: {action.value}")
        
        if action == RecoveryAction.URGENT_CALL:
            response = recovery_engine.get_urgent_call_response()
            logger.info(f"Response: {response}")
    
    # Get status
    status = recovery_engine.get_recovery_status()
    logger.info(f"Status: {status}")
    
    logger.info("Recovery Engine test complete")


if __name__ == "__main__":
    asyncio.run(main())
