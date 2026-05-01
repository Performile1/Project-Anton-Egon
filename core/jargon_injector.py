#!/usr/bin/env python3
"""
Project Anton Egon - Jargon Injector
Real-time phrase replacement in LLM responses for authentic voice

Phase 16: The Trickster Engine
"""

import re
import random
from typing import Optional, List, Dict, Any
from enum import Enum

from loguru import logger

from ui.phrase_library_editor import phrase_library, PhraseCategory, TriggerMood


class ReplacementStrategy(Enum):
    """Phrase replacement strategies"""
    EXACT = "exact"  # Replace exact generic phrases
    CONTEXTUAL = "contextual"  # Replace based on context
    FREQUENCY = "frequency"  # Replace based on frequency setting


class JargonInjector:
    """
    Jargon Injector
    Replaces generic AI phrases with personal jargon in real-time
    """
    
    def __init__(self, strategy: ReplacementStrategy = ReplacementStrategy.CONTEXTUAL):
        """
        Initialize Jargon Injector
        
        Args:
            strategy: Replacement strategy
        """
        self.strategy = strategy
        self.generic_phrases = self._load_generic_phrases()
        
        logger.info(f"Jargon Injector initialized with {strategy.value} strategy")
    
    def _load_generic_phrases(self) -> Dict[str, List[str]]:
        """
        Load generic AI phrases to replace
        
        Returns:
            Dictionary mapping categories to generic phrases
        """
        return {
            "greetings": [
                "Hello", "Hi", "Good morning", "Good afternoon", "Hey",
                "Hej", "God morgon", "God dag", "Tjena"
            ],
            "decisions": [
                "I agree", "Sounds good", "Let's do it", "That works",
                "Jag håller med", "Låter bra", "Det fungerar", "Okej"
            ],
            "pushback": [
                "I disagree", "That doesn't work", "We need to reconsider",
                "Jag håller inte med", "Det fungerar inte", "Vi måste tänka om"
            ],
            "fillers": [
                "Um", "Uh", "Like", "You know", "Basically",
                "Ehm", "Typ", "Du vet", "I grund och botten"
            ],
            "agreement": [
                "Yes", "Correct", "Right", "Absolutely",
                "Ja", "Rätt", "Korrekt", "Absolut"
            ],
            "disagreement": [
                "No", "Not really", "I don't think so",
                "Nej", "Inte riktigt", "Jag tror inte det"
            ],
            "transitions": [
                "Moving on", "Next", "Let's continue",
                "Låt oss gå vidare", "Nästa", "Fortsätter"
            ],
            "closings": [
                "Thank you", "Goodbye", "See you later",
                "Tack", "Hej då", "Vi ses"
            ]
        }
    
    def inject(
        self,
        text: str,
        current_mood: TriggerMood = TriggerMood.NEUTRAL,
        override_frequency: Optional[float] = None
    ) -> str:
        """
        Inject personal jargon into text
        
        Args:
            text: Original text from LLM
            current_mood: Current agent mood
            override_frequency: Override phrase frequency (0.0 - 1.0)
        
        Returns:
            Text with personal jargon injected
        """
        result = text
        
        # Get all phrases from library
        all_phrases = phrase_library.get_all_phrases()
        
        # Filter by mood (or include ANY mood phrases)
        mood_phrases = [
            p for p in all_phrases
            if p['trigger_mood'] == current_mood.value or p['trigger_mood'] == TriggerMood.ANY.value
        ]
        
        # Group by category
        phrases_by_category = {}
        for phrase in mood_phrases:
            cat = phrase['category']
            if cat not in phrases_by_category:
                phrases_by_category[cat] = []
            phrases_by_category[cat].append(phrase)
        
        # Replace based on strategy
        if self.strategy == ReplacementStrategy.EXACT:
            result = self._replace_exact(result, phrases_by_category)
        elif self.strategy == ReplacementStrategy.CONTEXTUAL:
            result = self._replace_contextual(result, phrases_by_category, override_frequency)
        elif self.strategy == ReplacementStrategy.FREQUENCY:
            result = self._replace_by_frequency(result, phrases_by_category, override_frequency)
        
        logger.debug(f"Jargon injected: {len(result - text)} characters added")
        return result
    
    def _replace_exact(self, text: str, phrases_by_category: Dict[str, List]) -> str:
        """
        Replace exact generic phrases with personal ones
        
        Args:
            text: Original text
            phrases_by_category: Phrases grouped by category
        
        Returns:
            Text with replacements
        """
        result = text
        
        for category, phrases in phrases_by_category.items():
            if category not in self.generic_phrases:
                continue
            
            generic_list = self.generic_phrases[category]
            personal_list = [p['text'] for p in phrases]
            
            if not personal_list:
                continue
            
            # Replace each generic phrase with a random personal one
            for generic in generic_list:
                if generic.lower() in result.lower():
                    personal = random.choice(personal_list)
                    # Case-insensitive replacement
                    pattern = re.compile(re.escape(generic), re.IGNORECASE)
                    result = pattern.sub(personal, result, count=1)
        
        return result
    
    def _replace_contextual(
        self,
        text: str,
        phrases_by_category: Dict[str, List],
        override_frequency: Optional[float] = None
    ) -> str:
        """
        Replace phrases based on context and frequency
        
        Args:
            text: Original text
            phrases_by_category: Phrases grouped by category
            override_frequency: Override phrase frequency
        
        Returns:
            Text with replacements
        """
        result = text
        
        for category, phrases in phrases_by_category.items():
            if category not in self.generic_phrases:
                continue
            
            generic_list = self.generic_phrases[category]
            
            for phrase in phrases:
                freq = override_frequency or phrase.get('frequency', 0.5)
                
                # Only replace if random check passes
                if random.random() > freq:
                    continue
                
                # Find matching generic phrase
                for generic in generic_list:
                    if generic.lower() in result.lower():
                        pattern = re.compile(re.escape(generic), re.IGNORECASE)
                        result = pattern.sub(phrase['text'], result, count=1)
                        break
        
        return result
    
    def _replace_by_frequency(
        self,
        text: str,
        phrases_by_category: Dict[str, List],
        override_frequency: Optional[float] = None
    ) -> str:
        """
        Replace phrases based purely on frequency
        
        Args:
            text: Original text
            phrases_by_category: Phrases grouped by category
            override_frequency: Override phrase frequency
        
        Returns:
            Text with replacements
        """
        result = text
        
        for category, phrases in phrases_by_category.items():
            if category not in self.generic_phrases:
                continue
            
            generic_list = self.generic_phrases[category]
            
            # Sort by frequency (highest first)
            sorted_phrases = sorted(phrases, key=lambda p: p.get('frequency', 0.5), reverse=True)
            
            for phrase in sorted_phrases:
                freq = override_frequency or phrase.get('frequency', 0.5)
                
                # Only replace if random check passes
                if random.random() > freq:
                    continue
                
                # Find matching generic phrase
                for generic in generic_list:
                    if generic.lower() in result.lower():
                        pattern = re.compile(re.escape(generic), re.IGNORECASE)
                        result = pattern.sub(phrase['text'], result, count=1)
                        break
        
        return result
    
    def add_custom_replacement(self, generic: str, personal: str, category: str):
        """
        Add custom replacement rule
        
        Args:
            generic: Generic phrase to replace
            personal: Personal phrase to use
            category: Category for the replacement
        """
        if category not in self.generic_phrases:
            self.generic_phrases[category] = []
        
        if generic not in self.generic_phrases[category]:
            self.generic_phrases[category].append(generic)
        
        logger.info(f"Added custom replacement: '{generic}' -> '{personal}'")


# Singleton instance
jargon_injector = JargonInjector()


async def main():
    """Test Jargon Injector"""
    logger.add("logs/jargon_injector_{time}.log", rotation="10 MB")
    
    # Import default phrases
    phrase_library.import_default_phrases()
    
    # Test injection
    test_text = "Hello everyone, I agree with that. Let's do it."
    injected = jargon_injector.inject(test_text, TriggerMood.HAPPY)
    
    logger.info(f"Original: {test_text}")
    logger.info(f"Injected: {injected}")
    
    logger.info("Jargon Injector test complete")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
