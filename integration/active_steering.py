#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Active Steering
Allows the operator to steer the agent mid-sentence via dashboard hotkeys.
"Knuff i rätt riktning" - course correction without full interruption.
"""

import sys
import asyncio
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timezone
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class SteeringCommand(Enum):
    """Commands the operator can send to steer the agent"""
    STOP_TALKING = "stop_talking"            # Immediately stop and listen
    CHANGE_TOPIC = "change_topic"            # Wrap up current point, shift topic
    BE_MORE_SPECIFIC = "be_more_specific"    # Add more detail/numbers
    BE_MORE_VAGUE = "be_more_vague"          # Stop giving specifics, stay high-level
    AGREE = "agree"                          # Agree with what was just said
    DISAGREE = "disagree"                    # Push back gently
    DEFER = "defer"                          # "Jag återkommer på det"
    SPEED_UP = "speed_up"                    # Talk faster, less filler
    SLOW_DOWN = "slow_down"                  # Slow down, be more deliberate
    INJECT_TEXT = "inject_text"              # Inject specific text to say next


class SteeringEvent(BaseModel):
    """A steering event from the operator"""
    command: SteeringCommand
    payload: Optional[str] = Field(None, description="Optional text payload for INJECT_TEXT or context")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    priority: int = Field(default=1, description="Priority (1=normal, 2=high, 3=urgent)")


class ActiveSteeringConfig(BaseModel):
    """Configuration for Active Steering"""
    enabled: bool = Field(default=True, description="Enable Active Steering")
    max_queue_size: int = Field(default=5, description="Max pending steering commands")
    inject_delay_ms: int = Field(default=200, description="Delay before injecting new direction")
    enable_hotkeys: bool = Field(default=True, description="Enable keyboard hotkeys")
    
    # Hotkey mappings (keyboard module key names)
    hotkey_stop: str = Field(default="F9", description="Stop talking")
    hotkey_agree: str = Field(default="ctrl+1", description="Agree")
    hotkey_disagree: str = Field(default="ctrl+2", description="Disagree")
    hotkey_defer: str = Field(default="ctrl+3", description="Defer")
    hotkey_specific: str = Field(default="ctrl+4", description="Be more specific")
    hotkey_vague: str = Field(default="ctrl+5", description="Be more vague")
    hotkey_change_topic: str = Field(default="ctrl+6", description="Change topic")


# Transition phrases for each steering command
STEERING_TRANSITIONS = {
    SteeringCommand.STOP_TALKING: [
        "",  # Just stop
    ],
    SteeringCommand.CHANGE_TOPIC: [
        "Men det var inte det jag ville komma till. ",
        "Nåväl, låt oss prata om något annat. ",
        "Vi lägger det åt sidan. ",
    ],
    SteeringCommand.BE_MORE_SPECIFIC: [
        "Mer specifikt, ",
        "Om vi tittar på siffrorna, ",
        "Låt mig vara mer konkret: ",
    ],
    SteeringCommand.BE_MORE_VAGUE: [
        "Generellt sett, ",
        "I stora drag, ",
        "Utan att gå in på detaljerna, ",
    ],
    SteeringCommand.AGREE: [
        "Ja, jag håller helt med. ",
        "Precis, det stämmer. ",
        "Absolut, det är en bra poäng. ",
    ],
    SteeringCommand.DISAGREE: [
        "Jag förstår vad du menar, men jag ser det lite annorlunda. ",
        "Det är en intressant vinkel, men vi bör överväga att ",
        "Jag hör dig, men baserat på vad jag vet, ",
    ],
    SteeringCommand.DEFER: [
        "Det är en viktig fråga som jag behöver kolla upp. Låt mig återkomma. ",
        "Jag vill inte ge dig fel information, så jag tar reda på det och skickar det skriftligt. ",
        "Bra fråga. Jag gräver i det efter mötet och återkommer. ",
    ],
    SteeringCommand.SPEED_UP: [],   # No transition, just adjusts pacing
    SteeringCommand.SLOW_DOWN: [],  # No transition, just adjusts pacing
    SteeringCommand.INJECT_TEXT: [], # Uses payload directly
}


class ActiveSteering:
    """
    Active Steering Controller
    Allows the real operator to nudge the AI agent mid-conversation
    via hotkeys or dashboard buttons.
    """
    
    def __init__(
        self,
        config: ActiveSteeringConfig,
        on_steering: Optional[Callable] = None,
        on_inject: Optional[Callable] = None
    ):
        """
        Initialize Active Steering
        
        Args:
            config: Steering configuration
            on_steering: Callback when steering command is processed
            on_inject: Callback to inject text into TTS pipeline
        """
        self.config = config
        self.on_steering = on_steering
        self.on_inject = on_inject
        
        # Command queue
        self.command_queue: asyncio.Queue = asyncio.Queue(maxsize=config.max_queue_size)
        
        # State
        self.is_active = False
        self.current_pacing: float = 1.0  # 1.0 = normal, <1 = faster, >1 = slower
        self.last_command: Optional[SteeringEvent] = None
        self.total_steers = 0
        
        # Register hotkeys
        if config.enable_hotkeys:
            self._register_hotkeys()
        
        logger.info("Active Steering initialized")
    
    def _register_hotkeys(self):
        """Register keyboard hotkeys for steering"""
        try:
            import keyboard
            
            keyboard.add_hotkey(self.config.hotkey_stop, 
                              lambda: self._queue_command(SteeringCommand.STOP_TALKING, priority=3))
            keyboard.add_hotkey(self.config.hotkey_agree, 
                              lambda: self._queue_command(SteeringCommand.AGREE))
            keyboard.add_hotkey(self.config.hotkey_disagree, 
                              lambda: self._queue_command(SteeringCommand.DISAGREE))
            keyboard.add_hotkey(self.config.hotkey_defer, 
                              lambda: self._queue_command(SteeringCommand.DEFER))
            keyboard.add_hotkey(self.config.hotkey_specific, 
                              lambda: self._queue_command(SteeringCommand.BE_MORE_SPECIFIC))
            keyboard.add_hotkey(self.config.hotkey_vague, 
                              lambda: self._queue_command(SteeringCommand.BE_MORE_VAGUE))
            keyboard.add_hotkey(self.config.hotkey_change_topic, 
                              lambda: self._queue_command(SteeringCommand.CHANGE_TOPIC))
            
            logger.info(f"Steering hotkeys registered: Stop={self.config.hotkey_stop}")
            
        except ImportError:
            logger.warning("keyboard module not available - hotkeys disabled")
        except Exception as e:
            logger.error(f"Failed to register hotkeys: {e}")
    
    def _queue_command(self, command: SteeringCommand, payload: str = None, priority: int = 1):
        """Queue a steering command (thread-safe)"""
        event = SteeringEvent(command=command, payload=payload, priority=priority)
        
        try:
            # For urgent commands, clear queue first
            if priority >= 3:
                while not self.command_queue.empty():
                    try:
                        self.command_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
            
            self.command_queue.put_nowait(event)
            logger.info(f"Steering command queued: {command.value} (priority={priority})")
            
        except asyncio.QueueFull:
            logger.warning(f"Steering queue full, dropping: {command.value}")
    
    def send_command(self, command: SteeringCommand, payload: str = None, priority: int = 1):
        """
        Send a steering command (from dashboard/API)
        
        Args:
            command: Steering command
            payload: Optional text payload
            priority: Command priority (1-3)
        """
        self._queue_command(command, payload, priority)
    
    def inject_text(self, text: str, priority: int = 2):
        """
        Inject specific text for the agent to say
        
        Args:
            text: Text to inject
            priority: Injection priority
        """
        self._queue_command(SteeringCommand.INJECT_TEXT, payload=text, priority=priority)
    
    async def process_next(self) -> Optional[Dict[str, Any]]:
        """
        Process next steering command from queue
        
        Returns:
            Steering action dict or None
        """
        if self.command_queue.empty():
            return None
        
        try:
            event = self.command_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None
        
        self.last_command = event
        self.total_steers += 1
        
        # Build action
        action = {
            "command": event.command.value,
            "timestamp": event.timestamp,
            "priority": event.priority,
        }
        
        if event.command == SteeringCommand.INJECT_TEXT:
            action["text"] = event.payload or ""
            action["transition"] = ""
        elif event.command == SteeringCommand.SPEED_UP:
            self.current_pacing = max(0.5, self.current_pacing - 0.2)
            action["pacing"] = self.current_pacing
        elif event.command == SteeringCommand.SLOW_DOWN:
            self.current_pacing = min(2.0, self.current_pacing + 0.2)
            action["pacing"] = self.current_pacing
        else:
            # Get transition phrase
            import random
            transitions = STEERING_TRANSITIONS.get(event.command, [])
            action["transition"] = random.choice(transitions) if transitions else ""
        
        # Trigger callback
        if self.on_steering:
            self.on_steering(action)
        
        # If there's text to inject, trigger injection callback
        if event.command == SteeringCommand.INJECT_TEXT and self.on_inject and event.payload:
            await asyncio.sleep(self.config.inject_delay_ms / 1000)
            self.on_inject(event.payload)
        
        logger.info(f"Steering processed: {event.command.value}")
        
        return action
    
    def has_pending_commands(self) -> bool:
        """Check if there are pending steering commands"""
        return not self.command_queue.empty()
    
    def get_pacing(self) -> float:
        """Get current pacing multiplier"""
        return self.current_pacing
    
    def reset_pacing(self):
        """Reset pacing to normal"""
        self.current_pacing = 1.0
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get steering status
        
        Returns:
            Status dictionary
        """
        return {
            "enabled": self.config.enabled,
            "hotkeys_enabled": self.config.enable_hotkeys,
            "pending_commands": self.command_queue.qsize(),
            "current_pacing": self.current_pacing,
            "total_steers": self.total_steers,
            "last_command": self.last_command.command.value if self.last_command else None,
            "hotkeys": {
                "stop": self.config.hotkey_stop,
                "agree": self.config.hotkey_agree,
                "disagree": self.config.hotkey_disagree,
                "defer": self.config.hotkey_defer,
                "specific": self.config.hotkey_specific,
                "vague": self.config.hotkey_vague,
                "change_topic": self.config.hotkey_change_topic
            }
        }


async def main():
    """Test Active Steering"""
    from loguru import logger
    
    logger.add("logs/active_steering_{time}.log", rotation="10 MB")
    
    def on_steering(action):
        logger.info(f"Steering: {action['command']} → '{action.get('transition', '')}'")
    
    def on_inject(text):
        logger.info(f"Injecting: '{text}'")
    
    # Create steering (hotkeys disabled for test)
    config = ActiveSteeringConfig(enable_hotkeys=False)
    steering = ActiveSteering(config, on_steering=on_steering, on_inject=on_inject)
    
    # Test commands
    steering.send_command(SteeringCommand.AGREE)
    steering.send_command(SteeringCommand.BE_MORE_SPECIFIC)
    steering.send_command(SteeringCommand.DEFER)
    steering.inject_text("Vi har faktiskt 15% rabatt den här månaden.")
    
    # Process all
    while steering.has_pending_commands():
        action = await steering.process_next()
        if action:
            logger.info(f"Processed: {action}")
    
    # Test pacing
    steering.send_command(SteeringCommand.SPEED_UP)
    await steering.process_next()
    logger.info(f"Pacing after speed up: {steering.get_pacing()}")
    
    steering.send_command(SteeringCommand.SLOW_DOWN)
    steering.send_command(SteeringCommand.SLOW_DOWN)
    await steering.process_next()
    await steering.process_next()
    logger.info(f"Pacing after 2x slow down: {steering.get_pacing()}")
    
    # Status
    status = steering.get_status()
    logger.info(f"Steering status: {status}")
    
    logger.info("Active Steering test complete")


if __name__ == "__main__":
    asyncio.run(main())
