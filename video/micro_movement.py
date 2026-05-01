#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Micro-movement Generator
Generates natural micro-movements during passive listening to avoid repetitive loops
"""

import sys
import numpy as np
import random
from typing import Optional, Dict, Tuple
from datetime import datetime
from enum import Enum

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class MovementType(Enum):
    """Types of micro-movements"""
    BLINK = "blink"
    EYE_MOVEMENT = "eye_movement"
    GAZE_CORRECTION = "gaze_correction"
    HEAD_TILT = "head_tilt"
    MOUTH_MOVEMENT = "mouth_movement"
    BREATHING = "breathing"
    FIDGET = "fidget"


class MicroMovementGenerator:
    """
    Generates natural micro-movements for passive listening
    Prevents repetitive video loops from being detected
    """
    
    def __init__(self, mood: str = "neutral"):
        """
        Initialize micro-movement generator
        
        Args:
            mood: Current mood (affects movement patterns)
        """
        self.mood = mood
        self.last_movement_time = datetime.now()
        self.movement_intervals = self._get_movement_intervals(mood)
        
        # Movement parameters
        self.blink_probability = self._get_blink_probability(mood)
        self.eye_movement_range = self._get_eye_movement_range(mood)
        self.head_tilt_range = self._get_head_tilt_range(mood)
        
        # Gaze correction state
        self.current_gaze_target = "camera"  # "camera" or "screen"
        self.is_speaking = False
        self.gaze_transition_progress = 0.0
        self.gaze_target_offset = (0.0, 0.0)  # (x, y) offset for gaze
        
        logger.info(f"Micro-movement generator initialized with mood: {mood}")
    
    def _get_movement_intervals(self, mood: str) -> Tuple[float, float]:
        """Get movement interval range based on mood"""
        if mood == "irritated":
            return (2.0, 5.0)  # More frequent movements
        elif mood == "stressed":
            return (1.5, 4.0)  # Even more frequent
        elif mood == "focused":
            return (3.0, 6.0)  # Moderate
        elif mood == "relaxed":
            return (5.0, 10.0)  # Less frequent
        else:  # neutral
            return (3.0, 8.0)  # Normal
    
    def _get_blink_probability(self, mood: str) -> float:
        """Get blink probability based on mood"""
        if mood == "irritated":
            return 0.3  # More blinking
        elif mood == "stressed":
            return 0.35  # Even more blinking
        elif mood == "focused":
            return 0.15  # Less blinking
        elif mood == "relaxed":
            return 0.1  # Very relaxed
        else:  # neutral
            return 0.2  # Normal
    
    def _get_eye_movement_range(self, mood: str) -> Tuple[float, float]:
        """Get eye movement range based on mood"""
        if mood == "irritated":
            return (0.15, 0.3)  # Larger, sharper movements
        elif mood == "stressed":
            return (0.2, 0.35)  # Even larger
        elif mood == "focused":
            return (0.05, 0.15)  # Smaller, precise movements
        elif mood == "relaxed":
            return (0.1, 0.2)  # Gentle movements
        else:  # neutral
            return (0.1, 0.25)  # Normal
    
    def _get_head_tilt_range(self, mood: str) -> Tuple[float, float]:
        """Get head tilt range based on mood"""
        if mood == "irritated":
            return (-0.15, -0.05)  # Slight negative tilt
        elif mood == "stressed":
            return (-0.2, -0.1)  # More negative
        elif mood == "focused":
            return (-0.05, 0.05)  # Minimal tilt
        elif mood == "relaxed":
            return (0.05, 0.15)  # Positive tilt
        else:  # neutral
            return (-0.1, 0.1)  # Normal
    
    def set_mood(self, mood: str):
        """
        Update mood and adjust movement parameters
        
        Args:
            mood: New mood
        """
        self.mood = mood
        self.movement_intervals = self._get_movement_intervals(mood)
        self.blink_probability = self._get_blink_probability(mood)
        self.eye_movement_range = self._get_eye_movement_range(mood)
        self.head_tilt_range = self._get_head_tilt_range(mood)
        logger.info(f"Mood updated to: {mood}")
    
    def set_speaking_state(self, is_speaking: bool):
        """
        Update speaking state for gaze correction
        
        Args:
            is_speaking: True if agent is currently speaking
        """
        self.is_speaking = is_speaking
        
        # Update gaze target based on speaking state
        target = "camera" if is_speaking else "screen"
        if self.current_gaze_target != target:
            self.current_gaze_target = target
            self.gaze_transition_progress = 0.0
            logger.debug(f"Gaze target changed to: {target}")
    
    def generate_gaze_correction(self) -> Dict:
        """
        Generate gaze correction movement
        Simulates looking at camera when speaking, screen when listening
        
        Returns:
            Movement parameters
        """
        # Calculate target offset based on gaze target
        if self.current_gaze_target == "camera":
            # Look directly at camera (minimal offset)
            target_offset = (0.0, 0.0)
        else:
            # Look at screen (slight downward/sideward offset)
            # Simulates looking at screen content or other participants
            target_offset = (
                random.uniform(-0.15, 0.15),  # Slight horizontal
                random.uniform(0.05, 0.2)      # Slight downward
            )
        
        # Smooth transition
        transition_speed = 0.1
        self.gaze_transition_progress = min(1.0, self.gaze_transition_progress + transition_speed)
        
        # Interpolate current offset to target
        current_x = self.gaze_target_offset[0] + (target_offset[0] - self.gaze_target_offset[0]) * self.gaze_transition_progress
        current_y = self.gaze_target_offset[1] + (target_offset[1] - self.gaze_target_offset[1]) * self.gaze_transition_progress
        
        self.gaze_target_offset = (current_x, current_y)
        
        return {
            'type': MovementType.GAZE_CORRECTION,
            'target': self.current_gaze_target,
            'x_offset': current_x,
            'y_offset': current_y,
            'is_speaking': self.is_speaking,
            'transition_progress': self.gaze_transition_progress
        }
    
    def should_generate_movement(self) -> bool:
        """
        Check if a movement should be generated now
        
        Returns:
            True if movement should be generated
        """
        time_since_last = (datetime.now() - self.last_movement_time).total_seconds()
        min_interval, max_interval = self.movement_intervals
        
        return time_since_last >= min_interval and random.random() < 0.3
    
    def generate_blink(self) -> Dict:
        """
        Generate blink movement
        
        Returns:
            Movement parameters
        """
        blink_duration = random.uniform(0.1, 0.3)
        blink_intensity = random.uniform(0.5, 0.9)
        
        return {
            'type': MovementType.BLINK,
            'duration': blink_duration,
            'intensity': blink_intensity
        }
    
    def generate_eye_movement(self) -> Dict:
        """
        Generate eye movement
        
        Returns:
            Movement parameters
        """
        min_range, max_range = self.eye_movement_range
        x_offset = random.uniform(min_range, max_range)
        y_offset = random.uniform(min_range, max_range)
        
        # Occasionally look at different "participants"
        if random.random() < 0.3:
            # Simulate looking at gallery view
            x_offset = random.uniform(-0.3, 0.3)
            y_offset = random.uniform(-0.2, 0.2)
        
        return {
            'type': MovementType.EYE_MOVEMENT,
            'x_offset': x_offset,
            'y_offset': y_offset,
            'duration': random.uniform(0.2, 0.5)
        }
    
    def generate_head_tilt(self) -> Dict:
        """
        Generate head tilt
        
        Returns:
            Movement parameters
        """
        min_tilt, max_tilt = self.head_tilt_range
        tilt = random.uniform(min_tilt, max_tilt)
        
        return {
            'type': MovementType.HEAD_TILT,
            'tilt': tilt,
            'duration': random.uniform(0.5, 1.5)
        }
    
    def generate_mouth_movement(self) -> Dict:
        """
        Generate subtle mouth movement (not speaking)
        
        Returns:
            Movement parameters
        """
        # Subtle mouth adjustment (breathing, swallowing)
        mouth_open = random.uniform(0.0, 0.1)
        
        return {
            'type': MovementType.MOUTH_MOVEMENT,
            'open': mouth_open,
            'duration': random.uniform(0.3, 0.8)
        }
    
    def generate_breathing(self) -> Dict:
        """
        Generate breathing movement
        
        Returns:
            Movement parameters
        """
        breath_cycle = random.uniform(3.0, 5.0)  # Breathing cycle in seconds
        intensity = random.uniform(0.5, 1.0)
        
        return {
            'type': MovementType.BREATHING,
            'cycle': breath_cycle,
            'intensity': intensity
        }
    
    def generate_fidget(self) -> Dict:
        """
        Generate fidget movement (adjust posture, etc.)
        
        Returns:
            Movement parameters
        """
        fidget_types = ["adjust_posture", "shift_weight", "stretch"]
        fidget_type = random.choice(fidget_types)
        
        return {
            'type': MovementType.FIDGET,
            'fidget_type': fidget_type,
            'duration': random.uniform(1.0, 2.0)
        }
    
    def get_next_movement(self) -> Optional[Dict]:
        """
        Get next random micro-movement
        
        Returns:
            Movement parameters or None if no movement
        """
        if not self.should_generate_movement():
            return None
        
        # Choose movement type based on probability
        # Prioritize gaze correction when speaking
        if self.is_speaking and random.random() < 0.4:
            movement_type = MovementType.GAZE_CORRECTION
        else:
            movement_type = random.choices(
                [MovementType.BLINK, MovementType.EYE_MOVEMENT, MovementType.HEAD_TILT,
                 MovementType.MOUTH_MOVEMENT, MovementType.BREATHING, MovementType.FIDGET,
                 MovementType.GAZE_CORRECTION],
                weights=[self.blink_probability, 0.25, 0.12, 0.08, 0.15, 0.05, 0.1]
            )[0]
        
        # Generate movement
        if movement_type == MovementType.BLINK:
            movement = self.generate_blink()
        elif movement_type == MovementType.EYE_MOVEMENT:
            movement = self.generate_eye_movement()
        elif movement_type == MovementType.HEAD_TILT:
            movement = self.generate_head_tilt()
        elif movement_type == MovementType.MOUTH_MOVEMENT:
            movement = self.generate_mouth_movement()
        elif movement_type == MovementType.BREATHING:
            movement = self.generate_breathing()
        elif movement_type == MovementType.FIDGET:
            movement = self.generate_fidget()
        elif movement_type == MovementType.GAZE_CORRECTION:
            movement = self.generate_gaze_correction()
        else:
            movement = None
        
        if movement:
            self.last_movement_time = datetime.now()
        
        return movement
    
    def apply_to_frame(self, frame: np.ndarray, movement: Dict) -> np.ndarray:
        """
        Apply micro-movement to frame
        
        Args:
            frame: Input frame
            movement: Movement parameters
        
        Returns:
            Frame with movement applied
        """
        if movement is None:
            return frame
        
        # Apply movement based on type
        # In production, this would integrate with LivePortrait or video animator
        # For now, return frame as placeholder
        
        return frame
    
    def get_status(self) -> Dict:
        """
        Get generator status
        
        Returns:
            Status dictionary
        """
        return {
            'mood': self.mood,
            'blink_probability': self.blink_probability,
            'movement_intervals': self.movement_intervals,
            'time_since_last_movement': (datetime.now() - self.last_movement_time).total_seconds()
        }


class ContinuousMovementEngine:
    """
    Continuous movement engine
    Generates smooth, continuous movements over time
    """
    
    def __init__(self, mood: str = "neutral"):
        """
        Initialize continuous movement engine
        
        Args:
            mood: Current mood
        """
        self.mood = mood
        self.generator = MicroMovementGenerator(mood)
        
        # Current movement state
        self.current_movement = None
        self.movement_progress = 0.0
        self.movement_start_time = None
        
        logger.info("Continuous movement engine initialized")
    
    def update(self, dt: float) -> Optional[Dict]:
        """
        Update movement state
        
        Args:
            dt: Time delta in seconds
        
        Returns:
            Current movement parameters
        """
        # Check if current movement is complete
        if self.current_movement is None:
            # Get new movement
            self.current_movement = self.generator.get_next_movement()
            if self.current_movement:
                self.movement_progress = 0.0
                self.movement_start_time = datetime.now()
                return self.current_movement
        else:
            # Update progress
            if self.movement_start_time:
                elapsed = (datetime.now() - self.movement_start_time).total_seconds()
                duration = self.current_movement.get('duration', 1.0)
                self.movement_progress = elapsed / duration
                
                # Check if complete
                if self.movement_progress >= 1.0:
                    self.current_movement = None
                    self.movement_progress = 0.0
                    self.movement_start_time = None
                else:
                    return self.current_movement
        
        return None
    
    def set_mood(self, mood: str):
        """
        Update mood
        
        Args:
            mood: New mood
        """
        self.mood = mood
        self.generator.set_mood(mood)
    
    def set_speaking_state(self, is_speaking: bool):
        """
        Update speaking state for gaze correction
        
        Args:
            is_speaking: True if agent is currently speaking
        """
        self.generator.set_speaking_state(is_speaking)


def main():
    """Test micro-movement generator"""
    from loguru import logger
    
    logger.add("logs/micro_movement_{time}.log", rotation="10 MB")
    
    # Create generator
    generator = MicroMovementGenerator("neutral")
    
    # Generate movements
    for i in range(10):
        movement = generator.get_next_movement()
        if movement:
            logger.info(f"Movement {i+1}: {movement['type'].value}")
        else:
            logger.info(f"No movement generated {i+1}")
    
    # Test mood change
    generator.set_mood("irritated")
    logger.info(f"Mood changed to irritated: {generator.get_status()}")
    
    # Test continuous engine
    engine = ContinuousMovementEngine("neutral")
    for i in range(5):
        movement = engine.update(0.1)
        if movement:
            logger.info(f"Continuous movement {i+1}: {movement['type'].value}")
    
    logger.info("Micro-movement generator test complete")


if __name__ == "__main__":
    main()
