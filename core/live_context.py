#!/usr/bin/env python3
"""
Project Anton Egon - Phase 11: Live Context (Active RAG)
Short-term priority memory that trumps all /vault data.
Supports slide-sync, live injection, and document pinning.
"""

import asyncio
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field


class ContextPriority(Enum):
    """Priority levels for live context items"""
    CRITICAL = "critical"      # Operator live injection → always wins
    SLIDE = "slide"            # Current slide content → high priority
    DOCUMENT = "document"      # Pinned document section → medium-high
    SESSION = "session"        # Session-level notes → medium
    BACKGROUND = "background"  # General context → lowest


class SlideState(BaseModel):
    """Tracks current presentation state"""
    document_name: str = ""
    total_slides: int = 0
    current_slide: int = 0
    slide_content: str = ""
    slide_notes: str = ""
    pinned: bool = False


class LiveInjection(BaseModel):
    """A live text injection from the operator"""
    text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    priority: ContextPriority = ContextPriority.CRITICAL
    ttl_seconds: int = 120  # Auto-expire after 2 minutes
    consumed: bool = False
    
    def is_expired(self) -> bool:
        """Check if injection has expired"""
        elapsed = (datetime.now(timezone.utc) - self.timestamp).total_seconds()
        return elapsed > self.ttl_seconds


class PinnedDocument(BaseModel):
    """A document section pinned for current context"""
    document_path: str
    section_title: str = ""
    content: str = ""
    page_range: str = ""  # e.g., "4-7"
    priority: ContextPriority = ContextPriority.DOCUMENT
    pinned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LiveContextConfig(BaseModel):
    """Configuration for Live Context manager"""
    max_injections: int = Field(default=20, description="Max stored injections")
    max_pinned_docs: int = Field(default=5, description="Max pinned documents")
    injection_ttl: int = Field(default=120, description="Default injection TTL in seconds")
    slide_context_chars: int = Field(default=2000, description="Max chars from slide content")
    priority_boost_prompt: str = Field(
        default="PRIORITERAD KONTEXT (använd detta FÖRE /vault-data):",
        description="Prompt prefix for priority context"
    )
    enable_slide_sync: bool = Field(default=True, description="Enable slide synchronization")
    enable_live_injection: bool = Field(default=True, description="Enable live text injection")
    presentations_dir: str = Field(default="assets/presentations", description="Presentation storage")


class LiveContextManager:
    """
    Short-term priority memory that trumps all /vault data.
    
    Three input channels:
    1. Slide-Sync: PDF presentation tracking ("Håll dig till Slide 4")
    2. Live Injection: Real-time operator notes ("Betona 5 års garanti")
    3. Document Pinning: Pin a section of a document for current context
    """
    
    def __init__(self, config: LiveContextConfig):
        """Initialize Live Context manager"""
        self.config = config
        
        # Slide state
        self.slide_state: Optional[SlideState] = None
        self.slides_cache: Dict[int, Dict[str, str]] = {}  # slide_num -> {content, notes}
        
        # Live injections (newest first)
        self.injections: List[LiveInjection] = []
        
        # Pinned documents
        self.pinned_docs: List[PinnedDocument] = []
        
        # Callbacks
        self._on_context_change: Optional[callable] = None
        
        # Ensure presentations dir exists
        Path(config.presentations_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info("Live Context Manager initialized")
    
    def set_on_context_change(self, callback: callable):
        """Register callback for context changes"""
        self._on_context_change = callback
    
    # ─── Slide Sync ───────────────────────────────────────────────
    
    async def load_presentation(self, pdf_path: str) -> bool:
        """
        Load a PDF presentation and extract slide content.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            True if loaded successfully
        """
        try:
            path = Path(pdf_path)
            if not path.exists():
                logger.error(f"Presentation not found: {pdf_path}")
                return False
            
            # Extract text from PDF pages
            slides = await self._extract_pdf_slides(str(path))
            
            if not slides:
                logger.warning(f"No slides extracted from: {pdf_path}")
                return False
            
            self.slides_cache = slides
            self.slide_state = SlideState(
                document_name=path.name,
                total_slides=len(slides),
                current_slide=1,
                slide_content=slides.get(1, {}).get("content", ""),
                slide_notes=slides.get(1, {}).get("notes", "")
            )
            
            logger.info(f"Loaded presentation: {path.name} ({len(slides)} slides)")
            await self._notify_change("slide_loaded")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load presentation: {e}")
            return False
    
    async def set_slide(self, slide_number: int) -> bool:
        """
        Set current slide number.
        
        Args:
            slide_number: 1-indexed slide number
            
        Returns:
            True if slide set successfully
        """
        if not self.slide_state:
            logger.warning("No presentation loaded")
            return False
        
        if slide_number < 1 or slide_number > self.slide_state.total_slides:
            logger.warning(f"Slide {slide_number} out of range (1-{self.slide_state.total_slides})")
            return False
        
        slide_data = self.slides_cache.get(slide_number, {})
        self.slide_state.current_slide = slide_number
        self.slide_state.slide_content = slide_data.get("content", "")
        self.slide_state.slide_notes = slide_data.get("notes", "")
        
        logger.info(f"Slide set to {slide_number}/{self.slide_state.total_slides}")
        await self._notify_change("slide_changed")
        return True
    
    async def next_slide(self) -> bool:
        """Advance to next slide"""
        if not self.slide_state:
            return False
        return await self.set_slide(self.slide_state.current_slide + 1)
    
    async def prev_slide(self) -> bool:
        """Go back to previous slide"""
        if not self.slide_state:
            return False
        return await self.set_slide(self.slide_state.current_slide - 1)
    
    def unload_presentation(self):
        """Unload current presentation"""
        self.slide_state = None
        self.slides_cache.clear()
        logger.info("Presentation unloaded")
    
    # ─── Live Injection ──────────────────────────────────────────
    
    async def inject(self, text: str, ttl_seconds: Optional[int] = None) -> str:
        """
        Inject live text that the agent should incorporate immediately.
        
        Args:
            text: Text to inject (e.g., "Betona att vi har 5 års garanti")
            ttl_seconds: Time-to-live in seconds (default from config)
            
        Returns:
            Injection ID
        """
        injection = LiveInjection(
            text=text.strip(),
            ttl_seconds=ttl_seconds or self.config.injection_ttl
        )
        
        self.injections.insert(0, injection)  # Newest first
        
        # Trim old injections
        if len(self.injections) > self.config.max_injections:
            self.injections = self.injections[:self.config.max_injections]
        
        logger.info(f"Live injection: '{text[:50]}...' (TTL: {injection.ttl_seconds}s)")
        await self._notify_change("injection_added")
        return injection.timestamp.isoformat()
    
    def get_active_injections(self) -> List[LiveInjection]:
        """Get all non-expired, non-consumed injections"""
        active = [inj for inj in self.injections if not inj.is_expired() and not inj.consumed]
        return active
    
    def consume_injection(self, injection: LiveInjection):
        """Mark an injection as consumed (used by agent)"""
        injection.consumed = True
        logger.debug(f"Injection consumed: '{injection.text[:30]}...'")
    
    def clear_injections(self):
        """Clear all live injections"""
        self.injections.clear()
        logger.info("All injections cleared")
    
    # ─── Document Pinning ────────────────────────────────────────
    
    async def pin_document(self, document_path: str, section_title: str = "",
                           content: str = "", page_range: str = "") -> bool:
        """
        Pin a document section for current context.
        
        Args:
            document_path: Path to document in /vault
            section_title: Section title to highlight
            content: Extracted content from the section
            page_range: Page range (e.g., "4-7")
            
        Returns:
            True if pinned successfully
        """
        if len(self.pinned_docs) >= self.config.max_pinned_docs:
            # Remove oldest pinned doc
            removed = self.pinned_docs.pop(0)
            logger.info(f"Unpinned oldest: {removed.document_path}")
        
        doc = PinnedDocument(
            document_path=document_path,
            section_title=section_title,
            content=content,
            page_range=page_range
        )
        
        self.pinned_docs.append(doc)
        logger.info(f"Pinned document: {document_path} (section: {section_title})")
        await self._notify_change("document_pinned")
        return True
    
    def unpin_document(self, document_path: str) -> bool:
        """Unpin a document"""
        before = len(self.pinned_docs)
        self.pinned_docs = [d for d in self.pinned_docs if d.document_path != document_path]
        removed = before - len(self.pinned_docs)
        if removed:
            logger.info(f"Unpinned: {document_path}")
        return removed > 0
    
    def clear_pinned(self):
        """Clear all pinned documents"""
        self.pinned_docs.clear()
        logger.info("All pinned documents cleared")
    
    # ─── Priority Context Builder ────────────────────────────────
    
    def build_priority_context(self) -> str:
        """
        Build the priority context string that gets injected BEFORE /vault data
        in the LLM prompt. This is the core output of the Live Context system.
        
        Returns:
            Formatted priority context string
        """
        parts = []
        
        # 1. Live injections (CRITICAL priority - always first)
        active_injections = self.get_active_injections()
        if active_injections:
            parts.append("🔴 OPERATÖRSINSTRUKTIONER (följ detta EXAKT):")
            for inj in active_injections:
                parts.append(f"  → {inj.text}")
        
        # 2. Current slide (SLIDE priority)
        if self.slide_state and self.config.enable_slide_sync:
            parts.append(f"\n📊 AKTUELL SLIDE ({self.slide_state.current_slide}/{self.slide_state.total_slides}):")
            if self.slide_state.slide_content:
                content = self.slide_state.slide_content[:self.config.slide_context_chars]
                parts.append(f"  Innehåll: {content}")
            if self.slide_state.slide_notes:
                parts.append(f"  Anteckningar: {self.slide_state.slide_notes}")
            if self.slide_state.pinned:
                parts.append("  ⚠️ PINNED: Håll dig till denna slide tills vidare.")
        
        # 3. Pinned documents (DOCUMENT priority)
        if self.pinned_docs:
            parts.append("\n📌 PINNADE DOKUMENT:")
            for doc in self.pinned_docs:
                title = doc.section_title or Path(doc.document_path).name
                parts.append(f"  [{title}]")
                if doc.content:
                    parts.append(f"  {doc.content[:500]}")
        
        if not parts:
            return ""
        
        header = self.config.priority_boost_prompt
        return f"\n{header}\n" + "\n".join(parts) + "\n"
    
    def has_active_context(self) -> bool:
        """Check if there's any active live context"""
        has_injections = len(self.get_active_injections()) > 0
        has_slide = self.slide_state is not None
        has_pinned = len(self.pinned_docs) > 0
        return has_injections or has_slide or has_pinned
    
    # ─── Internal Helpers ────────────────────────────────────────
    
    async def _extract_pdf_slides(self, pdf_path: str) -> Dict[int, Dict[str, str]]:
        """
        Extract text content from PDF pages.
        Each page = one slide.
        
        Returns:
            Dict mapping slide number (1-indexed) to {content, notes}
        """
        slides = {}
        
        try:
            # Try PyMuPDF (fitz) first
            import fitz
            doc = fitz.open(pdf_path)
            
            for i, page in enumerate(doc):
                text = page.get_text("text").strip()
                slides[i + 1] = {
                    "content": text,
                    "notes": ""  # PDF doesn't have speaker notes natively
                }
            
            doc.close()
            logger.info(f"Extracted {len(slides)} slides via PyMuPDF")
            
        except ImportError:
            # Fallback: try pdfplumber
            try:
                import pdfplumber
                with pdfplumber.open(pdf_path) as pdf:
                    for i, page in enumerate(pdf.pages):
                        text = page.extract_text() or ""
                        slides[i + 1] = {
                            "content": text.strip(),
                            "notes": ""
                        }
                logger.info(f"Extracted {len(slides)} slides via pdfplumber")
                
            except ImportError:
                logger.error("No PDF library available. Install PyMuPDF or pdfplumber.")
                return {}
        
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return {}
        
        return slides
    
    async def _notify_change(self, event_type: str):
        """Notify callback of context change"""
        if self._on_context_change:
            try:
                if asyncio.iscoroutinefunction(self._on_context_change):
                    await self._on_context_change(event_type, self.get_status())
                else:
                    self._on_context_change(event_type, self.get_status())
            except Exception as e:
                logger.error(f"Context change callback failed: {e}")
    
    # ─── Status ──────────────────────────────────────────────────
    
    def get_status(self) -> Dict[str, Any]:
        """Get current live context status"""
        return {
            "has_presentation": self.slide_state is not None,
            "current_slide": self.slide_state.current_slide if self.slide_state else None,
            "total_slides": self.slide_state.total_slides if self.slide_state else None,
            "document_name": self.slide_state.document_name if self.slide_state else None,
            "active_injections": len(self.get_active_injections()),
            "total_injections": len(self.injections),
            "pinned_documents": len(self.pinned_docs),
            "has_active_context": self.has_active_context(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def reset(self):
        """Reset all live context (between meetings)"""
        self.unload_presentation()
        self.clear_injections()
        self.clear_pinned()
        logger.info("Live Context reset")


async def main():
    """Test the Live Context manager"""
    config = LiveContextConfig()
    manager = LiveContextManager(config)
    
    # Test live injection
    await manager.inject("Betona att vi har 5 års garanti på alla produkter")
    await manager.inject("Nämn inte konkurrent X vid namn")
    
    # Test document pinning
    await manager.pin_document(
        "vault/client/acme/offert_2024.pdf",
        section_title="Prismodell",
        content="Grundpris: 450 000 SEK. Volymrabatt vid >100 enheter: 15%."
    )
    
    # Build priority context
    context = manager.build_priority_context()
    print(context)
    
    # Status
    status = manager.get_status()
    logger.info(f"Status: {status}")


if __name__ == "__main__":
    asyncio.run(main())
