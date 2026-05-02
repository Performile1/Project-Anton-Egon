#!/usr/bin/env python3
"""
Project Anton Egon - Phrase Library Editor
Linguistic DNA: Personal jargon injection for authentic voice

Phase 16: The Trickster Engine
"""

import json
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime

from loguru import logger


class PhraseCategory(Enum):
    """Phrase categories for different contexts"""
    GREETINGS = "greetings"
    DECISIONS = "decisions"
    PUSHBACK = "pushback"
    FILLERS = "fillers"
    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"
    TRANSITIONS = "transitions"
    CLOSINGS = "closings"
    HUMOR = "humor"
    TECHNICAL = "technical"


class TriggerMood(Enum):
    """Mood trigger for phrase usage"""
    HAPPY = "happy"
    NEUTRAL = "neutral"
    IRRITATED = "irritated"
    EXCITED = "excited"
    SERIOUS = "serious"
    CASUAL = "casual"
    ANY = "any"


@dataclass
class Phrase:
    """Personal phrase entry"""
    id: str
    text: str
    category: str
    trigger_mood: str
    frequency: float = 1.0  # Usage frequency (0.0 - 1.0)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""
    audio_file: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Phrase':
        return cls(**data)


class PhraseLibrary:
    """
    Phrase Library Manager
    Stores and manages personal phrases for jargon injection
    """
    
    def __init__(self, library_path: Optional[str] = None):
        """
        Initialize Phrase Library
        
        Args:
            library_path: Path to JSON library file
        """
        self.library_path = library_path or "config/phrase_library.json"
        self.phrases: Dict[str, Phrase] = {}
        self._load_library()
        
        logger.info(f"Phrase Library initialized: {len(self.phrases)} phrases")
    
    def _load_library(self):
        """Load phrases from JSON file"""
        try:
            path = Path(self.library_path)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for phrase_data in data.get('phrases', []):
                        phrase = Phrase.from_dict(phrase_data)
                        self.phrases[phrase.id] = phrase
                logger.info(f"Loaded {len(self.phrases)} phrases from {self.library_path}")
        except Exception as e:
            logger.error(f"Failed to load phrase library: {e}")
    
    def _save_library(self):
        """Save phrases to JSON file"""
        try:
            path = Path(self.library_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'version': '1.0',
                'last_updated': datetime.now().isoformat(),
                'phrases': [phrase.to_dict() for phrase in self.phrases.values()]
            }
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(self.phrases)} phrases to {self.library_path}")
        except Exception as e:
            logger.error(f"Failed to save phrase library: {e}")
    
    def add_phrase(self, phrase: Phrase) -> bool:
        """
        Add phrase to library
        
        Args:
            phrase: Phrase to add
        
        Returns:
            True if added successfully
        """
        if phrase.id in self.phrases:
            logger.warning(f"Phrase ID already exists: {phrase.id}")
            return False
        
        self.phrases[phrase.id] = phrase
        self._save_library()
        logger.info(f"Added phrase: {phrase.text}")
        return True
    
    def update_phrase(self, phrase: Phrase) -> bool:
        """
        Update existing phrase
        
        Args:
            phrase: Phrase to update
        
        Returns:
            True if updated successfully
        """
        if phrase.id not in self.phrases:
            logger.warning(f"Phrase ID not found: {phrase.id}")
            return False
        
        self.phrases[phrase.id] = phrase
        self._save_library()
        logger.info(f"Updated phrase: {phrase.text}")
        return True
    
    def delete_phrase(self, phrase_id: str) -> bool:
        """
        Delete phrase from library
        
        Args:
            phrase_id: Phrase ID to delete
        
        Returns:
            True if deleted successfully
        """
        if phrase_id not in self.phrases:
            logger.warning(f"Phrase ID not found: {phrase_id}")
            return False
        
        del self.phrases[phrase_id]
        self._save_library()
        logger.info(f"Deleted phrase: {phrase_id}")
        return True
    
    def get_phrase(self, phrase_id: str) -> Optional[Phrase]:
        """
        Get phrase by ID
        
        Args:
            phrase_id: Phrase ID
        
        Returns:
            Phrase or None
        """
        return self.phrases.get(phrase_id)
    
    def get_phrases_by_category(self, category: PhraseCategory) -> List[Phrase]:
        """
        Get all phrases in a category
        
        Args:
            category: Phrase category
        
        Returns:
            List of phrases
        """
        return [p for p in self.phrases.values() if p.category == category.value]
    
    def get_phrases_by_mood(self, mood: TriggerMood) -> List[Phrase]:
        """
        Get all phrases for a specific mood
        
        Args:
            mood: Trigger mood
        
        Returns:
            List of phrases
        """
        return [p for p in self.phrases.values() if p.trigger_mood == mood.value]
    
    def get_all_phrases(self) -> List[Dict[str, Any]]:
        """
        Get all phrases as dictionaries
        
        Returns:
            List of phrase dictionaries
        """
        return [phrase.to_dict() for phrase in self.phrases.values()]
    
    def get_categories(self) -> List[str]:
        """Get all used categories"""
        categories = set(p.category for p in self.phrases.values())
        return sorted(list(categories))
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get library statistics
        
        Returns:
            Statistics dictionary
        """
        category_counts = {}
        for phrase in self.phrases.values():
            cat = phrase.category
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        return {
            "total_phrases": len(self.phrases),
            "categories": category_counts,
            "last_updated": datetime.now().isoformat()
        }
    
    def search_phrases(self, query: str) -> List[Phrase]:
        """
        Search phrases by text
        
        Args:
            query: Search query
        
        Returns:
            List of matching phrases
        """
        query_lower = query.lower()
        return [
            p for p in self.phrases.values()
            if query_lower in p.text.lower() or query_lower in p.notes.lower()
        ]
    
    def import_default_phrases(self):
        """Import default Anton Egon phrases"""
        default_phrases = [
            Phrase(
                id="greeting_001",
                text="Tjena mors!",
                category=PhraseCategory.GREETINGS.value,
                trigger_mood=TriggerMood.HAPPY.value,
                frequency=0.8
            ),
            Phrase(
                id="greeting_002",
                text="Kul att se gänget!",
                category=PhraseCategory.GREETINGS.value,
                trigger_mood=TriggerMood.HAPPY.value,
                frequency=0.6
            ),
            Phrase(
                id="decision_001",
                text="Kanon, då klubbar vi det.",
                category=PhraseCategory.DECISIONS.value,
                trigger_mood=TriggerMood.HAPPY.value,
                frequency=0.9
            ),
            Phrase(
                id="decision_002",
                text="Hundra gubbar.",
                category=PhraseCategory.DECISIONS.value,
                trigger_mood=TriggerMood.HAPPY.value,
                frequency=0.7
            ),
            Phrase(
                id="pushback_001",
                text="Vi behöver komma till punkt här.",
                category=PhraseCategory.PUSHBACK.value,
                trigger_mood=TriggerMood.IRRITATED.value,
                frequency=0.8
            ),
            Phrase(
                id="pushback_002",
                text="Det där lirar inte.",
                category=PhraseCategory.PUSHBACK.value,
                trigger_mood=TriggerMood.IRRITATED.value,
                frequency=0.9
            ),
            Phrase(
                id="filler_001",
                text="Alltså...",
                category=PhraseCategory.FILLERS.value,
                trigger_mood=TriggerMood.ANY.value,
                frequency=0.5
            ),
            Phrase(
                id="filler_002",
                text="Jo, men visst.",
                category=PhraseCategory.FILLERS.value,
                trigger_mood=TriggerMood.ANY.value,
                frequency=0.4
            ),
        ]
        
        for phrase in default_phrases:
            if phrase.id not in self.phrases:
                self.phrases[phrase.id] = phrase
        
        self._save_library()
        logger.info(f"Imported {len(default_phrases)} default phrases")


# Singleton instance
phrase_library = PhraseLibrary()


async def main():
    """Test Phrase Library"""
    logger.add("logs/phrase_library_{time}.log", rotation="10 MB")
    
    # Import default phrases
    phrase_library.import_default_phrases()
    
    # Get stats
    stats = phrase_library.get_stats()
    logger.info(f"Library stats: {stats}")
    
    # Get all phrases
    phrases = phrase_library.get_all_phrases()
    logger.info(f"Phrases: {len(phrases)}")
    
    logger.info("Phrase Library test complete")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
