#!/usr/bin/env python3
"""
Project Anton Egon - Phase 5: Panic Logic
Global hotkeys for emergency freeze and shutdown
Phase 17-19: Safety Valves - F9 Safe-Word, F10 Panic, Ctrl+1-6 Manual Commands
"""

import keyboard
import asyncio
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field


class PanicAction(Enum):
    """Panic actions"""
    FREEZE = "freeze"  # Phase 5: Freeze video
    SHUTDOWN = "shutdown"  # Phase 5: Emergency shutdown
    OFF_THE_RECORD = "off_the_record"  # Phase 5: Off-the-record mode
    SAFE_WORD = "safe_word"  # Phase 17: Silence voice only (video continues)
    PANIC_LOOP = "panic_loop"  # Phase 17: Static low-connection loop + AI shutdown
    MANUAL_COMMAND = "manual_command"  # Phase 17: Ctrl+1-6 for opinion control


class ManualCommand(Enum):
    """Manual commands for opinion control (Ctrl+1-6)"""
    AGREE = "agree"  # Ctrl+1: Force agreement
    DISAGREE = "disagree"  # Ctrl+2: Force disagreement
    NEUTRAL = "neutral"  # Ctrl+3: Force neutral stance
    DEFER = "defer"  # Ctrl+4: Defer to human
    CLARIFY = "clarify"  # Ctrl+5: Ask for clarification
    PAUSE = "pause"  # Ctrl+6: Pause and think


class PanicConfig(BaseModel):
    """Configuration for panic logic"""
    freeze_hotkey: str = Field(default="f9", description="Hotkey to freeze")
    shutdown_hotkey: str = Field(default="f10", description="Hotkey to shutdown")
    off_the_record_hotkey: str = Field(default="f12", description="Hotkey for off-the-record mode")
    # Phase 17-19: Updated behavior
    safe_word_hotkey: str = Field(default="f9", description="Hotkey to silence voice (Safe-Word)")
    panic_loop_hotkey: str = Field(default="f10", description="Hotkey for panic loop (static + AI shutdown)")
    manual_commands_hotkey: str = Field(default="ctrl", description="Modifier for manual commands (Ctrl+1-6)")
    enable_hotkeys: bool = Field(default=True, description="Enable hotkey monitoring")


class PanicLogic:
    """
    Panic logic for emergency controls
    Global hotkeys for freeze, shutdown, and off-the-record mode
    Phase 17-19: Safety Valves - F9 Safe-Word, F10 Panic, Ctrl+1-6 Manual Commands
    """
    
    def __init__(self, config: PanicConfig):
        """Initialize panic logic"""
        self.config = config
        
        # State
        self.is_frozen = False
        self.is_shutdown = False
        self.off_the_record = False
        # Phase 17-19: New states
        self.voice_silenced = False  # Safe-Word: voice silenced, video continues
        self.panic_loop_active = False  # Panic loop: static + AI shutdown
        self.last_manual_command: Optional[ManualCommand] = None
        
        # Callbacks
        self.on_freeze: Optional[Callable] = None
        self.on_shutdown: Optional[Callable] = None
        self.on_off_the_record: Optional[Callable] = None
        # Phase 17-19: New callbacks
        self.on_safe_word: Optional[Callable] = None
        self.on_panic_loop: Optional[Callable] = None
        self.on_manual_command: Optional[Callable] = None
        
        # Hotkey hooks
        self.hotkey_hooks = {}
        
        logger.info(f"Panic Logic initialized (safe-word: {config.safe_word_hotkey}, panic: {config.panic_loop_hotkey})")
    
    def _on_freeze_pressed(self):
        """Handle freeze hotkey"""
        self.is_frozen = not self.is_frozen
        status = "FROZEN" if self.is_frozen else "UNFROZEN"
        logger.warning(f"🚨 PANIC: Video {status} (F9 pressed)")
        
        if self.on_freeze:
            self.on_freeze(self.is_frozen)
    
    def _on_shutdown_pressed(self):
        """Handle shutdown hotkey"""
        self.is_shutdown = True
        logger.warning("🚨 PANIC: Emergency shutdown initiated (F10 pressed)")
        
        if self.on_shutdown:
            self.on_shutdown()
    
    def _on_off_the_record_pressed(self):
        """Handle off-the-record hotkey"""
        self.off_the_record = not self.off_the_record
        status = "ENABLED" if self.off_the_record else "DISABLED"
        logger.warning(f"🚨 PANIC: Off-the-record mode {status} (F12 pressed)")
        
        if self.on_off_the_record:
            self.on_off_the_record(self.off_the_record)
    
    # ═══════════════════════════════════════════════════════════════
    # PHASE 17-19: SAFETY VALVES
    # ═══════════════════════════════════════════════════════════════
    def _on_safe_word_pressed(self):
        """Handle Safe-Word hotkey (F9) - Silence voice only, video continues"""
        self.voice_silenced = not self.voice_silenced
        status = "SILENCED" if self.voice_silenced else "UNSILENCED"
        logger.warning(f"🛡️ SAFE-WORD: Voice {status} (F9 pressed) - Video continues")
        
        if self.on_safe_word:
            self.on_safe_word(self.voice_silenced)
    
    def _on_panic_loop_pressed(self):
        """Handle Panic Loop hotkey (F10) - Static low-connection loop + AI shutdown"""
        self.panic_loop_active = True
        self.is_shutdown = True  # Also trigger AI shutdown
        logger.warning(f"🚨 PANIC LOOP: Static low-connection loop + AI shutdown (F10 pressed)")
        
        if self.on_panic_loop:
            self.on_panic_loop()
        
        if self.on_shutdown:
            self.on_shutdown()
    
    def _on_manual_command_pressed(self, number: int):
        """Handle manual command hotkey (Ctrl+1-6)"""
        command_map = {
            1: ManualCommand.AGREE,
            2: ManualCommand.DISAGREE,
            3: ManualCommand.NEUTRAL,
            4: ManualCommand.DEFER,
            5: ManualCommand.CLARIFY,
            6: ManualCommand.PAUSE
        }
        
        command = command_map.get(number)
        if command:
            self.last_manual_command = command
            logger.warning(f"🎮 MANUAL COMMAND: {command.value} (Ctrl+{number} pressed)")
            
            if self.on_manual_command:
                self.on_manual_command(command)
    
    def register_callbacks(
        self,
        on_freeze: Optional[Callable] = None,
        on_shutdown: Optional[Callable] = None,
        on_off_the_record: Optional[Callable] = None,
        on_safe_word: Optional[Callable] = None,
        on_panic_loop: Optional[Callable] = None,
        on_manual_command: Optional[Callable] = None
    ):
        """
        Register callback functions
        
        Args:
            on_freeze: Callback when freeze is toggled
            on_shutdown: Callback when shutdown is triggered
            on_off_the_record: Callback when off-the-record is toggled
            on_safe_word: Callback when safe-word is triggered (Phase 17)
            on_panic_loop: Callback when panic loop is triggered (Phase 17)
            on_manual_command: Callback when manual command is triggered (Phase 17)
        """
        self.on_freeze = on_freeze
        self.on_shutdown = on_shutdown
        self.on_off_the_record = on_off_the_record
        self.on_safe_word = on_safe_word
        self.on_panic_loop = on_panic_loop
        self.on_manual_command = on_manual_command
    
    def trigger_panic(self, action: PanicAction, manual_command_num: Optional[int] = None):
        """
        Manually trigger a panic action
        
        Args:
            action: Panic action to trigger
            manual_command_num: Manual command number (1-6) for MANUAL_COMMAND action
        """
        if action == PanicAction.FREEZE:
            self._on_freeze_pressed()
        elif action == PanicAction.SHUTDOWN:
            self._on_shutdown_pressed()
        elif action == PanicAction.OFF_THE_RECORD:
            self._on_off_the_record_pressed()
        elif action == PanicAction.SAFE_WORD:
            self._on_safe_word_pressed()
        elif action == PanicAction.PANIC_LOOP:
            self._on_panic_loop_pressed()
        elif action == PanicAction.MANUAL_COMMAND and manual_command_num:
            self._on_manual_command_pressed(manual_command_num)
    
    def _register_hotkeys(self):
        """Register hotkeys"""
        try:
            # Phase 17-19: Register Safe-Word hotkey (F9)
            self.hotkey_hooks['safe_word'] = keyboard.add_hotkey(
                self.config.safe_word_hotkey,
                self._on_safe_word_pressed
            )
            logger.info(f"Registered safe-word hotkey: {self.config.safe_word_hotkey}")
            
            # Phase 17-19: Register Panic Loop hotkey (F10)
            self.hotkey_hooks['panic_loop'] = keyboard.add_hotkey(
                self.config.panic_loop_hotkey,
                self._on_panic_loop_pressed
            )
            logger.info(f"Registered panic loop hotkey: {self.config.panic_loop_hotkey}")
            
            # Phase 17-19: Register manual command hotkeys (Ctrl+1-6)
            for i in range(1, 7):
                hotkey = f"{self.config.manual_commands_hotkey}+{i}"
                self.hotkey_hooks[f'manual_{i}'] = keyboard.add_hotkey(
                    hotkey,
                    lambda n=i: self._on_manual_command_pressed(n)
                )
                logger.info(f"Registered manual command hotkey: {hotkey}")
            
            # Phase 5: Legacy hotkeys (for backward compatibility)
            self.hotkey_hooks['freeze'] = keyboard.add_hotkey(
                self.config.freeze_hotkey,
                self._on_freeze_pressed
            )
            logger.info(f"Registered freeze hotkey (legacy): {self.config.freeze_hotkey}")
            
            self.hotkey_hooks['shutdown'] = keyboard.add_hotkey(
                self.config.shutdown_hotkey,
                self._on_shutdown_pressed
            )
            logger.info(f"Registered shutdown hotkey (legacy): {self.config.shutdown_hotkey}")
            
            self.hotkey_hooks['off_the_record'] = keyboard.add_hotkey(
                self.config.off_the_record_hotkey,
                self._on_off_the_record_pressed
            )
            logger.info(f"Registered off-the-record hotkey: {self.config.off_the_record_hotkey}")
            
        except Exception as e:
            logger.error(f"Failed to register hotkeys: {e}")
    
    def _unregister_hotkeys(self):
        """Unregister hotkeys"""
        try:
            for hook_name, hook in self.hotkey_hooks.items():
                if hook:
                    keyboard.remove_hotkey(hook)
                    logger.info(f"Unregistered hotkey: {hook_name}")
            
            self.hotkey_hooks.clear()
            
        except Exception as e:
            logger.error(f"Failed to unregister hotkeys: {e}")
    
    async def start(self):
        """Start panic logic monitoring"""
        if self.config.enable_hotkeys:
            self._register_hotkeys()
            logger.info("Panic logic monitoring started")
        else:
            logger.info("Panic logic hotkeys disabled")
    
    async def stop(self):
        """Stop panic logic monitoring"""
        self._unregister_hotkeys()
        logger.info("Panic logic monitoring stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current panic logic status"""
        return {
            "is_frozen": self.is_frozen,
            "is_shutdown": self.is_shutdown,
            "off_the_record": self.off_the_record,
            # Phase 17-19: New states
            "voice_silenced": self.voice_silenced,
            "panic_loop_active": self.panic_loop_active,
            "last_manual_command": self.last_manual_command.value if self.last_manual_command else None,
            "safe_word_hotkey": self.config.safe_word_hotkey,
            "panic_loop_hotkey": self.config.panic_loop_hotkey,
            "manual_commands_hotkey": self.config.manual_commands_hotkey,
            # Legacy
            "freeze_hotkey": self.config.freeze_hotkey,
            "shutdown_hotkey": self.config.shutdown_hotkey,
            "off_the_record_hotkey": self.config.off_the_record_hotkey,
            "hotkeys_enabled": self.config.enable_hotkeys,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test the panic logic"""
    from loguru import logger
    
    logger.add("logs/panic_logic_{time}.log", rotation="10 MB")
    
    # Create panic logic
    config = PanicConfig()
    panic = PanicLogic(config)
    
    # Test callbacks
    def on_freeze(is_frozen):
        logger.info(f"Freeze callback: {is_frozen}")
    
    def on_shutdown():
        logger.info("Shutdown callback triggered")
    
    def on_off_the_record(enabled):
        logger.info(f"Off-the-record callback: {enabled}")
    
    panic.register_callbacks(on_freeze, on_shutdown, on_off_the_record)
    
    # Test status
    status = panic.get_status()
    logger.info(f"Panic Logic status: {status}")
    
    # Test manual trigger
    try:
        await panic.start()
        logger.info("Hotkeys registered. Press F9 to freeze, F10 to shutdown, F12 for off-the-record")
        logger.info("Testing manual trigger...")
        
        # Test manual freeze
        panic.trigger_panic(PanicAction.FREEZE)
        await asyncio.sleep(1)
        panic.trigger_panic(PanicAction.FREEZE)  # Unfreeze
        
        # Test off-the-record
        panic.trigger_panic(PanicAction.OFF_THE_RECORD)
        await asyncio.sleep(1)
        panic.trigger_panic(PanicAction.OFF_THE_RECORD)
        
        await asyncio.sleep(2)
        await panic.stop()
    except Exception as e:
        logger.error(f"Test error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
