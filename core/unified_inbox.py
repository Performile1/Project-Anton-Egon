#!/usr/bin/env python3
"""
Project Anton Egon - Unified Inbox
Aggregates all incoming communications into a single view

Phase 13: Unified Communication Hub
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from enum import Enum
from dataclasses import dataclass, field

from loguru import logger

from core.dispatcher import IncomingMessage, OutgoingMessage, Platform, CommunicationMode


class InboxFilter(Enum):
    """Filter options for inbox"""
    ALL = "all"
    UNREAD = "unread"
    DRAFTS = "drafts"
    TEAMS = "teams"
    SLACK = "slack"
    EMAIL = "email"
    HIGH_PRIORITY = "high_priority"


class Priority(Enum):
    """Message priority"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class UnifiedMessage:
    """Unified message representation for inbox"""
    original: IncomingMessage
    priority: Priority = Priority.NORMAL
    is_read: bool = False
    is_flagged: bool = False
    tags: List[str] = field(default_factory=list)
    ai_summary: Optional[str] = None
    suggested_action: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.original.platform.value,
            "message_id": self.original.message_id,
            "sender": self.original.sender,
            "content": self.original.content[:500] + "..." if len(self.original.content) > 500 else self.original.content,
            "timestamp": self.original.timestamp.isoformat(),
            "priority": self.priority.name,
            "is_read": self.is_read,
            "is_flagged": self.is_flagged,
            "tags": self.tags,
            "ai_summary": self.ai_summary,
            "suggested_action": self.suggested_action,
            "created_at": self.created_at.isoformat(),
            "metadata": self.original.metadata
        }


class UnifiedInbox:
    """
    Unified Inbox
    Aggregates messages from all platforms into a single view
    """
    
    def __init__(self):
        self.messages: List[UnifiedMessage] = []
        self.dispatcher = None
        self.max_messages = 1000
        self.auto_cleanup_days = 30
        
        logger.info("Unified Inbox initialized")
    
    def set_dispatcher(self, dispatcher):
        """Set the dispatcher instance"""
        self.dispatcher = dispatcher
        logger.info("Dispatcher linked to Unified Inbox")
    
    async def add_message(self, message: IncomingMessage, priority: Priority = Priority.NORMAL):
        """
        Add message to inbox
        
        Args:
            message: Incoming message
            priority: Message priority
        """
        unified = UnifiedMessage(
            original=message,
            priority=priority
        )
        
        # Auto-detect priority based on content
        unified.priority = self._auto_detect_priority(message)
        
        # Generate AI summary
        unified.ai_summary = await self._generate_summary(message)
        
        # Suggest action
        unified.suggested_action = self._suggest_action(message)
        
        # Add to inbox
        self.messages.append(unified)
        
        # Sort by timestamp (newest first)
        self.messages.sort(key=lambda m: m.original.timestamp, reverse=True)
        
        # Cleanup old messages
        await self._cleanup()
        
        logger.info(f"Added message to inbox from {message.platform.value}")
    
    def get_messages(
        self,
        filter: InboxFilter = InboxFilter.ALL,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get messages from inbox
        
        Args:
            filter: Filter option
            limit: Number of messages to return
            offset: Offset for pagination
        
        Returns:
            List of message dictionaries
        """
        filtered = self.messages
        
        # Apply filter
        if filter == InboxFilter.UNREAD:
            filtered = [m for m in filtered if not m.is_read]
        elif filter == InboxFilter.DRAFTS:
            # Get drafts from dispatcher
            if self.dispatcher:
                return self.dispatcher.get_draft_queue()
        elif filter == InboxFilter.TEAMS:
            filtered = [m for m in filtered if m.original.platform == Platform.TEAMS_CHAT]
        elif filter == InboxFilter.SLACK:
            filtered = [m for m in filtered if m.original.platform == Platform.SLACK]
        elif filter == InboxFilter.EMAIL:
            filtered = [m for m in filtered if m.original.platform in [Platform.EMAIL_OUTLOOK, Platform.EMAIL_GMAIL]]
        elif filter == InboxFilter.HIGH_PRIORITY:
            filtered = [m for m in filtered if m.priority in [Priority.HIGH, Priority.URGENT]]
        
        # Apply pagination
        filtered = filtered[offset:offset + limit]
        
        return [m.to_dict() for m in filtered]
    
    def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific message by ID
        
        Args:
            message_id: Message ID
        
        Returns:
            Message dictionary or None
        """
        for msg in self.messages:
            if msg.original.message_id == message_id:
                return msg.to_dict()
        return None
    
    def mark_as_read(self, message_id: str) -> bool:
        """
        Mark message as read
        
        Args:
            message_id: Message ID
        
        Returns:
            True if marked successfully
        """
        for msg in self.messages:
            if msg.original.message_id == message_id:
                msg.is_read = True
                logger.info(f"Marked message as read: {message_id}")
                return True
        return False
    
    def mark_as_unread(self, message_id: str) -> bool:
        """
        Mark message as unread
        
        Args:
            message_id: Message ID
        
        Returns:
            True if marked successfully
        """
        for msg in self.messages:
            if msg.original.message_id == message_id:
                msg.is_read = False
                logger.info(f"Marked message as unread: {message_id}")
                return True
        return False
    
    def flag_message(self, message_id: str) -> bool:
        """
        Flag message for follow-up
        
        Args:
            message_id: Message ID
        
        Returns:
            True if flagged successfully
        """
        for msg in self.messages:
            if msg.original.message_id == message_id:
                msg.is_flagged = True
                logger.info(f"Flagged message: {message_id}")
                return True
        return False
    
    def unflag_message(self, message_id: str) -> bool:
        """
        Unflag message
        
        Args:
            message_id: Message ID
        
        Returns:
            True if unflagged successfully
        """
        for msg in self.messages:
            if msg.original.message_id == message_id:
                msg.is_flagged = False
                logger.info(f"Unflagged message: {message_id}")
                return True
        return False
    
    def add_tag(self, message_id: str, tag: str) -> bool:
        """
        Add tag to message
        
        Args:
            message_id: Message ID
            tag: Tag to add
        
        Returns:
            True if tag added successfully
        """
        for msg in self.messages:
            if msg.original.message_id == message_id:
                if tag not in msg.tags:
                    msg.tags.append(tag)
                logger.info(f"Added tag '{tag}' to message: {message_id}")
                return True
        return False
    
    def remove_tag(self, message_id: str, tag: str) -> bool:
        """
        Remove tag from message
        
        Args:
            message_id: Message ID
            tag: Tag to remove
        
        Returns:
            True if tag removed successfully
        """
        for msg in self.messages:
            if msg.original.message_id == message_id:
                if tag in msg.tags:
                    msg.tags.remove(tag)
                logger.info(f"Removed tag '{tag}' from message: {message_id}")
                return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get inbox statistics
        
        Returns:
            Statistics dictionary
        """
        total = len(self.messages)
        unread = len([m for m in self.messages if not m.is_read])
        flagged = len([m for m in self.messages if m.is_flagged])
        drafts = len(self.dispatcher.draft_queue) if self.dispatcher else 0
        
        # Count by platform
        platform_counts = {}
        for msg in self.messages:
            platform = msg.original.platform.value
            platform_counts[platform] = platform_counts.get(platform, 0) + 1
        
        return {
            "total_messages": total,
            "unread_messages": unread,
            "flagged_messages": flagged,
            "pending_drafts": drafts,
            "platform_counts": platform_counts,
            "oldest_message": self.messages[-1].original.timestamp.isoformat() if self.messages else None,
            "newest_message": self.messages[0].original.timestamp.isoformat() if self.messages else None
        }
    
    def _auto_detect_priority(self, message: IncomingMessage) -> Priority:
        """
        Auto-detect message priority based on content
        
        Args:
            message: Incoming message
        
        Returns:
            Priority level
        """
        content_lower = message.content.lower()
        
        # Urgent keywords
        urgent_keywords = [
            'urgent', 'asap', 'emergency', 'critical',
            'akut', 'bråttom', 'nödläge'
        ]
        
        for keyword in urgent_keywords:
            if keyword in content_lower:
                return Priority.URGENT
        
        # High priority keywords
        high_keywords = [
            'important', 'priority', 'deadline', 'contract',
            'viktigt', 'prioritet', 'deadline', 'kontrakt'
        ]
        
        for keyword in high_keywords:
            if keyword in content_lower:
                return Priority.HIGH
        
        # Default to normal
        return Priority.NORMAL
    
    async def _generate_summary(self, message: IncomingMessage) -> Optional[str]:
        """
        Generate AI summary of message
        
        Args:
            message: Incoming message
        
        Returns:
            Summary string
        """
        try:
            # TODO: Integrate with LLM for summarization
            # For now, return a simple truncation
            if len(message.content) > 200:
                return message.content[:200] + "..."
            return message.content
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return None
    
    def _suggest_action(self, message: IncomingMessage) -> Optional[str]:
        """
        Suggest action for message
        
        Args:
            message: Incoming message
        
        Returns:
            Suggested action string
        """
        content_lower = message.content.lower()
        
        # Suggest reply for questions
        if '?' in message.content:
            return "reply"
        
        # Suggest acknowledge for mentions
        if '@' in message.content or 'tagged' in content_lower:
            return "acknowledge"
        
        # Suggest schedule for meeting requests
        if 'meeting' in content_lower or 'möte' in content_lower:
            return "schedule"
        
        # Suggest review for documents
        if 'document' in content_lower or 'dokument' in content_lower:
            return "review"
        
        return None
    
    async def _cleanup(self):
        """Cleanup old messages"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.auto_cleanup_days)
        
        # Remove messages older than cutoff (excluding flagged ones)
        self.messages = [
            m for m in self.messages
            if m.original.timestamp > cutoff or m.is_flagged
        ]
        
        # Limit total messages
        if len(self.messages) > self.max_messages:
            # Keep newest messages and flagged ones
            flagged = [m for m in self.messages if m.is_flagged]
            unflagged = [m for m in self.messages if not m.is_flagged]
            unflagged = unflagged[:self.max_messages - len(flagged)]
            self.messages = flagged + unflagged
        
        logger.debug(f"Inbox cleanup complete: {len(self.messages)} messages")


# Singleton instance
unified_inbox = UnifiedInbox()


async def main():
    """Test Unified Inbox"""
    logger.add("logs/unified_inbox_{time}.log", rotation="10 MB")
    
    # Create test message
    test_message = IncomingMessage(
        platform=Platform.TEAMS_CHAT,
        message_id="test_001",
        sender="john.doe@example.com",
        content="Urgent: Need approval for budget by Friday",
        timestamp=datetime.now(timezone.utc)
    )
    
    # Add to inbox
    await unified_inbox.add_message(test_message)
    
    # Get stats
    stats = unified_inbox.get_stats()
    logger.info(f"Inbox stats: {stats}")
    
    # Get messages
    messages = unified_inbox.get_messages()
    logger.info(f"Messages: {len(messages)}")
    
    logger.info("Unified Inbox test complete")


if __name__ == "__main__":
    asyncio.run(main())
