#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Cross Dissolve
3-frame cross-dissolve for stitching (motion blur)
Replaces hard cuts with natural motion blur transitions between idle and action clips
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List
from enum import Enum
from dataclasses import dataclass

from loguru import logger


class DissolveMode(Enum):
    """Dissolve transition modes"""
    LINEAR = "linear"  # Linear fade
    EASE_IN = "ease_in"  # Ease in (slow start, fast end)
    EASE_OUT = "ease_out"  # Ease out (fast start, slow end)
    SMOOTH = "smooth"  # Smooth (ease in + ease out)


@dataclass
class DissolveConfig:
    """Cross-dissolve configuration"""
    frame_count: int = 3  # Number of frames for dissolve
    mode: DissolveMode = DissolveMode.SMOOTH
    preserve_alpha: bool = True  # Preserve alpha channel if present


class CrossDissolve:
    """
    Cross Dissolve
    Creates smooth transitions between video clips using 3-frame cross-dissolve
    Replaces hard cuts with natural motion blur
    """
    
    def __init__(self, config: DissolveConfig = None):
        """
        Initialize Cross Dissolve
        
        Args:
            config: Dissolve configuration
        """
        self.config = config or DissolveConfig()
        
        logger.info("Cross Dissolve initialized")
    
    def transition(self, frame_a: np.ndarray, frame_b: np.ndarray) -> List[np.ndarray]:
        """
        Create transition frames between two frames
        
        Args:
            frame_a: Source frame
            frame_b: Target frame
        
        Returns:
            List of transition frames
        """
        if frame_a is None or frame_b is None:
            return [frame_b]
        
        if frame_a.shape != frame_b.shape:
            logger.warning("Frame shapes don't match, resizing frame_b")
            frame_b = cv2.resize(frame_b, (frame_a.shape[1], frame_a.shape[0]))
        
        # Generate transition frames
        transition_frames = []
        
        for i in range(self.config.frame_count):
            alpha = self._get_alpha(i, self.config.frame_count)
            
            # Apply alpha blending
            if self.config.preserve_alpha and frame_a.shape[2] == 4:
                # RGBA
                blended = self._blend_rgba(frame_a, frame_b, alpha)
            else:
                # RGB/BGR
                blended = self._blend_rgb(frame_a, frame_b, alpha)
            
            transition_frames.append(blended)
        
        return transition_frames
    
    def _get_alpha(self, frame_index: int, total_frames: int) -> float:
        """
        Get alpha value for frame
        
        Args:
            frame_index: Current frame index (0-based)
            total_frames: Total number of frames
        
        Returns:
            Alpha value (0.0 to 1.0)
        """
        if total_frames <= 1:
            return 1.0
        
        t = frame_index / (total_frames - 1)
        
        if self.config.mode == DissolveMode.LINEAR:
            return t
        elif self.config.mode == DissolveMode.EASE_IN:
            return t * t  # Quadratic ease-in
        elif self.config.mode == DissolveMode.EASE_OUT:
            return 1 - (1 - t) * (1 - t)  # Quadratic ease-out
        elif self.config.mode == DissolveMode.SMOOTH:
            # Smoothstep: 3t^2 - 2t^3
            return t * t * (3 - 2 * t)
        else:
            return t
    
    def _blend_rgb(self, frame_a: np.ndarray, frame_b: np.ndarray, alpha: float) -> np.ndarray:
        """
        Blend two RGB frames
        
        Args:
            frame_a: Source frame
            frame_b: Target frame
            alpha: Blend factor (0.0 to 1.0)
        
        Returns:
            Blended frame
        """
        # Ensure same dtype
        frame_a = frame_a.astype(np.float32)
        frame_b = frame_b.astype(np.float32)
        
        # Blend
        blended = frame_a * (1 - alpha) + frame_b * alpha
        
        return blended.astype(np.uint8)
    
    def _blend_rgba(self, frame_a: np.ndarray, frame_b: np.ndarray, alpha: float) -> np.ndarray:
        """
        Blend two RGBA frames (preserve alpha)
        
        Args:
            frame_a: Source frame
            frame_b: Target frame
            alpha: Blend factor (0.0 to 1.0)
        
        Returns:
            Blended frame
        """
        # Blend RGB channels
        rgb_a = frame_a[:, :, :3].astype(np.float32)
        rgb_b = frame_b[:, :, :3].astype(np.float32)
        blended_rgb = rgb_a * (1 - alpha) + rgb_b * alpha
        
        # Blend alpha channels
        alpha_a = frame_a[:, :, 3:4].astype(np.float32)
        alpha_b = frame_b[:, :, 3:4].astype(np.float32)
        blended_alpha = alpha_a * (1 - alpha) + alpha_b * alpha
        
        # Combine
        blended = np.concatenate([blended_rgb, blended_alpha], axis=2)
        
        return blended.astype(np.uint8)
    
    def apply_to_sequence(self, frames: List[np.ndarray], transition_indices: List[int]) -> List[np.ndarray]:
        """
        Apply cross-dissolve to video sequence at specified indices
        
        Args:
            frames: List of frames
            transition_indices: Indices where transitions should occur
        
        Returns:
            List of frames with transitions applied
        """
        if not frames:
            return frames
        
        result = []
        last_transition_frame = None
        
        for i, frame in enumerate(frames):
            if i in transition_indices and last_transition_frame is not None:
                # Apply transition
                transition_frames = self.transition(last_transition_frame, frame)
                result.extend(transition_frames)
            else:
                result.append(frame)
            
            last_transition_frame = frame
        
        return result
    
    def set_frame_count(self, frame_count: int):
        """
        Set number of frames for dissolve
        
        Args:
            frame_count: Number of frames (default 3)
        """
        self.config.frame_count = max(1, frame_count)
        logger.info(f"Dissolve frame count set to {frame_count}")
    
    def set_mode(self, mode: DissolveMode):
        """
        Set dissolve mode
        
        Args:
            mode: Dissolve mode
        """
        self.config.mode = mode
        logger.info(f"Dissolve mode set to {mode.value}")
    
    def get_status(self) -> dict:
        """
        Get dissolve status
        
        Returns:
            Status dictionary
        """
        return {
            "frame_count": self.config.frame_count,
            "mode": self.config.mode.value,
            "preserve_alpha": self.config.preserve_alpha
        }


# Singleton instance
cross_dissolve: Optional[CrossDissolve] = None


def initialize_cross_dissolve(config: DissolveConfig = None) -> CrossDissolve:
    """Initialize Cross Dissolve singleton"""
    global cross_dissolve
    cross_dissolve = CrossDissolve(config)
    return cross_dissolve


def main():
    """Test Cross Dissolve"""
    logger.add("logs/cross_dissolve_{time}.log", rotation="10 MB")
    
    # Initialize dissolve
    dissolve = CrossDissolve()
    
    # Create test frames
    frame_a = np.zeros((480, 640, 3), dtype=np.uint8)
    frame_a[:] = (0, 0, 255)  # Red
    
    frame_b = np.zeros((480, 640, 3), dtype=np.uint8)
    frame_b[:] = (255, 0, 0)  # Blue
    
    # Apply transition
    transition_frames = dissolve.transition(frame_a, frame_b)
    
    logger.info(f"Generated {len(transition_frames)} transition frames")
    
    # Test different modes
    for mode in DissolveMode:
        dissolve.set_mode(mode)
        transition_frames = dissolve.transition(frame_a, frame_b)
        logger.info(f"Mode {mode.value}: {len(transition_frames)} frames")
    
    # Get status
    status = dissolve.get_status()
    logger.info(f"Status: {status}")
    
    logger.info("Cross Dissolve test complete")


if __name__ == "__main__":
    main()
