#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Strategic Lag: Complexity Delay
Adds human-like thinking delays before responses based on question complexity.
Triggers "thinking actions" (look up, clear throat, pause) to avoid unnaturally fast responses.
"""

import sys
import re
import random
import asyncio
from typing import Optional, Dict, Any, List, Callable
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class QuestionComplexity(Enum):
    """Question complexity levels"""
    SIMPLE = "simple"          # "Ja/Nej" questions - 0.3-0.8s delay
    MODERATE = "moderate"      # Regular questions - 0.8-1.5s delay
    COMPLEX = "complex"        # Numbers, history, analysis - 1.5-3.0s delay
    VERY_COMPLEX = "very_complex"  # Multi-part or strategic questions - 2.5-4.0s delay


class ThinkingAction(Enum):
    """Visible "thinking" actions to trigger during delay"""
    LOOK_UP = "look_up"               # Look up slightly (pondering)
    HEAD_TILT = "head_tilt"            # Slight head tilt
    CLEAR_THROAT = "clear_throat"      # "Hmm" + throat clear
    SQUINT = "squint"                  # Slight squint (concentrating)
    BRIEF_NOD = "brief_nod"            # Brief nod before answering
    TOUCH_CHIN = "touch_chin"          # Touch chin (thinking gesture)


class ComplexityDelayConfig(BaseModel):
    """Configuration for Complexity Delay"""
    enabled: bool = Field(default=True, description="Enable complexity delay")
    base_delay_simple: float = Field(default=0.3, description="Min delay for simple questions (seconds)")
    max_delay_simple: float = Field(default=0.8, description="Max delay for simple questions (seconds)")
    base_delay_moderate: float = Field(default=0.8, description="Min delay for moderate questions")
    max_delay_moderate: float = Field(default=1.5, description="Max delay for moderate questions")
    base_delay_complex: float = Field(default=1.5, description="Min delay for complex questions")
    max_delay_complex: float = Field(default=3.0, description="Max delay for complex questions")
    base_delay_very_complex: float = Field(default=2.5, description="Min delay for very complex questions")
    max_delay_very_complex: float = Field(default=4.0, description="Max delay for very complex questions")
    add_filler_words: bool = Field(default=True, description="Add 'hmm', 'eh' before complex answers")
    trigger_thinking_action: bool = Field(default=True, description="Trigger visible thinking actions")


class ComplexityDelay:
    """
    Strategic Lag - Complexity Delay
    Makes the agent respond at human-realistic speeds by analyzing question complexity
    and inserting appropriate thinking delays with visible "thinking" body language.
    """
    
    # Keywords that indicate complexity
    COMPLEXITY_INDICATORS = {
        "numbers": [
            "hur mycket", "hur många", "procent", "%", "siffror", "antal",
            "kostnad", "pris", "budget", "kronor", "kr", "sek",
            "how much", "how many", "percent", "number"
        ],
        "history": [
            "förra", "senast", "tidigare", "historik", "minns du",
            "sist vi", "förra mötet", "som du sa", "last time",
            "previously", "remember"
        ],
        "analysis": [
            "varför", "analysera", "jämför", "bedöm", "utvärdera",
            "vad tycker du", "din åsikt", "rekommenderar", "föreslår",
            "why", "analyze", "compare", "evaluate", "recommend"
        ],
        "multi_part": [
            " och ", " samt ", " dessutom ", " plus ", " också ",
            "för det första", "tre saker", "and also", "furthermore"
        ]
    }
    
    # Filler words/sounds for thinking
    FILLER_WORDS = [
        "Hmm...",
        "Eh...",
        "Låt mig tänka...",
        "Bra fråga...",
        "Ah...",
        "Ja, just det...",
        "Mm...",
    ]
    
    def __init__(self, config: ComplexityDelayConfig, on_thinking_action: Optional[Callable] = None):
        """
        Initialize Complexity Delay
        
        Args:
            config: Complexity Delay configuration
            on_thinking_action: Callback to trigger visible thinking action in video
        """
        self.config = config
        self.on_thinking_action = on_thinking_action
        
        logger.info("Complexity Delay initialized")
    
    def analyze_complexity(self, question: str) -> QuestionComplexity:
        """
        Analyze question complexity
        
        Args:
            question: Question text
        
        Returns:
            Complexity level
        """
        question_lower = question.lower()
        score = 0
        
        # Check for number-related keywords
        for keyword in self.COMPLEXITY_INDICATORS["numbers"]:
            if keyword in question_lower:
                score += 2
                break
        
        # Check for history-related keywords
        for keyword in self.COMPLEXITY_INDICATORS["history"]:
            if keyword in question_lower:
                score += 2
                break
        
        # Check for analysis-related keywords
        for keyword in self.COMPLEXITY_INDICATORS["analysis"]:
            if keyword in question_lower:
                score += 3
                break
        
        # Check for multi-part indicators
        for keyword in self.COMPLEXITY_INDICATORS["multi_part"]:
            if keyword in question_lower:
                score += 2
                break
        
        # Question length adds complexity
        word_count = len(question.split())
        if word_count > 20:
            score += 2
        elif word_count > 10:
            score += 1
        
        # Question mark count (multiple questions)
        question_marks = question.count("?")
        if question_marks > 1:
            score += 2
        
        # Classify
        if score >= 7:
            return QuestionComplexity.VERY_COMPLEX
        elif score >= 4:
            return QuestionComplexity.COMPLEX
        elif score >= 2:
            return QuestionComplexity.MODERATE
        else:
            return QuestionComplexity.SIMPLE
    
    def calculate_delay(self, complexity: QuestionComplexity) -> float:
        """
        Calculate thinking delay for complexity level
        
        Args:
            complexity: Question complexity
        
        Returns:
            Delay in seconds
        """
        if not self.config.enabled:
            return 0.0
        
        if complexity == QuestionComplexity.SIMPLE:
            return random.uniform(self.config.base_delay_simple, self.config.max_delay_simple)
        elif complexity == QuestionComplexity.MODERATE:
            return random.uniform(self.config.base_delay_moderate, self.config.max_delay_moderate)
        elif complexity == QuestionComplexity.COMPLEX:
            return random.uniform(self.config.base_delay_complex, self.config.max_delay_complex)
        elif complexity == QuestionComplexity.VERY_COMPLEX:
            return random.uniform(self.config.base_delay_very_complex, self.config.max_delay_very_complex)
        
        return 0.5
    
    def get_thinking_action(self, complexity: QuestionComplexity) -> ThinkingAction:
        """
        Select a thinking action appropriate for complexity level
        
        Args:
            complexity: Question complexity
        
        Returns:
            Thinking action to trigger
        """
        if complexity == QuestionComplexity.SIMPLE:
            actions = [ThinkingAction.BRIEF_NOD]
        elif complexity == QuestionComplexity.MODERATE:
            actions = [ThinkingAction.BRIEF_NOD, ThinkingAction.HEAD_TILT]
        elif complexity == QuestionComplexity.COMPLEX:
            actions = [ThinkingAction.LOOK_UP, ThinkingAction.SQUINT, ThinkingAction.TOUCH_CHIN]
        else:
            actions = [ThinkingAction.LOOK_UP, ThinkingAction.TOUCH_CHIN, ThinkingAction.CLEAR_THROAT]
        
        return random.choice(actions)
    
    def get_filler_word(self, complexity: QuestionComplexity) -> Optional[str]:
        """
        Get a filler word appropriate for complexity
        
        Args:
            complexity: Question complexity
        
        Returns:
            Filler word or None (simple questions don't get fillers)
        """
        if not self.config.add_filler_words:
            return None
        
        if complexity == QuestionComplexity.SIMPLE:
            return None
        
        # More complex = more likely to use filler
        if complexity == QuestionComplexity.MODERATE and random.random() > 0.5:
            return None
        
        return random.choice(self.FILLER_WORDS)
    
    async def apply_delay(self, question: str) -> Dict[str, Any]:
        """
        Analyze question and apply appropriate delay with thinking actions
        
        Args:
            question: Question text
        
        Returns:
            Delay info dictionary
        """
        # Analyze complexity
        complexity = self.analyze_complexity(question)
        
        # Calculate delay
        delay = self.calculate_delay(complexity)
        
        # Get thinking action
        thinking_action = self.get_thinking_action(complexity)
        
        # Get filler word
        filler = self.get_filler_word(complexity)
        
        # Trigger thinking action in video pipeline
        if self.config.trigger_thinking_action and self.on_thinking_action:
            self.on_thinking_action({
                "action": thinking_action.value,
                "duration": delay,
                "complexity": complexity.value
            })
        
        # Apply delay
        if delay > 0:
            logger.debug(f"Thinking delay: {delay:.1f}s ({complexity.value}) - action: {thinking_action.value}")
            await asyncio.sleep(delay)
        
        return {
            "complexity": complexity.value,
            "delay_seconds": round(delay, 2),
            "thinking_action": thinking_action.value,
            "filler_word": filler
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get delay status
        
        Returns:
            Status dictionary
        """
        return {
            "enabled": self.config.enabled,
            "add_filler_words": self.config.add_filler_words,
            "trigger_thinking_action": self.config.trigger_thinking_action,
            "delay_ranges": {
                "simple": f"{self.config.base_delay_simple}-{self.config.max_delay_simple}s",
                "moderate": f"{self.config.base_delay_moderate}-{self.config.max_delay_moderate}s",
                "complex": f"{self.config.base_delay_complex}-{self.config.max_delay_complex}s",
                "very_complex": f"{self.config.base_delay_very_complex}-{self.config.max_delay_very_complex}s"
            }
        }


async def main():
    """Test the Complexity Delay"""
    from loguru import logger
    
    logger.add("logs/complexity_delay_{time}.log", rotation="10 MB")
    
    def on_thinking_action(action_data):
        logger.info(f"🤔 Thinking action: {action_data}")
    
    # Create delay
    config = ComplexityDelayConfig()
    delay = ComplexityDelay(config, on_thinking_action=on_thinking_action)
    
    # Test questions
    test_questions = [
        "Ja?",
        "Kan du skicka det?",
        "Hur mycket kostar det per enhet?",
        "Varför föreslår du det och hur många procent rabatt kan vi ge? Och vad sa Lasse förra mötet?",
        "Vad tycker du om vår budget jämfört med förra kvartalets siffror?",
    ]
    
    for question in test_questions:
        complexity = delay.analyze_complexity(question)
        logger.info(f"\nQ: '{question}'")
        logger.info(f"  Complexity: {complexity.value}")
        
        result = await delay.apply_delay(question)
        logger.info(f"  Delay: {result['delay_seconds']}s | Action: {result['thinking_action']} | Filler: {result['filler_word']}")
    
    # Get status
    status = delay.get_status()
    logger.info(f"\nStatus: {status}")
    
    logger.info("Complexity Delay test complete")


if __name__ == "__main__":
    asyncio.run(main())
