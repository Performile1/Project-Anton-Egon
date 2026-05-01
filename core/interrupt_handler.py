#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Phase 7: Interruption Handler
Detects when someone interrupts the agent and handles graceful stop/listen transitions
"""

import sys
import asyncio
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timezone
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class InterruptState(Enum):
    """Agent interrupt states"""
    SPEAKING = "speaking"           # Agent is actively speaking
    LISTENING = "listening"         # Agent is listening
    INTERRUPTED = "interrupted"     # Agent was interrupted mid-speech
    YIELDING = "yielding"          # Agent is stopping speech and transitioning to listen


class InterruptAction(Enum):
    """Actions to take on interrupt"""
    MUTE_AUDIO = "mute_audio"              # Stop TTS playback immediately
    SWITCH_TO_LISTEN_CLIP = "switch_clip"   # Switch to "listening" video clip
    PAUSE_AND_RESUME = "pause_resume"       # Pause, let them speak, then resume
    FULL_STOP = "full_stop"                 # Stop completely, wait for new input


class InterruptHandlerConfig(BaseModel):
    """Configuration for Interrupt Handler"""
    silence_threshold_ms: int = Field(default=300, description="Silence duration (ms) before considering speech ended")
    interrupt_sensitivity: float = Field(default=0.5, description="Sensitivity to interruptions (0-1)")
    min_speech_overlap_ms: int = Field(default=200, description="Min overlap (ms) to count as interruption")
    resume_delay_ms: int = Field(default=500, description="Delay (ms) before resuming after interruption")
    enable_graceful_yield: bool = Field(default=True, description="Enable graceful yielding on interrupt")


class InterruptHandler:
    """
    Interruption Handler
    Detects when someone talks over the agent and manages graceful transitions
    """
    
    def __init__(
        self,
        config: InterruptHandlerConfig,
        on_interrupt: Optional[Callable] = None,
        on_resume: Optional[Callable] = None
    ):
        """
        Initialize Interrupt Handler
        
        Args:
            config: Interrupt Handler configuration
            on_interrupt: Callback when interrupt is detected
            on_resume: Callback when agent can resume
        """
        self.config = config
        self.on_interrupt = on_interrupt
        self.on_resume = on_resume
        
        # State
        self.current_state = InterruptState.LISTENING
        self.agent_is_speaking = False
        self.incoming_speech_detected = False
        self.last_interrupt_time: Optional[datetime] = None
        self.interrupt_count = 0
        
        # Speech tracking
        self.agent_speech_start: Optional[datetime] = None
        self.incoming_speech_start: Optional[datetime] = None
        self.speech_buffer_text: str = ""
        
        logger.info("Interrupt Handler initialized")
    
    def set_agent_speaking(self, is_speaking: bool, speech_text: Optional[str] = None):
        """
        Update agent speaking state
        
        Args:
            is_speaking: True if agent is currently speaking
            speech_text: What the agent is saying (for resume context)
        """
        self.agent_is_speaking = is_speaking
        
        if is_speaking:
            self.current_state = InterruptState.SPEAKING
            self.agent_speech_start = datetime.now(timezone.utc)
            if speech_text:
                self.speech_buffer_text = speech_text
        else:
            if self.current_state != InterruptState.INTERRUPTED:
                self.current_state = InterruptState.LISTENING
            self.agent_speech_start = None
    
    def detect_incoming_speech(self, audio_energy: float, is_speech: bool):
        """
        Process incoming audio to detect if someone is talking over the agent
        
        Args:
            audio_energy: Audio energy level (0-1)
            is_speech: True if VAD detects speech
        """
        if not is_speech:
            self.incoming_speech_detected = False
            self.incoming_speech_start = None
            return
        
        # Speech detected
        if not self.incoming_speech_detected:
            self.incoming_speech_detected = True
            self.incoming_speech_start = datetime.now(timezone.utc)
        
        # Check if this is an interruption (agent is speaking AND someone else talks)
        if self.agent_is_speaking and self.incoming_speech_detected:
            # Calculate overlap duration
            if self.incoming_speech_start:
                overlap_ms = (datetime.now(timezone.utc) - self.incoming_speech_start).total_seconds() * 1000
                
                if overlap_ms >= self.config.min_speech_overlap_ms:
                    # Check if energy exceeds sensitivity threshold
                    if audio_energy >= self.config.interrupt_sensitivity:
                        self._handle_interrupt()
    
    def _handle_interrupt(self):
        """Handle detected interruption"""
        if self.current_state == InterruptState.INTERRUPTED:
            return  # Already handling an interrupt
        
        self.current_state = InterruptState.INTERRUPTED
        self.last_interrupt_time = datetime.now(timezone.utc)
        self.interrupt_count += 1
        
        logger.info(f"Interrupt detected! (count: {self.interrupt_count})")
        
        # Determine action
        if self.config.enable_graceful_yield:
            action = InterruptAction.SWITCH_TO_LISTEN_CLIP
        else:
            action = InterruptAction.MUTE_AUDIO
        
        # Build interrupt event
        event_data = {
            "action": action.value,
            "interrupt_count": self.interrupt_count,
            "agent_was_saying": self.speech_buffer_text[:100] if self.speech_buffer_text else "",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Trigger callback
        if self.on_interrupt:
            self.on_interrupt(event_data)
    
    async def wait_for_silence_then_resume(self):
        """
        Wait for the interrupter to finish speaking, then signal resume
        """
        if self.current_state != InterruptState.INTERRUPTED:
            return
        
        self.current_state = InterruptState.YIELDING
        
        # Wait for silence
        silence_start = None
        
        while self.current_state == InterruptState.YIELDING:
            if not self.incoming_speech_detected:
                if silence_start is None:
                    silence_start = datetime.now(timezone.utc)
                
                silence_duration_ms = (datetime.now(timezone.utc) - silence_start).total_seconds() * 1000
                
                if silence_duration_ms >= self.config.silence_threshold_ms:
                    # Silence long enough, ready to resume
                    break
            else:
                silence_start = None  # Reset silence timer
            
            await asyncio.sleep(0.05)  # Check every 50ms
        
        # Add resume delay
        await asyncio.sleep(self.config.resume_delay_ms / 1000)
        
        # Signal resume
        self.current_state = InterruptState.LISTENING
        
        resume_data = {
            "previous_speech": self.speech_buffer_text[:100] if self.speech_buffer_text else "",
            "interrupt_count": self.interrupt_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if self.on_resume:
            self.on_resume(resume_data)
        
        logger.info("Interrupt resolved, ready to resume")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get handler status
        
        Returns:
            Status dictionary
        """
        return {
            "current_state": self.current_state.value,
            "agent_is_speaking": self.agent_is_speaking,
            "incoming_speech": self.incoming_speech_detected,
            "interrupt_count": self.interrupt_count,
            "last_interrupt": self.last_interrupt_time.isoformat() if self.last_interrupt_time else None
        }


def main():
    """Test the Interrupt Handler"""
    from loguru import logger
    
    logger.add("logs/interrupt_handler_{time}.log", rotation="10 MB")
    
    def on_interrupt(event_data):
        logger.info(f"🔇 INTERRUPT: {event_data}")
    
    def on_resume(resume_data):
        logger.info(f"🔊 RESUME: {resume_data}")
    
    # Create handler
    config = InterruptHandlerConfig()
    handler = InterruptHandler(config, on_interrupt=on_interrupt, on_resume=on_resume)
    
    # Simulate: Agent starts speaking
    handler.set_agent_speaking(True, "Vi kan erbjuda 15% rabatt...")
    logger.info(f"State: {handler.current_state.value}")
    
    # Simulate: Someone starts talking (interruption)
    handler.detect_incoming_speech(audio_energy=0.7, is_speech=True)
    
    # Simulate continued overlap
    import time
    time.sleep(0.3)  # 300ms overlap
    handler.detect_incoming_speech(audio_energy=0.7, is_speech=True)
    
    logger.info(f"State after interrupt: {handler.current_state.value}")
    
    # Get status
    status = handler.get_status()
    logger.info(f"Handler status: {status}")
    
    logger.info("Interrupt Handler test complete")


if __name__ == "__main__":
    main()
