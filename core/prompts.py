#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Prompts Manager
Dynamic prompt management with mood integration
"""

import json
from typing import Dict, Any, Optional
from pathlib import Path
import sys
from typing import Tuple

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from datetime import datetime, timezone
from pydantic import BaseModel, Field


class PersonaConfig(BaseModel):
    """Persona configuration for the agent"""
    name: str = Field(default="Anton", description="Agent name")
    role: str = Field(default="Senior Consultant", description="Agent role")
    tone: str = Field(default="Professional, friendly, and direct", description="Communication tone")
    language: str = Field(default="Swedish", description="Primary language")
    behaviors: List[str] = Field(default_factory=list, description="Behavioral guidelines")


class GuardrailConfig(BaseModel):
    """Guardrail configuration for safety"""
    restrictions: List[str] = Field(default_factory=list, description="Restricted topics/actions")
    data_leak_prevention: List[str] = Field(default_factory=list, description="Data leak prevention rules")
    conflict_resolution: str = Field(default="", description="Conflict resolution response")
    sensitive_topics: List[str] = Field(default_factory=list, description="Topics requiring follow-up")


class PromptsManager:
    """
    Manages agent prompts, persona, and guardrails
    Two layers of filters: Positive (personality) and Negative (guardrails)
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize prompts manager"""
        self.config_path = config_path or "config/system_prompts.json"
        
        # Initialize prompt injection guard
        self.injection_guard = PromptInjectionGuard()
        
        # Default persona
        self.persona = PersonaConfig(
            name="Anton",
            role="Senior Consultant",
            tone="Professional, friendly, and direct",
            language="Swedish",
            behaviors=[
                "Always verify information against knowledge base before answering",
                "If uncertain, admit it and suggest where to find the answer",
                "Be concise but thorough",
                "Maintain professional demeanor in all interactions",
                "Use clarifying questions to ensure understanding"
            ]
        )
        
        # Default guardrails
        self.guardrails = GuardrailConfig(
            restrictions=[
                "Never share confidential client information",
                "Never reveal internal company secrets",
                "Never make up information - stick to knowledge base",
                "Never engage in inappropriate or offensive content",
                "Never bypass security protocols"
            ],
            data_leak_prevention=[
                "Do not share document sources or metadata",
                "Do not reveal internal system architecture",
                "Do not disclose client names without explicit permission",
                "Do not share ingestion timestamps or file paths"
            ],
            conflict_resolution="Jag har noterat det du säger, låt mig dubbelkolla mot våra interna underlag och återkomma.",
            sensitive_topics=[
                "pricing strategy",
                "internal margins",
                "other client names",
                "confidential projects"
            ]
        )
        
        # Load from config if exists
        self.load_from_config()
        
        logger.info("Prompts Manager initialized")
    
    def load_from_config(self):
        """Load prompts from configuration file"""
        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Load persona
                if "positive" in config:
                    self.persona = PersonaConfig(
                        name=config["positive"].get("name", "Anton"),
                        role=config["positive"].get("role", "Senior Consultant"),
                        tone=config["positive"].get("tone", "Professional"),
                        behaviors=config["positive"].get("behavior", [])
                    )
                
                # Load guardrails
                if "negative" in config:
                    self.guardrails = GuardrailConfig(
                        restrictions=config["negative"].get("restrictions", []),
                        data_leak_prevention=config["negative"].get("data_leak_prevention", []),
                        conflict_resolution=config["negative"].get("conflict_resolution", ""),
                        sensitive_topics=config["negative"].get("sensitive_topics", [])
                    )
                
                logger.info(f"Loaded prompts from {self.config_path}")
                
        except Exception as e:
            logger.warning(f"Failed to load prompts from config: {e}")
    
    def build_system_prompt(self, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Build system prompt combining persona and guardrails
        
        Args:
            context: Additional context (emotion, agenda, etc.)
        
        Returns:
            Complete system prompt string
        """
        context = context or {}
        
        # Base persona prompt
        prompt_parts = [
            f"# System Instructions for {self.persona.name}",
            f"",
            f"## Persona",
            f"You are {self.persona.name}, a {self.persona.role}.",
            f"Your tone should be: {self.persona.tone}",
            f"Primary language: {self.persona.language}",
            f"",
            f"## Behavioral Guidelines",
        ]
        
        # Add behaviors
        for behavior in self.persona.behaviors:
            prompt_parts.append(f"- {behavior}")
        
        prompt_parts.append("")
        
        # Add guardrails
        prompt_parts.append("## Guardrails (STRICT - Never Violate)")
        for restriction in self.guardrails.restrictions:
            prompt_parts.append(f"- {restriction}")
        
        prompt_parts.append("")
        prompt_parts.append("## Data Leak Prevention")
        for rule in self.guardrails.data_leak_prevention:
            prompt_parts.append(f"- {rule}")
        
        # Add context if provided
        if context:
            prompt_parts.append("")
            prompt_parts.append("## Current Context")
            
            if "emotion" in context:
                prompt_parts.append(f"Detected Emotion: {context['emotion']}")
                # Add tone guidance based on emotion
                if context["emotion"].lower() in ["angry", "frustrated"]:
                    prompt_parts.append("Tone Adjustment: De-escalate, be empathetic, avoid confrontation")
                elif context["emotion"].lower() in ["happy", "excited"]:
                    prompt_parts.append("Tone Adjustment: Match enthusiasm, maintain professionalism")
            
            if "agenda" in context and context["agenda"]:
                prompt_parts.append(f"Meeting Agenda: {context['agenda'][:200]}...")
            
            if "recent_transcription" in context:
                prompt_parts.append(f"Recent Conversation: {context['recent_transcription'][:300]}...")
        
        prompt_parts.append("")
        
        # Add conflict resolution
        if self.guardrails.conflict_resolution:
            prompt_parts.append("## Conflict Resolution")
            prompt_parts.append(f"If there's a conflict between stated information and your knowledge, respond with:")
            prompt_parts.append(f'"{self.guardrails.conflict_resolution}"')
        
        prompt_parts.append("")
        
        # Add sensitive topics handling
        if self.guardrails.sensitive_topics:
            prompt_parts.append("## Sensitive Topics")
            prompt_parts.append("For the following topics, do not provide direct answers:")
            for topic in self.guardrails.sensitive_topics:
                prompt_parts.append(f"- {topic}")
            prompt_parts.append("Instead, say: 'Det där är en fråga jag behöver återkomma på efter mötet.'")
        
        return "\n".join(prompt_parts)
    
    def check_guardrails(self, response: str) -> tuple[bool, Optional[str]]:
        """
        Check if response violates guardrails
        
        Args:
            response: Generated response to check
        
        Returns:
            (is_safe, violation_reason)
        """
        # Check for sensitive topics
        for topic in self.guardrails.sensitive_topics:
            if topic.lower() in response.lower():
                return False, f"Response mentions sensitive topic: {topic}"
        
        # Check for data leaks (simple keyword check)
        leak_keywords = ["source file", "metadata", "timestamp", "file path", "document id"]
        for keyword in leak_keywords:
            if keyword.lower() in response.lower():
                return False, f"Response may leak data: {keyword}"
        
        # Check for inappropriate content (simple check)
        inappropriate_patterns = ["fuck", "shit", "damn", "hell"]
        for pattern in inappropriate_patterns:
            if pattern in response.lower():
                return False, f"Response contains inappropriate language"
        
        return True, None
    
    def sanitize_transcription(self, transcription: str) -> Tuple[bool, str]:
        """
        Sanitize transcription using prompt injection guard
        
        Args:
            transcription: Raw transcription
        
        Returns:
            (is_safe, sanitized_transcription)
        """
        is_safe, sanitized, reason = self.injection_guard.sanitize_input(transcription)
        
        if not is_safe:
            logger.error(f"Transcription blocked by injection guard: {reason}")
            return False, ""
        
        return True, sanitized
    
    def apply_tone_adjustment(self, emotion: str, base_response: str) -> str:
        """
        Adjust response tone based on detected emotion
        
        Args:
            emotion: Detected emotion
            base_response: Original response
        
        Returns:
            Tone-adjusted response
        """
        emotion_lower = emotion.lower()
        
        # Angry/Frustrated - add de-escalation
        if emotion_lower in ["angry", "frustrated", "annoyed"]:
            de_escalation_phrases = [
                "Jag förstår din oro.",
                "Låt oss se hur vi kan lösa detta tillsammans.",
                "Jag hör vad du säger och det är viktigt för mig."
            ]
            # Add de-escalation phrase at start
            phrase = de_escalation_phrases[hash(base_response) % len(de_escalation_phrases)]
            return f"{phrase} {base_response}"
        
        # Happy/Excited - add enthusiasm
        elif emotion_lower in ["happy", "excited", "joyful"]:
            enthusiasm_phrases = [
                "Det låter jättebra!",
                "Vad roligt att höra!",
                "Utmärkt!"
            ]
            phrase = enthusiasm_phrases[hash(base_response) % len(enthusiasm_phrases)]
            return f"{phrase} {base_response}"
        
        # Neutral/Sad - no adjustment needed
        return base_response
    
    # ─── Swenglish Buffer (Phase 7+) ───────────────────────────────────
    # Swedish business meetings naturally mix in ~10-15% English terms.
    # This module makes the agent sound like a modern Swedish consultant.
    
    SWENGLISH_TERMS = {
        # Business terms that are MORE natural in English in Swedish meetings
        "nyckeltal": "KPI:er",
        "färdplan": "roadmap",
        "leverabler": "deliverables",
        "intressenter": "stakeholders",
        "genomgång": "review",
        "tidsram": "timeline",
        "uppföljning": "follow-up",
        "kravspecifikation": "scope",
        "avkastning på investering": "ROI",
        "målgrupp": "target audience",
        "användarupplevelse": "UX",
        "slutprodukt": "output",
        "återkoppling": "feedback",
        "affärsmodell": "business case",
        "samarbetsverktyg": "collaboration tools",
        "tidslinje": "timeline",
        "leveransdatum": "deadline",
        "kapacitetsplanering": "resource planning",
        "vinkelrätt": "alignment",
        "slutanvändare": "end user",
    }
    
    # Phrases that sound more natural with English injection
    SWENGLISH_PHRASES = [
        ("Vi behöver gå igenom", "Vi behöver göra en quick review av"),
        ("Enligt planen", "Enligt vår roadmap"),
        ("Det ser bra ut", "Det ser bra ut, vi är on track"),
        ("Låt oss sammanfatta", "Låt oss göra en quick recap"),
        ("Jag kollar upp det", "Jag tar en action point på det"),
        ("Vi måste prioritera", "Vi måste prioritera, det är high prio"),
        ("Det påverkar tidsplanen", "Det impactar vår timeline"),
        ("Vi behöver mer information", "Vi behöver mer input på det"),
        ("Det stämmer", "Spot on"),
    ]
    
    def apply_swenglish_buffer(self, text: str, mix_ratio: float = 0.12) -> str:
        """
        Apply Swenglish Buffer to make text sound like a modern Swedish consultant.
        Replaces ~10-15% of formal Swedish terms with natural English business jargon.
        
        Args:
            text: Input text in Swedish
            mix_ratio: Target ratio of English terms (0.0-0.3, default 0.12 = 12%)
        
        Returns:
            Text with natural Swedish-English code-switching
        """
        import random
        
        result = text
        replacements_made = 0
        max_replacements = max(1, int(len(text.split()) * mix_ratio))
        
        # Shuffle terms to get random selection each time
        terms = list(self.SWENGLISH_TERMS.items())
        random.shuffle(terms)
        
        for swedish, english in terms:
            if replacements_made >= max_replacements:
                break
            if swedish.lower() in result.lower():
                # Case-insensitive replace (keep first occurrence only for naturalness)
                idx = result.lower().find(swedish.lower())
                if idx != -1:
                    result = result[:idx] + english + result[idx + len(swedish):]
                    replacements_made += 1
        
        # Apply phrase-level substitutions (max 1 per response for subtlety)
        phrases = list(self.SWENGLISH_PHRASES)
        random.shuffle(phrases)
        for swedish_phrase, english_phrase in phrases[:1]:
            if swedish_phrase.lower() in result.lower():
                idx = result.lower().find(swedish_phrase.lower())
                if idx != -1:
                    result = result[:idx] + english_phrase + result[idx + len(swedish_phrase):]
                    break
        
        return result
    
    def get_sensitive_topic_response(self) -> str:
        """Get standard response for sensitive topics"""
        return "Det där är en fråga jag behöver återkomma på efter mötet."
    
    def get_conflict_resolution_response(self) -> str:
        """Get conflict resolution response"""
        return self.guardrails.conflict_resolution or self.get_sensitive_topic_response()
    
    def update_persona(self, persona: PersonaConfig):
        """Update persona configuration"""
        self.persona = persona
        logger.info(f"Persona updated: {persona.name}")
    
    def update_guardrails(self, guardrails: GuardrailConfig):
        """Update guardrails configuration"""
        self.guardrails = guardrails
        logger.info("Guardrails updated")
    
    def save_to_config(self):
        """Save current configuration to file"""
        try:
            config = {
                "positive": {
                    "name": self.persona.name,
                    "role": self.persona.role,
                    "tone": self.persona.tone,
                    "behavior": self.persona.behaviors
                },
                "negative": {
                    "restrictions": self.guardrails.restrictions,
                    "data_leak_prevention": self.guardrails.data_leak_prevention,
                    "conflict_resolution": self.guardrails.conflict_resolution,
                    "sensitive_topics": self.guardrails.sensitive_topics
                }
            }
            
            config_file = Path(self.config_path)
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved prompts to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save prompts: {e}")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get summary of current configuration"""
        return {
            "persona": {
                "name": self.persona.name,
                "role": self.persona.role,
                "tone": self.persona.tone,
                "num_behaviors": len(self.persona.behaviors)
            },
            "guardrails": {
                "num_restrictions": len(self.guardrails.restrictions),
                "num_data_leak_rules": len(self.guardrails.data_leak_prevention),
                "has_conflict_resolution": bool(self.guardrails.conflict_resolution),
                "num_sensitive_topics": len(self.guardrails.sensitive_topics)
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test the prompts manager"""
    from loguru import logger
    
    logger.add("logs/prompts_{time}.log", rotation="10 MB")
    
    # Create prompts manager
    manager = PromptsManager()
    
    # Build system prompt
    context = {
        "emotion": "Neutral",
        "agenda": "Discuss project timeline",
        "recent_transcription": "What do you think about the deadline?"
    }
    
    system_prompt = manager.build_system_prompt(context)
    logger.info(f"System prompt:\n{system_prompt}")
    
    # Check guardrails
    test_response = "Based on the source file, the price is 1000 SEK"
    is_safe, reason = manager.check_guardrails(test_response)
    logger.info(f"Guardrail check: {is_safe}, reason: {reason}")
    
    # Tone adjustment
    adjusted = manager.apply_tone_adjustment("Happy", "That sounds good.")
    logger.info(f"Tone adjusted: {adjusted}")
    
    # Config summary
    logger.info(f"Config summary: {manager.get_config_summary()}")


if __name__ == "__main__":
    asyncio.run(main())
