#!/usr/bin/env python3
"""
Project Anton Egon - Phase 11: UI Detector
Detects platform-specific UI elements: hand-raised icons, chat notifications,
reactions, and mute indicators in Teams/Meet/Zoom windows.
"""

import asyncio
import sys
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Tuple
from datetime import datetime, timezone
from enum import Enum
from collections import deque

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class UIElement(Enum):
    """Detectable UI elements"""
    HAND_RAISED = "hand_raised"
    CHAT_NOTIFICATION = "chat_notification"
    REACTION_THUMBSUP = "reaction_thumbsup"
    REACTION_HEART = "reaction_heart"
    REACTION_LAUGH = "reaction_laugh"
    MUTED = "muted"
    SCREEN_SHARING = "screen_sharing"
    RECORDING_INDICATOR = "recording_indicator"


class PlatformUI(Enum):
    """Supported platforms"""
    TEAMS = "teams"
    MEET = "meet"
    ZOOM = "zoom"
    WEBEX = "webex"


class HandRaisedEvent(BaseModel):
    """A detected hand-raised event"""
    participant_name: str
    platform: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = 0.0
    position_in_queue: int = 0


class UIDetectorConfig(BaseModel):
    """Configuration for UI Detector"""
    platform: str = Field(default="teams", description="Target platform")
    scan_interval_ms: int = Field(default=500, description="UI scan interval in ms")
    confidence_threshold: float = Field(default=0.7, description="Min confidence for detection")
    hand_icon_templates_dir: str = Field(default="assets/templates/ui", description="Icon templates")
    use_template_matching: bool = Field(default=True, description="Use OpenCV template matching")
    use_color_detection: bool = Field(default=True, description="Use color-based detection")
    max_queue_size: int = Field(default=20, description="Max hand-raise queue size")
    dedup_cooldown_seconds: float = Field(default=5.0, description="Cooldown before re-detecting same person")


# Platform-specific UI element colors and positions
PLATFORM_UI_PROFILES = {
    "teams": {
        "hand_icon_color_hsv_low": (20, 150, 150),   # Yellow hand icon
        "hand_icon_color_hsv_high": (35, 255, 255),
        "hand_icon_min_area": 200,
        "hand_icon_max_area": 2000,
        "hand_position_region": "top_right",  # Where hand icon appears relative to video tile
        "chat_badge_color_hsv_low": (100, 150, 150),  # Blue chat badge
        "chat_badge_color_hsv_high": (130, 255, 255),
        "reaction_region": "bottom_center",
        "name_label_region": "bottom_left",
    },
    "meet": {
        "hand_icon_color_hsv_low": (100, 100, 150),  # Blue hand icon
        "hand_icon_color_hsv_high": (130, 255, 255),
        "hand_icon_min_area": 150,
        "hand_icon_max_area": 1500,
        "hand_position_region": "bottom_right",
        "chat_badge_color_hsv_low": (0, 0, 200),
        "chat_badge_color_hsv_high": (180, 30, 255),
        "reaction_region": "bottom_center",
        "name_label_region": "bottom_left",
    },
    "zoom": {
        "hand_icon_color_hsv_low": (15, 100, 150),   # Orange/yellow hand icon
        "hand_icon_color_hsv_high": (30, 255, 255),
        "hand_icon_min_area": 200,
        "hand_icon_max_area": 2000,
        "hand_position_region": "top_left",
        "chat_badge_color_hsv_low": (0, 150, 150),
        "chat_badge_color_hsv_high": (10, 255, 255),
        "reaction_region": "top_left",
        "name_label_region": "bottom_center",
    },
}


class UIDetector:
    """
    Detects platform-specific UI elements in meeting windows.
    
    Primary use case: detecting hand-raised icons to manage turn-taking.
    Secondary: chat notifications, reactions, mute status.
    """
    
    def __init__(self, config: UIDetectorConfig, on_detection: Optional[Callable] = None):
        """Initialize UI Detector"""
        self.config = config
        self.on_detection = on_detection
        
        # Platform profile
        self.platform = config.platform
        self.profile = PLATFORM_UI_PROFILES.get(config.platform, PLATFORM_UI_PROFILES["teams"])
        
        # Hand-raise queue (FIFO)
        self.hand_queue: deque = deque(maxlen=config.max_queue_size)
        self._hand_raise_history: Dict[str, datetime] = {}  # name -> last detected time
        
        # Template images (loaded from disk if available)
        self.templates: Dict[str, np.ndarray] = {}
        
        # State
        self._running = False
        self._scan_task: Optional[asyncio.Task] = None
        self._last_frame: Optional[np.ndarray] = None
        
        # Stats
        self.stats = {
            "total_scans": 0,
            "hands_detected": 0,
            "chat_notifications": 0,
            "reactions_detected": 0,
        }
        
        # Load templates
        self._load_templates()
        
        logger.info(f"UI Detector initialized for platform: {config.platform}")
    
    def _load_templates(self):
        """Load icon template images for template matching"""
        templates_dir = Path(self.config.hand_icon_templates_dir)
        if not templates_dir.exists():
            templates_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created templates directory: {templates_dir}")
            return
        
        for template_path in templates_dir.glob(f"{self.platform}_*.png"):
            name = template_path.stem  # e.g., "teams_hand_raised"
            img = cv2.imread(str(template_path), cv2.IMREAD_UNCHANGED)
            if img is not None:
                self.templates[name] = img
                logger.info(f"Loaded template: {name}")
    
    # ─── Core Detection ──────────────────────────────────────────
    
    def detect_hand_raised(self, frame: np.ndarray, 
                            participant_regions: Optional[Dict[str, Tuple[int, int, int, int]]] = None
                            ) -> List[HandRaisedEvent]:
        """
        Detect hand-raised icons in the meeting frame.
        
        Args:
            frame: Full meeting window screenshot (BGR)
            participant_regions: Optional dict of {name: (x, y, w, h)} for each participant tile
            
        Returns:
            List of HandRaisedEvent for newly detected hand raises
        """
        detections = []
        
        if participant_regions:
            # Check each participant's tile individually
            for name, (x, y, w, h) in participant_regions.items():
                tile = frame[y:y+h, x:x+w]
                if self._check_hand_icon_in_tile(tile):
                    event = self._register_hand_raise(name)
                    if event:
                        detections.append(event)
        else:
            # Full-frame color detection
            color_detections = self._detect_hand_by_color(frame)
            for region in color_detections:
                event = self._register_hand_raise(f"participant_{len(self.hand_queue) + 1}")
                if event:
                    detections.append(event)
        
        # Template matching (if templates available)
        if self.config.use_template_matching and self.templates:
            template_key = f"{self.platform}_hand_raised"
            if template_key in self.templates:
                template_detections = self._detect_by_template(frame, self.templates[template_key])
                # Merge with color detections (avoid duplicates)
                for loc in template_detections:
                    # Check if this location overlaps with existing detections
                    if not self._is_duplicate_location(loc, [d for d in detections]):
                        event = self._register_hand_raise(f"participant_tmpl_{len(self.hand_queue) + 1}")
                        if event:
                            detections.append(event)
        
        if detections:
            self.stats["hands_detected"] += len(detections)
            logger.info(f"Hand raised detected: {[d.participant_name for d in detections]}")
        
        return detections
    
    def detect_chat_notification(self, frame: np.ndarray) -> bool:
        """Detect if there's a new chat notification badge"""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        low = np.array(self.profile["chat_badge_color_hsv_low"])
        high = np.array(self.profile["chat_badge_color_hsv_high"])
        mask = cv2.inRange(hsv, low, high)
        
        # Look for small circular badge
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if 50 < area < 500:  # Small badge size
                perimeter = cv2.arcLength(contour, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    if circularity > 0.6:  # Roughly circular
                        self.stats["chat_notifications"] += 1
                        return True
        
        return False
    
    # ─── Hand Queue Management ───────────────────────────────────
    
    def get_hand_queue(self) -> List[str]:
        """Get ordered list of participants with raised hands"""
        return list(self.hand_queue)
    
    def get_next_in_queue(self) -> Optional[str]:
        """Get next participant in hand-raise queue (without removing)"""
        if self.hand_queue:
            return self.hand_queue[0]
        return None
    
    def dequeue_hand(self) -> Optional[str]:
        """Remove and return the first person in the hand-raise queue"""
        if self.hand_queue:
            name = self.hand_queue.popleft()
            logger.info(f"Dequeued hand: {name} (remaining: {len(self.hand_queue)})")
            return name
        return None
    
    def clear_hand(self, participant_name: str) -> bool:
        """Remove a specific participant from the hand-raise queue"""
        if participant_name in self.hand_queue:
            self.hand_queue.remove(participant_name)
            logger.info(f"Cleared hand: {participant_name}")
            return True
        return False
    
    def clear_all_hands(self):
        """Clear entire hand-raise queue"""
        self.hand_queue.clear()
        self._hand_raise_history.clear()
        logger.info("All hands cleared")
    
    # ─── Continuous Scanning ─────────────────────────────────────
    
    async def start_scanning(self, frame_provider: Callable):
        """
        Start continuous UI scanning.
        
        Args:
            frame_provider: Async callable that returns the current frame
        """
        self._running = True
        self._scan_task = asyncio.create_task(self._scan_loop(frame_provider))
        logger.info("UI scanning started")
    
    async def stop_scanning(self):
        """Stop continuous scanning"""
        self._running = False
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        logger.info("UI scanning stopped")
    
    async def _scan_loop(self, frame_provider: Callable):
        """Main scanning loop"""
        interval = self.config.scan_interval_ms / 1000.0
        
        while self._running:
            try:
                frame = await frame_provider()
                if frame is not None:
                    self._last_frame = frame
                    self.stats["total_scans"] += 1
                    
                    # Detect hand raises
                    hands = self.detect_hand_raised(frame)
                    
                    # Detect chat notifications
                    has_chat = self.detect_chat_notification(frame)
                    
                    # Notify callbacks
                    if hands and self.on_detection:
                        for hand in hands:
                            if asyncio.iscoroutinefunction(self.on_detection):
                                await self.on_detection(UIElement.HAND_RAISED, hand.dict())
                            else:
                                self.on_detection(UIElement.HAND_RAISED, hand.dict())
                    
                    if has_chat and self.on_detection:
                        if asyncio.iscoroutinefunction(self.on_detection):
                            await self.on_detection(UIElement.CHAT_NOTIFICATION, {"detected": True})
                        else:
                            self.on_detection(UIElement.CHAT_NOTIFICATION, {"detected": True})
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"UI scan error: {e}")
                await asyncio.sleep(1.0)
    
    # ─── Internal Detection Methods ──────────────────────────────
    
    def _check_hand_icon_in_tile(self, tile: np.ndarray) -> bool:
        """Check if a participant tile contains a hand-raised icon"""
        if tile is None or tile.size == 0:
            return False
        
        hsv = cv2.cvtColor(tile, cv2.COLOR_BGR2HSV)
        
        low = np.array(self.profile["hand_icon_color_hsv_low"])
        high = np.array(self.profile["hand_icon_color_hsv_high"])
        mask = cv2.inRange(hsv, low, high)
        
        # Check the expected region of the tile
        h, w = tile.shape[:2]
        region = self.profile["hand_position_region"]
        
        if region == "top_right":
            roi_mask = mask[0:h//3, 2*w//3:w]
        elif region == "top_left":
            roi_mask = mask[0:h//3, 0:w//3]
        elif region == "bottom_right":
            roi_mask = mask[2*h//3:h, 2*w//3:w]
        elif region == "bottom_left":
            roi_mask = mask[2*h//3:h, 0:w//3]
        else:
            roi_mask = mask
        
        # Find contours in the region
        contours, _ = cv2.findContours(roi_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.profile["hand_icon_min_area"] <= area <= self.profile["hand_icon_max_area"]:
                return True
        
        return False
    
    def _detect_hand_by_color(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect hand icons in full frame by color"""
        if frame is None or frame.size == 0:
            return []
        
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        low = np.array(self.profile["hand_icon_color_hsv_low"])
        high = np.array(self.profile["hand_icon_color_hsv_high"])
        mask = cv2.inRange(hsv, low, high)
        
        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        regions = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.profile["hand_icon_min_area"] <= area <= self.profile["hand_icon_max_area"]:
                x, y, w, h = cv2.boundingRect(contour)
                regions.append((x, y, w, h))
        
        return regions
    
    def _detect_by_template(self, frame: np.ndarray, template: np.ndarray, 
                             threshold: float = 0.8) -> List[Tuple[int, int]]:
        """Detect UI elements using template matching"""
        if frame is None or template is None:
            return []
        
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Handle template with alpha channel
        if len(template.shape) == 3 and template.shape[2] == 4:
            gray_template = cv2.cvtColor(template[:, :, :3], cv2.COLOR_BGR2GRAY)
        elif len(template.shape) == 3:
            gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            gray_template = template
        
        # Multi-scale template matching
        locations = []
        for scale in [0.8, 1.0, 1.2]:
            resized = cv2.resize(gray_template, None, fx=scale, fy=scale)
            if resized.shape[0] > gray_frame.shape[0] or resized.shape[1] > gray_frame.shape[1]:
                continue
            
            result = cv2.matchTemplate(gray_frame, resized, cv2.TM_CCOEFF_NORMED)
            locs = np.where(result >= threshold)
            
            for pt in zip(*locs[::-1]):
                locations.append(pt)
        
        return locations
    
    def _register_hand_raise(self, participant_name: str) -> Optional[HandRaisedEvent]:
        """Register a hand raise, respecting cooldown"""
        now = datetime.now(timezone.utc)
        
        # Check cooldown
        if participant_name in self._hand_raise_history:
            elapsed = (now - self._hand_raise_history[participant_name]).total_seconds()
            if elapsed < self.config.dedup_cooldown_seconds:
                return None
        
        # Check if already in queue
        if participant_name in self.hand_queue:
            return None
        
        # Add to queue
        self.hand_queue.append(participant_name)
        self._hand_raise_history[participant_name] = now
        
        event = HandRaisedEvent(
            participant_name=participant_name,
            platform=self.platform,
            confidence=self.config.confidence_threshold,
            position_in_queue=len(self.hand_queue)
        )
        
        logger.info(f"Hand raised: {participant_name} (queue position: {event.position_in_queue})")
        return event
    
    def _is_duplicate_location(self, loc: Tuple[int, int], existing: List, threshold: int = 50) -> bool:
        """Check if a detection location overlaps with existing detections"""
        for existing_det in existing:
            # Simple distance check
            if abs(loc[0] - existing_det.get("x", 0)) < threshold and \
               abs(loc[1] - existing_det.get("y", 0)) < threshold:
                return True
        return False
    
    # ─── Platform Switching ──────────────────────────────────────
    
    def set_platform(self, platform: str):
        """Switch to a different platform profile"""
        if platform in PLATFORM_UI_PROFILES:
            self.platform = platform
            self.profile = PLATFORM_UI_PROFILES[platform]
            self.clear_all_hands()
            self._load_templates()
            logger.info(f"Switched to platform: {platform}")
        else:
            logger.warning(f"Unknown platform: {platform}")
    
    # ─── Status ──────────────────────────────────────────────────
    
    def get_status(self) -> Dict[str, Any]:
        """Get detector status"""
        return {
            "platform": self.platform,
            "running": self._running,
            "hand_queue": list(self.hand_queue),
            "hand_queue_size": len(self.hand_queue),
            "templates_loaded": len(self.templates),
            "stats": self.stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test UI Detector"""
    config = UIDetectorConfig(platform="teams")
    detector = UIDetector(config)
    
    # Simulate hand raise detection
    logger.info(f"Status: {detector.get_status()}")
    
    # Manual queue test
    detector._register_hand_raise("Sara")
    detector._register_hand_raise("Lasse")
    detector._register_hand_raise("Anna")
    
    queue = detector.get_hand_queue()
    logger.info(f"Hand queue: {queue}")
    
    next_person = detector.dequeue_hand()
    logger.info(f"Next in queue: {next_person}")
    logger.info(f"Remaining: {detector.get_hand_queue()}")


if __name__ == "__main__":
    asyncio.run(main())
