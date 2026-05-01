#!/usr/bin/env python3
"""
Project Anton Egon - Phase 11: Engagement Analyzer
Monitors participant engagement via gaze direction, head pose, blink rate,
and eye closure ratio. Flags fatigue/disengagement using Mediapipe Face Mesh.
"""

import asyncio
import sys
import time
import numpy as np
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


class EngagementLevel(Enum):
    """Engagement status levels"""
    ACTIVE = "active"              # Looking at screen, blinking normally
    PASSIVE = "passive"            # Looking at screen but reduced engagement
    DISTRACTED = "distracted"      # Gaze away from screen for >5 seconds
    DROWSY = "drowsy"              # High blink rate + slow blinks
    ASLEEP = "asleep"              # Eyes closed >2 seconds + head tilt


class AlertType(Enum):
    """Types of engagement alerts"""
    GAZE_AWAY = "gaze_away"
    EYES_CLOSED = "eyes_closed"
    HEAD_DROP = "head_drop"
    BLINK_RATE_HIGH = "blink_rate_high"
    DISENGAGED = "disengaged"
    ASLEEP = "asleep"


class ParticipantState(BaseModel):
    """Tracked state for a single participant"""
    name: str
    engagement: EngagementLevel = EngagementLevel.ACTIVE
    
    # Gaze tracking
    gaze_on_screen: bool = True
    gaze_away_start: Optional[float] = None
    gaze_away_duration: float = 0.0
    
    # Eye tracking
    eye_aspect_ratio: float = 0.3  # EAR: ~0.3 open, <0.2 closed
    eyes_closed: bool = False
    eyes_closed_start: Optional[float] = None
    eyes_closed_duration: float = 0.0
    
    # Blink tracking
    blink_count: int = 0
    blink_rate_per_minute: float = 15.0  # Normal: 15-20/min
    last_blink_time: Optional[float] = None
    
    # Head pose
    head_pitch: float = 0.0  # Negative = looking down
    head_yaw: float = 0.0    # Left/right
    head_roll: float = 0.0   # Tilt
    head_drop_detected: bool = False
    
    # History
    last_active_time: float = 0.0
    alert_count: int = 0
    
    class Config:
        arbitrary_types_allowed = True


class EngagementConfig(BaseModel):
    """Configuration for Engagement Analyzer"""
    # Thresholds
    ear_threshold: float = Field(default=0.2, description="Eye Aspect Ratio threshold for 'closed'")
    eyes_closed_alert_seconds: float = Field(default=2.0, description="Seconds before flagging eyes closed")
    gaze_away_alert_seconds: float = Field(default=5.0, description="Seconds before flagging gaze away")
    head_drop_pitch_threshold: float = Field(default=-20.0, description="Head pitch degrees for 'head drop'")
    drowsy_blink_rate: float = Field(default=25.0, description="Blinks/min threshold for drowsy")
    
    # Timing
    analysis_interval_ms: int = Field(default=200, description="Analysis interval in ms")
    blink_window_seconds: float = Field(default=60.0, description="Window for blink rate calculation")
    
    # Safety
    alert_cooldown_seconds: float = Field(default=30.0, description="Min time between alerts for same person")
    require_whisper_mode: bool = Field(default=True, description="Only whisper alerts, never auto-callout")
    
    # Mediapipe
    min_detection_confidence: float = Field(default=0.5, description="Mediapipe face detection confidence")
    min_tracking_confidence: float = Field(default=0.5, description="Mediapipe face tracking confidence")


# Mediapipe Face Mesh landmark indices for eye tracking
# Left eye: 362, 385, 387, 263, 373, 380
# Right eye: 33, 160, 158, 133, 153, 144
LEFT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
RIGHT_EYE_INDICES = [33, 160, 158, 133, 153, 144]

# Iris landmarks for gaze direction
LEFT_IRIS = [474, 475, 476, 477]
RIGHT_IRIS = [469, 470, 471, 472]

# Nose tip for head pose
NOSE_TIP = 1
CHIN = 199
LEFT_EYE_CORNER = 33
RIGHT_EYE_CORNER = 263
LEFT_MOUTH = 61
RIGHT_MOUTH = 291


class EngagementAnalyzer:
    """
    Analyzes participant video feeds for engagement levels.
    
    Uses Mediapipe Face Mesh for:
    - Eye Aspect Ratio (EAR) → blink/closure detection
    - Iris tracking → gaze direction
    - Head pose estimation → pitch/yaw/roll
    - Fatigue analysis → combined metrics
    """
    
    def __init__(self, config: EngagementConfig, on_alert: Optional[Callable] = None):
        """Initialize Engagement Analyzer"""
        self.config = config
        self.on_alert = on_alert
        
        # Participant states
        self.participants: Dict[str, ParticipantState] = {}
        
        # Mediapipe face mesh (lazy loaded)
        self._face_mesh = None
        self._mp_face_mesh = None
        
        # Blink history per participant
        self._blink_history: Dict[str, deque] = {}  # name -> deque of blink timestamps
        
        # Alert cooldowns
        self._last_alert_time: Dict[str, float] = {}  # "name_alerttype" -> timestamp
        
        # Running state
        self._running = False
        self._analysis_task: Optional[asyncio.Task] = None
        
        logger.info("Engagement Analyzer initialized")
    
    def _init_mediapipe(self):
        """Lazy-load Mediapipe Face Mesh"""
        if self._face_mesh is not None:
            return True
        
        try:
            import mediapipe as mp
            self._mp_face_mesh = mp.solutions.face_mesh
            self._face_mesh = self._mp_face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,  # Includes iris landmarks
                min_detection_confidence=self.config.min_detection_confidence,
                min_tracking_confidence=self.config.min_tracking_confidence
            )
            logger.info("Mediapipe Face Mesh initialized (with iris refinement)")
            return True
        except ImportError:
            logger.error("Mediapipe not installed. Run: pip install mediapipe")
            return False
    
    # ─── Core Analysis ───────────────────────────────────────────
    
    def analyze_frame(self, participant_name: str, frame: np.ndarray) -> ParticipantState:
        """
        Analyze a single participant's video frame.
        
        Args:
            participant_name: Name of the participant
            frame: BGR frame of the participant's video tile
            
        Returns:
            Updated ParticipantState
        """
        if not self._init_mediapipe():
            return self._get_or_create_state(participant_name)
        
        state = self._get_or_create_state(participant_name)
        now = time.time()
        
        # Convert BGR to RGB for Mediapipe
        import cv2
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._face_mesh.process(rgb_frame)
        
        if not results.multi_face_landmarks:
            # No face detected - might be looking away completely
            state.gaze_on_screen = False
            if state.gaze_away_start is None:
                state.gaze_away_start = now
            state.gaze_away_duration = now - state.gaze_away_start
            self._update_engagement_level(state, now)
            return state
        
        landmarks = results.multi_face_landmarks[0]
        h, w = frame.shape[:2]
        
        # 1. Eye Aspect Ratio (EAR)
        left_ear = self._calculate_ear(landmarks, LEFT_EYE_INDICES, w, h)
        right_ear = self._calculate_ear(landmarks, RIGHT_EYE_INDICES, w, h)
        ear = (left_ear + right_ear) / 2.0
        state.eye_aspect_ratio = ear
        
        # Detect blink/closure
        if ear < self.config.ear_threshold:
            if not state.eyes_closed:
                state.eyes_closed = True
                state.eyes_closed_start = now
                # Register blink
                self._register_blink(participant_name, now)
            state.eyes_closed_duration = now - (state.eyes_closed_start or now)
        else:
            state.eyes_closed = False
            state.eyes_closed_start = None
            state.eyes_closed_duration = 0.0
        
        # 2. Gaze direction (iris tracking)
        gaze_on = self._estimate_gaze(landmarks, w, h)
        state.gaze_on_screen = gaze_on
        
        if gaze_on:
            state.gaze_away_start = None
            state.gaze_away_duration = 0.0
            state.last_active_time = now
        else:
            if state.gaze_away_start is None:
                state.gaze_away_start = now
            state.gaze_away_duration = now - state.gaze_away_start
        
        # 3. Head pose estimation
        pitch, yaw, roll = self._estimate_head_pose(landmarks, w, h)
        state.head_pitch = pitch
        state.head_yaw = yaw
        state.head_roll = roll
        state.head_drop_detected = pitch < self.config.head_drop_pitch_threshold
        
        # 4. Blink rate
        state.blink_rate_per_minute = self._calculate_blink_rate(participant_name, now)
        
        # 5. Update engagement level
        self._update_engagement_level(state, now)
        
        return state
    
    # ─── Eye Aspect Ratio ────────────────────────────────────────
    
    def _calculate_ear(self, landmarks, eye_indices: List[int], 
                        frame_w: int, frame_h: int) -> float:
        """
        Calculate Eye Aspect Ratio (EAR).
        EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
        """
        try:
            points = []
            for idx in eye_indices:
                lm = landmarks.landmark[idx]
                points.append((lm.x * frame_w, lm.y * frame_h))
            
            # Vertical distances
            v1 = np.linalg.norm(np.array(points[1]) - np.array(points[5]))
            v2 = np.linalg.norm(np.array(points[2]) - np.array(points[4]))
            
            # Horizontal distance
            h = np.linalg.norm(np.array(points[0]) - np.array(points[3]))
            
            if h == 0:
                return 0.3  # Default open
            
            ear = (v1 + v2) / (2.0 * h)
            return ear
            
        except Exception:
            return 0.3
    
    # ─── Gaze Estimation ─────────────────────────────────────────
    
    def _estimate_gaze(self, landmarks, frame_w: int, frame_h: int) -> bool:
        """
        Estimate if participant is looking at screen.
        Uses iris position relative to eye corners.
        
        Returns:
            True if looking at screen (roughly centered gaze)
        """
        try:
            # Get iris centers
            left_iris_pts = [landmarks.landmark[i] for i in LEFT_IRIS]
            right_iris_pts = [landmarks.landmark[i] for i in RIGHT_IRIS]
            
            left_iris_x = np.mean([p.x for p in left_iris_pts])
            right_iris_x = np.mean([p.x for p in right_iris_pts])
            
            # Get eye corners for reference
            left_inner = landmarks.landmark[133].x
            left_outer = landmarks.landmark[33].x
            right_inner = landmarks.landmark[362].x
            right_outer = landmarks.landmark[263].x
            
            # Calculate iris position ratio (0 = outer corner, 1 = inner corner)
            left_range = left_inner - left_outer
            right_range = right_outer - right_inner
            
            if left_range == 0 or right_range == 0:
                return True
            
            left_ratio = (left_iris_x - left_outer) / left_range
            right_ratio = (right_iris_x - right_inner) / right_range
            
            # If both irises are roughly centered (0.3-0.7), person is looking at screen
            avg_ratio = (left_ratio + right_ratio) / 2.0
            return 0.25 <= avg_ratio <= 0.75
            
        except Exception:
            return True  # Default: assume looking at screen
    
    # ─── Head Pose ───────────────────────────────────────────────
    
    def _estimate_head_pose(self, landmarks, frame_w: int, frame_h: int) -> Tuple[float, float, float]:
        """
        Estimate head pose (pitch, yaw, roll) from face landmarks.
        
        Returns:
            (pitch, yaw, roll) in degrees
        """
        try:
            import cv2
            
            # 3D model points (generic face model)
            model_points = np.array([
                (0.0, 0.0, 0.0),          # Nose tip
                (0.0, -330.0, -65.0),      # Chin
                (-225.0, 170.0, -135.0),   # Left eye corner
                (225.0, 170.0, -135.0),    # Right eye corner
                (-150.0, -150.0, -125.0),  # Left mouth corner
                (150.0, -150.0, -125.0)    # Right mouth corner
            ], dtype=np.float64)
            
            # 2D image points from landmarks
            indices = [NOSE_TIP, CHIN, LEFT_EYE_CORNER, RIGHT_EYE_CORNER, LEFT_MOUTH, RIGHT_MOUTH]
            image_points = np.array([
                (landmarks.landmark[idx].x * frame_w, landmarks.landmark[idx].y * frame_h)
                for idx in indices
            ], dtype=np.float64)
            
            # Camera internals (approximate)
            focal_length = frame_w
            center = (frame_w / 2, frame_h / 2)
            camera_matrix = np.array([
                [focal_length, 0, center[0]],
                [0, focal_length, center[1]],
                [0, 0, 1]
            ], dtype=np.float64)
            
            dist_coeffs = np.zeros((4, 1))
            
            # Solve PnP
            success, rotation_vec, translation_vec = cv2.solvePnP(
                model_points, image_points, camera_matrix, dist_coeffs,
                flags=cv2.SOLVEPNP_ITERATIVE
            )
            
            if not success:
                return (0.0, 0.0, 0.0)
            
            # Convert rotation vector to rotation matrix
            rotation_mat, _ = cv2.Rodrigues(rotation_vec)
            
            # Extract Euler angles
            sy = np.sqrt(rotation_mat[0, 0] ** 2 + rotation_mat[1, 0] ** 2)
            singular = sy < 1e-6
            
            if not singular:
                pitch = np.degrees(np.arctan2(rotation_mat[2, 1], rotation_mat[2, 2]))
                yaw = np.degrees(np.arctan2(-rotation_mat[2, 0], sy))
                roll = np.degrees(np.arctan2(rotation_mat[1, 0], rotation_mat[0, 0]))
            else:
                pitch = np.degrees(np.arctan2(-rotation_mat[1, 2], rotation_mat[1, 1]))
                yaw = np.degrees(np.arctan2(-rotation_mat[2, 0], sy))
                roll = 0.0
            
            return (pitch, yaw, roll)
            
        except Exception as e:
            logger.debug(f"Head pose estimation failed: {e}")
            return (0.0, 0.0, 0.0)
    
    # ─── Blink Tracking ──────────────────────────────────────────
    
    def _register_blink(self, participant_name: str, timestamp: float):
        """Register a blink event"""
        if participant_name not in self._blink_history:
            self._blink_history[participant_name] = deque(maxlen=100)
        self._blink_history[participant_name].append(timestamp)
    
    def _calculate_blink_rate(self, participant_name: str, now: float) -> float:
        """Calculate blinks per minute over the configured window"""
        if participant_name not in self._blink_history:
            return 15.0  # Default normal rate
        
        history = self._blink_history[participant_name]
        window_start = now - self.config.blink_window_seconds
        
        # Count blinks in window
        recent_blinks = [t for t in history if t >= window_start]
        
        if len(recent_blinks) < 2:
            return 15.0
        
        # Calculate rate
        duration_minutes = (now - recent_blinks[0]) / 60.0
        if duration_minutes <= 0:
            return 15.0
        
        return len(recent_blinks) / duration_minutes
    
    # ─── Engagement Level ────────────────────────────────────────
    
    def _update_engagement_level(self, state: ParticipantState, now: float):
        """Update engagement level based on all metrics"""
        old_level = state.engagement
        
        # ASLEEP: eyes closed >2s AND head drop
        if (state.eyes_closed_duration > self.config.eyes_closed_alert_seconds and 
            state.head_drop_detected):
            state.engagement = EngagementLevel.ASLEEP
        
        # DROWSY: high blink rate OR prolonged eye closure (without head drop)
        elif (state.blink_rate_per_minute > self.config.drowsy_blink_rate or
              state.eyes_closed_duration > self.config.eyes_closed_alert_seconds):
            state.engagement = EngagementLevel.DROWSY
        
        # DISTRACTED: gaze away for extended period
        elif state.gaze_away_duration > self.config.gaze_away_alert_seconds:
            state.engagement = EngagementLevel.DISTRACTED
        
        # PASSIVE: slightly elevated blink rate or occasional gaze away
        elif (state.blink_rate_per_minute > 20.0 or
              state.gaze_away_duration > 2.0):
            state.engagement = EngagementLevel.PASSIVE
        
        # ACTIVE: everything looks normal
        else:
            state.engagement = EngagementLevel.ACTIVE
        
        # Fire alert if engagement dropped
        if old_level != state.engagement and state.engagement in [
            EngagementLevel.DISTRACTED, EngagementLevel.DROWSY, EngagementLevel.ASLEEP
        ]:
            self._fire_alert(state, now)
    
    async def _fire_alert_async(self, state: ParticipantState, now: float):
        """Fire engagement alert (async wrapper)"""
        self._fire_alert(state, now)
    
    def _fire_alert(self, state: ParticipantState, now: float):
        """Fire engagement alert with cooldown"""
        alert_key = f"{state.name}_{state.engagement.value}"
        
        # Check cooldown
        if alert_key in self._last_alert_time:
            elapsed = now - self._last_alert_time[alert_key]
            if elapsed < self.config.alert_cooldown_seconds:
                return
        
        self._last_alert_time[alert_key] = now
        state.alert_count += 1
        
        # Map engagement to alert type
        alert_map = {
            EngagementLevel.ASLEEP: AlertType.ASLEEP,
            EngagementLevel.DROWSY: AlertType.EYES_CLOSED,
            EngagementLevel.DISTRACTED: AlertType.GAZE_AWAY,
        }
        alert_type = alert_map.get(state.engagement, AlertType.DISENGAGED)
        
        alert_data = {
            "participant": state.name,
            "engagement": state.engagement.value,
            "alert_type": alert_type.value,
            "details": self._build_alert_message(state),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        logger.warning(f"Engagement alert: {state.name} → {state.engagement.value}")
        
        if self.on_alert:
            try:
                self.on_alert(alert_data)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def _build_alert_message(self, state: ParticipantState) -> str:
        """Build human-readable alert message for The Whisperer"""
        name = state.name
        
        if state.engagement == EngagementLevel.ASLEEP:
            return f"{name} verkar ha somnat (ögon stängda {state.eyes_closed_duration:.1f}s, huvud nedåt)"
        elif state.engagement == EngagementLevel.DROWSY:
            return f"{name} visar tecken på trötthet (blinkfrekvens: {state.blink_rate_per_minute:.0f}/min)"
        elif state.engagement == EngagementLevel.DISTRACTED:
            return f"{name} har tittat bort från skärmen i {state.gaze_away_duration:.0f} sekunder"
        else:
            return f"{name} verkar inte vara fullt engagerad"
    
    # ─── Participant Management ──────────────────────────────────
    
    def _get_or_create_state(self, name: str) -> ParticipantState:
        """Get or create participant state"""
        if name not in self.participants:
            self.participants[name] = ParticipantState(
                name=name,
                last_active_time=time.time()
            )
        return self.participants[name]
    
    def remove_participant(self, name: str):
        """Remove a participant from tracking"""
        self.participants.pop(name, None)
        self._blink_history.pop(name, None)
    
    def clear_all(self):
        """Clear all participant tracking"""
        self.participants.clear()
        self._blink_history.clear()
        self._last_alert_time.clear()
    
    # ─── Batch Analysis ──────────────────────────────────────────
    
    def get_engagement_summary(self) -> Dict[str, Any]:
        """Get summary of all participants' engagement"""
        summary = {}
        for name, state in self.participants.items():
            summary[name] = {
                "engagement": state.engagement.value,
                "gaze_on_screen": state.gaze_on_screen,
                "blink_rate": round(state.blink_rate_per_minute, 1),
                "eyes_closed": state.eyes_closed,
                "head_pitch": round(state.head_pitch, 1),
                "alert_count": state.alert_count
            }
        return summary
    
    def get_disengaged_participants(self) -> List[str]:
        """Get list of participants who are not actively engaged"""
        disengaged = []
        for name, state in self.participants.items():
            if state.engagement in [EngagementLevel.DISTRACTED, 
                                     EngagementLevel.DROWSY, 
                                     EngagementLevel.ASLEEP]:
                disengaged.append(name)
        return disengaged
    
    def get_most_engaged(self) -> Optional[str]:
        """Get the most engaged participant"""
        active = [name for name, state in self.participants.items() 
                  if state.engagement == EngagementLevel.ACTIVE]
        return active[0] if active else None
    
    # ─── Status ──────────────────────────────────────────────────
    
    def get_status(self) -> Dict[str, Any]:
        """Get analyzer status"""
        return {
            "participants_tracked": len(self.participants),
            "mediapipe_loaded": self._face_mesh is not None,
            "engagement_summary": self.get_engagement_summary(),
            "disengaged": self.get_disengaged_participants(),
            "require_whisper_mode": self.config.require_whisper_mode,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test Engagement Analyzer"""
    config = EngagementConfig()
    analyzer = EngagementAnalyzer(config)
    
    # Simulate participant states (without actual video)
    state = analyzer._get_or_create_state("Lasse")
    state.eyes_closed = True
    state.eyes_closed_duration = 3.0
    state.head_drop_detected = True
    analyzer._update_engagement_level(state, time.time())
    
    logger.info(f"Lasse engagement: {state.engagement.value}")
    logger.info(f"Alert message: {analyzer._build_alert_message(state)}")
    
    state2 = analyzer._get_or_create_state("Sara")
    state2.gaze_away_duration = 8.0
    state2.gaze_on_screen = False
    analyzer._update_engagement_level(state2, time.time())
    
    logger.info(f"Sara engagement: {state2.engagement.value}")
    
    # Summary
    logger.info(f"Summary: {analyzer.get_engagement_summary()}")
    logger.info(f"Disengaged: {analyzer.get_disengaged_participants()}")


if __name__ == "__main__":
    asyncio.run(main())
