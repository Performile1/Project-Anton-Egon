#!/usr/bin/env python3
"""
Project Anton Egon - Phase 11: Facilitator Logic
Manages turn-taking, hand-raise queue, and engagement-based call-outs.
Integrates UI Detector, Engagement Analyzer, and The Whisperer for safe
social interventions with operator approval.
"""

import asyncio
import time
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timezone
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field


class FacilitatorMode(Enum):
    """How aggressive the facilitator should be"""
    SILENT = "silent"            # Only logs to Whisperer, never speaks
    WHISPER_ONLY = "whisper"     # Whispers to operator, waits for approval
    SEMI_AUTO = "semi_auto"      # Auto-handles hand queue, whispers for engagement
    FULL_AUTO = "full_auto"      # Handles everything autonomously (use with caution)


class CalloutStyle(Enum):
    """Style of engagement call-outs"""
    NOTETAKER = "notetaker"      # "Som er antecknare vill jag checka av..."
    FRIENDLY = "friendly"        # "Lasse, har du en fundering?"
    PLAYFUL = "playful"          # "Lasse, jag ser att du kämpar med energin..."
    FORMAL = "formal"            # "Innan vi går vidare, vill alla bekräfta?"


class QueueAction(BaseModel):
    """An action to take from the hand-raise queue"""
    participant_name: str
    action_type: str = "give_floor"  # give_floor, acknowledge, skip
    phrase: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EngagementAction(BaseModel):
    """An engagement-based action"""
    participant_name: str
    engagement_level: str
    suggested_phrase: str
    style: CalloutStyle = CalloutStyle.NOTETAKER
    approved: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FacilitatorConfig(BaseModel):
    """Configuration for Facilitator Logic"""
    mode: FacilitatorMode = Field(default=FacilitatorMode.WHISPER_ONLY, 
                                   description="Facilitator aggressiveness")
    callout_style: CalloutStyle = Field(default=CalloutStyle.NOTETAKER,
                                         description="Default call-out style")
    
    # Hand queue settings
    auto_acknowledge_hands: bool = Field(default=True, 
                                          description="Auto-acknowledge hand raises")
    hand_acknowledge_delay_seconds: float = Field(default=2.0,
                                                    description="Delay before acknowledging")
    max_queue_announce: int = Field(default=3, description="Max people to mention in queue")
    
    # Engagement settings
    engagement_check_interval: float = Field(default=30.0,
                                              description="Seconds between engagement checks")
    min_disengaged_seconds: float = Field(default=15.0,
                                           description="Min time disengaged before action")
    never_call_out_by_name_auto: bool = Field(default=True,
                                                description="Never auto-callout by name (safety)")
    
    # Phrases
    break_suggestion_threshold: int = Field(default=3,
                                             description="Disengaged participants before suggesting break")


# ─── Phrase Templates ────────────────────────────────────────────

HAND_QUEUE_PHRASES = {
    "single": [
        "Jag ser att {name} har en fråga.",
        "{name}, du ville säga något?",
        "Varsågod {name}, kör på.",
    ],
    "multiple": [
        "Jag ser att {names} har frågor. {first}, vill du börja?",
        "Vi har några frågor i kön. {first}, varsågod.",
    ],
    "acknowledge": [
        "Jag noterar att {name} vill säga något, vi kommer till dig strax.",
        "Tack {name}, jag har dig i kön.",
    ]
}

ENGAGEMENT_PHRASES = {
    CalloutStyle.NOTETAKER: {
        "general_check": "Som er antecknare vill jag bara checka av att alla är med på tåget innan vi går vidare till nästa punkt.",
        "individual_whisper": "{name} verkar ha tappat fokus. Vill du att jag checkar av?",
        "break_suggestion": "Vi har kört ett tag nu. Ska vi ta en kort bensträckare innan vi fortsätter?",
        "energy_low": "Jag märker att energin sjunker lite i rummet. Ska vi ta en kort paus?",
    },
    CalloutStyle.FRIENDLY: {
        "general_check": "Alla med? Ska vi köra vidare?",
        "individual_whisper": "{name} ser lite frånvarande ut. Ska jag fråga?",
        "break_suggestion": "Jag tror alla skulle må bra av en kort paus, vad säger ni?",
        "energy_low": "Lite tung stämning, ska vi lufta oss i 5 minuter?",
    },
    CalloutStyle.PLAYFUL: {
        "general_check": "Jag märker att ögonen börjar glida lite, ska vi byta ämne eller ta en paus?",
        "individual_whisper": "{name} ser ut att kämpa med energin. Busig callout?",
        "break_suggestion": "Okej, jag ser att kaffet börjar ta slut mentalt. Fem minuter?",
        "energy_low": "{name}, jag ser att du kämpar lite med energin där borta, ska vi ta en kort bensträckare eller har du en fundering kring {topic}?",
    },
    CalloutStyle.FORMAL: {
        "general_check": "Innan vi går vidare, vill jag säkerställa att alla parter har förstått och är eniga.",
        "individual_whisper": "{name} verkar inte engagerad. Formell check?",
        "break_suggestion": "Jag föreslår att vi tar en kort paus innan vi fortsätter med nästa agendapunkt.",
        "energy_low": "Vi har en hel del kvar att gå igenom. Kanske lämpligt med en kort paus?",
    }
}


class FacilitatorLogic:
    """
    Manages meeting facilitation: turn-taking, hand-raise queue,
    and engagement-based interventions.
    
    Safety principle: By default, NEVER auto-callout someone by name
    for disengagement. Always whisper to operator first.
    """
    
    def __init__(self, config: FacilitatorConfig,
                 on_speak: Optional[Callable] = None,
                 on_whisper: Optional[Callable] = None):
        """
        Initialize Facilitator.
        
        Args:
            config: Facilitator configuration
            on_speak: Callback when facilitator wants to speak (text) -> agent says it
            on_whisper: Callback when facilitator wants to whisper to operator
        """
        self.config = config
        self.on_speak = on_speak
        self.on_whisper = on_whisper
        
        # Hand-raise queue (managed by UI Detector, consumed here)
        self.hand_queue: List[str] = []
        self._queue_acknowledged: Dict[str, float] = {}  # name -> ack time
        
        # Engagement tracking
        self._engagement_states: Dict[str, Dict[str, Any]] = {}  # name -> latest state
        self._last_engagement_check: float = 0.0
        self._break_suggested_at: float = 0.0
        
        # Pending actions (awaiting operator approval)
        self.pending_actions: List[EngagementAction] = []
        
        # Current meeting topic (for contextual call-outs)
        self.current_topic: str = ""
        
        # Stats
        self.stats = {
            "hands_processed": 0,
            "engagement_alerts_sent": 0,
            "breaks_suggested": 0,
            "callouts_made": 0,
        }
        
        logger.info(f"Facilitator initialized (mode: {config.mode.value}, style: {config.callout_style.value})")
    
    # ─── Hand-Raise Queue ────────────────────────────────────────
    
    async def on_hand_raised(self, participant_name: str):
        """
        Called when UI Detector detects a hand raise.
        
        Args:
            participant_name: Who raised their hand
        """
        if participant_name in self.hand_queue:
            return  # Already in queue
        
        self.hand_queue.append(participant_name)
        logger.info(f"Hand raised: {participant_name} (queue: {self.hand_queue})")
        
        # Auto-acknowledge if configured
        if self.config.auto_acknowledge_hands and self.config.mode in [
            FacilitatorMode.SEMI_AUTO, FacilitatorMode.FULL_AUTO
        ]:
            await asyncio.sleep(self.config.hand_acknowledge_delay_seconds)
            await self._acknowledge_hand(participant_name)
        elif self.config.mode == FacilitatorMode.WHISPER_ONLY:
            await self._whisper(f"🖐️ {participant_name} räckte upp handen. Kö: {self.hand_queue}")
    
    async def give_floor_to_next(self) -> Optional[str]:
        """
        Give the floor to the next person in the hand-raise queue.
        
        Returns:
            Name of the person given the floor, or None
        """
        if not self.hand_queue:
            return None
        
        name = self.hand_queue.pop(0)
        self.stats["hands_processed"] += 1
        
        # Choose phrase
        if len(self.hand_queue) > 0:
            # More people waiting
            import random
            phrase = random.choice(HAND_QUEUE_PHRASES["single"])
            phrase = phrase.format(name=name)
            remaining = ", ".join(self.hand_queue[:self.config.max_queue_announce])
            phrase += f" (Sen har vi {remaining} i kön.)"
        else:
            import random
            phrase = random.choice(HAND_QUEUE_PHRASES["single"])
            phrase = phrase.format(name=name)
        
        await self._speak(phrase)
        logger.info(f"Floor given to: {name}")
        return name
    
    async def _acknowledge_hand(self, participant_name: str):
        """Acknowledge a hand raise without giving the floor yet"""
        import random
        phrase = random.choice(HAND_QUEUE_PHRASES["acknowledge"])
        phrase = phrase.format(name=participant_name)
        
        self._queue_acknowledged[participant_name] = time.time()
        await self._speak(phrase)
    
    def clear_hand(self, participant_name: str):
        """Remove someone from the hand queue"""
        if participant_name in self.hand_queue:
            self.hand_queue.remove(participant_name)
            logger.info(f"Hand cleared: {participant_name}")
    
    # ─── Engagement Monitoring ───────────────────────────────────
    
    async def update_engagement(self, participant_name: str, engagement_data: Dict[str, Any]):
        """
        Receive engagement update from Engagement Analyzer.
        
        Args:
            participant_name: Who the data is for
            engagement_data: {engagement, gaze_on_screen, blink_rate, etc.}
        """
        self._engagement_states[participant_name] = {
            **engagement_data,
            "updated_at": time.time()
        }
        
        now = time.time()
        
        # Periodic engagement check
        if now - self._last_engagement_check < self.config.engagement_check_interval:
            return
        
        self._last_engagement_check = now
        await self._check_engagement_levels()
    
    async def _check_engagement_levels(self):
        """Check all participants' engagement and decide on actions"""
        disengaged = []
        asleep = []
        
        for name, data in self._engagement_states.items():
            level = data.get("engagement", "active")
            if level == "asleep":
                asleep.append(name)
            elif level in ["drowsy", "distracted"]:
                disengaged.append(name)
        
        # Handle asleep participants (urgent)
        for name in asleep:
            await self._handle_asleep(name)
        
        # Handle generally low engagement
        total_disengaged = len(disengaged) + len(asleep)
        
        if total_disengaged >= self.config.break_suggestion_threshold:
            await self._suggest_break(total_disengaged)
        elif disengaged and self.config.mode != FacilitatorMode.SILENT:
            for name in disengaged:
                await self._handle_disengaged(name)
    
    async def _handle_asleep(self, participant_name: str):
        """Handle a participant who appears to be sleeping"""
        style_phrases = ENGAGEMENT_PHRASES.get(self.config.callout_style, 
                                                ENGAGEMENT_PHRASES[CalloutStyle.NOTETAKER])
        
        if self.config.mode == FacilitatorMode.FULL_AUTO and not self.config.never_call_out_by_name_auto:
            # Direct call-out (only if explicitly enabled)
            phrase = style_phrases.get("energy_low", "").format(
                name=participant_name, topic=self.current_topic or "agendan"
            )
            await self._speak(phrase)
            self.stats["callouts_made"] += 1
        else:
            # Whisper to operator (default safe behavior)
            whisper_msg = style_phrases.get("individual_whisper", "").format(name=participant_name)
            await self._whisper(f"😴 {whisper_msg}")
            
            # Create pending action for operator approval
            action = EngagementAction(
                participant_name=participant_name,
                engagement_level="asleep",
                suggested_phrase=style_phrases.get("energy_low", "").format(
                    name=participant_name, topic=self.current_topic or "agendan"
                ),
                style=self.config.callout_style
            )
            self.pending_actions.append(action)
        
        self.stats["engagement_alerts_sent"] += 1
    
    async def _handle_disengaged(self, participant_name: str):
        """Handle a disengaged participant"""
        style_phrases = ENGAGEMENT_PHRASES.get(self.config.callout_style,
                                                ENGAGEMENT_PHRASES[CalloutStyle.NOTETAKER])
        
        # Always whisper first (safety)
        whisper_msg = style_phrases.get("individual_whisper", "").format(name=participant_name)
        await self._whisper(f"👀 {whisper_msg}")
        self.stats["engagement_alerts_sent"] += 1
    
    async def _suggest_break(self, disengaged_count: int):
        """Suggest a break when multiple people are disengaged"""
        now = time.time()
        
        # Don't suggest breaks too frequently (min 10 minutes apart)
        if now - self._break_suggested_at < 600:
            return
        
        self._break_suggested_at = now
        style_phrases = ENGAGEMENT_PHRASES.get(self.config.callout_style,
                                                ENGAGEMENT_PHRASES[CalloutStyle.NOTETAKER])
        
        if self.config.mode in [FacilitatorMode.SEMI_AUTO, FacilitatorMode.FULL_AUTO]:
            phrase = style_phrases.get("break_suggestion", "Ska vi ta en paus?")
            await self._speak(phrase)
        else:
            phrase = style_phrases.get("break_suggestion", "")
            await self._whisper(f"☕ {disengaged_count} deltagare verkar oengagerade. Förslag: {phrase}")
        
        self.stats["breaks_suggested"] += 1
    
    # ─── Operator Approval ───────────────────────────────────────
    
    async def approve_action(self, action_index: int = 0) -> Optional[str]:
        """
        Approve a pending engagement action.
        
        Args:
            action_index: Index of the pending action to approve
            
        Returns:
            The phrase that was spoken, or None
        """
        if action_index >= len(self.pending_actions):
            return None
        
        action = self.pending_actions.pop(action_index)
        action.approved = True
        
        await self._speak(action.suggested_phrase)
        self.stats["callouts_made"] += 1
        logger.info(f"Approved callout for: {action.participant_name}")
        return action.suggested_phrase
    
    def reject_action(self, action_index: int = 0) -> bool:
        """Reject a pending action"""
        if action_index >= len(self.pending_actions):
            return False
        
        action = self.pending_actions.pop(action_index)
        logger.info(f"Rejected callout for: {action.participant_name}")
        return True
    
    def get_pending_actions(self) -> List[Dict[str, Any]]:
        """Get all pending actions awaiting approval"""
        return [
            {
                "index": i,
                "participant": a.participant_name,
                "level": a.engagement_level,
                "phrase": a.suggested_phrase,
                "style": a.style.value,
                "age_seconds": (datetime.now(timezone.utc) - a.timestamp).total_seconds()
            }
            for i, a in enumerate(self.pending_actions)
        ]
    
    # ─── General Check ───────────────────────────────────────────
    
    async def do_general_check(self):
        """
        Do a general engagement check without naming anyone.
        Safe for auto-mode: "Alla med? Ska vi köra vidare?"
        """
        style_phrases = ENGAGEMENT_PHRASES.get(self.config.callout_style,
                                                ENGAGEMENT_PHRASES[CalloutStyle.NOTETAKER])
        phrase = style_phrases.get("general_check", "Alla med?")
        await self._speak(phrase)
    
    # ─── Callbacks ───────────────────────────────────────────────
    
    async def _speak(self, text: str):
        """Send text to agent's speech pipeline"""
        if self.on_speak:
            try:
                if asyncio.iscoroutinefunction(self.on_speak):
                    await self.on_speak(text)
                else:
                    self.on_speak(text)
            except Exception as e:
                logger.error(f"Speak callback failed: {e}")
        logger.info(f"Facilitator speaks: {text}")
    
    async def _whisper(self, text: str):
        """Send whisper to operator dashboard"""
        if self.on_whisper:
            try:
                if asyncio.iscoroutinefunction(self.on_whisper):
                    await self.on_whisper(text)
                else:
                    self.on_whisper(text)
            except Exception as e:
                logger.error(f"Whisper callback failed: {e}")
        logger.debug(f"Facilitator whispers: {text}")
    
    # ─── Topic Tracking ──────────────────────────────────────────
    
    def set_topic(self, topic: str):
        """Set current meeting topic for contextual call-outs"""
        self.current_topic = topic
    
    # ─── Status ──────────────────────────────────────────────────
    
    def get_status(self) -> Dict[str, Any]:
        """Get facilitator status"""
        return {
            "mode": self.config.mode.value,
            "style": self.config.callout_style.value,
            "hand_queue": self.hand_queue,
            "pending_actions": len(self.pending_actions),
            "engagement_states": {
                name: data.get("engagement", "unknown")
                for name, data in self._engagement_states.items()
            },
            "current_topic": self.current_topic,
            "stats": self.stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test Facilitator Logic"""
    spoken = []
    whispered = []
    
    def on_speak(text):
        spoken.append(text)
        print(f"[SPEAK] {text}")
    
    def on_whisper(text):
        whispered.append(text)
        print(f"[WHISPER] {text}")
    
    config = FacilitatorConfig(mode=FacilitatorMode.WHISPER_ONLY)
    facilitator = FacilitatorLogic(config, on_speak=on_speak, on_whisper=on_whisper)
    
    # Test hand raises
    await facilitator.on_hand_raised("Sara")
    await facilitator.on_hand_raised("Lasse")
    
    print(f"\nHand queue: {facilitator.hand_queue}")
    
    # Give floor
    name = await facilitator.give_floor_to_next()
    print(f"Floor given to: {name}")
    
    # Test engagement alert
    await facilitator.update_engagement("Lasse", {"engagement": "asleep"})
    facilitator._last_engagement_check = 0  # Force check
    await facilitator._check_engagement_levels()
    
    print(f"\nPending actions: {facilitator.get_pending_actions()}")
    
    # Approve callout
    if facilitator.pending_actions:
        result = await facilitator.approve_action(0)
        print(f"Approved: {result}")
    
    print(f"\nStats: {facilitator.stats}")


if __name__ == "__main__":
    asyncio.run(main())
