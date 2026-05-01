#!/usr/bin/env python3
"""
Project Anton Egon - Microsoft Teams Chat Adapter
Handles real-time chat messages from Microsoft Teams

Phase 13: Unified Communication Hub
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum

import aiohttp
from loguru import logger

from core.dispatcher import IncomingMessage, OutgoingMessage, Platform


class TeamsEventType(Enum):
    """Teams webhook event types"""
    MESSAGE_CREATED = "messageCreated"
    MESSAGE_UPDATED = "messageUpdated"
    MESSAGE_DELETED = "messageDeleted"
    MEMBER_ADDED = "memberAdded"
    MEMBER_REMOVED = "memberRemoved"


class TeamsAdapter:
    """
    Microsoft Teams Chat Adapter
    Connects to Teams via Microsoft Graph API or Webhooks
    """
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        webhook_url: Optional[str] = None
    ):
        """
        Initialize Teams adapter
        
        Args:
            client_id: Azure AD application client ID
            client_secret: Azure AD application client secret
            tenant_id: Azure AD tenant ID
            webhook_url: Optional webhook URL for real-time events
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.webhook_url = webhook_url
        
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"
        self.scope = ["https://graph.microsoft.com/.default"]
        
        self.access_token = None
        self.is_connected = False
        
        logger.info("Teams Chat Adapter initialized")
    
    async def connect(self) -> bool:
        """
        Authenticate with Microsoft Graph API
        
        Returns:
            True if connected successfully
        """
        try:
            import msal
            
            app = msal.ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=self.authority
            )
            
            result = app.acquire_token_for_client(scopes=self.scope)
            
            if "access_token" in result:
                self.access_token = result["access_token"]
                self.is_connected = True
                logger.info("Teams adapter connected")
                return True
            else:
                logger.error(f"Teams authentication failed: {result.get('error_description')}")
                return False
                
        except Exception as e:
            logger.error(f"Teams connection error: {e}")
            return False
    
    async def get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def receive_messages(self, channel_id: str, limit: int = 10) -> List[IncomingMessage]:
        """
        Receive recent messages from a Teams channel
        
        Args:
            channel_id: Teams channel ID
            limit: Number of messages to fetch
        
        Returns:
            List of incoming messages
        """
        if not self.is_connected:
            logger.error("Teams adapter not connected")
            return []
        
        try:
            url = f"{self.graph_endpoint}/teams/{channel_id}/messages"
            headers = await self.get_headers()
            params = {"$top": limit, "$orderby": "createdDateTime desc"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        messages = []
                        
                        for msg in data.get("value", []):
                            incoming = self._parse_message(msg, channel_id)
                            if incoming:
                                messages.append(incoming)
                        
                        logger.info(f"Received {len(messages)} messages from Teams")
                        return messages
                    else:
                        logger.error(f"Failed to fetch messages: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error receiving Teams messages: {e}")
            return []
    
    async def send(self, message: OutgoingMessage) -> bool:
        """
        Send message to Teams
        
        Args:
            message: Outgoing message
        
        Returns:
            True if sent successfully
        """
        if not self.is_connected:
            logger.error("Teams adapter not connected")
            return False
        
        try:
            url = f"{self.graph_endpoint}/teams/{message.channel_id}/messages"
            headers = await self.get_headers()
            
            payload = {
                "body": {
                    "content": message.content,
                    "contentType": "html"
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 201:
                        logger.info(f"Message sent to Teams: {message.channel_id}")
                        return True
                    else:
                        logger.error(f"Failed to send message: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending Teams message: {e}")
            return False
    
    async def get_channels(self) -> List[Dict[str, Any]]:
        """
        Get all Teams channels
        
        Returns:
            List of channel information
        """
        if not self.is_connected:
            return []
        
        try:
            url = f"{self.graph_endpoint}/me/chats"
            headers = await self.get_headers()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("value", [])
                    else:
                        logger.error(f"Failed to fetch channels: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error fetching Teams channels: {e}")
            return []
    
    def _parse_message(self, msg: Dict[str, Any], channel_id: str) -> Optional[IncomingMessage]:
        """
        Parse Teams message to IncomingMessage
        
        Args:
            msg: Teams message object
            channel_id: Channel ID
        
        Returns:
            Incoming message or None
        """
        try:
            from_id = msg.get("from", {})
            user = from_id.get("user", {})
            
            content = msg.get("body", {}).get("content", "")
            
            incoming = IncomingMessage(
                platform=Platform.TEAMS_CHAT,
                message_id=msg.get("id", ""),
                sender=user.get("displayName", "Unknown"),
                content=content,
                timestamp=datetime.fromisoformat(msg.get("createdDateTime", "").replace("Z", "+00:00")),
                channel_id=channel_id,
                metadata={
                    "message_type": msg.get("messageType", "text"),
                    "attachments": msg.get("attachments", [])
                }
            )
            
            return incoming
            
        except Exception as e:
            logger.error(f"Error parsing Teams message: {e}")
            return None
    
    async def handle_webhook(self, event_data: Dict[str, Any]) -> Optional[IncomingMessage]:
        """
        Handle webhook event from Teams
        
        Args:
            event_data: Webhook event data
        
        Returns:
            Incoming message or None
        """
        try:
            event_type = event_data.get("value", [{}])[0].get("changeType")
            
            if event_type == TeamsEventType.MESSAGE_CREATED.value:
                resource = event_data.get("value", [{}])[0].get("resource", "")
                # Fetch full message
                # TODO: Implement message fetch by ID
                logger.info("New message created via webhook")
            
            return None
            
        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
            return None
    
    async def monitor_channel(self, channel_id: str, callback):
        """
        Monitor a channel for new messages (polling)
        
        Args:
            channel_id: Channel ID to monitor
            callback: Callback function for new messages
        """
        last_message_id = None
        
        while self.is_connected:
            messages = await self.receive_messages(channel_id, limit=5)
            
            for msg in messages:
                if last_message_id and msg.message_id != last_message_id:
                    await callback(msg)
                last_message_id = msg.message_id
            
            await asyncio.sleep(10)  # Poll every 10 seconds


async def main():
    """Test Teams Adapter"""
    logger.add("logs/teams_adapter_{time}.log", rotation="10 MB")
    
    adapter = TeamsAdapter(
        client_id="your_client_id",
        client_secret="your_client_secret",
        tenant_id="your_tenant_id"
    )
    
    # Test connection (will fail with placeholder credentials)
    # await adapter.connect()
    # channels = await adapter.get_channels()
    # logger.info(f"Channels: {channels}")
    
    logger.info("Teams Adapter module loaded")


if __name__ == "__main__":
    asyncio.run(main())
