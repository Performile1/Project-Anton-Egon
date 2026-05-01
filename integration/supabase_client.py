#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Sprint 4: Supabase Client
Database connection and CRUD operations for Supabase
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import json

# Try to import supabase client
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

from loguru import logger


class SupabaseConfig:
    """Supabase configuration"""
    URL = os.getenv("SUPABASE_URL", "")
    SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


class SupabaseClient:
    """
    Supabase database client
    Handles authentication and CRUD operations
    """
    
    def __init__(self, url: str = None, service_role_key: str = None):
        """
        Initialize Supabase client
        
        Args:
            url: Supabase URL (default: from env)
            service_role_key: Service role key (default: from env)
        """
        self.url = url or SupabaseConfig.URL
        self.service_role_key = service_role_key or SupabaseConfig.SERVICE_ROLE_KEY
        self.client: Optional[Client] = None
        self.connected = False
        
        if not SUPABASE_AVAILABLE:
            logger.warning("Supabase library not available - using mock mode")
            return
        
        if not self.url or not self.service_role_key:
            logger.warning("Supabase credentials not provided - using mock mode")
            return
        
        # Initialize client
        self._init_client()
    
    def _init_client(self):
        """Initialize Supabase client"""
        try:
            self.client = create_client(self.url, self.service_role_key)
            self.connected = True
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            self.connected = False
    
    # ═══════════════════════════════════════════════════════════════
    # PEOPLE CRM OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    async def get_people(self) -> List[Dict[str, Any]]:
        """
        Get all people from CRM
        
        Returns:
            List of people profiles
        """
        if not self.connected:
            logger.warning("Supabase not connected - returning empty list")
            return []
        
        try:
            response = self.client.table("people").select("*").execute()
            return response.data
        except Exception as e:
            logger.error(f"Error fetching people: {e}")
            return []
    
    async def get_person_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get person by email
        
        Args:
            email: Email address
        
        Returns:
            Person profile or None
        """
        if not self.connected:
            return None
        
        try:
            response = self.client.table("people").select("*").eq("email", email).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching person by email: {e}")
            return None
    
    async def create_person(self, person_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create new person in CRM
        
        Args:
            person_data: Person data (name, email, company, face_fingerprint, etc.)
        
        Returns:
            Created person or None
        """
        if not self.connected:
            logger.warning("Supabase not connected - cannot create person")
            return None
        
        try:
            # Add timestamp
            person_data["created_at"] = datetime.now(timezone.utc).isoformat()
            person_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            response = self.client.table("people").insert(person_data).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error creating person: {e}")
            return None
    
    async def update_person(self, person_id: str, person_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update person in CRM
        
        Args:
            person_id: Person UUID
            person_data: Updated person data
        
        Returns:
            Updated person or None
        """
        if not self.connected:
            return None
        
        try:
            # Add timestamp
            person_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            response = self.client.table("people").update(person_data).eq("id", person_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error updating person: {e}")
            return None
    
    # ═══════════════════════════════════════════════════════════════
    # MEETING LOGS OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    async def create_meeting_log(self, meeting_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create meeting log
        
        Args:
            meeting_data: Meeting data (platform, meeting_id, title, participants, etc.)
        
        Returns:
            Created meeting log or None
        """
        if not self.connected:
            return None
        
        try:
            # Add timestamp
            meeting_data["created_at"] = datetime.now(timezone.utc).isoformat()
            
            response = self.client.table("meeting_logs").insert(meeting_data).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error creating meeting log: {e}")
            return None
    
    async def update_meeting_log(self, meeting_id: str, meeting_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update meeting log
        
        Args:
            meeting_id: Meeting UUID
            meeting_data: Updated meeting data
        
        Returns:
            Updated meeting log or None
        """
        if not self.connected:
            return None
        
        try:
            response = self.client.table("meeting_logs").update(meeting_data).eq("id", meeting_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error updating meeting log: {e}")
            return None
    
    async def get_meeting_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get meeting logs
        
        Args:
            limit: Maximum number of logs to return
        
        Returns:
            List of meeting logs
        """
        if not self.connected:
            return []
        
        try:
            response = self.client.table("meeting_logs").select("*").limit(limit).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error fetching meeting logs: {e}")
            return []
    
    # ═══════════════════════════════════════════════════════════════
    # INBOX MESSAGES OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    async def get_inbox_messages(self, platform: str = None, unread_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get inbox messages
        
        Args:
            platform: Filter by platform (optional)
            unread_only: Only return unread messages
        
        Returns:
            List of inbox messages
        """
        if not self.connected:
            return []
        
        try:
            query = self.client.table("inbox_messages").select("*")
            
            if platform:
                query = query.eq("platform", platform)
            
            if unread_only:
                query = query.eq("is_read", False)
            
            response = query.execute()
            return response.data
        except Exception as e:
            logger.error(f"Error fetching inbox messages: {e}")
            return []
    
    async def create_inbox_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create inbox message
        
        Args:
            message_data: Message data (platform, message_id, sender, subject, body, etc.)
        
        Returns:
            Created message or None
        """
        if not self.connected:
            return None
        
        try:
            # Add timestamp
            message_data["created_at"] = datetime.now(timezone.utc).isoformat()
            
            response = self.client.table("inbox_messages").insert(message_data).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error creating inbox message: {e}")
            return None
    
    async def mark_message_read(self, message_id: str) -> bool:
        """
        Mark message as read
        
        Args:
            message_id: Message UUID
        
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        try:
            self.client.table("inbox_messages").update({"is_read": True}).eq("id", message_id).execute()
            return True
        except Exception as e:
            logger.error(f"Error marking message as read: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════
    # PHRASE LIBRARY OPERATIONS
    # ═══════════════════════════════════════════════════════════════
    async def get_phrases(self, category: str = None) -> List[Dict[str, Any]]:
        """
        Get phrases from library
        
        Args:
            category: Filter by category (optional)
        
        Returns:
            List of phrases
        """
        if not self.connected:
            return []
        
        try:
            query = self.client.table("phrase_library").select("*")
            
            if category:
                query = query.eq("category", category)
            
            response = query.execute()
            return response.data
        except Exception as e:
            logger.error(f"Error fetching phrases: {e}")
            return []
    
    async def create_phrase(self, phrase_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create phrase in library
        
        Args:
            phrase_data: Phrase data (phrase, category, etc.)
        
        Returns:
            Created phrase or None
        """
        if not self.connected:
            return None
        
        try:
            # Add timestamp
            phrase_data["created_at"] = datetime.now(timezone.utc).isoformat()
            phrase_data["usage_count"] = 0
            
            response = self.client.table("phrase_library").insert(phrase_data).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logger.error(f"Error creating phrase: {e}")
            return None
    
    async def increment_phrase_usage(self, phrase_id: str) -> bool:
        """
        Increment phrase usage count
        
        Args:
            phrase_id: Phrase UUID
        
        Returns:
            True if successful
        """
        if not self.connected:
            return False
        
        try:
            # Get current count
            response = self.client.table("phrase_library").select("usage_count").eq("id", phrase_id).execute()
            if response.data:
                current_count = response.data[0].get("usage_count", 0)
                self.client.table("phrase_library").update({
                    "usage_count": current_count + 1,
                    "last_used": datetime.now(timezone.utc).isoformat()
                }).eq("id", phrase_id).execute()
                return True
            return False
        except Exception as e:
            logger.error(f"Error incrementing phrase usage: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self.connected
    
    def get_status(self) -> Dict[str, Any]:
        """Get client status"""
        return {
            "connected": self.connected,
            "url": self.url[:20] + "..." if self.url else "Not set",
            "has_credentials": bool(self.service_role_key),
            "mock_mode": not SUPABASE_AVAILABLE or not self.connected
        }


# Singleton instance
supabase_client = SupabaseClient()
