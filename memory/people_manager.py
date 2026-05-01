#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Phase 6.1: People CRM
Manages person profiles with face fingerprints, sentiment profiles, key preferences, and history links
"""

import sys
import json
import uuid
import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

from loguru import logger
from pydantic import BaseModel, Field

# Sprint 4: Supabase integration
try:
    from integration.supabase_client import supabase_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class PersonProfile(BaseModel):
    """Person profile data structure"""
    person_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    person_name: str = Field(..., description="Person's name")
    face_id: Optional[str] = Field(None, description="Face fingerprint ID (128-d vector hash)")
    company: Optional[str] = Field(None, description="Company name")
    last_interaction: Optional[str] = Field(None, description="Last interaction date (ISO format)")
    key_points: List[str] = Field(default_factory=list, description="Key points about the person")
    mood_history: Optional[str] = Field(None, description="Mood history summary")
    platform_links: Dict[str, str] = Field(default_factory=dict, description="Platform-specific identifiers")
    meeting_count: int = Field(default=0, description="Number of meetings with this person")
    sentiment_avg: float = Field(default=0.5, description="Average sentiment score (0-1)")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# Sprint 4: Group Profile for multi-user meeting rooms
class GroupProfile(BaseModel):
    """Group profile for conference rooms (multiple face IDs)"""
    group_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    group_name: str = Field(..., description="Group/Room name")
    face_ids: List[str] = Field(default_factory=list, description="List of face IDs in this group")
    meeting_id: Optional[str] = Field(None, description="Associated meeting ID")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PeopleManagerConfig(BaseModel):
    """Configuration for People Manager"""
    people_dir: str = Field(default="memory/people", description="Directory for person profiles")
    face_threshold: float = Field(default=0.6, description="Face recognition threshold (0-1)")
    max_profiles: int = Field(default=1000, description="Maximum number of profiles to store")
    auto_save: bool = Field(default=True, description="Auto-save profiles after updates")


class PeopleManager:
    """
    People CRM Manager
    Manages person profiles with face fingerprints and cross-platform links
    """
    
    def __init__(self, config: PeopleManagerConfig):
        """
        Initialize People Manager
        
        Args:
            config: People Manager configuration
        """
        self.config = config
        
        # Directory structure
        self.people_dir = Path(config.people_dir)
        self.people_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache
        self.profiles: Dict[str, PersonProfile] = {}
        self.face_index: Dict[str, str] = {}  # face_id -> person_id
        self.name_index: Dict[str, str] = {}  # normalized_name -> person_id
        
        # Sprint 4: Group profiles cache
        self.group_profiles: Dict[str, GroupProfile] = {}  # group_id -> GroupProfile
        self.meeting_group_index: Dict[str, str] = {}  # meeting_id -> group_id
        
        # Load existing profiles
        self._load_profiles()
        
        # Sprint 4: Load from Supabase if available
        if SUPABASE_AVAILABLE and supabase_client.is_connected():
            self._sync_from_supabase()
        
        logger.info(f"People Manager initialized ({len(self.profiles)} profiles loaded)")
    
    def _load_profiles(self):
        """Load all profiles from disk"""
        profile_files = list(self.people_dir.glob("*.json"))
        
        for profile_file in profile_files:
            try:
                with open(profile_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                profile = PersonProfile(**data)
                self.profiles[profile.person_id] = profile
                
                # Build indexes
                if profile.face_id:
                    self.face_index[profile.face_id] = profile.person_id
                
                # Name index (normalized for fuzzy search)
                normalized_name = self._normalize_name(profile.person_name)
                self.name_index[normalized_name] = profile.person_id
                
            except Exception as e:
                logger.error(f"Failed to load profile {profile_file.name}: {e}")
        
        logger.info(f"Loaded {len(self.profiles)} profiles from disk")
    
    # ═══════════════════════════════════════════════════════════════
    # SPRINT 4: SUPABASE SYNC
    # ═══════════════════════════════════════════════════════════════
    async def _sync_from_supabase(self):
        """Sync profiles from Supabase to local cache"""
        if not SUPABASE_AVAILABLE or not supabase_client.is_connected():
            return
        
        try:
            # Fetch all people from Supabase
            people = await supabase_client.get_people()
            
            for person in people:
                # Convert Supabase format to PersonProfile
                profile = PersonProfile(
                    person_id=person.get("id", str(uuid.uuid4())),
                    person_name=person.get("name", "Unknown"),
                    face_id=person.get("face_fingerprint"),
                    company=person.get("company"),
                    last_interaction=person.get("last_interaction"),
                    key_points=person.get("notes", "").split("\n") if person.get("notes") else [],
                    meeting_count=0,
                    sentiment_avg=0.5,
                    created_at=person.get("created_at", datetime.now(timezone.utc).isoformat()),
                    updated_at=person.get("updated_at", datetime.now(timezone.utc).isoformat())
                )
                
                # Add to cache
                self.profiles[profile.person_id] = profile
                if profile.face_id:
                    self.face_index[profile.face_id] = profile.person_id
            
            logger.info(f"Synced {len(people)} profiles from Supabase")
        except Exception as e:
            logger.error(f"Supabase sync error: {e}")
    
    async def sync_to_supabase(self, person_id: str) -> bool:
        """
        Sync a profile to Supabase
        
        Args:
            person_id: Person ID to sync
        
        Returns:
            True if successful
        """
        if not SUPABASE_AVAILABLE or not supabase_client.is_connected():
            return False
        
        try:
            profile = self.profiles.get(person_id)
            if not profile:
                return False
            
            # Convert to Supabase format
            person_data = {
                "name": profile.person_name,
                "email": profile.platform_links.get("email", ""),
                "phone": profile.platform_links.get("phone", ""),
                "company": profile.company,
                "face_fingerprint": profile.face_id,
                "notes": "\n".join(profile.key_points),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Check if person exists in Supabase
            existing = await supabase_client.get_person_by_email(person_data["email"])
            
            if existing:
                # Update existing
                await supabase_client.update_person(existing["id"], person_data)
            else:
                # Create new
                await supabase_client.create_person(person_data)
            
            return True
        except Exception as e:
            logger.error(f"Error syncing to Supabase: {e}")
            return False
    
    # ═══════════════════════════════════════════════════════════════
    # SPRINT 4: GROUP PROFILE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    def create_group_profile(self, group_name: str, face_ids: List[str], meeting_id: str = None) -> GroupProfile:
        """
        Create a group profile for a meeting room
        
        Args:
            group_name: Group/Room name
            face_ids: List of face IDs in this group
            meeting_id: Associated meeting ID (optional)
        
        Returns:
            Created group profile
        """
        group = GroupProfile(
            group_name=group_name,
            face_ids=face_ids,
            meeting_id=meeting_id
        )
        
        self.group_profiles[group.group_id] = group
        
        if meeting_id:
            self.meeting_group_index[meeting_id] = group.group_id
        
        logger.info(f"Created group profile: {group_name} with {len(face_ids)} faces")
        return group
    
    def get_group_by_meeting(self, meeting_id: str) -> Optional[GroupProfile]:
        """
        Get group profile by meeting ID
        
        Args:
            meeting_id: Meeting ID
        
        Returns:
            Group profile or None
        """
        group_id = self.meeting_group_index.get(meeting_id)
        if group_id:
            return self.group_profiles.get(group_id)
        return None
    
    def add_face_to_group(self, group_id: str, face_id: str) -> bool:
        """
        Add a face ID to a group
        
        Args:
            group_id: Group ID
            face_id: Face ID to add
        
        Returns:
            True if successful
        """
        group = self.group_profiles.get(group_id)
        if group:
            if face_id not in group.face_ids:
                group.face_ids.append(face_id)
                group.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        return False
    
    def _normalize_name(self, name: str) -> str:
        """
        Normalize name for fuzzy matching
        
        Args:
            name: Person name
        
        Returns:
            Normalized name (lowercase, no special chars)
        """
        return name.lower().replace(" ", "").replace("-", "").replace(".", "")
    
    def _generate_face_id(self, face_vector: np.ndarray) -> str:
        """
        Generate face ID from face vector
        
        Args:
            face_vector: 128-d face vector
        
        Returns:
            Face ID (hash of vector)
        """
        # Use hash of vector as ID
        vector_bytes = face_vector.tobytes()
        vector_hash = hash(vector_bytes)
        return f"face_{abs(vector_hash)}"
    
    def _calculate_similarity(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two face vectors
        
        Args:
            vector1: First face vector
            vector2: Second face vector
        
        Returns:
            Similarity score (0-1)
        """
        # Cosine similarity
        dot_product = np.dot(vector1, vector2)
        norm1 = np.linalg.norm(vector1)
        norm2 = np.linalg.norm(vector2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
    
    def create_profile(
        self,
        face_vector: np.ndarray,
        name: str,
        company: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> PersonProfile:
        """
        Create new person profile
        
        Args:
            face_vector: 128-d face vector from DeepFace
            name: Person's name
            company: Company name (optional)
            metadata: Additional metadata
        
        Returns:
            Created profile
        """
        # Check if profile already exists
        existing_profile = self.identify_person(face_vector)
        if existing_profile:
            logger.warning(f"Person already exists: {existing_profile.person_name}")
            return existing_profile
        
        # Generate face ID
        face_id = self._generate_face_id(face_vector)
        
        # Create profile
        profile = PersonProfile(
            person_name=name,
            face_id=face_id,
            company=company,
            key_points=metadata.get("key_points", []) if metadata else [],
            mood_history=metadata.get("mood_history") if metadata else None,
            platform_links=metadata.get("platform_links", {}) if metadata else {}
        )
        
        # Save profile
        self._save_profile(profile)
        
        # Update indexes
        self.profiles[profile.person_id] = profile
        self.face_index[face_id] = profile.person_id
        normalized_name = self._normalize_name(name)
        self.name_index[normalized_name] = profile.person_id
        
        logger.info(f"Created profile for: {name}")
        
        return profile
    
    def identify_person(self, face_vector: np.ndarray, threshold: Optional[float] = None) -> Optional[PersonProfile]:
        """
        Identify person from face vector
        
        Args:
            face_vector: 128-d face vector
            threshold: Recognition threshold (default: config.face_threshold)
        
        Returns:
            Identified profile or None
        """
        if threshold is None:
            threshold = self.config.face_threshold
        
        best_match = None
        best_similarity = 0.0
        
        for person_id, profile in self.profiles.items():
            if profile.face_id:
                # Load profile to get face vector
                face_vector_stored = self._load_face_vector(profile.person_id)
                if face_vector_stored is not None:
                    similarity = self._calculate_similarity(face_vector, face_vector_stored)
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match = profile
        
        if best_match and best_similarity >= threshold:
            logger.debug(f"Identified person: {best_match.person_name} (similarity: {best_similarity:.3f})")
            return best_match
        
        return None
    
    def _load_face_vector(self, person_id: str) -> Optional[np.ndarray]:
        """
        Load face vector for person
        
        Args:
            person_id: Person ID
        
        Returns:
            Face vector or None
        """
        profile_file = self.people_dir / f"{person_id}.json"
        
        if not profile_file.exists():
            return None
        
        try:
            with open(profile_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load face vector from separate file
            face_vector_file = self.people_dir / f"{person_id}_face.npy"
            if face_vector_file.exists():
                face_vector = np.load(face_vector_file)
                return face_vector
            
            return None
        except Exception as e:
            logger.error(f"Failed to load face vector for {person_id}: {e}")
            return None
    
    def update_profile(self, person_id: str, updates: Dict[str, Any]):
        """
        Update existing profile
        
        Args:
            person_id: Person ID
            updates: Fields to update
        """
        if person_id not in self.profiles:
            logger.error(f"Profile not found: {person_id}")
            return
        
        profile = self.profiles[person_id]
        
        # Update fields
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        # Update timestamp
        profile.updated_at = datetime.now(timezone.utc).isoformat()
        
        # Save profile
        self._save_profile(profile)
        
        # Update indexes if name changed
        if "person_name" in updates:
            # Remove old name index
            old_normalized_name = self._normalize_name(profile.person_name)
            if old_normalized_name in self.name_index:
                del self.name_index[old_normalized_name]
            
            # Add new name index
            new_normalized_name = self._normalize_name(updates["person_name"])
            self.name_index[new_normalized_name] = person_id
        
        logger.info(f"Updated profile: {person_id}")
    
    def get_profile(self, person_id: str) -> Optional[PersonProfile]:
        """
        Get person profile
        
        Args:
            person_id: Person ID
        
        Returns:
            Profile or None
        """
        return self.profiles.get(person_id)
    
    def search_by_name(self, name: str) -> Optional[PersonProfile]:
        """
        Search profiles by name (fuzzy match)
        
        Args:
            name: Person name to search
        
        Returns:
            Matching profile or None
        """
        normalized_search = self._normalize_name(name)
        
        # Exact match
        if normalized_search in self.name_index:
            person_id = self.name_index[normalized_search]
            return self.profiles[person_id]
        
        # Fuzzy match (contains)
        for normalized_name, person_id in self.name_index.items():
            if normalized_search in normalized_name or normalized_name in normalized_search:
                return self.profiles[person_id]
        
        return None
    
    def link_platform(self, person_id: str, platform: str, identifier: str):
        """
        Link platform ID to person
        
        Args:
            person_id: Person ID
            platform: Platform name (teams, whatsapp, discord, etc.)
            identifier: Platform-specific identifier (email, phone number, etc.)
        """
        if person_id not in self.profiles:
            logger.error(f"Profile not found: {person_id}")
            return
        
        profile = self.profiles[person_id]
        profile.platform_links[platform] = identifier
        
        # Save profile
        self._save_profile(profile)
        
        logger.info(f"Linked {platform} to {person_id}: {identifier}")
    
    def add_meeting_reference(self, person_id: str, meeting_id: str):
        """
        Link meeting to person
        
        Args:
            person_id: Person ID
            meeting_id: Meeting ID
        """
        if person_id not in self.profiles:
            logger.error(f"Profile not found: {person_id}")
            return
        
        profile = self.profiles[person_id]
        profile.meeting_count += 1
        profile.last_interaction = datetime.now(timezone.utc).isoformat()
        
        # Save profile
        self._save_profile(profile)
        
        logger.info(f"Added meeting reference to {person_id}: {meeting_id}")
    
    def _save_profile(self, profile: PersonProfile):
        """
        Save profile to disk
        
        Args:
            profile: Profile to save
        """
        profile_file = self.people_dir / f"{profile.person_id}.json"
        
        with open(profile_file, 'w', encoding='utf-8') as f:
            json.dump(profile.dict(), f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved profile: {profile.person_id}")
    
    def _save_face_vector(self, person_id: str, face_vector: np.ndarray):
        """
        Save face vector to disk
        
        Args:
            person_id: Person ID
            face_vector: 128-d face vector
        """
        face_vector_file = self.people_dir / f"{person_id}_face.npy"
        np.save(face_vector_file, face_vector)
        
        logger.debug(f"Saved face vector: {person_id}")
    
    def get_all_profiles(self) -> List[PersonProfile]:
        """
        Get all profiles
        
        Returns:
            List of all profiles
        """
        return list(self.profiles.values())
    
    def get_profile_count(self) -> int:
        """
        Get number of profiles
        
        Returns:
            Profile count
        """
        return len(self.profiles)
    
    def delete_profile(self, person_id: str):
        """
        Delete profile
        
        Args:
            person_id: Person ID
        """
        if person_id not in self.profiles:
            logger.error(f"Profile not found: {person_id}")
            return
        
        profile = self.profiles[person_id]
        
        # Remove from indexes
        if profile.face_id and profile.face_id in self.face_index:
            del self.face_index[profile.face_id]
        
        normalized_name = self._normalize_name(profile.person_name)
        if normalized_name in self.name_index:
            del self.name_index[normalized_name]
        
        # Delete files
        profile_file = self.people_dir / f"{person_id}.json"
        face_vector_file = self.people_dir / f"{person_id}_face.npy"
        
        if profile_file.exists():
            profile_file.unlink()
        
        if face_vector_file.exists():
            face_vector_file.unlink()
        
        # Remove from memory
        del self.profiles[person_id]
        
        logger.info(f"Deleted profile: {person_id}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get manager status
        
        Returns:
            Status dictionary
        """
        return {
            "profile_count": len(self.profiles),
            "face_index_count": len(self.face_index),
            "name_index_count": len(self.name_index),
            "people_dir": str(self.people_dir),
            "face_threshold": self.config.face_threshold,
            "max_profiles": self.config.max_profiles
        }


def main():
    """Test the People Manager"""
    from loguru import logger
    
    logger.add("logs/people_manager_{time}.log", rotation="10 MB")
    
    # Create manager
    config = PeopleManagerConfig()
    manager = PeopleManager(config)
    
    # Test: Create a test profile with dummy face vector
    test_face_vector = np.random.rand(128).astype(np.float32)
    
    profile = manager.create_profile(
        face_vector=test_face_vector,
        name="Lasse Larsson",
        company="Logistik AB",
        metadata={
            "key_points": ["Föredrar korta presentationer"],
            "platform_links": {"whatsapp": "+46701234567"}
        }
    )
    
    logger.info(f"Created profile: {profile.person_name}")
    
    # Test: Identify person
    identified = manager.identify_person(test_face_vector)
    if identified:
        logger.info(f"Identified: {identified.person_name}")
    
    # Test: Search by name
    found = manager.search_by_name("Lasse")
    if found:
        logger.info(f"Found by name: {found.person_name}")
    
    # Test: Link platform
    manager.link_platform(profile.person_id, "teams", "lasse.l@logistik.se")
    
    # Test: Add meeting reference
    manager.add_meeting_reference(profile.person_id, "meeting_001")
    
    # Get status
    status = manager.get_status()
    logger.info(f"Manager status: {status}")
    
    logger.info("People Manager test complete")


if __name__ == "__main__":
    main()
