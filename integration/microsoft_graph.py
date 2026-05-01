#!/usr/bin/env python3
"""
Project Anton Egon - Microsoft Graph API Integration
Fetches meetings from Outlook/Teams via Microsoft Graph API
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from pathlib import Path

import msal
import requests
from loguru import logger


class MicrosoftGraphConfig:
    """Configuration for Microsoft Graph API"""
    CLIENT_ID = ""
    CLIENT_SECRET = ""
    TENANT_ID = ""
    AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
    SCOPE = ["https://graph.microsoft.com/.default"]
    GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"


class MicrosoftGraphCalendar:
    """
    Microsoft Graph API integration for Outlook/Teams calendar
    """
    
    def __init__(self, client_id: str, client_secret: str, tenant_id: str):
        """
        Initialize Microsoft Graph client
        
        Args:
            client_id: Azure AD application client ID
            client_secret: Azure AD application client secret
            tenant_id: Azure AD tenant ID
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"
        self.scope = ["https://graph.microsoft.com/.default"]
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"
        
        self.app = None
        self.access_token = None
        
        logger.info("Microsoft Graph Calendar initialized")
    
    def authenticate(self) -> bool:
        """
        Authenticate with Microsoft Graph API using client credentials flow
        
        Returns:
            True if authentication successful
        """
        try:
            # Create MSAL application
            self.app = msal.ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=self.authority
            )
            
            # Get access token
            result = self.app.acquire_token_for_client(scopes=self.scope)
            
            if "access_token" in result:
                self.access_token = result["access_token"]
                logger.info("Microsoft Graph authentication successful")
                return True
            else:
                logger.error(f"Microsoft Graph authentication failed: {result.get('error_description')}")
                return False
                
        except Exception as e:
            logger.error(f"Microsoft Graph authentication error: {e}")
            return False
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    def fetch_meetings(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        Fetch meetings from Outlook calendar
        
        Args:
            start_date: Start date for meeting query
            end_date: End date for meeting query
        
        Returns:
            List of meeting events
        """
        if not self.access_token:
            logger.error("Not authenticated. Call authenticate() first.")
            return []
        
        try:
            # Format dates for Graph API
            start_str = start_date.strftime("%Y-%m-%dT%H:%M:%S")
            end_str = end_date.strftime("%Y-%m-%dT%H:%M:%S")
            
            # Build query
            url = f"{self.graph_endpoint}/me/calendarView"
            params = {
                "startDateTime": f"{start_str}Z",
                "endDateTime": f"{end_str}Z",
                "$orderby": "start/dateTime"
            }
            
            headers = self.get_headers()
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                meetings = []
                
                for event in data.get("value", []):
                    meeting = self._parse_event(event)
                    if meeting:
                        meetings.append(meeting)
                
                logger.info(f"Fetched {len(meetings)} meetings from Microsoft Graph")
                return meetings
            else:
                logger.error(f"Failed to fetch meetings: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error fetching meetings: {e}")
            return []
    
    def _parse_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Microsoft Graph event to standard meeting format
        
        Args:
            event: Graph API event object
        
        Returns:
            Parsed meeting dictionary
        """
        try:
            start = event.get("start", {})
            end = event.get("end", {})
            
            meeting = {
                "id": event.get("id", ""),
                "title": event.get("subject", "Untitled Meeting"),
                "start_time": datetime.fromisoformat(start.get("dateTime", "").replace("Z", "+00:00")),
                "end_time": datetime.fromisoformat(end.get("dateTime", "").replace("Z", "+00:00")),
                "location": event.get("location", {}).get("displayName", ""),
                "description": event.get("body", {}).get("content", ""),
                "platform": "microsoft_teams",
                "is_online": self._is_online_meeting(event)
            }
            
            return meeting
            
        except Exception as e:
            logger.error(f"Error parsing event: {e}")
            return None
    
    def _is_online_meeting(self, event: Dict[str, Any]) -> bool:
        """Check if event is an online meeting"""
        return event.get("isOnlineMeeting", False) or \
               "onlineMeeting" in event or \
               "joinUrl" in event
    
    def get_meeting_url(self, event_id: str) -> Optional[str]:
        """
        Get Teams meeting URL for an event
        
        Args:
            event_id: Event ID
        
        Returns:
            Meeting URL or None
        """
        if not self.access_token:
            return None
        
        try:
            url = f"{self.graph_endpoint}/me/events/{event_id}"
            headers = self.get_headers()
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                event = response.json()
                online_meeting = event.get("onlineMeeting", {})
                return online_meeting.get("joinUrl")
            
        except Exception as e:
            logger.error(f"Error getting meeting URL: {e}")
        
        return None


async def main():
    """Test Microsoft Graph integration"""
    from loguru import logger
    
    logger.add("logs/microsoft_graph_{time}.log", rotation="10 MB")
    
    # Test with placeholder credentials
    client = MicrosoftGraphCalendar(
        client_id="your_client_id",
        client_secret="your_client_secret",
        tenant_id="your_tenant_id"
    )
    
    # Authentication will fail with placeholder credentials
    # Uncomment and add real credentials to test
    # if client.authenticate():
    #     start = datetime.now(timezone.utc)
    #     end = start + timedelta(hours=24)
    #     meetings = client.fetch_meetings(start, end)
    #     logger.info(f"Meetings: {meetings}")
    
    logger.info("Microsoft Graph integration module loaded")


if __name__ == "__main__":
    asyncio.run(main())
