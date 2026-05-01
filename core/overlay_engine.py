#!/usr/bin/env python3
"""
Project Anton Egon - Overlay Engine
Extreme Action Clips: Alpha overlay clips (water pour, surprise, etc.)

Phase 16: The Trickster Engine
"""

import cv2
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
import threading
import time

from loguru import logger


class OverlayType(Enum):
    """Types of overlays"""
    WATER_POUR = "water_pour"
    SURPRISE = "surprise"
    GLASS_ADJUST = "glass_adjust"
    CAT_JUMP = "cat_jump"
    CONFETTI = "confetti"
    SPARKLE = "sparkle"
    SMOKE = "smoke"


class OverlayPosition(Enum):
    """Overlay positions on frame"""
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    CENTER = "center"
    FULL_SCREEN = "full_screen"


@dataclass
class Overlay:
    """Overlay clip configuration"""
    id: str
    name: str
    overlay_type: OverlayType
    video_path: str
    position: OverlayPosition
    duration: float = 2.0  # Duration in seconds
    scale: float = 1.0
    opacity: float = 1.0
    loop: bool = False
    trigger_emotion: Optional[str] = None  # Emotion to trigger after overlay
    # Phase 17-19: Chroma Key configuration
    chroma_key: bool = False  # Enable chroma key
    chroma_color: Tuple[int, int, int] = (0, 255, 0)  # Green (BGR)
    chroma_threshold: int = 30  # Color distance threshold
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "overlay_type": self.overlay_type.value,
            "video_path": self.video_path,
            "position": self.position.value,
            "duration": self.duration,
            "scale": self.scale,
            "opacity": self.opacity,
            "loop": self.loop,
            "trigger_emotion": self.trigger_emotion,
            "chroma_key": self.chroma_key,
            "chroma_color": self.chroma_color,
            "chroma_threshold": self.chroma_threshold,
            "metadata": self.metadata
        }


class OverlayEngine:
    """
    Overlay Engine
    Plays alpha overlay clips on top of video feed
    """
    
    def __init__(self):
        """Initialize Overlay Engine"""
        self.overlays: Dict[str, Overlay] = {}
        self.active_overlays: List[Tuple[Overlay, float, cv2.VideoCapture]] = []  # (overlay, start_time, video_capture)
        self.lock = threading.Lock()
        
        logger.info("Overlay Engine initialized")
    
    def register_overlay(self, overlay: Overlay) -> bool:
        """
        Register an overlay clip
        
        Args:
            overlay: Overlay to register
        
        Returns:
            True if registered successfully
        """
        if overlay.id in self.overlays:
            logger.warning(f"Overlay ID already exists: {overlay.id}")
            return False
        
        self.overlays[overlay.id] = overlay
        logger.info(f"Registered overlay: {overlay.name}")
        return True
    
    def trigger_overlay(self, overlay_id: str) -> bool:
        """
        Trigger an overlay clip
        
        Args:
            overlay_id: Overlay ID
        
        Returns:
            True if triggered successfully
        """
        if overlay_id not in self.overlays:
            logger.warning(f"Overlay ID not found: {overlay_id}")
            return False
        
        overlay = self.overlays[overlay_id]
        
        try:
            # Load video
            cap = cv2.VideoCapture(overlay.video_path)
            if not cap.isOpened():
                logger.error(f"Failed to open overlay video: {overlay.video_path}")
                return False
            
            with self.lock:
                self.active_overlays.append((overlay, time.time(), cap))
            
            logger.info(f"Triggered overlay: {overlay.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error triggering overlay: {e}")
            return False
    
    def apply_overlays(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply active overlays to frame
        
        Args:
            frame: Input frame (BGR)
        
        Returns:
            Frame with overlays applied
        """
        with self.lock:
            now = time.time()
            
            # Process active overlays
            for i, (overlay, start_time, cap) in enumerate(self.active_overlays):
                elapsed = now - start_time
                
                # Check if overlay should still be active
                if elapsed > overlay.duration and not overlay.loop:
                    cap.release()
                    self.active_overlays.pop(i)
                    continue
                
                # Read next frame from overlay video
                ret, overlay_frame = cap.read()
                
                if not ret:
                    # End of video
                    if overlay.loop:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, overlay_frame = cap.read()
                    else:
                        cap.release()
                        self.active_overlays.pop(i)
                        continue
                
                if overlay_frame is not None:
                    # Phase 17-19: Apply Chroma Key if enabled
                    if overlay.chroma_key:
                        overlay_frame = self._apply_chroma_key(overlay_frame, overlay.chroma_color, overlay.chroma_threshold)
                    else:
                        # Convert to RGBA if needed
                        if overlay_frame.shape[2] == 3:
                            overlay_frame = cv2.cvtColor(overlay_frame, cv2.COLOR_BGR2BGRA)
                    
                    # Apply scaling
                    if overlay.scale != 1.0:
                        new_size = (
                            int(overlay_frame.shape[1] * overlay.scale),
                            int(overlay_frame.shape[0] * overlay.scale)
                        )
                        overlay_frame = cv2.resize(overlay_frame, new_size)
                    
                    # Apply opacity
                    if overlay.opacity < 1.0:
                        overlay_frame = self._apply_opacity(overlay_frame, overlay.opacity)
                    
                    # Calculate position
                    x, y = self._calculate_position(frame.shape, overlay_frame.shape, overlay.position)
                    
                    # Blend overlay onto frame
                    frame = self._blend_overlay(frame, overlay_frame, x, y)
            
            return frame
    
    def _calculate_position(
        self,
        frame_shape: Tuple[int, int, int],
        overlay_shape: Tuple[int, int, int],
        position: OverlayPosition
    ) -> Tuple[int, int]:
        """
        Calculate overlay position on frame
        
        Args:
            frame_shape: Frame shape (h, w, c)
            overlay_shape: Overlay shape (h, w, c)
            position: Position enum
        
        Returns:
            (x, y) coordinates
        """
        h, w = frame_shape[:2]
        overlay_h, overlay_w = overlay_shape[:2]
        
        if position == OverlayPosition.TOP_LEFT:
            return (0, 0)
        elif position == OverlayPosition.TOP_RIGHT:
            return (w - overlay_w, 0)
        elif position == OverlayPosition.BOTTOM_LEFT:
            return (0, h - overlay_h)
        elif position == OverlayPosition.BOTTOM_RIGHT:
            return (w - overlay_w, h - overlay_h)
        elif position == OverlayPosition.CENTER:
            return ((w - overlay_w) // 2, (h - overlay_h) // 2)
        elif position == OverlayPosition.FULL_SCREEN:
            return (0, 0)
        
        return (0, 0)
    
    def _apply_opacity(self, img: np.ndarray, opacity: float) -> np.ndarray:
        """
        Apply opacity to image
        
        Args:
            img: Input image (RGBA)
            opacity: Opacity value (0.0 - 1.0)
        
        Returns:
            Image with opacity applied
        """
        if img.shape[2] < 4:
            return img
        
        img = img.copy()
        img[:, :, 3] = (img[:, :, 3] * opacity).astype(np.uint8)
        return img
    
    # ═══════════════════════════════════════════════════════════════
    # PHASE 17-19: CHROMA KEY LOGIC
    # ═══════════════════════════════════════════════════════════════
    def _apply_chroma_key(
        self,
        frame: np.ndarray,
        chroma_color: Tuple[int, int, int],
        threshold: int = 30
    ) -> np.ndarray:
        """
        Apply chroma key to remove background color (green screen)
        
        Args:
            frame: Input frame (BGR)
            chroma_color: Color to remove (BGR tuple)
            threshold: Color distance threshold
        
        Returns:
            Frame with alpha channel (BGRA)
        """
        if frame.shape[2] == 4:
            return frame  # Already has alpha
        
        # Convert to RGBA
        frame_rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
        
        # Calculate color distance from chroma color
        chroma = np.array(chroma_color, dtype=np.float32)
        
        # For each pixel, calculate Euclidean distance to chroma color
        distances = np.sqrt(
            np.sum((frame[:, :, :3].astype(np.float32) - chroma) ** 2, axis=2)
        )
        
        # Create alpha mask (pixels close to chroma color become transparent)
        alpha = np.where(distances < threshold, 0, 255).astype(np.uint8)
        
        # Apply alpha to frame
        frame_rgba[:, :, 3] = alpha
        
        return frame_rgba
    
    def _blend_overlay(
        self,
        frame: np.ndarray,
        overlay_frame: np.ndarray,
        x: int,
        y: int
    ) -> np.ndarray:
        """
        Blend overlay onto frame using alpha channel
        
        Args:
            frame: Input frame (BGR)
            overlay_frame: Overlay frame (RGBA)
            x: X position
            y: Y position
        
        Returns:
            Frame with overlay blended
        """
        h, w = frame.shape[:2]
        overlay_h, overlay_w = overlay_frame.shape[:2]
        
        # For full screen, resize overlay to match frame
        if overlay_h == h and overlay_w == w:
            pass  # Already matching
        else:
            # Check bounds
            if x < 0 or y < 0 or x + overlay_w > w or y + overlay_h > h:
                return frame
        
        # Extract alpha channel
        alpha = overlay_frame[:, :, 3] / 255.0
        
        # Expand alpha to 3 channels
        alpha = np.dstack([alpha] * 3)
        
        # Blend
        overlay_rgb = overlay_frame[:, :, :3]
        frame[y:y+overlay_h, x:x+overlay_w] = (
            alpha * overlay_rgb +
            (1 - alpha) * frame[y:y+overlay_h, x:x+overlay_w]
        ).astype(np.uint8)
        
        return frame
    
    def get_active_overlays(self) -> List[Dict[str, Any]]:
        """Get list of active overlays"""
        with self.lock:
            return [overlay.to_dict() for overlay, _, _ in self.active_overlays]
    
    def get_all_overlays(self) -> List[Dict[str, Any]]:
        """Get all registered overlays"""
        return [overlay.to_dict() for overlay in self.overlays.values()]
    
    def stop_overlay(self, overlay_id: str) -> bool:
        """
        Stop an active overlay
        
        Args:
            overlay_id: Overlay ID
        
        Returns:
            True if stopped successfully
        """
        with self.lock:
            for i, (overlay, _, cap) in enumerate(self.active_overlays):
                if overlay.id == overlay_id:
                    cap.release()
                    self.active_overlays.pop(i)
                    logger.info(f"Stopped overlay: {overlay.name}")
                    return True
        
        return False
    
    def stop_all_overlays(self):
        """Stop all active overlays"""
        with self.lock:
            for _, _, cap in self.active_overlays:
                cap.release()
            self.active_overlays.clear()
            logger.info("Stopped all active overlays")
    
    def register_default_overlays(self):
        """Register default overlays (placeholder paths)"""
        default_overlays = [
            Overlay(
                id="water_pour_001",
                name="Water Pour",
                overlay_type=OverlayType.WATER_POUR,
                video_path="assets/overlays/water_pour.mp4",
                position=OverlayPosition.TOP_CENTER,
                duration=2.0,
                trigger_emotion="wet_surprise"
            ),
            Overlay(
                id="surprise_001",
                name="Surprise Look",
                overlay_type=OverlayType.SURPRISE,
                video_path="assets/overlays/surprise.mp4",
                position=OverlayPosition.FULL_SCREEN,
                duration=1.5,
                trigger_emotion="surprised"
            ),
            Overlay(
                id="glass_adjust_001",
                name="Adjust Glasses",
                overlay_type=OverlayType.GLASS_ADJUST,
                video_path="assets/overlays/glass_adjust.mp4",
                position=OverlayPosition.FULL_SCREEN,
                duration=1.0
            )
        ]
        
        for overlay in default_overlays:
            self.register_overlay(overlay)
        
        logger.info(f"Registered {len(default_overlays)} default overlays")


# Singleton instance
overlay_engine = OverlayEngine()


async def main():
    """Test Overlay Engine"""
    logger.add("logs/overlay_engine_{time}.log", rotation="10 MB")
    
    # Register default overlays
    overlay_engine.register_default_overlays()
    
    # Get all overlays
    overlays = overlay_engine.get_all_overlays()
    logger.info(f"Registered overlays: {len(overlays)}")
    
    logger.info("Overlay Engine test complete")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
