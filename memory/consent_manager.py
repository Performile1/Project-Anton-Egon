#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Phase 6.2: Consent Manager
Manages consent for meeting recording and data processing
"""

import sys
import json
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class ConsentStatus(Enum):
    """Consent status"""
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"


class ConsentRequest(BaseModel):
    """Consent request data structure"""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    meeting_id: str = Field(..., description="Meeting ID")
    platform: str = Field(..., description="Platform name")
    requested_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: ConsentStatus = Field(default=ConsentStatus.PENDING, description="Consent status")
    requested_by: Optional[str] = Field(None, description="User who requested consent")
    responded_at: Optional[str] = Field(None, description="When consent was responded to")
    responded_by: Optional[str] = Field(None, description="User who responded")


class ConsentManagerConfig(BaseModel):
    """Configuration for Consent Manager"""
    consent_dir: str = Field(default="memory/consent", description="Directory for consent records")
    auto_request: bool = Field(default=True, description="Auto-request consent on meeting start")
    consent_message_template: str = Field(
        default="Hej! Jag är Antons assistent (Anton Egon). Jag tar anteckningar och sammanfattar beslut under detta möte. Är det okej för alla att jag spelar in för referens?",
        description="Message template for consent request"
    )


class ConsentManager:
    """
    Consent Manager for meeting recording
    Manages consent requests and status tracking
    """
    
    def __init__(self, config: ConsentManagerConfig):
        """
        Initialize Consent Manager
        
        Args:
            config: Consent Manager configuration
        """
        self.config = config
        
        # Directory structure
        self.consent_dir = Path(config.consent_dir)
        self.consent_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache
        self.requests: Dict[str, ConsentRequest] = {}
        
        # Load existing requests
        self._load_requests()
        
        logger.info("Consent Manager initialized")
    
    def _load_requests(self):
        """Load all consent requests from disk"""
        request_files = list(self.consent_dir.glob("*.json"))
        
        for request_file in request_files:
            try:
                with open(request_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                request = ConsentRequest(**data)
                self.requests[request.request_id] = request
                
            except Exception as e:
                logger.error(f"Failed to load consent request {request_file.name}: {e}")
        
        logger.info(f"Loaded {len(self.requests)} consent requests from disk")
    
    def request_consent(self, meeting_id: str, platform: str, requested_by: Optional[str] = None) -> ConsentRequest:
        """
        Request consent for meeting recording
        
        Args:
            meeting_id: Meeting ID
            platform: Platform name
            requested_by: User who requested consent
        
        Returns:
            Consent request
        """
        request = ConsentRequest(
            meeting_id=meeting_id,
            platform=platform,
            requested_by=requested_by
        )
        
        # Save request
        self._save_request(request)
        
        # Add to cache
        self.requests[request.request_id] = request
        
        logger.info(f"Requested consent for meeting: {meeting_id}")
        
        return request
    
    def grant_consent(self, request_id: str, responded_by: str) -> Optional[ConsentRequest]:
        """
        Grant consent
        
        Args:
            request_id: Request ID
            responded_by: User who granted consent
        
        Returns:
            Updated request or None
        """
        if request_id not in self.requests:
            logger.error(f"Request not found: {request_id}")
            return None
        
        request = self.requests[request_id]
        request.status = ConsentStatus.GRANTED
        request.responded_at = datetime.now(timezone.utc).isoformat()
        request.responded_by = responded_by
        
        # Save request
        self._save_request(request)
        
        logger.info(f"Consent granted for request: {request_id}")
        
        return request
    
    def deny_consent(self, request_id: str, responded_by: str) -> Optional[ConsentRequest]:
        """
        Deny consent
        
        Args:
            request_id: Request ID
            responded_by: User who denied consent
        
        Returns:
            Updated request or None
        """
        if request_id not in self.requests:
            logger.error(f"Request not found: {request_id}")
            return None
        
        request = self.requests[request_id]
        request.status = ConsentStatus.DENIED
        request.responded_at = datetime.now(timezone.utc).isoformat()
        request.responded_by = responded_by
        
        # Save request
        self._save_request(request)
        
        logger.info(f"Consent denied for request: {request_id}")
        
        return request
    
    def revoke_consent(self, request_id: str) -> Optional[ConsentRequest]:
        """
        Revoke previously granted consent
        
        Args:
            request_id: Request ID
        
        Returns:
            Updated request or None
        """
        if request_id not in self.requests:
            logger.error(f"Request not found: {request_id}")
            return None
        
        request = self.requests[request_id]
        request.status = ConsentStatus.REVOKED
        request.responded_at = datetime.now(timezone.utc).isoformat()
        
        # Save request
        self._save_request(request)
        
        logger.info(f"Consent revoked for request: {request_id}")
        
        return request
    
    def check_consent(self, meeting_id: str) -> ConsentStatus:
        """
        Check consent status for a meeting
        
        Args:
            meeting_id: Meeting ID
        
        Returns:
            Consent status
        """
        # Find request for meeting
        for request in self.requests.values():
            if request.meeting_id == meeting_id:
                return request.status
        
        return ConsentStatus.PENDING
    
    def get_request_by_meeting(self, meeting_id: str) -> Optional[ConsentRequest]:
        """
        Get consent request by meeting ID
        
        Args:
            meeting_id: Meeting ID
        
        Returns:
            Consent request or None
        """
        for request in self.requests.values():
            if request.meeting_id == meeting_id:
                return request
        
        return None
    
    def get_pending_requests(self) -> List[ConsentRequest]:
        """
        Get all pending consent requests
        
        Returns:
            List of pending requests
        """
        return [r for r in self.requests.values() if r.status == ConsentStatus.PENDING]
    
    def get_granted_requests(self) -> List[ConsentRequest]:
        """
        Get all granted consent requests
        
        Returns:
            List of granted requests
        """
        return [r for r in self.requests.values() if r.status == ConsentStatus.GRANTED]
    
    def get_all_requests(self) -> List[ConsentRequest]:
        """
        Get all consent requests
        
        Returns:
            List of all requests
        """
        return list(self.requests.values())
    
    def _save_request(self, request: ConsentRequest):
        """
        Save consent request to disk
        
        Args:
            request: Request to save
        """
        request_file = self.consent_dir / f"{request.request_id}.json"
        
        with open(request_file, 'w', encoding='utf-8') as f:
            json.dump(request.dict(), f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved consent request: {request.request_id}")
    
    def get_consent_message(self, meeting_id: str) -> str:
        """
        Get consent message for a meeting
        
        Args:
            meeting_id: Meeting ID
        
        Returns:
            Consent message
        """
        return self.config.consent_message_template
    
    def delete_request(self, request_id: str):
        """
        Delete consent request
        
        Args:
            request_id: Request ID
        """
        if request_id not in self.requests:
            logger.error(f"Request not found: {request_id}")
            return
        
        # Delete file
        request_file = self.consent_dir / f"{request_id}.json"
        if request_file.exists():
            request_file.unlink()
        
        # Remove from cache
        del self.requests[request_id]
        
        logger.info(f"Deleted consent request: {request_id}")
    
    def cleanup_old_requests(self, days: int = 30):
        """
        Delete requests older than specified days
        
        Args:
            days: Number of days to keep
        """
        cutoff_date = datetime.now(timezone.utc) - timezone.timedelta(days=days)
        deleted_count = 0
        
        for request_id, request in list(self.requests.items()):
            requested_at = datetime.fromisoformat(request.requested_at)
            if requested_at < cutoff_date:
                self.delete_request(request_id)
                deleted_count += 1
        
        logger.info(f"Cleanup complete: {deleted_count} requests deleted")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get manager status
        
        Returns:
            Status dictionary
        """
        total = len(self.requests)
        pending = len([r for r in self.requests.values() if r.status == ConsentStatus.PENDING])
        granted = len([r for r in self.requests.values() if r.status == ConsentStatus.GRANTED])
        denied = len([r for r in self.requests.values() if r.status == ConsentStatus.DENIED])
        revoked = len([r for r in self.requests.values() if r.status == ConsentStatus.REVOKED])
        
        return {
            "total_requests": total,
            "pending": pending,
            "granted": granted,
            "denied": denied,
            "revoked": revoked,
            "consent_dir": str(self.consent_dir)
        }


def main():
    """Test the Consent Manager"""
    from loguru import logger
    
    logger.add("logs/consent_manager_{time}.log", rotation="10 MB")
    
    # Create manager
    config = ConsentManagerConfig()
    manager = ConsentManager(config)
    
    # Test: Request consent
    request = manager.request_consent("meeting_001", "teams", "user_1")
    logger.info(f"Requested consent: {request.request_id}")
    
    # Test: Check consent
    status = manager.check_consent("meeting_001")
    logger.info(f"Consent status: {status.value}")
    
    # Test: Grant consent
    manager.grant_consent(request.request_id, "user_2")
    
    # Test: Check consent again
    status = manager.check_consent("meeting_001")
    logger.info(f"Consent status after grant: {status.value}")
    
    # Test: Get pending requests
    pending = manager.get_pending_requests()
    logger.info(f"Pending requests: {len(pending)}")
    
    # Test: Get status
    status = manager.get_status()
    logger.info(f"Manager status: {status}")
    
    logger.info("Consent Manager test complete")


if __name__ == "__main__":
    main()
