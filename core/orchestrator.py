#!/usr/bin/env python3
"""
Project Anton Egon - Phase 3: Core Orchestrator
Async event loop for coordinating all agent components
"""

import asyncio
import signal
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

# Import Phase 2 components
import sys
sys.path.append(str(Path(__file__).parent.parent))

from audio.listener import AudioListener
from vision.detector import VisionDetector
from vision.name_reader import NameReader
from core.status_manager import StatusManager, get_status_manager

# Phase 3 components
from core.decision_engine import DecisionEngine, DecisionConfig
from core.prompts import PromptsManager
from core.action_scheduler import ActionScheduler, ActionConfig
from memory.context_buffer import ContextBuffer, ContextConfig

# Phase 4 components
from video.wardrobe_manager import WardrobeManager
from video.animator import VideoAnimator
from audio.synthesizer import AudioSynthesizer
from video.obs_bridge import OBSBridge
from audio.audio_router import AudioRouter

# Phase 5 components
from integration.obs_connector import OBSConnector
from integration.panic_logic import PanicLogic
from ui.dashboard import Dashboard, DashboardConfig
from integration.post_meeting import PostMeetingAutomation
from core.calendar_sync import CalendarSync, CalendarConfig

# Phase 6 components
from memory.people_manager import PeopleManager, PeopleManagerConfig
from memory.shadow_logger import ShadowLogger, ShadowLoggerConfig
from memory.consent_manager import ConsentManager, ConsentManagerConfig
from memory.entity_extractor import EntityExtractor, EntityExtractorConfig
from memory.temporal_graph import TemporalGraph, TemporalGraphConfig
from memory.crm_connector import CRMConnector, CRMConnectorConfig

# Phase 7 components
from core.thermal_guard import ThermalGuard, ThermalGuardConfig
from integration.whisperer import Whisperer, WhispererConfig
from integration.web_search import WebSearch, WebSearchConfig
from core.interrupt_handler import InterruptHandler, InterruptHandlerConfig

# Phase 8 components
from core.speculative_ingest import SpeculativeIngest, SpeculativeIngestConfig
from core.streaming_pipeline import StreamingPipeline, StreamingPipelineConfig
from audio.pre_roll import AudioPreRoll, AudioPreRollConfig

# Phase 9 components
from core.fact_verifier import HardFactVerifier, FactVerifierConfig
from integration.active_steering import ActiveSteering, ActiveSteeringConfig

# Phase 11 components
from core.live_context import LiveContextManager, LiveContextConfig
from vision.ui_detector import UIDetector, UIDetectorConfig
from vision.engagement_analyzer import EngagementAnalyzer, EngagementConfig
from core.facilitator_logic import FacilitatorLogic, FacilitatorConfig
from video.slide_master import SlideMaster, SlideMasterConfig

# Configuration
MEMORY_DIR = Path("memory")
CONFIG_DIR = Path("config")


class AgentState(Enum):
    """Agent operational states"""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    GENERATING = "generating"
    ANIMATING = "animating"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class OrchestratorConfig(BaseModel):
    """Configuration for the orchestrator"""
    loop_interval: float = Field(default=0.1, description="Main loop interval in seconds")
    enable_audio: bool = Field(default=True, description="Enable audio processing")
    enable_vision: bool = Field(default=True, description="Enable vision processing")
    enable_emotion: bool = Field(default=True, description="Enable emotion analysis")
    enable_rag: bool = Field(default=True, description="Enable RAG retrieval")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Phase 2 specific settings
    audio_model: str = Field(default="large-v3-turbo", description="Whisper model size")
    vision_fps: float = Field(default=1.5, description="Vision detection FPS")
    ocr_fps: float = Field(default=0.5, description="OCR name reading FPS")
    teams_window: Optional[str] = Field(default="Microsoft Teams", description="Teams window title")
    
    # Phase 3 specific settings
    enable_decision_engine: bool = Field(default=True, description="Enable decision engine")
    enable_prompts_manager: bool = Field(default=True, description="Enable prompts manager")
    enable_action_scheduler: bool = Field(default=True, description="Enable action scheduler")
    enable_context_buffer: bool = Field(default=True, description="Enable context buffer")
    meeting_agenda_path: str = Field(default="memory/meeting/meeting_agenda.md", description="Meeting agenda path")
    previous_notes_path: str = Field(default="memory/meeting/previous_notes.txt", description="Previous notes path")
    
    # Phase 4 specific settings
    enable_wardrobe: bool = Field(default=False, description="Enable wardrobe manager")
    enable_animator: bool = Field(default=False, description="Enable video animator")
    enable_synthesizer: bool = Field(default=False, description="Enable audio synthesizer")
    enable_obs_bridge: bool = Field(default=False, description="Enable OBS bridge")
    enable_audio_router: bool = Field(default=False, description="Enable audio router")
    target_fps: int = Field(default=20, description="Target FPS for video output")
    
    # Phase 5 specific settings
    enable_obs_connector: bool = Field(default=False, description="Enable OBS A/V sync connector")
    enable_panic_logic: bool = Field(default=False, description="Enable panic hotkeys")
    enable_dashboard: bool = Field(default=False, description="Enable monitoring dashboard")
    enable_post_meeting: bool = Field(default=False, description="Enable post-meeting automation")
    
    # Phase 6 specific settings
    enable_people_crm: bool = Field(default=False, description="Enable People CRM")
    enable_shadow_logger: bool = Field(default=False, description="Enable Shadow Logger")
    enable_consent_manager: bool = Field(default=False, description="Enable Consent Manager")
    enable_entity_extractor: bool = Field(default=False, description="Enable Entity Extractor")
    enable_temporal_graph: bool = Field(default=False, description="Enable Temporal Graph")
    enable_crm_connector: bool = Field(default=False, description="Enable CRM Connector")
    
    # Phase 7 specific settings
    enable_thermal_guard: bool = Field(default=False, description="Enable Thermal Guard")
    enable_whisperer: bool = Field(default=False, description="Enable The Whisperer")
    enable_web_search: bool = Field(default=False, description="Enable Web Search")
    enable_interrupt_handler: bool = Field(default=False, description="Enable Interrupt Handler")
    
    # Phase 8 specific settings
    enable_speculative_ingest: bool = Field(default=False, description="Enable Speculative Ingest")
    enable_streaming_pipeline: bool = Field(default=False, description="Enable Streaming Pipeline")
    enable_audio_preroll: bool = Field(default=False, description="Enable Audio Pre-roll")
    
    # Phase 9 specific settings
    enable_fact_verifier: bool = Field(default=False, description="Enable Hard Fact Verifier")
    enable_active_steering: bool = Field(default=False, description="Enable Active Steering")
    
    # Phase 11 specific settings
    enable_live_context: bool = Field(default=False, description="Enable Live Context (Active RAG)")
    enable_ui_detector: bool = Field(default=False, description="Enable UI Detector (hand-raise)")
    enable_engagement_analyzer: bool = Field(default=False, description="Enable Engagement Analyzer")
    enable_facilitator: bool = Field(default=False, description="Enable Facilitator Logic")
    enable_slide_master: bool = Field(default=False, description="Enable Slide Master (presentation navigation)")


class Orchestrator:
    """
    Main orchestrator for Project Anton Egon
    Coordinates all components in an async event loop
    """
    
    def __init__(self, config: OrchestratorConfig):
        """Initialize the orchestrator"""
        self.config = config
        self.state = AgentState.IDLE
        self.running = False
        self._shutdown_event = asyncio.Event()
        
        # Phase 2 components
        self.audio_listener: Optional[AudioListener] = None
        self.vision_detector: Optional[VisionDetector] = None
        self.name_reader: Optional[NameReader] = None
        self.status_manager: Optional[StatusManager] = None
        
        # Phase 3 components
        self.decision_engine: Optional[DecisionEngine] = None
        self.prompts_manager: Optional[PromptsManager] = None
        self.action_scheduler: Optional[ActionScheduler] = None
        self.context_buffer: Optional[ContextBuffer] = None
        
        # Phase 4 components
        self.wardrobe_manager = None
        self.video_animator = None
        self.audio_synthesizer = None
        self.audio_router = None
        self.obs_bridge = None
        
        # Phase 5 components
        self.obs_connector = None
        self.panic_logic = None
        self.dashboard = None
        self.post_meeting = None
        self.calendar_sync = None
        
        # Phase 6 components
        self.people_manager = None
        self.shadow_logger = None
        self.consent_manager = None
        self.entity_extractor = None
        self.temporal_graph = None
        self.crm_connector = None
        
        # Phase 7 components
        self.thermal_guard = None
        self.whisperer = None
        self.web_search = None
        self.interrupt_handler = None
        
        # Phase 8 components
        self.speculative_ingest = None
        self.streaming_pipeline = None
        self.audio_preroll = None
        
        # Phase 9 components
        self.fact_verifier = None
        self.active_steering = None
        
        # Phase 2: Vision Detector
        if self.config.enable_vision:
            try:
                self.vision_detector = VisionDetector(
                    target_fps=self.config.vision_fps,
                    on_detection=self._on_detection,
                    window_title=self.config.teams_window
                )
                logger.info("Vision detector initialized")
            except Exception as e:
                logger.error(f"Failed to initialize vision detector: {e}")
        
        # Phase 2: Name Reader (OCR)
        if self.config.enable_vision:
            try:
                self.name_reader = NameReader(
                    target_fps=self.config.ocr_fps,
                    on_name_detected=self._on_name_detected,
                    window_title=self.config.teams_window
                )
                logger.info("Name reader initialized")
            except Exception as e:
                logger.error(f"Failed to initialize name reader: {e}")
        
        # Phase 3: Decision Engine
        if self.config.enable_decision_engine:
            try:
                decision_config = DecisionConfig()
                self.decision_engine = DecisionEngine(decision_config)
                # Load meeting context
                self.decision_engine.load_meeting_context(
                    self.config.meeting_agenda_path,
                    self.config.previous_notes_path
                )
                logger.info("Decision engine initialized")
            except Exception as e:
                logger.error(f"Failed to initialize decision engine: {e}")
        
        # Phase 3: Prompts Manager
        if self.config.enable_prompts_manager:
            try:
                self.prompts_manager = PromptsManager()
                logger.info("Prompts manager initialized")
            except Exception as e:
                logger.error(f"Failed to initialize prompts manager: {e}")
        
        # Phase 3: Action Scheduler
        if self.config.enable_action_scheduler:
            try:
                action_config = ActionConfig()
                self.action_scheduler = ActionScheduler(action_config)
                logger.info("Action scheduler initialized")
            except Exception as e:
                logger.error(f"Failed to initialize action scheduler: {e}")
        
        # Phase 3: Context Buffer
        if self.config.enable_context_buffer:
            try:
                context_config = ContextConfig()
                self.context_buffer = ContextBuffer(context_config)
                logger.info("Context buffer initialized")
            except Exception as e:
                logger.error(f"Failed to initialize context buffer: {e}")
        
        # Phase 3+ components (placeholder)
        if self.config.enable_rag:
            logger.info("RAG retriever: Phase 3+ - not yet implemented")
        
        # Phase 5: Calendar Sync
        if self.config.enable_post_meeting:
            try:
                calendar_config = CalendarConfig()
                self.calendar_sync = CalendarSync(calendar_config)
                logger.info("Calendar sync initialized")
            except Exception as e:
                logger.error(f"Failed to initialize calendar sync: {e}")
        
        # Phase 6: People CRM
        if self.config.enable_people_crm:
            try:
                people_config = PeopleManagerConfig()
                self.people_manager = PeopleManager(people_config)
                logger.info("People CRM initialized")
            except Exception as e:
                logger.error(f"Failed to initialize People CRM: {e}")
        
        # Phase 6: Shadow Logger
        if self.config.enable_shadow_logger:
            try:
                shadow_config = ShadowLoggerConfig()
                self.shadow_logger = ShadowLogger(shadow_config)
                logger.info("Shadow Logger initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Shadow Logger: {e}")
        
        # Phase 6: Consent Manager
        if self.config.enable_consent_manager:
            try:
                consent_config = ConsentManagerConfig()
                self.consent_manager = ConsentManager(consent_config)
                logger.info("Consent Manager initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Consent Manager: {e}")
        
        # Phase 6: Entity Extractor
        if self.config.enable_entity_extractor:
            try:
                entity_config = EntityExtractorConfig()
                self.entity_extractor = EntityExtractor(entity_config)
                logger.info("Entity Extractor initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Entity Extractor: {e}")
        
        # Phase 6: Temporal Graph
        if self.config.enable_temporal_graph:
            try:
                temporal_config = TemporalGraphConfig()
                self.temporal_graph = TemporalGraph(temporal_config)
                logger.info("Temporal Graph initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Temporal Graph: {e}")
        
        # Phase 6: CRM Connector
        if self.config.enable_crm_connector:
            try:
                crm_config = CRMConnectorConfig()
                self.crm_connector = CRMConnector(
                    crm_config,
                    self.people_manager,
                    self.temporal_graph,
                    self.entity_extractor
                )
                logger.info("CRM Connector initialized")
            except Exception as e:
                logger.error(f"Failed to initialize CRM Connector: {e}")
        
        # Phase 7: Thermal Guard
        if self.config.enable_thermal_guard:
            try:
                thermal_config = ThermalGuardConfig()
                self.thermal_guard = ThermalGuard(thermal_config, on_thermal_event=self._on_thermal_event)
                logger.info("Thermal Guard initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Thermal Guard: {e}")
        
        # Phase 7: The Whisperer
        if self.config.enable_whisperer:
            try:
                whisper_config = WhispererConfig()
                self.whisperer = Whisperer(whisper_config, on_whisper=self._on_whisper)
                logger.info("The Whisperer initialized")
            except Exception as e:
                logger.error(f"Failed to initialize The Whisperer: {e}")
        
        # Phase 7: Web Search
        if self.config.enable_web_search:
            try:
                search_config = WebSearchConfig()
                self.web_search = WebSearch(search_config)
                logger.info("Web Search initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Web Search: {e}")
        
        # Phase 7: Interrupt Handler
        if self.config.enable_interrupt_handler:
            try:
                interrupt_config = InterruptHandlerConfig()
                self.interrupt_handler = InterruptHandler(
                    interrupt_config,
                    on_interrupt=self._on_interrupt,
                    on_resume=self._on_resume
                )
                logger.info("Interrupt Handler initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Interrupt Handler: {e}")
        
        # Phase 8: Speculative Ingest
        if self.config.enable_speculative_ingest:
            try:
                spec_config = SpeculativeIngestConfig()
                self.speculative_ingest = SpeculativeIngest(
                    spec_config,
                    on_intent_detected=self._on_intent_detected,
                    on_context_ready=self._on_context_ready
                )
                logger.info("Speculative Ingest initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Speculative Ingest: {e}")
        
        # Phase 8: Streaming Pipeline
        if self.config.enable_streaming_pipeline:
            try:
                stream_config = StreamingPipelineConfig()
                self.streaming_pipeline = StreamingPipeline(
                    stream_config,
                    on_stage_change=self._on_pipeline_stage_change,
                    on_first_audio=self._on_first_audio
                )
                logger.info("Streaming Pipeline initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Streaming Pipeline: {e}")
        
        # Phase 8: Audio Pre-roll
        if self.config.enable_audio_preroll:
            try:
                preroll_config = AudioPreRollConfig()
                self.audio_preroll = AudioPreRoll(preroll_config)
                logger.info("Audio Pre-roll initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Audio Pre-roll: {e}")
        
        # Phase 9: Hard Fact Verifier
        if self.config.enable_fact_verifier:
            try:
                fv_config = FactVerifierConfig()
                self.fact_verifier = HardFactVerifier(fv_config)
                logger.info("Hard Fact Verifier initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Fact Verifier: {e}")
        
        # Phase 9: Active Steering
        if self.config.enable_active_steering:
            try:
                steer_config = ActiveSteeringConfig()
                self.active_steering = ActiveSteering(
                    steer_config,
                    on_steering=self._on_steering_command
                )
                logger.info("Active Steering initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Active Steering: {e}")
        
        # Phase 11: Live Context (Active RAG)
        if self.config.enable_live_context:
            try:
                lc_config = LiveContextConfig()
                self.live_context = LiveContextManager(lc_config)
                logger.info("Live Context Manager initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Live Context: {e}")
        
        # Phase 11: UI Detector
        if self.config.enable_ui_detector:
            try:
                uid_config = UIDetectorConfig(platform=self.config.platform)
                self.ui_detector = UIDetector(uid_config, on_detection=self._on_ui_detection)
                logger.info("UI Detector initialized")
            except Exception as e:
                logger.error(f"Failed to initialize UI Detector: {e}")
        
        # Phase 11: Engagement Analyzer
        if self.config.enable_engagement_analyzer:
            try:
                ea_config = EngagementConfig()
                self.engagement_analyzer = EngagementAnalyzer(ea_config, on_alert=self._on_engagement_alert)
                logger.info("Engagement Analyzer initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Engagement Analyzer: {e}")
        
        # Phase 11: Facilitator Logic
        if self.config.enable_facilitator:
            try:
                fac_config = FacilitatorConfig()
                self.facilitator = FacilitatorLogic(
                    fac_config,
                    on_speak=self._on_facilitator_speak,
                    on_whisper=self._on_facilitator_whisper
                )
                logger.info("Facilitator Logic initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Facilitator: {e}")
        
        # Phase 11: Slide Master
        if self.config.enable_slide_master:
            try:
                sm_config = SlideMasterConfig()
                self.slide_master = SlideMaster(sm_config)
                logger.info("Slide Master initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Slide Master: {e}")
        
        logger.info("Orchestrator initialized successfully")
        if self.config.enable_rag:
            logger.info("RAG retriever: Phase 3+ - not yet implemented")
        
        logger.info("Orchestrator initialization complete")
    
    async def shutdown(self):
        """Gracefully shutdown all components"""
        logger.info("Shutting down orchestrator...")
        self.state = AgentState.SHUTDOWN
        self.running = False
        self._shutdown_event.set()
        
        # Stop Phase 5 components
        if self.panic_logic:
            await self.panic_logic.stop()
        
        if self.obs_connector:
            await self.obs_connector.stop()
        
        if self.dashboard:
            await self.dashboard.stop()
        
        if self.calendar_sync:
            await self.calendar_sync.stop()
        
        # Process post-meeting automation
        if self.post_meeting:
            await self.post_meeting.process_meeting_end(self.state.value)
        
        # Stop Phase 3 components
        if self.context_buffer:
            self.context_buffer.persist_to_disk()
        
        # Stop Phase 2 components
        if self.audio_listener:
            await self.audio_listener.stop()
        
        if self.vision_detector:
            await self.vision_detector.stop()
        
        if self.name_reader:
            await self.name_reader.stop()
        
        if self.status_manager:
            self.status_manager.update_agent_state(self.state.value)
        
        logger.info("Orchestrator shutdown complete")
    
    async def _audio_loop(self):
        """Audio processing loop (Phase 2)"""
        if not self.audio_listener:
            logger.warning("Audio listener not initialized, skipping audio loop")
            return
        
        try:
            await self.audio_listener.start()
            logger.info("Audio listener started")
            
            # Keep running until shutdown
            while self.running and self.config.enable_audio:
                await asyncio.sleep(1.0)
                
        except Exception as e:
            logger.error(f"Audio loop error: {e}")
            await asyncio.sleep(1)
    
    async def _vision_loop(self):
        """Vision processing loop (Phase 2)"""
        if not self.vision_detector:
            logger.warning("Vision detector not initialized, skipping vision loop")
            return
        
        try:
            await self.vision_detector.start()
            logger.info("Vision detector started")
            
            # Keep running until shutdown
            while self.running and self.config.enable_vision:
                await asyncio.sleep(1.0)
                
        except Exception as e:
            logger.error(f"Vision loop error: {e}")
            await asyncio.sleep(1)
    
    async def _emotion_loop(self):
        """Emotion analysis loop (Phase 2) - integrated into vision detector"""
        # Emotion analysis is now part of vision detector
        # This loop is kept for compatibility but does nothing
        while self.running and self.config.enable_emotion:
            try:
                await asyncio.sleep(2.0)
            except Exception as e:
                logger.error(f"Emotion loop error: {e}")
                await asyncio.sleep(1)
    
    async def _name_reading_loop(self):
        """Name reading loop (Phase 2)"""
        if not self.name_reader:
            logger.warning("Name reader not initialized, skipping name reading loop")
            return
        
        try:
            await self.name_reader.start()
            logger.info("Name reader started")
            
            # Keep running until shutdown
            while self.running and self.config.enable_vision:
                await asyncio.sleep(1.0)
        except Exception as e:
            logger.error(f"Name reading loop error: {e}")
            await asyncio.sleep(1)
    
    async def _synthesis_loop(self):
        """Audio/video synthesis loop (Phase 4)"""
        while self.running:
            try:
                # Placeholder for audio synthesis and video animation
                await asyncio.sleep(0.05)  # 20 FPS target
            except Exception as e:
                logger.error(f"Synthesis loop error: {e}")
                await asyncio.sleep(1)
    
    async def main_loop(self):
        """Main coordination loop"""
        logger.info("Starting main orchestrator loop")
        
        # Start all component loops
        tasks = []
        
        if self.config.enable_audio:
            tasks.append(asyncio.create_task(self._audio_loop(), name="audio"))
        
        if self.config.enable_vision:
            tasks.append(asyncio.create_task(self._vision_loop(), name="vision"))
        
        if self.config.enable_emotion:
            tasks.append(asyncio.create_task(self._emotion_loop(), name="emotion"))
        
        if self.config.enable_vision:
            tasks.append(asyncio.create_task(self._name_reading_loop(), name="name_reading"))

        tasks.append(asyncio.create_task(self._cognitive_loop(), name="cognitive"))
        tasks.append(asyncio.create_task(self._synthesis_loop(), name="synthesis"))
        
        # Start Phase 4 components
        if self.video_animator:
            await self.video_animator.start()
        
        if self.obs_bridge:
            await self.obs_bridge.start()
        
        if self.audio_router:
            await self.audio_router.start()
        
        # Start Phase 5 components
        if self.panic_logic:
            asyncio.create_task(self.panic_logic.start())
        
        if self.obs_connector:
            asyncio.create_task(self.obs_connector.start())
        
        if self.dashboard:
            asyncio.create_task(self.dashboard.start())
        
        if self.calendar_sync:
            asyncio.create_task(self.calendar_sync.start())
        
        # Monitor tasks
        try:
            await self._shutdown_event.wait()
            
            # Cancel all tasks
            for task in tasks:
                task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            raise
    
    async def run(self):
        """Run the orchestrator"""
        self.running = True
        self.state = AgentState.LISTENING
        
        await self.initialize()
        
        try:
            await self.main_loop()
        except asyncio.CancelledError:
            logger.info("Orchestrator cancelled")
        finally:
            await self.shutdown()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current orchestrator status"""
        return {
            "state": self.state.value,
            "running": self.running,
            "config": self.config.dict(),
            "timestamp": datetime.now().isoformat()
        }

    async def _on_transcription(self, result: Dict[str, Any]):
        """Callback for audio transcription results"""
        try:
            text = result.get("text", "")
            if text:
                logger.info(f"Transcription received: {text}")
                
                # Update status manager
                if self.status_manager:
                    self.status_manager.update_transcription(text)
                    self.status_manager.add_to_history("transcription", result)
                
                # Update context buffer
                if self.context_buffer:
                    self.context_buffer.add_transcription(text, speaker="Lasse")  # Speaker detection to be implemented
                    self.context_buffer.add_to_context({"type": "transcription", "text": text})
                
                # Update decision engine
                if self.decision_engine:
                    self.decision_engine.add_to_context({"type": "transcription", "text": text})
                
                # Check if agent's name is mentioned (trigger module)
                # This will be enhanced in Phase 3
                
        except Exception as e:
            logger.error(f"Error handling transcription: {e}")
    
    async def _on_detection(self, result: Dict[str, Any]):
        """Callback for vision detection results"""
        try:
            faces = result.get("faces", [])
            num_faces = result.get("num_faces", 0)
            
            if faces:
                logger.info(f"Detection received: {num_faces} face(s)")
                
                # Extract emotions from faces
                emotions = [face.get("emotion", "neutral") for face in faces]
                dominant_emotion = max(set(emotions), key=emotions.count) if emotions else "neutral"
                
                # Update status manager
                if self.status_manager:
                    self.status_manager.update_faces(num_faces, emotions)
                    self.status_manager.update_emotion(dominant_emotion)
                    self.status_manager.add_to_history("detection", result)
                
                # Update context buffer
                if self.context_buffer:
                    for face in faces:
                        self.context_buffer.add_emotion(
                            face.get("emotion", "neutral"),
                            face.get("emotion_confidence", 0.0)
                        )
                
                # Update decision engine
                if self.decision_engine:
                    self.decision_engine.add_to_context({"type": "emotion", "emotion": dominant_emotion})
                
        except Exception as e:
            logger.error(f"Error handling detection: {e}")
    
    async def _on_name_detected(self, result: Dict[str, Any]):
        """Callback for name reading results"""
        try:
            names = result.get("names", [])
            
            if names:
                logger.info(f"Names detected: {names}")
                
                # Update status manager
                if self.status_manager:
                    self.status_manager.update_names(names)
                    self.status_manager.add_to_history("name_detection", result)
                
                # Update context buffer
                if self.context_buffer:
                    self.context_buffer.add_name_detection(names)
                
                # Name matching logic (contextual awareness)
                # This will be enhanced in Phase 3
                if self.action_scheduler:
                    for name in names:
                        greeting = self.action_scheduler.on_meeting_start(name)
                        if greeting:
                            logger.info(f"Greeting: {greeting}")
                
        except Exception as e:
            logger.error(f"Error handling name detection: {e}")
    
    def _on_panic_freeze(self, is_frozen: bool):
        """Handle panic freeze"""
        logger.warning(f"PANIC FREEZE: {is_frozen}")
        if self.status_manager:
            self.status_manager.update_agent_state("FROZEN" if is_frozen else self.state.value)
    
    def _on_panic_shutdown(self):
        """Handle panic shutdown"""
        logger.error("PANIC SHUTDOWN TRIGGERED")
        asyncio.create_task(self.shutdown())
    
    def _on_panic_off_the_record(self, enabled: bool):
        """Handle off-the-record mode"""
        logger.warning(f"OFF-THE-RECORD: {enabled}")
        if self.decision_engine:
            self.decision_engine.toggle_off_the_record()



async def main():
    """Main entry point"""
    # Setup logging
    logger.add("logs/orchestrator_{time}.log", rotation="10 MB")
    logger.info("Starting Project Anton Egon Orchestrator")
    
    # Create configuration
    config = OrchestratorConfig(
        loop_interval=0.1,
        enable_audio=True,
        enable_vision=True,
        enable_emotion=True,
        enable_rag=True,
        log_level="INFO"
    )
    
    # Create and run orchestrator
    orchestrator = Orchestrator(config)
    
    # Setup signal handlers for graceful shutdown
    def signal_handler():
        logger.info("Shutdown signal received")
        asyncio.create_task(orchestrator.shutdown())
    
    # Note: Signal handling may need platform-specific setup
    
    try:
        await orchestrator.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        await orchestrator.shutdown()
    except Exception as e:
        logger.info(f"Orchestrator error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
