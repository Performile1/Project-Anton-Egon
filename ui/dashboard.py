#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Phase 5: Dashboard UI
Graphical interface for monitoring agent status
"""

import sys
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import json

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class Platform(Enum):
    """Supported platforms"""
    TEAMS = "teams"
    MEET = "meet"
    ZOOM = "zoom"
    WHATSAPP = "whatsapp"
    DISCORD = "discord"


class DashboardConfig(BaseModel):
    """Configuration for dashboard"""
    refresh_interval: float = Field(default=1.0, description="Refresh interval in seconds")
    show_emotions: bool = Field(default=True, description="Show emotion monitor")
    show_transcription: bool = Field(default=True, description="Show real-time transcription")
    max_log_lines: int = Field(default=50, description="Maximum log lines to display")
    default_platform: str = Field(default="teams", description="Default platform")


class Dashboard:
    """
    Dashboard UI for monitoring agent status
    Real-time log, emotion monitor, and manual override controls
    """
    
    def __init__(self, config: DashboardConfig):
        """Initialize dashboard"""
        self.config = config
        
        # State
        self.running = False
        self.dashboard_task = None
        
        # Data
        self.status_data: Dict[str, Any] = {}
        self.logs = []
        self.emotions: Dict[str, str] = {}
        
        # Platform selector
        self.current_platform = Platform(config.default_platform)
        self.platform_callback: Optional[Callable] = None
        # Available platforms
        self.available_platforms = list(Platform)
        
        
        logger.info(f"Dashboard initialized (platform: {self.current_platform.value})")
    
    def update_status(self, status_data: Dict[str, Any]):
        """
        Update status data
        
        Args:
            status_data: Status data from orchestrator
        """
        self.status_data = status_data
        logger.debug(f"Status updated: {status_data.get('state', 'unknown')}")
    
    def add_log(self, log_entry: str, level: str = "INFO"):
        """
        Add log entry
        
        Args:
            log_entry: Log message
            level: Log level
        """
        self.logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": log_entry
        })
        
        # Keep only recent logs
        if len(self.logs) > self.config.max_log_lines:
            self.logs.pop(0)
    
    def update_emotions(self, emotions: Dict[str, str]):
        """
        Update emotion monitor
        
        Args:
            emotions: Dictionary of speaker -> emotion
        """
        self.emotions = emotions
    
    def get_available_platforms(self) -> list:
        """Get list of available platforms"""
        return [p.value for p in self.available_platforms]
    
    def get_agenda_display(self) -> str:
        """Get formatted agenda display"""
        if not self.daily_agenda:
            return "No meetings scheduled"
        
        display = []
        for item in self.daily_agenda:
            status_icon = "✅" if item["status"] == "agent_ready" else "🚗"
            type_display = item["type"].upper()
            outfit = f"Outfit: {item['outfit']}" if item['outfit'] != "N/A" else "Agent inactive"
            
            display.append(f"{status_icon} {item['time']} - {item['title']}: ({type_display} - {outfit})")
        
        return "\n".join(display)
    
    def get_emotion_display(self) -> str:
        """Get formatted emotion display"""
        if not self.emotions:
            return "No emotions detected"
        
        display = []
        for speaker, emotion in self.emotions.items():
            display.append(f"{speaker}: {emotion}")
        
        return "\n".join(display)
    
    def get_status_display(self) -> str:
        """Get formatted status display"""
        if not self.status_data:
            return "No status data"
        
        display = []
        display.append(f"Platform: {self.current_platform.value.upper()}")
        display.append(f"State: {self.status_data.get('state', 'unknown')}")
        display.append(f"Active Speaker: {self.status_data.get('active_speaker', 'N/A')}")
        display.append(f"Emotion: {self.status_data.get('emotion', 'N/A')}")
        display.append(f"Last Keyword: {self.status_data.get('last_keyword', 'N/A')}")
        display.append(f"Detected Names: {', '.join(self.status_data.get('names', []))}")
        
        return "\n".join(display)
    
    def get_log_display(self) -> str:
        """Get formatted log display"""
        if not self.logs:
            return "No logs"
        
        display = []
        for log in self.logs[-self.config.max_log_lines:]:
            display.append(f"[{log['timestamp']}] {log['level']}: {log['message']}")
        
        return "\n".join(display)
    
    async def _display_loop(self):
        """Main display loop"""
        logger.info("Starting dashboard display loop")
        
        while self.running:
            try:
                # Clear console (simple implementation)
                # In production, use a proper GUI library like Tkinter, PyQt, or web-based
                
                print("\n" + "="*80)
                print("ANTON EGON - DASHBOARD")
                print("="*80)
                
                # Status
                print("\n[STATUS]")
                print(self.get_status_display())
                
                # Emotions
                if self.config.show_emotions:
                    print("\n[EMOTIONS]")
                    print(self.get_emotion_display())
                
                # Logs
                if self.config.show_transcription:
                    print("\n[RECENT LOGS]")
                    print(self.get_log_display())
                
                # Controls
                print("\n[CONTROLS]")
                print("F9 - Freeze/Unfreeze")
                print("F10 - Emergency Shutdown")
                print("F12 - Off-the-record mode")
                
                print("\nPress Ctrl+C to stop dashboard")
                
                await asyncio.sleep(self.config.refresh_interval)
                
            except KeyboardInterrupt:
                logger.info("Dashboard stopped by user")
                break
            except Exception as e:
                logger.error(f"Dashboard display error: {e}")
                await asyncio.sleep(1)
    
    async def start(self):
        """Start dashboard"""
        if self.running:
            logger.warning("Dashboard already running")
            return
        
        logger.info("Starting dashboard")
        self.running = True
        
        # Start display task
        self.dashboard_task = asyncio.create_task(self._display_loop())
    
    async def stop(self):
        """Stop dashboard"""
        if not self.running:
            return
        
        logger.info("Stopping dashboard")
        self.running = False
        
        # Cancel dashboard task
        if self.dashboard_task:
            self.dashboard_task.cancel()
            try:
                await self.dashboard_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Dashboard stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current dashboard status"""
        return {
            "running": self.running,
            "logs_count": len(self.logs),
            "emotions_count": len(self.emotions),
            "agenda_count": len(self.daily_agenda),
            "current_platform": self.current_platform.value,
            "refresh_interval": self.config.refresh_interval,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test the dashboard"""
    from loguru import logger
    
    logger.add("logs/dashboard_{time}.log", rotation="10 MB")
    
    # Create dashboard
    config = DashboardConfig()
    dashboard = Dashboard(config)
    
    # Test status update
    dashboard.update_status({
        "state": "LISTENING",
        "active_speaker": "Lasse",
        "emotion": "Happy",
        "last_keyword": "budget",
        "names": ["Lasse", "Anna"]
    })
    
    # Test logs
    dashboard.add_log("Agent initialized", "INFO")
    dashboard.add_log("Transcription: Hej, hur är det?", "INFO")
    dashboard.add_log("Emotion detected: Happy", "DEBUG")
    
    # Test emotions
    dashboard.update_emotions({"Lasse": "Happy", "Anna": "Neutral"})
    
    # Test status
    status = dashboard.get_status()
    logger.info(f"Dashboard status: {status}")
    
    # Test display (short test)
    try:
        await dashboard.start()
        await asyncio.sleep(5)  # Display for 5 seconds
        await dashboard.stop()
    except Exception as e:
        logger.error(f"Test error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
