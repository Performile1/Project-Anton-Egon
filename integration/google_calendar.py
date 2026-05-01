#!/usr/bin/env python3
"""
Project Anton Egon - Google Calendar API Integration
Fetches meetings from Google Calendar
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from pathlib import Path

import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from loguru import logger


class GoogleCalendarConfig:
    """Configuration for Google Calendar API"""
    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
    CREDENTIALS_PATH = "credentials/google_calendar.json"
    TOKEN_PATH = "credentials/google_calendar_token.json"


class GoogleCalendar:
    """
    Google Calendar API integration
    """
    
    def __init__(self, credentials_path: str = None):
        """
        Initialize Google Calendar client
        
        Args:
            credentials_path: Path to OAuth2 credentials JSON file
        """
        self.credentials_path = credentials_path or GoogleCalendarConfig.CREDENTIALS_PATH
        self.token_path = GoogleCalendarConfig.TOKEN_PATH
        self.scopes = GoogleCalendarConfig.SCOPES
        
        self.credentials = None
        self.service = None
        
        logger.info("Google Calendar initialized")
    
    def authenticate(self) -> bool:
        """
        Authenticate with Google Calendar API using OAuth2
        
        Returns:
            True if authentication successful
        """
        try:
            # Load existing token if available
            if os.path.exists(self.token_path):
                with open(self.token_path, "rb") as token:
                    self.credentials = pickle.load(token)
            
            # If no valid credentials, perform OAuth flow
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    self.credentials.refresh(Request())
                else:
                    if not os.path.exists(self.credentials_path):
                        logger.error(f"Credentials file not found: {self.credentials_path}")
                        logger.info("Please download credentials from Google Cloud Console:")
                        logger.info("https://console.cloud.google.com/apis/credentials")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_path, self.scopes
                    )
                    self.credentials = flow.run_local_server(port=0)
                
                # Save credentials for future use
                with open(self.token_path, "wb") as token:
                    pickle.dump(self.credentials, token)
            
            # Build service
            self.service = build("calendar", "v3", credentials=self.credentials)
            logger.info("Google Calendar authentication successful")
            return True
            
        except Exception as e:
            logger.error(f"Google Calendar authentication error: {e}")
            return False
    
    def fetch_meetings(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        Fetch meetings from Google Calendar
        
        Args:
            start_date: Start date for meeting query
            end_date: End date for meeting query
        
        Returns:
            List of meeting events
        """
        if not self.service:
            logger.error("Not authenticated. Call authenticate() first.")
            return []
        
        try:
            # Format dates for Calendar API
            start_str = start_date.isoformat() + "Z"
            end_str = end_date.isoformat() + "Z"
            
            # Build query
            events_result = self.service.events().list(
                calendarId="primary",
                timeMin=start_str,
                timeMax=end_str,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            
            events = events_result.get("items", [])
            meetings = []
            
            for event in events:
                meeting = self._parse_event(event)
                if meeting:
                    meetings.append(meeting)
            
            logger.info(f"Fetched {len(meetings)} meetings from Google Calendar")
            return meetings
            
        except HttpError as e:
            logger.error(f"Google Calendar API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching meetings: {e}")
            return []
    
    def _parse_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Google Calendar event to standard meeting format
        
        Args:
            event: Calendar API event object
        
        Returns:
            Parsed meeting dictionary
        """
        try:
            start = event.get("start", {})
            end = event.get("end", {})
            
            # Handle date vs datetime
            start_datetime = start.get("dateTime") or start.get("date")
            end_datetime = end.get("dateTime") or end.get("date")
            
            # Parse datetime
            if "dateTime" in start:
                start_time = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                end_time = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
            else:
                # All-day event
                start_time = datetime.fromisoformat(start["date"])
                end_time = datetime.fromisoformat(end["date"])
            
            meeting = {
                "id": event.get("id", ""),
                "title": event.get("summary", "Untitled Meeting"),
                "start_time": start_time,
                "end_time": end_time,
                "location": event.get("location", ""),
                "description": event.get("description", ""),
                "platform": self._detect_platform(event),
                "is_online": self._is_online_meeting(event)
            }
            
            return meeting
            
        except Exception as e:
            logger.error(f"Error parsing event: {e}")
            return None
    
    def _detect_platform(self, event: Dict[str, Any]) -> str:
        """Detect meeting platform from event data"""
        description = event.get("description", "").lower()
        location = event.get("location", "").lower()
        conference_data = event.get("conferenceData", {})
        
        if "meet.google.com" in description or "meet.google.com" in location:
            return "google_meet"
        elif "zoom.us" in description or "zoom" in location:
            return "zoom"
        elif "teams.microsoft.com" in description or "teams" in location:
            return "microsoft_teams"
        elif conference_data:
            return "google_meet"  # Default for Google Meet conferences
        else:
            return "unknown"
    
    def _is_online_meeting(self, event: Dict[str, Any]) -> bool:
        """Check if event is an online meeting"""
        description = event.get("description", "").lower()
        location = event.get("location", "").lower()
        
        online_indicators = [
            "meet.google.com",
            "zoom.us",
            "teams.microsoft.com",
            "hangout",
            "video call"
        ]
        
        return any(indicator in description or indicator in location for indicator in online_indicators)


async def main():
    """Test Google Calendar integration"""
    from loguru import logger
    
    logger.add("logs/google_calendar_{time}.log", rotation="10 MB")
    
    # Test with placeholder credentials
    client = GoogleCalendar()
    
    # Authentication will fail without credentials file
    # Uncomment and add credentials to test
    # if client.authenticate():
    #     start = datetime.now(timezone.utc)
    #     end = start + timedelta(hours=24)
    #     meetings = client.fetch_meetings(start, end)
    #     logger.info(f"Meetings: {meetings}")
    
    logger.info("Google Calendar integration module loaded")


if __name__ == "__main__":
    asyncio.run(main())
