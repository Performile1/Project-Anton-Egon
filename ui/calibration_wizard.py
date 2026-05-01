#!/usr/bin/env python3
"""
Project Anton Egon - Calibration Wizard
Face mapping for LivePortrait outfits

Phase 16: The Trickster Engine
"""

import cv2
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
import json

import mediapipe as mp
from loguru import logger


class CalibrationStep(Enum):
    """Calibration steps"""
    NEUTRAL_EXPRESSION = "neutral_expression"
    MOUTH_OPEN = "mouth_open"
    EYES_CLOSED = "eyes_closed"
    HEAD_LEFT = "head_left"
    HEAD_RIGHT = "head_right"
    HEAD_UP = "head_up"
    HEAD_DOWN = "head_down"
    SMILE = "smile"
    FROWN = "frown"
    VOICE_SOFT = "voice_soft"  # Phase 17: Voice calibration
    VOICE_NORMAL = "voice_normal"
    VOICE_LOUD = "voice_loud"


@dataclass
class CalibrationData:
    """Calibration data for an outfit"""
    outfit_id: str
    outfit_name: str
    landmarks: Dict[str, List[Tuple[float, float]]] = field(default_factory=dict)
    eye_left_center: Optional[Tuple[float, float]] = None
    eye_right_center: Optional[Tuple[float, float]] = None
    mouth_center: Optional[Tuple[float, float]] = None
    nose_tip: Optional[Tuple[float, float]] = None
    face_bbox: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h
    # Phase 17: Voice calibration data
    voice_volume_map: Dict[str, float] = field(default_factory=dict)  # soft/normal/loud -> mouth_openness
    mouth_openness_baseline: float = 0.0  # Neutral mouth openness
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "outfit_id": self.outfit_id,
            "outfit_name": self.outfit_name,
            "landmarks": self.landmarks,
            "eye_left_center": self.eye_left_center,
            "eye_right_center": self.eye_right_center,
            "mouth_center": self.mouth_center,
            "nose_tip": self.nose_tip,
            "face_bbox": self.face_bbox,
            "voice_volume_map": self.voice_volume_map,
            "mouth_openness_baseline": self.mouth_openness_baseline,
            "created_at": self.created_at
        }


class CalibrationWizard:
    """
    Calibration Wizard
    Guides user through face mapping for LivePortrait outfits
    """
    
    def __init__(self, calibration_path: Optional[str] = None):
        """
        Initialize Calibration Wizard
        
        Args:
            calibration_path: Path to calibration data file
        """
        self.calibration_path = calibration_path or "config/calibration_data.json"
        self.calibrations: Dict[str, CalibrationData] = {}
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Landmark indices for key facial features
        self.key_landmarks = {
            "left_eye": [33, 160, 158, 133, 153, 144],
            "right_eye": [362, 385, 387, 263, 373, 380],
            "mouth": [61, 146, 91, 181, 84, 17, 314, 405],
            "nose": [1, 2, 98, 327, 164],
            "jaw": [234, 454, 152, 377, 400]
        }
        
        self._load_calibrations()
        logger.info("Calibration Wizard initialized")
    
    def _load_calibrations(self):
        """Load calibration data from file"""
        try:
            path = Path(self.calibration_path)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for outfit_id, calib_data in data.get('calibrations', {}).items():
                        calib = CalibrationData(
                            outfit_id=outfit_id,
                            outfit_name=calib_data.get('outfit_name', ''),
                            landmarks=calib_data.get('landmarks', {}),
                            eye_left_center=tuple(calib_data.get('eye_left_center')) if calib_data.get('eye_left_center') else None,
                            eye_right_center=tuple(calib_data.get('eye_right_center')) if calib_data.get('eye_right_center') else None,
                            mouth_center=tuple(calib_data.get('mouth_center')) if calib_data.get('mouth_center') else None,
                            nose_tip=tuple(calib_data.get('nose_tip')) if calib_data.get('nose_tip') else None,
                            face_bbox=tuple(calib_data.get('face_bbox')) if calib_data.get('face_bbox') else None,
                            created_at=calib_data.get('created_at', '')
                        )
                        self.calibrations[outfit_id] = calib
                logger.info(f"Loaded {len(self.calibrations)} calibrations")
        except Exception as e:
            logger.error(f"Failed to load calibrations: {e}")
    
    def _save_calibrations(self):
        """Save calibration data to file"""
        try:
            path = Path(self.calibration_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'version': '1.0',
                'last_updated': datetime.now().isoformat(),
                'calibrations': {
                    outfit_id: calib.to_dict()
                    for outfit_id, calib in self.calibrations.items()
                }
            }
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(self.calibrations)} calibrations")
        except Exception as e:
            logger.error(f"Failed to save calibrations: {e}")
    
    def start_calibration(self, outfit_id: str, outfit_name: str) -> bool:
        """
        Start new calibration for an outfit
        
        Args:
            outfit_id: Outfit ID
            outfit_name: Outfit name
        
        Returns:
            True if started successfully
        """
        if outfit_id in self.calibrations:
            logger.warning(f"Calibration already exists for {outfit_id}")
            return False
        
        self.calibrations[outfit_id] = CalibrationData(
            outfit_id=outfit_id,
            outfit_name=outfit_name
        )
        
        logger.info(f"Started calibration for {outfit_name}")
        return True
    
    def capture_frame(self, frame: np.ndarray, outfit_id: str, step: CalibrationStep) -> bool:
        """
        Capture frame for calibration step
        
        Args:
            frame: Input frame (BGR)
            outfit_id: Outfit ID
            step: Calibration step
        
        Returns:
            True if captured successfully
        """
        if outfit_id not in self.calibrations:
            logger.warning(f"No calibration for outfit: {outfit_id}")
            return False
        
        # Convert to RGB for Mediapipe
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(frame_rgb)
        
        if not results.multi_face_landmarks:
            logger.warning("No face detected")
            return False
        
        face_landmarks = results.multi_face_landmarks[0]
        h, w = frame.shape[:2]
        
        # Extract landmarks
        landmarks = {}
        for feature, indices in self.key_landmarks.items():
            landmarks[feature] = [
                (face_landmarks.landmark[idx].x * w, face_landmarks.landmark[idx].y * h)
                for idx in indices
            ]
        
        # Calculate key points
        eye_left_center = self._calculate_center(landmarks.get('left_eye', []))
        eye_right_center = self._calculate_center(landmarks.get('right_eye', []))
        mouth_center = self._calculate_center(landmarks.get('mouth', []))
        nose_tip = landmarks.get('nose', [(0, 0)])[0] if landmarks.get('nose') else None
        
        # Calculate face bounding box
        all_points = [point for points in landmarks.values() for point in points]
        if all_points:
            x_coords = [p[0] for p in all_points]
            y_coords = [p[1] for p in all_points]
            face_bbox = (
                int(min(x_coords)),
                int(min(y_coords)),
                int(max(x_coords) - min(x_coords)),
                int(max(y_coords) - min(y_coords))
            )
        else:
            face_bbox = None
        
        # Store calibration data
        calib = self.calibrations[outfit_id]
        calib.landmarks[step.value] = landmarks
        calib.eye_left_center = eye_left_center
        calib.eye_right_center = eye_right_center
        calib.mouth_center = mouth_center
        calib.nose_tip = nose_tip
        calib.face_bbox = face_bbox
        
        self._save_calibrations()
        logger.info(f"Captured frame for step: {step.value}")
        
        return True
    
    def _calculate_center(self, points: List[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
        """
        Calculate center point of landmarks
        
        Args:
            points: List of (x, y) coordinates
        
        Returns:
            Center point or None
        """
        if not points:
            return None
        
        avg_x = sum(p[0] for p in points) / len(points)
        avg_y = sum(p[1] for p in points) / len(points)
        
        return (avg_x, avg_y)
    
    def get_calibration(self, outfit_id: str) -> Optional[CalibrationData]:
        """
        Get calibration data for an outfit
        
        Args:
            outfit_id: Outfit ID
        
        Returns:
            Calibration data or None
        """
        return self.calibrations.get(outfit_id)
    
    def get_all_calibrations(self) -> List[Dict[str, Any]]:
        """Get all calibrations"""
        return [calib.to_dict() for calib in self.calibrations.values()]
    
    def delete_calibration(self, outfit_id: str) -> bool:
        """
        Delete calibration for an outfit
        
        Args:
            outfit_id: Outfit ID
        
        Returns:
            True if deleted successfully
        """
        if outfit_id not in self.calibrations:
            logger.warning(f"No calibration for outfit: {outfit_id}")
            return False
        
        del self.calibrations[outfit_id]
        self._save_calibrations()
        
        logger.info(f"Deleted calibration for {outfit_id}")
        return True
    
    def get_calibration_progress(self, outfit_id: str) -> Dict[str, Any]:
        """
        Get calibration progress for an outfit
        
        Args:
            outfit_id: Outfit ID
        
        Returns:
            Progress dictionary
        """
        calib = self.calibrations.get(outfit_id)
        if not calib:
            return {"outfit_id": outfit_id, "progress": 0, "steps_completed": []}
        
        total_steps = len(CalibrationStep)
        completed_steps = len(calib.landmarks)
        
        return {
            "outfit_id": outfit_id,
            "outfit_name": calib.outfit_name,
            "progress": completed_steps / total_steps,
            "steps_completed": list(calib.landmarks.keys()),
            "total_steps": total_steps
        }
    
    def get_next_step(self, outfit_id: str) -> Optional[CalibrationStep]:
        """
        Get next calibration step for an outfit
        
        Args:
            outfit_id: Outfit ID
        
        Returns:
            Next step or None if complete
        """
        calib = self.calibrations.get(outfit_id)
        if not calib:
            return CalibrationStep.NEUTRAL_EXPRESSION
        
        completed = set(calib.landmarks.keys())
        
        for step in CalibrationStep:
            if step.value not in completed:
                return step
        
        return None  # All steps completed
    
    # ═══════════════════════════════════════════════════════════════
    # VOICE CALIBRATION (Phase 17)
    # ═══════════════════════════════════════════════════════════════
    def calculate_mouth_openness(self, landmarks: Dict[str, List[Tuple[float, float]]]) -> float:
        """
        Calculate mouth openness from landmarks
        
        Args:
            landmarks: Face landmarks dictionary
        
        Returns:
            Mouth openness value (0.0 - 1.0)
        """
        if "mouth" not in landmarks:
            return 0.0
        
        mouth_points = landmarks["mouth"]
        if len(mouth_points) < 4:
            return 0.0
        
        # Calculate distance between upper and lower lip
        upper_lip = mouth_points[0]  # Top center
        lower_lip = mouth_points[3]  # Bottom center
        
        distance = ((upper_lip[0] - lower_lip[0]) ** 2 + (upper_lip[1] - lower_lip[1]) ** 2) ** 0.5
        
        # Normalize (typical range 0-50 pixels, normalize to 0-1)
        openness = min(distance / 50.0, 1.0)
        
        return openness
    
    def capture_voice_calibration(
        self,
        frame: np.ndarray,
        outfit_id: str,
        voice_level: str,
        audio_volume: float
    ) -> bool:
        """
        Capture voice calibration frame
        
        Args:
            frame: Input frame (BGR)
            outfit_id: Outfit ID
            voice_level: "soft", "normal", or "loud"
            audio_volume: Audio volume level (0.0 - 1.0)
        
        Returns:
            True if captured successfully
        """
        if outfit_id not in self.calibrations:
            logger.warning(f"No calibration for outfit: {outfit_id}")
            return False
        
        # Extract landmarks
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(frame_rgb)
        
        if not results.multi_face_landmarks:
            logger.warning("No face detected")
            return False
        
        face_landmarks = results.multi_face_landmarks[0]
        h, w = frame.shape[:2]
        
        # Extract mouth landmarks
        mouth_landmarks = {}
        for feature, indices in self.key_landmarks.items():
            if feature == "mouth":
                mouth_landmarks[feature] = [
                    (face_landmarks.landmark[idx].x * w, face_landmarks.landmark[idx].y * h)
                    for idx in indices
                ]
        
        # Calculate mouth openness
        mouth_openness = self.calculate_mouth_openness(mouth_landmarks)
        
        # Store calibration data
        calib = self.calibrations[outfit_id]
        
        # Set baseline for neutral expression
        if voice_level == "normal":
            calib.mouth_openness_baseline = mouth_openness
        
        # Store voice volume map
        calib.voice_volume_map[voice_level] = mouth_openness
        
        # Store landmarks for this step
        step_map = {
            "soft": "voice_soft",
            "normal": "voice_normal",
            "loud": "voice_loud"
        }
        step = CalibrationStep(step_map.get(voice_level, "voice_normal"))
        calib.landmarks[step.value] = mouth_landmarks
        
        self._save_calibrations()
        logger.info(f"Captured voice calibration: {voice_level} -> openness {mouth_openness:.2f}")
        
        return True
    
    def get_mouth_openness_for_volume(self, outfit_id: str, audio_volume: float) -> Optional[float]:
        """
        Get expected mouth openness for a given audio volume
        
        Args:
            outfit_id: Outfit ID
            audio_volume: Audio volume (0.0 - 1.0)
        
        Returns:
            Expected mouth openness or None
        """
        calib = self.calibrations.get(outfit_id)
        if not calib:
            return None
        
        # Determine voice level based on volume
        if audio_volume < 0.33:
            voice_level = "soft"
        elif audio_volume < 0.66:
            voice_level = "normal"
        else:
            voice_level = "loud"
        
        # Get calibrated openness for this level
        if voice_level in calib.voice_volume_map:
            return calib.voice_volume_map[voice_level]
        
        # Fallback to interpolation
        if "soft" in calib.voice_volume_map and "loud" in calib.voice_volume_map:
            soft = calib.voice_volume_map["soft"]
            loud = calib.voice_volume_map["loud"]
            return soft + (loud - soft) * audio_volume
        
        return None


# Singleton instance
calibration_wizard = CalibrationWizard()


async def main():
    """Test Calibration Wizard"""
    logger.add("logs/calibration_wizard_{time}.log", rotation="10 MB")
    
    # Start calibration
    calibration_wizard.start_calibration("outfit_001", "Business Suit")
    
    # Get progress
    progress = calibration_wizard.get_calibration_progress("outfit_001")
    logger.info(f"Calibration progress: {progress}")
    
    # Get next step
    next_step = calibration_wizard.get_next_step("outfit_001")
    logger.info(f"Next step: {next_step}")
    
    logger.info("Calibration Wizard test complete")


if __name__ == "__main__":
    import asyncio
    from datetime import datetime
    asyncio.run(main())
