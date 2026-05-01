#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Color Matcher
Automatic lighting/color matching between pre-recorded video and real-time environment
"""

import sys
import numpy as np
import cv2
from typing import Optional, Tuple, Dict
from datetime import datetime
from collections import deque

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class ColorMatcher:
    """
    Color matching and correction module
    Adjusts pre-recorded video to match real-time lighting conditions
    """
    
    def __init__(self, buffer_size: int = 10):
        """
        Initialize color matcher
        
        Args:
            buffer_size: Number of frames to average for lighting analysis
        """
        self.buffer_size = buffer_size
        self.frame_buffer = deque(maxlen=buffer_size)
        
        # Reference lighting profile (from pre-recorded video)
        self.reference_profile = None
        
        # Current lighting profile (from real-time environment)
        self.current_profile = None
        
        # Adjustment parameters
        self.gamma = 1.0
        self.brightness = 0
        self.contrast = 1.0
        self.saturation = 1.0
        
        logger.info("Color matcher initialized")
    
    def analyze_frame(self, frame: np.ndarray) -> Dict[str, float]:
        """
        Analyze frame lighting characteristics
        
        Args:
            frame: Input frame (BGR format)
        
        Returns:
            Dictionary with lighting metrics
        """
        # Convert to LAB color space for better lighting analysis
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        
        # Split channels
        l, a, b = cv2.split(lab)
        
        # Calculate statistics
        metrics = {
            'brightness': np.mean(l),
            'contrast': np.std(l),
            'saturation': np.mean(np.sqrt(a**2 + b**2)),
            'avg_color': np.mean(frame, axis=(0, 1))
        }
        
        return metrics
    
    def set_reference_profile(self, reference_frame: np.ndarray):
        """
        Set reference lighting profile from pre-recorded video
        
        Args:
            reference_frame: Frame from pre-recorded video
        """
        self.reference_profile = self.analyze_frame(reference_frame)
        logger.info(f"Reference profile set: brightness={self.reference_profile['brightness']:.2f}")
    
    def update_current_profile(self, frame: np.ndarray):
        """
        Update current lighting profile from real-time environment
        
        Args:
            frame: Current frame from camera
        """
        profile = self.analyze_frame(frame)
        self.frame_buffer.append(profile)
        
        # Calculate average profile
        if len(self.frame_buffer) == self.buffer_size:
            profiles = list(self.frame_buffer)
            self.current_profile = {
                'brightness': np.mean([p['brightness'] for p in profiles]),
                'contrast': np.mean([p['contrast'] for p in profiles]),
                'saturation': np.mean([p['saturation'] for p in profiles]),
                'avg_color': np.mean([p['avg_color'] for p in profiles], axis=0)
            }
    
    def calculate_adjustments(self) -> Dict[str, float]:
        """
        Calculate color adjustments based on reference and current profiles
        
        Returns:
            Dictionary with adjustment parameters
        """
        if self.reference_profile is None or self.current_profile is None:
            return {'gamma': 1.0, 'brightness': 0, 'contrast': 1.0, 'saturation': 1.0}
        
        ref = self.reference_profile
        curr = self.current_profile
        
        # Calculate brightness adjustment
        brightness_diff = ref['brightness'] - curr['brightness']
        self.brightness = brightness_diff * 0.5  # Apply 50% of difference
        
        # Calculate contrast adjustment
        contrast_ratio = ref['contrast'] / (curr['contrast'] + 1e-6)
        self.contrast = np.clip(contrast_ratio, 0.5, 2.0)
        
        # Calculate saturation adjustment
        saturation_ratio = ref['saturation'] / (curr['saturation'] + 1e-6)
        self.saturation = np.clip(saturation_ratio, 0.5, 2.0)
        
        # Calculate gamma based on brightness difference
        if brightness_diff > 20:
            self.gamma = 0.9  # Darken
        elif brightness_diff < -20:
            self.gamma = 1.1  # Brighten
        else:
            self.gamma = 1.0
        
        return {
            'gamma': self.gamma,
            'brightness': self.brightness,
            'contrast': self.contrast,
            'saturation': self.saturation
        }
    
    def apply_adjustments(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply color adjustments to frame
        
        Args:
            frame: Input frame (BGR format)
        
        Returns:
            Adjusted frame
        """
        adjusted = frame.copy()
        
        # Apply brightness
        if self.brightness != 0:
            adjusted = cv2.add(adjusted, np.ones(adjusted.shape, dtype=np.uint8) * int(self.brightness))
        
        # Apply contrast
        if self.contrast != 1.0:
            adjusted = cv2.convertScaleAbs(adjusted, alpha=self.contrast, beta=0)
        
        # Apply gamma
        if self.gamma != 1.0:
            # Build lookup table
            table = np.array([((i / 255.0) ** (1.0 / self.gamma)) * 255 for i in range(256)]).astype(np.uint8)
            adjusted = cv2.LUT(adjusted, table)
        
        # Apply saturation
        if self.saturation != 1.0:
            hsv = cv2.cvtColor(adjusted, cv2.COLOR_BGR2HSV)
            hsv[:, :, 1] = np.clip(hsv[:, :, 1] * self.saturation, 0, 255)
            adjusted = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        
        return adjusted
    
    def match_frame(self, frame: np.ndarray, current_frame: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Match frame lighting to current environment
        
        Args:
            frame: Frame to adjust (from pre-recorded video)
            current_frame: Current environment frame (optional)
        
        Returns:
            Adjusted frame
        """
        # Update current profile if current frame provided
        if current_frame is not None:
            self.update_current_profile(current_frame)
        
        # Calculate adjustments
        adjustments = self.calculate_adjustments()
        
        # Apply adjustments
        adjusted_frame = self.apply_adjustments(frame)
        
        return adjusted_frame
    
    def get_time_based_adjustment(self) -> Dict[str, float]:
        """
        Get time-based color adjustment based on current time
        
        Returns:
            Dictionary with time-based adjustments
        """
        now = datetime.now()
        hour = now.hour
        
        # Time-based adjustments
        if 6 <= hour < 10:  # Morning
            return {'gamma': 1.05, 'brightness': 10, 'contrast': 1.1, 'saturation': 1.1}
        elif 10 <= hour < 16:  # Midday
            return {'gamma': 1.0, 'brightness': 0, 'contrast': 1.0, 'saturation': 1.0}
        elif 16 <= hour < 19:  # Afternoon
            return {'gamma': 0.95, 'brightness': -10, 'contrast': 0.9, 'saturation': 0.9}
        else:  # Evening/Night
            return {'gamma': 0.85, 'brightness': -20, 'contrast': 0.8, 'saturation': 0.8}
    
    def get_status(self) -> Dict:
        """
        Get color matcher status
        
        Returns:
            Status dictionary
        """
        return {
            'reference_profile': self.reference_profile is not None,
            'current_profile': self.current_profile is not None,
            'gamma': self.gamma,
            'brightness': self.brightness,
            'contrast': self.contrast,
            'saturation': self.saturation
        }


class ShadowEngine:
    """
    Shadow Engine - Advanced lighting matching
    Analyzes and matches shadows and lighting direction
    """
    
    def __init__(self):
        """Initialize shadow engine"""
        self.light_direction = None
        self.shadow_intensity = 0.5
        self.ambient_light = 0.5
        
        logger.info("Shadow engine initialized")
    
    def detect_light_direction(self, frame: np.ndarray) -> Tuple[float, float]:
        """
        Detect light direction from frame using edge analysis
        
        Args:
            frame: Input frame
        
        Returns:
            (x, y) direction vector
        """
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150)
        
        # Calculate gradients
        grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        
        # Average gradient direction
        x_dir = np.mean(grad_x)
        y_dir = np.mean(grad_y)
        
        # Normalize
        magnitude = np.sqrt(x_dir**2 + y_dir**2)
        if magnitude > 0:
            x_dir /= magnitude
            y_dir /= magnitude
        
        return (float(x_dir), float(y_dir))
    
    def match_shadows(self, frame: np.ndarray, target_direction: Tuple[float, float]) -> np.ndarray:
        """
        Match shadows to target light direction
        
        Args:
            frame: Input frame
            target_direction: Target light direction (x, y)
        
        Returns:
            Frame with matched shadows
        """
        # Detect current light direction
        current_dir = self.detect_light_direction(frame)
        
        # Calculate angle difference
        angle_diff = np.arctan2(target_direction[1], target_direction[0]) - np.arctan2(current_dir[1], current_dir[0])
        
        # Apply rotation to match direction
        # In production, use more sophisticated shadow matching
        if abs(angle_diff) > 0.1:
            # Rotate frame slightly to match light direction
            center = (frame.shape[1] // 2, frame.shape[0] // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, np.degrees(angle_diff), 1.0)
            frame = cv2.warpAffine(frame, rotation_matrix, (frame.shape[1], frame.shape[0]))
        
        return frame


def main():
    """Test color matcher"""
    from loguru import logger
    
    logger.add("logs/color_matcher_{time}.log", rotation="10 MB")
    
    # Create color matcher
    matcher = ColorMatcher()
    
    # Create test frame
    test_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Set reference profile
    matcher.set_reference_profile(test_frame)
    
    # Update current profile
    darker_frame = (test_frame * 0.7).astype(np.uint8)
    matcher.update_current_profile(darker_frame)
    
    # Calculate adjustments
    adjustments = matcher.calculate_adjustments()
    logger.info(f"Color adjustments: {adjustments}")
    
    # Apply adjustments
    adjusted_frame = matcher.apply_adjustments(test_frame)
    logger.info(f"Original brightness: {np.mean(test_frame):.2f}")
    logger.info(f"Adjusted brightness: {np.mean(adjusted_frame):.2f}")
    
    logger.info("Color matcher test complete")


if __name__ == "__main__":
    main()
