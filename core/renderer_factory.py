#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Unified Rendering API
Abstracts local vs cloud rendering
"""

import asyncio
import sys
from typing import Optional, Dict, Any
from enum import Enum
from pathlib import Path

import yaml
from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class RenderMode(Enum):
    """Rendering modes"""
    LOCAL = "LOCAL"
    CLOUD = "CLOUD"
    FALLBACK = "FALLBACK"  # Emergency fallback (CPU-based)


class RendererConfig:
    """Configuration for renderer"""
    def __init__(self, config_path: str = "config/system_config.yaml"):
        self.config_path = Path(config_path)
        self.render_mode = RenderMode.LOCAL
        self.cloud_server_url = None
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}, using defaults")
            self.render_mode = RenderMode.LOCAL
            return
        
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)
        
        # Determine render mode
        render_mode_str = config.get("render_mode", {}).get("mode", "LOCAL")
        try:
            self.render_mode = RenderMode[render_mode_str.upper()]
        except KeyError:
            logger.warning(f"Invalid render mode: {render_mode_str}, using LOCAL")
            self.render_mode = RenderMode.LOCAL
        
        # Cloud server URL
        self.cloud_server_url = config.get("cloud_server", {}).get("url", None)
        
        logger.info(f"Renderer config loaded: mode={self.render_mode.value}, cloud_url={self.cloud_server_url}")


class Renderer:
    """
    Unified rendering interface
    Abstraction layer for local vs cloud rendering
    """
    
    def __init__(self, config: RendererConfig = None):
        self.config = config or RendererConfig()
        self.local_renderer = None
        self.cloud_bridge = None
        self.fallback_renderer = None
        
        self._initialize_renderers()
    
    def _initialize_renderers(self):
        """Initialize renderers based on config"""
        try:
            # Initialize local renderer
            if self.config.render_mode in [RenderMode.LOCAL, RenderMode.FALLBACK]:
                try:
                    from video.animator import VideoAnimator, AnimatorConfig
                    from video.liveportrait import LivePortraitAnimator
                    
                    animator_config = AnimatorConfig(
                        mode="liveportrait",
                        base_video_path="assets/video/outfits/outfit_shirt_idle.mp4"
                    )
                    self.local_renderer = VideoAnimator(animator_config)
                    logger.info("Local renderer initialized")
                except ImportError as e:
                    logger.warning(f"Could not initialize local renderer: {e}")
            
            # Initialize cloud bridge
            if self.config.render_mode == RenderMode.CLOUD:
                try:
                    from core.cloud_bridge import CloudBridge
                    self.cloud_bridge = CloudBridge(self.config.cloud_server_url)
                    logger.info("Cloud bridge initialized")
                except ImportError as e:
                    logger.warning(f"Could not initialize cloud bridge: {e}")
            
            # Initialize fallback renderer (always available)
            try:
                from video.animator import VideoAnimator, AnimatorConfig
                fallback_config = AnimatorConfig(
                    mode="placeholder",
                    enable_gpu=False  # CPU-only for fallback
                )
                self.fallback_renderer = VideoAnimator(fallback_config)
                logger.info("Fallback renderer initialized")
            except ImportError as e:
                logger.warning(f"Could not initialize fallback renderer: {e}")
        
        except Exception as e:
            logger.error(f"Error initializing renderers: {e}")
    
    def get_frame(self, text: str, emotion: str = "neutral", audio_features: Dict[str, Any] = None) -> Any:
        """
        Get rendered frame based on current mode
        
        Args:
            text: Text to speak (for lip-sync)
            emotion: Facial emotion
            audio_features: Audio features for lip-sync
        
        Returns:
            Rendered frame (numpy array or similar)
        """
        try:
            if self.config.render_mode == RenderMode.LOCAL:
                return self._render_local(text, emotion, audio_features)
            elif self.config.render_mode == RenderMode.CLOUD:
                return self._render_cloud(text, emotion, audio_features)
            else:
                return self._render_fallback(text, emotion, audio_features)
        except Exception as e:
            logger.error(f"Error rendering frame: {e}, falling back")
            return self._render_fallback(text, emotion, audio_features)
    
    def _render_local(self, text: str, emotion: str, audio_features: Dict[str, Any] = None) -> Any:
        """Render locally using GPU"""
        if self.local_renderer is None:
            logger.warning("Local renderer not available, falling back")
            return self._render_fallback(text, emotion, audio_features)
        
        # Set expression
        if self.local_renderer.liveportrait:
            self.local_renderer.liveportrait.set_expression(
                self.local_renderer.liveportrait.get_expression_from_emotion(emotion)
            )
        
        # Get frame
        frame = self.local_renderer.get_frame(audio_features)
        return frame
    
    def _render_cloud(self, text: str, emotion: str, audio_features: Dict[str, Any] = None) -> Any:
        """Render in cloud via WebRTC"""
        if self.cloud_bridge is None:
            logger.warning("Cloud bridge not available, falling back to local")
            return self._render_local(text, emotion, audio_features)
        
        # Send request to cloud
        frame = self.cloud_bridge.request_frame(text, emotion, audio_features)
        return frame
    
    def _render_fallback(self, text: str, emotion: str, audio_features: Dict[str, Any] = None) -> Any:
        """Render fallback (CPU-based placeholder)"""
        if self.fallback_renderer is None:
            logger.error("Fallback renderer not available, returning None")
            return None
        
        # Get placeholder frame
        frame = self.fallback_renderer.get_frame(audio_features)
        return frame
    
    def switch_mode(self, mode: RenderMode):
        """Switch rendering mode"""
        logger.info(f"Switching render mode from {self.config.render_mode.value} to {mode.value}")
        self.config.render_mode = mode
        
        # Reinitialize renderers if needed
        if mode == RenderMode.CLOUD and self.cloud_bridge is None:
            try:
                from core.cloud_bridge import CloudBridge
                self.cloud_bridge = CloudBridge(self.config.cloud_server_url)
                logger.info("Cloud bridge initialized after mode switch")
            except ImportError as e:
                logger.warning(f"Could not initialize cloud bridge: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get renderer status"""
        return {
            "mode": self.config.render_mode.value,
            "local_available": self.local_renderer is not None,
            "cloud_available": self.cloud_bridge is not None,
            "fallback_available": self.fallback_renderer is not None,
            "cloud_server_url": self.cloud_server_url
        }


async def main():
    """Test renderer factory"""
    from loguru import logger
    
    logger.add("logs/renderer_factory_{time}.log", rotation="10 MB")
    
    # Create renderer
    renderer = Renderer()
    
    # Get status
    status = renderer.get_status()
    logger.info(f"Renderer status: {status}")
    
    # Test rendering
    test_text = "Hello, this is a test"
    frame = renderer.get_frame(test_text, emotion="happy")
    logger.info(f"Rendered frame: {type(frame)}")
    
    # Test mode switch
    renderer.switch_mode(RenderMode.FALLBACK)
    status = renderer.get_status()
    logger.info(f"Status after switch: {status}")
    
    logger.info("Renderer factory test complete")


if __name__ == "__main__":
    asyncio.run(main())
