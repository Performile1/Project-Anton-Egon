#!/usr/bin/env python3
"""
Project Anton Egon - Prop Engine
Prop Shop: Mediapipe face tracking overlays (clown nose, sunglasses, mustache)

Phase 16: The Trickster Engine
"""

import cv2
import numpy as np
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path

import mediapipe as mp
from loguru import logger


class PropType(Enum):
    """Types of props"""
    CLOWN_NOSE = "clown_nose"
    SUNGLASSES = "sunglasses"
    MUSTACHE = "mustache"
    HAT = "hat"
    EYEBROWS = "eyebrows"
    GLASSES = "glasses"


class PropPosition(Enum):
    """Anchor points on face"""
    NOSE_TIP = "nose_tip"
    NOSE_BRIDGE = "nose_bridge"
    EYES = "eyes"
    MOUTH = "mouth"
    FOREHEAD = "forehead"
    CHEEKS = "cheeks"


@dataclass
class Prop:
    """Prop configuration"""
    id: str
    name: str
    prop_type: PropType
    image_path: str
    position: PropPosition
    scale: float = 1.0
    rotation: float = 0.0
    opacity: float = 1.0
    enabled: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "prop_type": self.prop_type.value,
            "image_path": self.image_path,
            "position": self.position.value,
            "scale": self.scale,
            "rotation": self.rotation,
            "opacity": self.opacity,
            "enabled": self.enabled,
            "metadata": self.metadata
        }


class PropEngine:
    """
    Prop Engine
    Applies Mediapipe face tracking overlays to video frames
    """
    
    def __init__(self):
        """Initialize Prop Engine"""
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        self.props: Dict[str, Prop] = {}
        self.active_props: List[Prop] = []
        
        # Face mesh landmark indices
        self.landmarks = {
            "nose_tip": 1,
            "nose_bridge": 6,
            "left_eye": 33,
            "right_eye": 263,
            "left_mouth": 61,
            "right_mouth": 291,
            "forehead": 10,
            "left_cheek": 234,
            "right_cheek": 454
        }
        
        logger.info("Prop Engine initialized with Mediapipe Face Mesh")
    
    def register_prop(self, prop: Prop) -> bool:
        """
        Register a prop
        
        Args:
            prop: Prop to register
        
        Returns:
            True if registered successfully
        """
        if prop.id in self.props:
            logger.warning(f"Prop ID already exists: {prop.id}")
            return False
        
        self.props[prop.id] = prop
        logger.info(f"Registered prop: {prop.name}")
        return True
    
    def enable_prop(self, prop_id: str) -> bool:
        """
        Enable a prop
        
        Args:
            prop_id: Prop ID
        
        Returns:
            True if enabled successfully
        """
        if prop_id not in self.props:
            logger.warning(f"Prop ID not found: {prop_id}")
            return False
        
        prop = self.props[prop_id]
        prop.enabled = True
        
        # Add to active if not already there
        if prop not in self.active_props:
            self.active_props.append(prop)
        
        logger.info(f"Enabled prop: {prop.name}")
        return True
    
    def disable_prop(self, prop_id: str) -> bool:
        """
        Disable a prop
        
        Args:
            prop_id: Prop ID
        
        Returns:
            True if disabled successfully
        """
        if prop_id not in self.props:
            logger.warning(f"Prop ID not found: {prop_id}")
            return False
        
        prop = self.props[prop_id]
        prop.enabled = False
        
        # Remove from active
        if prop in self.active_props:
            self.active_props.remove(prop)
        
        logger.info(f"Disabled prop: {prop.name}")
        return True
    
    def apply_props(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply active props to frame
        
        Args:
            frame: Input frame (BGR)
        
        Returns:
            Frame with props applied
        """
        if not self.active_props:
            return frame
        
        # Convert to RGB for Mediapipe
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(frame_rgb)
        
        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                for prop in self.active_props:
                    frame = self._apply_single_prop(frame, face_landmarks, prop)
        
        return frame
    
    def _apply_single_prop(
        self,
        frame: np.ndarray,
        face_landmarks,
        prop: Prop
    ) -> np.ndarray:
        """
        Apply single prop to frame
        
        Args:
            frame: Input frame
            face_landmarks: Mediapipe face landmarks
            prop: Prop to apply
        
        Returns:
            Frame with prop applied
        """
        try:
            # Get anchor point
            landmark_idx = self.landmarks.get(prop.position.value)
            if landmark_idx is None:
                return frame
            
            # Get landmark coordinates
            h, w = frame.shape[:2]
            landmark = face_landmarks.landmark[landmark_idx]
            x = int(landmark.x * w)
            y = int(landmark.y * h)
            
            # Load prop image
            prop_img = self._load_prop_image(prop.image_path)
            if prop_img is None:
                logger.warning(f"Failed to load prop image: {prop.image_path}")
                return frame
            
            # Scale prop
            if prop.scale != 1.0:
                new_size = (int(prop_img.shape[1] * prop.scale), int(prop_img.shape[0] * prop.scale))
                prop_img = cv2.resize(prop_img, new_size)
            
            # Apply opacity
            if prop.opacity < 1.0:
                prop_img = self._apply_opacity(prop_img, prop.opacity)
            
            # Apply rotation
            if prop.rotation != 0.0:
                prop_img = self._rotate_image(prop_img, prop.rotation)
            
            # Calculate position (centered on landmark)
            prop_h, prop_w = prop_img.shape[:2]
            x_start = x - prop_w // 2
            y_start = y - prop_h // 2
            
            # Blend prop onto frame
            frame = self._blend_prop(frame, prop_img, x_start, y_start)
            
            return frame
            
        except Exception as e:
            logger.error(f"Error applying prop {prop.name}: {e}")
            return frame
    
    def _load_prop_image(self, image_path: str) -> Optional[np.ndarray]:
        """
        Load prop image with alpha channel
        
        Args:
            image_path: Path to image
        
        Returns:
            Image array or None
        """
        try:
            path = Path(image_path)
            if not path.exists():
                logger.warning(f"Prop image not found: {image_path}")
                return None
            
            # Load with alpha channel
            img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            
            if img is None:
                logger.warning(f"Failed to load image: {image_path}")
                return None
            
            # Convert to RGBA if needed
            if img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            
            return img
            
        except Exception as e:
            logger.error(f"Error loading prop image: {e}")
            return None
    
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
    
    def _rotate_image(self, img: np.ndarray, angle: float) -> np.ndarray:
        """
        Rotate image
        
        Args:
            img: Input image
            angle: Rotation angle in degrees
        
        Returns:
            Rotated image
        """
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        
        # Get rotation matrix
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Rotate
        rotated = cv2.warpAffine(img, matrix, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        
        return rotated
    
    def _blend_prop(
        self,
        frame: np.ndarray,
        prop_img: np.ndarray,
        x: int,
        y: int
    ) -> np.ndarray:
        """
        Blend prop onto frame using alpha channel
        
        Args:
            frame: Input frame (BGR)
            prop_img: Prop image (RGBA)
            x: X position
            y: Y position
        
        Returns:
            Frame with prop blended
        """
        h, w = frame.shape[:2]
        prop_h, prop_w = prop_img.shape[:2]
        
        # Check bounds
        if x < 0 or y < 0 or x + prop_w > w or y + prop_h > h:
            return frame
        
        # Extract alpha channel
        alpha = prop_img[:, :, 3] / 255.0
        
        # Blend
        for c in range(3):
            frame[y:y+prop_h, x:x+prop_w, c] = (
                alpha * prop_img[:, :, c] +
                (1 - alpha) * frame[y:y+prop_h, x:x+prop_w, c]
            ).astype(np.uint8)
        
        return frame
    
    def get_active_props(self) -> List[Dict[str, Any]]:
        """Get list of active props"""
        return [prop.to_dict() for prop in self.active_props]
    
    def get_all_props(self) -> List[Dict[str, Any]]:
        """Get all registered props"""
        return [prop.to_dict() for prop in self.props.values()]
    
    def toggle_prop(self, prop_id: str) -> bool:
        """
        Toggle prop enabled state
        
        Args:
            prop_id: Prop ID
        
        Returns:
            True if toggled successfully
        """
        if prop_id not in self.props:
            return False
        
        prop = self.props[prop_id]
        if prop.enabled:
            return self.disable_prop(prop_id)
        else:
            return self.enable_prop(prop_id)
    
    def clear_all_props(self):
        """Disable all active props"""
        for prop in self.active_props.copy():
            self.disable_prop(prop.id)
        logger.info("Cleared all active props")
    
    def register_default_props(self):
        """Register default props (placeholder paths)"""
        default_props = [
            Prop(
                id="clown_nose_001",
                name="Clown Nose",
                prop_type=PropType.CLOWN_NOSE,
                image_path="assets/props/clown_nose.png",
                position=PropPosition.NOSE_TIP,
                scale=0.8
            ),
            Prop(
                id="sunglasses_001",
                name="Cool Sunglasses",
                prop_type=PropType.SUNGLASSES,
                image_path="assets/props/sunglasses.png",
                position=PropPosition.EYES,
                scale=1.0
            ),
            Prop(
                id="mustache_001",
                name="Classic Mustache",
                prop_type=PropType.MUSTACHE,
                image_path="assets/props/mustache.png",
                position=PropPosition.MOUTH,
                scale=0.9
            )
        ]
        
        for prop in default_props:
            self.register_prop(prop)
        
        logger.info(f"Registered {len(default_props)} default props")


# Singleton instance
prop_engine = PropEngine()


async def main():
    """Test Prop Engine"""
    logger.add("logs/prop_engine_{time}.log", rotation="10 MB")
    
    # Register default props
    prop_engine.register_default_props()
    
    # Get all props
    props = prop_engine.get_all_props()
    logger.info(f"Registered props: {len(props)}")
    
    # Enable clown nose
    prop_engine.enable_prop("clown_nose_001")
    
    # Get active props
    active = prop_engine.get_active_props()
    logger.info(f"Active props: {len(active)}")
    
    logger.info("Prop Engine test complete")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
