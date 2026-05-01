#!/usr/bin/env python3
"""
Project Anton Egon - Email Engine
Reads and writes emails via Outlook (Microsoft Graph) and Gmail API

Phase 13: Unified Communication Hub
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from enum import Enum

import aiohttp
from loguru import logger

from core.dispatcher import IncomingMessage, OutgoingMessage, Platform


class EmailProvider(Enum):
    """Email providers"""
    OUTLOOK = "outlook"
    GMAIL = "gmail"


class EmailEngine:
    """
    Email Engine
    Handles email reading and writing for Outlook and Gmail
    """
    
    def __init__(
        self,
        provider: EmailProvider,
        client_id: str,
        client_secret: str,
        tenant_id: Optional[str] = None,
        refresh_token: Optional[str] = None
    ):
        """
        Initialize Email Engine
        
        Args:
            provider: Email provider (OUTLOOK or GMAIL)
            client_id: OAuth client ID
            client_secret: OAuth client secret
            tenant_id: Azure AD tenant ID (Outlook only)
            refresh_token: OAuth refresh token
        """
        self.provider = provider
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.refresh_token = refresh_token
        
        self.access_token = None
        self.is_connected = False
        
        # API endpoints
        if provider == EmailProvider.OUTLOOK:
            self.authority = f"https://login.microsoftonline.com/{tenant_id}"
            self.graph_endpoint = "https://graph.microsoft.com/v1.0"
            self.scope = ["https://graph.microsoft.com/.default"]
        else:  # Gmail
            self.auth_endpoint = "https://oauth2.googleapis.com/token"
            self.gmail_endpoint = "https://gmail.googleapis.com/gmail/v1"
            self.scope = ["https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.readonly"]
        
        logger.info(f"Email Engine initialized for {provider.value}")
    
    async def connect(self) -> bool:
        """
        Authenticate with email provider
        
        Returns:
            True if connected successfully
        """
        try:
            if self.provider == EmailProvider.OUTLOOK:
                return await self._connect_outlook()
            else:
                return await self._connect_gmail()
        except Exception as e:
            logger.error(f"Email connection error: {e}")
            return False
    
    async def _connect_outlook(self) -> bool:
        """Authenticate with Microsoft Graph API"""
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
                logger.info("Outlook email connected")
                return True
            else:
                logger.error(f"Outlook authentication failed: {result.get('error_description')}")
                return False
                
        except Exception as e:
            logger.error(f"Outlook connection error: {e}")
            return False
    
    async def _connect_gmail(self) -> bool:
        """Authenticate with Gmail API"""
        try:
            # Use refresh token to get access token
            async with aiohttp.ClientSession() as session:
                url = self.auth_endpoint
                params = {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token"
                }
                
                async with session.post(url, params=params) as response:
                    data = await response.json()
                    
                    if "access_token" in data:
                        self.access_token = data["access_token"]
                        self.is_connected = True
                        logger.info("Gmail connected")
                        return True
                    else:
                        logger.error(f"Gmail authentication failed: {data.get('error')}")
                        return False
                        
        except Exception as e:
            logger.error(f"Gmail connection error: {e}")
            return False
    
    async def get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    async def receive_emails(self, limit: int = 10, unread_only: bool = False) -> List[IncomingMessage]:
        """
        Receive recent emails
        
        Args:
            limit: Number of emails to fetch
            unread_only: Only fetch unread emails
        
        Returns:
            List of incoming email messages
        """
        if not self.is_connected:
            logger.error("Email engine not connected")
            return []
        
        try:
            if self.provider == EmailProvider.OUTLOOK:
                return await self._receive_outlook_emails(limit, unread_only)
            else:
                return await self._receive_gmail_emails(limit, unread_only)
        except Exception as e:
            logger.error(f"Error receiving emails: {e}")
            return []
    
    async def _receive_outlook_emails(self, limit: int, unread_only: bool) -> List[IncomingMessage]:
        """Receive emails from Outlook"""
        try:
            url = f"{self.graph_endpoint}/me/mailFolders/inbox/messages"
            headers = await self.get_headers()
            params = {
                "$top": limit,
                "$orderby": "receivedDateTime desc"
            }
            
            if unread_only:
                params["$filter"] = "isRead eq false"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        messages = []
                        
                        for msg in data.get("value", []):
                            incoming = self._parse_outlook_email(msg)
                            if incoming:
                                messages.append(incoming)
                        
                        logger.info(f"Received {len(messages)} emails from Outlook")
                        return messages
                    else:
                        logger.error(f"Failed to fetch emails: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error receiving Outlook emails: {e}")
            return []
    
    async def _receive_gmail_emails(self, limit: int, unread_only: bool) -> List[IncomingMessage]:
        """Receive emails from Gmail"""
        try:
            url = f"{self.gmail_endpoint}/users/me/messages"
            headers = await self.get_headers()
            params = {
                "maxResults": limit,
                "q": "is:inbox" + (" is:unread" if unread_only else "")
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        messages = []
                        
                        for msg in data.get("messages", []):
                            # Fetch full message
                            full_msg = await self._fetch_gmail_message(msg.get("id"))
                            if full_msg:
                                incoming = self._parse_gmail_email(full_msg)
                                if incoming:
                                    messages.append(incoming)
                        
                        logger.info(f"Received {len(messages)} emails from Gmail")
                        return messages
                    else:
                        logger.error(f"Failed to fetch emails: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Error receiving Gmail emails: {e}")
            return []
    
    async def _fetch_gmail_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full Gmail message"""
        try:
            url = f"{self.gmail_endpoint}/users/me/messages/{message_id}"
            headers = await self.get_headers()
            params = {"format": "full"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        return await response.json()
            return None
        except Exception as e:
            logger.error(f"Error fetching Gmail message: {e}")
            return None
    
    async def send(self, message: OutgoingMessage) -> bool:
        """
        Send email
        
        Args:
            message: Outgoing message (email)
        
        Returns:
            True if sent successfully
        """
        if not self.is_connected:
            logger.error("Email engine not connected")
            return False
        
        try:
            if self.provider == EmailProvider.OUTLOOK:
                return await self._send_outlook_email(message)
            else:
                return await self._send_gmail_email(message)
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
    
    async def _send_outlook_email(self, message: OutgoingMessage) -> bool:
        """Send email via Outlook"""
        try:
            url = f"{self.graph_endpoint}/me/sendMail"
            headers = await self.get_headers()
            
            payload = {
                "message": {
                    "subject": message.metadata.get("subject", "Re:"),
                    "body": {
                        "contentType": "Text",
                        "content": message.content
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": message.recipient
                            }
                        }
                    ]
                }
            }
            
            # If thread_id exists, reply to thread
            if message.thread_id:
                payload["message"]["conversationId"] = message.thread_id
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 202:
                        logger.info(f"Email sent via Outlook to {message.recipient}")
                        return True
                    else:
                        logger.error(f"Failed to send email: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending Outlook email: {e}")
            return False
    
    async def _send_gmail_email(self, message: OutgoingMessage) -> bool:
        """Send email via Gmail"""
        try:
            import base64
            
            url = f"{self.gmail_endpoint}/users/me/messages/send"
            headers = await self.get_headers()
            
            # Build raw email
            email_content = f"Content-Type: text/plain; charset=UTF-8\n"
            email_content += f"To: {message.recipient}\n"
            email_content += f"Subject: {message.metadata.get('subject', 'Re:')}\n\n"
            email_content += message.content
            
            encoded = base64.urlsafe_b64encode(email_content.encode()).decode()
            
            payload = {"raw": encoded}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Email sent via Gmail to {message.recipient}")
                        return True
                    else:
                        logger.error(f"Failed to send email: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Error sending Gmail email: {e}")
            return False
    
    def _parse_outlook_email(self, msg: Dict[str, Any]) -> Optional[IncomingMessage]:
        """Parse Outlook email to IncomingMessage"""
        try:
            from_addr = msg.get("from", {}).get("emailAddress", {})
            subject = msg.get("subject", "")
            
            incoming = IncomingMessage(
                platform=Platform.EMAIL_OUTLOOK,
                message_id=msg.get("id", ""),
                sender=from_addr.get("address", ""),
                content=f"{subject}\n\n{msg.get('body', {}).get('content', '')}",
                timestamp=datetime.fromisoformat(msg.get("receivedDateTime", "").replace("Z", "+00:00")),
                thread_id=msg.get("conversationId"),
                metadata={
                    "subject": subject,
                    "sender_name": from_addr.get("name", ""),
                    "is_read": msg.get("isRead", False),
                    "has_attachments": msg.get("hasAttachments", False)
                }
            )
            
            return incoming
            
        except Exception as e:
            logger.error(f"Error parsing Outlook email: {e}")
            return None
    
    def _parse_gmail_email(self, msg: Dict[str, Any]) -> Optional[IncomingMessage]:
        """Parse Gmail email to IncomingMessage"""
        try:
            import base64
            
            headers = {}
            body = ""
            
            # Parse headers
            for header in msg.get("payload", {}).get("headers", []):
                name = header.get("name", "").lower()
                value = header.get("value", "")
                headers[name] = value
            
            # Parse body
            if "body" in msg.get("payload", {}):
                data = msg["payload"]["body"].get("data")
                if data:
                    body = base64.urlsafe_b64decode(data).decode()
            
            subject = headers.get("subject", "")
            sender = headers.get("from", "")
            
            incoming = IncomingMessage(
                platform=Platform.EMAIL_GMAIL,
                message_id=msg.get("id", ""),
                sender=sender,
                content=f"{subject}\n\n{body}",
                timestamp=datetime.fromtimestamp(int(msg.get("internalDate", 0)) / 1000, tz=timezone.utc),
                thread_id=msg.get("threadId"),
                metadata={
                    "subject": subject,
                    "sender_name": sender,
                    "is_read": "UNREAD" not in msg.get("labelIds", [])
                }
            )
            
            return incoming
            
        except Exception as e:
            logger.error(f"Error parsing Gmail email: {e}")
            return None
    
    async def summarize_thread(self, thread_id: str) -> Optional[str]:
        """
        Summarize an email thread
        
        Args:
            thread_id: Thread ID
        
        Returns:
            Thread summary
        """
        # TODO: Implement thread summarization using LLM
        logger.info(f"Summarizing thread: {thread_id}")
        return None


async def main():
    """Test Email Engine"""
    logger.add("logs/email_engine_{time}.log", rotation="10 MB")
    
    # Test Outlook
    outlook = EmailEngine(
        provider=EmailProvider.OUTLOOK,
        client_id="your_client_id",
        client_secret="your_client_secret",
        tenant_id="your_tenant_id"
    )
    
    # Test Gmail
    gmail = EmailEngine(
        provider=EmailProvider.GMAIL,
        client_id="your_client_id",
        client_secret="your_client_secret",
        refresh_token="your_refresh_token"
    )
    
    logger.info("Email Engine module loaded")


if __name__ == "__main__":
    asyncio.run(main())
