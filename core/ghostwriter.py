#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Ghostwriter Mode
Autonomous meeting handling with VETO/Takeover controls
Phase 23: Ghostwriter Mode
"""

import asyncio
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import deque

from loguru import logger


class GhostwriterMode(Enum):
    """Ghostwriter operating modes"""
    PASSIVE = "passive"  # Listen only, no responses
    ASSISTIVE = "assistive"  Suggest responses, require approval
    AUTONOMOUS = "autonomous"  # Full autonomous responses
    VETO_ONLY = "veto_only"  # Only intervene when VETO triggered


class InterventionTrigger(Enum):
    """Triggers for Ghostwriter intervention"""
    CONFUSION = "confusion"  # User seems confused
    STUCK = "stuck"  # Conversation stuck
    MISUNDERSTANDING = "misunderstanding"  # Misunderstanding detected
    REQUEST = "request"  # Explicit user request for help


@dataclass
class MeetingContext:
    """Context for active meeting"""
    meeting_id: str
    participants: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "participants": self.participants,
            "start_time": self.start_time.isoformat(),
            "transcript": self.transcript,
            "action_items": self.action_items,
            "decisions": self.decisions
        }


@dataclass
class Intervention:
    """Ghostwriter intervention"""
    intervention_id: str
    trigger: InterventionTrigger
    suggested_response: str
    confidence: float
    timestamp: datetime
    approved: bool = False
    vetoed: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intervention_id": self.intervention_id,
            "trigger": self.trigger.value,
            "suggested_response": self.suggested_response,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "approved": self.approved,
            "vetoed": self.vetoed
        }


class GhostwriterConfig:
    """Ghostwriter configuration"""
    default_mode: GhostwriterMode = GhostwriterMode.ASSISTIVE
    enable_auto_summary: bool = True
    enable_slack_integration: bool = False
    slack_webhook_url: Optional[str] = None
    max_transcript_length: int = 1000  # Max messages in transcript
    intervention_threshold: float = 0.7  # Confidence threshold for intervention


class Ghostwriter:
    """
    Ghostwriter Mode
    Autonomous meeting handling with VETO/Takeover controls
    """
    
    def __init__(self, config: GhostwriterConfig = None):
        """
        Initialize Ghostwriter
        
        Args:
            config: Ghostwriter configuration
        """
        self.config = config or GhostwriterConfig()
        self.mode = self.config.default_mode
        self.is_active = False
        self.current_meeting: Optional[MeetingContext] = None
        self.interventions: List[Intervention] = []
        self.recent_messages: deque = deque(maxlen=20)
        
        logger.info("Ghostwriter initialized")
    
    def activate(self, meeting_id: str, participants: List[str] = None):
        """
        Activate Ghostwriter for a meeting
        
        Args:
            meeting_id: Meeting identifier
            participants: List of participant names
        """
        self.current_meeting = MeetingContext(
            meeting_id=meeting_id,
            participants=participants or []
        )
        self.is_active = True
        self.interventions = []
        self.recent_messages.clear()
        
        logger.info(f"Ghostwriter activated for meeting {meeting_id}")
    
    def deactivate(self):
        """Deactivate Ghostwriter"""
        self.is_active = False
        self.current_meeting = None
        logger.info("Ghostwriter deactivated")
    
    def set_mode(self, mode: GhostwriterMode):
        """
        Set Ghostwriter mode
        
        Args:
            mode: Operating mode
        """
        self.mode = mode
        logger.info(f"Ghostwriter mode set to {mode.value}")
    
    def add_transcript_entry(self, speaker: str, text: str, is_ai: bool = False):
        """
        Add entry to meeting transcript
        
        Args:
            speaker: Speaker name
            text: Spoken text
            is_ai: True if Anton Egon spoke
        """
        if not self.current_meeting:
            return
        
        entry = {
            "speaker": speaker,
            "text": text,
            "is_ai": is_ai,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self.current_meeting.transcript.append(entry)
        self.recent_messages.append(entry)
        
        # Limit transcript length
        if len(self.current_meeting.transcript) > self.config.max_transcript_length:
            self.current_meeting.transcript.pop(0)
        
        logger.debug(f"Transcript entry added: {speaker}")
    
    def detect_intervention_opportunity(self) -> Optional[InterventionTrigger]:
        """
        Detect if intervention is needed
        
        Returns:
            Trigger type or None
        """
        if not self.is_active or self.mode == GhostwriterMode.PASSIVE:
            return None
        
        # Analyze recent messages for intervention triggers
        recent_text = " ".join([m["text"] for m in self.recent_messages]).lower()
        
        # Check for confusion indicators
        confusion_patterns = ["jag förstår inte", "vad menar du", "kan du förklara", "förvirrad"]
        if any(pattern in recent_text for pattern in confusion_patterns):
            return InterventionTrigger.CONFUSION
        
        # Check for stuck conversation
        if len(self.recent_messages) >= 10:
            last_10 = list(self.recent_messages)[-10:]
            if all(m["speaker"] == last_10[0]["speaker"] for m in last_10):
                return InterventionTrigger.STUCK
        
        # Check for misunderstanding
        misunderstanding_patterns = ["det var inte det jag sa", "du missförstod", "fel"]
        if any(pattern in recent_text for pattern in misunderstanding_patterns):
            return InterventionTrigger.MISUNDERSTANDING
        
        return None
    
    def generate_intervention(self, trigger: InterventionTrigger) -> Intervention:
        """
        Generate intervention suggestion
        
        Args:
            trigger: Intervention trigger
        
        Returns:
            Intervention object
        """
        # Generate suggested response based on trigger
        responses = {
            InterventionTrigger.CONFUSION: "Låt mig förtydliga. Vi diskuterade just nu...",
            InterventionTrigger.STUCK: "Vi verkar ha fastnat. Låt mig sammanfatta vad vi har kommit fram till hittills.",
            InterventionTrigger.MISUNDERSTANDING: "Jag vill säkerställa att vi förstår varandra korrekt.",
            InterventionTrigger.REQUEST: "Hur kan jag hjälpa till?"
        }
        
        suggested_response = responses.get(trigger, "Hur kan jag hjälpa?")
        
        intervention = Intervention(
            intervention_id=f"int_{datetime.now(timezone.utc).timestamp()}",
            trigger=trigger,
            suggested_response=suggested_response,
            confidence=0.8,
            timestamp=datetime.now(timezone.utc)
        )
        
        self.interventions.append(intervention)
        return intervention
    
    def approve_intervention(self, intervention_id: str) -> bool:
        """
        Approve intervention (send response)
        
        Args:
            intervention_id: Intervention identifier
        
        Returns:
            True if approved successfully
        """
        for intervention in self.interventions:
            if intervention.intervention_id == intervention_id:
                intervention.approved = True
                logger.info(f"Intervention {intervention_id} approved")
                return True
        return False
    
    def veto_intervention(self, intervention_id: str) -> bool:
        """
        Veto intervention (cancel response)
        
        Args:
            intervention_id: Intervention identifier
        
        Returns:
            True if vetoed successfully
        """
        for intervention in self.interventions:
            if intervention.intervention_id == intervention_id:
                intervention.vetoed = True
                logger.info(f"Intervention {intervention_id} vetoed")
                return True
        return False
    
    def generate_summary(self) -> Dict[str, Any]:
        """
        Generate meeting summary
        
        Returns:
            Summary dictionary
        """
        if not self.current_meeting:
            return {}
        
        # Extract key points from transcript
        transcript_text = " ".join([m["text"] for m in self.current_meeting.transcript])
        
        # Simple keyword extraction (in production, use LLM)
        keywords = ["beslut", "åtgärd", "diskuterade", "kommer", "ska"]
        key_points = [sentence for sentence in transcript_text.split(". ") 
                    if any(keyword in sentence.lower() for keyword in keywords)]
        
        summary = {
            "meeting_id": self.current_meeting.meeting_id,
            "duration": (datetime.now(timezone.utc) - self.current_meeting.start_time).total_seconds() / 60,
            "participant_count": len(self.current_meeting.participants),
            "message_count": len(self.current_meeting.transcript),
            "intervention_count": len(self.interventions),
            "key_points": key_points[:5],  # Top 5 key points
            "action_items": self.current_meeting.action_items,
            "decisions": self.current_meeting.decisions
        }
        
        return summary
    
    async def send_slack_summary(self, summary: Dict[str, Any]):
        """
        Send meeting summary to Slack
        
        Args:
            summary: Meeting summary
        """
        if not self.config.enable_slack_integration or not self.config.slack_webhook_url:
            logger.warning("Slack integration not configured")
            return
        
        try:
            import aiohttp
            
            message = {
                "text": f"📝 Meeting Summary: {summary['meeting_id']}",
                "attachments": [
                    {
                        "color": "#36a64f",
                        "fields": [
                            {"title": "Duration", "value": f"{summary['duration']:.1f} min", "short": True},
                            {"title": "Participants", "value": str(summary['participant_count']), "short": True},
                            {"title": "Interventions", "value": str(summary['intervention_count']), "short": True},
                            {"title": "Key Points", "value": "\n".join(summary['key_points'][:3]), "short": False}
                        ]
                    }
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                await session.post(self.config.slack_webhook_url, json=message)
            
            logger.info(f"Slack summary sent for meeting {summary['meeting_id']}")
        except Exception as e:
            logger.error(f"Failed to send Slack summary: {e}")
    
    def end_meeting(self) -> Dict[str, Any]:
        """
        End meeting and generate final summary
        
        Returns:
            Meeting summary
        """
        summary = self.generate_summary()
        
        if self.config.enable_auto_summary:
            logger.info(f"Meeting ended: {summary}")
        
        # Store meeting context (in production, save to database)
        self.deactivate()
        
        return summary


# Singleton instance
ghostwriter: Optional[Ghostwriter] = None


def initialize_ghostwriter(config: GhostwriterConfig = None) -> Ghostwriter:
    """Initialize Ghostwriter singleton"""
    global ghostwriter
    ghostwriter = Ghostwriter(config)
    return ghostwriter
