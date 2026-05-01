#!/usr/bin/env python3
"""
Project Anton Egon - Phase 5: OBS Connector
A/V sync check and virtual camera streaming
"""

import time
import asyncio
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timezone

from loguru import logger
from pydantic import BaseModel, Field


class OBSConnectorConfig(BaseModel):
    """Configuration for OBS connector"""
    sync_tolerance_ms: float = Field(default=30, description="A/V sync tolerance in milliseconds")
    audio_latency_ms: float = Field(default=100, description="Audio latency in milliseconds")
    video_latency_ms: float = Field(default=250, description="Video latency in milliseconds")
    enable_sync_check: bool = Field(default=True, description="Enable A/V sync checking")
    buffer_size_ms: float = Field(default=100, description="Timestamp buffer size in milliseconds")


class TimestampBuffer:
    """
    Timestamp buffer for A/V sync
    Buffers audio and video timestamps to ensure sync
    """
    
    def __init__(self, buffer_size_ms: float = 100):
        """
        Initialize timestamp buffer
        
        Args:
            buffer_size_ms: Buffer size in milliseconds
        """
        self.buffer_size_ms = buffer_size_ms
        self.audio_buffer = deque()
        self.video_buffer = deque()
        
        logger.info(f"Timestamp buffer initialized (size: {buffer_size_ms}ms)")
    
    def add_audio(self, timestamp: float, data: Any = None):
        """
        Add audio timestamp to buffer
        
        Args:
            timestamp: Audio timestamp in seconds
            data: Optional audio data
        """
        self.audio_buffer.append((timestamp, data))
        
        # Prune old entries
        cutoff = time.time() - (self.buffer_size_ms / 1000)
        while self.audio_buffer and self.audio_buffer[0][0] < cutoff:
            self.audio_buffer.popleft()
    
    def add_video(self, timestamp: float, data: Any = None):
        """
        Add video timestamp to buffer
        
        Args:
            timestamp: Video timestamp in seconds
            data: Optional video data
        """
        self.video_buffer.append((timestamp, data))
        
        # Prune old entries
        cutoff = time.time() - (self.buffer_size_ms / 1000)
        while self.video_buffer and self.video_buffer[0][0] < cutoff:
            self.video_buffer.popleft()
    
    def get_synced_pair(self) -> Optional[Tuple[Any, Any, float]]:
        """
        Get synced audio/video pair
        Returns the pair with the smallest timestamp difference
        
        Returns:
            (audio_data, video_data, offset_ms) or None if no synced pair
        """
        if not self.audio_buffer or not self.video_buffer:
            return None
        
        # Find best match (smallest time difference)
        best_audio = None
        best_video = None
        min_diff = float('inf')
        
        for audio_ts, audio_data in self.audio_buffer:
            for video_ts, video_data in self.video_buffer:
                diff = abs(audio_ts - video_ts)
                if diff < min_diff:
                    min_diff = diff
                    best_audio = (audio_ts, audio_data)
                    best_video = (video_ts, video_data)
        
        if min_diff > (self.buffer_size_ms / 1000):
            return None
        
        offset_ms = (best_audio[0] - best_video[0]) * 1000
        return (best_audio[1], best_video[1], offset_ms)
    
    def clear(self):
        """Clear all buffers"""
        self.audio_buffer.clear()
        self.video_buffer.clear()
        logger.debug("Timestamp buffers cleared")


class OBSConnector:
    """
    OBS Connector for A/V sync monitoring
    Measures time difference between audio and video to ensure lip-sync accuracy
    """
    
    def __init__(self, config: OBSConnectorConfig):
        """Initialize OBS connector"""
        self.config = config
        
        # State
        self.running = False
        self.audio_timestamps = []
        self.video_timestamps = []
        self.sync_offset_ms = 0.0
        
        # Timestamp buffer for sync
        self.timestamp_buffer = TimestampBuffer(config.buffer_size_ms)
        
        # Callbacks
        self.on_sync_issue: Optional[Callable] = None
        self.on_sync_restored: Optional[Callable] = None
        
        logger.info(f"OBS Connector initialized (sync tolerance: {config.sync_tolerance_ms}ms)")
    
    def register_audio_timestamp(self, timestamp: float, data: Any = None):
        """
        Register audio timestamp for sync check
        
        Args:
            timestamp: Audio timestamp in seconds
            data: Optional audio data
        """
        self.audio_timestamps.append((time.time(), timestamp))
        self.timestamp_buffer.add_audio(timestamp, data)
        
        # Keep only recent timestamps
        if len(self.audio_timestamps) > 100:
            self.audio_timestamps.pop(0)
    
    def register_video_timestamp(self, timestamp: float, data: Any = None):
        """
        Register video timestamp for sync check
        
        Args:
            timestamp: Video timestamp in seconds
            data: Optional video data
        """
        self.video_timestamps.append((time.time(), timestamp))
        self.timestamp_buffer.add_video(timestamp, data)
        
        # Keep only recent timestamps
        if len(self.video_timestamps) > 100:
            self.video_timestamps.pop(0)
    
    def get_synced_output(self) -> Optional[Tuple[Any, Any, float]]:
        """
        Get synced audio/video output from buffer
        Forces sync by buffering the faster stream
        
        Returns:
            (audio_data, video_data, offset_ms) or None if no synced pair
        """
        return self.timestamp_buffer.get_synced_pair()
    
    def calculate_sync_offset(self) -> float:
        """
        Calculate current A/V sync offset
        
        Returns:
            Offset in milliseconds (positive = audio ahead, negative = video ahead)
        """
        if not self.audio_timestamps or not self.video_timestamps:
            return 0.0
        
        # Get most recent timestamps
        latest_audio = self.audio_timestamps[-1][1]
        latest_video = self.video_timestamps[-1][1]
        
        # Calculate offset (audio - video)
        offset_ms = (latest_audio - latest_video) * 1000
        
        # Apply expected latencies
        offset_ms += (self.config.audio_latency_ms - self.config.video_latency_ms)
        
        self.sync_offset_ms = offset_ms
        return offset_ms
    
    def check_sync(self) -> bool:
        """
        Check if A/V sync is within tolerance
        
        Returns:
            True if sync is acceptable
        """
        offset = self.calculate_sync_offset()
        is_synced = abs(offset) <= self.config.sync_tolerance_ms
        
        if not is_synced and self.on_sync_issue:
            self.on_sync_issue(offset)
        elif is_synced and self.on_sync_restored and abs(self.sync_offset_ms) > self.config.sync_tolerance_ms:
            self.on_sync_restored()
        
        return is_synced
    
    async def _sync_check_loop(self):
        """Main sync check loop"""
        logger.info("Starting A/V sync check loop")
        
        while self.running:
            try:
                if self.config.enable_sync_check:
                    is_synced = self.check_sync()
                    
                    if not is_synced:
                        logger.warning(f"A/V sync issue detected: {self.sync_offset_ms:.1f}ms offset")
                
                await asyncio.sleep(0.1)  # Check every 100ms
                
            except Exception as e:
                logger.error(f"Sync check loop error: {e}")
                await asyncio.sleep(1)
    
    async def start(self):
        """Start sync monitoring"""
        if self.running:
            logger.warning("OBS connector already running")
            return
        
        logger.info("Starting OBS connector")
        self.running = True
        
        # Start sync check task
        asyncio.create_task(self._sync_check_loop())
    
    async def stop(self):
        """Stop sync monitoring"""
        if not self.running:
            return
        
        logger.info("Stopping OBS connector")
        self.running = False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current connector status"""
        return {
            "running": self.running,
            "sync_offset_ms": self.sync_offset_ms,
            "sync_tolerance_ms": self.config.sync_tolerance_ms,
            "is_synced": abs(self.sync_offset_ms) <= self.config.sync_tolerance_ms,
            "audio_latency_ms": self.config.audio_latency_ms,
            "video_latency_ms": self.config.video_latency_ms,
            "audio_timestamps_count": len(self.audio_timestamps),
            "video_timestamps_count": len(self.video_timestamps),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test the OBS connector"""
    from loguru import logger
    
    logger.add("logs/obs_connector_{time}.log", rotation="10 MB")
    
    # Create OBS connector
    config = OBSConnectorConfig()
    connector = OBSConnector(config)
    
    # Test status
    status = connector.get_status()
    logger.info(f"OBS Connector status: {status}")
    
    # Test sync check
    try:
        await connector.start()
        
        # Simulate audio/video timestamps
        for i in range(10):
            connector.register_audio_timestamp(time.time())
            connector.register_video_timestamp(time.time() + 0.05)  # 50ms offset
            await asyncio.sleep(0.1)
        
        offset = connector.calculate_sync_offset()
        logger.info(f"Sync offset: {offset:.1f}ms")
        
        await asyncio.sleep(2)
        await connector.stop()
    except Exception as e:
        logger.error(f"Test error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
