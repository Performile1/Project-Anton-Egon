#!/usr/bin/env python3
"""
Project Anton Egon - Meeting Behavior Engine
Phase 23: Human Fallibility Engine
Simulates human behaviors at meeting start to break the "perfect AI" pattern
"""

import random
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass
from loguru import logger


class JoinScenario(Enum):
    """Meeting join scenarios"""
    LATE_JOINER = "late_joiner"  # Join 5 min late with apology
    MUTE_GLITCHER = "mute_glitcher"  # Join early, simulates talking without audio
    PHONE_CALLER = "phone_caller"  # Join early with phone call clip


@dataclass
class MeetingBehaviorConfig:
    """Configuration for meeting behavior engine"""
    enabled: bool = True
    late_joiner_probability: float = 0.33  # 33% chance
    mute_glitcher_probability: float = 0.33  # 33% chance
    phone_caller_probability: float = 0.34  # 34% chance
    late_joiner_delay_minutes: int = 5  # Join 5 min late
    early_join_minutes: int = 3  # Join 3 min early
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "late_joiner_probability": self.late_joiner_probability,
            "mute_glitcher_probability": self.mute_glitcher_probability,
            "phone_caller_probability": self.phone_caller_probability,
            "late_joiner_delay_minutes": self.late_joiner_delay_minutes,
            "early_join_minutes": self.early_join_minutes
        }


class MeetingBehaviorEngine:
    """
    Human Fallibility Engine
    Simulates human behaviors at meeting start
    """
    
    def __init__(self, config: Optional[MeetingBehaviorConfig] = None):
        """Initialize meeting behavior engine"""
        self.config = config or MeetingBehaviorConfig()
        self.current_scenario: Optional[JoinScenario] = None
        self.is_active: bool = False
        
        # Phrase library for apologies
        self.apology_phrases = [
            "Sjukt ledsen hörni, mötet innan drog över tiden. Nu kör vi!",
            "Ledsen för dröjsmålet, tekniken strulade lite här hemma. Kanon att vara på plats.",
            "Ursäkta, jag satt fast i en annan tråd. Var är vi i agendan?",
            "Förlåt att jag är sen, hade ett brådskande samtal. Vad har jag missat?",
            "Sorry allihop, klockan här hemma gick lite fel. Vi kör!",
            "Ledsen, jag var tvungen att ta ett kort samtal. Hänger på nu."
        ]
        
        logger.info("Meeting Behavior Engine initialized")
    
    def roll_join_dice(self) -> JoinScenario:
        """
        Roll the Join-Dice to select scenario
        
        Returns:
            Selected JoinScenario based on probabilities
        """
        if not self.config.enabled:
            return JoinScenario.LATE_JOINER  # Default to normal behavior
        
        # Roll dice (1-6)
        dice_roll = random.randint(1, 6)
        
        if dice_roll <= 2:
            # 1-2: Late Joiner
            logger.info(f"Join-Dice rolled {dice_roll}: Late Joiner scenario")
            return JoinScenario.LATE_JOINER
        elif dice_roll <= 4:
            # 3-4: Mute Glitcher
            logger.info(f"Join-Dice rolled {dice_roll}: Mute Glitcher scenario")
            return JoinScenario.MUTE_GLITCHER
        else:
            # 5-6: Phone Caller
            logger.info(f"Join-Dice rolled {dice_roll}: Phone Caller scenario")
            return JoinScenario.PHONE_CALLER
    
    def get_join_delay(self, scenario: JoinScenario) -> timedelta:
        """
        Get join delay for scenario
        
        Args:
            scenario: Selected join scenario
        
        Returns:
            Timedelta for join delay (positive = late, negative = early)
        """
        if scenario == JoinScenario.LATE_JOINER:
            return timedelta(minutes=self.config.late_joiner_delay_minutes)
        elif scenario in [JoinScenario.MUTE_GLITCHER, JoinScenario.PHONE_CALLER]:
            return timedelta(minutes=-self.config.early_join_minutes)
        else:
            return timedelta(0)
    
    def get_apology_phrase(self) -> str:
        """
        Get random apology phrase for late joiner
        
        Returns:
            Apology phrase
        """
        return random.choice(self.apology_phrases)
    
    def get_scenario_description(self, scenario: JoinScenario) -> str:
        """
        Get human-readable description of scenario
        
        Args:
            scenario: Join scenario
        
        Returns:
            Description string
        """
        descriptions = {
            JoinScenario.LATE_JOINER: "The Busy Executive - Join 5 min late with apology",
            JoinScenario.MUTE_GLITCHER: "The Mute-Glitcher - Join early, simulate talking without audio",
            JoinScenario.PHONE_CALLER: "The Multitasker - Join early with phone call clip"
        }
        return descriptions.get(scenario, "Unknown scenario")
    
    def calculate_join_time(self, meeting_start: datetime) -> datetime:
        """
        Calculate actual join time based on scenario
        
        Args:
            meeting_start: Scheduled meeting start time
        
        Returns:
            Actual join time
        """
        scenario = self.roll_join_dice()
        self.current_scenario = scenario
        
        delay = self.get_join_delay(scenario)
        join_time = meeting_start + delay
        
        logger.info(f"Meeting start: {meeting_start}, Join time: {join_time}, Scenario: {scenario.value}")
        
        return join_time
    
    async def execute_scenario(self, scenario: JoinScenario, orchestrator=None):
        """
        Execute the selected scenario
        
        Args:
            scenario: Join scenario to execute
            orchestrator: Orchestrator instance for executing actions
        """
        self.is_active = True
        self.current_scenario = scenario
        
        try:
            if scenario == JoinScenario.LATE_JOINER:
                await self._execute_late_joiner(orchestrator)
            elif scenario == JoinScenario.MUTE_GLITCHER:
                await self._execute_mute_glitcher(orchestrator)
            elif scenario == JoinScenario.PHONE_CALLER:
                await self._execute_phone_caller(orchestrator)
        except Exception as e:
            logger.error(f"Error executing scenario {scenario.value}: {e}")
        finally:
            self.is_active = False
    
    async def _execute_late_joiner(self, orchestrator=None):
        """Execute Late Joiner scenario"""
        logger.info("Executing Late Joiner scenario")
        
        # Wait for delay
        await asyncio.sleep(self.config.late_joiner_delay_minutes * 60)
        
        # Join meeting with apology
        apology = self.get_apology_phrase()
        
        if orchestrator:
            # Send apology via orchestrator
            await orchestrator.send_message(apology)
        
        logger.info(f"Late joiner executed with apology: {apology}")
    
    async def _execute_mute_glitcher(self, orchestrator=None):
        """Execute Mute Glitcher scenario"""
        logger.info("Executing Mute Glitcher scenario")
        
        # Join early
        await asyncio.sleep(self.config.early_join_minutes * 60)
        
        # Set status to "Talking" but no audio
        if orchestrator:
            await orchestrator.set_status("Talking")
            # Disable audio output
            await orchestrator.set_audio_enabled(False)
        
        # Wait for someone to notice
        logger.info("Mute Glitcher: Waiting for 'Anton, you're on mute' trigger")
        
        # This would be triggered by speech recognition in production
        # For now, we'll wait for a manual trigger or timeout
        await asyncio.sleep(60)  # Wait 1 minute
        
        # Apologize and enable audio
        apology = "Sorry, I was on mute. What did I miss?"
        
        if orchestrator:
            await orchestrator.send_message(apology)
            await orchestrator.set_audio_enabled(True)
        
        logger.info("Mute Glitcher executed")
    
    async def _execute_phone_caller(self, orchestrator=None):
        """Execute Phone Caller scenario"""
        logger.info("Executing Phone Caller scenario")
        
        # Join early
        await asyncio.sleep(self.config.early_join_minutes * 60)
        
        # Start phone call clip
        if orchestrator:
            # Play pre-recorded phone call video/audio
            await orchestrator.play_asset("phone_call_clip")
        
        # Wait until meeting start
        await asyncio.sleep(self.config.early_join_minutes * 60)
        
        # Stop phone call and join meeting
        greeting = "Hoppsan, hej allihop, märkte inte att jag kommit in än!"
        
        if orchestrator:
            await orchestrator.stop_asset()
            await orchestrator.send_message(greeting)
        
        logger.info("Phone Caller executed")
    
    def update_config(self, **kwargs):
        """
        Update configuration
        
        Args:
            **kwargs: Configuration parameters to update
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"Updated config: {key} = {value}")
    
    def get_config(self) -> MeetingBehaviorConfig:
        """Get current configuration"""
        return self.config
    
    def reset(self):
        """Reset engine state"""
        self.current_scenario = None
        self.is_active = False
        logger.info("Meeting Behavior Engine reset")


# Singleton instance
meeting_behavior_engine = MeetingBehaviorEngine()
