#!/usr/bin/env python3
"""
Project Anton Egon - Session Guard
Session Locking: Binary choice for Cloud Mode (High Fidelity) vs Local Mode (Safety First)

Phase 16: The Trickster Engine
"""

import asyncio
import socket
import time
from typing import Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone

import aiohttp
from loguru import logger


class SessionMode(Enum):
    """Session rendering modes"""
    CLOUD = "cloud"  # High fidelity, requires stable network
    LOCAL = "local"  # Safety first, pre-recorded base outfits


class NetworkQuality(Enum):
    """Network quality levels"""
    EXCELLENT = "excellent"  # < 50ms ping
    GOOD = "good"  # 50-80ms ping
    FAIR = "fair"  # 80-150ms ping
    POOR = "poor"  # > 150ms ping
    UNAVAILABLE = "unavailable"


@dataclass
class NetworkTestResult:
    """Network test result"""
    quality: NetworkQuality
    ping_ms: float
    packet_loss: float
    bandwidth_mbps: Optional[float]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "quality": self.quality.value,
            "ping_ms": self.ping_ms,
            "packet_loss": self.packet_loss,
            "bandwidth_mbps": self.bandwidth_mbps,
            "timestamp": self.timestamp.isoformat()
        }


class SessionGuard:
    """
    Session Guard
    Manages session mode selection based on network quality
    """
    
    def __init__(self, ping_threshold_ms: float = 80.0):
        """
        Initialize Session Guard
        
        Args:
            ping_threshold_ms: Threshold for cloud mode (default 80ms)
        """
        self.ping_threshold_ms = ping_threshold_ms
        self.current_mode: Optional[SessionMode] = None
        self.last_network_test: Optional[NetworkTestResult] = None
        self.is_locked = False
        self.fallback_image_path: Optional[str] = None  # Local fallback image
        self.fallback_text = "Connecting to cloud power..."  # Fallback overlay text
        
        # Test servers for ping
        self.test_hosts = [
            "google.com",
            "cloudflare.com",
            "microsoft.com"
        ]
        
        logger.info(f"Session Guard initialized (ping threshold: {ping_threshold_ms}ms)")
    
    async def test_network(self) -> NetworkTestResult:
        """
        Test network quality
        
        Returns:
            Network test result
        """
        start_time = time.time()
        ping_times = []
        packet_loss = 0.0
        
        # Test ping to multiple hosts
        for host in self.test_hosts:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                
                ping_start = time.time()
                sock.connect((host, 443))
                ping_end = time.time()
                
                sock.close()
                
                ping_ms = (ping_end - ping_start) * 1000
                ping_times.append(ping_ms)
                
            except Exception as e:
                packet_loss += 1.0 / len(self.test_hosts)
                logger.warning(f"Network test failed for {host}: {e}")
        
        # Calculate average ping
        avg_ping = sum(ping_times) / len(ping_times) if ping_times else float('inf')
        
        # Determine network quality
        if avg_ping < 50:
            quality = NetworkQuality.EXCELLENT
        elif avg_ping < 80:
            quality = NetworkQuality.GOOD
        elif avg_ping < 150:
            quality = NetworkQuality.FAIR
        elif avg_ping < float('inf'):
            quality = NetworkQuality.POOR
        else:
            quality = NetworkQuality.UNAVAILABLE
        
        result = NetworkTestResult(
            quality=quality,
            ping_ms=avg_ping,
            packet_loss=packet_loss,
            bandwidth_mbps=None,  # TODO: Implement bandwidth test
            timestamp=datetime.now(timezone.utc)
        )
        
        self.last_network_test = result
        logger.info(f"Network test: {quality.value}, ping: {avg_ping:.2f}ms, packet loss: {packet_loss:.2%}")
        
        return result
    
    async def recommend_mode(self) -> SessionMode:
        """
        Recommend session mode based on network quality
        
        Returns:
            Recommended session mode
        """
        if self.last_network_test is None:
            await self.test_network()
        
        if self.last_network_test is None:
            # Network test failed, default to local
            logger.warning("Network test unavailable, defaulting to LOCAL mode")
            return SessionMode.LOCAL
        
        # Decision logic
        if self.last_network_test.quality in [NetworkQuality.EXCELLENT, NetworkQuality.GOOD]:
            return SessionMode.CLOUD
        else:
            return SessionMode.LOCAL
    
    async def lock_session(self, mode: SessionMode) -> bool:
        """
        Lock session to specific mode
        
        Args:
            mode: Session mode to lock to
        
        Returns:
            True if locked successfully
        """
        if self.is_locked:
            logger.warning("Session already locked")
            return False
        
        self.current_mode = mode
        self.is_locked = True
        
        logger.info(f"Session locked to {mode.value} mode")
        return True
    
    def unlock_session(self) -> bool:
        """
        Unlock session
        
        Returns:
            True if unlocked successfully
        """
        if not self.is_locked:
            logger.warning("Session not locked")
            return False
        
        self.is_locked = False
        self.current_mode = None
        
        logger.info("Session unlocked")
        return True
    
    def get_current_mode(self) -> Optional[SessionMode]:
        """Get current session mode"""
        return self.current_mode
    
    def get_network_status(self) -> Optional[Dict[str, Any]]:
        """Get network status"""
        if self.last_network_test:
            return self.last_network_test.to_dict()
        return None
    
    def should_use_cloud(self) -> bool:
        """
        Check if cloud mode should be used
        
        Returns:
            True if cloud mode is recommended
        """
        if self.last_network_test is None:
            return False
        
        return self.last_network_test.ping_ms < self.ping_threshold_ms
    
    async def auto_select_mode(self) -> SessionMode:
        """
        Automatically select mode based on network test
        
        Returns:
            Selected session mode
        """
        result = await self.test_network()
        
        if result.quality in [NetworkQuality.EXCELLENT, NetworkQuality.GOOD]:
            mode = SessionMode.CLOUD
        else:
            mode = SessionMode.LOCAL
        
        await self.lock_session(mode)
        
        return mode
    
    def get_mode_recommendation_text(self) -> str:
        """
        Get human-readable mode recommendation
        
        Returns:
            Recommendation text
        """
        if self.last_network_test is None:
            return "Network test required"
        
        if self.last_network_test.quality == NetworkQuality.EXCELLENT:
            return f"EXCELLENT network ({self.last_network_test.ping_ms:.0f}ms) - Cloud Mode recommended"
        elif self.last_network_test.quality == NetworkQuality.GOOD:
            return f"GOOD network ({self.last_network_test.ping_ms:.0f}ms) - Cloud Mode recommended"
        elif self.last_network_test.quality == NetworkQuality.FAIR:
            return f"FAIR network ({self.last_network_test.ping_ms:.0f}ms) - Local Mode recommended"
        elif self.last_network_test.quality == NetworkQuality.POOR:
            return f"POOR network ({self.last_network_test.ping_ms:.0f}ms) - Local Mode required"
        else:
            return "Network unavailable - Local Mode required"
    
    def set_fallback_image(self, image_path: str):
        """
        Set local fallback image for cloud failure
        
        Args:
            image_path: Path to fallback image
        """
        self.fallback_image_path = image_path
        logger.info(f"Fallback image set to {image_path}")
    
    def trigger_fallback(self) -> Dict[str, Any]:
        """
        Trigger local fallback (called when cloud instance fails)
        
        Returns:
            Fallback configuration
        """
        logger.warning("Triggering local fallback due to cloud failure")
        
        # Switch to local mode
        self.current_mode = SessionMode.LOCAL
        
        return {
            "mode": "local",
            "fallback_image": self.fallback_image_path,
            "overlay_text": self.fallback_text,
            "reason": "Cloud instance failure - switched to local fallback"
        }


# Singleton instance
session_guard = SessionGuard()


async def main():
    """Test Session Guard"""
    logger.add("logs/session_guard_{time}.log", rotation="10 MB")
    
    # Test network
    result = await session_guard.test_network()
    logger.info(f"Network test result: {result.to_dict()}")
    
    # Get recommendation
    mode = await session_guard.recommend_mode()
    logger.info(f"Recommended mode: {mode.value}")
    
    # Get recommendation text
    text = session_guard.get_mode_recommendation_text()
    logger.info(f"Recommendation: {text}")
    
    logger.info("Session Guard test complete")


if __name__ == "__main__":
    asyncio.run(main())
