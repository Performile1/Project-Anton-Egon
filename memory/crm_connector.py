#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Phase 6.3: CRM Connector
Connects People CRM with meeting history and entity extraction
"""

import sys
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class CRMConnectorConfig(BaseModel):
    """Configuration for CRM Connector"""
    auto_update_profiles: bool = Field(default=True, description="Auto-update person profiles")
    max_key_points: int = Field(default=10, description="Max key points per person")
    sync_cross_platform: bool = Field(default=True, description="Auto-sync cross-platform data")


class CRMConnector:
    """
    CRM Connector
    Connects People CRM with meeting history and entity extraction
    """
    
    def __init__(self, config: CRMConnectorConfig, people_manager, temporal_graph, entity_extractor):
        """
        Initialize CRM Connector
        
        Args:
            config: CRM Connector configuration
            people_manager: People Manager instance
            temporal_graph: Temporal Graph instance
            entity_extractor: Entity Extractor instance
        """
        self.config = config
        self.people_manager = people_manager
        self.temporal_graph = temporal_graph
        self.entity_extractor = entity_extractor
        
        logger.info("CRM Connector initialized")
    
    def process_meeting(
        self,
        meeting_id: str,
        transcriptions: List[Dict[str, Any]],
        entities: List[Dict[str, Any]],
        person_ids: List[str]
    ):
        """
        Process meeting data and update CRM
        
        Args:
            meeting_id: Meeting ID
            transcriptions: List of transcriptions
            entities: List of extracted entities
            person_ids: List of person IDs
        """
        # Generate meeting summary
        summary = self._generate_summary(transcriptions, entities)
        
        # Add meeting to temporal graph
        metadata = {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "platform": "teams",  # Should be passed in
            "entity_count": len(entities)
        }
        
        self.temporal_graph.add_meeting(
            meeting_id=meeting_id,
            summary=summary,
            metadata=metadata,
            person_ids=person_ids
        )
        
        # Update person profiles with extracted entities
        if self.config.auto_update_profiles:
            self.update_person_profiles(person_ids, entities)
        
        logger.info(f"Processed meeting: {meeting_id}")
    
    def update_person_profiles(self, person_ids: List[str], entities: List[Dict[str, Any]]):
        """
        Update person profiles with extracted entities
        
        Args:
            person_ids: List of person IDs
            entities: List of extracted entities
        """
        for person_id in person_ids:
            profile = self.people_manager.get_profile(person_id)
            if not profile:
                continue
            
            # Extract key points from entities
            new_key_points = []
            
            for entity in entities:
                entity_type = entity.get("type")
                context = entity.get("context")
                
                if entity_type == "promise" and context:
                    new_key_points.append(f"Löfte: {context}")
                elif entity_type == "pain_point" and context:
                    new_key_points.append(f"Utmaning: {context}")
                elif entity_type == "personal_info" and context:
                    new_key_points.append(f"Personlig info: {context}")
            
            # Add new key points (limit to max)
            if new_key_points:
                current_key_points = profile.key_points.copy()
                current_key_points.extend(new_key_points)
                
                # Keep only most recent key points
                if len(current_key_points) > self.config.max_key_points:
                    current_key_points = current_key_points[-self.config.max_key_points:]
                
                # Update profile
                self.people_manager.update_profile(
                    person_id=person_id,
                    updates={"key_points": current_key_points}
                )
        
        logger.info(f"Updated profiles for {len(person_ids)} persons")
    
    def sync_cross_platform(self, person_id: str) -> Dict[str, Any]:
        """
        Sync data across platforms
        
        Args:
            person_id: Person ID
        
        Returns:
            Sync status
        """
        profile = self.people_manager.get_profile(person_id)
        if not profile:
            logger.warning(f"Profile not found: {person_id}")
            return {"status": "error", "message": "Profile not found"}
        
        # Get cross-platform context
        context = self.temporal_graph.get_cross_platform_context(person_id)
        
        # Sync platform links if needed
        platform_links = profile.platform_links
        
        sync_status = {
            "person_id": person_id,
            "platforms_synced": list(context.get("platforms", [])),
            "total_meetings": context.get("total_meetings", 0),
            "last_interactions": context.get("last_interactions", {})
        }
        
        logger.info(f"Cross-platform sync for {person_id}: {sync_status}")
        
        return sync_status
    
    def generate_summary(self, meeting_id: str) -> str:
        """
        Generate meeting summary
        
        Args:
            meeting_id: Meeting ID
        
        Returns:
            Meeting summary
        """
        meeting = self.temporal_graph.get_meeting(meeting_id)
        if not meeting:
            return "Meeting not found"
        
        return meeting.get("summary", "No summary available")
    
    def get_pending_updates(self) -> List[Dict[str, Any]]:
        """
        Get pending profile updates for review
        
        Returns:
            List of pending updates
        """
        # For now, return all profiles that need review
        # In a full implementation, this would track which profiles have pending changes
        profiles = self.people_manager.get_all_profiles()
        
        pending_updates = []
        for profile in profiles:
            # Check if profile has been updated recently
            updated_at = datetime.fromisoformat(profile.updated_at)
            days_since_update = (datetime.now(timezone.utc) - updated_at).days
            
            if days_since_update < 7:  # Updated within last 7 days
                pending_updates.append({
                    "person_id": profile.person_id,
                    "person_name": profile.person_name,
                    "updated_at": profile.updated_at,
                    "key_points_count": len(profile.key_points)
                })
        
        return pending_updates
    
    def _generate_summary(self, transcriptions: List[Dict[str, Any]], entities: List[Dict[str, Any]]) -> str:
        """
        Generate meeting summary from transcriptions and entities
        
        Args:
            transcriptions: List of transcriptions
            entities: List of entities
        
        Returns:
            Meeting summary
        """
        if not transcriptions:
            return "No transcriptions available"
        
        # Combine transcriptions
        all_text = " ".join([t.get("text", "") for t in transcriptions])
        
        # Extract key entities
        promises = [e for e in entities if e.get("type") == "promise"]
        prices = [e for e in entities if e.get("type") == "price"]
        pain_points = [e for e in entities if e.get("type") == "pain_point"]
        
        # Build summary
        summary_parts = []
        
        if promises:
            summary_parts.append("Löften:")
            for promise in promises[:3]:
                summary_parts.append(f"- {promise.get('context', promise.get('text', ''))}")
        
        if prices:
            summary_parts.append("Priser:")
            for price in prices[:3]:
                value = price.get("value", "Okänt")
                summary_parts.append(f"- {value}")
        
        if pain_points:
            summary_parts.append("Utmaningar:")
            for pain in pain_points[:3]:
                summary_parts.append(f"- {pain.get('context', pain.get('text', ''))}")
        
        if not summary_parts:
            return all_text[:200] + "..." if len(all_text) > 200 else all_text
        
        return "\n".join(summary_parts)
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get connector status
        
        Returns:
            Status dictionary
        """
        return {
            "auto_update_profiles": self.config.auto_update_profiles,
            "max_key_points": self.config.max_key_points,
            "sync_cross_platform": self.config.sync_cross_platform,
            "people_count": self.people_manager.get_profile_count(),
            "meeting_count": self.temporal_graph.get_status()["total_meetings"]
        }


def main():
    """Test the CRM Connector"""
    from loguru import logger
    
    logger.add("logs/crm_connector_{time}.log", rotation="10 MB")
    
    # Import dependencies
    from memory.people_manager import PeopleManager, PeopleManagerConfig
    from memory.temporal_graph import TemporalGraph, TemporalGraphConfig
    from memory.entity_extractor import EntityExtractor, EntityExtractorConfig
    
    # Create instances
    people_config = PeopleManagerConfig()
    people_manager = PeopleManager(people_config)
    
    graph_config = TemporalGraphConfig()
    temporal_graph = TemporalGraph(graph_config)
    
    extractor_config = EntityExtractorConfig()
    entity_extractor = EntityExtractor(extractor_config)
    
    # Create connector
    config = CRMConnectorConfig()
    connector = CRMConnector(config, people_manager, temporal_graph, entity_extractor)
    
    # Test: Process meeting
    transcriptions = [
        {"text": "Vi diskuterade offerten för Q3", "speaker_id": "user_1"},
        {"text": "Jag skickar den på måndag", "speaker_id": "user_2"}
    ]
    
    entities = [
        {"type": "promise", "text": "Jag skickar den på måndag", "context": "skickar offert"}
    ]
    
    connector.process_meeting(
        meeting_id="meeting_001",
        transcriptions=transcriptions,
        entities=entities,
        person_ids=["person_1"]
    )
    
    # Test: Get status
    status = connector.get_status()
    logger.info(f"CRM Connector status: {status}")
    
    logger.info("CRM Connector test complete")


if __name__ == "__main__":
    main()
