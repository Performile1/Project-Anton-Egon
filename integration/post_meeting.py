#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Post-Meeting Automation
Automatic summary generation and memory updates
"""

import asyncio
import sys
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
from pydantic import BaseModel, Field


class PostMeetingConfig(BaseModel):
    """Configuration for post-meeting automation"""
    auto_summary: bool = Field(default=True, description="Auto-generate meeting summary")
    ask_memory_update: bool = Field(default=True, description="Ask for memory update")
    summary_path: str = Field(default="memory/meeting/summary.md", description="Summary output path")
    notes_path: str = Field(default="memory/meeting/previous_notes.txt", description="Notes output path")


class PostMeetingAutomation:
    """
    Post-meeting automation
    Generates summary and asks for memory update
    """
    
    def __init__(self, config: PostMeetingConfig):
        """Initialize post-meeting automation"""
        self.config = config
        
        logger.info("Post-Meeting Automation initialized")
    
    def generate_summary(self, context: Dict[str, Any]) -> str:
        """
        Generate meeting summary
        
        Args:
            context: Meeting context (transcriptions, emotions, etc.)
        
        Returns:
            Generated summary markdown
        """
        try:
            transcriptions = context.get("transcriptions", [])
            emotions = context.get("emotions", {})
            names = context.get("names", [])
            keywords = context.get("keywords", [])
            
            summary_lines = []
            summary_lines.append(f"# Meeting Summary")
            summary_lines.append(f"\n**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
            summary_lines.append(f"**Time:** {datetime.now(timezone.utc).strftime('%H:%M:%S')} UTC")
            summary_lines.append(f"\n---")
            
            # Attendees
            if names:
                summary_lines.append("## Attendees")
                for name in names:
                    summary_lines.append(f"- {name}")
                summary_lines.append("")
            
            # Key Points
            if transcriptions:
                summary_lines.append("## Key Discussion Points")
                # Take first 10 transcriptions as key points
                for i, trans in enumerate(transcriptions[:10]):
                    summary_lines.append(f"{i+1}. {trans}")
                summary_lines.append("")
            
            # Emotions
            if emotions:
                summary_lines.append("## Emotional Atmosphere")
                for person, emotion in emotions.items():
                    summary_lines.append(f"- {person}: {emotion}")
                summary_lines.append("")
            
            # Keywords
            if keywords:
                summary_lines.append("## Key Topics")
                summary_lines.append(", ".join(keywords))
                summary_lines.append("")
            
            # Action Items
            summary_lines.append("## Action Items")
            summary_lines.append("- Review meeting notes")
            summary_lines.append("- Follow up on discussed topics")
            summary_lines.append("")
            
            return "\n".join(summary_lines)
            
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return ""
    
    def save_summary(self, summary: str):
        """
        Save summary to file
        
        Args:
            summary: Summary markdown content
        """
        try:
            summary_path = Path(self.config.summary_path)
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(summary)
            
            logger.info(f"Summary saved to {self.config.summary_path}")
            
        except Exception as e:
            logger.error(f"Failed to save summary: {e}")
    
    def update_notes(self, context: Dict[str, Any]):
        """
        Update meeting notes
        
        Args:
            context: Meeting context
        """
        try:
            notes_path = Path(self.config.notes_path)
            notes_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Append new notes
            with open(notes_path, 'a', encoding='utf-8') as f:
                f.write(f"\n\n--- Meeting ended at {datetime.now(timezone.utc).strftime('%H:%M:%S')} ---\n")
                f.write("Auto-generated notes:\n")
                f.write(f"Total transcriptions: {len(context.get('transcriptions', []))}\n")
                f.write(f"Detected emotions: {list(context.get('emotions', {}).keys())}\n")
            
            logger.info(f"Notes updated in {self.config.notes_path}")
            
        except Exception as e:
            logger.error(f"Failed to update notes: {e}")
    
    def ask_memory_update(self, learned_info: List[str]) -> bool:
        """
        Ask user for memory update confirmation
        
        Args:
            learned_info: List of information learned during meeting
        
        Returns:
            True if user confirms memory update
        """
        if not learned_info:
            return False
        
        print("\n" + "="*80)
        print("POST-MEETING: Memory Update")
        print("="*80)
        print("\nI learned the following during the meeting:")
        for i, info in enumerate(learned_info, 1):
            print(f"{i}. {info}")
        
        print("\nShould I save this information to long-term memory? (y/n)")
        
        # In production, this would be a GUI dialog
        # For now, return False to avoid blocking
        return False
    
    def process_meeting_end(self, context: Dict[str, Any]):
        """
        Process meeting end
        
        Args:
            context: Meeting context
        """
        logger.info("Processing meeting end...")
        
        # Generate summary
        if self.config.auto_summary:
            summary = self.generate_summary(context)
            if summary:
                self.save_summary(summary)
        
        # Update notes
        self.update_notes(context)
        
        # Ask for memory update
        if self.config.ask_memory_update:
            learned_info = self._extract_learned_info(context)
            if learned_info:
                self.ask_memory_update(learned_info)
        
        logger.info("Post-meeting processing complete")
    
    def _extract_learned_info(self, context: Dict[str, Any]) -> List[str]:
        """
        Extract learned information from context
        
        Args:
            context: Meeting context
        
        Returns:
            List of learned information
        """
        learned = []
        
        # Extract from keywords
        keywords = context.get("keywords", [])
        for keyword in keywords:
            if keyword.lower() in ["budget", "price", "cost", "timeline", "deadline"]:
                learned.append(f"Discussed {keyword}")
        
        # Extract from transcriptions (simple heuristic)
        transcriptions = context.get("transcriptions", [])
        for trans in transcriptions:
            if "ny" in trans.lower() or "nytt" in trans.lower():
                learned.append(f"New information: {trans[:50]}...")
        
        return learned
    
    def get_status(self) -> Dict[str, Any]:
        """Get current automation status"""
        return {
            "auto_summary": self.config.auto_summary,
            "ask_memory_update": self.config.ask_memory_update,
            "summary_path": self.config.summary_path,
            "notes_path": self.config.notes_path,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def main():
    """Test the post-meeting automation"""
    from loguru import logger
    
    logger.add("logs/post_meeting_{time}.log", rotation="10 MB")
    
    # Create post-meeting automation
    config = PostMeetingConfig()
    automation = PostMeetingAutomation(config)
    
    # Test context
    test_context = {
        "transcriptions": [
            "Hej, hur är det?",
            "Vi behöver diskutera budgeten",
            "Det nya priset är 5000 SEK"
        ],
        "emotions": {"Lasse": "Happy", "Anna": "Neutral"},
        "names": ["Lasse", "Anna"],
        "keywords": ["budget", "price", "ny"]
    }
    
    # Test summary generation
    summary = automation.generate_summary(test_context)
    print("Generated Summary:")
    print(summary)
    
    # Test status
    status = automation.get_status()
    logger.info(f"Post-Meeting Automation status: {status}")


if __name__ == "__main__":
    main()
