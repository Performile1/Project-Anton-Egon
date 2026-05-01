#!/usr/bin/env python3
"""
Project Anton Egon - Slack Adapter
Handles real-time messages from Slack channels and DMs

Phase 13: Unified Communication Hub
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

import aiohttp
from loguru import logger

from core.dispatcher import IncomingMessage, OutgoingMessage, Platform


class SlackAdapter:
    """
    Slack Adapter
    Connects to Slack via Slack API (Web API or Socket Mode)
    """
    
    def __init__(self, bot_token: str, signing_secret: Optional[str] = None):
        """
        Initialize Slack adapter
        
        Args:
            bot_token: Slack Bot Token (xoxb-...)
            signing_secret: Slack Signing Secret (for webhooks)
        """
        self.bot_token = bot_token
        self.signing_secret = signing_secret
        
        self.api_endpoint = "https://slack.com/api"
        self.is_connected = False
        
        logger.info("Slack Adapter initialized")
    
    async def connect(self) -> bool:
        """
        Authenticate with Slack API
        
        Returns:
            True if connected successfully
        """
        try:
            # Test connection with auth.test
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_endpoint}/auth.test"
                headers = {
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/json"
                }
                
                async with session.post(url, headers=headers) as response:
                    data = await response.json()
                    
                    if data.get("ok"):
                        self.is_connected = True
                        logger.info(f"Slack adapter connected as {data.get('user')}")
                        return True
                    else:
                        logger.error(f"Slack authentication failed: {data.get('error')}")
                        return False
                        
        except Exception as e:
            logger.error(f"Slack connection error: {e}")
            return False
    
    async def get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json"
        }
    
    async def receive_messages(self, channel_id: str, limit: int = 10) -> List[IncomingMessage]:
        """
        Receive recent messages from a Slack channel
        
        Args:
            channel_id: Slack channel ID
            limit: Number of messages to fetch
        
        Returns:
            List of incoming messages
        """
        if not self.is_connected:
            logger.error("Slack adapter not connected")
            return []
        
        try:
            url = f"{self.api_endpoint}/conversations.history"
            headers = await self.get_headers()
            params = {
                "channel": channel_id,
                "limit": limit,
                "include_all_metadata": True
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    data = await response.json()
                    
                    if data.get("ok"):
                        messages = []
                        
                        for msg in data.get("messages", []):
                            incoming = self._parse_message(msg, channel_id)
                            if incoming:
                                messages.append(incoming)
                        
                        logger.info(f"Received {len(messages)} messages from Slack")
                        return messages
                    else:
                        logger.error(f"Failed to fetch messages: {data.get('error')}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error receiving Slack messages: {e}")
            return []
    
    async def send(self, message: OutgoingMessage) -> bool:
        """
        Send message to Slack
        
        Args:
            message: Outgoing message
        
        Returns:
            True if sent successfully
        """
        if not self.is_connected:
            logger.error("Slack adapter not connected")
            return False
        
        try:
            url = f"{self.api_endpoint}/chat.postMessage"
            headers = await self.get_headers()
            
            payload = {
                "channel": message.channel_id,
                "text": message.content,
                "as_user": False
            }
            
            # If thread_id exists, reply in thread
            if message.thread_id:
                payload["thread_ts"] = message.thread_id
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    data = await response.json()
                    
                    if data.get("ok"):
                        logger.info(f"Message sent to Slack: {message.channel_id}")
                        return True
                    else:
                        logger.error(f"Failed to send message: {data.get('error')}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending Slack message: {e}")
            return False
    
    async def get_channels(self) -> List[Dict[str, Any]]:
        """
        Get all Slack channels
        
        Returns:
            List of channel information
        """
        if not self.is_connected:
            return []
        
        try:
            url = f"{self.api_endpoint}/conversations.list"
            headers = await self.get_headers()
            params = {"types": "public_channel,private_channel,mpim,im"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    data = await response.json()
                    
                    if data.get("ok"):
                        return data.get("channels", [])
                    else:
                        logger.error(f"Failed to fetch channels: {data.get('error')}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error fetching Slack channels: {e}")
            return []
    
    async def get_users(self) -> List[Dict[str, Any]]:
        """
        Get all Slack users
        
        Returns:
            List of user information
        """
        if not self.is_connected:
            return []
        
        try:
            url = f"{self.api_endpoint}/users.list"
            headers = await self.get_headers()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    
                    if data.get("ok"):
                        return data.get("members", [])
                    else:
                        logger.error(f"Failed to fetch users: {data.get('error')}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error fetching Slack users: {e}")
            return []
    
    def _parse_message(self, msg: Dict[str, Any], channel_id: str) -> Optional[IncomingMessage]:
        """
        Parse Slack message to IncomingMessage
        
        Args:
            msg: Slack message object
            channel_id: Channel ID
        
        Returns:
            Incoming message or None
        """
        try:
            # Skip bot messages and messages from the bot itself
            if msg.get("bot_id") or msg.get("subtype") == "bot_message":
                return None
            
            content = msg.get("text", "")
            user_id = msg.get("user", "")
            timestamp = float(msg.get("ts", 0))
            
            incoming = IncomingMessage(
                platform=Platform.SLACK,
                message_id=msg.get("ts", ""),
                sender=user_id,  # Will be resolved to name later
                content=content,
                timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc),
                channel_id=channel_id,
                thread_id=msg.get("thread_ts"),
                metadata={
                    "message_type": msg.get("subtype", "message"),
                    "reactions": msg.get("reactions", []),
                    "attachments": msg.get("attachments", [])
                }
            )
            
            return incoming
            
        except Exception as e:
            logger.error(f"Error parsing Slack message: {e}")
            return None
    
    async def resolve_user_name(self, user_id: str) -> str:
        """
        Resolve user ID to display name
        
        Args:
            user_id: Slack user ID
        
        Returns:
            Display name
        """
        try:
            url = f"{self.api_endpoint}/users.info"
            headers = await self.get_headers()
            params = {"user": user_id}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    data = await response.json()
                    
                    if data.get("ok"):
                        user = data.get("user", {})
                        return user.get("real_name", user.get("name", user_id))
                    
            return user_id
                    
        except Exception as e:
            logger.error(f"Error resolving user name: {e}")
            return user_id
    
    async def monitor_channel(self, channel_id: str, callback):
        """
        Monitor a channel for new messages (polling)
        
        Args:
            channel_id: Channel ID to monitor
            callback: Callback function for new messages
        """
        last_timestamp = None
        
        while self.is_connected:
            messages = await self.receive_messages(channel_id, limit=5)
            
            for msg in messages:
                if last_timestamp and msg.message_id != last_timestamp:
                    # Resolve sender name
                    msg.sender = await self.resolve_user_name(msg.sender)
                    await callback(msg)
                last_timestamp = msg.message_id
            
            await asyncio.sleep(10)  # Poll every 10 seconds


async def main():
    """Test Slack Adapter"""
    logger.add("logs/slack_adapter_{time}.log", rotation="10 MB")
    
    adapter = SlackAdapter(
        bot_token="xoxb-your-bot-token"
    )
    
    # Test connection (will fail with placeholder token)
    # await adapter.connect()
    # channels = await adapter.get_channels()
    # logger.info(f"Channels: {channels}")
    
    logger.info("Slack Adapter module loaded")


if __name__ == "__main__":
    asyncio.run(main())
