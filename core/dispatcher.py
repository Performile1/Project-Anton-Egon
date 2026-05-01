#!/usr/bin/env python3
"""
Project Anton Egon - Unified Communication Dispatcher
Central hub for all incoming communications (chat, email, video)
Routes through Mood Engine and Knowledge Vault before responding

Phase 13: Unified Communication Hub
Phase 17: Cloud Infrastructure - Supabase CRM integration
"""

import asyncio
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
import os

from loguru import logger

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("Supabase not installed. CRM integration disabled.")


class CommunicationMode(Enum):
    """Communication mode for agent response"""
    AUTONOMOUS = "autonomous"  # Agent responds directly (low risk)
    DRAFT = "draft"  # Agent writes draft, user approves (high risk)
    WHISPER = "whisper"  # Agent notifies user, user decides


class Platform(Enum):
    """Supported communication platforms"""
    TEAMS_CHAT = "teams_chat"
    TEAMS_MEETING = "teams_meeting"
    SLACK = "slack"
    EMAIL_OUTLOOK = "email_outlook"
    EMAIL_GMAIL = "email_gmail"
    MEET_CHAT = "meet_chat"
    ZOOM_CHAT = "zoom_chat"
    DISCORD = "discord"


@dataclass
class IncomingMessage:
    """Incoming message from any platform"""
    platform: Platform
    message_id: str
    sender: str
    content: str
    timestamp: datetime
    channel_id: Optional[str] = None
    thread_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "message_id": self.message_id,
            "sender": self.sender,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "channel_id": self.channel_id,
            "thread_id": self.thread_id,
            "metadata": self.metadata
        }


@dataclass
class OutgoingMessage:
    """Outgoing message to any platform"""
    platform: Platform
    recipient: str
    content: str
    mode: CommunicationMode
    message_id: Optional[str] = None
    channel_id: Optional[str] = None
    thread_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform.value,
            "recipient": self.recipient,
            "content": self.content,
            "mode": self.mode.value,
            "message_id": self.message_id,
            "channel_id": self.channel_id,
            "thread_id": self.thread_id,
            "metadata": self.metadata
        }


class UnifiedDispatcher:
    """
    Central dispatcher for all communications
    Coordinates between platform adapters, Mood Engine, and Knowledge Vault
    Phase 17: Supabase CRM integration for centralized contact and meeting storage
    """
    
    def __init__(self):
        self.adapters: Dict[Platform, Any] = {}
        self.message_queue: List[IncomingMessage] = []
        self.draft_queue: List[OutgoingMessage] = []
        self.mood_engine = None
        self.knowledge_vault = None
        self.default_mode = CommunicationMode.DRAFT  # Safe default
        
        # Supabase CRM client
        self.supabase: Optional[Client] = None
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if SUPABASE_AVAILABLE and self.supabase_url and self.supabase_key:
            try:
                self.supabase = create_client(self.supabase_url, self.supabase_key)
                logger.info("Supabase CRM client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase: {e}")
        
        logger.info("Unified Dispatcher initialized")
    
    def register_adapter(self, platform: Platform, adapter: Any):
        """
        Register a platform adapter
        
        Args:
            platform: Platform enum
            adapter: Adapter instance (must have send() and receive() methods)
        """
        self.adapters[platform] = adapter
        logger.info(f"Registered adapter for {platform.value}")
    
    def set_mood_engine(self, mood_engine):
        """Set the Mood Engine instance"""
        self.mood_engine = mood_engine
        logger.info("Mood Engine linked to Dispatcher")
    
    def set_knowledge_vault(self, vault):
        """Set the Knowledge Vault instance"""
        self.knowledge_vault = vault
        logger.info("Knowledge Vault linked to Dispatcher")
    
    def set_default_mode(self, mode: CommunicationMode):
        """Set default communication mode"""
        self.default_mode = mode
        logger.info(f"Default mode set to {mode.value}")
    
    # ═══════════════════════════════════════════════════════════════
    # SUPABASE CRM METHODS (Phase 17)
    # ═══════════════════════════════════════════════════════════════
    
    async def store_contact(self, contact_data: Dict[str, Any]) -> bool:
        """
        Store contact in Supabase CRM
        
        Args:
            contact_data: Contact data (name, email, platform, etc.)
        
        Returns:
            True if stored successfully
        """
        if not self.supabase:
            logger.warning("Supabase not available")
            return False
        
        try:
            response = self.supabase.table('contacts').upsert(contact_data).execute()
            logger.info(f"Stored contact: {contact_data.get('name', 'Unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to store contact: {e}")
            return False
    
    async def store_meeting_log(self, meeting_data: Dict[str, Any]) -> bool:
        """
        Store meeting log in Supabase CRM
        
        Args:
            meeting_data: Meeting data (platform, participants, summary, etc.)
        
        Returns:
            True if stored successfully
        """
        if not self.supabase:
            logger.warning("Supabase not available")
            return False
        
        try:
            response = self.supabase.table('meetings').insert(meeting_data).execute()
            logger.info(f"Stored meeting log: {meeting_data.get('title', 'Unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to store meeting log: {e}")
            return False
    
    async def store_communication_log(self, log_data: Dict[str, Any]) -> bool:
        """
        Store communication log in Supabase CRM
        
        Args:
            log_data: Communication log (message, platform, timestamp, etc.)
        
        Returns:
            True if stored successfully
        """
        if not self.supabase:
            logger.warning("Supabase not available")
            return False
        
        try:
            response = self.supabase.table('communication_logs').insert(log_data).execute()
            logger.debug(f"Stored communication log")
            return True
        except Exception as e:
            logger.error(f"Failed to store communication log: {e}")
            return False
    
    async def get_contact(self, contact_id: str) -> Optional[Dict[str, Any]]:
        """
        Get contact from Supabase CRM
        
        Args:
            contact_id: Contact ID
        
        Returns:
            Contact data or None
        """
        if not self.supabase:
            return None
        
        try:
            response = self.supabase.table('contacts').select('*').eq('id', contact_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get contact: {e}")
            return None
    
    async def get_contact_by_platform(self, platform: str, platform_id: str) -> Optional[Dict[str, Any]]:
        """
        Get contact by platform identifier
        
        Args:
            platform: Platform name
            platform_id: Platform-specific ID (email, username, etc.)
        
        Returns:
            Contact data or None
        """
        if not self.supabase:
            return None
        
        try:
            response = self.supabase.table('contacts').select('*').eq('platform', platform).eq('platform_id', platform_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to get contact by platform: {e}")
            return None
    
    async def receive_message(self, message: IncomingMessage) -> Optional[OutgoingMessage]:
        """
        Receive and process incoming message
        
        Args:
            message: Incoming message from any platform
        
        Returns:
            Outgoing message (or None if no response needed)
        """
        logger.info(f"Received message from {message.platform.value}: {message.sender}")
        
        # Add to message queue
        self.message_queue.append(message)
        
        # Determine response mode based on content
        mode = self._determine_mode(message)
        
        # Process through Mood Engine
        mood_context = None
        if self.mood_engine:
            mood_context = await self._get_mood_context(message)
        
        # Search Knowledge Vault for relevant context
        vault_context = None
        if self.knowledge_vault:
            vault_context = await self._search_vault(message.content)
        
        # Generate response
        response = await self._generate_response(message, mood_context, vault_context, mode)
        
        if response:
            if mode == CommunicationMode.DRAFT:
                self.draft_queue.append(response)
                logger.info(f"Draft generated for {message.platform.value}")
            elif mode == CommunicationMode.AUTONOMOUS:
                await self.send_message(response)
                logger.info(f"Sent autonomous response to {message.platform.value}")
            elif mode == CommunicationMode.WHISPER:
                logger.info(f"Whisper notification for {message.platform.value}")
                # TODO: Send whisper notification to dashboard
        
        return response
    
    async def send_message(self, message: OutgoingMessage) -> bool:
        """
        Send outgoing message through appropriate adapter
        
        Args:
            message: Outgoing message
        
        Returns:
            True if sent successfully
        """
        adapter = self.adapters.get(message.platform)
        if not adapter:
            logger.error(f"No adapter registered for {message.platform.value}")
            return False
        
        try:
            # Apply Swenglish Buffer if needed
            content = self._apply_swenglish(message.content)
            message.content = content
            
            # Send through adapter
            await adapter.send(message)
            logger.info(f"Message sent to {message.platform.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    def _determine_mode(self, message: IncomingMessage) -> CommunicationMode:
        """
        Determine response mode based on message content
        
        Args:
            message: Incoming message
        
        Returns:
            Communication mode
        """
        content_lower = message.content.lower()
        
        # High-risk keywords -> Draft mode
        high_risk_keywords = [
            'offer', 'quote', 'contract', 'price', 'budget',
            'strategy', 'decision', 'approve', 'legal',
            'offert', 'kontrakt', 'pris', 'budget', 'strategi'
        ]
        
        for keyword in high_risk_keywords:
            if keyword in content_lower:
                return CommunicationMode.DRAFT
        
        # Low-risk keywords -> Autonomous mode
        low_risk_keywords = [
            'meeting', 'time', 'schedule', 'document', 'link',
            'möte', 'tid', 'schema', 'dokument', 'länk'
        ]
        
        for keyword in low_risk_keywords:
            if keyword in content_lower:
                return CommunicationMode.AUTONOMOUS
        
        # Default to draft for safety
        return self.default_mode
    
    async def _get_mood_context(self, message: IncomingMessage) -> Optional[Dict[str, Any]]:
        """
        Get mood context from Mood Engine
        
        Args:
            message: Incoming message
        
        Returns:
            Mood context dictionary
        """
        if not self.mood_engine:
            return None
        
        try:
            # Analyze message for emotional context
            mood = self.mood_engine.analyze_emotion(message.content)
            return {
                "current_mood": mood,
                "suggested_tone": self.mood_engine.get_suggested_tone(mood)
            }
        except Exception as e:
            logger.error(f"Failed to get mood context: {e}")
            return None
    
    async def _search_vault(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """
        Search Knowledge Vault for relevant context
        
        Args:
            query: Search query
        
        Returns:
            List of relevant documents
        """
        if not self.knowledge_vault:
            return None
        
        try:
            results = await self.knowledge_vault.search(query, top_k=3)
            return results
        except Exception as e:
            logger.error(f"Failed to search vault: {e}")
            return None
    
    async def _generate_response(
        self,
        message: IncomingMessage,
        mood_context: Optional[Dict[str, Any]],
        vault_context: Optional[List[Dict[str, Any]]],
        mode: CommunicationMode
    ) -> Optional[OutgoingMessage]:
        """
        Generate response using LLM
        
        Args:
            message: Incoming message
            mood_context: Mood context from Mood Engine
            vault_context: Relevant documents from Knowledge Vault
            mode: Communication mode
        
        Returns:
            Outgoing message (or None)
        """
        try:
            # Build prompt with context
            prompt = self._build_prompt(message, mood_context, vault_context)
            
            # Generate response using LLM
            # TODO: Integrate with core/streaming_pipeline.py or core/decision_engine.py
            # For now, return a placeholder
            response_content = f"[{mode.value.upper()}] Response to: {message.content}"
            
            return OutgoingMessage(
                platform=message.platform,
                recipient=message.sender,
                content=response_content,
                mode=mode,
                channel_id=message.channel_id,
                thread_id=message.thread_id
            )
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            return None
    
    def _build_prompt(
        self,
        message: IncomingMessage,
        mood_context: Optional[Dict[str, Any]],
        vault_context: Optional[List[Dict[str, Any]]]
    ) -> str:
        """Build LLM prompt with context"""
        prompt = f"You are Anton Egon, a professional AI assistant.\n\n"
        prompt += f"Message from {message.sender}: {message.content}\n\n"
        
        if mood_context:
            prompt += f"Current mood: {mood_context.get('current_mood')}\n"
            prompt += f"Suggested tone: {mood_context.get('suggested_tone')}\n\n"
        
        if vault_context:
            prompt += "Relevant context from knowledge vault:\n"
            for doc in vault_context:
                prompt += f"- {doc.get('content', '')[:200]}...\n"
            prompt += "\n"
        
        prompt += "Respond in a professional manner using the Swedish business context with 10-15% English business terms (Swenglish Buffer)."
        
        return prompt
    
    def _apply_swenglish(self, content: str) -> str:
        """
        Apply Swenglish Buffer (already implemented in core/prompts.py)
        
        Args:
            content: Original content
        
        Returns:
            Content with Swenglish applied
        """
        # TODO: Integrate with core/prompts.py swenglish buffer
        return content
    
    def get_message_queue(self) -> List[Dict[str, Any]]:
        """Get all queued messages"""
        return [msg.to_dict() for msg in self.message_queue]
    
    def get_draft_queue(self) -> List[Dict[str, Any]]:
        """Get all pending drafts"""
        return [draft.to_dict() for draft in self.draft_queue]
    
    def approve_draft(self, draft_id: str) -> bool:
        """
        Approve and send a draft
        
        Args:
            draft_id: Draft message ID
        
        Returns:
            True if approved and sent
        """
        # Find draft
        draft = next((d for d in self.draft_queue if d.message_id == draft_id), None)
        if not draft:
            logger.error(f"Draft not found: {draft_id}")
            return False
        
        # Send draft
        success = asyncio.run(self.send_message(draft))
        
        # Remove from queue
        if success:
            self.draft_queue.remove(draft)
        
        return success
    
    def reject_draft(self, draft_id: str) -> bool:
        """
        Reject a draft
        
        Args:
            draft_id: Draft message ID
        
        Returns:
            True if rejected
        """
        draft = next((d for d in self.draft_queue if d.message_id == draft_id), None)
        if not draft:
            logger.error(f"Draft not found: {draft_id}")
            return False
        
        self.draft_queue.remove(draft)
        logger.info(f"Draft rejected: {draft_id}")
        return True


# Singleton instance
dispatcher = UnifiedDispatcher()


async def main():
    """Test Unified Dispatcher"""
    logger.add("logs/dispatcher_{time}.log", rotation="10 MB")
    
    # Create test message
    test_message = IncomingMessage(
        platform=Platform.TEAMS_CHAT,
        message_id="test_001",
        sender="john.doe@example.com",
        content="När har vi möte nästa vecka?",
        timestamp=datetime.now(timezone.utc)
    )
    
    # Process message
    response = await dispatcher.receive_message(test_message)
    
    if response:
        logger.info(f"Response generated: {response.to_dict()}")
    
    logger.info("Unified Dispatcher test complete")


if __name__ == "__main__":
    asyncio.run(main())
