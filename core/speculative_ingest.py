#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Speculative Ingest
Predictive RAG search + Intent Recognition from partial transcriptions.
Starts preparing answers BEFORE the question is fully spoken.
"""

import sys
import asyncio
import re
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime, timezone
from enum import Enum
from collections import deque

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class Intent(Enum):
    """Recognized intents from partial speech"""
    PRICE_INQUIRY = "price_inquiry"
    BUDGET_QUESTION = "budget_question"
    TIMELINE_QUESTION = "timeline_question"
    TECHNICAL_QUESTION = "technical_question"
    OPINION_REQUEST = "opinion_request"
    HISTORY_RECALL = "history_recall"
    PERSONAL_QUESTION = "personal_question"
    CONFIRMATION = "confirmation"
    OBJECTION = "objection"
    UNKNOWN = "unknown"


class SpeculativeResult(BaseModel):
    """Result from speculative analysis"""
    intent: str
    confidence: float = Field(default=0.0, description="Intent confidence (0-1)")
    keywords: List[str] = Field(default_factory=list, description="Detected keywords")
    rag_queries: List[str] = Field(default_factory=list, description="Pre-prepared RAG queries")
    draft_context: Optional[str] = Field(None, description="Pre-fetched context from vault")
    word_count_at_trigger: int = Field(default=0, description="Words seen when intent triggered")


class SpeculativeIngestConfig(BaseModel):
    """Configuration for Speculative Ingest"""
    enabled: bool = Field(default=True, description="Enable speculative ingest")
    min_words_for_intent: int = Field(default=3, description="Min words before attempting intent recognition")
    intent_confidence_threshold: float = Field(default=0.6, description="Min confidence to act on intent")
    max_speculative_queries: int = Field(default=3, description="Max parallel RAG queries to prepare")
    draft_timeout_seconds: float = Field(default=2.0, description="Max time to wait for draft context")


# Intent trigger patterns: keyword → (intent, confidence_boost)
INTENT_PATTERNS = {
    # Price / Budget
    "pris": (Intent.PRICE_INQUIRY, 0.7),
    "kostar": (Intent.PRICE_INQUIRY, 0.8),
    "kostnad": (Intent.PRICE_INQUIRY, 0.8),
    "offert": (Intent.PRICE_INQUIRY, 0.7),
    "budget": (Intent.BUDGET_QUESTION, 0.8),
    "investering": (Intent.BUDGET_QUESTION, 0.7),
    "kronor": (Intent.PRICE_INQUIRY, 0.6),
    "rabatt": (Intent.PRICE_INQUIRY, 0.7),
    
    # Timeline
    "deadline": (Intent.TIMELINE_QUESTION, 0.8),
    "leverans": (Intent.TIMELINE_QUESTION, 0.7),
    "tidsplan": (Intent.TIMELINE_QUESTION, 0.8),
    "schema": (Intent.TIMELINE_QUESTION, 0.6),
    "vecka": (Intent.TIMELINE_QUESTION, 0.5),
    "datum": (Intent.TIMELINE_QUESTION, 0.6),
    "färdig": (Intent.TIMELINE_QUESTION, 0.6),
    
    # Technical
    "teknisk": (Intent.TECHNICAL_QUESTION, 0.7),
    "implementation": (Intent.TECHNICAL_QUESTION, 0.7),
    "integration": (Intent.TECHNICAL_QUESTION, 0.7),
    "api": (Intent.TECHNICAL_QUESTION, 0.8),
    "server": (Intent.TECHNICAL_QUESTION, 0.6),
    "databas": (Intent.TECHNICAL_QUESTION, 0.7),
    
    # Opinion
    "tycker": (Intent.OPINION_REQUEST, 0.7),
    "åsikt": (Intent.OPINION_REQUEST, 0.8),
    "rekommenderar": (Intent.OPINION_REQUEST, 0.7),
    "föreslår": (Intent.OPINION_REQUEST, 0.7),
    "bästa": (Intent.OPINION_REQUEST, 0.6),
    
    # History / Recall
    "förra": (Intent.HISTORY_RECALL, 0.6),
    "senast": (Intent.HISTORY_RECALL, 0.6),
    "tidigare": (Intent.HISTORY_RECALL, 0.6),
    "minns": (Intent.HISTORY_RECALL, 0.8),
    "sist": (Intent.HISTORY_RECALL, 0.6),
    
    # Confirmation
    "stämmer": (Intent.CONFIRMATION, 0.7),
    "korrekt": (Intent.CONFIRMATION, 0.7),
    "rätt": (Intent.CONFIRMATION, 0.5),
    
    # Objection
    "men": (Intent.OBJECTION, 0.3),
    "dock": (Intent.OBJECTION, 0.4),
    "problem": (Intent.OBJECTION, 0.6),
    "svårt": (Intent.OBJECTION, 0.5),
    "dyrt": (Intent.OBJECTION, 0.7),
}

# RAG query templates per intent
RAG_QUERY_TEMPLATES = {
    Intent.PRICE_INQUIRY: [
        "priser kostnader offert",
        "prismodell per enhet",
        "rabatter volympriser"
    ],
    Intent.BUDGET_QUESTION: [
        "budget projekt kostnad",
        "budgetfördelning kvartal",
        "ekonomisk plan"
    ],
    Intent.TIMELINE_QUESTION: [
        "tidsplan leverans deadline",
        "projektplan milstolpar",
        "schema leveransdatum"
    ],
    Intent.TECHNICAL_QUESTION: [
        "teknisk specifikation",
        "implementation integration",
        "systemarkitektur"
    ],
    Intent.HISTORY_RECALL: [
        "senaste mötet beslut",
        "tidigare diskussion",
        "historik överenskommelse"
    ],
    Intent.OPINION_REQUEST: [
        "rekommendation bästa praxis",
        "förslag strategi",
        "analys bedömning"
    ],
}


class SpeculativeIngest:
    """
    Speculative Ingest Engine
    Analyzes partial transcriptions in real-time to predict intent
    and pre-fetch relevant context before the question is complete.
    """
    
    def __init__(
        self,
        config: SpeculativeIngestConfig,
        on_intent_detected: Optional[Callable] = None,
        on_context_ready: Optional[Callable] = None
    ):
        """
        Initialize Speculative Ingest
        
        Args:
            config: Configuration
            on_intent_detected: Callback when intent is recognized
            on_context_ready: Callback when draft context is pre-fetched
        """
        self.config = config
        self.on_intent_detected = on_intent_detected
        self.on_context_ready = on_context_ready
        
        # State
        self.current_words: List[str] = []
        self.current_intent: Optional[Intent] = None
        self.current_confidence: float = 0.0
        self.speculative_result: Optional[SpeculativeResult] = None
        self.is_processing: bool = False
        
        # History for draft-and-verify
        self.draft_queue: deque = deque(maxlen=5)
        
        logger.info("Speculative Ingest initialized")
    
    def feed_word(self, word: str) -> Optional[SpeculativeResult]:
        """
        Feed a single word from streaming transcription.
        Called every time Whisper produces a new word.
        
        Args:
            word: New word from transcription stream
        
        Returns:
            SpeculativeResult if intent was recognized, None otherwise
        """
        if not self.config.enabled:
            return None
        
        self.current_words.append(word.lower().strip())
        
        # Need minimum words before analysis
        if len(self.current_words) < self.config.min_words_for_intent:
            return None
        
        # Analyze intent from accumulated words
        result = self._analyze_intent()
        
        if result and result.confidence >= self.config.intent_confidence_threshold:
            self.speculative_result = result
            self.current_intent = Intent(result.intent)
            self.current_confidence = result.confidence
            
            # Trigger callback
            if self.on_intent_detected:
                self.on_intent_detected(result.dict())
            
            logger.info(f"Intent detected: {result.intent} ({result.confidence:.0%}) after {len(self.current_words)} words")
            
            return result
        
        return None
    
    def feed_chunk(self, text_chunk: str) -> Optional[SpeculativeResult]:
        """
        Feed a text chunk (multiple words) from transcription.
        
        Args:
            text_chunk: Text chunk from Whisper
        
        Returns:
            SpeculativeResult if intent recognized
        """
        words = text_chunk.strip().split()
        result = None
        
        for word in words:
            r = self.feed_word(word)
            if r is not None:
                result = r  # Return latest match
        
        return result
    
    def _analyze_intent(self) -> Optional[SpeculativeResult]:
        """
        Analyze accumulated words for intent
        
        Returns:
            SpeculativeResult or None
        """
        detected_intents: Dict[Intent, float] = {}
        detected_keywords: List[str] = []
        
        for word in self.current_words:
            if word in INTENT_PATTERNS:
                intent, confidence = INTENT_PATTERNS[word]
                
                # Accumulate confidence for same intent
                if intent in detected_intents:
                    detected_intents[intent] = min(1.0, detected_intents[intent] + confidence * 0.3)
                else:
                    detected_intents[intent] = confidence
                
                detected_keywords.append(word)
        
        if not detected_intents:
            return None
        
        # Pick highest confidence intent
        best_intent = max(detected_intents, key=detected_intents.get)
        best_confidence = detected_intents[best_intent]
        
        # Question mark boosts confidence
        full_text = " ".join(self.current_words)
        if "?" in full_text:
            best_confidence = min(1.0, best_confidence + 0.1)
        
        # Prepare RAG queries
        rag_queries = self._prepare_rag_queries(best_intent, detected_keywords)
        
        return SpeculativeResult(
            intent=best_intent.value,
            confidence=best_confidence,
            keywords=detected_keywords,
            rag_queries=rag_queries,
            word_count_at_trigger=len(self.current_words)
        )
    
    def _prepare_rag_queries(self, intent: Intent, keywords: List[str]) -> List[str]:
        """
        Prepare RAG queries based on intent and keywords
        
        Args:
            intent: Detected intent
            keywords: Detected keywords
        
        Returns:
            List of RAG query strings
        """
        queries = []
        
        # Get template queries for intent
        templates = RAG_QUERY_TEMPLATES.get(intent, [])
        queries.extend(templates[:self.config.max_speculative_queries])
        
        # Add keyword-based query
        if keywords:
            keyword_query = " ".join(keywords)
            queries.append(keyword_query)
        
        return queries[:self.config.max_speculative_queries]
    
    async def prefetch_context(self, rag_search_fn: Callable) -> Optional[str]:
        """
        Pre-fetch context from vault using speculative RAG queries.
        Call this with your actual RAG search function.
        
        Args:
            rag_search_fn: Async function that takes a query string and returns results
        
        Returns:
            Pre-fetched context string or None
        """
        if not self.speculative_result or not self.speculative_result.rag_queries:
            return None
        
        self.is_processing = True
        
        try:
            # Run queries in parallel with timeout
            tasks = [
                asyncio.wait_for(
                    rag_search_fn(query),
                    timeout=self.config.draft_timeout_seconds
                )
                for query in self.speculative_result.rag_queries
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine valid results
            context_parts = []
            for result in results:
                if isinstance(result, str) and result:
                    context_parts.append(result)
                elif isinstance(result, list):
                    for item in result:
                        if isinstance(item, str):
                            context_parts.append(item)
            
            if context_parts:
                draft_context = "\n".join(context_parts[:3])  # Max 3 context chunks
                self.speculative_result.draft_context = draft_context
                
                # Trigger callback
                if self.on_context_ready:
                    self.on_context_ready({
                        "intent": self.speculative_result.intent,
                        "context": draft_context[:500],
                        "queries_used": len(self.speculative_result.rag_queries)
                    })
                
                logger.info(f"Pre-fetched context ready ({len(draft_context)} chars)")
                return draft_context
            
            return None
            
        except Exception as e:
            logger.error(f"Prefetch error: {e}")
            return None
        finally:
            self.is_processing = False
    
    def get_draft_context(self) -> Optional[str]:
        """
        Get pre-fetched draft context (if available)
        
        Returns:
            Draft context or None
        """
        if self.speculative_result and self.speculative_result.draft_context:
            return self.speculative_result.draft_context
        return None
    
    def reset(self):
        """Reset state for new utterance"""
        self.current_words = []
        self.current_intent = None
        self.current_confidence = 0.0
        self.speculative_result = None
        self.is_processing = False
    
    def invalidate_draft(self):
        """
        Invalidate current draft (user changed direction mid-sentence).
        Called when intent changes significantly.
        """
        if self.speculative_result:
            logger.info(f"Draft invalidated (was: {self.speculative_result.intent})")
            self.draft_queue.append(self.speculative_result)
            self.speculative_result = None
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get engine status
        
        Returns:
            Status dictionary
        """
        return {
            "enabled": self.config.enabled,
            "current_words": len(self.current_words),
            "current_intent": self.current_intent.value if self.current_intent else None,
            "current_confidence": round(self.current_confidence, 2),
            "has_draft_context": bool(self.speculative_result and self.speculative_result.draft_context),
            "is_processing": self.is_processing,
            "drafts_invalidated": len(self.draft_queue)
        }


def main():
    """Test the Speculative Ingest"""
    from loguru import logger
    
    logger.add("logs/speculative_ingest_{time}.log", rotation="10 MB")
    
    def on_intent(data):
        logger.info(f"🎯 Intent: {data['intent']} ({data['confidence']:.0%})")
        logger.info(f"   Keywords: {data['keywords']}")
        logger.info(f"   RAG queries: {data['rag_queries']}")
    
    # Create engine
    config = SpeculativeIngestConfig()
    engine = SpeculativeIngest(config, on_intent_detected=on_intent)
    
    # Simulate streaming transcription: "Vad har vi för budget för projektet?"
    test_sentences = [
        "Vad har vi för budget för projektet?",
        "Hur mycket kostar det per enhet?",
        "Kan du visa mig tidsplanen?",
        "Vad sa Lasse förra mötet om leveransen?",
        "Jag tycker det är för dyrt",
    ]
    
    for sentence in test_sentences:
        engine.reset()
        logger.info(f"\n--- Streaming: '{sentence}' ---")
        
        words = sentence.split()
        for i, word in enumerate(words):
            result = engine.feed_word(word)
            if result:
                logger.info(f"   → Intent after word {i+1}/{len(words)}: {result.intent}")
    
    # Get status
    status = engine.get_status()
    logger.info(f"\nStatus: {status}")
    
    logger.info("Speculative Ingest test complete")


if __name__ == "__main__":
    main()
