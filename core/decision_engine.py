#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Decision Engine
Context-aware decision making for agent actions
"""

import asyncio
import random
import sys
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from enum import Enum

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from pydantic import BaseModel, Field


class DecisionMode(Enum):
    """Decision modes for the agent"""
    DIRECT_RESPONSE = "direct_response"
    FILLER_RESPONSE = "filler_response"
    CONTEXTUAL_FILLER = "contextual_filler"
    WAIT_FOR_MORE = "wait_for_more"
    DISTRACTION_ACTION = "distraction_action"
    INTERRUPT = "interrupt"
    OFF_THE_RECORD = "off_the_record"


class ActionClipType(Enum):
    """Types of action clips for contextual fillers"""
    THINKING_SIDE = "thinking_side"  # Look at side screen
    CHECKING_NOTES = "checking_notes"  # Look down at notes
    CALCULATING = "calculating"  # Hand gesture for calculating
    SEARCHING = "searching"  # Typing gesture
    CONFIRMING = "confirming"  # Nodding gesture


class DecisionConfig(BaseModel):
    """Configuration for decision engine"""
    max_latency_ms: float = Field(default=1500, description="Max acceptable latency before filler")
    filler_probability: float = Field(default=0.3, description="Probability of using filler")
    distraction_threshold: float = Field(default=0.6, description="Confidence threshold for distraction")
    interrupt_on_vad: bool = Field(default=True, description="Interrupt on voice activity detection")
    safety_hotkey: str = Field(default="F12", description="Hotkey for off-the-record mode")
    context_window_minutes: int = Field(default=5, description="Context buffer window in minutes")
    enable_contextual_fillers: bool = Field(default=True, description="Enable contextual fillers")


class DecisionEngine:
    """
    Decision engine for choosing agent responses
    Weighs input signals: Text + Emotion + Agenda + Memory
    Implements latency masking and interrupt logic
    """
    
    def __init__(self, config: DecisionConfig):
        """Initialize decision engine"""
        self.config = config
        
        # State
        self.current_mode = DecisionMode.WAIT_FOR_MORE
        self.is_speaking = False
        self.last_response_time = None
        self.off_the_record_mode = False
        
        # Context
        self.context_buffer: List[Dict[str, Any]] = []
        self.agenda: Optional[str] = None
        self.previous_notes: Optional[str] = None
        
        # Contextual filler mappings
        self.contextual_fillers = self._init_contextual_fillers()
        
        logger.info("Decision Engine initialized")
    
    def load_meeting_context(self, agenda_path: str, notes_path: str):
        """Load meeting agenda and previous notes"""
        try:
            from pathlib import Path
            
            agenda_file = Path(agenda_path)
            if agenda_file.exists():
                with open(agenda_file, 'r', encoding='utf-8') as f:
                    self.agenda = f.read()
                logger.info(f"Loaded meeting agenda from {agenda_path}")
            
            notes_file = Path(notes_path)
            if notes_file.exists():
                with open(notes_file, 'r', encoding='utf-8') as f:
                    self.previous_notes = f.read()
                logger.info(f"Loaded previous notes from {notes_path}")
            
        except Exception as e:
            logger.error(f"Failed to load meeting context: {e}")
    
    def _init_contextual_fillers(self) -> Dict[str, Dict[str, Any]]:
        """
        Initialize contextual filler mappings
        Maps question types to specific filler phrases and action clips
        
        Returns:
            Dictionary of contextual filler configurations
        """
        return {
            "pricing": {
                "keywords": ["pris", "kostnad", "offert", "budget", "pengar", "kronor", "sek"],
                "phrases": [
                    "Bra fråga, låt mig bara dubbelkolla den exakta siffran här...",
                    "Det där är en viktig detalj, jag behöver verifiera prissättningen...",
                    "Låt mig kolla de aktuella priserna..."
                ],
                "action_clip": ActionClipType.CHECKING_NOTES,
                "priority": "high"
            },
            "technical": {
                "keywords": ["teknisk", "specifikation", "funktion", "hur fungerar", "teknologi"],
                "phrases": [
                    "Det är en teknisk detalj, låt mig kolla specifikationen...",
                    "Jag behöver verifiera den tekniska informationen...",
                    "Låt mig se hur det fungerar i detalj..."
                ],
                "action_clip": ActionClipType.SEARCHING,
                "priority": "medium"
            },
            "timeline": {
                "keywords": ["tidslinje", "deadline", "tidsplan", "när", "tid", "vecka", "månad"],
                "phrases": [
                    "Låt mig kolla tidsplanen för det...",
                    "Jag behöver dubbelkolla datumet...",
                    "Vad gäller tidslinjen, låt mig se..."
                ],
                "action_clip": ActionClipType.CHECKING_NOTES,
                "priority": "medium"
            },
            "data": {
                "keywords": ["data", "siffror", "statistik", "rapport", "mätning", "analys"],
                "phrases": [
                    "Jag behöver titta på data för det...",
                    "Låt mig kolla statistiken...",
                    "Det där kräver lite data-analys..."
                ],
                "action_clip": ActionClipType.CALCULATING,
                "priority": "medium"
            },
            "agreement": {
                "keywords": ["avtal", "kontrakt", "villkor", "regler", "policy", "överenskommelse"],
                "phrases": [
                    "Jag behöver kolla villkoren i avtalet...",
                    "Låt mig läsa igenom kontraktet...",
                    "Vad gäller avtalet, jag måste verifiera..."
                ],
                "action_clip": ActionClipType.CHECKING_NOTES,
                "priority": "high"
            },
            "contact": {
                "keywords": ["kontakta", "mail", "telefon", "person", "namn", "vem"],
                "phrases": [
                    "Jag behöver kolla vem som är ansvarig...",
                    "Låt mig se kontaktpersonen...",
                    "Jag måste dubbelkolla den informationen..."
                ],
                "action_clip": ActionClipType.SEARCHING,
                "priority": "low"
            }
        }
    
    def add_to_context(self, event: Dict[str, Any]):
        """Add event to context buffer"""
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.context_buffer.append(event)
        
        # Keep only events within context window
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=self.config.context_window_minutes)
        self.context_buffer = [
            e for e in self.context_buffer 
            if datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")) > cutoff_time
        ]
    
    def get_context(self) -> List[Dict[str, Any]]:
        """Get current context buffer"""
        return self.context_buffer.copy()
    
    def check_conflict_resolution(self, user_statement: str) -> Optional[str]:
        """
        Check for conflicts between agenda and user statements
        Returns conflict response if needed
        """
        if not self.agenda:
            return None
        
        # Simple conflict detection (can be enhanced)
        conflict_keywords = ["menar", "säger", "påstår", "tycker"]
        for keyword in conflict_keywords:
            if keyword in user_statement.lower():
                # Check if this contradicts agenda
                # This is a simplified version - real implementation would use NLP
                return "Jag har noterat det du säger, låt mig dubbelkolla mot våra interna underlag och återkomma."
        
        return None
    
    def should_use_filler(self, latency_ms: float) -> bool:
        """Determine if filler should be used based on latency"""
        if latency_ms > self.config.max_latency_ms:
            logger.info(f"Latency {latency_ms}ms exceeds threshold, using filler")
            return True
        
        # Random filler based on probability
        if random.random() < self.config.filler_probability:
            logger.debug("Using random filler")
            return True
        
        return False
    
    def should_interrupt(self, vad_detected: bool) -> bool:
        """Determine if agent should interrupt current speech"""
        if not self.config.interrupt_on_vad:
            return False
        
        if vad_detected and self.is_speaking:
            logger.info("VAD detected, interrupting speech")
            return True
        
        return False
    
    def decide_response_mode(
        self,
        transcription: str,
        emotion: str,
        confidence: float,
        vad_detected: bool = False
    ) -> DecisionMode:
        """
        Decide on response mode based on input signals
        
        Args:
            transcription: Current transcription
            emotion: Detected emotion
            confidence: LLM confidence score
            vad_detected: Voice activity detected
        
        Returns:
            DecisionMode to use
        """
        # Check off-the-record mode
        if self.off_the_record_mode:
            logger.info("Off-the-record mode active")
            return DecisionMode.OFF_THE_RECORD
        
        # Check for interrupt
        if self.should_interrupt(vad_detected):
            return DecisionMode.INTERRUPT
        
        # Check for conflict resolution
        conflict_response = self.check_conflict_resolution(transcription)
        if conflict_response:
            logger.info("Conflict detected, using conflict resolution")
            return DecisionMode.WAIT_FOR_MORE
        
        # Check for contextual filler
        contextual_filler = self.get_contextual_filler(transcription)
        if contextual_filler:
            logger.info(f"Contextual filler detected: {contextual_filler['context']}")
            return DecisionMode.CONTEXTUAL_FILLER
        
        # Check confidence threshold
        if confidence < self.config.distraction_threshold:
            logger.info(f"Low confidence ({confidence}), using distraction")
            return DecisionMode.DISTRACTION_ACTION
        
        # Check for complex questions (simple heuristic)
        complex_indicators = ["hur", "varför", "vilken", "vilka", "förklara", "beskriv"]
        if any(indicator in transcription.lower() for indicator in complex_indicators):
            logger.info("Complex question detected, may use distraction")
            # 50% chance of distraction for complex questions
            if random.random() < 0.5:
                return DecisionMode.DISTRACTION_ACTION
        
        # Default to direct response
        return DecisionMode.DIRECT_RESPONSE
    
    def get_filler_phrase(self) -> str:
        """Get a random filler phrase"""
        fillers = [
            "Hmm, låt mig se här...",
            "Det är en intressant fråga...",
            "Jag behöver tänka ett ögonblick...",
            "Låt mig formulera om det...",
            "Just det, jag minns...",
            "Vad var det jag skulle säga..."
        ]
        return random.choice(fillers)
    
    def get_contextual_filler_phrase(self, transcription: str) -> Optional[str]:
        """
        Get contextual filler phrase based on question context
        
        Args:
            transcription: User transcription
        
        Returns:
            Contextual filler phrase or None if no context detected
        """
        contextual_filler = self.get_contextual_filler(transcription)
        if contextual_filler:
            return contextual_filler["phrase"]
        return None
    
    def get_action_clip_for_filler(self, transcription: str) -> Optional[ActionClipType]:
        """
        Get action clip type for contextual filler
        
        Args:
            transcription: User transcription
        
        Returns:
            Action clip type or None if no context detected
        """
        contextual_filler = self.get_contextual_filler(transcription)
        if contextual_filler:
            return contextual_filler["action_clip"]
        return None
    
    def toggle_off_the_record(self):
        """Toggle off-the-record mode"""
        self.off_the_record_mode = not self.off_the_record_mode
        status = "enabled" if self.off_the_record_mode else "disabled"
        logger.info(f"Off-the-record mode {status}")
        
        return self.off_the_record_mode
    
    def get_off_the_record_response(self) -> str:
        """Get response for off-the-record mode"""
        return "Vänta, jag ska bara ta det här samtalet."
    
    def set_speaking_state(self, is_speaking: bool):
        """Set speaking state"""
        self.is_speaking = is_speaking
        if is_speaking:
            self.last_response_time = datetime.now(timezone.utc)
    
    def get_decision_summary(self) -> Dict[str, Any]:
        """Get summary of current decision state"""
        return {
            "current_mode": self.current_mode.value,
            "is_speaking": self.is_speaking,
            "off_the_record_mode": self.off_the_record_mode,
            "context_size": len(self.context_buffer),
            "agenda_loaded": self.agenda is not None,
            "notes_loaded": self.previous_notes is not None,
            "contextual_fillers_enabled": self.config.enable_contextual_fillers,
            "contextual_filler_count": len(self.contextual_fillers),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test the decision engine"""
    from loguru import logger
    
    logger.add("logs/decision_engine_{time}.log", rotation="10 MB")
    
    # Create decision engine
    config = DecisionConfig()
    engine = DecisionEngine(config)
    
    # Test decision making
    transcription = "Vad tror du om priset på den här produkten?"
    emotion = "Neutral"
    confidence = 0.8
    
    mode = engine.decide_response_mode(transcription, emotion, confidence)
    logger.info(f"Decision mode: {mode.value}")
    
    # Test filler
    filler = engine.get_filler_phrase()
    logger.info(f"Filler phrase: {filler}")
    
    # Test context
    engine.add_to_context({"type": "transcription", "text": "Hej"})
    engine.add_to_context({"type": "emotion", "emotion": "Happy"})
    
    logger.info(f"Context: {engine.get_context()}")
    logger.info(f"Decision summary: {engine.get_decision_summary()}")


if __name__ == "__main__":
    asyncio.run(main())
