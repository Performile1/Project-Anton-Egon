#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Streaming Pipeline
Waterfall architecture: Whisper → Llama → TTS → LivePortrait running in parallel.
Each stage starts as soon as it has enough data, without waiting for the full output of the previous stage.
Target: First-byte latency < 500ms.
Phase 17-19: Groq API integration for <200ms text generation
"""

import sys
import asyncio
import os
from typing import Optional, Dict, Any, List, Callable, AsyncGenerator
from datetime import datetime, timezone
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Groq SDK for ultra-fast LLM inference
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("Groq SDK not installed. Install with: pip install groq")


class PipelineStage(Enum):
    """Pipeline stages"""
    IDLE = "idle"
    TRANSCRIBING = "transcribing"      # Whisper streaming words
    INFERRING = "inferring"            # Llama generating tokens
    SYNTHESIZING = "synthesizing"      # TTS converting first sentence
    ANIMATING = "animating"            # LivePortrait lip-syncing
    COMPLETE = "complete"


class StreamingPipelineConfig(BaseModel):
    """Configuration for Streaming Pipeline"""
    enabled: bool = Field(default=True, description="Enable streaming pipeline")
    min_words_for_inference: int = Field(default=5, description="Min transcription words before starting LLM")
    sentence_boundary_chars: str = Field(default=".!?,;:", description="Characters that mark sentence boundaries")
    max_concurrent_tts: int = Field(default=2, description="Max concurrent TTS generations")
    first_byte_target_ms: int = Field(default=500, description="Target first-byte latency (ms)")
    enable_speculative_decoding: bool = Field(default=True, description="Enable draft model for speculative decoding")
    # Phase 17-19: Groq configuration
    use_groq: bool = Field(default=False, description="Use Groq API for ultra-fast inference")
    groq_model: str = Field(default="llama-3.1-70b-versatile", description="Groq model to use")
    groq_api_key: Optional[str] = Field(default=None, description="Groq API key")
    enable_jargon_injection: bool = Field(default=False, description="Enable Jargon Injection middleware")


class PipelineMetrics(BaseModel):
    """Pipeline performance metrics"""
    transcription_start: Optional[str] = None
    inference_start: Optional[str] = None
    first_token_time: Optional[str] = None
    tts_start: Optional[str] = None
    first_audio_time: Optional[str] = None
    animation_start: Optional[str] = None
    total_latency_ms: float = 0.0
    first_byte_latency_ms: float = 0.0
    tokens_generated: int = 0
    sentences_synthesized: int = 0


class StreamingPipeline:
    """
    Streaming Pipeline - Waterfall Architecture
    
    Flow:
    1. Whisper streams words → feeds Speculative Ingest
    2. After enough context, Llama starts generating tokens
    3. As soon as first sentence is complete, TTS starts
    4. As soon as first audio chunk is ready, LivePortrait starts lip-sync
    
    All stages run concurrently via asyncio.
    Phase 17-19: Groq API integration for <200ms text generation
    """
    
    def __init__(
        self,
        config: StreamingPipelineConfig,
        on_stage_change: Optional[Callable] = None,
        on_first_audio: Optional[Callable] = None,
    ):
        """
        Initialize Streaming Pipeline
        
        Args:
            config: Pipeline configuration
            on_stage_change: Callback when pipeline stage changes
            on_first_audio: Callback when first audio byte is ready
        """
        self.config = config
        self.on_stage_change = on_stage_change
        self.on_first_audio = on_first_audio
        
        # State
        self.current_stage = PipelineStage.IDLE
        self.is_running = False
        self.metrics = PipelineMetrics()
        
        # Queues for inter-stage communication
        self.transcription_queue: asyncio.Queue = asyncio.Queue()
        self.token_queue: asyncio.Queue = asyncio.Queue()
        self.sentence_queue: asyncio.Queue = asyncio.Queue()
        self.audio_queue: asyncio.Queue = asyncio.Queue()
        
        # Sentence buffer for accumulating tokens into sentences
        self._sentence_buffer: List[str] = []
        
        # Phase 17-19: Groq client
        self.groq_client = None
        if config.use_groq and GROQ_AVAILABLE:
            api_key = config.groq_api_key or os.getenv("GROQ_API_KEY")
            if api_key:
                try:
                    self.groq_client = Groq(api_key=api_key)
                    logger.info(f"Groq client initialized (model: {config.groq_model})")
                except Exception as e:
                    logger.error(f"Failed to initialize Groq client: {e}")
            else:
                logger.warning("Groq API key not provided")
        
        # Phase 17-19: Jargon Injector reference
        self.jargon_injector = None
        
        logger.info("Streaming Pipeline initialized")
    
    def _set_stage(self, stage: PipelineStage):
        """Update pipeline stage and trigger callback"""
        if stage != self.current_stage:
            prev = self.current_stage
            self.current_stage = stage
            
            if self.on_stage_change:
                self.on_stage_change({
                    "previous": prev.value,
                    "current": stage.value,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
    
    def set_jargon_injector(self, jargon_injector):
        """Set Jargon Injector for middleware (Phase 17-19)"""
        self.jargon_injector = jargon_injector
        logger.info("Jargon Injector linked to Streaming Pipeline")
    
    # ═══════════════════════════════════════════════════════════════
    # PHASE 17-19: GROQ INFERENCE
    # ═══════════════════════════════════════════════════════════════
    async def groq_inference_stream(
        self,
        prompt: str,
        context: str = "",
        system_prompt: str = "Du är Anton Egon, en professionell men personlig AI-assistent."
    ) -> AsyncGenerator[str, None]:
        """
        Stream tokens from Groq API for ultra-fast inference (<200ms)
        
        Args:
            prompt: User input prompt
            context: Additional context from knowledge vault
            system_prompt: System prompt for the LLM
        
        Yields:
            Tokens from Groq API
        """
        if not self.groq_client:
            logger.error("Groq client not initialized")
            return
        
        try:
            # Build messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{context}\n\n{prompt}"}
            ]
            
            # Call Groq API with streaming
            start_time = datetime.now(timezone.utc)
            
            stream = self.groq_client.chat.completions.create(
                model=self.config.groq_model,
                messages=messages,
                stream=True,
                max_tokens=500,
                temperature=0.7
            )
            
            first_token = True
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    
                    if first_token:
                        first_token_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
                        logger.info(f"Groq first token: {first_token_time:.0f}ms")
                        first_token = False
                    
                    # Phase 17-19: Apply Jargon Injection if enabled
                    if self.config.enable_jargon_injection and self.jargon_injector:
                        # For streaming, we inject at sentence boundaries
                        # This is a simplified approach - full streaming injection is complex
                        yield token
                    else:
                        yield token
        
        except Exception as e:
            logger.error(f"Groq inference error: {e}")
            raise
    
    async def groq_inference_complete(
        self,
        prompt: str,
        context: str = "",
        system_prompt: str = "Du är Anton Egon, en professionell men personlig AI-assistent."
    ) -> str:
        """
        Get complete response from Groq API (non-streaming)
        Used for Jargon Injection which needs full text
        
        Args:
            prompt: User input prompt
            context: Additional context from knowledge vault
            system_prompt: System prompt for the LLM
        
        Returns:
            Complete response text
        """
        if not self.groq_client:
            logger.error("Groq client not initialized")
            return ""
        
        try:
            # Build messages
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{context}\n\n{prompt}"}
            ]
            
            # Call Groq API
            start_time = datetime.now(timezone.utc)
            
            response = self.groq_client.chat.completions.create(
                model=self.config.groq_model,
                messages=messages,
                stream=False,
                max_tokens=500,
                temperature=0.7
            )
            
            latency = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            logger.info(f"Groq complete inference: {latency:.0f}ms")
            
            text = response.choices[0].message.content
            
            # Phase 17-19: Apply Jargon Injection
            if self.config.enable_jargon_injection and self.jargon_injector:
                from core.jargon_injector import jargon_injector as ji
                text = ji.inject_jargon(text)
                logger.info("Jargon Injection applied")
            
            return text
        
        except Exception as e:
            logger.error(f"Groq inference error: {e}")
            return ""
    
    async def process_utterance(
        self,
        transcription_stream: AsyncGenerator[str, None],
        llm_fn: Callable,
        tts_fn: Callable,
        animation_fn: Optional[Callable] = None,
        speculative_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a complete utterance through the streaming pipeline.
        
        Args:
            transcription_stream: Async generator yielding words from Whisper
            llm_fn: Async function(prompt, context) → AsyncGenerator[str] (token stream)
            tts_fn: Async function(text) → bytes (audio data)
            animation_fn: Optional async function(audio_bytes) → video frames
            speculative_context: Pre-fetched context from Speculative Ingest
        
        Returns:
            Pipeline metrics and results
        """
        self.is_running = True
        self.metrics = PipelineMetrics()
        self.metrics.transcription_start = datetime.now(timezone.utc).isoformat()
        
        # Stage 1: Collect transcription
        self._set_stage(PipelineStage.TRANSCRIBING)
        
        transcription_words = []
        async for word in transcription_stream:
            transcription_words.append(word)
            await self.transcription_queue.put(word)
            
            # Check if we have enough to start inference
            if len(transcription_words) >= self.config.min_words_for_inference:
                break  # Start inference with what we have
        
        # Collect remaining words in background
        remaining_task = asyncio.create_task(
            self._collect_remaining(transcription_stream, transcription_words)
        )
        
        # Stage 2: Start LLM inference
        self._set_stage(PipelineStage.INFERRING)
        self.metrics.inference_start = datetime.now(timezone.utc).isoformat()
        
        prompt = " ".join(transcription_words)
        context = speculative_context or ""
        
        # Run inference and TTS in parallel
        inference_task = asyncio.create_task(
            self._run_inference(llm_fn, prompt, context)
        )
        
        tts_task = asyncio.create_task(
            self._run_tts_pipeline(tts_fn)
        )
        
        animation_task = None
        if animation_fn:
            animation_task = asyncio.create_task(
                self._run_animation_pipeline(animation_fn)
            )
        
        # Wait for all stages
        await inference_task
        await remaining_task
        
        # Signal end of sentences
        await self.sentence_queue.put(None)
        await tts_task
        
        # Signal end of audio
        await self.audio_queue.put(None)
        if animation_task:
            await animation_task
        
        self._set_stage(PipelineStage.COMPLETE)
        
        # Calculate total latency
        if self.metrics.transcription_start and self.metrics.first_audio_time:
            start = datetime.fromisoformat(self.metrics.transcription_start)
            first_audio = datetime.fromisoformat(self.metrics.first_audio_time)
            self.metrics.first_byte_latency_ms = (first_audio - start).total_seconds() * 1000
        
        self.is_running = False
        
        return {
            "metrics": self.metrics.dict(),
            "transcription": " ".join(transcription_words),
            "stage": self.current_stage.value
        }
    
    async def _collect_remaining(self, stream: AsyncGenerator[str, None], words: List[str]):
        """Collect remaining transcription words"""
        try:
            async for word in stream:
                words.append(word)
                await self.transcription_queue.put(word)
        except Exception:
            pass  # Stream ended
    
    async def _run_inference(self, llm_fn: Callable, prompt: str, context: str):
        """
        Run LLM inference and stream tokens into sentence queue.
        Splits output at sentence boundaries for early TTS.
        """
        self._sentence_buffer = []
        
        try:
            token_stream = llm_fn(prompt, context)
            first_token = True
            
            async for token in token_stream:
                self.metrics.tokens_generated += 1
                
                if first_token:
                    self.metrics.first_token_time = datetime.now(timezone.utc).isoformat()
                    first_token = False
                
                self._sentence_buffer.append(token)
                
                # Check for sentence boundary
                if any(c in token for c in self.config.sentence_boundary_chars):
                    sentence = "".join(self._sentence_buffer).strip()
                    if sentence:
                        await self.sentence_queue.put(sentence)
                        self.metrics.sentences_synthesized += 1
                        self._sentence_buffer = []
            
            # Flush remaining buffer
            if self._sentence_buffer:
                sentence = "".join(self._sentence_buffer).strip()
                if sentence:
                    await self.sentence_queue.put(sentence)
                    self.metrics.sentences_synthesized += 1
        
        except Exception as e:
            logger.error(f"Inference error: {e}")
    
    async def _run_tts_pipeline(self, tts_fn: Callable):
        """
        TTS pipeline: reads sentences from queue, generates audio.
        Starts as soon as first sentence is available.
        """
        first_audio = True
        
        while True:
            sentence = await self.sentence_queue.get()
            if sentence is None:
                break
            
            self._set_stage(PipelineStage.SYNTHESIZING)
            
            if first_audio:
                self.metrics.tts_start = datetime.now(timezone.utc).isoformat()
            
            try:
                audio_bytes = await tts_fn(sentence)
                
                if audio_bytes:
                    await self.audio_queue.put(audio_bytes)
                    
                    if first_audio:
                        self.metrics.first_audio_time = datetime.now(timezone.utc).isoformat()
                        first_audio = False
                        
                        if self.on_first_audio:
                            self.on_first_audio({
                                "sentence": sentence,
                                "audio_size": len(audio_bytes),
                                "timestamp": self.metrics.first_audio_time
                            })
            
            except Exception as e:
                logger.error(f"TTS error: {e}")
    
    async def _run_animation_pipeline(self, animation_fn: Callable):
        """
        Animation pipeline: reads audio from queue, generates lip-sync video.
        Starts as soon as first audio chunk is available.
        """
        while True:
            audio_bytes = await self.audio_queue.get()
            if audio_bytes is None:
                break
            
            self._set_stage(PipelineStage.ANIMATING)
            
            if self.metrics.animation_start is None:
                self.metrics.animation_start = datetime.now(timezone.utc).isoformat()
            
            try:
                await animation_fn(audio_bytes)
            except Exception as e:
                logger.error(f"Animation error: {e}")
    
    def abort(self):
        """Abort the current pipeline (e.g., on interruption)"""
        self.is_running = False
        self._set_stage(PipelineStage.IDLE)
        logger.info("Pipeline aborted")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get pipeline status
        
        Returns:
            Status dictionary
        """
        return {
            "stage": self.current_stage.value,
            "is_running": self.is_running,
            "metrics": self.metrics.dict() if self.metrics else None,
            "first_byte_target_ms": self.config.first_byte_target_ms,
            "speculative_decoding": self.config.enable_speculative_decoding
        }


async def main():
    """Test the Streaming Pipeline"""
    from loguru import logger
    
    logger.add("logs/streaming_pipeline_{time}.log", rotation="10 MB")
    
    # Mock streaming transcription
    async def mock_transcription():
        words = "Vad har vi för budget för nästa kvartal?".split()
        for word in words:
            await asyncio.sleep(0.1)  # Simulate Whisper streaming
            yield word
    
    # Mock LLM inference (token by token)
    async def mock_llm(prompt, context):
        response = "Baserat på vår senaste analys ligger budgeten på 2,5 miljoner. Vi har allokerat 40% till utveckling."
        tokens = list(response)
        for token in tokens:
            await asyncio.sleep(0.02)  # Simulate token generation
            yield token
    
    # Mock TTS
    async def mock_tts(text):
        await asyncio.sleep(0.1)  # Simulate TTS
        return b"fake_audio_bytes"
    
    def on_stage_change(data):
        logger.info(f"Stage: {data['previous']} → {data['current']}")
    
    def on_first_audio(data):
        logger.info(f"🔊 First audio ready! Sentence: '{data['sentence']}'")
    
    # Create pipeline
    config = StreamingPipelineConfig()
    pipeline = StreamingPipeline(config, on_stage_change=on_stage_change, on_first_audio=on_first_audio)
    
    # Run pipeline
    result = await pipeline.process_utterance(
        transcription_stream=mock_transcription(),
        llm_fn=mock_llm,
        tts_fn=mock_tts,
        speculative_context="Budget Q3: 2.5M SEK"
    )
    
    logger.info(f"Pipeline result: {result['metrics']}")
    logger.info(f"First-byte latency: {result['metrics']['first_byte_latency_ms']:.0f}ms")
    
    # Get status
    status = pipeline.get_status()
    logger.info(f"Pipeline status: {status}")
    
    logger.info("Streaming Pipeline test complete")


if __name__ == "__main__":
    asyncio.run(main())
