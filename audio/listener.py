#!/usr/bin/env python3
"""
Project Anton Egon - Phase 2: Audio Listener
Async audio streaming with Faster-Whisper and Silero VAD
"""

import asyncio
import queue
import threading
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timezone
import numpy as np

from faster_whisper import WhisperModel
from silero_vad import VADIterator, load_silero_vad
import sounddevice as sd
import torch

from loguru import logger


class AudioConfig:
    """Audio configuration"""
    SAMPLE_RATE = 16000  # Whisper requires 16kHz
    CHUNK_SIZE = 512  # Audio chunk size for processing
    CHANNELS = 1  # Mono audio
    VAD_THRESHOLD = 0.5  # Voice activity threshold
    VAD_PADDING = 30  # Padding in ms for VAD
    MAX_LATENCY_MS = 500  # Maximum acceptable latency


class AudioListener:
    """
    Async audio listener with VAD and transcription
    Streams text to the orchestrator in real-time
    """
    
    def __init__(
        self,
        model_size: str = "large-v3-turbo",
        device: str = "auto",
        on_transcription: Optional[Callable] = None
    ):
        """
        Initialize audio listener
        
        Args:
            model_size: Whisper model size
            device: Device for inference ("auto", "cpu", "cuda")
            on_transcription: Callback for transcription results
        """
        self.model_size = model_size
        self.device = device
        self.on_transcription = on_transcription
        
        self.audio_queue = queue.Queue()
        self.running = False
        self.transcription_task = None
        self.vad_iterator = None
        
        logger.info(f"Initializing AudioListener with model: {model_size}")
        
        # Initialize Whisper model
        self._init_whisper()
        
        # Initialize VAD
        self._init_vad()
    
    def _init_whisper(self):
        """Initialize Faster-Whisper model"""
        try:
            # Determine device
            if self.device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                device = self.device
            
            logger.info(f"Loading Whisper model on {device}")
            self.whisper_model = WhisperModel(
                self.model_size,
                device=device,
                compute_type="float16" if device == "cuda" else "int8"
            )
            logger.info("Whisper model loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    
    def _init_vad(self):
        """Initialize Silero VAD"""
        try:
            logger.info("Loading Silero VAD model")
            torch.hub.set_dir("models")
            vad_model = load_silero_vad()
            self.vad_iterator = VADIterator(
                vad_model,
                threshold=AudioConfig.VAD_THRESHOLD,
                sampling_rate=AudioConfig.SAMPLE_RATE,
                min_silence_duration_ms=AudioConfig.VAD_PADDING,
                speech_pad_ms=AudioConfig.VAD_PADDING
            )
            logger.info("Silero VAD loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load VAD: {e}")
            raise
    
    def _audio_callback(self, indata, frames, time, status):
        """Callback for audio stream"""
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        # Put audio data in queue for processing
        self.audio_queue.put(indata.copy())
    
    async def _process_audio(self):
        """Process audio chunks with VAD and transcription"""
        logger.info("Starting audio processing loop")
        
        speech_buffer = []
        is_speech = False
        
        while self.running:
            try:
                # Get audio chunk from queue (non-blocking)
                try:
                    audio_chunk = self.audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Flatten audio chunk
                audio_flat = audio_chunk.flatten()
                
                # Apply VAD
                vad_result = self.vad_iterator(torch.from_numpy(audio_float32 = audio_flat.astype(np.float32)))
                
                if vad_result:
                    # Speech detected
                    if not is_speech:
                        logger.debug("Speech started")
                        is_speech = True
                    speech_buffer.extend(audio_flat)
                else:
                    # Silence detected
                    if is_speech:
                        logger.debug("Speech ended")
                        is_speech = False
                        
                        # Transcribe accumulated speech
                        if len(speech_buffer) > 0:
                            await self._transcribe_speech(speech_buffer)
                            speech_buffer = []
                
                # Timeout for speech buffer (if speech goes on too long)
                if is_speech and len(speech_buffer) > AudioConfig.SAMPLE_RATE * 10:
                    logger.debug("Speech buffer timeout, transcribing")
                    await self._transcribe_speech(speech_buffer)
                    speech_buffer = []
                    is_speech = False
                
            except Exception as e:
                logger.error(f"Error processing audio: {e}")
                await asyncio.sleep(0.1)
        
        # Transcribe remaining speech buffer
        if len(speech_buffer) > 0:
            await self._transcribe_speech(speech_buffer)
    
    async def _transcribe_speech(self, audio_buffer):
        """Transcribe speech buffer using Whisper"""
        try:
            # Convert to numpy array
            audio_array = np.array(audio_buffer, dtype=np.float32)
            
            # Transcribe with Whisper
            start_time = datetime.now(timezone.utc)
            segments, info = self.whisper_model.transcribe(
                audio_array,
                beam_size=5,
                language=None,  # Auto-detect language
                condition_on_previous_text=True,
                vad_filter=False  # We already use VAD
            )
            
            # Calculate latency
            latency_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            if latency_ms > AudioConfig.MAX_LATENCY_MS:
                logger.warning(f"High transcription latency: {latency_ms:.0f}ms")
            
            # Process segments
            full_text = ""
            for segment in segments:
                text = segment.text.strip()
                if text:
                    full_text += text + " "
                    
                    # Emit transcription result
                    result = {
                        "text": text,
                        "start": segment.start,
                        "end": segment.end,
                        "language": info.language,
                        "language_probability": info.language_probability,
                        "latency_ms": latency_ms,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    logger.info(f"Transcription: {text}")
                    
                    # Call callback if provided
                    if self.on_transcription:
                        await self.on_transcription(result)
            
            return full_text.strip()
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""
    
    async def start(self):
        """Start audio listening"""
        if self.running:
            logger.warning("Audio listener already running")
            return
        
        logger.info("Starting audio listener")
        self.running = True
        
        # Start audio stream
        try:
            self.stream = sd.InputStream(
                samplerate=AudioConfig.SAMPLE_RATE,
                channels=AudioConfig.CHANNELS,
                dtype=np.float32,
                blocksize=AudioConfig.CHUNK_SIZE,
                callback=self._audio_callback
            )
            self.stream.start()
            logger.info("Audio stream started")
            
            # Start transcription task
            self.transcription_task = asyncio.create_task(self._process_audio())
            
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            self.running = False
            raise
    
    async def stop(self):
        """Stop audio listening"""
        if not self.running:
            return
        
        logger.info("Stopping audio listener")
        self.running = False
        
        # Stop audio stream
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        
        # Cancel transcription task
        if self.transcription_task:
            self.transcription_task.cancel()
            try:
                await self.transcription_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Audio listener stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current listener status"""
        return {
            "running": self.running,
            "model_size": self.model_size,
            "device": self.device,
            "queue_size": self.audio_queue.qsize(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test the audio listener"""
    from loguru import logger
    
    logger.add("logs/audio_listener_{time}.log", rotation="10 MB")
    
    # Test callback
    async def on_transcription(result):
        logger.info(f"Transcribed: {result['text']}")
    
    # Create listener
    listener = AudioListener(on_transcription=on_transcription)
    
    try:
        await listener.start()
        logger.info("Listening... Press Ctrl+C to stop")
        
        # Run for 30 seconds
        await asyncio.sleep(30)
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await listener.stop()


if __name__ == "__main__":
    asyncio.run(main())
