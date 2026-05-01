#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Audio Echo Cancellation (AEC)
Prevents feedback loops and echo in audio routing
"""

import sys
import numpy as np
from typing import Optional, Tuple
from collections import deque

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class EchoCanceller:
    """
    Audio Echo Cancellation (AEC) module
    Subtracts meeting audio from agent's listening input to prevent feedback loops
    """
    
    def __init__(self, sample_rate: int = 16000, buffer_size: int = 5):
        """
        Initialize echo canceller
        
        Args:
            sample_rate: Audio sample rate (Hz)
            buffer_size: Buffer size in seconds
        """
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.samples_per_buffer = sample_rate * buffer_size
        
        # Ring buffer for meeting audio (far-end signal)
        self.meeting_audio_buffer = deque(maxlen=self.samples_per_buffer)
        
        # Adaptive filter coefficients (simplified LMS algorithm)
        self.filter_length = 512
        self.filter_coeffs = np.zeros(self.filter_length)
        self.learning_rate = 0.01
        
        # Echo estimate
        self.echo_estimate_buffer = deque(maxlen=self.samples_per_buffer)
        
        logger.info(f"Echo canceller initialized: {sample_rate} Hz, {buffer_size}s buffer")
    
    def register_meeting_audio(self, audio_chunk: np.ndarray):
        """
        Register meeting audio (far-end signal) that might cause echo
        
        Args:
            audio_chunk: Audio chunk from meeting (numpy array)
        """
        # Convert to float32 if needed
        if audio_chunk.dtype != np.float32:
            audio_chunk = audio_chunk.astype(np.float32)
        
        # Add to buffer
        for sample in audio_chunk:
            self.meeting_audio_buffer.append(sample)
    
    def cancel_echo(self, agent_audio: np.ndarray) -> np.ndarray:
        """
        Cancel echo from agent audio (near-end signal)
        
        Args:
            agent_audio: Audio from agent's microphone (may contain echo)
        
        Returns:
            Echo-cancelled audio
        """
        # Convert to float32 if needed
        if agent_audio.dtype != np.float32:
            agent_audio = agent_audio.astype(np.float32)
        
        # If no meeting audio, return as-is
        if len(self.meeting_audio_buffer) < self.filter_length:
            return agent_audio
        
        # Convert buffer to numpy array
        meeting_audio = np.array(list(self.meeting_audio_buffer))
        
        # Estimate echo using adaptive filter
        echo_estimate = self._estimate_echo(meeting_audio)
        
        # Subtract echo from agent audio
        cancelled_audio = agent_audio - echo_estimate[:len(agent_audio)]
        
        # Clip to prevent overflow
        cancelled_audio = np.clip(cancelled_audio, -1.0, 1.0)
        
        return cancelled_audio
    
    def _estimate_echo(self, meeting_audio: np.ndarray) -> np.ndarray:
        """
        Estimate echo using simplified LMS adaptive filter
        
        Args:
            meeting_audio: Meeting audio buffer
        
        Returns:
            Echo estimate
        """
        # Simplified LMS algorithm
        # In production, use proper AEC library like speexdsp or WebRTC AEC
        
        # Get recent meeting audio
        recent_audio = meeting_audio[-self.filter_length:]
        
        # Compute echo estimate (convolution)
        echo_estimate = np.convolve(recent_audio, self.filter_coeffs, mode='valid')
        
        # Pad to match length
        if len(echo_estimate) < len(meeting_audio):
            echo_estimate = np.pad(echo_estimate, (0, len(meeting_audio) - len(echo_estimate)))
        
        return echo_estimate
    
    def update_filter(self, error_signal: np.ndarray, reference_signal: np.ndarray):
        """
        Update adaptive filter coefficients using error signal
        
        Args:
            error_signal: Error signal (cancelled audio)
            reference_signal: Reference signal (meeting audio)
        """
        # Simplified LMS update
        # In production, use proper adaptive filter update
        
        if len(reference_signal) < self.filter_length or len(error_signal) == 0:
            return
        
        # Get recent reference
        recent_ref = reference_signal[-self.filter_length:]
        
        # Update filter coefficients
        for i in range(len(error_signal)):
            if i + self.filter_length <= len(reference_signal):
                ref_window = reference_signal[i:i + self.filter_length]
                self.filter_coeffs += self.learning_rate * error_signal[i] * ref_window
    
    def reset(self):
        """Reset echo canceller state"""
        self.meeting_audio_buffer.clear()
        self.echo_estimate_buffer.clear()
        self.filter_coeffs = np.zeros(self.filter_length)
        logger.info("Echo canceller reset")


class VoiceActivityDetector:
    """
    Simple Voice Activity Detection (VAD)
    Helps distinguish agent voice from echo
    """
    
    def __init__(self, sample_rate: int = 16000, threshold: float = 0.01):
        """
        Initialize VAD
        
        Args:
            sample_rate: Audio sample rate
            threshold: Energy threshold for voice detection
        """
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.frame_size = int(sample_rate * 0.02)  # 20ms frames
        
    def is_speech(self, audio: np.ndarray) -> bool:
        """
        Detect if audio contains speech
        
        Args:
            audio: Audio chunk
        
        Returns:
            True if speech detected
        """
        # Calculate energy
        energy = np.mean(audio ** 2)
        
        # Simple threshold-based detection
        # In production, use proper VAD like webrtcvad
        return energy > self.threshold
    
    def get_voice_segments(self, audio: np.ndarray) -> list:
        """
        Get voice segments in audio
        
        Args:
            audio: Audio chunk
        
        Returns:
            List of (start, end) indices
        """
        segments = []
        in_speech = False
        start_idx = 0
        
        for i in range(0, len(audio), self.frame_size):
            frame = audio[i:i + self.frame_size]
            if len(frame) < self.frame_size:
                break
            
            is_speech = self.is_speech(frame)
            
            if is_speech and not in_speech:
                in_speech = True
                start_idx = i
            elif not is_speech and in_speech:
                in_speech = False
                segments.append((start_idx, i))
        
        return segments


class AudioRouterWithAEC:
    """
    Audio Router with Echo Cancellation
    Routes audio with echo cancellation to prevent feedback loops
    """
    
    def __init__(self, sample_rate: int = 16000):
        """
        Initialize audio router with AEC
        
        Args:
            sample_rate: Audio sample rate
        """
        self.sample_rate = sample_rate
        self.echo_canceller = EchoCanceller(sample_rate)
        self.vad = VoiceActivityDetector(sample_rate)
        
        # State tracking
        self.agent_speaking = False
        self.meeting_audio_level = 0.0
        
        logger.info("Audio router with AEC initialized")
    
    def process_agent_audio(self, agent_audio: np.ndarray, meeting_audio: np.ndarray) -> np.ndarray:
        """
        Process agent audio with echo cancellation
        
        Args:
            agent_audio: Audio from agent microphone
            meeting_audio: Audio from meeting (Teams output)
        
        Returns:
            Echo-cancelled agent audio
        """
        # Register meeting audio
        self.echo_canceller.register_meeting_audio(meeting_audio)
        
        # Cancel echo from agent audio
        cancelled_audio = self.echo_canceller.cancel_echo(agent_audio)
        
        # Update filter with error signal
        self.echo_canceller.update_filter(cancelled_audio, meeting_audio)
        
        # Detect if agent is speaking
        self.agent_speaking = self.vad.is_speech(cancelled_audio)
        
        # Calculate meeting audio level
        self.meeting_audio_level = np.mean(np.abs(meeting_audio))
        
        return cancelled_audio
    
    def should_transcribe(self, audio: np.ndarray) -> bool:
        """
        Determine if audio should be transcribed
        Only transcribe if agent is speaking (not echo)
        
        Args:
            audio: Audio chunk
        
        Returns:
            True if should transcribe
        """
        is_speech = self.vad.is_speech(audio)
        
        # Only transcribe if speech detected and agent is speaking
        # This prevents transcribing echo or meeting audio
        return is_speech and self.agent_speaking
    
    def get_status(self) -> dict:
        """
        Get AEC status
        
        Returns:
            Status dictionary
        """
        return {
            "agent_speaking": self.agent_speaking,
            "meeting_audio_level": self.meeting_audio_level,
            "buffer_size": self.echo_canceller.buffer_size,
            "filter_length": self.echo_canceller.filter_length
        }


def main():
    """Test echo canceller"""
    from loguru import logger
    
    logger.add("logs/echo_canceller_{time}.log", rotation="10 MB")
    
    # Create echo canceller
    aec = EchoCanceller(sample_rate=16000, buffer_size=5)
    
    # Simulate meeting audio
    meeting_audio = np.random.randn(16000 * 2).astype(np.float32) * 0.1
    
    # Simulate agent audio with echo
    agent_audio = np.random.randn(16000).astype(np.float32) * 0.05 + meeting_audio[:16000] * 0.5
    
    # Cancel echo
    cancelled_audio = aec.cancel_echo(agent_audio)
    
    logger.info(f"Original energy: {np.mean(agent_audio ** 2):.6f}")
    logger.info(f"Cancelled energy: {np.mean(cancelled_audio ** 2):.6f}")
    logger.info(f"Echo reduction: {(1 - np.mean(cancelled_audio ** 2) / np.mean(agent_audio ** 2)) * 100:.2f}%")
    
    logger.info("Echo canceller test complete")


if __name__ == "__main__":
    main()
