#!/usr/bin/env python3
"""
Project Anton Egon - Phase 4: Audio Router
Virtual audio cable routing for streaming audio to Teams
"""

import pyaudio
import wave
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import asyncio

from loguru import logger
from pydantic import BaseModel, Field


class AudioRouterConfig(BaseModel):
    """Configuration for audio router"""
    input_device: str = Field(default="", description="Input device name")
    output_device: str = Field(default="", description="Output device name (virtual cable)")
    sample_rate: int = Field(default=44100, description="Sample rate in Hz")
    channels: int = Field(default=1, description="Number of audio channels")
    chunk_size: int = Field(default=1024, description="Audio chunk size")
    enable_virtual_cable: bool = Field(default=True, description="Enable virtual audio cable")


class AudioRouter:
    """
    Audio router for streaming audio to virtual audio cable
    Routes synthesizer output to Teams via VB-Cable or similar
    """
    
    def __init__(self, config: AudioRouterConfig):
        """Initialize audio router"""
        self.config = config
        
        # PyAudio instance
        self.pyaudio = None
        self.output_stream = None
        
        # State
        self.running = False
        self.audio_queue = []
        
        logger.info(f"Audio Router initialized (output: {config.output_device or 'default'})")
    
    def _list_audio_devices(self) -> Dict[str, Any]:
        """List available audio devices"""
        try:
            p = pyaudio.PyAudio()
            
            devices = {
                "input": [],
                "output": []
            }
            
            for i in range(p.get_device_count()):
                device_info = p.get_device_info_by_index(i)
                if device_info["maxInputChannels"] > 0:
                    devices["input"].append({
                        "index": i,
                        "name": device_info["name"],
                        "channels": device_info["maxInputChannels"]
                    })
                if device_info["maxOutputChannels"] > 0:
                    devices["output"].append({
                        "index": i,
                        "name": device_info["name"],
                        "channels": device_info["maxOutputChannels"]
                    })
            
            p.terminate()
            
            return devices
            
        except Exception as e:
            logger.error(f"Failed to list audio devices: {e}")
            return {"input": [], "output": []}
    
    def _init_output_stream(self):
        """Initialize output stream to virtual audio cable"""
        try:
            self.pyaudio = pyaudio.PyAudio()
            
            # Find output device
            output_device_index = None
            if self.config.output_device:
                devices = self._list_audio_devices()
                for device in devices["output"]:
                    if self.config.output_device.lower() in device["name"].lower():
                        output_device_index = device["index"]
                        break
            
            # Open output stream
            self.output_stream = self.pyaudio.open(
                format=pyaudio.paInt16,
                channels=self.config.channels,
                rate=self.config.sample_rate,
                output=True,
                output_device_index=output_device_index,
                frames_per_buffer=self.config.chunk_size
            )
            
            logger.info(f"Output stream initialized (device: {output_device_index or 'default'})")
            
        except Exception as e:
            logger.error(f"Failed to initialize output stream: {e}")
    
    def enqueue_audio(self, audio_data: bytes):
        """
        Enqueue audio data for playback
        
        Args:
            audio_data: Raw audio data (PCM)
        """
        self.audio_queue.append(audio_data)
        logger.debug(f"Enqueued audio: {len(audio_data)} bytes (queue size: {len(self.audio_queue)})")
    
    async def _playback_loop(self):
        """Main audio playback loop"""
        logger.info("Starting audio playback loop")
        
        while self.running:
            try:
                if self.audio_queue and self.output_stream:
                    audio_data = self.audio_queue.pop(0)
                    self.output_stream.write(audio_data)
                else:
                    await asyncio.sleep(0.01)
                    
            except Exception as e:
                logger.error(f"Playback loop error: {e}")
                await asyncio.sleep(0.1)
    
    async def start(self):
        """Start audio router"""
        if self.running:
            logger.warning("Audio router already running")
            return
        
        logger.info("Starting audio router")
        self.running = True
        
        # Initialize output stream
        if self.config.enable_virtual_cable:
            self._init_output_stream()
        
        # Start playback task
        asyncio.create_task(self._playback_loop())
    
    async def stop(self):
        """Stop audio router"""
        if not self.running:
            return
        
        logger.info("Stopping audio router")
        self.running = False
        
        # Close output stream
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
            self.output_stream = None
        
        # Terminate PyAudio
        if self.pyaudio:
            self.pyaudio.terminate()
            self.pyaudio = None
        
        logger.info("Audio router stopped")
    
    def clear_queue(self):
        """Clear audio queue"""
        self.audio_queue.clear()
        logger.info("Audio queue cleared")
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        return len(self.audio_queue)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current router status"""
        return {
            "running": self.running,
            "output_device": self.config.output_device,
            "sample_rate": self.config.sample_rate,
            "channels": self.config.channels,
            "queue_size": len(self.audio_queue),
            "stream_active": self.output_stream is not None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test the audio router"""
    from loguru import logger
    
    logger.add("logs/audio_router_{time}.log", rotation="10 MB")
    
    # Create audio router
    config = AudioRouterConfig()
    router = AudioRouter(config)
    
    # List available devices
    devices = router._list_audio_devices()
    logger.info(f"Available devices: {devices}")
    
    # Test status
    status = router.get_status()
    logger.info(f"Audio Router status: {status}")
    
    # Test playback (short test)
    try:
        await router.start()
        await asyncio.sleep(2)
        await router.stop()
    except Exception as e:
        logger.error(f"Test error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
