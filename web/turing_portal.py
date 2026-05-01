#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Turing Test Portal
Public A/B testing framework for Turing-test evaluation
Phase 24: TuringTest.online
"""

import asyncio
import random
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone

from loguru import logger


class TestVariant(Enum):
    """A/B test variants"""
    ANTON_EGON = "anton_egon"  # AI twin
    HUMAN = "human"  # Real human
    CONTROL = "control"  # No response


class AvailabilityStatus(Enum):
    """Fake availability status"""
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


@dataclass
class TestSession:
    """Turing test session"""
    session_id: str
    variant: TestVariant
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    messages: List[Dict[str, Any]] = field(default_factory=list)
    user_guess: Optional[str] = None
    ground_truth: Optional[str] = None
    feedback: Optional[str] = None
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "variant": self.variant.value,
            "start_time": self.start_time.isoformat(),
            "messages": self.messages,
            "user_guess": self.user_guess,
            "ground_truth": self.ground_truth,
            "feedback": self.feedback,
            "confidence": self.confidence
        }


@dataclass
class FeedbackData:
    """Ground truth feedback data"""
    session_id: str
    user_guess: str
    actual_variant: str
    confidence: float
    feedback_text: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_guess": self.user_guess,
            "actual_variant": self.actual_variant,
            "confidence": self.confidence,
            "feedback_text": self.feedback_text,
            "timestamp": self.timestamp.isoformat()
        }


class TuringPortalConfig:
    """Turing Portal configuration"""
    enable_fake_availability: bool = True
    availability_probability: float = 0.7  # 70% chance of being available
    busy_probability: float = 0.2  # 20% chance of being busy
    offline_probability: float = 0.1  # 10% chance of being offline
    enable_ground_truth_collection: bool = True
    ab_test_ratio: float = 0.5  # 50/50 split between AI and human


class TuringPortal:
    """
    Turing Test Portal
    Public A/B testing framework for Turing-test evaluation
    """
    
    def __init__(self, config: TuringPortalConfig = None):
        """
        Initialize Turing Portal
        
        Args:
            config: Portal configuration
        """
        self.config = config or TuringPortalConfig()
        self.sessions: Dict[str, TestSession] = {}
        self.feedback_data: List[FeedbackData] = []
        self.current_availability = AvailabilityStatus.AVAILABLE
        
        logger.info("Turing Portal initialized")
    
    def get_availability(self) -> AvailabilityStatus:
        """
        Fas 24: Get current availability status (Fake Availability logic)
        
        Returns:
            Availability status
        """
        if not self.config.enable_fake_availability:
            return AvailabilityStatus.AVAILABLE
        
        # Randomly determine availability based on probabilities
        rand = random.random()
        
        if rand < self.config.offline_probability:
            self.current_availability = AvailabilityStatus.OFFLINE
        elif rand < self.config.offline_probability + self.config.busy_probability:
            self.current_availability = AvailabilityStatus.BUSY
        else:
            self.current_availability = AvailabilityStatus.AVAILABLE
        
        return self.current_availability
    
    def create_session(self, user_id: str = "anonymous") -> TestSession:
        """
        Create new test session with A/B variant assignment
        
        Args:
            user_id: User identifier
        
        Returns:
            Test session
        """
        import uuid
        
        session_id = str(uuid.uuid4())[:8]
        
        # Assign variant based on A/B test ratio
        if random.random() < self.config.ab_test_ratio:
            variant = TestVariant.ANTON_EGON
        else:
            variant = TestVariant.HUMAN
        
        session = TestSession(
            session_id=session_id,
            variant=variant
        )
        
        self.sessions[session_id] = session
        logger.info(f"Created session {session_id} with variant {variant.value}")
        
        return session
    
    def add_message(self, session_id: str, sender: str, text: str):
        """
        Add message to session transcript
        
        Args:
            session_id: Session identifier
            sender: Sender name
            text: Message text
        """
        if session_id not in self.sessions:
            return
        
        self.sessions[session_id].messages.append({
            "sender": sender,
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def submit_guess(self, session_id: str, guess: str, confidence: float = 0.0) -> bool:
        """
        Submit user's guess about whether they spoke to AI or human
        
        Args:
            session_id: Session identifier
            guess: User's guess ("ai" or "human")
            confidence: User's confidence (0-1)
        
        Returns:
            True if submitted successfully
        """
        if session_id not in self.sessions:
            return False
        
        self.sessions[session_id].user_guess = guess
        self.sessions[session_id].confidence = confidence
        self.sessions[session_id].ground_truth = self.sessions[session_id].variant.value
        
        logger.info(f"Session {session_id}: User guessed {guess} (confidence: {confidence})")
        return True
    
    def submit_feedback(self, session_id: str, feedback: str) -> bool:
        """
        Fas 24: Submit feedback for Ground Truth data collection
        
        Args:
            session_id: Session identifier
            feedback: Feedback text
        
        Returns:
            True if submitted successfully
        """
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        
        feedback_data = FeedbackData(
            session_id=session_id,
            user_guess=session.user_guess or "unknown",
            actual_variant=session.variant.value,
            confidence=session.confidence,
            feedback_text=feedback
        )
        
        self.feedback_data.append(feedback_data)
        session.feedback = feedback
        
        logger.info(f"Feedback submitted for session {session_id}")
        return True
    
    def get_session(self, session_id: str) -> Optional[TestSession]:
        """
        Get session by ID
        
        Args:
            session_id: Session identifier
        
        Returns:
            Test session or None
        """
        return self.sessions.get(session_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get portal statistics
        
        Returns:
            Statistics dictionary
        """
        total_sessions = len(self.sessions)
        ai_sessions = sum(1 for s in self.sessions.values() if s.variant == TestVariant.ANTON_EGON)
        human_sessions = sum(1 for s in self.sessions.values() if s.variant == TestVariant.HUMAN)
        
        correct_guesses = 0
        for session in self.sessions.values():
            if session.user_guess:
                if (session.user_guess == "ai" and session.variant == TestVariant.ANTON_EGON) or \
                   (session.user_guess == "human" and session.variant == TestVariant.HUMAN):
                    correct_guesses += 1
        
        accuracy = correct_guesses / total_sessions if total_sessions > 0 else 0
        
        return {
            "total_sessions": total_sessions,
            "ai_sessions": ai_sessions,
            "human_sessions": human_sessions,
            "correct_guesses": correct_guesses,
            "accuracy": accuracy,
            "feedback_count": len(self.feedback_data),
            "current_availability": self.current_availability.value
        }
    
    def export_ground_truth(self) -> List[Dict[str, Any]]:
        """
        Export Ground Truth data for analysis
        
        Returns:
            List of feedback data dictionaries
        """
        return [f.to_dict() for f in self.feedback_data]


# Singleton instance
turing_portal: Optional[TuringPortal] = None


def initialize_turing_portal(config: TuringPortalConfig = None) -> TuringPortal:
    """Initialize Turing Portal singleton"""
    global turing_portal
    turing_portal = TuringPortal(config)
    return turing_portal


async def main():
    """Test Turing Portal"""
    logger.add("logs/turing_portal_{time}.log", rotation="10 MB")
    
    portal = initialize_turing_portal()
    
    # Test availability
    availability = portal.get_availability()
    logger.info(f"Current availability: {availability.value}")
    
    # Create test session
    session = portal.create_session("test_user")
    logger.info(f"Session created: {session.to_dict()}")
    
    # Add messages
    portal.add_message(session.session_id, "User", "Hello, how are you?")
    portal.add_message(session.session_id, "Anton", "I'm doing well, thanks for asking!")
    
    # Submit guess
    portal.submit_guess(session.session_id, "ai", confidence=0.8)
    
    # Submit feedback
    portal.submit_feedback(session.session_id, "The response felt slightly robotic but natural")
    
    # Get statistics
    stats = portal.get_statistics()
    logger.info(f"Portal statistics: {stats}")
    
    logger.info("Turing Portal test complete")


if __name__ == "__main__":
    asyncio.run(main())
