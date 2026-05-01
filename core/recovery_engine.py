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
    LOW_CONFIDENCE = "low_confidence"  # Sprint 5: Confidence < 70%
    HIGH_STRESS = "high_stress"  # Bio-Feedback: High stress detected
    ELEVATED_HEART_RATE = "elevated_heart_rate"  # Bio-Feedback: Elevated heart rate


class RecoveryAction(Enum):
    """Recovery action types"""
    URGENT_CALL = "urgent_call"  # "Hoppsan, extremt brådskande samtal"
    HUMBLE_CORRECTION = "humble_correction"  # Correct previous statement
    PAUSE_AND_THINK = "pause_and_think"  # Pause before responding
    DEFER_TO_HUMAN = "defer_to_human"  # "Låt mig fråga min operatör"
    SILENCE = "silence"  # Stop speaking
    CLARIFICATION_PROMPT = "clarification_prompt"  # Sprint 5: Ask for clarification when confidence < 70%


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


class DeviceType(Enum):
    """Bio-feedback device types"""
    APPLE_WATCH = "apple_watch"
    SAMSUNG_WATCH = "samsung_watch"
    ANDROID_PHONE = "android_phone"
    IPHONE = "iphone"
    FITBIT = "fitbit"
    GARMIN = "garmin"


@dataclass
class BioFeedbackData:
    """Bio-feedback data from wearable devices"""
    device_type: DeviceType
    device_id: str
    heart_rate: Optional[float] = None  # BPM
    heart_rate_variability: Optional[float] = None  # HRV in ms
    stress_level: Optional[float] = None  # 0-100
    oxygen_saturation: Optional[float] = None  # SpO2 percentage
    skin_temperature: Optional[float] = None  # Celsius
    activity_level: Optional[str] = None  # resting, walking, running, etc.
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_type": self.device_type.value,
            "device_id": self.device_id,
            "heart_rate": self.heart_rate,
            "heart_rate_variability": self.heart_rate_variability,
            "stress_level": self.stress_level,
            "oxygen_saturation": self.oxygen_saturation,
            "skin_temperature": self.skin_temperature,
            "activity_level": self.activity_level,
            "timestamp": self.timestamp.isoformat()
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
        
        # Sprint 5: Identity Verification - Confidence threshold
        self.confidence_threshold = 0.7  # 70% confidence threshold
        self.enable_identity_verification = True
        
        # Bio-Feedback thresholds
        self.stress_threshold = 70.0  # Stress level > 70 triggers recovery
        self.heart_rate_threshold = 100.0  # Heart rate > 100 BPM triggers recovery
        self.enable_bio_feedback = True
        
        # Bio-feedback history
        self.bio_feedback_history: List[BioFeedbackData] = []
        self.max_bio_history = 50
        
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
    
    def detect_triggers(self, message: str, is_agent: bool = True, confidence: Optional[float] = None) -> Optional[RecoveryTrigger]:
        """
        Detect recovery triggers in message
        
        Args:
            message: Message text
            is_agent: True if message is from agent, False if from user
            confidence: Sprint 5: Confidence score (0-1) for identity verification
        
        Returns:
            Detected trigger or None
        """
        if not self.is_active or self.in_recovery:
            return None
        
        # Sprint 5: Identity Verification - Check confidence threshold
        if self.enable_identity_verification and confidence is not None and confidence < self.confidence_threshold:
            logger.warning(f"Low confidence detected: {confidence:.2f} < {self.confidence_threshold}")
            return RecoveryTrigger.LOW_CONFIDENCE
        
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
    
    def initiate_recovery(self, trigger: RecoveryTrigger, confidence: Optional[float] = None) -> RecoveryAction:
        """
        Initiate recovery sequence based on trigger
        
        Args:
            trigger: Detected trigger
            confidence: Sprint 5: Confidence score for context
        
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
            confidence=confidence or 0.8,
            metadata={"confidence_score": confidence} if confidence else {}
        )
        
        # Determine action based on trigger
        if trigger == RecoveryTrigger.QUESTIONING:
            action = RecoveryAction.URGENT_CALL
        elif trigger == RecoveryTrigger.HALLUCINATION:
            action = RecoveryAction.HUMBLE_CORRECTION
        elif trigger == RecoveryTrigger.NAME_MENTION:
            action = RecoveryAction.PAUSE_AND_THINK
        elif trigger == RecoveryTrigger.LOW_CONFIDENCE:
            # Sprint 5: Identity Verification - Ask for clarification
            action = RecoveryAction.CLARIFICATION_PROMPT
        else:
            action = RecoveryAction.DEFER_TO_HUMAN
        
        logger.info(f"Recovery initiated: {trigger.value} -> {action.value}")
        return action
    
    def get_urgent_call_response(self) -> str:
        """
        Get urgent call escape sequence response
        
        Returns:
            Urgent call response text
        """
        return "Hoppsan, extremt brådskande samtal kommer in. Jag måste ta detta, återkommer om en stund."
    
    def get_clarification_prompt(self, confidence: float, context: str) -> str:
        """
        Sprint 5: Get clarification prompt when confidence is low
        
        Args:
            confidence: Confidence score (0-1)
            context: Context about what needs clarification
        
        Returns:
            Clarification prompt text
        """
        prompts = [
            f"Förlåt, jag är inte helt säker på vad du menar. Kan du förtydliga?",
            f"Jag vill vara säker på att jag förstår rätt. Kan du utveckla lite?",
            f"Kan du ge mig mer kontext så jag kan svara korrekt?",
            f"Jag vill undvika missförstånd. Vad menar du exakt?",
            f"För att jag ska kunna hjälpa dig bäst, kan du förklara mer?"
        ]
        
        # Select prompt based on confidence level
        if confidence < 0.5:
            return prompts[0]  # More direct when confidence is very low
        elif confidence < 0.6:
            return prompts[1]
        elif confidence < 0.7:
            return prompts[2]
        else:
            return prompts[3]
    
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
    
    # ═══════════════════════════════════════════════════════════════
    # BIO-FEEDBACK ENDPOINTS (Apple Watch, Samsung Watch, Android, iPhone)
    # ═══════════════════════════════════════════════════════════════
    def receive_bio_feedback(self, device_type: DeviceType, device_id: str, 
                            heart_rate: float = None, heart_rate_variability: float = None,
                            stress_level: float = None, oxygen_saturation: float = None,
                            skin_temperature: float = None, activity_level: str = None) -> Optional[RecoveryTrigger]:
        """
        Receive bio-feedback data from wearable device
        
        Args:
            device_type: Type of device (Apple Watch, Samsung Watch, Android, iPhone)
            device_id: Unique device identifier
            heart_rate: Heart rate in BPM
            heart_rate_variability: HRV in ms
            stress_level: Stress level 0-100
            oxygen_saturation: SpO2 percentage
            skin_temperature: Skin temperature in Celsius
            activity_level: Activity level (resting, walking, running, etc.)
        
        Returns:
            Recovery trigger if threshold exceeded, None otherwise
        """
        if not self.enable_bio_feedback:
            return None
        
        # Create bio-feedback data object
        bio_data = BioFeedbackData(
            device_type=device_type,
            device_id=device_id,
            heart_rate=heart_rate,
            heart_rate_variability=heart_rate_variability,
            stress_level=stress_level,
            oxygen_saturation=oxygen_saturation,
            skin_temperature=skin_temperature,
            activity_level=activity_level
        )
        
        # Add to history
        self.bio_feedback_history.append(bio_data)
        if len(self.bio_feedback_history) > self.max_bio_history:
            self.bio_feedback_history.pop(0)
        
        # Check thresholds
        trigger = self.check_bio_feedback_thresholds(bio_data)
        
        if trigger:
            logger.warning(f"Bio-feedback trigger detected: {trigger.value} from {device_type.value}")
        
        return trigger
    
    def check_bio_feedback_thresholds(self, bio_data: BioFeedbackData) -> Optional[RecoveryTrigger]:
        """
        Check if bio-feedback data exceeds thresholds
        
        Args:
            bio_data: Bio-feedback data
        
        Returns:
            Recovery trigger if threshold exceeded, None otherwise
        """
        trigger = None
        
        # Check stress level
        if bio_data.stress_level is not None and bio_data.stress_level > self.stress_threshold:
            trigger = RecoveryTrigger.HIGH_STRESS
        
        # Check heart rate
        if bio_data.heart_rate is not None and bio_data.heart_rate > self.heart_rate_threshold:
            trigger = RecoveryTrigger.ELEVATED_HEART_RATE
        
        return trigger
    
    def get_apple_watch_data(self, device_id: str, **kwargs) -> Optional[RecoveryTrigger]:
        """
        Receive bio-feedback data from Apple Watch
        
        Args:
            device_id: Apple Watch device identifier
            **kwargs: Bio-feedback parameters
        
        Returns:
            Recovery trigger if threshold exceeded
        """
        return self.receive_bio_feedback(DeviceType.APPLE_WATCH, device_id, **kwargs)
    
    def get_samsung_watch_data(self, device_id: str, **kwargs) -> Optional[RecoveryTrigger]:
        """
        Receive bio-feedback data from Samsung Watch
        
        Args:
            device_id: Samsung Watch device identifier
            **kwargs: Bio-feedback parameters
        
        Returns:
            Recovery trigger if threshold exceeded
        """
        return self.receive_bio_feedback(DeviceType.SAMSUNG_WATCH, device_id, **kwargs)
    
    def get_android_data(self, device_id: str, **kwargs) -> Optional[RecoveryTrigger]:
        """
        Receive bio-feedback data from Android phone
        
        Args:
            device_id: Android device identifier
            **kwargs: Bio-feedback parameters
        
        Returns:
            Recovery trigger if threshold exceeded
        """
        return self.receive_bio_feedback(DeviceType.ANDROID_PHONE, device_id, **kwargs)
    
    def get_iphone_data(self, device_id: str, **kwargs) -> Optional[RecoveryTrigger]:
        """
        Receive bio-feedback data from iPhone
        
        Args:
            device_id: iPhone device identifier
            **kwargs: Bio-feedback parameters
        
        Returns:
            Recovery trigger if threshold exceeded
        """
        return self.receive_bio_feedback(DeviceType.IPHONE, device_id, **kwargs)
    
    def get_bio_feedback_summary(self) -> Dict[str, Any]:
        """
        Get summary of recent bio-feedback data
        
        Returns:
            Summary dictionary
        """
        if not self.bio_feedback_history:
            return {"message": "No bio-feedback data available"}
        
        # Calculate averages
        heart_rates = [d.heart_rate for d in self.bio_feedback_history if d.heart_rate is not None]
        stress_levels = [d.stress_level for d in self.bio_feedback_history if d.stress_level is not None]
        
        avg_heart_rate = sum(heart_rates) / len(heart_rates) if heart_rates else None
        avg_stress = sum(stress_levels) / len(stress_levels) if stress_levels else None
        
        # Count by device type
        device_counts = {}
        for data in self.bio_feedback_history:
            device_type = data.device_type.value
            device_counts[device_type] = device_counts.get(device_type, 0) + 1
        
        return {
            "total_readings": len(self.bio_feedback_history),
            "average_heart_rate": avg_heart_rate,
            "average_stress_level": avg_stress,
            "device_counts": device_counts,
            "latest_reading": self.bio_feedback_history[-1].to_dict() if self.bio_feedback_history else None
        }
    
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
