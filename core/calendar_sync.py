#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Calendar Sync Module
Fetches and classifies meetings from Microsoft Graph and Google Calendar APIs
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path

import pytz
from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from pydantic import BaseModel, Field


class MeetingType(Enum):
    """Meeting type classification"""
    DIGITAL = "digital"
    PHYSICAL = "physical"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class MeetingStatus(Enum):
    """Meeting status for agent"""
    AGENT_READY = "agent_ready"
    HUMAN_REQUIRED = "human_required"
    CONFLICT = "conflict"


class Meeting(BaseModel):
    """Meeting data model"""
    id: str
    title: str
    start_time: datetime
    end_time: datetime
    location: str = ""
    description: str = ""
    platform: str = ""
    meeting_type: MeetingType = MeetingType.UNKNOWN
    status: MeetingStatus = MeetingStatus.UNKNOWN
    outfit: str = "casual"
    notes: str = ""


class CalendarConfig(BaseModel):
    """Configuration for calendar sync"""
    enable_microsoft_graph: bool = Field(default=False, description="Enable Microsoft Graph API (Outlook/Teams)")
    enable_google_calendar: bool = Field(default=False, description="Enable Google Calendar API")
    timezone: str = Field(default="Europe/Stockholm", description="System timezone")
    check_interval_minutes: int = Field(default=15, description="Check interval in minutes")
    look_ahead_hours: int = Field(default=24, description="Look ahead in hours")
    
    # Microsoft Graph API settings
    microsoft_client_id: str = Field(default="", description="Microsoft Graph Client ID")
    microsoft_client_secret: str = Field(default="", description="Microsoft Graph Client Secret")
    microsoft_tenant_id: str = Field(default="", description="Microsoft Graph Tenant ID")
    
    # Google Calendar API settings
    google_credentials_path: str = Field(default="credentials/google_calendar.json", description="Google Calendar credentials path")


class CalendarSync:
    """
    Calendar synchronization and meeting classification
    Fetches meetings from Microsoft Graph and Google Calendar APIs
    """
    
    def __init__(self, config: CalendarConfig):
        """Initialize calendar sync"""
        self.config = config
        
        # State
        self.running = False
        self.sync_task = None
        self.meetings: List[Meeting] = []
        
        # Callbacks
        self.on_new_meeting: Optional[callable] = None
        self.on_meeting_status_change: Optional[callable] = None
        
        logger.info(f"Calendar Sync initialized (timezone: {config.timezone})")
    
    def classify_meeting(self, event: Dict[str, Any]) -> MeetingType:
        """
        Classify meeting type based on metadata
        
        Args:
            event: Meeting event data
        
        Returns:
            MeetingType classification
        """
        description = event.get("description", "").lower()
        location = event.get("location", "").lower()
        
        # Digital platforms
        digital_indicators = [
            "teams.microsoft.com",
            "meet.google.com",
            "zoom.us",
            "zoom",
            "teams",
            "google meet",
            "webex",
            "slack"
        ]
        
        # Physical indicators
        physical_indicators = [
            "gata",
            "väg",
            "rum",
            "konferens",
            "kontor",
            "address",
            "floor",
            "suite"
        ]
        
        # Check for digital indicators
        has_digital = any(indicator in description or indicator in location for indicator in digital_indicators)
        
        # Check for physical indicators
        has_physical = any(indicator in location for indicator in physical_indicators)
        
        # Check for URL
        has_url = any(url in description for url in ["http://", "https://"])
        
        if has_digital or has_url:
            if has_physical:
                return MeetingType.HYBRID
            return MeetingType.DIGITAL
        elif has_physical:
            return MeetingType.PHYSICAL
        
        return MeetingType.UNKNOWN
    
    def determine_agent_status(self, meeting: Meeting) -> MeetingStatus:
        """
        Determine if agent should attend or human required
        
        Args:
            meeting: Meeting object
        
        Returns:
            MeetingStatus
        """
        if meeting.meeting_type == MeetingType.DIGITAL:
            return MeetingStatus.AGENT_READY
        elif meeting.meeting_type == MeetingType.PHYSICAL:
            return MeetingStatus.HUMAN_REQUIRED
        elif meeting.meeting_type == MeetingType.HYBRID:
            # Ask user for preference (to be implemented)
            return MeetingStatus.AGENT_READY
        else:
            return MeetingStatus.HUMAN_REQUIRED
    
    def fetch_microsoft_graph_meetings(self) -> List[Dict[str, Any]]:
        """
        Fetch meetings from Microsoft Graph API (Outlook/Teams)
        
        Returns:
            List of meeting events
        """
        # Placeholder for Microsoft Graph API integration
        # In production, use msal library and Graph API
        logger.info("Fetching Microsoft Graph meetings (placeholder)")
        return []
    
    def fetch_google_calendar_meetings(self) -> List[Dict[str, Any]]:
        """
        Fetch meetings from Google Calendar API
        
        Returns:
            List of meeting events
        """
        if not self.config.enable_google_calendar:
            return []
        
        try:
            from integration.google_calendar import GoogleCalendar
            
            client = GoogleCalendar(credentials_path=self.config.google_credentials_path)
            
            if client.authenticate():
                # Get timezone
                tz = pytz.timezone(self.config.timezone)
                now = datetime.now(tz)
                end = now + timedelta(hours=self.config.look_ahead_hours)
                
                # Convert to UTC for API
                start_utc = now.astimezone(timezone.utc)
                end_utc = end.astimezone(timezone.utc)
                
                meetings = client.fetch_meetings(start_utc, end_utc)
                logger.info(f"Fetched {len(meetings)} meetings from Google Calendar")
                return meetings
            else:
                logger.error("Google Calendar authentication failed")
                return []
                
        except ImportError:
            logger.error("Google Calendar integration not available")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch Google Calendar meetings: {e}")
            return []
    
    def fetch_all_meetings(self) -> List[Meeting]:
        """
        Fetch and merge meetings from all configured sources
        
        Returns:
            List of Meeting objects
        """
        all_events = []
        
        # Fetch from Microsoft Graph
        if self.config.enable_microsoft_graph:
            all_events.extend(self.fetch_microsoft_graph_meetings())
        
        # Fetch from Google Calendar
        if self.config.enable_google_calendar:
            all_events.extend(self.fetch_google_calendar_meetings())
        
        # Convert to Meeting objects
        meetings = []
        for event in all_events:
            meeting = Meeting(
                id=event.get("id", ""),
                title=event.get("title", "Untitled Meeting"),
                start_time=event.get("start_time", datetime.now(timezone.utc)),
                end_time=event.get("end_time", datetime.now(timezone.utc)),
                location=event.get("location", ""),
                description=event.get("description", ""),
                platform=event.get("platform", "")
            )
            
            # Classify meeting type
            meeting.meeting_type = self.classify_meeting(event)
            
            # Determine agent status
            meeting.status = self.determine_agent_status(meeting)
            
            meetings.append(meeting)
        
        return meetings
    
    def detect_double_booking(self, meetings: List[Meeting]) -> List[Dict[str, Any]]:
        """
        Detect double-booked meetings
        
        Args:
            meetings: List of meetings
        
        Returns:
            List of conflicts
        """
        conflicts = []
        
        # Sort meetings by start time
        sorted_meetings = sorted(meetings, key=lambda m: m.start_time)
        
        for i in range(len(sorted_meetings) - 1):
            current = sorted_meetings[i]
            next_meeting = sorted_meetings[i + 1]
            
            # Check for overlap
            if current.end_time > next_meeting.start_time:
                conflicts.append({
                    "meeting1": current.title,
                    "meeting2": next_meeting.title,
                    "time": current.start_time,
                    "type": "overlap"
                })
        
        return conflicts
    
    def get_daily_agenda(self) -> List[Dict[str, Any]]:
        """
        Get daily agenda formatted for dashboard
        
        Returns:
            List of agenda items
        """
        agenda = []
        
        for meeting in self.meetings:
            agenda_item = {
                "time": meeting.start_time.strftime("%H:%M"),
                "title": meeting.title,
                "status": meeting.status.value,
                "type": meeting.meeting_type.value,
                "outfit": meeting.outfit if meeting.status == MeetingStatus.AGENT_READY else "N/A"
            }
            agenda.append(agenda_item)
        
        return agenda
    
    async def _sync_loop(self):
        """Main synchronization loop"""
        logger.info("Starting calendar sync loop")
        
        while self.running:
            try:
                # Fetch all meetings
                self.meetings = self.fetch_all_meetings()
                
                # Detect conflicts
                conflicts = self.detect_double_booking(self.meetings)
                if conflicts:
                    logger.warning(f"Detected {len(conflicts)} double-booking conflicts")
                    # TODO: Ask user for priority
                
                # Notify callbacks
                if self.on_new_meeting and self.meetings:
                    self.on_new_meeting(self.meetings)
                
                logger.info(f"Synced {len(self.meetings)} meetings")
                
                # Sleep for check interval
                await asyncio.sleep(self.config.check_interval_minutes * 60)
                
            except Exception as e:
                logger.error(f"Calendar sync loop error: {e}")
                await asyncio.sleep(60)
    
    async def start(self):
        """Start calendar synchronization"""
        if self.running:
            logger.warning("Calendar sync already running")
            return
        
        logger.info("Starting calendar sync")
        self.running = True
        
        # Start sync task
        self.sync_task = asyncio.create_task(self._sync_loop())
    
    async def stop(self):
        """Stop calendar synchronization"""
        if not self.running:
            return
        
        logger.info("Stopping calendar sync")
        self.running = False
        
        # Cancel sync task
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Calendar sync stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current sync status"""
        return {
            "running": self.running,
            "meetings_count": len(self.meetings),
            "digital_count": len([m for m in self.meetings if m.meeting_type == MeetingType.DIGITAL]),
            "physical_count": len([m for m in self.meetings if m.meeting_type == MeetingType.PHYSICAL]),
            "check_interval": self.config.check_interval_minutes,
            "timezone": self.config.timezone,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test the calendar sync"""
    from loguru import logger
    
    logger.add("logs/calendar_sync_{time}.log", rotation="10 MB")
    
    # Create calendar sync
    config = CalendarConfig()
    sync = CalendarSync(config)
    
    # Test classification
    test_event = {
        "title": "Team Meeting",
        "description": "Join via Teams: https://teams.microsoft.com/l/meetup/xxx",
        "location": ""
    }
    
    meeting_type = sync.classify_meeting(test_event)
    logger.info(f"Classification: {meeting_type.value}")
    
    # Test status
    status = sync.get_status()
    logger.info(f"Calendar Sync status: {status}")
    
    # Test sync loop (short test)
    try:
        await sync.start()
        await asyncio.sleep(2)
        await sync.stop()
    except Exception as e:
        logger.error(f"Test error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
