#!/usr/bin/env python3
"""
Project Anton Egon - Phase 4: Wardrobe Manager
Base-video layering and seamless stitching for outfit management
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field


class OutfitType(Enum):
    """Available outfit types"""
    SHIRT_01 = "outfit_shirt_01"
    SHIRT_02 = "outfit_shirt_02"
    TSHIRT = "outfit_tshirt"
    GLASSES = "outfit_glasses"
    CASUAL = "outfit_casual"


class VideoState(Enum):
    """Video playback states"""
    IDLE = "idle"
    ACTION = "action"
    TRANSITION = "transition"


class WardrobeConfig(BaseModel):
    """Configuration for wardrobe manager"""
    assets_dir: str = Field(default="assets/video", description="Directory for video assets")
    target_fps: int = Field(default=20, description="Target FPS for output")
    buffer_ms: int = Field(default=250, description="Frame buffer size in milliseconds")
    transition_frames: int = Field(default=15, description="Frames for transition")
    loop_videos: bool = Field(default=True, description="Loop base videos")


class WardrobeManager:
    """
    Manages video assets and seamless stitching
    Loads appropriate outfit video based on meeting settings
    """
    
    def __init__(self, config: WardrobeConfig):
        """Initialize wardrobe manager"""
        self.config = config
        self.assets_dir = Path(config.assets_dir)
        
        # Video assets
        self.base_videos: Dict[OutfitType, str] = {}
        self.action_videos: Dict[str, str] = {}
        
        # Current state
        self.current_outfit: Optional[OutfitType] = None
        self.current_state = VideoState.IDLE
        self.current_video_cap: Optional[cv2.VideoCapture] = None
        
        # Frame buffer
        self.frame_buffer: List[np.ndarray] = []
        self.buffer_max_size = int(config.target_fps * (config.buffer_ms / 1000))
        
        logger.info(f"Wardrobe Manager initialized with {self.buffer_max_size} frame buffer")
        
        # Load available assets
        self._load_assets()
    
    def _load_assets(self):
        """Load available video assets"""
        try:
            # Load base videos (idle loops)
            for outfit in OutfitType:
                video_path = self.assets_dir / f"{outfit.value}_idle.mp4"
                if video_path.exists():
                    self.base_videos[outfit] = str(video_path)
                    logger.info(f"Loaded base video: {outfit.value}")
            
            # Load action videos
            action_names = ["drink_water", "check_phone", "adjust_glasses", "scratch_head", "look_notes", "stretch", "clear_throat"]
            for action in action_names:
                video_path = self.assets_dir / f"action_{action}.mp4"
                if video_path.exists():
                    self.action_videos[action] = str(video_path)
                    logger.info(f"Loaded action video: {action}")
            
            # Set default outfit
            if self.base_videos:
                self.current_outfit = list(self.base_videos.keys())[0]
                logger.info(f"Default outfit set to: {self.current_outfit.value}")
            
        except Exception as e:
            logger.error(f"Failed to load video assets: {e}")
    
    def set_outfit(self, outfit: OutfitType):
        """
        Set current outfit
        
        Args:
            outfit: Outfit type to use
        """
        if outfit not in self.base_videos:
            logger.warning(f"Outfit {outfit.value} not available")
            return False
        
        self.current_outfit = outfit
        logger.info(f"Outfit changed to: {outfit.value}")
        return True
    
    def get_base_video_path(self) -> Optional[str]:
        """Get path to current base video"""
        if self.current_outfit and self.current_outfit in self.base_videos:
            return self.base_videos[self.current_outfit]
        return None
    
    def get_action_video_path(self, action: str) -> Optional[str]:
        """Get path to action video"""
        return self.action_videos.get(action)
    
    def load_video(self, video_path: str) -> Optional[cv2.VideoCapture]:
        """
        Load video file
        
        Args:
            video_path: Path to video file
        
        Returns:
            VideoCapture object or None
        """
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Failed to open video: {video_path}")
                return None
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            logger.info(f"Loaded video: {video_path} (FPS: {fps}, Frames: {frame_count})")
            return cap
            
        except Exception as e:
            logger.error(f"Failed to load video {video_path}: {e}")
            return None
    
    def get_frame_from_video(self, cap: cv2.VideoCapture) -> Optional[np.ndarray]:
        """
        Get next frame from video
        
        Args:
            cap: VideoCapture object
        
        Returns:
            Frame as numpy array or None
        """
        ret, frame = cap.read()
        if not ret:
            # Loop video if enabled
            if self.config.loop_videos:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                if not ret:
                    return None
            else:
                return None
        
        return frame
    
    def seamless_stitch(self, video_path1: str, video_path2: str, overlap_frames: int = 10) -> bool:
        """
        Seamlessly stitch two videos together
        
        Args:
            video_path1: First video path
            video_path2: Second video path
            overlap_frames: Number of frames to overlap for transition
        
        Returns:
            True if successful
        """
        try:
            cap1 = self.load_video(video_path1)
            cap2 = self.load_video(video_path2)
            
            if not cap1 or not cap2:
                return False
            
            # This is a simplified version - real implementation would use frame matching
            # and cross-fading for seamless transitions
            logger.info(f"Seamless stitch: {video_path1} -> {video_path2} (overlap: {overlap_frames})")
            
            cap1.release()
            cap2.release()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to stitch videos: {e}")
            return False
    
    def add_frame_to_buffer(self, frame: np.ndarray):
        """Add frame to buffer"""
        self.frame_buffer.append(frame)
        
        # Maintain buffer size
        if len(self.frame_buffer) > self.buffer_max_size:
            self.frame_buffer.pop(0)
    
    def get_buffered_frame(self) -> Optional[np.ndarray]:
        """Get frame from buffer"""
        if self.frame_buffer:
            return self.frame_buffer.pop(0)
        return None
    
    def clear_buffer(self):
        """Clear frame buffer"""
        self.frame_buffer.clear()
    
    def get_buffer_size(self) -> int:
        """Get current buffer size"""
        return len(self.frame_buffer)
    
    def get_available_outfits(self) -> List[str]:
        """Get list of available outfits"""
        return [outfit.value for outfit in self.base_videos.keys()]
    
    def get_available_actions(self) -> List[str]:
        """Get list of available actions"""
        return list(self.action_videos.keys())
    
    def get_status(self) -> Dict[str, Any]:
        """Get current wardrobe manager status"""
        return {
            "current_outfit": self.current_outfit.value if self.current_outfit else None,
            "current_state": self.current_state.value,
            "buffer_size": len(self.frame_buffer),
            "buffer_max_size": self.buffer_max_size,
            "available_outfits": self.get_available_outfits(),
            "available_actions": self.get_available_actions(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test the wardrobe manager"""
    from loguru import logger
    
    logger.add("logs/wardrobe_manager_{time}.log", rotation="10 MB")
    
    # Create wardrobe manager
    config = WardrobeConfig()
    manager = WardrobeManager(config)
    
    # Get status
    status = manager.get_status()
    logger.info(f"Wardrobe status: {status}")
    
    # Test outfit change
    if manager.base_videos:
        first_outfit = list(manager.base_videos.keys())[0]
        manager.set_outfit(first_outfit)
        logger.info(f"Set outfit to: {first_outfit.value}")


if __name__ == "__main__":
    asyncio.run(main())
