#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Deepfake Defense: Texture Imperfection Generator
Adds subtle camera-like imperfections to AI-generated video to avoid synthetic detection.
Simulates cheap webcam artifacts: sensor noise, slight blur, compression, color shift.
"""

import sys
import random
import numpy as np
from typing import Optional, Dict, Any, Tuple
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

try:
    import cv2
except ImportError:
    cv2 = None
    logger.warning("OpenCV not available - texture imperfection disabled")


class WebcamProfile(Enum):
    """Simulated webcam quality profiles"""
    LOGITECH_C920 = "logitech_c920"      # Good webcam, minimal artifacts
    BUILTIN_LAPTOP = "builtin_laptop"      # Typical laptop webcam, more noise
    CHEAP_USB = "cheap_usb"                # Cheap USB cam, lots of artifacts
    CUSTOM = "custom"                       # User-defined profile


class TextureImperfectionConfig(BaseModel):
    """Configuration for Texture Imperfection Generator"""
    enabled: bool = Field(default=True, description="Enable texture imperfections")
    webcam_profile: str = Field(default="builtin_laptop", description="Simulated webcam quality")
    
    # Noise
    sensor_noise_intensity: float = Field(default=0.015, description="Gaussian sensor noise (0-0.1)")
    hot_pixel_chance: float = Field(default=0.0001, description="Chance of hot pixel per frame")
    
    # Blur & Sharpness
    micro_blur_chance: float = Field(default=0.05, description="Chance of slight autofocus blur per frame")
    micro_blur_kernel: int = Field(default=3, description="Blur kernel size (odd number)")
    
    # Compression
    jpeg_quality_min: int = Field(default=82, description="Min JPEG quality (simulates compression)")
    jpeg_quality_max: int = Field(default=95, description="Max JPEG quality")
    
    # Color
    white_balance_drift: float = Field(default=0.02, description="White balance drift magnitude")
    exposure_flicker: float = Field(default=0.01, description="Exposure flicker magnitude")
    
    # Temporal
    frame_drop_chance: float = Field(default=0.005, description="Chance of duplicating previous frame")


# Preset profiles
WEBCAM_PROFILES = {
    "logitech_c920": TextureImperfectionConfig(
        sensor_noise_intensity=0.008,
        hot_pixel_chance=0.00005,
        micro_blur_chance=0.02,
        jpeg_quality_min=88,
        jpeg_quality_max=95,
        white_balance_drift=0.01,
        exposure_flicker=0.005,
        frame_drop_chance=0.002
    ),
    "builtin_laptop": TextureImperfectionConfig(
        sensor_noise_intensity=0.018,
        hot_pixel_chance=0.0002,
        micro_blur_chance=0.06,
        jpeg_quality_min=78,
        jpeg_quality_max=90,
        white_balance_drift=0.025,
        exposure_flicker=0.015,
        frame_drop_chance=0.008
    ),
    "cheap_usb": TextureImperfectionConfig(
        sensor_noise_intensity=0.035,
        hot_pixel_chance=0.0005,
        micro_blur_chance=0.10,
        micro_blur_kernel=5,
        jpeg_quality_min=65,
        jpeg_quality_max=82,
        white_balance_drift=0.04,
        exposure_flicker=0.03,
        frame_drop_chance=0.015
    )
}


class TextureImperfectionGenerator:
    """
    Deepfake Defense - Texture Imperfection Generator
    Adds realistic webcam-like imperfections to AI-generated video frames
    to make them harder to detect as synthetic by platform algorithms.
    """
    
    def __init__(self, config: Optional[TextureImperfectionConfig] = None, webcam_profile: str = "builtin_laptop"):
        """
        Initialize Texture Imperfection Generator
        
        Args:
            config: Custom config (overrides profile)
            webcam_profile: Webcam profile preset
        """
        if config:
            self.config = config
        elif webcam_profile in WEBCAM_PROFILES:
            self.config = WEBCAM_PROFILES[webcam_profile]
        else:
            self.config = TextureImperfectionConfig()
        
        # State for temporal effects
        self.previous_frame: Optional[np.ndarray] = None
        self.frame_count: int = 0
        self.current_wb_offset: np.ndarray = np.zeros(3, dtype=np.float32)
        self.current_exposure_offset: float = 0.0
        
        logger.info(f"Texture Imperfection Generator initialized (profile: {webcam_profile})")
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply webcam-like imperfections to a frame
        
        Args:
            frame: Input frame (BGR, uint8)
        
        Returns:
            Frame with imperfections applied
        """
        if not self.config.enabled or cv2 is None:
            return frame
        
        self.frame_count += 1
        result = frame.copy()
        
        # 1. Frame drop simulation (duplicate previous frame)
        if self.previous_frame is not None and random.random() < self.config.frame_drop_chance:
            result = self.previous_frame.copy()
            logger.debug(f"Frame drop simulated at frame {self.frame_count}")
            return result
        
        # 2. Sensor noise (Gaussian)
        result = self._add_sensor_noise(result)
        
        # 3. Hot pixels (salt noise)
        result = self._add_hot_pixels(result)
        
        # 4. Micro-blur (autofocus drift)
        result = self._add_micro_blur(result)
        
        # 5. White balance drift
        result = self._add_white_balance_drift(result)
        
        # 6. Exposure flicker
        result = self._add_exposure_flicker(result)
        
        # 7. JPEG compression artifacts
        result = self._add_compression_artifacts(result)
        
        # Store for frame drop simulation
        self.previous_frame = result.copy()
        
        return result
    
    def _add_sensor_noise(self, frame: np.ndarray) -> np.ndarray:
        """Add Gaussian sensor noise"""
        if self.config.sensor_noise_intensity <= 0:
            return frame
        
        noise = np.random.normal(0, self.config.sensor_noise_intensity * 255, frame.shape).astype(np.float32)
        result = np.clip(frame.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        return result
    
    def _add_hot_pixels(self, frame: np.ndarray) -> np.ndarray:
        """Add random hot pixels (stuck bright pixels from cheap sensors)"""
        if self.config.hot_pixel_chance <= 0:
            return frame
        
        h, w = frame.shape[:2]
        num_hot_pixels = int(h * w * self.config.hot_pixel_chance)
        
        for _ in range(num_hot_pixels):
            y = random.randint(0, h - 1)
            x = random.randint(0, w - 1)
            frame[y, x] = [255, 255, 255]  # Bright white hot pixel
        
        return frame
    
    def _add_micro_blur(self, frame: np.ndarray) -> np.ndarray:
        """Add occasional slight autofocus blur"""
        if random.random() >= self.config.micro_blur_chance:
            return frame
        
        kernel_size = self.config.micro_blur_kernel
        if kernel_size % 2 == 0:
            kernel_size += 1
        
        return cv2.GaussianBlur(frame, (kernel_size, kernel_size), 0)
    
    def _add_white_balance_drift(self, frame: np.ndarray) -> np.ndarray:
        """Add slow white balance drift (simulates auto-WB adjustment)"""
        drift_speed = 0.1  # How fast WB changes
        target = np.random.normal(0, self.config.white_balance_drift, 3).astype(np.float32)
        
        # Smooth transition (lerp towards target)
        self.current_wb_offset = self.current_wb_offset * (1 - drift_speed) + target * drift_speed
        
        # Apply offset to channels
        result = frame.astype(np.float32)
        for c in range(3):
            result[:, :, c] = np.clip(result[:, :, c] + self.current_wb_offset[c] * 255, 0, 255)
        
        return result.astype(np.uint8)
    
    def _add_exposure_flicker(self, frame: np.ndarray) -> np.ndarray:
        """Add subtle exposure flicker (simulates auto-exposure adjustments)"""
        drift_speed = 0.15
        target = random.gauss(0, self.config.exposure_flicker)
        
        self.current_exposure_offset = self.current_exposure_offset * (1 - drift_speed) + target * drift_speed
        
        result = frame.astype(np.float32)
        result = np.clip(result + self.current_exposure_offset * 255, 0, 255)
        
        return result.astype(np.uint8)
    
    def _add_compression_artifacts(self, frame: np.ndarray) -> np.ndarray:
        """Add JPEG compression artifacts"""
        quality = random.randint(self.config.jpeg_quality_min, self.config.jpeg_quality_max)
        
        # Encode and decode as JPEG to introduce compression artifacts
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
        _, encoded = cv2.imencode('.jpg', frame, encode_param)
        result = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get generator status
        
        Returns:
            Status dictionary
        """
        return {
            "enabled": self.config.enabled,
            "frame_count": self.frame_count,
            "sensor_noise": self.config.sensor_noise_intensity,
            "wb_offset": self.current_wb_offset.tolist(),
            "exposure_offset": round(self.current_exposure_offset, 4)
        }


def main():
    """Test the Texture Imperfection Generator"""
    from loguru import logger
    
    logger.add("logs/texture_imperfection_{time}.log", rotation="10 MB")
    
    if cv2 is None:
        logger.error("OpenCV required for texture imperfection test")
        return
    
    # Create generator with built-in laptop profile
    generator = TextureImperfectionGenerator(webcam_profile="builtin_laptop")
    
    # Create a synthetic "perfect" frame (solid gradient - looks too clean)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:, :, 0] = np.linspace(100, 200, 640).astype(np.uint8)  # Blue gradient
    frame[:, :, 1] = 150  # Green constant
    frame[:, :, 2] = 180  # Red constant
    
    # Process 10 frames
    for i in range(10):
        result = generator.process_frame(frame)
        logger.info(f"Frame {i}: input mean={frame.mean():.1f}, output mean={result.mean():.1f}")
    
    # Get status
    status = generator.get_status()
    logger.info(f"Generator status: {status}")
    
    logger.info("Texture Imperfection Generator test complete")


if __name__ == "__main__":
    main()
