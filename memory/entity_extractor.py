#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Phase 6.2: Entity Extractor
Extracts entities (prices, dates, promises, pain points) from transcriptions using keyword-based NER
"""

import sys
import re
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class EntityType(Enum):
    """Types of entities to extract"""
    PROMISE = "promise"
    PRICE = "price"
    DATE = "date"
    PAIN_POINT = "pain_point"
    PERSONAL_INFO = "personal_info"


class Entity(BaseModel):
    """Extracted entity"""
    entity_type: EntityType
    text: str
    value: Optional[Any] = None
    confidence: float = Field(default=1.0, description="Confidence score (0-1)")
    context: Optional[str] = Field(None, description="Surrounding text for context")


class EntityExtractorConfig(BaseModel):
    """Configuration for Entity Extractor"""
    enable_price_extraction: bool = Field(default=True, description="Enable price extraction")
    enable_date_extraction: bool = Field(default=True, description="Enable date extraction")
    enable_promise_extraction: bool = Field(default=True, description="Enable promise extraction")
    enable_pain_point_extraction: bool = Field(default=True, description="Enable pain point extraction")
    enable_personal_info_extraction: bool = Field(default=True, description="Enable personal info extraction")
    confidence_threshold: float = Field(default=0.7, description="Minimum confidence to keep entity")


class EntityExtractor:
    """
    Entity Extractor using keyword-based NER
    Extracts prices, dates, promises, pain points, and personal information from text
    """
    
    # Keyword patterns for each entity type
    PATTERNS = {
        EntityType.PRICE: [
            "pris", "kostnad", "offert", "budget", "kronor", "sek", "kr",
            "dollar", "$", "euro", "€", "pound", "£", "betala", "kostar"
        ],
        EntityType.DATE: [
            "måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag",
            "datum", "vecka", "månad", "år", "idag", "imorgon", "igår",
            "nästa vecka", "veckan", "månaden", "året", "januari", "februari",
            "mars", "april", "maj", "juni", "juli", "augusti", "september",
            "oktober", "november", "december"
        ],
        EntityType.PROMISE: [
            "skickar", "kommer", "lovar", "ska", "återkommer", "följer upp",
            "kollar", "fixar", "ordnar", "ser till", "garanterar", "bekräftar"
        ],
        EntityType.PAIN_POINT: [
            "problem", "utmaning", "svårighet", "bekymmer", "utmaning",
            "svårt", "svårt att", "fungerar inte", "inte fungerar",
            "problem med", "utmaning med", "besvär", "hinder"
        ],
        EntityType.PERSONAL_INFO: [
            "semester", "ledig", "sjuk", "familj", "hund", "katt", "barn",
            "gift", "singel", "flyttar", "bor", "hem", "hus", "lägenhet"
        ]
    }
    
    def __init__(self, config: EntityExtractorConfig):
        """
        Initialize Entity Extractor
        
        Args:
            config: Entity Extractor configuration
        """
        self.config = config
        
        logger.info("Entity Extractor initialized")
    
    def extract_entities(self, text: str) -> List[Entity]:
        """
        Extract entities from text
        
        Args:
            text: Text to extract entities from
        
        Returns:
            List of extracted entities
        """
        entities = []
        text_lower = text.lower()
        
        # Extract each entity type
        if self.config.enable_price_extraction:
            price_entities = self._extract_prices(text, text_lower)
            entities.extend(price_entities)
        
        if self.config.enable_date_extraction:
            date_entities = self._extract_dates(text, text_lower)
            entities.extend(date_entities)
        
        if self.config.enable_promise_extraction:
            promise_entities = self._extract_promises(text, text_lower)
            entities.extend(promise_entities)
        
        if self.config.enable_pain_point_extraction:
            pain_entities = self._extract_pain_points(text, text_lower)
            entities.extend(pain_entities)
        
        if self.config.enable_personal_info_extraction:
            personal_entities = self._extract_personal_info(text, text_lower)
            entities.extend(person_entities)
        
        # Filter by confidence threshold
        entities = [e for e in entities if e.confidence >= self.config.confidence_threshold]
        
        logger.debug(f"Extracted {len(entities)} entities from text")
        
        return entities
    
    def _extract_prices(self, text: str, text_lower: str) -> List[Entity]:
        """Extract price entities"""
        entities = []
        
        # Check for price keywords
        for keyword in self.PATTERNS[EntityType.PRICE]:
            if keyword in text_lower:
                # Try to extract price value
                price_value = self._extract_price_value(text)
                
                # Get context (surrounding text)
                context = self._get_context(text, keyword)
                
                entities.append(Entity(
                    entity_type=EntityType.PRICE,
                    text=text,
                    value=price_value,
                    context=context
                ))
        
        return entities
    
    def _extract_price_value(self, text: str) -> Optional[float]:
        """Extract price value from text"""
        # Pattern for prices: 1000, 1 000, 1.000, 1000 kr, 1000 sek, etc.
        patterns = [
            r'(\d+[.,]?\d*)\s*(?:kr|sek|kronor|\$|dollar|euro|€)',
            r'(\d+[.,]?\d*)\s*(?:tusen|hundra)',
            r'(\d+[.,]?\d*)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value_str = match.group(1).replace(',', '').replace('.', '')
                    value = float(value_str)
                    return value
                except (ValueError, IndexError):
                    pass
        
        return None
    
    def _extract_dates(self, text: str, text_lower: str) -> List[Entity]:
        """Extract date entities"""
        entities = []
        
        # Check for date keywords
        for keyword in self.PATTERNS[EntityType.DATE]:
            if keyword in text_lower:
                # Try to extract date value
                date_value = self._extract_date_value(text)
                
                # Get context
                context = self._get_context(text, keyword)
                
                entities.append(Entity(
                    entity_type=EntityType.DATE,
                    text=text,
                    value=date_value,
                    context=context
                ))
        
        return entities
    
    def _extract_date_value(self, text: str) -> Optional[str]:
        """Extract date value from text"""
        # Pattern for dates: 2024-04-29, 29/4/2024, 29 april 2024, etc.
        patterns = [
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{1,2}/\d{1,2}/\d{4})',
            r'(\d{1,2}\s+(?:januari|februari|mars|april|maj|juni|juli|augusti|september|oktober|november|december)\s+\d{4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_promises(self, text: str, text_lower: str) -> List[Entity]:
        """Extract promise entities"""
        entities = []
        
        # Check for promise keywords
        for keyword in self.PATTERNS[EntityType.PROMISE]:
            if keyword in text_lower:
                # Get context
                context = self._get_context(text, keyword)
                
                entities.append(Entity(
                    entity_type=EntityType.PROMISE,
                    text=text,
                    context=context
                ))
        
        return entities
    
    def _extract_pain_points(self, text: str, text_lower: str) -> List[Entity]:
        """Extract pain point entities"""
        entities = []
        
        # Check for pain point keywords
        for keyword in self.PATTERNS[EntityType.PAIN_POINT]:
            if keyword in text_lower:
                # Get context
                context = self._get_context(text, keyword)
                
                entities.append(Entity(
                    entity_type=EntityType.PAIN_POINT,
                    text=text,
                    context=context
                ))
        
        return entities
    
    def _extract_personal_info(self, text: str, text_lower: str) -> List[Entity]:
        """Extract personal information entities"""
        entities = []
        
        # Check for personal info keywords
        for keyword in self.PATTERNS[EntityType.PERSONAL_INFO]:
            if keyword in text_lower:
                # Get context
                context = self._get_context(text, keyword)
                
                entities.append(Entity(
                    entity_type=EntityType.PERSONAL_INFO,
                    text=text,
                    context=context
                ))
        
        return entities
    
    def _get_context(self, text: str, keyword: str, window: int = 50) -> str:
        """
        Get surrounding text for context
        
        Args:
            text: Full text
            keyword: Keyword to find context for
            window: Number of characters before/after keyword
        
        Returns:
            Context string
        """
        text_lower = text.lower()
        keyword_lower = keyword.lower()
        
        index = text_lower.find(keyword_lower)
        if index == -1:
            return text[:100]  # Return first 100 chars if keyword not found
        
        start = max(0, index - window)
        end = min(len(text), index + len(keyword) + window)
        
        return text[start:end].strip()
    
    def classify_entity(self, text: str) -> Optional[EntityType]:
        """
        Classify entity type from text
        
        Args:
            text: Text to classify
        
        Returns:
            Entity type or None
        """
        text_lower = text.lower()
        
        for entity_type, keywords in self.PATTERNS.items():
            for keyword in keywords:
                if keyword in text_lower:
                    return entity_type
        
        return None


def main():
    """Test the Entity Extractor"""
    from loguru import logger
    
    logger.add("logs/entity_extractor_{time}.log", rotation="10 MB")
    
    # Create extractor
    config = EntityExtractorConfig()
    extractor = EntityExtractor(config)
    
    # Test transcriptions
    test_texts = [
        "Jag skickar offerten på måndag.",
        "Priset är 10 000 kronor.",
        "Vi har problem med ledtiderna.",
        "Jag ska på semester till Spanien.",
        "Det kostar 5 000 kr."
    ]
    
    for text in test_texts:
        entities = extractor.extract_entities(text)
        logger.info(f"Text: '{text}'")
        for entity in entities:
            logger.info(f"  - {entity.entity_type.value}: {entity.context}")
    
    logger.info("Entity Extractor test complete")


if __name__ == "__main__":
    main()
