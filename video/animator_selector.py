#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Animator Selector
Selects appropriate animator based on render mode
Progressive Architecture: Stitcher Mode (pre-recorded) vs Generative Mode (LivePortrait)
"""

import sys
from typing import Optional, Dict, Any
from enum import Enum
from pathlib import Path

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class RenderEngine(Enum):
    """Render engine types for progressive architecture"""
    STITCHER = "stitcher"  # Pre-recorded assets (Idle, Nod, Laugh, Speak)
    GENERATIVE = "generative"  # LivePortrait/RunPod AI-driven video


class StitcherNode(Enum):
    """Stitcher node types for pre-recorded assets"""
    IDLE = "idle"
    NOD = "nod"
    LAUGH = "laugh"
    SPEAK = "speak"


class AnimatorSelector:
    """
    Selects appropriate animator based on render engine
    Progressive Architecture: Stitcher Mode (fail-safe) vs Generative Mode (AI)
    """
    
    def __init__(self):
        self.current_engine = RenderEngine.STITCHER
        self.stitcher_nodes = {}  # Dict[StitcherNode, video_path]
        self.generative_animator = None
        
        self._load_stitcher_nodes()
        self._initialize_animator()
    
    def _load_stitcher_nodes(self):
        """Load pre-recorded stitcher node assets"""
        assets_dir = Path("assets/video/stitcher_nodes")
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        for node in StitcherNode:
            # Try to find video file for this node
            video_path = assets_dir / f"{node.value}.mp4"
            if video_path.exists():
                self.stitcher_nodes[node] = str(video_path)
                logger.info(f"Loaded stitcher node: {node.value} -> {video_path}")
            else:
                logger.warning(f"Stitcher node not found: {node.value} -> {video_path}")
                # Create placeholder
                self.stitcher_nodes[node] = None
    
    def _initialize_animator(self):
        """Initialize animator based on current render engine"""
        logger.info(f"Initializing animator for engine: {self.current_engine.value}")
        
        if self.current_engine == RenderEngine.GENERATIVE:
            self._initialize_generative_animator()
        # Stitcher mode doesn't need initialization - uses pre-recorded assets
    
    def _initialize_generative_animator(self):
        """Initialize generative animator (LivePortrait)"""
        try:
            from video.liveportrait import LivePortraitAnimator
            
            self.generative_animator = LivePortraitAnimator()
            logger.info("Generative animator (LivePortrait) initialized")
            
        except ImportError as e:
            logger.error(f"Failed to initialize generative animator: {e}")
            logger.info("Falling back to stitcher mode")
            self.current_engine = RenderEngine.STITCHER
    
    def get_frame(self, text: str, emotion: str = "neutral", audio_features: Dict[str, Any] = None,
                  mood_adjustments: Dict[str, float] = None, stitcher_node: StitcherNode = None) -> Any:
        """
        Get frame from appropriate animator

        Args:
            text: Text to speak
            emotion: Facial emotion
            audio_features: Audio features for lip-sync
            mood_adjustments: Visual mood adjustments from mood engine
            stitcher_node: Specific stitcher node to use (for Stitcher Mode)

        Returns:
            Rendered frame
        """
        try:
            if self.current_engine == RenderEngine.STITCHER:
                return self._get_stitcher_frame(stitcher_node or StitcherNode.IDLE)
            elif self.current_engine == RenderEngine.GENERATIVE:
                return self._get_generative_frame(text, emotion, audio_features, mood_adjustments)
            else:
                logger.error(f"Unknown render engine: {self.current_engine}")
                return None

        except Exception as e:
            logger.error(f"Error getting frame: {e}")
            # Fallback to stitcher mode
            return self._get_stitcher_frame(StitcherNode.IDLE)

    def _get_stitcher_frame(self, node: StitcherNode) -> Any:
        """Get frame from stitcher node (pre-recorded asset)"""
        video_path = self.stitcher_nodes.get(node)
        if video_path is None:
            logger.warning(f"Stitcher node not available: {node.value}, using IDLE")
            video_path = self.stitcher_nodes.get(StitcherNode.IDLE)
        
        if video_path is None:
            logger.error("No stitcher nodes available")
            return None
        
        # Return video path for playback (actual frame reading handled by video player)
        return {"type": "stitcher", "path": video_path, "node": node.value}

    def _get_generative_frame(self, text: str, emotion: str, audio_features: Dict[str, Any] = None,
                             mood_adjustments: Dict[str, float] = None) -> Any:
        """Get frame from generative animator (LivePortrait)"""
        if self.generative_animator is None:
            logger.warning("Generative animator not available, using stitcher mode")
            return self._get_stitcher_frame(StitcherNode.IDLE)

        # Get frame from LivePortrait
        frame = self.generative_animator.get_frame(text, emotion, audio_features)
        return {"type": "generative", "frame": frame}

    def switch_engine(self, engine: RenderEngine):
        """
        Switch to different render engine

        Args:
            engine: New render engine
        """
        logger.info(f"Switching from {self.current_engine.value} to {engine.value}")

        # Update current engine
        self.current_engine = engine

        # Reinitialize animator
        self._initialize_animator()

        logger.info(f"Switched to {engine.value}")

    def get_status(self) -> Dict[str, Any]:
        """Get animator selector status"""
        return {
            "current_engine": self.current_engine.value,
            "stitcher_nodes": {node.value: path is not None for node, path in self.stitcher_nodes.items()},
            "generative_available": self.generative_animator is not None
        }


def main():
    """Test animator selector"""
    logger.add("logs/animator_selector_{time}.log", rotation="10 MB")

    # Create selector
    selector = AnimatorSelector()

    # Get status
    status = selector.get_status()
    logger.info(f"Animator selector status: {status}")

    # Test getting frame (stitcher mode)
    frame = selector.get_frame(stitcher_node=StitcherNode.IDLE)
    logger.info(f"Frame received (stitcher): {type(frame)}")

    # Test switching to generative mode
    selector.switch_engine(RenderEngine.GENERATIVE)
    status = selector.get_status()
    logger.info(f"Status after switch to generative: {status}")

    logger.info("Animator selector test complete")


if __name__ == "__main__":
    main()
