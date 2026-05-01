#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Phase 6.3: Temporal Graph
Temporal knowledge graph with ChromaDB + JSON hybrid for meeting history and contextual recall
"""

import sys
import json
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class TemporalGraphConfig(BaseModel):
    """Configuration for Temporal Graph"""
    meeting_history_dir: str = Field(default="memory/meeting_history", description="Directory for meeting history")
    chroma_collection_name: str = Field(default="meeting_history", description="ChromaDB collection name")
    max_meetings_per_person: int = Field(default=100, description="Max meetings to store per person")


class TemporalGraph:
    """
    Temporal Knowledge Graph
    Manages meeting history with ChromaDB + JSON hybrid for semantic and factual recall
    """
    
    def __init__(self, config: TemporalGraphConfig):
        """
        Initialize Temporal Graph
        
        Args:
            config: Temporal Graph configuration
        """
        self.config = config
        
        # Directory structure
        self.meeting_history_dir = Path(config.meeting_history_dir)
        self.meeting_history_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache
        self.meetings: Dict[str, Dict[str, Any]] = {}
        self.person_meetings: Dict[str, List[str]] = {}  # person_id -> list of meeting_ids
        
        # Load existing meetings
        self._load_meetings()
        
        logger.info("Temporal Graph initialized")
    
    def _load_meetings(self):
        """Load all meetings from disk"""
        for person_dir in self.meeting_history_dir.iterdir():
            if not person_dir.is_dir():
                continue
            
            for meeting_file in person_dir.glob("*.json"):
                try:
                    with open(meeting_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    meeting_id = data["meeting_id"]
                    self.meetings[meeting_id] = data
                    
                    # Index by person
                    for person_id in data.get("person_ids", []):
                        if person_id not in self.person_meetings:
                            self.person_meetings[person_id] = []
                        self.person_meetings[person_id].append(meeting_id)
                    
                except Exception as e:
                    logger.error(f"Failed to load meeting {meeting_file.name}: {e}")
        
        logger.info(f"Loaded {len(self.meetings)} meetings from disk")
    
    def add_meeting(
        self,
        meeting_id: str,
        summary: str,
        metadata: Dict[str, Any],
        person_ids: Optional[List[str]] = None
    ):
        """
        Add meeting to temporal graph
        
        Args:
            meeting_id: Meeting ID
            summary: Meeting summary text
            metadata: Meeting metadata (platform, date, etc.)
            person_ids: List of person IDs who attended
        """
        if person_ids is None:
            person_ids = []
        
        # Create meeting record
        meeting = {
            "meeting_id": meeting_id,
            "summary": summary,
            "metadata": metadata,
            "person_ids": person_ids,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Save meeting
        self._save_meeting(meeting)
        
        # Add to cache
        self.meetings[meeting_id] = meeting
        
        # Index by person
        for person_id in person_ids:
            if person_id not in self.person_meetings:
                self.person_meetings[person_id] = []
            self.person_meetings[person_id].append(meeting_id)
        
        logger.info(f"Added meeting to temporal graph: {meeting_id}")
    
    def add_person_link(self, meeting_id: str, person_id: str):
        """
        Link person to meeting
        
        Args:
            meeting_id: Meeting ID
            person_id: Person ID
        """
        if meeting_id not in self.meetings:
            logger.warning(f"Meeting not found: {meeting_id}")
            return
        
        # Add person to meeting
        meeting = self.meetings[meeting_id]
        if person_id not in meeting["person_ids"]:
            meeting["person_ids"].append(person_id)
        
        # Add meeting to person
        if person_id not in self.person_meetings:
            self.person_meetings[person_id] = []
        if meeting_id not in self.person_meetings[person_id]:
            self.person_meetings[person_id].append(meeting_id)
        
        # Save updated meeting
        self._save_meeting(meeting)
        
        logger.debug(f"Linked person {person_id} to meeting {meeting_id}")
    
    def search_meetings(
        self,
        query: str,
        person_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search meetings semantically (keyword-based for now)
        
        Args:
            query: Search query
            person_id: Filter by person ID (optional)
            limit: Max results
        
        Returns:
            List of matching meetings
        """
        query_lower = query.lower()
        results = []
        
        for meeting_id, meeting in self.meetings.items():
            # Filter by person if specified
            if person_id and person_id not in meeting["person_ids"]:
                continue
            
            # Check if query matches summary or metadata
            summary_lower = meeting["summary"].lower()
            metadata_str = str(meeting["metadata"]).lower()
            
            if query_lower in summary_lower or query_lower in metadata_str:
                results.append(meeting)
        
        # Sort by date (newest first)
        results.sort(key=lambda x: x.get("metadata", {}).get("date", ""), reverse=True)
        
        return results[:limit]
    
    def get_person_history(self, person_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get person's meeting history
        
        Args:
            person_id: Person ID
            limit: Max meetings to return
        
        Returns:
            List of meetings with this person
        """
        if person_id not in self.person_meetings:
            return []
        
        meeting_ids = self.person_meetings[person_id]
        meetings = [self.meetings[mid] for mid in meeting_ids if mid in self.meetings]
        
        # Sort by date (newest first)
        meetings.sort(key=lambda x: x.get("metadata", {}).get("date", ""), reverse=True)
        
        return meetings[:limit]
    
    def get_contextual_recap(self, person_id: str, meeting_id: str) -> str:
        """
        Generate contextual recap before meeting
        
        Args:
            person_id: Person ID
            meeting_id: Current meeting ID
        
        Returns:
            Recap text
        """
        # Get person's recent meetings
        recent_meetings = self.get_person_history(person_id, limit=3)
        
        if not recent_meetings:
            return "Ingen tidigare möteshistorik hittad."
        
        # Generate recap
        recap_parts = []
        recap_parts.append(f"Senaste möten med denna person:")
        
        for i, meeting in enumerate(recent_meetings):
            date = meeting.get("metadata", {}).get("date", "Okänt datum")
            platform = meeting.get("metadata", {}).get("platform", "Okänd plattform")
            summary = meeting.get("summary", "Ingen sammanfattning")
            
            recap_parts.append(f"\n{i+1}. {date} ({platform}):")
            recap_parts.append(f"   {summary}")
        
        return "\n".join(recap_parts)
    
    def get_cross_platform_context(self, person_id: str) -> Dict[str, Any]:
        """
        Get cross-platform context for a person
        
        Args:
            person_id: Person ID
        
        Returns:
            Cross-platform context
        """
        meetings = self.get_person_history(person_id)
        
        # Group by platform
        platforms = {}
        for meeting in meetings:
            platform = meeting.get("metadata", {}).get("platform", "unknown")
            if platform not in platforms:
                platforms[platform] = []
            platforms[platform].append(meeting)
        
        # Get last interaction per platform
        last_interactions = {}
        for platform, platform_meetings in platforms.items():
            if platform_meetings:
                last_meeting = platform_meetings[0]  # Already sorted by date
                last_interactions[platform] = {
                    "date": last_meeting.get("metadata", {}).get("date"),
                    "summary": last_meeting.get("summary", "")
                }
        
        return {
            "person_id": person_id,
            "total_meetings": len(meetings),
            "platforms": list(platforms.keys()),
            "last_interactions": last_interactions
        }
    
    def _save_meeting(self, meeting: Dict[str, Any]):
        """
        Save meeting to disk
        
        Args:
            meeting: Meeting data
        """
        # Determine person directory (use first person_id or "general")
        person_ids = meeting.get("person_ids", [])
        if person_ids:
            person_dir = self.meeting_history_dir / person_ids[0]
        else:
            person_dir = self.meeting_history_dir / "general"
        
        person_dir.mkdir(parents=True, exist_ok=True)
        
        meeting_file = person_dir / f"{meeting['meeting_id']}.json"
        
        with open(meeting_file, 'w', encoding='utf-8') as f:
            json.dump(meeting, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved meeting: {meeting['meeting_id']}")
    
    def get_meeting(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """
        Get meeting by ID
        
        Args:
            meeting_id: Meeting ID
        
        Returns:
            Meeting data or None
        """
        return self.meetings.get(meeting_id)
    
    def get_all_meetings(self) -> List[Dict[str, Any]]:
        """
        Get all meetings
        
        Returns:
            List of all meetings
        """
        return list(self.meetings.values())
    
    def delete_meeting(self, meeting_id: str):
        """
        Delete meeting
        
        Args:
            meeting_id: Meeting ID
        """
        if meeting_id not in self.meetings:
            logger.error(f"Meeting not found: {meeting_id}")
            return
        
        meeting = self.meetings[meeting_id]
        person_ids = meeting.get("person_ids", [])
        
        # Remove from person index
        for person_id in person_ids:
            if person_id in self.person_meetings:
                if meeting_id in self.person_meetings[person_id]:
                    self.person_meetings[person_id].remove(meeting_id)
        
        # Delete file
        if person_ids:
            person_dir = self.meeting_history_dir / person_ids[0]
        else:
            person_dir = self.meeting_history_dir / "general"
        
        meeting_file = person_dir / f"{meeting_id}.json"
        if meeting_file.exists():
            meeting_file.unlink()
        
        # Remove from cache
        del self.meetings[meeting_id]
        
        logger.info(f"Deleted meeting: {meeting_id}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get graph status
        
        Returns:
            Status dictionary
        """
        return {
            "total_meetings": len(self.meetings),
            "total_persons": len(self.person_meetings),
            "meeting_history_dir": str(self.meeting_history_dir)
        }


def main():
    """Test the Temporal Graph"""
    from loguru import logger
    
    logger.add("logs/temporal_graph_{time}.log", rotation="10 MB")
    
    # Create graph
    config = TemporalGraphConfig()
    graph = TemporalGraph(config)
    
    # Test: Add meeting
    graph.add_meeting(
        meeting_id="meeting_001",
        summary="Diskuterade offert för Q3",
        metadata={"platform": "teams", "date": "2026-04-29"},
        person_ids=["person_1", "person_2"]
    )
    
    # Test: Add another meeting
    graph.add_meeting(
        meeting_id="meeting_002",
        summary="Följande upp på leveransproblem",
        metadata={"platform": "whatsapp", "date": "2026-04-28"},
        person_ids=["person_1"]
    )
    
    # Test: Get person history
    history = graph.get_person_history("person_1")
    logger.info(f"Person history: {len(history)} meetings")
    
    # Test: Get contextual recap
    recap = graph.get_contextual_recap("person_1", "meeting_003")
    logger.info(f"Contextual recap:\n{recap}")
    
    # Test: Get cross-platform context
    context = graph.get_cross_platform_context("person_1")
    logger.info(f"Cross-platform context: {context}")
    
    # Test: Search meetings
    results = graph.search_meetings("offert")
    logger.info(f"Search results: {len(results)} meetings")
    
    # Get status
    status = graph.get_status()
    logger.info(f"Graph status: {status}")
    
    logger.info("Temporal Graph test complete")


if __name__ == "__main__":
    main()
