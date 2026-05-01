#!/usr/bin/env python3
"""
Project Anton Egon - Phase 11: Slide Master
PDF presentation indexing with Spatial OCR, keyboard-based navigation,
verbal pinpointing, and virtual pointer coordination.

Flow:
  1. index_presentation() → OCR + ChromaDB vectors per slide element
  2. navigate_to(slide_number) → pyautogui arrow keys to shared window
  3. describe_element(element_id) → verbal deixis + gaze sync coords
"""

import asyncio
import sys
import time
import io
import re
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding
if sys.platform == 'win32':
    import _io
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# ─── Data Models ─────────────────────────────────────────────────

class SlideRegion(Enum):
    """Spatial regions on a slide (3×3 grid)"""
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    MIDDLE_LEFT = "middle_left"
    MIDDLE_CENTER = "middle_center"
    MIDDLE_RIGHT = "middle_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"


class ElementType(Enum):
    """Types of visual elements on a slide"""
    TITLE = "title"
    SUBTITLE = "subtitle"
    BODY_TEXT = "body_text"
    BULLET_POINT = "bullet_point"
    TABLE = "table"
    CHART = "chart"
    IMAGE = "image"
    DIAGRAM = "diagram"
    NUMBER = "number"
    FOOTER = "footer"
    UNKNOWN = "unknown"


class PresentationApp(Enum):
    """Supported presentation applications"""
    POWERPOINT = "powerpoint"
    ACROBAT = "acrobat"
    GOOGLE_SLIDES = "google_slides"
    BROWSER = "browser"
    KEYNOTE = "keynote"


class PresentationMode(Enum):
    """Who is presenting?"""
    PRESENTER = "presenter"    # Anton Egon presents, participants ask questions
    OBSERVER = "observer"      # Someone else presents, Anton Egon observes/questions


@dataclass
class SlideElement:
    """A single detected element on a slide"""
    element_id: str
    slide_number: int
    element_type: ElementType
    text: str
    region: SlideRegion
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1) normalized 0-1
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def tag(self) -> str:
        """Generate spatial tag: Slide_05_Section_TopRight"""
        return f"Slide_{self.slide_number:02d}_Section_{self.region.value}"
    
    @property
    def center(self) -> Tuple[float, float]:
        """Get center point of element (normalized 0-1)"""
        cx = (self.bbox[0] + self.bbox[2]) / 2
        cy = (self.bbox[1] + self.bbox[3]) / 2
        return (cx, cy)


@dataclass 
class IndexedSlide:
    """A fully indexed slide"""
    slide_number: int
    image_path: Optional[str] = None
    full_text: str = ""
    elements: List[SlideElement] = field(default_factory=list)
    vector_ids: List[str] = field(default_factory=list)  # ChromaDB vector IDs
    
    def get_elements_in_region(self, region: SlideRegion) -> List[SlideElement]:
        """Get all elements in a specific region"""
        return [e for e in self.elements if e.region == region]
    
    def get_elements_by_type(self, elem_type: ElementType) -> List[SlideElement]:
        """Get all elements of a specific type"""
        return [e for e in self.elements if e.element_type == elem_type]


class SlideMasterConfig(BaseModel):
    """Configuration for Slide Master"""
    # Mode
    mode: PresentationMode = Field(default=PresentationMode.PRESENTER, description="Presenter or Observer")
    
    # Indexing
    presentations_dir: str = Field(default="assets/presentations", description="Presentation storage")
    slide_images_dir: str = Field(default="assets/presentations/slides", description="Rendered slide images")
    ocr_language: str = Field(default="swe+eng", description="Tesseract OCR language")
    dpi: int = Field(default=200, description="DPI for PDF rendering")
    
    # Navigation
    presentation_app: PresentationApp = Field(default=PresentationApp.POWERPOINT, description="Target app")
    navigation_delay_ms: int = Field(default=300, description="Delay between arrow key presses")
    window_title_pattern: str = Field(default="PowerPoint", description="Window title to target")
    
    # ChromaDB
    collection_name: str = Field(default="slide_elements", description="ChromaDB collection")
    
    # Pinpointing
    enable_virtual_pointer: bool = Field(default=False, description="Enable OBS virtual pointer overlay")
    pointer_color: str = Field(default="#FF0000", description="Pointer circle color")
    pointer_radius: int = Field(default=20, description="Pointer circle radius in pixels")
    
    # Gaze sync
    enable_gaze_sync: bool = Field(default=True, description="Sync agent gaze to pointed element")
    
    # Observer mode
    observer_screenshot_interval_ms: int = Field(default=2000, description="Interval for screenshot-based slide tracking")
    observer_auto_index: bool = Field(default=True, description="Auto-index slides from screen captures")


# ─── Verbal Deixis Templates ────────────────────────────────────

REGION_PHRASES = {
    SlideRegion.TOP_LEFT: [
        "Om vi tittar uppe till vänster",
        "Här uppe i vänstra hörnet",
        "Den sektionen uppe till vänster",
    ],
    SlideRegion.TOP_CENTER: [
        "Om vi tittar på rubriken här uppe",
        "Överst på sliden",
        "Precis här uppe",
    ],
    SlideRegion.TOP_RIGHT: [
        "Uppe till höger ser vi",
        "I det övre högra hörnet",
        "Om ni tittar uppe till höger",
    ],
    SlideRegion.MIDDLE_LEFT: [
        "Här till vänster",
        "På vänster sida",
        "Om vi tittar åt vänster",
    ],
    SlideRegion.MIDDLE_CENTER: [
        "Här i mitten",
        "Rakt framför oss",
        "I centrum av sliden",
    ],
    SlideRegion.MIDDLE_RIGHT: [
        "Här till höger",
        "På höger sida ser vi",
        "Om vi tittar åt höger",
    ],
    SlideRegion.BOTTOM_LEFT: [
        "Nere till vänster",
        "I nedre vänstra hörnet",
        "Om vi tittar ner till vänster",
    ],
    SlideRegion.BOTTOM_CENTER: [
        "Längst ner",
        "I botten av sliden",
        "Nere ser vi",
    ],
    SlideRegion.BOTTOM_RIGHT: [
        "Nere till höger",
        "I nedre högra hörnet",
        "Om vi tittar ner till höger",
    ],
}

ELEMENT_TYPE_PHRASES = {
    ElementType.CHART: [
        "grafen som visar {description}",
        "diagrammet med {description}",
        "den här visualiseringen av {description}",
    ],
    ElementType.TABLE: [
        "tabellen med {description}",
        "siffrorna i tabellen",
        "den här jämförelsen",
    ],
    ElementType.NUMBER: [
        "siffran {text}",
        "det talet, {text}",
    ],
    ElementType.TITLE: [
        "rubriken '{text}'",
    ],
    ElementType.BULLET_POINT: [
        "punkten om {description}",
        "det stycket om {description}",
    ],
    ElementType.IMAGE: [
        "bilden som illustrerar {description}",
    ],
}

NAVIGATION_PHRASES = {
    "go_back": [
        "Självklart, låt mig bläddra tillbaka...",
        "Absolut, jag går tillbaka...",
        "Ja, låt mig navigera dit...",
    ],
    "go_forward": [
        "Låt mig gå framåt...",
        "Vi hoppar framåt till den...",
    ],
    "arrived": [
        "Här har vi den.",
        "Varsågod, här ser vi den.",
        "Nu är vi på plats.",
    ],
}

# Observer-mode: phrases when Anton Egon questions someone else's presentation
OBSERVER_PHRASES = {
    "request_go_back": [
        "Ursäkta {presenter}, kan du gå tillbaka till sliden om {topic}?",
        "Förlåt att jag avbryter, men kan vi backa till {topic}?",
        "{presenter}, jag skulle vilja titta på den där sliden med {topic} igen.",
    ],
    "challenge": [
        "Intressant. Om vi tittar på {element}, hur matchar det med {context}?",
        "Jag noterar att {element} visar {value}. Stämmer det med era senaste siffror?",
        "En snabb fråga om {element} – hur förklarar ni {topic}?",
    ],
    "reference_own_data": [
        "Enligt våra siffror så ligger det snarare på {value}.",
        "I vår senaste analys såg vi att {context}.",
        "Det är intressant, för vår data visar {context}.",
    ],
    "acknowledge_slide_change": [
        "Tack.",
        "Perfekt, just den.",
        "Ja, precis den sliden.",
    ],
    "note_discrepancy": [
        "Hmm, det skiljer sig lite från vad vi sett internt.",
        "Intressant, vi har lite annorlunda siffror på det.",
    ],
}


class SlideMaster:
    """
    Manages presentation indexing, navigation, and pinpointing.
    
    Two modes:
    - PRESENTER: Anton Egon runs the presentation. Participants ask questions,
      Anton navigates back/forward and pinpoints elements.
    - OBSERVER: Someone else (e.g., Lasse) presents. Anton indexes their slides
      via screen capture, can challenge claims, request go-back, and cross-reference
      with /vault data.
    
    Core flow:
    1. index_presentation() → OCR each slide, vectorize, store in ChromaDB
    2. navigate_to(slide) → pyautogui arrow keys (PRESENTER) or verbal request (OBSERVER)
    3. describe_element(id) → verbal phrase + gaze coordinates
    """
    
    def __init__(self, config: SlideMasterConfig):
        """Initialize Slide Master"""
        self.config = config
        self.mode = config.mode
        
        # Indexed presentations (support multiple: own + others')
        self.slides: Dict[int, IndexedSlide] = {}
        self.presentation_name: str = ""
        self.total_slides: int = 0
        
        # Observer: track external presenter's slides separately
        self.observed_slides: Dict[int, IndexedSlide] = {}
        self.observed_presentation: str = ""
        self.observed_current_slide: int = 0
        self._observer_presenter_name: str = ""  # e.g., "Lasse"
        
        # Navigation state
        self.current_slide: int = 0
        self._navigation_lock = asyncio.Lock()
        
        # ChromaDB collection (lazy loaded)
        self._collection = None
        
        # Virtual pointer state
        self.pointer_position: Optional[Tuple[float, float]] = None  # normalized (x, y)
        self.pointer_visible: bool = False
        
        # Gaze target (for animator gaze sync)
        self.gaze_target: Optional[Tuple[float, float]] = None  # normalized screen coords
        
        # Callbacks
        self._on_gaze_update: Optional[callable] = None
        self._on_pointer_update: Optional[callable] = None
        self._on_speak: Optional[callable] = None  # For observer verbal requests
        
        # Observer scanning
        self._observer_running = False
        self._observer_task: Optional[asyncio.Task] = None
        
        # Ensure directories
        Path(config.presentations_dir).mkdir(parents=True, exist_ok=True)
        Path(config.slide_images_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Slide Master initialized (mode: {config.mode.value}, app: {config.presentation_app.value})")
    
    def set_callbacks(self, on_gaze: callable = None, on_pointer: callable = None,
                      on_speak: callable = None):
        """Set callbacks for gaze, pointer, and speech updates"""
        self._on_gaze_update = on_gaze
        self._on_pointer_update = on_pointer
        self._on_speak = on_speak
    
    # ═══════════════════════════════════════════════════════════════
    # MODE SWITCHING
    # ═══════════════════════════════════════════════════════════════
    
    def set_mode(self, mode: PresentationMode, presenter_name: str = ""):
        """
        Switch between PRESENTER and OBSERVER mode.
        
        Args:
            mode: PRESENTER (Anton Egon presents) or OBSERVER (someone else presents)
            presenter_name: Name of external presenter (only for OBSERVER mode)
        """
        self.mode = mode
        if mode == PresentationMode.OBSERVER:
            self._observer_presenter_name = presenter_name
            logger.info(f"Switched to OBSERVER mode (presenter: {presenter_name})")
        else:
            self._observer_presenter_name = ""
            logger.info("Switched to PRESENTER mode")
    
    @property
    def is_presenter(self) -> bool:
        return self.mode == PresentationMode.PRESENTER
    
    @property
    def is_observer(self) -> bool:
        return self.mode == PresentationMode.OBSERVER
    
    # ═══════════════════════════════════════════════════════════════
    # 1. SLIDE INDEXING
    # ═══════════════════════════════════════════════════════════════
    
    async def index_presentation(self, pdf_path: str) -> int:
        """
        Index a PDF presentation: render slides, run OCR, vectorize.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Number of slides indexed
        """
        path = Path(pdf_path)
        if not path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            return 0
        
        self.presentation_name = path.stem
        self.slides.clear()
        
        logger.info(f"Indexing presentation: {path.name}")
        
        # Step 1: Render PDF pages to images
        slide_images = await self._render_pdf_to_images(str(path))
        if not slide_images:
            return 0
        
        self.total_slides = len(slide_images)
        
        # Step 2: OCR each slide with spatial information
        for slide_num, img_path in slide_images.items():
            elements = await self._ocr_slide_spatial(slide_num, img_path)
            
            # Get full text
            full_text = " ".join([e.text for e in elements if e.text])
            
            indexed = IndexedSlide(
                slide_number=slide_num,
                image_path=img_path,
                full_text=full_text,
                elements=elements
            )
            
            self.slides[slide_num] = indexed
            logger.debug(f"Slide {slide_num}: {len(elements)} elements, {len(full_text)} chars")
        
        # Step 3: Vectorize in ChromaDB
        await self._vectorize_slides()
        
        # Set initial slide
        self.current_slide = 1
        
        logger.info(f"Indexed {self.total_slides} slides with {sum(len(s.elements) for s in self.slides.values())} elements")
        return self.total_slides
    
    async def _render_pdf_to_images(self, pdf_path: str) -> Dict[int, str]:
        """Render PDF pages to images"""
        images = {}
        
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            
            for i, page in enumerate(doc):
                slide_num = i + 1
                
                # Render at configured DPI
                mat = fitz.Matrix(self.config.dpi / 72, self.config.dpi / 72)
                pix = page.get_pixmap(matrix=mat)
                
                img_path = Path(self.config.slide_images_dir) / f"{self.presentation_name}_slide_{slide_num:03d}.png"
                pix.save(str(img_path))
                
                images[slide_num] = str(img_path)
            
            doc.close()
            logger.info(f"Rendered {len(images)} slides to images")
            
        except ImportError:
            logger.error("PyMuPDF not installed. Run: pip install PyMuPDF")
        except Exception as e:
            logger.error(f"PDF rendering failed: {e}")
        
        return images
    
    async def _ocr_slide_spatial(self, slide_number: int, image_path: str) -> List[SlideElement]:
        """
        Run spatial OCR on a slide image.
        Returns elements with bounding boxes and region classification.
        """
        elements = []
        
        try:
            import cv2
            import numpy as np
            
            img = cv2.imread(image_path)
            if img is None:
                return elements
            
            h, w = img.shape[:2]
            
            # Try Tesseract OCR with bounding boxes
            try:
                import pytesseract
                
                # Get word-level bounding boxes
                data = pytesseract.image_to_data(
                    img, 
                    lang=self.config.ocr_language,
                    output_type=pytesseract.Output.DICT
                )
                
                # Group words into text blocks by block_num
                blocks: Dict[int, Dict] = {}
                for i in range(len(data['text'])):
                    text = data['text'][i].strip()
                    if not text or int(data['conf'][i]) < 30:
                        continue
                    
                    block_num = data['block_num'][i]
                    if block_num not in blocks:
                        blocks[block_num] = {
                            'texts': [],
                            'x_min': float('inf'),
                            'y_min': float('inf'),
                            'x_max': 0,
                            'y_max': 0,
                            'conf_sum': 0,
                            'count': 0,
                        }
                    
                    b = blocks[block_num]
                    b['texts'].append(text)
                    x, y = data['left'][i], data['top'][i]
                    bw, bh = data['width'][i], data['height'][i]
                    b['x_min'] = min(b['x_min'], x)
                    b['y_min'] = min(b['y_min'], y)
                    b['x_max'] = max(b['x_max'], x + bw)
                    b['y_max'] = max(b['y_max'], y + bh)
                    b['conf_sum'] += int(data['conf'][i])
                    b['count'] += 1
                
                # Convert blocks to SlideElements
                for block_num, block in blocks.items():
                    text = " ".join(block['texts'])
                    if len(text) < 2:
                        continue
                    
                    # Normalize bbox to 0-1
                    bbox = (
                        block['x_min'] / w,
                        block['y_min'] / h,
                        block['x_max'] / w,
                        block['y_max'] / h
                    )
                    
                    # Classify region
                    region = self._classify_region(bbox)
                    
                    # Classify element type
                    elem_type = self._classify_element_type(text, bbox, slide_number)
                    
                    # Generate element ID
                    elem_id = f"s{slide_number:02d}_b{block_num}_{region.value}"
                    
                    avg_conf = block['conf_sum'] / block['count'] if block['count'] > 0 else 0
                    
                    element = SlideElement(
                        element_id=elem_id,
                        slide_number=slide_number,
                        element_type=elem_type,
                        text=text,
                        region=region,
                        bbox=bbox,
                        confidence=avg_conf / 100.0,
                        metadata={"tag": f"Slide_{slide_number:02d}_Section_{region.value}"}
                    )
                    elements.append(element)
                
            except ImportError:
                # Fallback: use PyMuPDF text extraction (no spatial data)
                logger.warning("pytesseract not available, using basic text extraction")
                try:
                    import fitz
                    doc = fitz.open(image_path.replace('.png', '.pdf'))
                    # This won't work for images, but as fallback concept
                except Exception:
                    pass
            
        except Exception as e:
            logger.error(f"Spatial OCR failed for slide {slide_number}: {e}")
        
        return elements
    
    def _classify_region(self, bbox: Tuple[float, float, float, float]) -> SlideRegion:
        """Classify which region of the slide a bbox belongs to (3×3 grid)"""
        cx = (bbox[0] + bbox[2]) / 2
        cy = (bbox[1] + bbox[3]) / 2
        
        # Column
        if cx < 0.33:
            col = "left"
        elif cx < 0.66:
            col = "center"
        else:
            col = "right"
        
        # Row
        if cy < 0.33:
            row = "top"
        elif cy < 0.66:
            row = "middle"
        else:
            row = "bottom"
        
        region_map = {
            ("top", "left"): SlideRegion.TOP_LEFT,
            ("top", "center"): SlideRegion.TOP_CENTER,
            ("top", "right"): SlideRegion.TOP_RIGHT,
            ("middle", "left"): SlideRegion.MIDDLE_LEFT,
            ("middle", "center"): SlideRegion.MIDDLE_CENTER,
            ("middle", "right"): SlideRegion.MIDDLE_RIGHT,
            ("bottom", "left"): SlideRegion.BOTTOM_LEFT,
            ("bottom", "center"): SlideRegion.BOTTOM_CENTER,
            ("bottom", "right"): SlideRegion.BOTTOM_RIGHT,
        }
        
        return region_map.get((row, col), SlideRegion.MIDDLE_CENTER)
    
    def _classify_element_type(self, text: str, bbox: Tuple[float, float, float, float],
                                slide_number: int) -> ElementType:
        """Classify what type of element this is based on text and position"""
        cy = (bbox[1] + bbox[3]) / 2
        height = bbox[3] - bbox[1]
        
        # Title: top of slide, typically large text
        if cy < 0.15 and height > 0.03:
            return ElementType.TITLE
        
        # Subtitle: just below title
        if cy < 0.25 and height > 0.02:
            return ElementType.SUBTITLE
        
        # Footer: bottom of slide
        if cy > 0.90:
            return ElementType.FOOTER
        
        # Numbers: mostly digits
        digit_ratio = sum(c.isdigit() for c in text) / max(len(text), 1)
        if digit_ratio > 0.5 and len(text) < 20:
            return ElementType.NUMBER
        
        # Bullet points: starts with bullet or dash
        if text.strip().startswith(('•', '-', '–', '→', '►', '*')):
            return ElementType.BULLET_POINT
        
        # Table-like: contains tab characters or aligned numbers
        if '\t' in text or re.search(r'\d+\s{2,}\d+', text):
            return ElementType.TABLE
        
        return ElementType.BODY_TEXT
    
    async def _vectorize_slides(self):
        """Store slide elements in ChromaDB for semantic search"""
        try:
            import chromadb
            
            client = chromadb.Client()
            
            # Delete existing collection if any
            try:
                client.delete_collection(self.config.collection_name)
            except Exception:
                pass
            
            collection = client.create_collection(
                name=self.config.collection_name,
                metadata={"presentation": self.presentation_name}
            )
            self._collection = collection
            
            # Add all elements
            ids = []
            documents = []
            metadatas = []
            
            for slide_num, slide in self.slides.items():
                # Add full slide text
                if slide.full_text:
                    doc_id = f"slide_{slide_num:02d}_full"
                    ids.append(doc_id)
                    documents.append(slide.full_text)
                    metadatas.append({
                        "slide_number": slide_num,
                        "type": "full_slide",
                        "presentation": self.presentation_name
                    })
                    slide.vector_ids.append(doc_id)
                
                # Add individual elements
                for elem in slide.elements:
                    if len(elem.text) < 5:
                        continue
                    
                    doc_id = elem.element_id
                    ids.append(doc_id)
                    documents.append(f"Slide {slide_num}, {elem.region.value}: {elem.text}")
                    metadatas.append({
                        "slide_number": slide_num,
                        "region": elem.region.value,
                        "element_type": elem.element_type.value,
                        "tag": elem.tag,
                        "bbox_x": elem.center[0],
                        "bbox_y": elem.center[1],
                        "presentation": self.presentation_name
                    })
                    slide.vector_ids.append(doc_id)
            
            if ids:
                collection.add(ids=ids, documents=documents, metadatas=metadatas)
                logger.info(f"Vectorized {len(ids)} slide elements in ChromaDB")
            
        except ImportError:
            logger.warning("ChromaDB not available, skipping vectorization")
        except Exception as e:
            logger.error(f"Vectorization failed: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # 2. NAVIGATION BRIDGE (The Remote Control)
    # ═══════════════════════════════════════════════════════════════
    
    async def navigate_to(self, target_slide: int) -> Dict[str, Any]:
        """
        Navigate to a specific slide by sending keyboard commands.
        
        Args:
            target_slide: 1-indexed slide number
            
        Returns:
            Navigation result with pre-roll phrase and status
        """
        if target_slide < 1 or target_slide > self.total_slides:
            logger.warning(f"Slide {target_slide} out of range (1-{self.total_slides})")
            return {"success": False, "error": "out_of_range"}
        
        async with self._navigation_lock:
            diff = target_slide - self.current_slide
            
            if diff == 0:
                return {"success": True, "phrase": "", "slide": self.current_slide}
            
            # Choose navigation phrase
            import random
            if diff < 0:
                phrase = random.choice(NAVIGATION_PHRASES["go_back"])
            else:
                phrase = random.choice(NAVIGATION_PHRASES["go_forward"])
            
            # Send arrow keys
            direction = "left" if diff < 0 else "right"
            steps = abs(diff)
            
            logger.info(f"Navigating: slide {self.current_slide} → {target_slide} ({steps} {direction})")
            
            success = await self._send_keyboard_navigation(direction, steps)
            
            if success:
                self.current_slide = target_slide
                arrival = random.choice(NAVIGATION_PHRASES["arrived"])
                
                return {
                    "success": True,
                    "phrase": phrase,
                    "arrival_phrase": arrival,
                    "slide": self.current_slide,
                    "steps": steps,
                    "direction": direction
                }
            else:
                return {"success": False, "error": "keyboard_injection_failed"}
    
    async def _send_keyboard_navigation(self, direction: str, steps: int) -> bool:
        """Send arrow key presses to the presentation window"""
        try:
            import pyautogui
            
            # First, focus the presentation window
            focused = self._focus_presentation_window()
            if not focused:
                logger.warning("Could not focus presentation window, sending keys anyway")
            
            # Minimal delay for safety
            pyautogui.PAUSE = self.config.navigation_delay_ms / 1000.0
            
            key = "left" if direction == "left" else "right"
            
            for i in range(steps):
                pyautogui.press(key)
                await asyncio.sleep(self.config.navigation_delay_ms / 1000.0)
            
            logger.info(f"Sent {steps}× {key} arrow key(s)")
            return True
            
        except ImportError:
            logger.error("pyautogui not installed. Run: pip install pyautogui")
            return False
        except Exception as e:
            logger.error(f"Keyboard navigation failed: {e}")
            return False
    
    def _focus_presentation_window(self) -> bool:
        """Try to focus the presentation application window"""
        try:
            import pyautogui
            import subprocess
            
            if sys.platform == 'win32':
                # Use PowerShell to bring window to front
                pattern = self.config.window_title_pattern
                script = f'''
                $wnd = Get-Process | Where-Object {{$_.MainWindowTitle -like "*{pattern}*"}} | Select-Object -First 1
                if ($wnd) {{
                    [void][System.Reflection.Assembly]::LoadWithPartialName("Microsoft.VisualBasic")
                    [Microsoft.VisualBasic.Interaction]::AppActivate($wnd.Id)
                }}
                '''
                subprocess.run(["powershell", "-Command", script], 
                             capture_output=True, timeout=3)
                return True
            
        except Exception as e:
            logger.debug(f"Window focus failed: {e}")
        
        return False
    
    # ═══════════════════════════════════════════════════════════════
    # 3. PINPOINTING – Verbal Deixis + Gaze Sync
    # ═══════════════════════════════════════════════════════════════
    
    def describe_element(self, element_id: str, vault_context: str = "") -> Dict[str, Any]:
        """
        Generate a verbal description pointing to a specific slide element.
        
        Args:
            element_id: The element to describe
            vault_context: Additional context from /vault about this element
            
        Returns:
            {phrase, gaze_target, pointer_position, element}
        """
        # Find the element
        element = self._find_element(element_id)
        if not element:
            return {"phrase": "", "error": "element_not_found"}
        
        import random
        
        # Build verbal deixis phrase
        region_phrase = random.choice(REGION_PHRASES.get(element.region, ["Här"]))
        
        type_phrases = ELEMENT_TYPE_PHRASES.get(element.element_type)
        if type_phrases:
            type_phrase = random.choice(type_phrases).format(
                text=element.text[:50],
                description=vault_context[:100] if vault_context else element.text[:50]
            )
        else:
            type_phrase = f"'{element.text[:50]}'"
        
        full_phrase = f"{region_phrase}, {type_phrase}"
        
        # Set gaze target
        gaze_target = self._element_to_gaze_coords(element)
        self.gaze_target = gaze_target
        
        if self._on_gaze_update:
            self._on_gaze_update(gaze_target)
        
        # Set virtual pointer
        if self.config.enable_virtual_pointer:
            self.pointer_position = element.center
            self.pointer_visible = True
            if self._on_pointer_update:
                self._on_pointer_update(element.center, True)
        
        return {
            "phrase": full_phrase,
            "gaze_target": gaze_target,
            "pointer_position": element.center,
            "element": {
                "id": element.element_id,
                "type": element.element_type.value,
                "region": element.region.value,
                "tag": element.tag,
                "text": element.text[:200],
            }
        }
    
    def hide_pointer(self):
        """Hide the virtual pointer"""
        self.pointer_visible = False
        self.pointer_position = None
        if self._on_pointer_update:
            self._on_pointer_update(None, False)
    
    def _element_to_gaze_coords(self, element: SlideElement) -> Tuple[float, float]:
        """
        Convert element position to gaze coordinates for the animator.
        Maps slide region to screen region where shared content typically appears.
        
        Returns:
            (x, y) gaze target normalized 0-1 (0,0 = camera, shifts for screen regions)
        """
        cx, cy = element.center
        
        # In a Teams call, shared content is typically in the center-right area
        # Gaze (0.5, 0.5) = looking at camera
        # We shift slightly based on element position
        gaze_x = 0.3 + (cx * 0.4)   # Range: 0.3 - 0.7 (looking right-ish)
        gaze_y = 0.4 + (cy * 0.3)   # Range: 0.4 - 0.7 (looking slightly down)
        
        return (gaze_x, gaze_y)
    
    # ═══════════════════════════════════════════════════════════════
    # 4. SEMANTIC SEARCH
    # ═══════════════════════════════════════════════════════════════
    
    async def find_slide_by_query(self, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """
        Search for relevant slides/elements by semantic query.
        
        Args:
            query: Natural language query (e.g., "dippen i mars")
            n_results: Max results to return
            
        Returns:
            List of matching elements with slide numbers and descriptions
        """
        results = []
        
        # ChromaDB semantic search
        if self._collection:
            try:
                search_results = self._collection.query(
                    query_texts=[query],
                    n_results=n_results
                )
                
                if search_results and search_results['ids']:
                    for i, doc_id in enumerate(search_results['ids'][0]):
                        metadata = search_results['metadatas'][0][i] if search_results['metadatas'] else {}
                        document = search_results['documents'][0][i] if search_results['documents'] else ""
                        
                        results.append({
                            "element_id": doc_id,
                            "slide_number": metadata.get("slide_number", 0),
                            "region": metadata.get("region", ""),
                            "element_type": metadata.get("element_type", ""),
                            "tag": metadata.get("tag", ""),
                            "text": document,
                            "score": search_results['distances'][0][i] if search_results.get('distances') else 0
                        })
                        
            except Exception as e:
                logger.error(f"ChromaDB search failed: {e}")
        
        # Fallback: keyword search in indexed slides
        if not results:
            results = self._keyword_search(query, n_results)
        
        return results
    
    def _keyword_search(self, query: str, n_results: int) -> List[Dict[str, Any]]:
        """Fallback keyword search through indexed slides"""
        query_lower = query.lower()
        matches = []
        
        for slide_num, slide in self.slides.items():
            for elem in slide.elements:
                if query_lower in elem.text.lower():
                    matches.append({
                        "element_id": elem.element_id,
                        "slide_number": slide_num,
                        "region": elem.region.value,
                        "element_type": elem.element_type.value,
                        "tag": elem.tag,
                        "text": elem.text[:200],
                        "score": 0.0
                    })
        
        return matches[:n_results]
    
    # ═══════════════════════════════════════════════════════════════
    # 5. OBSERVER MODE – Anton Egon watches someone else's presentation
    # ═══════════════════════════════════════════════════════════════
    
    async def observe_presentation(self, pdf_path: str, presenter_name: str) -> int:
        """
        Index another presenter's presentation for observation/challenge.
        
        Args:
            pdf_path: Path to the presenter's PDF
            presenter_name: Name of the presenter (e.g., "Lasse")
            
        Returns:
            Number of slides indexed
        """
        self.set_mode(PresentationMode.OBSERVER, presenter_name)
        
        count = await self.index_presentation(pdf_path)
        if count > 0:
            # Copy to observed_slides for reference
            self.observed_slides = dict(self.slides)
            self.observed_presentation = self.presentation_name
            logger.info(f"Observing {presenter_name}'s presentation: {count} slides indexed")
        
        return count
    
    async def request_go_back(self, topic: str) -> Dict[str, Any]:
        """
        In OBSERVER mode, verbally ask the presenter to go back to a slide.
        Anton Egon cannot control their PowerPoint – he asks politely.
        
        Args:
            topic: What Anton wants to revisit (e.g., "prognosen för Q2")
            
        Returns:
            Phrase and slide reference
        """
        import random
        
        # Find relevant slide
        results = await self.find_slide_by_query(topic)
        target_slide = results[0]["slide_number"] if results else None
        
        # Build polite request phrase
        phrase = random.choice(OBSERVER_PHRASES["request_go_back"]).format(
            presenter=self._observer_presenter_name or "du",
            topic=topic
        )
        
        if self._on_speak:
            try:
                if asyncio.iscoroutinefunction(self._on_speak):
                    await self._on_speak(phrase)
                else:
                    self._on_speak(phrase)
            except Exception as e:
                logger.error(f"Speak callback failed: {e}")
        
        logger.info(f"Observer request: go back to slide about '{topic}' (slide {target_slide})")
        
        return {
            "mode": "observer",
            "action": "request_go_back",
            "phrase": phrase,
            "target_slide": target_slide,
            "topic": topic
        }
    
    async def challenge_slide(self, element_id: str, vault_context: str = "",
                               own_value: str = "") -> Dict[str, Any]:
        """
        Challenge a claim on the presenter's slide using /vault data.
        
        Args:
            element_id: Element to challenge
            vault_context: Counter-data from /vault
            own_value: Specific value from own data
            
        Returns:
            Challenge phrase and details
        """
        import random
        
        element = self._find_element(element_id)
        if not element:
            return {"phrase": "", "error": "element_not_found"}
        
        phrases = []
        
        # Reference the element
        region_phrase = random.choice(REGION_PHRASES.get(element.region, ["Här"]))
        
        # Build challenge
        if own_value:
            challenge = random.choice(OBSERVER_PHRASES["challenge"]).format(
                element=element.text[:30],
                value=own_value,
                context=vault_context[:80] if vault_context else "era siffror",
                topic=element.text[:30]
            )
            phrases.append(challenge)
            
            # Reference own data
            ref = random.choice(OBSERVER_PHRASES["reference_own_data"]).format(
                value=own_value,
                context=vault_context[:100] if vault_context else own_value
            )
            phrases.append(ref)
        else:
            challenge = random.choice(OBSERVER_PHRASES["challenge"]).format(
                element=element.text[:30],
                value=element.text[:20],
                context=vault_context[:80] if vault_context else "det vi sett",
                topic=element.text[:30]
            )
            phrases.append(challenge)
        
        # Gaze sync: look at the element being discussed
        gaze_target = self._element_to_gaze_coords(element)
        self.gaze_target = gaze_target
        
        if self._on_gaze_update:
            self._on_gaze_update(gaze_target)
        
        full_phrase = " ".join(phrases)
        logger.info(f"Observer challenge: {full_phrase[:80]}...")
        
        return {
            "mode": "observer",
            "action": "challenge",
            "phrase": full_phrase,
            "element": {
                "id": element.element_id,
                "type": element.element_type.value,
                "region": element.region.value,
                "text": element.text[:200],
            },
            "gaze_target": gaze_target,
            "vault_context": vault_context[:200],
        }
    
    def handle_observed_slide_change(self, new_slide_number: int):
        """
        Update tracking when the external presenter changes slide.
        Called by vision system when slide change is detected on screen.
        
        Args:
            new_slide_number: The slide the presenter moved to
        """
        old = self.observed_current_slide
        self.observed_current_slide = new_slide_number
        self.current_slide = new_slide_number
        
        if old != new_slide_number:
            logger.info(f"Observed slide change: {old} → {new_slide_number}")
    
    # ═══════════════════════════════════════════════════════════════
    # 6. HIGH-LEVEL ORCHESTRATION (mode-aware)
    # ═══════════════════════════════════════════════════════════════
    
    async def handle_slide_request(self, user_query: str, vault_lookup: callable = None) -> Dict[str, Any]:
        """
        Full flow for slide-related requests. Mode-aware:
        
        PRESENTER mode (Anton Egon presents):
          "Gå tillbaka till prognosen" → navigate + pinpoint + explain
        
        OBSERVER mode (someone else presents):
          "Gå tillbaka till prognosen" → politely ask presenter + prepare challenge
        
        Args:
            user_query: Natural language request
            vault_lookup: Optional async callable(query) → str for vault enrichment
            
        Returns:
            Full response with phrases and navigation info
        """
        # 1. Find the relevant slide
        results = await self.find_slide_by_query(user_query)
        
        if not results:
            return {
                "success": False,
                "phrase": "Hmm, jag hittar inte den sliden just nu. Vilken slide menade du?",
                "action": "ask_clarification"
            }
        
        best = results[0]
        target_slide = best["slide_number"]
        element_id = best["element_id"]
        
        # Get vault context
        vault_context = ""
        if vault_lookup:
            try:
                vault_context = await vault_lookup(best.get("text", user_query))
            except Exception as e:
                logger.debug(f"Vault lookup failed: {e}")
        
        # ── PRESENTER MODE: Anton Egon navigates himself ──
        if self.is_presenter:
            nav_result = await self.navigate_to(target_slide)
            
            phrases = []
            if nav_result.get("phrase"):
                phrases.append(nav_result["phrase"])
            
            await asyncio.sleep(0.5)
            
            if nav_result.get("arrival_phrase"):
                phrases.append(nav_result["arrival_phrase"])
            
            desc = self.describe_element(element_id, vault_context=vault_context)
            if desc.get("phrase"):
                phrases.append(desc["phrase"])
            
            enrichment = ""
            if vault_context:
                enrichment = f" {vault_context}"
            
            return {
                "success": True,
                "mode": "presenter",
                "phrases": phrases,
                "full_phrase": " ".join(phrases) + enrichment,
                "slide_number": target_slide,
                "element": desc.get("element"),
                "gaze_target": desc.get("gaze_target"),
                "navigation": nav_result
            }
        
        # ── OBSERVER MODE: Anton Egon asks presenter to go back ──
        else:
            import random
            
            # Ask presenter to navigate
            topic = best.get("text", user_query)[:40]
            request_phrase = random.choice(OBSERVER_PHRASES["request_go_back"]).format(
                presenter=self._observer_presenter_name or "du",
                topic=topic
            )
            
            phrases = [request_phrase]
            
            # Prepare what to say when slide appears
            desc = self.describe_element(element_id, vault_context=vault_context)
            
            # If we have vault data that contradicts, prepare challenge
            followup_phrases = []
            if vault_context:
                ref = random.choice(OBSERVER_PHRASES["reference_own_data"]).format(
                    value=vault_context[:50],
                    context=vault_context[:100]
                )
                followup_phrases.append(ref)
            
            if desc.get("phrase"):
                followup_phrases.append(desc["phrase"])
            
            return {
                "success": True,
                "mode": "observer",
                "phrases": phrases,
                "full_phrase": " ".join(phrases),
                "followup_phrases": followup_phrases,
                "slide_number": target_slide,
                "element": desc.get("element"),
                "gaze_target": desc.get("gaze_target"),
                "awaiting_presenter": True
            }
    
    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════
    
    def _find_element(self, element_id: str) -> Optional[SlideElement]:
        """Find an element by ID across all slides"""
        for slide in self.slides.values():
            for elem in slide.elements:
                if elem.element_id == element_id:
                    return elem
        return None
    
    def get_slide_summary(self, slide_number: int) -> str:
        """Get a text summary of a slide"""
        slide = self.slides.get(slide_number)
        if not slide:
            return ""
        
        parts = [f"Slide {slide_number}:"]
        for elem in slide.elements:
            parts.append(f"  [{elem.region.value}] ({elem.element_type.value}) {elem.text[:80]}")
        
        return "\n".join(parts)
    
    def get_all_slides_summary(self) -> str:
        """Get compact summary of all slides"""
        lines = [f"Presentation: {self.presentation_name} ({self.total_slides} slides)"]
        for num in sorted(self.slides.keys()):
            slide = self.slides[num]
            title_elems = slide.get_elements_by_type(ElementType.TITLE)
            title = title_elems[0].text[:60] if title_elems else slide.full_text[:60]
            lines.append(f"  [{num}] {title}")
        return "\n".join(lines)
    
    # ─── Status ──────────────────────────────────────────────────
    
    def get_status(self) -> Dict[str, Any]:
        """Get Slide Master status"""
        status = {
            "mode": self.mode.value,
            "presentation": self.presentation_name,
            "total_slides": self.total_slides,
            "current_slide": self.current_slide,
            "total_elements": sum(len(s.elements) for s in self.slides.values()),
            "vectorized": self._collection is not None,
            "pointer_visible": self.pointer_visible,
            "gaze_target": self.gaze_target,
            "app": self.config.presentation_app.value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if self.is_observer:
            status["observer_presenter"] = self._observer_presenter_name
            status["observed_current_slide"] = self.observed_current_slide
        return status


async def main():
    """Test Slide Master"""
    config = SlideMasterConfig()
    master = SlideMaster(config)
    
    logger.info(f"Status: {master.get_status()}")
    
    # Test region classification
    bbox_top_right = (0.7, 0.1, 0.9, 0.2)
    region = master._classify_region(bbox_top_right)
    logger.info(f"Region for {bbox_top_right}: {region.value}")
    
    # Test element description (mock)
    elem = SlideElement(
        element_id="s05_b1_middle_center",
        slide_number=5,
        element_type=ElementType.CHART,
        text="Prognos Q1-Q4 2024",
        region=SlideRegion.MIDDLE_CENTER,
        bbox=(0.2, 0.3, 0.8, 0.7),
        confidence=0.92
    )
    master.slides[5] = IndexedSlide(slide_number=5, elements=[elem])
    master.total_slides = 10
    master.current_slide = 5
    
    desc = master.describe_element("s05_b1_middle_center", vault_context="nedgång pga säsongsvariation")
    logger.info(f"Description: {desc}")


if __name__ == "__main__":
    asyncio.run(main())
