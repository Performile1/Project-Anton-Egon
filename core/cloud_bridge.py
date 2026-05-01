#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Cloud Bridge
WebRTC tunnel for cloud rendering with failover logic
Phase 17: Cloud Infrastructure - Tailscale integration
"""

import asyncio
import sys
import json
import subprocess
from typing import Optional, Dict, Any
from enum import Enum
import hashlib
import time
import socket

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class ConnectionState(Enum):
    """Connection states"""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    FAILED = "FAILED"


class TailscaleManager:
    """
    Tailscale Manager
    Manages Tailscale VPN connection for secure tunnel to cloud server
    """
    
    def __init__(self, auth_key: Optional[str] = None):
        """
        Initialize Tailscale Manager
        
        Args:
            auth_key: Tailscale auth key (for headless setup)
        """
        self.auth_key = auth_key
        self.is_installed = self._check_tailscale_installed()
        self.is_connected = False
        self.tailscale_ip = None
        
        logger.info(f"Tailscale Manager initialized (installed: {self.is_installed})")
    
    def _check_tailscale_installed(self) -> bool:
        """Check if Tailscale is installed"""
        try:
            result = subprocess.run(
                ["tailscale", "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Tailscale not installed: {e}")
            return False
    
    def install_tailscale(self) -> bool:
        """
        Install Tailscale (Linux only)
        
        Returns:
            True if installed successfully
        """
        if sys.platform != "linux":
            logger.error("Tailscale auto-install only supported on Linux")
            return False
        
        try:
            logger.info("Installing Tailscale...")
            subprocess.run(
                ["wget", "-q", "https://tailscale.com/install.sh"],
                check=True
            )
            subprocess.run(["sh", "install.sh"], check=True)
            
            self.is_installed = self._check_tailscale_installed()
            logger.info(f"Tailscale installed: {self.is_installed}")
            
            return self.is_installed
            
        except Exception as e:
            logger.error(f"Failed to install Tailscale: {e}")
            return False
    
    async def connect(self, hostname: Optional[str] = None) -> bool:
        """
        Connect to Tailscale network
        
        Args:
            hostname: Optional hostname to assign
        
        Returns:
            True if connected successfully
        """
        if not self.is_installed:
            logger.error("Tailscale not installed")
            return False
        
        try:
            # Check if already connected
            status = await self.get_status()
            if status and status.get("online", False):
                self.is_connected = True
                self.tailscale_ip = status.get("tailscale_ips", [None])[0]
                logger.info(f"Already connected to Tailscale (IP: {self.tailscale_ip})")
                return True
            
            # Connect command
            cmd = ["tailscale", "up"]
            
            if self.auth_key:
                cmd.extend(["--authkey", self.auth_key])
            
            if hostname:
                cmd.extend(["--hostname", hostname])
            
            logger.info(f"Connecting to Tailscale network...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.is_connected = True
                
                # Get Tailscale IP
                status = await self.get_status()
                if status:
                    self.tailscale_ip = status.get("tailscale_ips", [None])[0]
                
                logger.info(f"Connected to Tailscale (IP: {self.tailscale_ip})")
                return True
            else:
                logger.error(f"Failed to connect to Tailscale: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to Tailscale: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """
        Disconnect from Tailscale network
        
        Returns:
            True if disconnected successfully
        """
        if not self.is_installed:
            return False
        
        try:
            subprocess.run(["tailscale", "down"], check=True, timeout=10)
            self.is_connected = False
            self.tailscale_ip = None
            logger.info("Disconnected from Tailscale")
            return True
        except Exception as e:
            logger.error(f"Failed to disconnect from Tailscale: {e}")
            return False
    
    async def get_status(self) -> Optional[Dict[str, Any]]:
        """
        Get Tailscale status
        
        Returns:
            Status dictionary or None
        """
        if not self.is_installed:
            return None
        
        try:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                status = json.loads(result.stdout)
                return status
            else:
                logger.warning(f"Failed to get Tailscale status: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting Tailscale status: {e}")
            return None
    
    async def get_peer_ip(self, hostname: str) -> Optional[str]:
        """
        Get Tailscale IP for a peer by hostname
        
        Args:
            hostname: Peer hostname (e.g., "runpod-server")
        
        Returns:
            Tailscale IP or None
        """
        status = await self.get_status()
        if not status:
            return None
        
        peers = status.get("Peer", {})
        
        for peer_name, peer_data in peers.items():
            if hostname.lower() in peer_name.lower():
                return peer_data.get("TailscaleIPs", [None])[0]
        
        logger.warning(f"Peer not found: {hostname}")
        return None
    
    def resolve_hostname(self, hostname: str) -> Optional[str]:
        """
        Resolve Tailscale hostname to IP (blocking)
        
        Args:
            hostname: Tailscale hostname
        
        Returns:
            IP address or None
        """
        try:
            # Tailscale uses .ts.net domain
            ts_hostname = f"{hostname}.ts.net"
            ip = socket.gethostbyname(ts_hostname)
            logger.debug(f"Resolved {hostname} to {ip}")
            return ip
        except Exception as e:
            logger.warning(f"Failed to resolve {hostname}: {e}")
            return None


class DataGuard:
    """Data leaking guard - strips metadata before sending to cloud"""
    
    @staticmethod
    def sanitize_text(text: str) -> str:
        """
        Sanitize text before sending to cloud
        Removes metadata, keeps only pure text to be spoken
        
        Args:
            text: Input text
        
        Returns:
            Sanitized text
        """
        # Remove common metadata patterns
        # This is a basic implementation - can be enhanced
        
        # Remove file paths
        import re
        text = re.sub(r'[A-Za-z]:\\[^\\/:*?"<>|]*', '', text)
        text = re.sub(r'/[^\\/:*?"<>|]*', '', text)
        
        # Remove email addresses (optional - uncomment if needed)
        # text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
        
        # Remove phone numbers (optional - uncomment if needed)
        # text = re.sub(r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '[PHONE]', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    @staticmethod
    def hash_sensitive_data(data: str) -> str:
        """
        Hash sensitive data for logging (not sent to cloud)
        
        Args:
            data: Sensitive data
        
        Returns:
            Hashed string
        """
        return hashlib.sha256(data.encode()).hexdigest()[:16]


class BandwidthMonitor:
    """Monitor bandwidth and adjust quality"""
    
    def __init__(self):
        self.ping_history = []
        self.bandwidth_history = []
        self.current_resolution = "1080p"
        self.target_ping_ms = 100
        self.max_ping_ms = 300
    
    def add_ping(self, ping_ms: float):
        """Add ping measurement"""
        self.ping_history.append(ping_ms)
        if len(self.ping_history) > 10:
            self.ping_history.pop(0)
    
    def get_avg_ping(self) -> Optional[float]:
        """Get average ping"""
        if not self.ping_history:
            return None
        return sum(self.ping_history) / len(self.ping_history)
    
    def should_downgrade_quality(self) -> bool:
        """Check if quality should be downgraded"""
        avg_ping = self.get_avg_ping()
        if avg_ping and avg_ping > self.max_ping_ms:
            return True
        return False
    
    def should_upgrade_quality(self) -> bool:
        """Check if quality should be upgraded"""
        avg_ping = self.get_avg_ping()
        if avg_ping and avg_ping < self.target_ping_ms and self.current_resolution == "720p":
            return True
        return False
    
    def adjust_quality(self):
        """Adjust resolution based on bandwidth"""
        if self.should_downgrade_quality() and self.current_resolution == "1080p":
            logger.warning(f"High ping detected ({self.get_avg_ping()}ms), downgrading to 720p")
            self.current_resolution = "720p"
        elif self.should_upgrade_quality():
            logger.info(f"Low ping detected ({self.get_avg_ping()}ms), upgrading to 1080p")
            self.current_resolution = "1080p"


class CloudBridge:
    """
    WebRTC tunnel for cloud rendering
    Handles connection, failover, and bandwidth monitoring
    Phase 17: Tailscale integration for secure tunnel
    """
    
    def __init__(self, server_url: str, tailscale_hostname: Optional[str] = None, use_tailscale: bool = True):
        self.server_url = server_url
        self.tailscale_hostname = tailscale_hostname
        self.use_tailscale = use_tailscale
        self.connection_state = ConnectionState.DISCONNECTED
        self.data_guard = DataGuard()
        self.bandwidth_monitor = BandwidthMonitor()
        self.connection_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 2  # seconds
        
        # Initialize Tailscale manager
        self.tailscale_manager = None
        if use_tailscale:
            self.tailscale_manager = TailscaleManager()
        
        logger.info(f"Cloud bridge initialized (server: {server_url}, tailscale: {use_tailscale})")
    
    async def connect(self) -> bool:
        """Connect to cloud server"""
        if self.connection_state == ConnectionState.CONNECTED:
            return True
        
        self.connection_state = ConnectionState.CONNECTING
        logger.info(f"Connecting to cloud server: {self.server_url}")
        
        try:
            # Connect via Tailscale if enabled
            if self.use_tailscale and self.tailscale_manager:
                if not self.tailscale_manager.is_connected:
                    logger.info("Connecting to Tailscale network...")
                    await self.tailscale_manager.connect(hostname="anton-egon-laptop")
                
                # Resolve server URL via Tailscale if hostname provided
                if self.tailscale_hostname:
                    resolved_ip = self.tailscale_manager.resolve_hostname(self.tailscale_hostname)
                    if resolved_ip:
                        logger.info(f"Resolved {self.tailscale_hostname} to {resolved_ip} via Tailscale")
                        # Update server URL to use Tailscale IP
                        self.server_url = f"http://{resolved_ip}:8000"
            
            # Placeholder for actual WebRTC connection
            # In production, this would use aiortc
            
            # Simulate connection
            await asyncio.sleep(0.5)
            
            self.connection_state = ConnectionState.CONNECTED
            self.connection_attempts = 0
            logger.info("Connected to cloud server")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to cloud server: {e}")
            self.connection_state = ConnectionState.FAILED
            return False
    
    async def disconnect(self):
        """Disconnect from cloud server"""
        self.connection_state = ConnectionState.DISCONNECTED
        logger.info("Disconnected from cloud server")
    
    async def request_frame(self, text: str, emotion: str, audio_features: Dict[str, Any] = None) -> Any:
        """
        Request frame from cloud server
        
        Args:
            text: Text to speak
            emotion: Facial emotion
            audio_features: Audio features for lip-sync
        
        Returns:
            Rendered frame
        """
        # Ensure connected
        if self.connection_state != ConnectionState.CONNECTED:
            if not await self.connect():
                raise ConnectionError("Failed to connect to cloud server")
        
        # Sanitize text before sending
        sanitized_text = self.data_guard.sanitize_text(text)
        logger.debug(f"Sending sanitized text to cloud (hash: {self.data_guard.hash_sensitive_data(sanitized_text)})")
        
        try:
            start_time = time.time()
            
            # Placeholder for actual WebRTC request
            # In production, this would use aiortc to send request and receive frame
            
            # Simulate rendering time
            await asyncio.sleep(0.2)
            
            # Measure ping
            ping_ms = (time.time() - start_time) * 1000
            self.bandwidth_monitor.add_ping(ping_ms)
            
            # Adjust quality if needed
            self.bandwidth_monitor.adjust_quality()
            
            # Return placeholder frame
            import numpy as np
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[100:380, 100:540] = [50, 50, 50]
            
            logger.debug(f"Frame received from cloud (ping: {ping_ms:.2f}ms, resolution: {self.bandwidth_monitor.current_resolution})")
            
            return frame
            
        except Exception as e:
            logger.error(f"Error requesting frame from cloud: {e}")
            
            # Attempt reconnection
            await self._handle_connection_error()
            
            raise
    
    async def _handle_connection_error(self):
        """Handle connection error with reconnection logic"""
        self.connection_attempts += 1
        
        if self.connection_attempts <= self.max_reconnect_attempts:
            logger.warning(f"Connection error, attempting reconnect ({self.connection_attempts}/{self.max_reconnect_attempts})")
            self.connection_state = ConnectionState.RECONNECTING
            
            await asyncio.sleep(self.reconnect_delay * self.connection_attempts)
            
            if await self.connect():
                logger.info("Reconnected successfully")
            else:
                logger.error("Reconnection failed")
        else:
            logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached, giving up")
            self.connection_state = ConnectionState.FAILED
    
    def get_status(self) -> Dict[str, Any]:
        """Get bridge status"""
        return {
            "state": self.connection_state.value,
            "server_url": self.server_url,
            "connection_attempts": self.connection_attempts,
            "avg_ping_ms": self.bandwidth_monitor.get_avg_ping(),
            "current_resolution": self.bandwidth_monitor.current_resolution
        }


async def main():
    """Test cloud bridge"""
    from loguru import logger
    
    logger.add("logs/cloud_bridge_{time}.log", rotation="10 MB")
    
    # Create bridge
    bridge = CloudBridge("ws://localhost:8080")
    
    # Test connection
    connected = await bridge.connect()
    logger.info(f"Connection result: {connected}")
    
    # Test frame request
    try:
        frame = await bridge.request_frame("Hello world", "happy")
        logger.info(f"Frame received: {type(frame)}")
    except Exception as e:
        logger.error(f"Error: {e}")
    
    # Get status
    status = bridge.get_status()
    logger.info(f"Bridge status: {status}")
    
    # Disconnect
    await bridge.disconnect()
    
    logger.info("Cloud bridge test complete")


if __name__ == "__main__":
    asyncio.run(main())
