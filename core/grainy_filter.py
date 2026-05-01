#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Grainy Filter
Adds film grain to hide AI artifacts and make synthetic video look more authentic
Safety Net: Use proactively if LivePortrait looks "off" during important meetings
"""

import cv2
import numpy as np
from typing import Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from loguru import logger


class GrainIntensity(Enum):
    """Grain intensity levels"""
    SUBTLE = "subtle"  # Light grain, barely noticeable
    MODERATE = "moderate"  # Standard film look
    HEAVY = "heavy"  # Strong grain, hides more artifacts
    EXTREME = "extreme"  # Maximum grain for emergency use


@dataclass
class GrainConfig:
    """Grain filter configuration"""
    intensity: GrainIntensity = GrainIntensity.MODERATE
    grain_size: float = 1.0  # Size of grain particles
    monochrome: bool = True  # True for black & white grain, False for color
    temporal_consistency: float = 0.5  # 0-1, how consistent grain is across frames


class GrainyFilter:
    """
    Grainy Filter
    Adds film grain to video to hide AI artifacts and make synthetic content look more authentic
    """
    
    def __init__(self, config: GrainConfig = None):
        """
        Initialize Grainy Filter
        
        Args:
            config: Grain configuration
        """
        self.config = config or GrainConfig()
        self.previous_grain: Optional[np.ndarray] = None
        
        logger.info("Grainy Filter initialized")
    
    def apply(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply grain filter to frame
        
        Args:
            frame: Input frame (BGR)
        
        Returns:
            Frame with grain applied
        """
        if frame is None:
            return frame
        
        # Generate noise
        noise = self._generate_noise(frame.shape[:2])
        
        # Apply temporal consistency
        if self.previous_grain is not None and self.config.temporal_consistency > 0:
            noise = (noise * (1 - self.config.temporal_consistency) + 
                    self.previous_grain * self.config.temporal_consistency)
        
        # Store for next frame
        self.previous_grain = noise
        
        # Add noise to frame
        if self.config.monochrome:
            # Convert to grayscale for noise, then apply to all channels
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            noisy = cv2.add(gray, noise)
            result = cv2.cvtColor(noisy, cv2.COLOR_GRAY2BGR)
        else:
            # Add color noise directly
            result = cv2.add(frame, noise)
        
        return result
    
    def _generate_noise(self, shape: Tuple[int, int]) -> np.ndarray:
        """
        Generate noise pattern
        
        Args:
            shape: Shape of noise (height, width)
        
        Returns:
            Noise array
        """
        # Get intensity parameters
        intensity_params = self._get_intensity_params()
        
        # Generate noise
        noise = np.random.normal(
            loc=0,
            scale=intensity_params['scale'],
            size=shape
        ).astype(np.int16)
        
        # Apply grain size (blur for larger grain)
        if self.config.grain_size > 1.0:
            kernel_size = int(self.config.grain_size * 2) + 1
            noise = cv2.GaussianBlur(noise, (kernel_size, kernel_size), 0)
        
        return noise
    
    def _get_intensity_params(self) -> dict:
        """
        Get intensity parameters based on GrainIntensity
        
        Returns:
            Dictionary with scale and clip values
        """
        intensity_map = {
            GrainIntensity.SUBTLE: {'scale': 5, 'clip': 10},
            GrainIntensity.MODERATE: {'scale': 15, 'clip': 30},
            GrainIntensity.HEAVY: {'scale': 30, 'clip': 50},
            GrainIntensity.EXTREME: {'scale': 50, 'clip': 80}
        }
        
        return intensity_map.get(self.config.intensity, intensity_map[GrainIntensity.MODERATE])
    
    def set_intensity(self, intensity: GrainIntensity):
        """
        Set grain intensity
        
        Args:
            intensity: New intensity level
        """
        self.config.intensity = intensity
        logger.info(f"Grain intensity set to {intensity.value}")
    
    def enable_safety_net(self):
        """
        Enable safety net mode (heavy grain for emergency use)
        """
        self.set_intensity(GrainIntensity.HEAVY)
        logger.warning("Safety Net enabled: Heavy grain to hide AI artifacts")
    
    def disable(self):
        """Disable grain filter"""
        self.previous_grain = None
        logger.info("Grainy Filter disabled")
    
    def get_status(self) -> dict:
        """
        Get filter status
        
        Returns:
            Status dictionary
        """
        return {
            "enabled": True,
            "intensity": self.config.intensity.value,
            "grain_size": self.config.grain_size,
            "monochrome": self.config.monochrome,
            "temporal_consistency": self.config.temporal_consistency
        }


# Singleton instance
grainy_filter: Optional[GrainyFilter] = None


def initialize_grainy_filter(config: GrainConfig = None) -> GrainyFilter:
    """Initialize Grainy Filter singleton"""
    global grainy_filter
    grainy_filter = GrainyFilter(config)
    return grainy_filter


def main():
    """Test Grainy Filter"""
    logger.add("logs/grainy_filter_{time}.log", rotation="10 MB")
    
    # Initialize filter
    filter = GrainyFilter()
    
    # Create test frame
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    test_frame[:] = (100, 150, 200)  # Blue background
    
    # Apply grain
    result = filter.apply(test_frame)
    
    # Test different intensities
    for intensity in GrainIntensity:
        filter.set_intensity(intensity)
        result = filter.apply(test_frame)
        logger.info(f"Applied grain with intensity: {intensity.value}")
    
    # Enable safety net
    filter.enable_safety_net()
    result = filter.apply(test_frame)
    
    # Get status
    status = filter.get_status()
    logger.info(f"Filter status: {status}")
    
    logger.info("Grainy Filter test complete")


if __name__ == "__main__":
    main()
