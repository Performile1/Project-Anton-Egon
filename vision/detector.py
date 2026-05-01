#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Phase 2: Vision Detector
Face detection with YOLO and emotion analysis with DeepFace
"""

import sys
import asyncio
import cv2
import numpy as np
from typing import Optional, Callable, Dict, Any, List
from datetime import datetime, timezone
from pathlib import Path

from ultralytics import YOLO
from deepface import DeepFace
import mss
import torch

# Phase 18: Mediapipe for face-mesh extraction
try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# Platform configurations
PLATFORM_CONFIGS = {
    "teams": {
        "window_title": "Microsoft Teams",
        "capture_region": "dynamic"
    },
    "meet": {
        "window_title": "Google Meet",
        "capture_region": "dynamic"
    },
    "zoom": {
        "window_title": "Zoom Meeting",
        "capture_region": "dynamic"
    },
    "whatsapp": {
        "window_title": "WhatsApp",
        "capture_region": "dynamic"
    },
    "discord": {
        "window_title": "Discord",
        "capture_region": "full"
    }
}


class VisionConfig:
    """Vision configuration"""
    TARGET_FPS = 1.5  # Limit to 1-2 FPS to save CPU
    CONFIDENCE_THRESHOLD = 0.5
    EMOTION_MODEL = "deepface"
    FACE_DETECTION_MODEL = "yolov8n"
    SCREEN_CAPTURE_REGION = None  # None = full screen, or {"top": y, "left": x, "width": w, "height": h}
    
    # Sprint 3: Multi-Identity Tracking
    ENABLE_MULTI_FACE = True  # Enable multi-face tracking
    MAX_FACES = 10  # Maximum number of faces to track
    FACE_RECOGNITION_THRESHOLD = 0.6  # Threshold for face matching
    ENABLE_SPATIAL_INDEXING = True  # Enable spatial indexing (Left, Center, Right)


class VisionDetector:
    """
    Vision detector for face detection and emotion analysis
    Runs at low FPS (1-2) to conserve CPU for other phases
    """
    
    def __init__(
        self,
        target_fps: float = VisionConfig.TARGET_FPS,
        on_detection: Optional[Callable] = None,
        window_title: Optional[str] = None,  # Teams window title for focused capture
        platform: str = "teams"
    ):
        """
        Initialize vision detector
        
        Args:
            target_fps: Target frames per second (default: 1.5)
            on_detection: Callback for detection results
            window_title: Window title to capture (e.g., "Microsoft Teams")
            platform: Platform name (teams, meet, zoom, whatsapp, discord)
        """
        self.target_fps = target_fps
        self.on_detection = on_detection
        self.window_title = window_title
        self.platform = platform.lower() if platform else "teams"
        
        # Get platform configuration
        self.platform_config = PLATFORM_CONFIGS.get(self.platform, PLATFORM_CONFIGS["teams"])
        
        # Override window_title if not provided
        if not self.window_title and "window_title" in self.platform_config:
            self.window_title = self.platform_config["window_title"]
        
        self.running = False
        self.detection_task = None
        self.window_region = None
        
        logger.info(f"Initializing VisionDetector at {target_fps} FPS (platform: {self.platform})")
        
        # Initialize YOLO model
        self._init_yolo()
        
        # Initialize DeepFace
        self._init_deepface()
        
        # Phase 18: Initialize Mediapipe Face Mesh
        self._init_face_mesh()
        
        # Initialize screen capture
        self._init_screen_capture()
    
    def _init_yolo(self):
        """Initialize YOLO model for face detection"""
        try:
            logger.info(f"Loading YOLO model: {VisionConfig.FACE_DETECTION_MODEL}")
            self.yolo_model = YOLO(f"{VisionConfig.FACE_DETECTION_MODEL}.pt")
            
            # Use CPU for YOLO to save GPU for critical components
            self.yolo_model.to("cpu")
            
            logger.info("YOLO model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
    
    def _init_deepface(self):
        """Initialize DeepFace for emotion analysis"""
        try:
            logger.info("Loading DeepFace models")
            # DeepFace loads models on first use
            self.deepface_backend = "opencv"  # Use OpenCV backend for speed
            logger.info("DeepFace initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize DeepFace: {e}")
            raise
    
    # ═══════════════════════════════════════════════════════════════
    # PHASE 18: MEDIAPIPE FACE MESH
    # ═══════════════════════════════════════════════════════════════
    def _init_face_mesh(self):
        """Initialize Mediapipe Face Mesh for detailed facial landmarks"""
        if not MEDIAPIPE_AVAILABLE:
            logger.warning("Mediapipe not available - face-mesh extraction disabled")
            self.face_mesh = None
            return
        
        try:
            logger.info("Initializing Mediapipe Face Mesh")
            # Sprint 3: Support multiple faces for multi-identity tracking
            max_faces = VisionConfig.MAX_FACES if VisionConfig.ENABLE_MULTI_FACE else 1
            
            self.face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=max_faces,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            logger.info(f"Mediapipe Face Mesh initialized successfully (max_faces: {max_faces})")
        except Exception as e:
            logger.error(f"Failed to initialize Face Mesh: {e}")
            self.face_mesh = None
    
    def _init_screen_capture(self):
        """Initialize screen capture (MSS)"""
        try:
            self.screen_capture = mss.mss()
            
            # If window title specified, find window region (Windows only)
            if self.window_title:
                self._find_window_region()
            
            logger.info("Screen capture initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize screen capture: {e}")
            raise
    
    def _detect_text_regions(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect text regions in frame (for Zoom dynamic tracking)
        
        Args:
            frame: Input frame
        
        Returns:
            List of detected text regions with coordinates
        """
        # Placeholder for dynamic text detection
        # In production, use EasyOCR or Tesseract to detect text regions
        # For now, return empty list
        return []
        """Find window region by title (Windows only)"""
        try:
            import win32gui
            import win32con
            
            def callback(hwnd, extra):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if self.window_title.lower() in title.lower():
                        rect = win32gui.GetWindowRect(hwnd)
                        self.window_region = {
                            "top": rect[1],
                            "left": rect[0],
                            "width": rect[2] - rect[0],
                            "height": rect[3] - rect[1]
                        }
                        logger.info(f"Found window region: {self.window_region}")
            
            win32gui.EnumWindows(callback, None)
            
            if not self.window_region:
                logger.warning(f"Window '{self.window_title}' not found, using full screen")
            
        except ImportError:
            logger.warning("win32gui not available, using full screen capture")
        except Exception as e:
            logger.error(f"Failed to find window region: {e}")
    
    def _capture_screen(self) -> np.ndarray:
        """Capture screen or window region"""
        try:
            if self.window_region:
                monitor = self.window_region
            else:
                monitor = self.screen_capture.monitors[0]  # Primary monitor
            
            # Capture screen
            screenshot = self.screen_capture.grab(monitor)
            
            # Convert to numpy array (BGR format for OpenCV)
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            return img
            
        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return np.zeros((480, 640, 3), dtype=np.uint8)
    
    def _detect_faces(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Detect faces using YOLO"""
        try:
            # Run YOLO inference
            results = self.yolo_model(image, conf=VisionConfig.CONFIDENCE_THRESHOLD)
            
            faces = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    # Get box coordinates
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    confidence = box.conf[0].cpu().numpy()
                    
                    # Sprint 3: Add spatial indexing
                    h, w = image.shape[:2]
                    center_x = (x1 + x2) / 2
                    
                    # Determine spatial position (Left, Center, Right)
                    if VisionConfig.ENABLE_SPATIAL_INDEXING:
                        if center_x < w / 3:
                            spatial_position = "left"
                        elif center_x < 2 * w / 3:
                            spatial_position = "center"
                        else:
                            spatial_position = "right"
                    else:
                        spatial_position = "unknown"
                    
                    faces.append({
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "confidence": float(confidence),
                        "spatial_position": spatial_position,
                        "center_x": float(center_x),
                        "center_y": float((y1 + y2) / 2)
                    })
            
            # Sprint 3: Limit to max faces
            if VisionConfig.ENABLE_MULTI_FACE and len(faces) > VisionConfig.MAX_FACES:
                faces = sorted(faces, key=lambda x: x["confidence"], reverse=True)[:VisionConfig.MAX_FACES]
            
            return faces
            
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return []
    
    def _analyze_emotion(self, image: np.ndarray, face_bbox: List[int]) -> Dict[str, Any]:
        """Analyze emotion for a specific face region"""
        try:
            x1, y1, x2, y2 = face_bbox
            face_image = image[y1:y2, x1:x2]
            
            # Skip if face region is too small
            if face_image.shape[0] < 50 or face_image.shape[1] < 50:
                return {"emotion": "unknown", "confidence": 0.0}
            
            # Analyze emotion with DeepFace
            result = DeepFace.analyze(
                face_image,
                actions=['emotion'],
                enforce_detection=False,
                verbose=False
            )
            
            if isinstance(result, list):
                result = result[0]
            
            dominant_emotion = result.get('dominant_emotion', 'neutral')
            emotions = result.get('emotion', {})
            
            return {
                "emotion": dominant_emotion,
                "confidence": emotions.get(dominant_emotion, 0.0),
                "all_emotions": emotions
            }
            
        except Exception as e:
            logger.debug(f"Emotion analysis error: {e}")
            return {"emotion": "neutral", "confidence": 0.0}
    
    def extract_face_vector(self, image: np.ndarray, face_bbox: List[int]) -> Optional[np.ndarray]:
        """
        Extract 128-d face vector (embedding) for face recognition
        
        Args:
            image: Input image
            face_bbox: Face bounding box [x1, y1, x2, y2]
        
        Returns:
            128-d face vector or None if extraction fails
        """
        try:
            x1, y1, x2, y2 = face_bbox
            face_image = image[y1:y2, x1:x2]
            
            # Skip if face region is too small
            if face_image.shape[0] < 50 or face_image.shape[1] < 50:
                logger.debug("Face region too small for vector extraction")
                return None
            
            # Extract face embedding with DeepFace
            # Using Facenet model for 128-d vectors
            embeddings = DeepFace.represent(
                face_image,
                model_name='Facenet',
                enforce_detection=False,
                verbose=False
            )
            
            if isinstance(embeddings, list) and len(embeddings) > 0:
                # Get the first embedding (128-d vector)
                face_vector = np.array(embeddings[0]['embedding'])
                return face_vector
            
            return None
            
        except Exception as e:
            logger.debug(f"Face vector extraction error: {e}")
            return None
    
    # ═══════════════════════════════════════════════════════════════
    # SPRINT 3: MULTI-IDENTITY TRACKING
    # ═══════════════════════════════════════════════════════════════
    def recognize_face(self, face_vector: np.ndarray, people_crm: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Recognize face by comparing vector with People CRM
        
        Args:
            face_vector: 128-d face vector to recognize
            people_crm: List of people profiles with face_fingerprints
        
        Returns:
            Matched person or None if no match found
        """
        if face_vector is None or not people_crm:
            return None
        
        try:
            best_match = None
            best_score = 0.0
            
            for person in people_crm:
                if 'face_fingerprint' not in person or person['face_fingerprint'] is None:
                    continue
                
                # Compare face vectors using cosine similarity
                crm_vector = np.array(person['face_fingerprint'])
                similarity = np.dot(face_vector, crm_vector) / (np.linalg.norm(face_vector) * np.linalg.norm(crm_vector))
                
                if similarity > VisionConfig.FACE_RECOGNITION_THRESHOLD and similarity > best_score:
                    best_score = similarity
                    best_match = person
            
            if best_match:
                return {
                    "name": best_match.get("name", "Unknown"),
                    "email": best_match.get("email", ""),
                    "company": best_match.get("company", ""),
                    "confidence": float(best_score)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Face recognition error: {e}")
            return None
    
    def draw_bounding_boxes(self, image: np.ndarray, faces: List[Dict[str, Any]], recognized_people: List[Dict[str, Any]]) -> np.ndarray:
        """
        Draw bounding boxes with name tags on image
        
        Args:
            image: Input image (BGR)
            faces: List of detected faces with bbox and spatial_position
            recognized_people: List of recognized people for each face
        
        Returns:
            Image with bounding boxes and name tags drawn
        """
        try:
            for i, face in enumerate(faces):
                bbox = face["bbox"]
                spatial_position = face.get("spatial_position", "unknown")
                
                # Get recognized person if available
                person_info = recognized_people[i] if i < len(recognized_people) else None
                name = person_info.get("name", f"Person {i+1}") if person_info else f"Person {i+1}"
                confidence = person_info.get("confidence", 0.0) if person_info else 0.0
                
                # Color based on spatial position
                color_map = {
                    "left": (0, 255, 255),    # Cyan
                    "center": (0, 255, 0),    # Green
                    "right": (255, 0, 255)    # Magenta
                }
                color = color_map.get(spatial_position, (255, 255, 0))  # Yellow default
                
                # Draw bounding box
                x1, y1, x2, y2 = bbox
                cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
                
                # Draw name tag background
                label = f"{name}"
                if confidence > 0:
                    label += f" ({confidence:.2f})"
                
                (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                cv2.rectangle(image, (x1, y1 - label_h - 10), (x1 + label_w, y1), color, -1)
                
                # Draw name tag text
                cv2.putText(image, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                
                # Draw spatial position indicator
                cv2.putText(image, spatial_position.upper(), (x1, y2 + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            
            return image
            
        except Exception as e:
            logger.error(f"Error drawing bounding boxes: {e}")
            return image
    
    # ═══════════════════════════════════════════════════════════════
    # SPRINT 3: VISUAL VOICE ACTIVITY DETECTION (V-VAD)
    # ═══════════════════════════════════════════════════════════════
    def extract_lip_movement(self, mesh_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract lip movement from face mesh landmarks for V-VAD
        
        Args:
            mesh_data: Face mesh data from extract_face_mesh
        
        Returns:
            Dictionary with lip movement metrics
        """
        if mesh_data is None or 'key_points' not in mesh_data:
            return {"movement_score": 0.0, "is_speaking": False}
        
        try:
            key_points = mesh_data['key_points']
            
            # Get lip landmarks
            left_mouth = key_points.get('left_mouth', {})
            right_mouth = key_points.get('right_mouth', {})
            upper_lip = key_points.get('upper_lip', {})
            lower_lip = key_points.get('lower_lip', {})
            
            # Calculate mouth opening (distance between upper and lower lip)
            mouth_opening = abs(lower_lip.get('y', 0) - upper_lip.get('y', 0))
            
            # Calculate mouth width (distance between left and right mouth)
            mouth_width = abs(right_mouth.get('x', 0) - left_mouth.get('x', 0))
            
            # Movement score based on mouth opening and width changes
            # This is a simplified version - in production, you'd track changes over time
            movement_score = mouth_opening * 10.0 + mouth_width * 2.0
            
            # Speaking threshold (tunable based on testing)
            speaking_threshold = 0.3
            is_speaking = movement_score > speaking_threshold
            
            return {
                "movement_score": float(movement_score),
                "is_speaking": is_speaking,
                "mouth_opening": float(mouth_opening),
                "mouth_width": float(mouth_width)
            }
            
        except Exception as e:
            logger.error(f"Lip movement extraction error: {e}")
            return {"movement_score": 0.0, "is_speaking": False}
    
    def detect_active_speaker(self, faces: List[Dict[str, Any]], lip_movements: List[Dict[str, Any]]) -> Optional[int]:
        """
        Determine which face is the active speaker based on lip movement
        
        Args:
            faces: List of detected faces
            lip_movements: List of lip movement data for each face
        
        Returns:
            Index of active speaker or None if no clear speaker
        """
        try:
            if not faces or not lip_movements:
                return None
            
            # Find face with highest movement score that is speaking
            best_speaker_idx = None
            best_score = 0.0
            
            for i, lip_data in enumerate(lip_movements):
                if lip_data.get("is_speaking", False):
                    score = lip_data.get("movement_score", 0.0)
                    if score > best_score:
                        best_score = score
                        best_speaker_idx = i
            
            return best_speaker_idx
            
        except Exception as e:
            logger.error(f"Active speaker detection error: {e}")
            return None
    
    # ═══════════════════════════════════════════════════════════════
    # PHASE 18: FACE MESH EXTRACTION
    # ═══════════════════════════════════════════════════════════════
    def extract_face_mesh(self, image: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Extract face mesh landmarks using Mediapipe
        
        Args:
            image: Input image (BGR)
        
        Returns:
            Dictionary with face mesh landmarks or None if extraction fails
        """
        if self.face_mesh is None:
            logger.debug("Face Mesh not initialized")
            return None
        
        try:
            # Convert to RGB for Mediapipe
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Process with Face Mesh
            results = self.face_mesh.process(image_rgb)
            
            if results.multi_face_landmarks:
                landmarks = results.multi_face_landmarks[0]
                
                # Convert landmarks to numpy array
                mesh_points = []
                for landmark in landmarks.landmark:
                    mesh_points.append({
                        'x': landmark.x,
                        'y': landmark.y,
                        'z': landmark.z
                    })
                
                # Extract key facial features
                key_points = self._extract_key_facial_points(landmarks)
                
                return {
                    'mesh_points': mesh_points,
                    'key_points': key_points,
                    'num_landmarks': len(mesh_points)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Face mesh extraction error: {e}")
            return None
    
    def _extract_key_facial_points(self, landmarks) -> Dict[str, Dict[str, float]]:
        """
        Extract key facial points for calibration
        
        Args:
            landmarks: Mediapipe face mesh landmarks
        
        Returns:
            Dictionary with key facial points (nose, eyes, mouth, etc.)
        """
        key_indices = {
            'nose_tip': 1,
            'nose_bridge': 6,
            'left_eye': 33,
            'right_eye': 263,
            'left_mouth': 61,
            'right_mouth': 291,
            'upper_lip': 13,
            'lower_lip': 14,
            'forehead': 10,
            'left_cheek': 234,
            'right_cheek': 454
        }
        
        key_points = {}
        for name, idx in key_indices.items():
            if idx < len(landmarks.landmark):
                lm = landmarks.landmark[idx]
                key_points[name] = {
                    'x': lm.x,
                    'y': lm.y,
                    'z': lm.z
                }
        
        return key_points
    
    def draw_face_mesh(self, image: np.ndarray, mesh_data: Dict[str, Any], color: Tuple[int, int, int] = (0, 255, 0)) -> np.ndarray:
        """
        Draw face mesh visualization on image
        
        Args:
            image: Input image (BGR)
            mesh_data: Face mesh data from extract_face_mesh
            color: Color for mesh lines (BGR)
        
        Returns:
            Image with face mesh drawn
        """
        if mesh_data is None or 'mesh_points' not in mesh_data:
            return image
        
        try:
            h, w = image.shape[:2]
            mesh_points = mesh_data['mesh_points']
            
            # Draw mesh points
            for point in mesh_points:
                x = int(point['x'] * w)
                y = int(point['y'] * h)
                cv2.circle(image, (x, y), 1, color, -1)
            
            # Draw key points with larger circles
            if 'key_points' in mesh_data:
                for name, point in mesh_data['key_points'].items():
                    x = int(point['x'] * w)
                    y = int(point['y'] * h)
                    cv2.circle(image, (x, y), 3, (0, 0, 255), -1)
            
            return image
            
        except Exception as e:
            logger.error(f"Error drawing face mesh: {e}")
            return image
    
    async def _detection_loop(self):
        """Main detection loop"""
        logger.info("Starting vision detection loop")
        
        frame_interval = 1.0 / self.target_fps
        
        while self.running:
            start_time = asyncio.get_event_loop().time()
            
            try:
                # Capture screen
                image = self._capture_screen()
                
                # Process frame
                result = self._process_frame(image)
                
                # Emit detection results
                if result["faces"] and self.on_detection:
                    await self.on_detection(result)
                
                # Sleep to maintain target FPS
                elapsed = asyncio.get_event_loop().time() - start_time
                sleep_time = max(0, frame_interval - elapsed)
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Detection loop error: {e}")
                await asyncio.sleep(1.0)
    
    async def start(self):
        """Start vision detection"""
        if self.running:
            logger.warning("Vision detector already running")
            return
        
        logger.info("Starting vision detector")
        self.running = True
        
        # Start detection task
        self.detection_task = asyncio.create_task(self._detection_loop())
    
    async def stop(self):
        """Stop vision detection"""
        if not self.running:
            return
        
        logger.info("Stopping vision detector")
        self.running = False
        
        # Cancel detection task
        if self.detection_task:
            self.detection_task.cancel()
            try:
                await self.detection_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Vision detector stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current detector status"""
        return {
            "running": self.running,
            "target_fps": self.target_fps,
            "window_title": self.window_title,
            "window_region": self.window_region,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test the vision detector"""
    from loguru import logger
    
    logger.add("logs/vision_detector_{time}.log", rotation="10 MB")
    
    # Test callback
    async def on_detection(result):
        logger.info(f"Detected {result['num_faces']} face(s)")
        for face in result['faces']:
            logger.info(f"  - Emotion: {face['emotion']} (conf: {face['emotion_confidence']:.2f})")
    
    # Create detector (use full screen for testing)
    detector = VisionDetector(target_fps=1.0, on_detection=on_detection)
    
    try:
        await detector.start()
        logger.info("Detecting... Press Ctrl+C to stop")
        
        # Run for 30 seconds
        await asyncio.sleep(30)
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await detector.stop()


if __name__ == "__main__":
    asyncio.run(main())
