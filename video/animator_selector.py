#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Animator Selector
Selects appropriate animator based on render mode
"""

import sys
from typing import Optional, Dict, Any
from enum import Enum

from loguru import logger
from core.config_manager import ConfigManager, RenderMode

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class AnimatorSelector:
    """
    Selects appropriate animator based on render mode
    Handles LOCAL_FULL, CLOUD_POWER, HYBRID_PLACEHOLDER modes
    """
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.current_mode = RenderMode.HYBRID_PLACEHOLDER
        self.local_animator = None
        self.cloud_animator = None
        self.placeholder_animator = None
        
        self._initialize_animator()
    
    def _initialize_animator(self):
        """Initialize animator based on current render mode"""
        self.current_mode = self.config_manager.get_render_mode()
        
        logger.info(f"Initializing animator for mode: {self.current_mode.value}")
        
        if self.current_mode == RenderMode.LOCAL_FULL:
            self._initialize_local_animator()
        elif self.current_mode == RenderMode.CLOUD_POWER:
            self._initialize_cloud_animator()
        elif self.current_mode == RenderMode.HYBRID_PLACEHOLDER:
            self._initialize_placeholder_animator()
    
    def _initialize_local_animator(self):
        """Initialize local full-power animator (LivePortrait on GPU)"""
        try:
            from video.animator import VideoAnimator, AnimatorConfig
            from video.liveportrait import LivePortraitAnimator
            
            # Create animator with LivePortrait mode
            animator_config = AnimatorConfig(
                mode="liveportrait",
                base_video_path="assets/video/outfits/outfit_shirt_idle.mp4",
                enable_gpu=True
            )
            
            self.local_animator = VideoAnimator(animator_config)
            logger.info("Local full-power animator initialized")
            
        except ImportError as e:
            logger.error(f"Failed to initialize local animator: {e}")
            logger.info("Falling back to placeholder animator")
            self._initialize_placeholder_animator()
    
    def _initialize_cloud_animator(self):
        """Initialize cloud power animator (WebRTC bridge)"""
        try:
            from core.renderer_factory import Renderer
            
            cloud_config = self.config_manager.get_cloud_server_config()
            self.cloud_animator = Renderer()
            
            logger.info("Cloud power animator initialized")
            
        except ImportError as e:
            logger.error(f"Failed to initialize cloud animator: {e}")
            logger.info("Falling back to placeholder animator")
            self._initialize_placeholder_animator()
    
    def _initialize_placeholder_animator(self):
        """Initialize placeholder animator (CPU-based)"""
        try:
            from video.animator import VideoAnimator, AnimatorConfig
            
            # Create animator with placeholder mode
            animator_config = AnimatorConfig(
                mode="placeholder",
                enable_gpu=False  # CPU-only
            )
            
            self.placeholder_animator = VideoAnimator(animator_config)
            logger.info("Placeholder animator initialized")
            
        except ImportError as e:
            logger.error(f"Failed to initialize placeholder animator: {e}")
    
    def get_frame(self, text: str, emotion: str = "neutral", audio_features: Dict[str, Any] = None, 
                  mood_adjustments: Dict[str, float] = None) -> Any:
        """
        Get frame from appropriate animator
        
        Args:
            text: Text to speak
            emotion: Facial emotion
            audio_features: Audio features for lip-sync
            mood_adjustments: Visual mood adjustments from mood engine
        
        Returns:
            Rendered frame
        """
        try:
            if self.current_mode == RenderMode.LOCAL_FULL:
                return self._get_local_frame(text, emotion, audio_features, mood_adjustments)
            elif self.current_mode == RenderMode.CLOUD_POWER:
                return self._get_cloud_frame(text, emotion, audio_features, mood_adjustments)
            elif self.current_mode == RenderMode.HYBRID_PLACEHOLDER:
                return self._get_placeholder_frame(text, emotion, audio_features, mood_adjustments)
            else:
                logger.error(f"Unknown render mode: {self.current_mode}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting frame: {e}")
            # Fallback to placeholder
            if self.placeholder_animator:
                return self._get_placeholder_frame(text, emotion, audio_features, mood_adjustments)
            return None
    
    def _get_local_frame(self, text: str, emotion: str, audio_features: Dict[str, Any] = None,
                       mood_adjustments: Dict[str, float] = None) -> Any:
        """Get frame from local animator"""
        if self.local_animator is None:
            logger.warning("Local animator not available, using placeholder")
            return self._get_placeholder_frame(text, emotion, audio_features, mood_adjustments)
        
        # Apply mood adjustments to LivePortrait if available
        if mood_adjustments and self.local_animator.liveportrait:
            # Adjust expression based on mood
            # This would integrate with LivePortrait's expression control
            pass
        
        # Get frame
        frame = self.local_animator.get_frame(audio_features)
        return frame
    
    def _get_cloud_frame(self, text: str, emotion: str, audio_features: Dict[str, Any] = None,
                       mood_adjustments: Dict[str, float] = None) -> Any:
        """Get frame from cloud animator"""
        if self.cloud_animator is None:
            logger.warning("Cloud animator not available, using placeholder")
            return self._get_placeholder_frame(text, emotion, audio_features, mood_adjustments)
        
        # Send request to cloud with mood adjustments
        # This would integrate with cloud bridge
        frame = self.cloud_animator.get_frame(text, emotion, audio_features)
        return frame
    
    def _get_placeholder_frame(self, text: str, emotion: str, audio_features: Dict[str, Any] = None,
                              mood_adjustments: Dict[str, float] = None) -> Any:
        """Get frame from placeholder animator"""
        if self.placeholder_animator is None:
            logger.error("Placeholder animator not available")
            return None
        
        # Get frame (placeholder mode ignores most parameters)
        frame = self.placeholder_animator.get_frame(audio_features)
        return frame
    
    def switch_mode(self, mode: RenderMode):
        """
        Switch to different render mode
        
        Args:
            mode: New render mode
        """
        logger.info(f"Switching from {self.current_mode.value} to {mode.value}")
        
        # Update config
        self.config_manager.set_render_mode(mode)
        
        # Reinitialize animator
        self.current_mode = mode
        self._initialize_animator()
        
        logger.info(f"Switched to {mode.value}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get animator selector status"""
        return {
            "current_mode": self.current_mode.value,
            "local_available": self.local_animator is not None,
            "cloud_available": self.cloud_animator is not None,
            "placeholder_available": self.placeholder_animator is not None,
            "config_render_mode": self.config_manager.get_render_mode().value
        }


def main():
    """Test animator selector"""
    from loguru import logger
    
    logger.add("logs/animator_selector_{time}.log", rotation="10 MB")
    
    # Create selector
    selector = AnimatorSelector()
    
    # Get status
    status = selector.get_status()
    logger.info(f"Animator selector status: {status}")
    
    # Test getting frame
    frame = selector.get_frame("Hello world", "happy")
    logger.info(f"Frame received: {type(frame)}")
    
    # Test mode switch
    selector.switch_mode(RenderMode.HYBRID_PLACEHOLDER)
    status = selector.get_status()
    logger.info(f"Status after switch: {status}")
    
    logger.info("Animator selector test complete")


if __name__ == "__main__":
    main()
