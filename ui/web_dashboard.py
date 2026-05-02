#!/usr/bin/env python3
"""
Project Anton Egon - Web Dashboard UI
Modern web-based dashboard for monitoring agent status
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum

from fastapi import FastAPI, Request, Response, Form, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from core.unified_inbox import unified_inbox
from ui.phrase_library_editor import phrase_library
from core.prop_engine import prop_engine
from core.overlay_engine import overlay_engine
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from loguru import logger

from ui.studio import Studio, StudioConfig, create_studio_router, studio_recording_websocket


class AgentStatus(BaseModel):
    """Agent status model"""
    state: str
    active_speaker: str
    emotion: str
    last_keyword: str
    names: List[str]
    platform: str
    timestamp: str


class WebDashboard:
    """
    Web-based dashboard UI for Anton Egon
    Real-time monitoring via WebSocket
    """
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        """
        Initialize web dashboard
        
        Args:
            host: Host to bind to
            port: Port to bind to
        """
        self.host = host
        self.port = port
        self.app = FastAPI(title="Anton Egon Dashboard")
        self.websocket_clients: List[WebSocket] = []
        
        # Data
        self.status_data: Dict[str, Any] = {}
        self.logs: List[Dict[str, Any]] = []
        self.emotions: Dict[str, str] = {}
        self.daily_agenda: List[Dict[str, Any]] = []
        
        # Prompts
        self.positive_prompts: List[str] = []
        self.negative_prompts: List[str] = []
        
        # Studio & Harvester
        self.studio = Studio(StudioConfig())
        
        self._setup_routes()
        
        # Mount Studio API router
        studio_router = create_studio_router(self.studio)
        self.app.include_router(studio_router)
        
        logger.info(f"Web dashboard initialized (http://{host}:{port})")
    
    def _setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def get_dashboard():
            """Serve dashboard HTML"""
            return self._get_html_template()
        
        @self.app.post("/api/clip")
        async def record_clip(
            clip_type: str = Form(...),
            emotion: str = Form(...),
            duration: int = Form(default=5)
        ):
            """Record new clip (placeholder - needs actual recording implementation)"""
            # This would integrate with actual recording hardware
            # For now, return success
            logger.info(f"Clip recording requested: {clip_type}, emotion: {emotion}, duration: {duration}s")
            return {"status": "success", "message": "Recording initiated (placeholder)"}
        
        @self.app.post("/api/animation-mode")
        async def switch_animation_mode(mode: str = Form(...)):
            """Switch animation mode"""
            try:
                # This would integrate with the animator to switch mode
                logger.info(f"Animation mode switch requested: {mode}")
                return {"status": "success", "mode": mode}
            except Exception as e:
                logger.error(f"Error switching animation mode: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})

        @self.app.post("/api/render-engine")
        async def set_render_engine(request: Request):
            """Set render engine (Stitcher Mode vs Generative Mode)"""
            try:
                from video.animator_selector import AnimatorSelector, RenderEngine

                data = await request.json()
                engine_str = data.get("engine", "stitcher")

                engine_map = {
                    "stitcher": RenderEngine.STITCHER,
                    "generative": RenderEngine.GENERATIVE
                }

                engine = engine_map.get(engine_str, RenderEngine.STITCHER)

                # Create selector and switch engine
                selector = AnimatorSelector()
                selector.switch_engine(engine)

                logger.info(f"Render engine set to {engine.value}")
                return {"success": True, "engine": engine.value}
            except Exception as e:
                logger.error(f"Error setting render engine: {e}")
                return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

        @self.app.post("/api/settings/save")
        async def save_settings(request: Request):
            """Save API settings to .env file"""
            try:
                from pathlib import Path

                data = await request.json()

                env_path = Path(".env")
                env_content = []

                # Read existing .env file
                if env_path.exists():
                    with open(env_path, 'r') as f:
                        env_content = f.readlines()

                # Create a dict of existing values
                env_dict = {}
                for line in env_content:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.split('=', 1)
                        env_dict[key.strip()] = value.strip()

                # Update with new values
                if data.get('supabase_url'):
                    env_dict['SUPABASE_URL'] = data['supabase_url']
                if data.get('supabase_key'):
                    env_dict['SUPABASE_SERVICE_ROLE_KEY'] = data['supabase_key']
                if data.get('openai_key'):
                    env_dict['OPENAI_API_KEY'] = data['openai_key']
                if data.get('groq_key'):
                    env_dict['GROQ_API_KEY'] = data['groq_key']

                # Write back to .env
                with open(env_path, 'w') as f:
                    for key, value in env_dict.items():
                        f.write(f"{key}={value}\n")

                logger.info("API settings saved to .env file")
                return {"success": True}
            except Exception as e:
                logger.error(f"Failed to save settings: {e}")
                return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

        @self.app.get("/api/settings/load")
        async def load_settings():
            """Load API settings from .env file"""
            try:
                from pathlib import Path
                from dotenv import load_dotenv

                env_path = Path(".env")

                if not env_path.exists():
                    return {"success": True, "settings": {}}

                # Load .env file
                load_dotenv(env_path)

                import os
                settings = {
                    "supabase_url": os.getenv('SUPABASE_URL', ''),
                    "supabase_key": os.getenv('SUPABASE_SERVICE_ROLE_KEY', ''),
                    "openai_key": os.getenv('OPENAI_API_KEY', ''),
                    "groq_key": os.getenv('GROQ_API_KEY', '')
                }

                return {"success": True, "settings": settings}
            except Exception as e:
                logger.error(f"Failed to load settings: {e}")
                return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
        
        @self.app.get("/api/status")
        async def get_status():
            """Get current agent status"""
            return self.status_data
        
        @self.app.get("/api/logs")
        async def get_logs():
            """Get recent logs"""
            return self.logs[-50:]
        
        @self.app.get("/api/emotions")
        async def get_emotions():
            """Get emotion data"""
            return self.emotions
        
        @self.app.get("/api/agenda")
        async def get_agenda():
            """Get daily agenda"""
            return self.agenda
        
        @self.app.get("/api/inbox/stats")
        async def get_inbox_stats():
            """Get inbox statistics"""
            return unified_inbox.get_stats()
        
        @self.app.get("/api/inbox/messages")
        async def get_inbox_messages(filter: str = "all", limit: int = 50, offset: int = 0):
            """Get messages from inbox"""
            from core.unified_inbox import InboxFilter
            filter_map = {
                "all": InboxFilter.ALL,
                "unread": InboxFilter.UNREAD,
                "drafts": InboxFilter.DRAFTS,
                "teams": InboxFilter.TEAMS,
                "slack": InboxFilter.SLACK,
                "email": InboxFilter.EMAIL,
                "high_priority": InboxFilter.HIGH_PRIORITY
            }
            inbox_filter = filter_map.get(filter, InboxFilter.ALL)
            return unified_inbox.get_messages(inbox_filter, limit, offset)
        
        @self.app.post("/api/inbox/messages/{message_id}/read")
        async def mark_message_read(message_id: str):
            """Mark message as read"""
            success = unified_inbox.mark_as_read(message_id)
            return {"status": "success" if success else "failed"}
        
        @self.app.post("/api/inbox/messages/{message_id}/flag")
        async def flag_message(message_id: str):
            """Flag message"""
            success = unified_inbox.flag_message(message_id)
            return {"status": "success" if success else "failed"}
        
        # ═══════════════════════════════════════════════════════════════
        # PHRASE LIBRARY API (Phase 16)
        # ═══════════════════════════════════════════════════════════════
        @self.app.get("/api/phrases/stats")
        async def get_phrase_stats():
            """Get phrase library statistics"""
            return phrase_library.get_stats()
        
        @self.app.get("/api/phrases")
        async def get_phrases(filter: str = "all"):
            """Get phrases from library"""
            if filter == "all":
                return phrase_library.get_all_phrases()
            else:
                from ui.phrase_library_editor import PhraseCategory
                category = PhraseCategory(filter)
                return [p.to_dict() for p in phrase_library.get_phrases_by_category(category)]
        
        @self.app.post("/api/phrases")
        async def add_phrase(phrase_data: Dict[str, Any]):
            """Add new phrase"""
            import uuid
            from ui.phrase_library_editor import Phrase
            phrase = Phrase(
                id=str(uuid.uuid4()),
                text=phrase_data.get("text", ""),
                category=phrase_data.get("category", "fillers"),
                trigger_mood=phrase_data.get("trigger_mood", "any"),
                frequency=phrase_data.get("frequency", 0.5),
                notes=phrase_data.get("notes", "")
            )
            success = phrase_library.add_phrase(phrase)
            return {"status": "success" if success else "failed"}
        
        @self.app.post("/api/phrases/import")
        async def import_default_phrases():
            """Import default phrases"""
            phrase_library.import_default_phrases()
            return {"status": "success"}
        
        @self.app.delete("/api/phrases/{phrase_id}")
        async def delete_phrase(phrase_id: str):
            """Delete phrase"""
            success = phrase_library.delete_phrase(phrase_id)
            return {"status": "success" if success else "failed"}
        
        # ═══════════════════════════════════════════════════════════════
        # CHAOS DASHBOARD API (Phase 16)
        # ═══════════════════════════════════════════════════════════════
        @self.app.get("/api/props")
        async def get_props():
            """Get all props"""
            prop_engine.register_default_props()
            return prop_engine.get_all_props()
        
        @self.app.post("/api/props/{prop_id}/toggle")
        async def toggle_prop(prop_id: str):
            """Toggle prop enabled state"""
            success = prop_engine.toggle_prop(prop_id)
            return {"status": "success" if success else "failed"}
        
        @self.app.post("/api/props/clear")
        async def clear_all_props():
            """Clear all active props"""
            prop_engine.clear_all_props()
            return {"status": "success"}
        
        @self.app.get("/api/overlays")
        async def get_overlays():
            """Get all overlays"""
            overlay_engine.register_default_overlays()
            return overlay_engine.get_all_overlays()
        
        @self.app.post("/api/overlays/{overlay_id}/trigger")
        async def trigger_overlay(overlay_id: str):
            """Trigger overlay"""
            success = overlay_engine.trigger_overlay(overlay_id)
            return {"status": "success" if success else "failed"}
        
        @self.app.post("/api/overlays/clear")
        async def stop_all_overlays():
            """Stop all active overlays"""
            overlay_engine.stop_all_overlays()
            return {"status": "success"}
        
        # ═══════════════════════════════════════════════════════════════
        # TURING MIRROR API (Phase 18)
        # ═══════════════════════════════════════════════════════════════
        @self.app.post("/api/turing/mode")
        async def set_mirror_mode(mode: str = Form(...)):
            """Set Turing Mirror mode"""
            try:
                from ui.studio_mirror import studio_mirror, MirrorMode
                mode_map = {
                    'side_by_side': MirrorMode.SIDE_BY_SIDE,
                    'ghost_overlay': MirrorMode.GHOST_OVERLAY,
                    'lip_sync': MirrorMode.LIP_SYNC_ANALYZER,
                    'uncanny': MirrorMode.UNCANNY_ALERT
                }
                mirror_mode = mode_map.get(mode, MirrorMode.SIDE_BY_SIDE)
                studio_mirror.set_mode(mirror_mode)
                logger.info(f"Turing Mirror mode set to {mode}")
                return {"status": "success", "mode": mode}
            except Exception as e:
                logger.error(f"Error setting mirror mode: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})
        
        @self.app.get("/api/turing/quality")
        async def get_quality_metrics():
            """Get quality metrics from Studio Mirror"""
            try:
                from ui.studio_mirror import studio_mirror
                avg_quality = studio_mirror.get_average_quality()
                return {
                    "average_quality": avg_quality,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            except Exception as e:
                logger.error(f"Error getting quality metrics: {e}")
                return {"average_quality": None, "error": str(e)}
        
        @self.app.post("/api/turing/sync-test")
        async def run_sync_test():
            """Run sync test to measure latency"""
            try:
                # Simulate sync test - in production this would send actual test signal
                import time
                start = time.time()
                
                # Simulate Groq inference latency
                await asyncio.sleep(0.15)  # 150ms simulated latency
                
                latency_ms = (time.time() - start) * 1000
                
                logger.info(f"Sync test completed: {latency_ms:.0f}ms")
                return {
                    "status": "success",
                    "latency_ms": latency_ms,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            except Exception as e:
                logger.error(f"Error running sync test: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})
        
        # ═══════════════════════════════════════════════════════════════
        # QA ENGINE API (Phase 18)
        # ═══════════════════════════════════════════════════════════════
        @self.app.get("/api/qa/report")
        async def get_qa_report():
            """Get QA report from qa_engine"""
            try:
                from core.qa_engine import qa_engine
                report = qa_engine.generate_qa_report()
                return report
            except Exception as e:
                logger.error(f"Error getting QA report: {e}")
                return {"error": str(e)}
        
        @self.app.post("/api/qa/stress-test")
        async def run_stress_test(video_path: str = "assets/video/outfits/test.mp4"):
            """Run stress test (autonomous benchmark)"""
            try:
                from core.qa_engine import qa_engine, QAMode
                qa_engine.mode = QAMode.AUTONOMOUS_BENCHMARK
                
                # Run benchmark in background
                asyncio.create_task(qa_engine.run_autonomous_benchmark(video_path))
                
                return {"status": "success", "message": "Stress test started"}
            except Exception as e:
                logger.error(f"Error starting stress test: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})
        
        @self.app.post("/api/qa/stop-test")
        async def stop_stress_test():
            """Stop stress test"""
            try:
                from core.qa_engine import qa_engine
                qa_engine.stop()
                return {"status": "success", "message": "Test stopped"}
            except Exception as e:
                logger.error(f"Error stopping stress test: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})
        
        # ═══════════════════════════════════════════════════════════════
        # SETUP WIZARD API (Phase 22)
        # ═══════════════════════════════════════════════════════════════
        @self.app.get("/api/setup/platform")
        async def detect_platform():
            """Detect platform and system information"""
            try:
                import platform
                import sys
                
                return {
                    "platform": platform.system(),
                    "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                    "os": platform.platform()
                }
            except Exception as e:
                logger.error(f"Error detecting platform: {e}")
                return JSONResponse(status_code=500, content={"error": str(e)})
        
        @self.app.post("/api/setup/test-supabase")
        async def test_supabase(url: str, key: str):
            """Test Supabase connection"""
            try:
                from supabase import create_client
                
                client = create_client(url, key)
                # Try a simple query
                response = client.table('people').select('count').execute()
                
                return {"success": True, "message": "Connection successful"}
            except Exception as e:
                logger.error(f"Supabase connection test failed: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/setup/test-groq")
        async def test_groq(key: str):
            """Test Groq API connection"""
            try:
                from groq import Groq
                
                client = Groq(api_key=key)
                # Try a simple completion
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": "Hello"}],
                    max_tokens=10
                )
                
                return {"success": True, "message": "Connection successful"}
            except Exception as e:
                logger.error(f"Groq connection test failed: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/setup/test-tailscale")
        async def test_tailscale(key: str, ip: str):
            """Test Tailscale connection (simulated)"""
            try:
                # In production, this would actually test the Tailscale connection
                # For now, we'll validate the key format
                if not key.startswith('tskey-'):
                    return {"success": False, "error": "Invalid Tailscale key format"}
                
                return {"success": True, "message": "Key format valid (actual connection test requires Tailscale daemon)"}
            except Exception as e:
                logger.error(f"Tailscale connection test failed: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/setup/save-config")
        async def save_config(config: Dict[str, str]):
            """Save configuration to .env file"""
            try:
                from pathlib import Path
                
                env_path = Path(".env")
                with open(env_path, 'w') as f:
                    for key, value in config.items():
                        f.write(f"{key}={value}\n")
                
                return {"success": True}
            except Exception as e:
                logger.error(f"Failed to save configuration: {e}")
                return {"success": False, "error": str(e)}
        
        # CALIBRATION API (Sprint 3: The Mirror)
        @self.app.post("/api/setup/calibration")
        async def apply_calibration(request: Request):
            """Apply visual calibration settings"""
            try:
                data = await request.json()
                
                # In production, this would apply calibration to the video pipeline
                logger.info(f"Applying calibration: {data}")
                
                return {"success": True, "calibration": data}
            except Exception as e:
                logger.error(f"Failed to apply calibration: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/setup/calibration/save")
        async def save_calibration_profile(request: Request):
            """Save calibration profile"""
            try:
                data = await request.json()
                
                # Save to calibration profile file
                from pathlib import Path
                calib_path = Path("config/calibration.json")
                calib_path.parent.mkdir(parents=True, exist_ok=True)
                
                import json
                with open(calib_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                logger.info(f"Saved calibration profile: {data}")
                return {"success": True}
            except Exception as e:
                logger.error(f"Failed to save calibration profile: {e}")
                return {"success": False, "error": str(e)}
        
        # ═══════════════════════════════════════════════════════════════
        # BILLING API (Fas 22: Billing Engine & Marketplace)
        # ═══════════════════════════════════════════════════════════════
        @self.app.get("/api/billing/balance")
        async def get_billing_balance():
            """Get user's credit balance"""
            try:
                from core.billing_manager import billing_manager
                if not billing_manager:
                    return {"anton_credits": 0, "gpu_credits": 0.0, "subscription_tier": "freemium"}
                
                # In production, this would get the actual user ID from auth
                user_id = "default_user"
                balance = billing_manager.get_user_balance(user_id)
                
                if balance:
                    return balance.to_dict()
                else:
                    return {"anton_credits": 0, "gpu_credits": 0.0, "subscription_tier": "freemium"}
            except Exception as e:
                logger.error(f"Failed to get billing balance: {e}")
                return {"error": str(e)}
        
        @self.app.post("/api/billing/purchase")
        async def purchase_credits(request: Request):
            """Purchase Anton Credits"""
            try:
                from core.billing_manager import billing_manager, CreditPackage
                if not billing_manager:
                    return {"success": False, "error": "Billing manager not initialized"}
                
                data = await request.json()
                package_id = data.get("package")
                
                # Map package ID to enum
                package_map = {
                    "starter": CreditPackage.STARTER,
                    "pro": CreditPackage.PRO,
                    "enterprise": CreditPackage.ENTERPRISE
                }
                
                package = package_map.get(package_id)
                if not package:
                    return {"success": False, "error": "Invalid package"}
                
                # In production, this would get the actual user ID and payment method from auth
                user_id = "default_user"
                payment_method_id = "pm_test"  # Placeholder
                
                result = await billing_manager.purchase_credits(user_id, package, payment_method_id)
                return result
            except Exception as e:
                logger.error(f"Failed to purchase credits: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/billing/subscribe")
        async def subscribe_premium(request: Request):
            """Subscribe to premium tier"""
            try:
                data = await request.json()
                tier = data.get("tier")
                feature = data.get("feature")
                
                # Placeholder for subscription logic
                # In production, this would integrate with Stripe subscriptions
                logger.info(f"Subscription request: {tier} - {feature}")
                
                return {"success": True, "message": f"Subscribed to {tier} for {feature}"}
            except Exception as e:
                logger.error(f"Failed to subscribe: {e}")
                return {"success": False, "error": str(e)}
        
        # ═══════════════════════════════════════════════════════════════
        # GHOSTWRITER API (Fas 23: Ghostwriter Mode)
        # ═══════════════════════════════════════════════════════════════
        @self.app.post("/api/ghostwriter/mode")
        async def set_ghostwriter_mode(request: Request):
            """Set Ghostwriter mode"""
            try:
                from core.ghostwriter import ghostwriter, GhostwriterMode
                if not ghostwriter:
                    return {"success": False, "error": "Ghostwriter not initialized"}
                
                data = await request.json()
                mode = data.get("mode")
                
                mode_map = {
                    "passive": GhostwriterMode.PASSIVE,
                    "assistive": GhostwriterMode.ASSISTIVE,
                    "autonomous": GhostwriterMode.AUTONOMOUS,
                    "veto_only": GhostwriterMode.VETO_ONLY
                }
                
                ghostwriter_mode = mode_map.get(mode)
                if ghostwriter_mode:
                    ghostwriter.set_mode(ghostwriter_mode)
                    return {"success": True}
                else:
                    return {"success": False, "error": "Invalid mode"}
            except Exception as e:
                logger.error(f"Failed to set Ghostwriter mode: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/ghostwriter/activate")
        async def activate_ghostwriter(request: Request):
            """Activate Ghostwriter for meeting"""
            try:
                from core.ghostwriter import ghostwriter
                if not ghostwriter:
                    return {"success": False, "error": "Ghostwriter not initialized"}
                
                import uuid
                meeting_id = str(uuid.uuid4())[:8]
                ghostwriter.activate(meeting_id)
                
                return {"success": True, "meeting_id": meeting_id}
            except Exception as e:
                logger.error(f"Failed to activate Ghostwriter: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/ghostwriter/deactivate")
        async def deactivate_ghostwriter(request: Request):
            """Deactivate Ghostwriter"""
            try:
                from core.ghostwriter import ghostwriter
                if not ghostwriter:
                    return {"success": False, "error": "Ghostwriter not initialized"}
                
                ghostwriter.deactivate()
                return {"success": True}
            except Exception as e:
                logger.error(f"Failed to deactivate Ghostwriter: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/ghostwriter/veto")
        async def veto_intervention(request: Request):
            """Veto intervention"""
            try:
                from core.ghostwriter import ghostwriter
                if not ghostwriter:
                    return {"success": False, "error": "Ghostwriter not initialized"}
                
                data = await request.json()
                intervention_id = data.get("intervention_id")
                
                success = ghostwriter.veto_intervention(intervention_id)
                return {"success": success}
            except Exception as e:
                logger.error(f"Failed to veto intervention: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/ghostwriter/approve")
        async def approve_intervention(request: Request):
            """Approve intervention"""
            try:
                from core.ghostwriter import ghostwriter
                if not ghostwriter:
                    return {"success": False, "error": "Ghostwriter not initialized"}
                
                data = await request.json()
                intervention_id = data.get("intervention_id")
                
                success = ghostwriter.approve_intervention(intervention_id)
                return {"success": success}
            except Exception as e:
                logger.error(f"Failed to approve intervention: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/ghostwriter/takeover")
        async def takeover_control(request: Request):
            """Manual takeover control"""
            try:
                from core.ghostwriter import ghostwriter, GhostwriterMode
                if not ghostwriter:
                    return {"success": False, "error": "Ghostwriter not initialized"}
                
                ghostwriter.set_mode(GhostwriterMode.PASSIVE)
                return {"success": True}
            except Exception as e:
                logger.error(f"Failed to takeover control: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.get("/api/ghostwriter/interventions")
        async def get_interventions():
            """Get pending interventions"""
            try:
                from core.ghostwriter import ghostwriter
                if not ghostwriter:
                    return {"interventions": []}
                
                interventions = [i.to_dict() for i in ghostwriter.interventions]
                return {"interventions": interventions}
            except Exception as e:
                logger.error(f"Failed to get interventions: {e}")
                return {"interventions": []}
        
        @self.app.post("/api/ghostwriter/summary")
        async def send_meeting_summary(request: Request):
            """Send meeting summary to Slack"""
            try:
                from core.ghostwriter import ghostwriter
                if not ghostwriter:
                    return {"success": False, "error": "Ghostwriter not initialized"}
                
                summary = ghostwriter.generate_summary()
                
                if ghostwriter.config.enable_slack_integration:
                    await ghostwriter.send_slack_summary(summary)
                    return {"success": True, "summary": summary}
                else:
                    return {"success": True, "summary": summary, "message": "Slack integration disabled"}
            except Exception as e:
                logger.error(f"Failed to send meeting summary: {e}")
                return {"success": False, "error": str(e)}
        
        # ═══════════════════════════════════════════════════════════════
        # TURING PORTAL API (Fas 24: Ground Truth Feedback)
        # ═══════════════════════════════════════════════════════════════
        @self.app.post("/api/turing/create-session")
        async def create_turing_session(request: Request):
            """Create new Turing test session"""
            try:
                from web.turing_portal import turing_portal
                if not turing_portal:
                    return {"success": False, "error": "Turing Portal not initialized"}
                
                session = turing_portal.create_session()
                return {"success": True, "session_id": session.session_id, "variant": session.variant.value}
            except Exception as e:
                logger.error(f"Failed to create Turing session: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/turing/submit-feedback")
        async def submit_turing_feedback(request: Request):
            """Submit Ground Truth feedback"""
            try:
                from web.turing_portal import turing_portal
                if not turing_portal:
                    return {"success": False, "error": "Turing Portal not initialized"}
                
                data = await request.json()
                session_id = data.get("session_id")
                guess = data.get("guess")
                confidence = data.get("confidence", 0.0)
                feedback = data.get("feedback", "")
                
                # Submit guess
                if guess:
                    turing_portal.submit_guess(session_id, guess, confidence)
                
                # Submit feedback
                if feedback:
                    turing_portal.submit_feedback(session_id, feedback)
                
                return {"success": True}
            except Exception as e:
                logger.error(f"Failed to submit feedback: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.get("/api/turing/availability")
        async def get_turing_availability():
            """Get current availability status"""
            try:
                from web.turing_portal import turing_portal
                if not turing_portal:
                    return {"availability": "unknown"}
                
                availability = turing_portal.get_availability()
                return {"availability": availability.value}
            except Exception as e:
                logger.error(f"Failed to get availability: {e}")
                return {"availability": "error"}
        
        @self.app.get("/api/turing/statistics")
        async def get_turing_statistics():
            """Get Turing Portal statistics"""
            try:
                from web.turing_portal import turing_portal
                if not turing_portal:
                    return {"error": "Turing Portal not initialized"}
                
                stats = turing_portal.get_statistics()
                return stats
            except Exception as e:
                logger.error(f"Failed to get statistics: {e}")
                return {"error": str(e)}
        
        # ═══════════════════════════════════════════════════════════════
        # BIOMETRICS API (Face Scan & AI Video Generation)
        # ═══════════════════════════════════════════════════════════════
        @self.app.post("/api/biometrics/scan")
        async def biometrics_scan(request: Request):
            """Start biometrics scan"""
            try:
                from core.biometrics_scanner import biometrics_scanner
                if not biometrics_scanner:
                    return {"success": False, "error": "Biometrics scanner not initialized"}
                
                data = await request.json()
                user_id = data.get("user_id", "default_user")
                
                profile = await biometrics_scanner.start_scan(user_id)
                
                return {
                    "success": True,
                    "profile_id": profile.profile_id,
                    "face_data": profile.face_data.to_dict(),
                    "outfit_data": profile.outfit_data.to_dict()
                }
            except Exception as e:
                logger.error(f"Failed to run biometrics scan: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/biometrics/generate-video")
        async def generate_ai_video(request: Request):
            """Generate AI video from prompt"""
            try:
                from core.biometrics_scanner import biometrics_scanner
                if not biometrics_scanner:
                    return {"success": False, "error": "Biometrics scanner not initialized"}
                
                data = await request.json()
                prompt = data.get("prompt")
                duration = data.get("duration", 3)
                quality = data.get("quality", "medium")
                
                # Placeholder for AI video generation
                # In production, integrate with Runway, D-ID, or similar AI video API
                import uuid
                output_file = f"assets/pranks/generated_{str(uuid.uuid4())[:8]}.mp4"
                
                logger.info(f"Generating AI video: {prompt} (duration: {duration}s, quality: {quality})")
                
                return {
                    "success": True,
                    "output_file": output_file,
                    "message": "Video generation queued (placeholder implementation)"
                }
            except Exception as e:
                logger.error(f"Failed to generate AI video: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.get("/api/biometrics/status")
        async def biometrics_status():
            """Get biometrics scanner status"""
            try:
                from core.biometrics_scanner import biometrics_scanner
                if not biometrics_scanner:
                    return {"status": "not_initialized"}
                
                return biometrics_scanner.get_status()
            except Exception as e:
                logger.error(f"Failed to get biometrics status: {e}")
                return {"error": str(e)}
        
        # ═══════════════════════════════════════════════════════════════
        # VIDEO PROVIDERS API (AI Video Generation)
        # ═══════════════════════════════════════════════════════════════
        @self.app.get("/api/video-providers/status")
        async def video_providers_status():
            """Get all video providers status"""
            try:
                from core.video_providers import video_provider_manager
                if not video_provider_manager:
                    return {"error": "Video provider manager not initialized"}
                
                return video_provider_manager.get_all_providers_status()
            except Exception as e:
                logger.error(f"Failed to get video providers status: {e}")
                return {"error": str(e)}
        
        @self.app.post("/api/video-providers/set-active")
        async def set_active_video_provider(request: Request):
            """Set active video provider"""
            try:
                from core.video_providers import video_provider_manager, VideoProvider
                if not video_provider_manager:
                    return {"success": False, "error": "Video provider manager not initialized"}
                
                data = await request.json()
                provider_id = data.get("provider")
                
                provider = VideoProvider(provider_id)
                video_provider_manager.set_active_provider(provider)
                
                config = video_provider_manager.get_provider_config(provider)
                
                return {
                    "success": True,
                    "provider_name": provider.value,
                    "credits": config.credits,
                    "price_per_second": config.price_per_second
                }
            except Exception as e:
                logger.error(f"Failed to set active provider: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/video-providers/purchase-credits")
        async def purchase_video_credits(request: Request):
            """Purchase credits for video provider"""
            try:
                from core.video_providers import video_provider_manager, VideoProvider
                if not video_provider_manager:
                    return {"success": False, "error": "Video provider manager not initialized"}
                
                data = await request.json()
                provider_id = data.get("provider")
                credits = data.get("credits")
                
                provider = VideoProvider(provider_id)
                video_provider_manager.add_credits(provider, credits)
                
                config = video_provider_manager.get_provider_config(provider)
                
                return {
                    "success": True,
                    "new_balance": config.credits
                }
            except Exception as e:
                logger.error(f"Failed to purchase credits: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/video-providers/generate")
        async def generate_video_with_provider(request: Request):
            """Generate video using selected provider"""
            try:
                from core.video_providers import video_provider_manager, VideoProvider, GenerationRequest
                if not video_provider_manager:
                    return {"success": False, "error": "Video provider manager not initialized"}
                
                data = await request.json()
                prompt = data.get("prompt")
                duration = data.get("duration", 3)
                quality = data.get("quality", "medium")
                
                provider = video_provider_manager.get_active_provider()
                if not provider:
                    return {"success": False, "error": "No active provider selected"}
                
                request_obj = GenerationRequest(
                    provider=provider,
                    prompt=prompt,
                    duration=duration,
                    quality=quality
                )
                
                response = await video_provider_manager.generate_video(request_obj)
                
                return {
                    "success": response.status == "completed",
                    "output_file": response.output_file,
                    "credits_used": response.credits_used,
                    "error": response.error
                }
            except Exception as e:
                logger.error(f"Failed to generate video: {e}")
                return {"success": False, "error": str(e)}
        
        # ═══════════════════════════════════════════════════════════════
        # HUMAN FLAWS API (Phase 23)
        # ═══════════════════════════════════════════════════════════════
        @self.app.get("/api/flaws/config")
        async def get_flaws_config():
            """Get current meeting behavior configuration"""
            try:
                # Return current configuration
                return {
                    "enabled": True,
                    "join_probability": 0.7,
                    "leave_probability": 0.3,
                    "mic_mute_probability": 0.15,
                    "camera_off_probability": 0.1,
                    "background_noise_probability": 0.05
                }
            except Exception as e:
                return {"error": str(e)}

        @self.app.post("/api/flaws/config")
        async def update_flaws_config(request: Request):
            """Update meeting behavior configuration"""
            try:
                data = await request.json()
                # Update configuration (placeholder)
                return {"success": True, "config": data}
            except Exception as e:
                return {"error": str(e)}

        @self.app.post("/api/flaws/toggle")
        async def toggle_flaws_engine(request: Request):
            """Toggle Human Flaws engine"""
            try:
                data = await request.json()
                enabled = data.get("enabled", False)
                return {"success": True, "enabled": enabled}
            except Exception as e:
                return {"error": str(e)}

        @self.app.post("/api/flaws/roll-dice")
        async def roll_flaws_dice(request: Request):
            """Roll the dice for scenario probabilities"""
            try:
                # Simulate dice roll
                return {
                    "success": True,
                    "scenarios": {
                        "join": 0.7,
                        "leave": 0.3,
                        "mic_mute": 0.15,
                        "camera_off": 0.1,
                        "background_noise": 0.05
                    }
                }
            except Exception as e:
                return {"error": str(e)}

        # INFRASTRUCTURE MANAGER API
        # ═══════════════════════════════════════════════════════════════
        @self.app.get("/api/infra/status")
        async def get_infra_status():
            """Get Infrastructure Manager status"""
            try:
                from core.infra_manager import infra_manager
                status = infra_manager.get_status()
                return status
            except Exception as e:
                return {"error": str(e)}

        @self.app.post("/api/infra/register")
        async def register_provider(request: Request):
            """Register a GPU provider"""
            try:
                from core.infra_manager import infra_manager, GPUProvider
                data = await request.json()
                
                provider_map = {
                    "runpod": GPUProvider.RUNPOD,
                    "vast_ai": GPUProvider.VAST_AI,
                    "lambda_labs": GPUProvider.LAMBDA_LABS,
                    "paperspace": GPUProvider.PAPERSPACE,
                    "modal": GPUProvider.MODAL,
                    "tensordock": GPUProvider.TENSORDOCK,
                    "google_vertex": GPUProvider.GOOGLE_VERTEX
                }
                
                provider = provider_map.get(data.get("provider"))
                if provider:
                    infra_manager.register_provider(
                        provider=provider,
                        api_key=data.get("api_key"),
                        region=data.get("region")
                    )
                    return {"success": True}
                else:
                    return {"error": "Invalid provider"}
            except Exception as e:
                return {"error": str(e)}

        @self.app.get("/api/infra/balance/{provider}")
        async def check_provider_balance(provider: str):
            """Check balance for a provider"""
            try:
                from core.infra_manager import infra_manager, GPUProvider
                
                provider_map = {
                    "runpod": GPUProvider.RUNPOD,
                    "vast_ai": GPUProvider.VAST_AI,
                    "lambda_labs": GPUProvider.LAMBDA_LABS,
                    "paperspace": GPUProvider.PAPERSPACE
                }
                
                gpu_provider = provider_map.get(provider)
                if gpu_provider:
                    balance = await infra_manager.check_balance(gpu_provider)
                    return {"balance": balance}
                else:
                    return {"error": "Invalid provider"}
            except Exception as e:
                return {"error": str(e)}

        @self.app.post("/api/infra/start")
        async def start_instance(request: Request):
            """Start a GPU instance"""
            try:
                from core.infra_manager import infra_manager, GPUProvider, GPUType
                
                data = await request.json()
                
                provider_map = {
                    "runpod": GPUProvider.RUNPOD,
                    "vast_ai": GPUProvider.VAST_AI,
                    "lambda_labs": GPUProvider.LAMBDA_LABS,
                    "paperspace": GPUProvider.PAPERSPACE
                }
                
                gpu_type_map = {
                    "rtx_4090": GPUType.RTX_4090,
                    "rtx_4080": GPUType.RTX_4080,
                    "rtx_3090": GPUType.RTX_3090,
                    "rtx_3060": GPUType.RTX_3060,
                    "a100": GPUType.A100,
                    "h100": GPUType.H100
                }
                
                provider = provider_map.get(data.get("provider"))
                gpu_type = gpu_type_map.get(data.get("gpu_type"))
                
                if provider and gpu_type:
                    instance = await infra_manager.start_instance(
                        provider=provider,
                        gpu_type=gpu_type,
                        region=data.get("region")
                    )
                    if instance:
                        return {
                            "success": True,
                            "instance_id": instance.instance_id,
                            "status": instance.status.value
                        }
                    else:
                        return {"error": "Failed to start instance"}
                else:
                    return {"error": "Invalid provider or GPU type"}
            except Exception as e:
                return {"error": str(e)}

        @self.app.post("/api/infra/stop")
        async def stop_instance(request: Request):
            """Stop a GPU instance"""
            try:
                from core.infra_manager import infra_manager
                data = await request.json()
                
                success = await infra_manager.stop_instance(data.get("instance_id"))
                return {"success": success}
            except Exception as e:
                return {"error": str(e)}

        @self.app.post("/api/infra/stop-all")
        async def stop_all_instances():
            """Stop all active instances"""
            try:
                from core.infra_manager import infra_manager
                await infra_manager.stop_all_instances()
                return {"success": True}
            except Exception as e:
                return {"error": str(e)}

        @self.app.post("/api/flaws/roll-dice")
        async def roll_join_dice():
            """Roll the Join-Dice to test a scenario"""
            try:
                from core.meeting_behavior import meeting_behavior_engine
                
                scenario = meeting_behavior_engine.roll_join_dice()
                dice_roll = random.randint(1, 6)
                
                return {
                    "success": True,
                    "dice_roll": dice_roll,
                    "scenario": scenario.value,
                    "description": meeting_behavior_engine.get_scenario_description(scenario)
                }
            except Exception as e:
                logger.error(f"Failed to roll join dice: {e}")
                return {"success": False, "error": str(e)}
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates"""
            await websocket.accept()
            self.websocket_clients.append(websocket)
            
            try:
                while True:
                    # Keep connection alive
                    await websocket.receive_text()
            except WebSocketDisconnect:
                self.websocket_clients.remove(websocket)
        
        @self.app.websocket("/ws/studio-recording")
        async def studio_recording_ws(websocket: WebSocket):
            """WebSocket for MediaRecorder binary stream"""
            await studio_recording_websocket(websocket, self.studio)
    
    def _get_html_template(self) -> str:
        """Get HTML template for dashboard with Studio & Harvester tabs"""
        return """
<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Anton Egon - Dashboard & Studio</title>
    <style>
        :root {
            --bg: #0f0f1a; --card: #16213e; --border: #0f3460;
            --accent: #4ecca3; --danger: #e94560; --warn: #ffd700;
            --text: #e0e0e0; --muted: #8892b0;
        }
        * { margin:0; padding:0; box-sizing:border-box; }
        body { font-family:'Segoe UI',system-ui,sans-serif; background:var(--bg); color:var(--text); }

        /* ── Tabs ── */
        .tab-bar { display:flex; background:#0a0a15; border-bottom:2px solid var(--border); position:sticky; top:0; z-index:100; }
        .tab-btn { padding:14px 28px; background:none; border:none; color:var(--muted); cursor:pointer;
                   font-size:1em; font-weight:600; transition:all .2s; border-bottom:3px solid transparent; }
        .tab-btn:hover { color:var(--text); background:rgba(78,204,163,.08); }
        .tab-btn.active { color:var(--accent); border-bottom-color:var(--accent); }
        .tab-content { display:none; padding:20px; max-width:1500px; margin:0 auto; }
        .tab-content.active { display:block; }

        /* ── Cards & Grid ── */
        .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; }
        .card { background:var(--card); padding:18px; border-radius:10px; border:1px solid var(--border); }
        .card h3 { color:var(--danger); margin-bottom:12px; font-size:1.05em; }
        .status-item { margin:6px 0; padding:8px 10px; background:var(--border); border-radius:4px; font-size:.9em; }
        .log-item { margin:3px 0; padding:4px; font-size:.82em; font-family:monospace; }
        .log-item.info { color:var(--accent); } .log-item.warning { color:var(--warn); } .log-item.error { color:var(--danger); }

        /* ── Studio Layout ── */
        .studio-layout { display:grid; grid-template-columns:340px 1fr 300px; gap:16px; min-height:calc(100vh - 100px); }
        @media(max-width:1100px) { .studio-layout { grid-template-columns:1fr; } }

        /* ── Teleprompter ── */
        .teleprompter { background:var(--card); border-radius:10px; padding:20px; border:1px solid var(--border); overflow-y:auto; max-height:calc(100vh - 120px); }
        .tp-sentence { padding:12px; margin:6px 0; border-radius:6px; cursor:pointer; border-left:4px solid transparent; transition:all .15s; }
        .tp-sentence:hover { background:rgba(78,204,163,.08); }
        .tp-sentence.current { background:rgba(78,204,163,.15); border-left-color:var(--accent); font-size:1.15em; }
        .tp-sentence.done { opacity:.5; text-decoration:line-through; border-left-color:var(--muted); }
        .tp-emotion-tag { display:inline-block; padding:2px 8px; border-radius:10px; font-size:.72em; font-weight:700; margin-right:6px; }
        .tp-emotion-tag.neutral { background:#334; color:#8892b0; }
        .tp-emotion-tag.enthusiastic { background:#1a3320; color:#4ecca3; }
        .tp-emotion-tag.serious { background:#331a1a; color:#e94560; }
        .tp-emotion-tag.questioning { background:#1a2833; color:#5dade2; }
        .tp-emotion-tag.empathetic { background:#33291a; color:#f0b27a; }

        /* ── Video Monitor ── */
        .monitor { position:relative; background:#000; border-radius:10px; overflow:hidden; aspect-ratio:16/9; }
        .monitor video { width:100%; height:100%; object-fit:cover; }
        .ghost-overlay { position:absolute; top:0; left:0; width:100%; height:100%; opacity:.25; pointer-events:none; object-fit:cover; }
        .rec-badge { position:absolute; top:12px; left:12px; background:var(--danger); color:#fff; padding:4px 12px; border-radius:4px;
                     font-weight:700; font-size:.85em; animation:pulse 1s infinite; display:none; }
        @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:.5;} }

        /* ── Controls ── */
        .btn { padding:10px 20px; border:none; border-radius:6px; cursor:pointer; font-weight:600; font-size:.9em; transition:all .15s; }
        .btn:hover { filter:brightness(1.15); }
        .btn-rec { background:var(--danger); color:#fff; font-size:1.1em; padding:12px 32px; }
        .btn-stop { background:#555; color:#fff; }
        .btn-accent { background:var(--accent); color:#0f0f1a; }
        .btn-outline { background:none; border:1px solid var(--border); color:var(--text); }
        .btn-outline.active { border-color:var(--accent); color:var(--accent); }
        .controls-row { display:flex; gap:10px; margin:12px 0; flex-wrap:wrap; align-items:center; }

        /* ── Audio Meter ── */
        .audio-meter { height:8px; background:#1a1a2e; border-radius:4px; overflow:hidden; margin:8px 0; }
        .audio-meter-fill { height:100%; border-radius:4px; transition:width .1s; }
        .audio-meter-fill.ok { background:var(--accent); }
        .audio-meter-fill.hot { background:var(--warn); }
        .audio-meter-fill.clip { background:var(--danger); }

        /* ── Progress bars ── */
        .progress-bar { background:#1a1a2e; border-radius:4px; overflow:hidden; height:22px; margin:6px 0; position:relative; }
        .progress-fill { height:100%; border-radius:4px; transition:width .3s; display:flex; align-items:center; padding-left:8px;
                         font-size:.75em; font-weight:600; color:#0f0f1a; }
        .progress-fill.green { background:var(--accent); }
        .progress-fill.orange { background:var(--warn); }

        /* ── Harvester ── */
        .platform-card { display:flex; align-items:center; gap:14px; padding:16px; background:var(--card);
                         border:2px solid var(--border); border-radius:10px; cursor:pointer; transition:all .2s; }
        .platform-card:hover { border-color:var(--accent); }
        .platform-card.active { border-color:var(--accent); background:rgba(78,204,163,.08); }
        .platform-icon { font-size:2em; }

        select, input[type=number] { width:100%; padding:8px; background:var(--border); border:none; color:#fff; border-radius:5px; margin-bottom:8px; }
        select:focus, input:focus { outline:2px solid var(--accent); }
    </style>
</head>
<body>

<!-- ══════ TAB BAR ══════ -->
<div class="tab-bar">
    <button class="tab-btn" onclick="switchTab('setup')" style="background:var(--accent);color:#0f0f1a;">⚙️ Setup</button>
    <button class="tab-btn active" onclick="switchTab('dashboard')">Dashboard</button>
    <button class="tab-btn" onclick="switchTab('inbox')">Unified Inbox</button>
    <button class="tab-btn" onclick="switchTab('phrases')">Phrase Library</button>
    <button class="tab-btn" onclick="switchTab('chaos')">Chaos Dashboard</button>
    <button class="tab-btn" onclick="switchTab('flaws')">Human Flaws</button>
    <button class="tab-btn" onclick="switchTab('compute')">Compute & Power</button>
    <button class="tab-btn" onclick="switchTab('store')">🛒 Anton Store</button>
    <button class="tab-btn" onclick="switchTab('shadowing')">👻 Shadowing</button>
    <button class="tab-btn" onclick="switchTab('biometrics')">🧬 Biometrics</button>
    <button class="tab-btn" onclick="switchTab('turing')">🎭 Turing Test</button>
    <button class="tab-btn" onclick="switchTab('health')">System Health</button>
    <button class="tab-btn" onclick="switchTab('studio')">The Studio</button>
    <button class="tab-btn" onclick="switchTab('harvester')">Active Harvest</button>
    <button class="tab-btn" onclick="switchTab('settings')">Settings</button>
    <button class="tab-btn" onclick="switchTab('help')">❓ Help</button>
</div>

<!-- ══════ TAB 0: SETUP WIZARD ══════ -->
<div id="tab-setup" class="tab-content">
    <div class="grid" style="max-width:1200px;margin:0 auto;">
        <div class="card" style="grid-column:1/-1;">
            <h3>⚙️ Anton Egon Setup Wizard</h3>
            <p style="color:var(--muted);margin-bottom:24px;">
                Configure external services before running Anton Egon. This wizard will guide you through setting up Supabase, Groq, Tailscale, Vercel, and RunPod.
            </p>
            
            <!-- Platform Detection -->
            <div class="card" style="margin-bottom:16px;">
                <h4>Platform Detection</h4>
                <div id="platform-info" style="margin:12px 0;">
                    <div class="status-item">Detected Platform: <span id="detected-platform">Detecting...</span></div>
                    <div class="status-item">Python Version: <span id="python-version">-</span></div>
                    <div class="status-item">Operating System: <span id="os-info">-</span></div>
                </div>
            </div>
            
            <!-- Lighting Requirements (Safety: Critical Path) -->
            <div class="card" style="margin-bottom:16px;border-left:4px solid #ffa502;">
                <h4>💡 Lighting Requirements (Critical for LivePortrait)</h4>
                <p style="color:var(--muted);font-size:.9em;margin-bottom:12px;">
                    LivePortrait hates moving shadows on your face. Follow these requirements for stable AI rendering.
                </p>
                
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:12px;">
                    <div>
                        <label style="font-size:.85em;color:var(--muted);display:block;margin-bottom:8px;">✅ Three-Point Lighting</label>
                        <div style="font-size:.85em;color:var(--muted);margin-bottom:8px;">
                            Use three-point lighting (or large ring light) to eliminate shadows on your face.
                        </div>
                        <div style="display:flex;gap:8px;">
                            <button class="btn btn-accent" onclick="confirmLightingSetup()">Confirm Setup</button>
                        </div>
                    </div>
                    <div>
                        <label style="font-size:.85em;color:var(--muted);display:block;margin-bottom:8px;">❌ No Natural Daylight</label>
                        <div style="font-size:.85em;color:var(--muted);margin-bottom:8px;">
                            NO daylight from windows. Clouds passing change color temperature, causing AI to appear to change skin color every 5 minutes.
                        </div>
                        <div id="lighting-status" style="font-size:.85em;color:var(--muted);margin-top:8px;">Status: Not confirmed</div>
                    </div>
                </div>
                
                <div style="padding:12px;background:var(--bg-dark);border-radius:8px;">
                    <div style="font-weight:bold;margin-bottom:8px;">⚠️ Why This Matters:</div>
                    <div style="font-size:.85em;color:var(--muted);">
                        <div style="margin-bottom:4px;">• Moving shadows break face tracking</div>
                        <div style="margin-bottom:4px;">• Color temperature changes cause skin tone shifts</div>
                        <div>• Consistent lighting = stable AI rendering</div>
                    </div>
                </div>
            </div>
            
            <!-- Setup Steps -->
            <div id="setup-steps">
                <!-- Visual Calibration (Sprint 3: The Mirror) -->
                <div class="card" style="margin-bottom:16px;border-left:4px solid #ff6b6b;">
                    <h4>🎭 Visual Calibration (The Mirror)</h4>
                    <p style="color:var(--muted);font-size:.9em;margin-bottom:12px;">
                        Calibrate your digital twin for perfect visual alignment. This is critical for the Turing Mirror to work flawlessly.
                    </p>
                    
                    <!-- Calibration Mode Selection -->
                    <div style="display:flex;gap:12px;margin-bottom:16px;">
                        <button class="btn btn-accent" onclick="startCalibration('sidebyside')">Side-by-Side View</button>
                        <button class="btn" onclick="startCalibration('ghost')">Ghost Overlay</button>
                        <button class="btn" onclick="startCalibration('facemesh')">Face Mesh</button>
                    </div>
                    
                    <!-- Calibration Preview -->
                    <div id="calibration-preview" style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:12px;">
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Real Camera (You)</label>
                            <div id="real-camera-preview" style="width:100%;height:300px;background:var(--bg-dark);border-radius:8px;display:flex;align-items:center;justify-content:center;color:var(--muted);">
                                Click "Start Calibration" to begin
                            </div>
                        </div>
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Digital Twin (Anton Egon)</label>
                            <div id="ai-twin-preview" style="width:100%;height:300px;background:var(--bg-dark);border-radius:8px;display:flex;align-items:center;justify-content:center;color:var(--muted);">
                                Waiting for real camera...
                            </div>
                        </div>
                    </div>
                    
                    <!-- Calibration Controls -->
                    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:12px;">
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Face Scale</label>
                            <input type="range" id="face-scale" min="0.5" max="1.5" step="0.01" value="1.0" style="width:100%;">
                        </div>
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Face Offset X</label>
                            <input type="range" id="face-offset-x" min="-100" max="100" step="1" value="0" style="width:100%;">
                        </div>
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Face Offset Y</label>
                            <input type="range" id="face-offset-y" min="-100" max="100" step="1" value="0" style="width:100%;">
                        </div>
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Ghost Opacity</label>
                            <input type="range" id="ghost-opacity" min="0" max="100" step="1" value="50" style="width:100%;">
                        </div>
                    </div>
                    
                    <div style="display:flex;gap:8px;">
                        <button class="btn btn-accent" onclick="applyCalibration()">Apply Calibration</button>
                        <button class="btn btn-outline" onclick="saveCalibrationProfile()">Save Profile</button>
                        <button class="btn" onclick="resetCalibration()">Reset</button>
                    </div>
                    <div id="calibration-status" style="margin-top:12px;font-size:.85em;color:var(--muted);"></div>
                </div>
                
                <!-- Physical Setup Guide (Sprint 5: Onboarding) -->
                <div class="card" style="margin-bottom:16px;border-left:4px solid #4ecca3;">
                    <h4>🏠 Physical Setup Guide</h4>
                    <p style="color:var(--muted);font-size:.9em;margin-bottom:12px;">
                        Follow this interactive guide to optimize your physical environment for Anton Egon.
                    </p>
                    
                    <!-- Setup Steps -->
                    <div id="setup-steps-container">
                        <div class="setup-step" data-step="1" style="margin-bottom:16px;padding:16px;background:var(--bg-dark);border-radius:8px;border-left:4px solid var(--accent);">
                            <h5 style="margin-bottom:8px;">Step 1: Camera Positioning</h5>
                            <p style="color:var(--muted);font-size:.85em;margin-bottom:12px;">
                                Position your webcam at eye level, approximately 60-90cm from your face. Ensure your face is centered and well-lit.
                            </p>
                            <div style="display:flex;gap:8px;">
                                <button class="btn btn-sm btn-accent" onclick="completeSetupStep(1)">✓ Complete</button>
                                <button class="btn btn-sm" onclick="skipSetupStep(1)">Skip</button>
                            </div>
                        </div>
                        
                        <div class="setup-step" data-step="2" style="margin-bottom:16px;padding:16px;background:var(--bg-dark);border-radius:8px;border-left:4px solid #ffd700;opacity:0.6;">
                            <h5 style="margin-bottom:8px;">Step 2: Lighting</h5>
                            <p style="color:var(--muted);font-size:.85em;margin-bottom:12px;">
                                Use soft, diffused lighting from the front. Avoid backlighting (light source behind you). Natural light from a window is ideal.
                            </p>
                            <div style="display:flex;gap:8px;">
                                <button class="btn btn-sm btn-accent" onclick="completeSetupStep(2)">✓ Complete</button>
                                <button class="btn btn-sm" onclick="skipSetupStep(2)">Skip</button>
                            </div>
                        </div>
                        
                        <div class="setup-step" data-step="3" style="margin-bottom:16px;padding:16px;background:var(--bg-dark);border-radius:8px;border-left:4px solid #ff6b6b;opacity:0.4;">
                            <h5 style="margin-bottom:8px;">Step 3: Audio Setup</h5>
                            <p style="color:var(--muted);font-size:.85em;margin-bottom:12px;">
                                Use a high-quality USB microphone positioned 20-30cm from your mouth. Test audio levels to ensure clear voice capture.
                            </p>
                            <div style="display:flex;gap:8px;">
                                <button class="btn btn-sm btn-accent" onclick="completeSetupStep(3)">✓ Complete</button>
                                <button class="btn btn-sm" onclick="skipSetupStep(3)">Skip</button>
                            </div>
                        </div>
                        
                        <div class="setup-step" data-step="4" style="margin-bottom:16px;padding:16px;background:var(--bg-dark);border-radius:8px;border-left:4px solid #0078d4;opacity:0.3;">
                            <h5 style="margin-bottom:8px;">Step 4: Background</h5>
                            <p style="color:var(--muted);font-size:.85em;margin-bottom:12px;">
                                Choose a clean, professional background. Avoid clutter or distracting elements. A solid color wall or bookshelf works well.
                            </p>
                            <div style="display:flex;gap:8px;">
                                <button class="btn btn-sm btn-accent" onclick="completeSetupStep(4)">✓ Complete</button>
                                <button class="btn btn-sm" onclick="skipSetupStep(4)">Skip</button>
                            </div>
                        </div>
                    </div>
                    
                    <div id="setup-progress" style="margin-top:16px;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                            <span style="font-size:.85em;color:var(--muted);">Setup Progress</span>
                            <span id="setup-progress-text" style="font-size:.85em;color:var(--accent);">0/4 Complete</span>
                        </div>
                        <div style="width:100%;height:8px;background:var(--border);border-radius:4px;">
                            <div id="setup-progress-bar" style="width:0%;height:100%;background:var(--accent);border-radius:4px;transition:width 0.3s;"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Step 1: Supabase -->
                <div class="card" style="margin-bottom:16px;border-left:4px solid var(--accent);">
                    <h4>Step 1: Supabase Setup</h4>
                    <p style="color:var(--muted);font-size:.9em;margin-bottom:12px;">
                        Supabase is used for persistent storage (contacts, meetings, inbox messages).
                    </p>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Supabase URL</label>
                            <input type="text" id="supabase-url" placeholder="https://your-project.supabase.co" style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                        </div>
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Service Role Key</label>
                            <input type="password" id="supabase-key" placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                        </div>
                    </div>
                    <div style="margin-bottom:12px;">
                        <label style="font-size:.85em;color:var(--muted);">Anon Key (Optional)</label>
                        <input type="password" id="supabase-anon" placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                    </div>
                    <div style="display:flex;gap:8px;">
                        <button class="btn btn-outline" onclick="testSupabaseConnection()">Test Connection</button>
                        <button class="btn btn-accent" onclick="generateSupabaseSQL()">Generate SQL Script</button>
                    </div>
                    <div id="supabase-status" style="margin-top:12px;font-size:.85em;color:var(--muted);"></div>
                </div>
                
                <!-- Step 2: Groq -->
                <div class="card" style="margin-bottom:16px;border-left:4px solid #ffd700;">
                    <h4>Step 2: Groq API</h4>
                    <p style="color:var(--muted);font-size:.9em;margin-bottom:12px;">
                        Groq provides ultra-fast LLM inference (&lt;200ms latency). Get your API key at <a href="https://console.groq.com" target="_blank" style="color:var(--accent);">console.groq.com</a>
                    </p>
                    <div style="margin-bottom:12px;">
                        <label style="font-size:.85em;color:var(--muted);">Groq API Key</label>
                        <input type="password" id="groq-key" placeholder="gsk_..." style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                    </div>
                    <button class="btn btn-outline" onclick="testGroqConnection()">Test Connection</button>
                    <div id="groq-status" style="margin-top:12px;font-size:.85em;color:var(--muted);"></div>
                </div>
                
                <!-- Step 3: Tailscale -->
                <div class="card" style="margin-bottom:16px;border-left:4px solid #4ecca3;">
                    <h4>Step 3: Tailscale VPN</h4>
                    <p style="color:var(--muted);font-size:.9em;margin-bottom:12px;">
                        Tailscale provides secure tunnel to RunPod cloud GPU. Create auth key at <a href="https://login.tailscale.com/admin/settings/keys" target="_blank" style="color:var(--accent);">Tailscale Admin</a>
                    </p>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Auth Key</label>
                            <input type="password" id="tailscale-key" placeholder="tskey-..." style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                        </div>
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Cloud Server IP (Tailscale)</label>
                            <input type="text" id="cloud-ip" placeholder="100.64.0.5" style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                        </div>
                    </div>
                    <button class="btn btn-outline" onclick="testTailscaleConnection()">Test Connection</button>
                    <div id="tailscale-status" style="margin-top:12px;font-size:.85em;color:var(--muted);"></div>
                </div>
                
                <!-- Step 4: Microsoft Calendar -->
                <div class="card" style="margin-bottom:16px;border-left:4px solid #0078d4;">
                    <h4>Step 4: Microsoft Calendar (Optional)</h4>
                    <p style="color:var(--muted);font-size:.9em;margin-bottom:12px;">
                        For Outlook calendar integration. Get credentials at <a href="https://portal.azure.com" target="_blank" style="color:var(--accent);">Azure Portal</a>
                    </p>
                    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px;">
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Client ID</label>
                            <input type="text" id="ms-client-id" placeholder="..." style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                        </div>
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Client Secret</label>
                            <input type="password" id="ms-secret" placeholder="..." style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                        </div>
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Tenant ID</label>
                            <input type="text" id="ms-tenant" placeholder="..." style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                        </div>
                    </div>
                    <div id="ms-status" style="margin-top:12px;font-size:.85em;color:var(--muted);">Skip if not using Outlook</div>
                </div>
                
                <!-- Step 5: Communication Platforms -->
                <div class="card" style="margin-bottom:16px;border-left:4px solid #5c2d91;">
                    <h4>Step 5: Communication Platforms (Optional)</h4>
                    <p style="color:var(--muted);font-size:.9em;margin-bottom:12px;">
                        Configure Slack, Email, or other platforms for Unified Inbox.
                    </p>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Slack Bot Token</label>
                            <input type="password" id="slack-token" placeholder="xoxb-..." style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                        </div>
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">SMTP Password (Email)</label>
                            <input type="password" id="smtp-password" placeholder="App password" style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                        </div>
                    </div>
                    <div id="comm-status" style="margin-top:12px;font-size:.85em;color:var(--muted);">Skip if not using these platforms</div>
                </div>
                
                <!-- Step 6: Save Configuration -->
                <div class="card" style="margin-bottom:16px;border-left:4px solid #e94560;">
                    <h4>Step 6: Save Configuration</h4>
                    <p style="color:var(--muted);font-size:.9em;margin-bottom:12px;">
                        Save all configuration to .env file. This will create/overwrite the .env file in the project root.
                    </p>
                    <div style="display:flex;gap:8px;">
                        <button class="btn btn-accent" onclick="saveConfiguration()">Save to .env</button>
                        <button class="btn btn-outline" onclick="downloadConfiguration()">Download .env</button>
                        <button class="btn btn-outline" onclick="testAllConnections()">Test All Connections</button>
                    </div>
                    <div id="save-status" style="margin-top:12px;font-size:.85em;color:var(--muted);"></div>
                </div>
            </div>
            
            <!-- SQL Script Modal -->
            <div id="sql-modal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.8);z-index:1000;align-items:center;justify-content:center;">
                <div class="card" style="max-width:800px;max-height:80vh;overflow-y:auto;">
                    <h4>Supabase SQL Script</h4>
                    <p style="color:var(--muted);font-size:.9em;margin-bottom:12px;">
                        Copy this script and run it in your Supabase SQL Editor to create the required tables.
                    </p>
                    <textarea id="sql-script" style="width:100%;height:300px;padding:12px;background:#0f0f1a;border:1px solid var(--border);color:#fff;font-family:monospace;font-size:.85em;border-radius:5px;" readonly></textarea>
                    <div style="display:flex;gap:8px;margin-top:12px;">
                        <button class="btn btn-accent" onclick="copySQLScript()">Copy to Clipboard</button>
                        <button class="btn btn-outline" onclick="closeSQLModal()">Close</button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- ══════ TAB 1: HUMAN FLAWS (Phase 23) ══════ -->
<div id="tab-flaws" class="tab-content">
    <div class="grid" style="max-width:1200px;margin:0 auto;">
        <div class="card" style="grid-column:1/-1;">
            <h3>🎭 Human Fallibility Engine</h3>
            <p style="color:var(--muted);margin-bottom:24px;">
                Configure human-like behaviors at meeting start to break the "perfect AI" pattern. 
                These scenarios simulate natural human imperfections like late joins, mute glitches, and multitasking.
            </p>
            
            <!-- Enable/Disable -->
            <div class="card" style="margin-bottom:16px;">
                <h4>Engine Status</h4>
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
                    <input type="checkbox" id="flaws-enabled" checked onchange="toggleFlawsEngine()">
                    <label for="flaws-enabled" style="font-size:.9em;">Enable Human Fallibility Engine</label>
                </div>
                <div id="flaws-status" style="font-size:.85em;color:var(--muted);">Engine is enabled</div>
            </div>
            
            <!-- Scenario Probabilities -->
            <div class="card" style="margin-bottom:16px;">
                <h4>Scenario Probabilities</h4>
                <p style="color:var(--muted);font-size:.85em;margin-bottom:12px;">
                    Adjust the probability of each scenario. Total should equal 100%.
                </p>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px;">
                    <div>
                        <label style="font-size:.85em;color:var(--muted);">Late Joiner (%)</label>
                        <input type="number" id="late-joiner-prob" value="33" min="0" max="100" style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                    </div>
                    <div>
                        <label style="font-size:.85em;color:var(--muted);">Mute Glitcher (%)</label>
                        <input type="number" id="mute-glitcher-prob" value="33" min="0" max="100" style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                    </div>
                    <div>
                        <label style="font-size:.85em;color:var(--muted);">Phone Caller (%)</label>
                        <input type="number" id="phone-caller-prob" value="34" min="0" max="100" style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                    </div>
                </div>
                <div id="prob-total" style="font-size:.85em;color:var(--muted);margin-bottom:12px;">Total: 100%</div>
                <button class="btn btn-accent" onclick="saveFlawsConfig()">Save Probabilities</button>
            </div>
            
            <!-- Scenario Details -->
            <div class="card" style="margin-bottom:16px;">
                <h4>Scenario Details</h4>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">
                    <div style="padding:12px;background:rgba(255,215,0,.1);border-radius:8px;">
                        <h5 style="margin:0 0 8px 0;font-size:.9em;">🕐 Late Joiner</h5>
                        <p style="font-size:.8em;color:var(--muted);margin:0;">
                            Join 5 minutes late with random apology from phrase library.
                        </p>
                    </div>
                    <div style="padding:12px;background:rgba(78,204,163,.1);border-radius:8px;">
                        <h5 style="margin:0 0 8px 0;font-size:.9em;">🔇 Mute Glitcher</h5>
                        <p style="font-size:.8em;color:var(--muted);margin:0;">
                            Join early, set status to "Talking" without audio. Wait for "on mute" trigger.
                        </p>
                    </div>
                    <div style="padding:12px;background:rgba(233,69,96,.1);border-radius:8px;">
                        <h5 style="margin:0 0 8px 0;font-size:.9em;">📞 Phone Caller</h5>
                        <p style="font-size:.8em;color:var(--muted);margin:0;">
                            Join early with phone call clip. Stop at meeting start with greeting.
                        </p>
                    </div>
                </div>
            </div>
            
            <!-- Timing Configuration -->
            <div class="card" style="margin-bottom:16px;">
                <h4>Timing Configuration</h4>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
                    <div>
                        <label style="font-size:.85em;color:var(--muted);">Late Join Delay (minutes)</label>
                        <input type="number" id="late-delay" value="5" min="1" max="30" style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                    </div>
                    <div>
                        <label style="font-size:.85em;color:var(--muted);">Early Join Time (minutes)</label>
                        <input type="number" id="early-join" value="3" min="1" max="10" style="width:100%;padding:8px;background:var(--border);border:none;color:#fff;border-radius:5px;">
                    </div>
                </div>
                <button class="btn btn-outline" onclick="saveFlawsConfig()">Save Timing</button>
            </div>
            
            <!-- Test Scenario -->
            <div class="card" style="margin-bottom:16px;">
                <h4>Test Scenario</h4>
                <p style="color:var(--muted);font-size:.85em;margin-bottom:12px;">
                    Roll the Join-Dice to test a random scenario (doesn't actually join a meeting).
                </p>
                <button class="btn btn-accent" onclick="rollJoinDice()">Roll Join-Dice</button>
                <div id="dice-result" style="margin-top:12px;font-size:.85em;color:var(--muted);"></div>
            </div>
            
            <!-- Current Scenario Info -->
            <div class="card" style="margin-bottom:16px;">
                <h4>Current Scenario</h4>
                <div id="current-scenario" style="font-size:.85em;color:var(--muted);">No scenario active</div>
            </div>
        </div>
    </div>
</div>

<!-- ══════ TAB 2: DASHBOARD ══════ -->
<div id="tab-dashboard" class="tab-content active">
    <div class="grid">
        <div class="card"><h3>Status</h3><div id="status-content">Loading...</div></div>
        <div class="card"><h3>Daily Agenda</h3><div id="agenda-content">Loading...</div></div>
        <div class="card"><h3>Emotions</h3><div id="emotions-content">Loading...</div></div>
        <div class="card"><h3>Recent Logs</h3><div id="logs-content" style="max-height:300px;overflow-y:auto;">Loading...</div></div>
    </div>
</div>

<!-- ══════ TAB 2: COMPUTE & POWER (Infrastructure Manager) ══════ -->
<div id="tab-compute" class="tab-content">
    <div class="grid" style="max-width:1200px;margin:0 auto;">
        <!-- Cost Tracking -->
        <div class="card" style="grid-column:1/-1;">
            <h3>💰 Cost Tracking</h3>
            <div style="display:flex;gap:24px;align-items:center;">
                <div>
                    <div style="font-size:.85em;color:var(--muted);">Running cost this session</div>
                    <div id="session-cost" style="font-size:2em;font-weight:700;color:var(--accent);">$0.00</div>
                </div>
                <div>
                    <div style="font-size:.85em;color:var(--muted);">Active instances</div>
                    <div id="active-instances" style="font-size:1.5em;font-weight:700;">0</div>
                </div>
                <div>
                    <div style="font-size:.85em;color:var(--muted);">Auto-shutdown</div>
                    <div id="auto-shutdown-status" style="font-size:1.5em;font-weight:700;">Enabled (4h)</div>
                </div>
            </div>
        </div>

        <!-- Provider Selection -->
        <div class="card" style="grid-column:1/-1;">
            <h3>🏭 GPU Provider</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;">
                <div>
                    <label style="font-size:.85em;color:var(--muted);">Select Provider</label>
                    <select id="gpu-provider">
                        <option value="runpod">RunPod (Recommended)</option>
                        <option value="vast_ai">Vast.ai (Cheapest)</option>
                        <option value="lambda_labs">Lambda Labs (Stable)</option>
                        <option value="paperspace">Paperspace (Docker-friendly)</option>
                        <option value="modal">Modal (Serverless)</option>
                        <option value="tensordock">TensorDock (Aggregated)</option>
                        <option value="google_vertex">Google Vertex AI (Enterprise)</option>
                    </select>
                </div>
                <div>
                    <label style="font-size:.85em;color:var(--muted);">API Key</label>
                    <input type="password" id="gpu-api-key" placeholder="Paste your API key (encrypted)">
                </div>
                <div>
                    <label style="font-size:.85em;color:var(--muted);">Region (optional)</label>
                    <select id="gpu-region">
                        <option value="">Auto-select</option>
                        <option value="us-east-1">US East</option>
                        <option value="us-west-1">US West</option>
                        <option value="eu-west-1">Europe West</option>
                        <option value="eu-central-1">Europe Central</option>
                        <option value="ap-southeast-1">Asia Pacific</option>
                    </select>
                </div>
                <div>
                    <label style="font-size:.85em;color:var(--muted);">GPU Type</label>
                    <select id="gpu-type">
                        <option value="rtx_4090">RTX 4090 (1080p, $0.44/h)</option>
                        <option value="rtx_4080">RTX 4080 (1080p, $0.35/h)</option>
                        <option value="rtx_3090">RTX 3090 (1080p, $0.28/h)</option>
                        <option value="rtx_3060">RTX 3060 (720p, $0.15/h)</option>
                        <option value="a100">A100 (4K, Enterprise)</option>
                    </select>
                </div>
            </div>
            <div style="margin-top:12px;">
                <button class="btn btn-accent" onclick="registerProvider()">Register Provider</button>
                <button class="btn" onclick="checkBalance()">Check Balance</button>
            </div>
            <div id="provider-status" style="margin-top:12px;color:var(--muted);"></div>
        </div>

        <!-- Available Instances -->
        <div class="card" style="grid-column:1/-1;">
            <h3>📋 Available Instances</h3>
            <div style="margin-bottom:12px;">
                <button class="btn" onclick="refreshInstances()">Refresh</button>
            </div>
            <div id="available-instances" style="max-height:300px;overflow-y:auto;">Loading...</div>
        </div>

        <!-- Active Instances -->
        <div class="card" style="grid-column:1/-1;">
            <h3>🚀 Active Instances</h3>
            <div id="active-instances-list" style="max-height:300px;overflow-y:auto;">No active instances</div>
        </div>

        <!-- Auto-Deploy -->
        <div class="card" style="grid-column:1/-1;">
            <h3>🚀 Auto-Deploy</h3>
            <p style="color:var(--muted);margin-bottom:12px;">
                Automatically start Anton Egon Docker container on selected GPU when you click "Start Agent"
            </p>
            <div style="display:flex;gap:12px;align-items:center;">
                <label>
                    <input type="checkbox" id="auto-deploy-enabled" checked> Enable Auto-Deploy
                </label>
                <button class="btn btn-accent" onclick="startAutoDeploy()">Start Agent on Cloud</button>
                <button class="btn btn-danger" onclick="stopAllInstances()">Stop All Instances</button>
            </div>
        </div>

        <!-- Credits & Payments -->
        <div class="card" style="grid-column:1/-1;">
            <h3>💳 Credits & Payments</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;">
                <div>
                    <label style="font-size:.85em;color:var(--muted);">Purchase Credits</label>
                    <select id="credit-amount">
                        <option value="10">$10 (RunPod)</option>
                        <option value="25">$25 (RunPod)</option>
                        <option value="50">$50 (RunPod)</option>
                        <option value="100">$100 (RunPod)</option>
                    </select>
                </div>
                <div>
                    <label style="font-size:.85em;color:var(--muted);">Card Number</label>
                    <input type="text" id="card-number" placeholder="XXXX XXXX XXXX XXXX" maxlength="19">
                </div>
                <div>
                    <label style="font-size:.85em;color:var(--muted);">Expiry</label>
                    <input type="text" id="card-expiry" placeholder="MM/YY" maxlength="5">
                </div>
                <div>
                    <label style="font-size:.85em;color:var(--muted);">CVC</label>
                    <input type="text" id="card-cvc" placeholder="123" maxlength="3">
                </div>
            </div>
            <div style="margin-top:12px;">
                <button class="btn btn-accent" onclick="purchaseCredits()">Purchase Credits</button>
            </div>
            <div id="payment-status" style="margin-top:12px;color:var(--muted);"></div>
        </div>

        <!-- Freemium/Premium Wardrobe -->
        <div class="card" style="grid-column:1/-1;">
            <h3>👔 Freemium/Premium Wardrobe</h3>
            <div style="display:flex;gap:24px;margin-bottom:12px;">
                <div>
                    <div style="font-size:.85em;color:var(--muted);">Freemium Wardrobe</div>
                    <div id="freemium-items" style="display:flex;gap:8px;flex-wrap:wrap;">
                        <span class="badge" style="background:var(--bg-dark);">👔 Business Suit</span>
                        <span class="badge" style="background:var(--bg-dark);">👕 Casual Shirt</span>
                        <span class="badge" style="background:var(--bg-dark);">🧥 Jacket</span>
                    </div>
                </div>
                <div>
                    <div style="font-size:.85em;color:var(--muted);">Premium Wardrobe ($5/mo)</div>
                    <div id="premium-items" style="display:flex;gap:8px;flex-wrap:wrap;">
                        <span class="badge" style="background:var(--accent);color:#0f0f1a;">🎩 Fedora</span>
                        <span class="badge" style="background:var(--accent);color:#0f0f1a;">🕶️ Sunglasses</span>
                        <span class="badge" style="background:var(--accent);color:#0f0f1a;">🧣 Scarf</span>
                        <span class="badge" style="background:var(--accent);color:#0f0f1a;">🎀 Bowtie</span>
                    </div>
                </div>
            </div>
            <button class="btn btn-accent" onclick="upgradeToPremium()">Upgrade to Premium ($5/mo)</button>
        </div>

        <!-- Freemium/Premium Pranks -->
        <div class="card" style="grid-column:1/-1;">
            <h3>🎭 Freemium/Premium Pranks</h3>
            <div style="display:flex;gap:24px;margin-bottom:12px;">
                <div>
                    <div style="font-size:.85em;color:var(--muted);">Freemium Pranks</div>
                    <div id="freemium-pranks" style="display:flex;gap:8px;flex-wrap:wrap;">
                        <span class="badge" style="background:var(--bg-dark);">😴 Yawn</span>
                        <span class="badge" style="background:var(--bg-dark);">🤔 Confused</span>
                        <span class="badge" style="background:var(--bg-dark);">😏 Smirk</span>
                    </div>
                </div>
                <div>
                    <div style="font-size:.85em;color:var(--muted);">Premium Pranks ($5/mo)</div>
                    <div id="premium-pranks" style="display:flex;gap:8px;flex-wrap:wrap;">
                        <span class="badge" style="background:var(--accent);color:#0f0f1a;">🤡 Clown Nose</span>
                        <span class="badge" style="background:var(--accent);color:#0f0f1a;">👻 Ghost Face</span>
                        <span class="badge" style="background:var(--accent);color:#0f0f1a;">🎃 Pumpkin Head</span>
                        <span class="badge" style="background:var(--accent);color:#0f0f1a;">🦄 Unicorn Horn</span>
                    </div>
                </div>
            </div>
            <button class="btn btn-accent" onclick="upgradeToPremium()">Unlock Premium Pranks ($5/mo)</button>
        </div>
    </div>
</div>

<!-- ══════ TAB 9: BIOMETRICS ══════ -->
<div id="tab-biometrics" class="tab-content">
    <div class="grid" style="max-width:1200px;margin:0 auto;">
        <!-- Face Scan -->
        <div class="card" style="grid-column:1/-1;">
            <h3>🧬 Face & Outfit Scan</h3>
            <p style="color:var(--muted);font-size:.9em;margin-bottom:16px;">Scan your face and outfit to enable AI-generated prank/distraction clips that look like you.</p>
            
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
                <!-- Camera Preview -->
                <div>
                    <div style="margin-bottom:8px;font-size:.9em;color:var(--muted);">Camera Preview</div>
                    <div class="monitor" style="background:#000;border-radius:8px;aspect-ratio:16/9;position:relative;">
                        <video id="biometrics-camera" autoplay muted playsinline style="width:100%;height:100%;object-fit:cover;"></video>
                        <div id="scan-overlay" style="position:absolute;top:0;left:0;width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.7);color:#fff;">
                            <div>Camera not started</div>
                        </div>
                    </div>
                    <div style="display:flex;gap:12px;margin-top:12px;">
                        <button class="btn btn-accent" onclick="startBiometricsCamera()">Start Camera</button>
                        <button class="btn btn-outline" onclick="stopBiometricsCamera()">Stop Camera</button>
                    </div>
                </div>
                
                <!-- Scan Info -->
                <div>
                    <div style="margin-bottom:8px;font-size:.9em;color:var(--muted);">Scan Status</div>
                    <div id="scan-status" style="padding:16px;background:var(--bg-dark);border-radius:8px;margin-bottom:12px;">
                        <div style="font-weight:bold;margin-bottom:8px;">Status: <span id="biometrics-status">Idle</span></div>
                        <div style="font-size:.85em;">
                            <div>Face Data: <span id="face-data-status">Not scanned</span></div>
                            <div>Outfit Data: <span id="outfit-data-status">Not scanned</span></div>
                            <div>Profile ID: <span id="profile-id">-</span></div>
                        </div>
                    </div>
                    <button class="btn btn-accent" onclick="startBiometricsScan()" style="width:100%;">Start Full Scan</button>
                </div>
            </div>
        </div>

        <!-- AI Video Generation -->
        <div class="card" style="grid-column:1/-1;">
            <h3>🎬 AI Video Generation</h3>
            <p style="color:var(--muted);font-size:.9em;margin-bottom:16px;">Generate prank/distraction clips using AI prompts (requires face scan first).</p>
            
            <!-- Provider Selection -->
            <div style="margin-bottom:16px;padding:16px;background:var(--bg-dark);border-radius:8px;">
                <div style="font-weight:bold;margin-bottom:12px;">Select Provider</div>
                <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;">
                    <div class="card" style="padding:12px;cursor:pointer;" onclick="selectProvider('runway')">
                        <div style="font-weight:bold;margin-bottom:4px;">🚀 RunwayML</div>
                        <div style="font-size:.85em;color:var(--muted);">$0.05/sec • High quality</div>
                        <div id="runway-credits" style="font-size:.85em;margin-top:8px;">Credits: 0</div>
                    </div>
                    <div class="card" style="padding:12px;cursor:pointer;" onclick="selectProvider('d_id')">
                        <div style="font-weight:bold;margin-bottom:4px;">🎭 D-ID</div>
                        <div style="font-size:.85em;color:var(--muted);">$0.03/sec • Lip-sync</div>
                        <div id="d_id-credits" style="font-size:.85em;margin-top:8px;">Credits: 0</div>
                    </div>
                    <div class="card" style="padding:12px;cursor:pointer;" onclick="selectProvider('heygen')">
                        <div style="font-weight:bold;margin-bottom:4px;">🎬 HeyGen</div>
                        <div style="font-size:.85em;color:var(--muted);">$0.04/sec • Fast</div>
                        <div id="heygen-credits" style="font-size:.85em;margin-top:8px;">Credits: 0</div>
                    </div>
                    <div class="card" style="padding:12px;cursor:pointer;" onclick="selectProvider('synthesia')">
                        <div style="font-weight:bold;margin-bottom:4px;">🎥 Synthesia</div>
                        <div style="font-size:.85em;color:var(--muted);">$0.06/sec • Professional</div>
                        <div id="synthesia-credits" style="font-size:.85em;margin-top:8px;">Credits: 0</div>
                    </div>
                </div>
            </div>
            
            <!-- Selected Provider Info -->
            <div id="selected-provider-info" style="margin-bottom:16px;padding:12px;background:var(--accent);color:#0f0f1a;border-radius:8px;display:none;">
                <div style="font-weight:bold;">Selected: <span id="selected-provider-name">-</span></div>
                <div style="font-size:.85em;">Credits: <span id="selected-provider-credits">-</span> | Price: $<span id="selected-provider-price">-</span>/sec</div>
            </div>
            
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
                <!-- Prompt Input -->
                <div>
                    <div style="margin-bottom:8px;font-size:.9em;color:var(--muted);">Prompt</div>
                    <textarea id="ai-video-prompt" rows="4" placeholder="Describe the prank/distraction you want to generate. Example: 'Person reaches for a glass of water on the table and accidentally pours it over themselves'" style="width:100%;resize:vertical;margin-bottom:12px;"></textarea>
                    
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;">
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Duration (seconds)</label>
                            <input type="number" id="video-duration" value="3" min="1" max="10" style="width:100%;">
                        </div>
                        <div>
                            <label style="font-size:.85em;color:var(--muted);">Quality</label>
                            <select id="video-quality" style="width:100%;">
                                <option value="low">Low (Fast)</option>
                                <option value="medium" selected>Medium</option>
                                <option value="high">High (Slow)</option>
                            </select>
                        </div>
                    </div>
                    
                    <button class="btn btn-accent" onclick="generateAIVideo()" style="width:100%;">Generate Video</button>
                </div>
                
                <!-- Generation Status -->
                <div>
                    <div style="margin-bottom:8px;font-size:.9em;color:var(--muted);">Generation Status</div>
                    <div id="generation-status" style="padding:16px;background:var(--bg-dark);border-radius:8px;">
                        <div style="font-size:.85em;">
                            <div>Status: <span id="gen-status">Ready</span></div>
                            <div style="margin-top:8px;">Progress: <span id="gen-progress">0%</span></div>
                            <div style="margin-top:8px;">Output: <span id="gen-output">-</span></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Credit Purchase -->
        <div class="card" style="grid-column:1/-1;">
            <h3>💳 Purchase Credits</h3>
            <p style="color:var(--muted);font-size:.9em;margin-bottom:16px;">Purchase credits for selected provider to generate videos.</p>
            
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
                <!-- Credit Packages -->
                <div>
                    <div style="margin-bottom:8px;font-size:.9em;color:var(--muted);">Credit Packages</div>
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
                        <div class="card" style="padding:12px;cursor:pointer;" onclick="selectCreditPackage(10)">
                            <div style="font-weight:bold;">10 Credits</div>
                            <div style="font-size:.85em;color:var(--muted);">~200s video</div>
                            <div style="font-size:.9em;font-weight:bold;margin-top:4px;">$1.00</div>
                        </div>
                        <div class="card" style="padding:12px;cursor:pointer;" onclick="selectCreditPackage(50)">
                            <div style="font-weight:bold;">50 Credits</div>
                            <div style="font-size:.85em;color:var(--muted);">~1000s video</div>
                            <div style="font-size:.9em;font-weight:bold;margin-top:4px;">$4.50</div>
                        </div>
                        <div class="card" style="padding:12px;cursor:pointer;" onclick="selectCreditPackage(100)">
                            <div style="font-weight:bold;">100 Credits</div>
                            <div style="font-size:.85em;color:var(--muted);">~2000s video</div>
                            <div style="font-size:.9em;font-weight:bold;margin-top:4px;">$8.00</div>
                        </div>
                        <div class="card" style="padding:12px;cursor:pointer;" onclick="selectCreditPackage(500)">
                            <div style="font-weight:bold;">500 Credits</div>
                            <div style="font-size:.85em;color:var(--muted);">~10000s video</div>
                            <div style="font-size:.9em;font-weight:bold;margin-top:4px;">$35.00</div>
                        </div>
                    </div>
                </div>
                
                <!-- Purchase Info -->
                <div>
                    <div style="margin-bottom:8px;font-size:.9em;color:var(--muted);">Purchase Summary</div>
                    <div style="padding:16px;background:var(--bg-dark);border-radius:8px;">
                        <div style="font-size:.85em;">
                            <div style="margin-bottom:8px;">Provider: <span id="purchase-provider">-</span></div>
                            <div style="margin-bottom:8px;">Package: <span id="selected-package">-</span> credits</div>
                            <div style="margin-bottom:8px;">Price: $<span id="package-price">-</span></div>
                            <div style="margin-bottom:16px;">Est. Video Time: <span id="est-video-time">-</span></div>
                        </div>
                        <button class="btn btn-accent" onclick="purchaseCredits()" style="width:100%;">Purchase Credits</button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Pre-made Prank Templates -->
        <div class="card" style="grid-column:1/-1;">
            <h3>🎭 Pre-made Prank Templates</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px;">
                <div class="card" style="padding:12px;">
                    <div style="font-weight:bold;margin-bottom:4px;">💧 Water Pour</div>
                    <div style="font-size:.85em;color:var(--muted);margin-bottom:8px;">Person pours water over themselves</div>
                    <button class="btn btn-outline" onclick="useTemplate('water_pour')" style="width:100%;">Use Template</button>
                </div>
                <div class="card" style="padding:12px;">
                    <div style="font-weight:bold;margin-bottom:4px;">🤡 Clown Nose</div>
                    <div style="font-size:.85em;color:var(--muted);margin-bottom:8px;">Person puts on a clown nose</div>
                    <button class="btn btn-outline" onclick="useTemplate('clown_nose')" style="width:100%;">Use Template</button>
                </div>
                <div class="card" style="padding:12px;">
                    <div style="font-weight:bold;margin-bottom:4px;">😲 Surprised</div>
                    <div style="font-size:.85em;color:var(--muted);margin-bottom:8px;">Shocked expression with mouth open</div>
                    <button class="btn btn-outline" onclick="useTemplate('surprised')" style="width:100%;">Use Template</button>
                </div>
                <div class="card" style="padding:12px;">
                    <div style="font-weight:bold;margin-bottom:4px;">😴 Yawn</div>
                    <div style="font-size:.85em;color:var(--muted);margin-bottom:8px;">Big yawn during meeting</div>
                    <button class="btn btn-outline" onclick="useTemplate('yawn')" style="width:100%;">Use Template</button>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- ══════ TAB 8: SHADOWING ══════ -->
<div id="tab-shadowing" class="tab-content">
    <div class="grid" style="max-width:1200px;margin:0 auto;">
        <!-- Ghostwriter Mode -->
        <div class="card" style="grid-column:1/-1;">
            <h3>👻 Ghostwriter Mode</h3>
            <div style="display:flex;gap:16px;align-items:center;margin-bottom:16px;">
                <div>
                    <label style="font-size:.85em;color:var(--muted);">Mode</label>
                    <select id="ghostwriter-mode" onchange="setGhostwriterMode(this.value)">
                        <option value="passive">Passive (Listen Only)</option>
                        <option value="assistive" selected>Assistive (Suggest & Approve)</option>
                        <option value="autonomous">Autonomous (Full Control)</option>
                        <option value="veto_only">VETO Only (Emergency)</option>
                    </select>
                </div>
                <div>
                    <label style="font-size:.85em;color:var(--muted);">Status</label>
                    <div id="ghostwriter-status" style="font-size:1.2em;font-weight:bold;color:#ff6b6b;">Inactive</div>
                </div>
            </div>
            <div style="display:flex;gap:12px;">
                <button class="btn btn-accent" onclick="activateGhostwriter()">Activate Ghostwriter</button>
                <button class="btn btn-danger" onclick="deactivateGhostwriter()">Deactivate</button>
            </div>
        </div>

        <!-- VETO/Takeover Controls -->
        <div class="card" style="grid-column:1/-1;">
            <h3>🛡️ VETO/Takeover Controls</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;">
                <div class="card" style="border:2px solid #ff6b6b;padding:16px;text-align:center;">
                    <div style="font-size:2em;margin-bottom:8px;">🚫</div>
                    <div style="font-weight:bold;margin-bottom:8px;">VETO</div>
                    <div style="font-size:.85em;color:var(--muted);margin-bottom:12px;">Cancel pending response</div>
                    <button class="btn btn-danger" onclick="vetoIntervention()">VETO Response</button>
                </div>
                <div class="card" style="border:2px solid var(--accent);padding:16px;text-align:center;">
                    <div style="font-size:2em;margin-bottom:8px;">✅</div>
                    <div style="font-weight:bold;margin-bottom:8px;">APPROVE</div>
                    <div style="font-size:.85em;color:var(--muted);margin-bottom:12px;">Send suggested response</div>
                    <button class="btn btn-accent" onclick="approveIntervention()">Approve Response</button>
                </div>
                <div class="card" style="border:2px solid #ffd700;padding:16px;text-align:center;">
                    <div style="font-size:2em;margin-bottom:8px;">🎤</div>
                    <div style="font-weight:bold;margin-bottom:8px;">TAKEOVER</div>
                    <div style="font-size:.85em;color:var(--muted);margin-bottom:12px;">Manual control override</div>
                    <button class="btn btn-accent" onclick="takeoverControl()">Take Control</button>
                </div>
            </div>
        </div>

        <!-- Pending Interventions -->
        <div class="card" style="grid-column:1/-1;">
            <h3>📋 Pending Interventions</h3>
            <div id="interventions-list" style="display:flex;flex-direction:column;gap:12px;">
                <div style="color:var(--muted);text-align:center;padding:24px;">No pending interventions</div>
            </div>
        </div>

        <!-- Meeting Context -->
        <div class="card" style="grid-column:1/-1;">
            <h3>📝 Meeting Context</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;">
                <div>
                    <div style="font-size:.85em;color:var(--muted);">Meeting ID</div>
                    <div id="meeting-id">Not active</div>
                </div>
                <div>
                    <div style="font-size:.85em;color:var(--muted);">Participants</div>
                    <div id="participant-count">0</div>
                </div>
                <div>
                    <div style="font-size:.85em;color:var(--muted);">Duration</div>
                    <div id="meeting-duration">0 min</div>
                </div>
                <div>
                    <div style="font-size:.85em;color:var(--muted);">Interventions</div>
                    <div id="intervention-count">0</div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- ══════ TAB 7: ANTON STORE ══════ -->
<div id="tab-store" class="tab-content">
    <div class="grid" style="max-width:1200px;margin:0 auto;">
        <!-- Credit Balance -->
        <div class="card" style="grid-column:1/-1;">
            <h3>💰 Your Balance</h3>
            <div style="display:flex;gap:24px;align-items:center;">
                <div>
                    <div style="font-size:.85em;color:var(--muted);">Anton Credits</div>
                    <div id="anton-credits" style="font-size:2em;font-weight:bold;color:var(--accent);">0</div>
                </div>
                <div>
                    <div style="font-size:.85em;color:var(--muted);">GPU Credits</div>
                    <div id="gpu-credits" style="font-size:2em;font-weight:bold;color:#ffd700;">$0.00</div>
                </div>
                <div>
                    <div style="font-size:.85em;color:var(--muted);">Subscription</div>
                    <div id="subscription-tier" style="font-size:1.2em;font-weight:bold;">Freemium</div>
                </div>
            </div>
        </div>

        <!-- Credit Packages -->
        <div class="card" style="grid-column:1/-1;">
            <h3>🎁 Purchase Anton Credits</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:16px;">
                <div class="card" style="border:2px solid var(--border);padding:16px;">
                    <h4 style="color:var(--accent);">Starter</h4>
                    <div style="font-size:2em;font-weight:bold;margin:8px 0;">$10</div>
                    <div style="color:var(--muted);font-size:.9em;margin-bottom:12px;">100 Anton Credits</div>
                    <button class="btn btn-accent" onclick="purchasePackage('starter')">Purchase</button>
                </div>
                <div class="card" style="border:2px solid var(--accent);padding:16px;">
                    <div style="font-size:.85em;background:var(--accent);color:#0f0f1a;display:inline-block;padding:2px 8px;border-radius:4px;margin-bottom:8px;">BEST VALUE</div>
                    <h4 style="color:var(--accent);">Pro</h4>
                    <div style="font-size:2em;font-weight:bold;margin:8px 0;">$50</div>
                    <div style="color:var(--muted);font-size:.9em;margin-bottom:12px;">600 Anton Credits (20% bonus)</div>
                    <button class="btn btn-accent" onclick="purchasePackage('pro')">Purchase</button>
                </div>
                <div class="card" style="border:2px solid #ffd700;padding:16px;">
                    <h4 style="color:#ffd700;">Enterprise</h4>
                    <div style="font-size:2em;font-weight:bold;margin:8px 0;">$100</div>
                    <div style="color:var(--muted);font-size:.9em;margin-bottom:12px;">1500 Anton Credits (50% bonus)</div>
                    <button class="btn btn-accent" onclick="purchasePackage('enterprise')">Purchase</button>
                </div>
            </div>
        </div>

        <!-- Premium Wardrobe -->
        <div class="card" style="grid-column:1/-1;">
            <h3>👔 Premium Wardrobe</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;">
                <div class="card" style="padding:12px;text-align:center;">
                    <div style="font-size:2em;margin-bottom:8px;">🎩</div>
                    <div style="font-size:.9em;font-weight:bold;">Fedora</div>
                    <div style="font-size:.85em;color:var(--accent);">Premium</div>
                </div>
                <div class="card" style="padding:12px;text-align:center;">
                    <div style="font-size:2em;margin-bottom:8px;">🕶️</div>
                    <div style="font-size:.9em;font-weight:bold;">Sunglasses</div>
                    <div style="font-size:.85em;color:var(--accent);">Premium</div>
                </div>
                <div class="card" style="padding:12px;text-align:center;">
                    <div style="font-size:2em;margin-bottom:8px;">🧣</div>
                    <div style="font-size:.9em;font-weight:bold;">Scarf</div>
                    <div style="font-size:.85em;color:var(--accent);">Premium</div>
                </div>
                <div class="card" style="padding:12px;text-align:center;">
                    <div style="font-size:2em;margin-bottom:8px;">🎀</div>
                    <div style="font-size:.9em;font-weight:bold;">Bowtie</div>
                    <div style="font-size:.85em;color:var(--accent);">Premium</div>
                </div>
            </div>
            <div style="margin-top:12px;">
                <button class="btn btn-accent" onclick="unlockPremiumWardrobe()">Unlock Premium Wardrobe ($5/mo)</button>
            </div>
        </div>

        <!-- Premium Pranks -->
        <div class="card" style="grid-column:1/-1;">
            <h3>🎭 Premium Pranks</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;">
                <div class="card" style="padding:12px;text-align:center;">
                    <div style="font-size:2em;margin-bottom:8px;">🤡</div>
                    <div style="font-size:.9em;font-weight:bold;">Clown Nose</div>
                    <div style="font-size:.85em;color:var(--accent);">Premium</div>
                </div>
                <div class="card" style="padding:12px;text-align:center;">
                    <div style="font-size:2em;margin-bottom:8px;">👻</div>
                    <div style="font-size:.9em;font-weight:bold;">Ghost Face</div>
                    <div style="font-size:.85em;color:var(--accent);">Premium</div>
                </div>
                <div class="card" style="padding:12px;text-align:center;">
                    <div style="font-size:2em;margin-bottom:8px;">🎃</div>
                    <div style="font-size:.9em;font-weight:bold;">Pumpkin Head</div>
                    <div style="font-size:.85em;color:var(--accent);">Premium</div>
                </div>
                <div class="card" style="padding:12px;text-align:center;">
                    <div style="font-size:2em;margin-bottom:8px;">🦄</div>
                    <div style="font-size:.9em;font-weight:bold;">Unicorn Horn</div>
                    <div style="font-size:.85em;color:var(--accent);">Premium</div>
                </div>
            </div>
            <div style="margin-top:12px;">
                <button class="btn btn-accent" onclick="unlockPremiumPranks()">Unlock Premium Pranks ($5/mo)</button>
            </div>
        </div>
    </div>
</div>

<!-- ══════ TAB 3: UNIFIED INBOX ══════ -->
<div id="tab-inbox" class="tab-content">
    <div class="grid" style="max-width:1200px;margin:0 auto;">
        <!-- Inbox Stats -->
        <div class="card" style="grid-column:1/-1;">
            <h3>Inbox Statistics</h3>
            <div id="inbox-stats">Loading...</div>
        </div>

        <!-- Filters -->
        <div class="card" style="grid-column:1/-1;">
            <h3>Filters</h3>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
                <button class="btn btn-accent" onclick="filterInbox('all')">All</button>
                <button class="btn" onclick="filterInbox('unread')">Unread</button>
                <button class="btn" onclick="filterInbox('drafts')">Drafts</button>
                <button class="btn" onclick="filterInbox('teams')">Teams</button>
                <button class="btn" onclick="filterInbox('slack')">Slack</button>
                <button class="btn" onclick="filterInbox('email')">Email</button>
                <button class="btn" onclick="filterInbox('high_priority')">High Priority</button>
            </div>
        </div>

        <!-- Messages List -->
        <div class="card" style="grid-column:1/-1;">
            <h3>Messages</h3>
            <div id="inbox-messages" style="max-height:600px;overflow-y:auto;"></div>
        </div>
    </div>
</div>

<!-- ══════ TAB 3: PHRASE LIBRARY ══════ -->
<div id="tab-phrases" class="tab-content">
    <div class="grid" style="max-width:1200px;margin:0 auto;">
        <!-- Library Stats -->
        <div class="card" style="grid-column:1/-1;">
            <h3>Phrase Library Statistics</h3>
            <div id="phrase-stats">Loading...</div>
        </div>

        <!-- Add New Phrase -->
        <div class="card" style="grid-column:1/-1;">
            <h3>Add New Phrase</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;">
                <div>
                    <label style="font-size:.85em;color:var(--muted);">Phrase Text</label>
                    <input type="text" id="phrase-text" placeholder="e.g., 'Kanon, då klubbar vi det.'">
                </div>
                <div>
                    <label style="font-size:.85em;color:var(--muted);">Category</label>
                    <select id="phrase-category">
                        <option value="greetings">Greetings</option>
                        <option value="decisions">Decisions</option>
                        <option value="pushback">Pushback</option>
                        <option value="fillers">Fillers</option>
                        <option value="agreement">Agreement</option>
                        <option value="disagreement">Disagreement</option>
                        <option value="transitions">Transitions</option>
                        <option value="closings">Closings</option>
                        <option value="humor">Humor</option>
                        <option value="technical">Technical</option>
                    </select>
                </div>
                <div>
                    <label style="font-size:.85em;color:var(--muted);">Trigger Mood</label>
                    <select id="phrase-mood">
                        <option value="any">Any</option>
                        <option value="happy">Happy</option>
                        <option value="neutral">Neutral</option>
                        <option value="irritated">Irritated</option>
                        <option value="excited">Excited</option>
                        <option value="serious">Serious</option>
                        <option value="casual">Casual</option>
                    </select>
                </div>
                <div>
                    <label style="font-size:.85em;color:var(--muted);">Frequency (0-1)</label>
                    <input type="number" id="phrase-frequency" min="0" max="1" step="0.1" value="0.5">
                </div>
            </div>
            <div style="margin-top:12px;">
                <label style="font-size:.85em;color:var(--muted);">Notes</label>
                <input type="text" id="phrase-notes" placeholder="Optional notes...">
            </div>
            <div style="margin-top:12px;">
                <button class="btn btn-accent" onclick="addPhrase()">Add Phrase</button>
                <button class="btn" onclick="importDefaultPhrases()">Import Default Phrases</button>
            </div>
        </div>

        <!-- Phrase List -->
        <div class="card" style="grid-column:1/-1;">
            <h3>Phrases</h3>
            <div style="display:flex;gap:8px;margin-bottom:12px;">
                <button class="btn" onclick="filterPhrases('all')">All</button>
                <button class="btn" onclick="filterPhrases('greetings')">Greetings</button>
                <button class="btn" onclick="filterPhrases('decisions')">Decisions</button>
                <button class="btn" onclick="filterPhrases('pushback')">Pushback</button>
            </div>
            <div id="phrase-list" style="max-height:600px;overflow-y:auto;"></div>
        </div>
    </div>
</div>

<!-- ══════ TAB 4: CHAOS DASHBOARD ══════ -->
<div id="tab-chaos" class="tab-content">
    <div class="grid" style="max-width:1200px;margin:0 auto;">
        <!-- Props Section -->
        <div class="card" style="grid-column:1/-1;">
            <h3>🎭 Prop Shop</h3>
            <p style="color:var(--muted);margin-bottom:16px;">Click to toggle props on your avatar</p>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;" id="prop-controls">
                <!-- Props will be loaded here -->
            </div>
        </div>

        <!-- Overlays Section -->
        <div class="card" style="grid-column:1/-1;">
            <h3>🎬 Action Overlays</h3>
            <p style="color:var(--muted);margin-bottom:16px;">Trigger alpha overlay clips</p>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;" id="overlay-controls">
                <!-- Overlays will be loaded here -->
            </div>
        </div>

        <!-- Quick Actions -->
        <div class="card" style="grid-column:1/-1;">
            <h3>⚡ Quick Actions</h3>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
                <button class="btn btn-accent" onclick="triggerOverlay('water_pour_001')">💧 Water Pour</button>
                <button class="btn" onclick="triggerOverlay('surprise_001')">😲 Surprise</button>
                <button class="btn" onclick="triggerOverlay('glass_adjust_001')">👓 Adjust Glasses</button>
                <button class="btn" onclick="clearAllProps()">Clear All Props</button>
                <button class="btn" onclick="stopAllOverlays()">Stop All Overlays</button>
            </div>
        </div>
    </div>
</div>

<!-- ══════ TAB 5: THE STUDIO ══════ -->
<div id="tab-studio" class="tab-content">
    <div class="studio-layout">

        <!-- LEFT: Teleprompter & Controls -->
        <div>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Recording Mode:</label>
                <select id="studio-mode" onchange="loadTeleprompter()">
                    <option value="voice_sentence">Voice Sentences</option>
                    <option value="voice_preroll">Pre-roll Clips</option>
                    <option value="wardrobe_idle">Wardrobe: Idle</option>
                    <option value="wardrobe_action">Wardrobe: Actions</option>
                    <option value="stitcher_nodes">🎬 Stitcher Nodes (WebRTC)</option>
                </select>
            </div>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Outfit:</label>
                <select id="studio-outfit">
                    <option value="outfit_shirt_01">Skjorta 1</option>
                    <option value="outfit_shirt_02">Skjorta 2</option>
                    <option value="outfit_tshirt">T-shirt</option>
                    <option value="outfit_glasses">Glasogon</option>
                    <option value="outfit_casual">Casual</option>
                </select>
            </div>

            <div class="teleprompter" id="teleprompter">
                <p style="color:var(--muted);">Select a mode to load sentences...</p>
            </div>
        </div>

        <!-- CENTER: Live Monitor -->
        <div>
            <div class="monitor" id="video-monitor">
                <video id="webcam-preview" autoplay muted playsinline></video>
                <img id="ghost-img" class="ghost-overlay" style="display:none;">
                <div class="rec-badge" id="rec-badge">REC</div>
            </div>

            <!-- Audio Meter -->
            <div style="margin-top:10px;">
                <div style="display:flex;justify-content:space-between;font-size:.8em;color:var(--muted);">
                    <span>Audio Level</span>
                    <span id="audio-db">-60 dB</span>
                </div>
                <div class="audio-meter">
                    <div class="audio-meter-fill ok" id="audio-meter-fill" style="width:5%;"></div>
                </div>
            </div>

            <!-- Controls -->
            <div class="controls-row">
                <button class="btn btn-rec" id="btn-rec" onclick="startRecording()">REC</button>
                <button class="btn btn-stop" id="btn-stop" onclick="stopRecording()" disabled>STOP</button>
                <button class="btn btn-outline" onclick="toggleGhost()">Ghost Overlay</button>
                <span id="rec-timer" style="font-family:monospace;font-size:1.2em;color:var(--accent);margin-left:auto;">00:00</span>
            </div>

            <div id="rec-status" style="font-size:.85em;color:var(--muted);margin-top:6px;"></div>
        </div>

        <!-- RIGHT: Progress -->
        <div>
            <div class="card" style="margin-bottom:12px;">
                <h3>Video Progress</h3>
                <div id="video-progress">Loading...</div>
            </div>
            <div class="card" style="margin-bottom:12px;">
                <h3>Audio Progress</h3>
                <div id="audio-progress">Loading...</div>
            </div>
            <div class="card" style="margin-bottom:12px;">
                <h3>Pre-roll Progress</h3>
                <div id="preroll-progress">Loading...</div>
            </div>
            <div class="card">
                <h3>System</h3>
                <div id="system-status">
                    <div class="status-item">Brightness: <span id="brightness-status">OK</span></div>
                    <div class="status-item">Audio: <span id="audio-status">OK</span></div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- ══════ TAB 5: TURING MIRROR (Phase 18) ══════ -->
<div id="tab-turing" class="tab-content">
    <div class="grid" style="max-width:1400px;margin:0 auto;">
        <!-- Mirror Mode Selection -->
        <div class="card" style="grid-column:1/-1;">
            <h3>Turing Mirror Mode</h3>
            <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;">
                <button class="btn btn-accent" onclick="setMirrorMode('side_by_side')">Side-by-Side</button>
                <button class="btn btn-outline" onclick="setMirrorMode('ghost_overlay')">Ghost Overlay</button>
                <button class="btn btn-outline" onclick="setMirrorMode('lip_sync')">Lip-Sync Analyzer</button>
                <button class="btn btn-outline" onclick="setMirrorMode('uncanny')">Uncanny Alert</button>
            </div>
            <div style="font-size:.85em;color:var(--muted);">
                Current mode: <span id="mirror-mode" style="color:var(--accent);font-weight:700;">Side-by-Side</span>
            </div>
        </div>

        <!-- Dual Stream Display -->
        <div class="card" style="grid-column:1/-1;">
            <h3>Side-by-Side Validation</h3>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
                <!-- Live Camera -->
                <div>
                    <div style="margin-bottom:8px;font-size:.9em;color:var(--muted);">Live Camera</div>
                    <div class="monitor" style="background:#000;border-radius:8px;aspect-ratio:16/9;position:relative;">
                        <video id="live-camera" autoplay muted playsinline style="width:100%;height:100%;object-fit:cover;"></video>
                        <div class="ghost-overlay" id="live-ghost" style="display:none;"></div>
                        <div style="position:absolute;top:8px;left:8px;background:rgba(0,0,0,.7);color:#fff;padding:4px 8px;border-radius:4px;font-size:.75em;">LIVE</div>
                    </div>
                </div>
                <!-- Anton Egon Avatar -->
                <div>
                    <div style="margin-bottom:8px;font-size:.9em;color:var(--muted);">Anton Egon Avatar</div>
                    <div class="monitor" style="background:#000;border-radius:8px;aspect-ratio:16/9;position:relative;">
                        <video id="avatar-video" autoplay muted playsinline style="width:100%;height:100%;object-fit:cover;"></video>
                        <div style="position:absolute;top:8px;right:8px;background:rgba(78,204,163,.8);color:#0f0f1a;padding:4px 8px;border-radius:4px;font-size:.75em;font-weight:700;">AVATAR</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Quality Metrics -->
        <div class="card">
            <h3>Quality Metrics</h3>
            <div id="quality-metrics">
                <div class="status-item">Lip Sync: <span id="lip-sync-score">-</span></div>
                <div class="status-item">Lighting Match: <span id="lighting-score">-</span></div>
                <div class="status-item">Face Alignment: <span id="alignment-score">-</span></div>
                <div class="status-item">Motion Smoothness: <span id="motion-score">-</span></div>
                <div class="status-item" style="font-weight:700;">Overall: <span id="overall-score">-</span></div>
            </div>
        </div>

        <!-- Sync Test -->
        <div class="card">
            <h3>Sync Test</h3>
            <p style="color:var(--muted);font-size:.9em;margin-bottom:12px;">Test latency by sending a test signal to Anton Egon.</p>
            <div class="controls-row">
                <button class="btn btn-accent" onclick="runSyncTest()">Run Sync Test</button>
            </div>
            <div id="sync-test-results" style="margin-top:12px;font-size:.85em;color:var(--muted);">
                Latency: <span id="latency-ms">-</span> ms
            </div>
        </div>

        <!-- Warnings -->
        <div class="card">
            <h3>Warnings</h3>
            <div id="mirror-warnings" style="font-size:.85em;">
                <div style="color:var(--accent);">No warnings</div>
            </div>
        </div>

        <!-- Fas 24: Ground Truth Feedback Form -->
        <div class="card" style="grid-column:1/-1;">
            <h3>📝 Ground Truth Feedback (Fas 24)</h3>
            <p style="color:var(--muted);font-size:.9em;margin-bottom:12px;">Help us improve Anton Egon by providing feedback on your Turing test experience.</p>
            
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:12px;">
                <div>
                    <label style="font-size:.85em;color:var(--muted);">Session ID</label>
                    <input type="text" id="feedback-session-id" placeholder="Auto-generated" readonly style="background:var(--bg-dark);">
                </div>
                <div>
                    <label style="font-size:.85em;color:var(--muted);">Your Guess</label>
                    <select id="feedback-guess">
                        <option value="">Select...</option>
                        <option value="ai">I spoke to AI</option>
                        <option value="human">I spoke to a human</option>
                        <option value="unsure">I'm unsure</option>
                    </select>
                </div>
                <div>
                    <label style="font-size:.85em;color:var(--muted);">Confidence</label>
                    <input type="range" id="feedback-confidence" min="0" max="100" value="50" style="width:100%;">
                    <div style="font-size:.8em;color:var(--muted);text-align:center;"><span id="confidence-value">50</span>%</div>
                </div>
            </div>
            
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Detailed Feedback</label>
                <textarea id="feedback-text" rows="4" placeholder="What made you think this? Any observations about the conversation?" style="width:100%;resize:vertical;"></textarea>
            </div>
            
            <div style="display:flex;gap:12px;">
                <button class="btn btn-accent" onclick="submitGroundTruthFeedback()">Submit Feedback</button>
                <button class="btn btn-outline" onclick="startNewTuringTest()">Start New Test</button>
            </div>
            
            <div id="feedback-status" style="margin-top:12px;font-size:.85em;color:var(--muted);"></div>
        </div>
    </div>
</div>

<!-- ══════ TAB 6: SYSTEM HEALTH (Phase 18) ══════ -->
<div id="tab-health" class="tab-content">
    <div class="grid" style="max-width:1400px;margin:0 auto;">
        <!-- QA Report Summary -->
        <div class="card" style="grid-column:1/-1;">
            <h3>QA Report Summary</h3>
            <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;">
                <button class="btn btn-accent" onclick="loadQAReport()">Load QA Report</button>
                <button class="btn btn-outline" onclick="runStressTest()">Start Stress Test</button>
                <button class="btn btn-outline" onclick="stopStressTest()" id="btn-stop-stress" disabled>Stop Test</button>
            </div>
            <div id="qa-report-status" style="font-size:.85em;color:var(--muted);">No report loaded</div>
        </div>

        <!-- Quality Metrics Visualization -->
        <div class="card">
            <h3>Quality Metrics</h3>
            <div id="qa-metrics">
                <div class="status-item">Lip Sync Accuracy: <span id="qa-lip-sync">-</span>%</div>
                <div class="status-item">Visual Stability: <span id="qa-visual-stability">-</span>%</div>
                <div class="status-item">Response Latency: <span id="qa-latency">-</span>ms</div>
                <div class="status-item">Emotion Consistency: <span id="qa-emotion">-</span>%</div>
                <div class="status-item" style="font-weight:700;">Overall Status: <span id="qa-overall">-</span></div>
            </div>
            <!-- Progress bars for metrics -->
            <div style="margin-top:16px;">
                <div class="progress-bar">
                    <div class="progress-fill green" id="qa-lip-sync-bar" style="width:0%"></div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill green" id="qa-visual-bar" style="width:0%"></div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill green" id="qa-emotion-bar" style="width:0%"></div>
                </div>
            </div>
        </div>

        <!-- Artifact Detection -->
        <div class="card">
            <h3>Artifact Detection</h3>
            <div id="qa-artifacts">
                <div class="status-item">Pixel Jitter: <span id="qa-jitter">-</span> pixels</div>
                <div class="status-item">Frame Drops: <span id="qa-drops">-</span></div>
                <div class="status-item">Masking Errors: <span id="qa-mask-errors">-</span></div>
            </div>
        </div>

        <!-- Thermal Health -->
        <div class="card">
            <h3>Thermal Health</h3>
            <div id="qa-thermal">
                <div class="status-item">CPU Temperature: <span id="qa-cpu-temp">-</span>°C</div>
                <div class="status-item">GPU Temperature: <span id="qa-gpu-temp">-</span>°C</div>
            </div>
        </div>

        <!-- Warnings -->
        <div class="card" style="grid-column:1/-1;">
            <h3>Warnings & Alerts</h3>
            <div id="qa-warnings" style="font-size:.85em;color:var(--muted);">
                No warnings
            </div>
        </div>
    </div>
</div>

<!-- ══════ TAB 7: ACTIVE HARVEST ══════ -->
<div id="tab-harvester" class="tab-content">
    <div class="grid" style="max-width:900px;margin:0 auto;">
        <div class="card" style="grid-column:1/-1;">
            <h3>Platform Selection</h3>
            <p style="color:var(--muted);margin-bottom:16px;">Select a platform to start passive observation.</p>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;">
                <div class="platform-card" onclick="selectPlatform('teams')">
                    <span class="platform-icon">Teams</span>
                    <div><strong>Microsoft Teams</strong><br><small style="color:var(--muted)">Window auto-detect</small></div>
                </div>
                <div class="platform-card" onclick="selectPlatform('meet')">
                    <span class="platform-icon">Meet</span>
                    <div><strong>Google Meet</strong><br><small style="color:var(--muted)">Chrome tab capture</small></div>
                </div>
                <div class="platform-card" onclick="selectPlatform('zoom')">
                    <span class="platform-icon">Zoom</span>
                    <div><strong>Zoom</strong><br><small style="color:var(--muted)">Window auto-detect</small></div>
                </div>
                <div class="platform-card" onclick="selectPlatform('whatsapp')">
                    <span class="platform-icon">WA</span>
                    <div><strong>WhatsApp Desktop</strong><br><small style="color:var(--muted)">Desktop app</small></div>
                </div>
            </div>
        </div>

        <div class="card">
            <h3>Harvest Mode</h3>
            <select id="harvest-mode">
                <option value="my_voice_only">Save only my responses (Voice training)</option>
                <option value="customer_profiles">Save customer profiles (People CRM)</option>
                <option value="full_shadow">Full shadow (All data)</option>
            </select>
            <div class="controls-row">
                <button class="btn btn-accent" id="btn-harvest-start" onclick="startHarvester()">Start Harvesting</button>
                <button class="btn btn-stop" id="btn-harvest-stop" onclick="stopHarvester()" disabled>Stop</button>
            </div>
            <div id="harvest-status" style="margin-top:10px;font-size:.85em;color:var(--muted);"></div>
        </div>

        <div class="card">
            <h3>Harvest Stats</h3>
            <div id="harvest-stats">
                <div class="status-item">Platform: <span id="h-platform">None</span></div>
                <div class="status-item">Status: <span id="h-status">Inactive</span></div>
                <div class="status-item">Mode: <span id="h-mode">-</span></div>
            </div>
        </div>
    </div>
</div>

<!-- ══════ TAB 7: SETTINGS ══════ -->
<div id="tab-settings" class="tab-content">
    <div class="grid">
        <!-- Render Engine Selector (Progressive Architecture) -->
        <div class="card" style="border-left:4px solid var(--accent);">
            <h3>🎬 Render Engine Selector</h3>
            <p style="color:var(--muted);font-size:.85em;margin-bottom:12px;">
                Progressive render architecture: Start with Stitcher Mode for reliability, upgrade to Generative Mode for AI-driven video.
            </p>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Render Engine:</label>
                <select id="render-engine" onchange="switchRenderEngine()">
                    <option value="stitcher">Stitcher Mode (Pre-recorded Assets)</option>
                    <option value="generative">Generative Mode (LivePortrait/RunPod)</option>
                </select>
            </div>
            <div id="stitcher-info" style="padding:12px;background:rgba(78,204,163,.1);border-radius:8px;margin-bottom:12px;">
                <div style="font-weight:bold;margin-bottom:8px;color:var(--accent);">✅ Stitcher Mode</div>
                <div style="font-size:.85em;color:var(--muted);">
                    <div style="margin-bottom:4px;">• Uses pre-recorded assets (Idle, Nod, Laugh, Speak)</div>
                    <div style="margin-bottom:4px;">• 100% fail-safe - no AI dependencies</div>
                    <div style="margin-bottom:4px;">• Low latency, consistent performance</div>
                    <div>• Perfect for critical meetings where reliability matters</div>
                </div>
            </div>
            <div id="generative-info" style="padding:12px;background:rgba(233,69,96,.1);border-radius:8px;margin-bottom:12px;display:none;">
                <div style="font-weight:bold;margin-bottom:8px;color:var(--danger);">⚡ Generative Mode</div>
                <div style="font-size:.85em;color:var(--muted);">
                    <div style="margin-bottom:4px;">• LivePortrait AI for real-time lip-sync</div>
                    <div style="margin-bottom:4px;">• Requires GPU (RunPod) or local GPU</div>
                    <div style="margin-bottom:4px;">• Higher latency, more resource-intensive</div>
                    <div>• Best for casual meetings where AI novelty matters</div>
                </div>
            </div>
            <div class="controls-row">
                <button class="btn btn-accent" onclick="saveRenderEngine()">Save Render Engine</button>
            </div>
        </div>

        <!-- System Configuration -->
        <div class="card">
            <h3>System Configuration</h3>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Performance Mode:</label>
                <select id="perf-mode">
                    <option value="balanced">Balanced</option>
                    <option value="performance">Performance</option>
                    <option value="quality">Quality</option>
                </select>
            </div>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Thermal Guard:</label>
                <select id="thermal-guard">
                    <option value="enabled">Enabled (Auto-switch)</option>
                    <option value="disabled">Disabled</option>
                </select>
            </div>
            <div class="controls-row">
                <button class="btn btn-accent" onclick="saveSystemConfig()">Save Configuration</button>
            </div>
        </div>

        <!-- API Settings -->
        <div class="card" style="border-left:4px solid var(--warn);">
            <h3>🔑 API Settings</h3>
            <p style="color:var(--muted);font-size:.85em;margin-bottom:12px;">
                Configure external API keys and endpoints. These are saved to .env file.
            </p>
            
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Supabase URL:</label>
                <input type="text" id="api-supabase-url" placeholder="https://your-project.supabase.co" style="width:100%;">
            </div>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Supabase Service Role Key:</label>
                <input type="password" id="api-supabase-key" placeholder="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." style="width:100%;">
            </div>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">OpenAI API Key (optional):</label>
                <input type="password" id="api-openai-key" placeholder="sk-..." style="width:100%;">
            </div>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Groq API Key (optional):</label>
                <input type="password" id="api-groq-key" placeholder="gsk_..." style="width:100%;">
            </div>
            
            <div class="controls-row">
                <button class="btn btn-accent" onclick="saveAPISettings()">Save API Settings</button>
                <button class="btn btn-outline" onclick="loadAPISettings()">Load from .env</button>
            </div>
            
            <div id="api-status" style="margin-top:12px;font-size:.85em;color:var(--muted);"></div>
        </div>

        <!-- Prompts -->
        <div class="card">
            <h3>Prompt Management</h3>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Positive Prompt:</label>
                <input type="text" id="positive-prompt" placeholder="Add positive prompt" style="width:100%;">
                <button class="btn btn-accent" style="margin-top:6px;" onclick="addPrompt('positive')">Add Positive</button>
            </div>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Negative Prompt:</label>
                <input type="text" id="negative-prompt" placeholder="Add negative prompt" style="width:100%;">
                <button class="btn btn-danger" style="margin-top:6px;" onclick="addPrompt('negative')">Add Negative</button>
            </div>
            <div id="prompts-list" style="margin-top:12px;"></div>
        </div>

        <!-- File Uploads -->
        <div class="card">
            <h3>File Uploads</h3>
            <form id="upload-form" style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">File Type:</label>
                <select id="file-type">
                    <option value="document">Document (PDF/DOCX/XLS)</option>
                    <option value="outfit">Outfit Video (MP4)</option>
                    <option value="background">Background Image (JPG/PNG)</option>
                    <option value="audio">Audio Filler (WAV/MP3)</option>
                </select>
                <label style="font-size:.85em;color:var(--muted);">Category:</label>
                <select id="category">
                    <option value="general">General</option>
                    <option value="internal">Internal</option>
                    <option value="client">Client</option>
                </select>
                <input type="file" id="file-input" style="width:100%;">
                <button type="submit" class="btn btn-accent" style="margin-top:8px;">Upload</button>
            </form>
            <div id="upload-status" style="font-size:.85em;color:var(--muted);"></div>
        </div>

        <!-- Animation Mode -->
        <div class="card">
            <h3>Animation Mode</h3>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Current Mode:</label>
                <select id="anim-mode">
                    <option value="idle">Idle</option>
                    <option value="speaking">Speaking</option>
                    <option value="listening">Listening</option>
                </select>
            </div>
            <div class="controls-row">
                <button class="btn btn-accent" onclick="switchAnimationMode()">Switch Mode</button>
            </div>
        </div>

        <!-- Platform Selection -->
        <div class="card">
            <h3>Platform Selection</h3>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Meeting Platform:</label>
                <select id="platform-select">
                    <option value="teams">Microsoft Teams</option>
                    <option value="meet">Google Meet</option>
                    <option value="zoom">Zoom</option>
                    <option value="webex">Webex</option>
                    <option value="slack">Slack Huddles</option>
                </select>
            </div>
            <div class="controls-row">
                <button class="btn btn-accent" onclick="setPlatform()">Set Platform</button>
            </div>
        </div>

        <!-- Model Settings -->
        <div class="card">
            <h3>Model Settings</h3>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">LLM Model:</label>
                <select id="llm-model">
                    <option value="llama-3-8b">Llama 3 8B</option>
                    <option value="llama-3-70b">Llama 3 70B</option>
                    <option value="mistral-7b">Mistral 7B</option>
                </select>
            </div>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Temperature:</label>
                <input type="number" id="llm-temp" value="0.7" min="0" max="2" step="0.1" style="width:100%;">
            </div>
            <div class="controls-row">
                <button class="btn btn-accent" onclick="saveModelSettings()">Save Model Settings</button>
            </div>
        </div>

        <!-- Feature Toggles -->
        <div class="card" style="grid-column:1/-1;">
            <h3>Feature Toggles</h3>
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;">
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
                    <input type="checkbox" id="feat-speculative-ingest" checked>
                    <span>Speculative Ingest</span>
                </label>
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
                    <input type="checkbox" id="feat-streaming" checked>
                    <span>Streaming Pipeline</span>
                </label>
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
                    <input type="checkbox" id="feat-audio-preroll" checked>
                    <span>Audio Pre-roll</span>
                </label>
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
                    <input type="checkbox" id="feat-fact-verifier" checked>
                    <span>Hard Fact Verifier</span>
                </label>
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
                    <input type="checkbox" id="feat-active-steering" checked>
                    <span>Active Steering</span>
                </label>
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
                    <input type="checkbox" id="feat-swenglish" checked>
                    <span>Swenglish Buffer</span>
                </label>
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
                    <input type="checkbox" id="feat-strategic-lag" checked>
                    <span>Strategic Lag</span>
                </label>
                <label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
                    <input type="checkbox" id="feat-interruption" checked>
                    <span>Interruption Handler</span>
                </label>
            </div>
            <div class="controls-row" style="margin-top:12px;">
                <button class="btn btn-accent" onclick="saveFeatureToggles()">Save Toggles</button>
            </div>
        </div>
    </div>
</div>

<script>
// ═══════════════════════════════════════════════════════════════
// TAB SWITCHING
// ═══════════════════════════════════════════════════════════════
function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    event.target.classList.add('active');
    if (name === 'studio') { initStudio(); loadProgress(); }
    if (name === 'harvester') { loadHarvesterStatus(); }
}

// ═══════════════════════════════════════════════════════════════
// DASHBOARD (existing polling)
// ═══════════════════════════════════════════════════════════════
setInterval(async () => {
    try {
        const r = await fetch('/api/status'); const d = await r.json();
        document.getElementById('status-content').innerHTML = `
            <div class="status-item"><strong>State:</strong> ${d.state||'N/A'}</div>
            <div class="status-item"><strong>Speaker:</strong> ${d.active_speaker||'N/A'}</div>
            <div class="status-item"><strong>Emotion:</strong> ${d.emotion||'N/A'}</div>
            <div class="status-item"><strong>Keyword:</strong> ${d.last_keyword||'N/A'}</div>
            <div class="status-item"><strong>Platform:</strong> ${d.platform||'N/A'}</div>`;
    } catch(e){}
}, 2000);
setInterval(async () => {
    try {
        const r = await fetch('/api/agenda'); const d = await r.json();
        document.getElementById('agenda-content').innerHTML = d.map(i => `
            <div class="status-item" style="border-left:3px solid ${i.status==='agent_ready'?'var(--accent)':'var(--danger)'}">
            <strong>${i.time}</strong> - ${i.title} <small>(${i.type})</small></div>`).join('') || '<p style="color:var(--muted)">No meetings</p>';
    } catch(e){}
}, 5000);
setInterval(async () => {
    try {
        const r = await fetch('/api/logs'); const d = await r.json();
        document.getElementById('logs-content').innerHTML = d.slice(-30).reverse().map(l =>
            `<div class="log-item ${l.level.toLowerCase()}">[${l.timestamp?.substring(11,19)||''}] ${l.message}</div>`).join('') || 'No logs';
    } catch(e){}
}, 2000);

// ═══════════════════════════════════════════════════════════════
// STUDIO: WebCam + MediaRecorder
// ═══════════════════════════════════════════════════════════════
let mediaStream = null, mediaRecorder = null, recordingWs = null;
let recInterval = null, recStartTime = 0;
let currentSentenceIdx = 0, teleprompterData = [];

async function initStudio() {
    if (mediaStream) return;
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
            video: { width:1280, height:720, frameRate:20 },
            audio: { sampleRate:48000, channelCount:1 }
        });
        document.getElementById('webcam-preview').srcObject = mediaStream;
        startAudioMeter();
    } catch(e) {
        document.getElementById('rec-status').textContent = 'Camera access denied: ' + e.message;
    }
}

function startAudioMeter() {
    if (!mediaStream) return;
    const ctx = new AudioContext({ sampleRate: 48000 });
    const src = ctx.createMediaStreamSource(mediaStream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    src.connect(analyser);
    const buf = new Uint8Array(analyser.frequencyBinCount);

    function update() {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) { const v = (buf[i] - 128) / 128; sum += v * v; }
        const rms = Math.sqrt(sum / buf.length);
        const db = rms > 0.001 ? 20 * Math.log10(rms) : -60;
        const pct = Math.max(0, Math.min(100, (db + 60) / 60 * 100));
        const fill = document.getElementById('audio-meter-fill');
        fill.style.width = pct + '%';
        fill.className = 'audio-meter-fill ' + (db > -3 ? 'clip' : db > -12 ? 'hot' : 'ok');
        document.getElementById('audio-db').textContent = db.toFixed(1) + ' dB';
        requestAnimationFrame(update);
    }
    update();
}

async function loadTeleprompter() {
    const mode = document.getElementById('studio-mode').value;
    
    if (mode === 'stitcher_nodes') {
        renderStitcherNodesUI();
        return;
    }
    
    try {
        const r = await fetch('/api/studio/teleprompter/' + mode);
        const d = await r.json();
        teleprompterData = d.items || [];
        currentSentenceIdx = teleprompterData.findIndex(s => !s.done);
        if (currentSentenceIdx < 0) currentSentenceIdx = 0;
        renderTeleprompter();
    } catch(e) { console.error(e); }
}

function renderStitcherNodesUI() {
    const el = document.getElementById('teleprompter');
    el.innerHTML = `
        <div style="padding:12px;">
            <h4 style="margin-bottom:12px;color:var(--accent);">🎬 Stitcher Nodes Recording</h4>
            <p style="color:var(--muted);font-size:.85em;margin-bottom:16px;">
                Record pre-recorded assets for Stitcher Mode. These are fail-safe assets that don't require AI.
            </p>
            
            <div style="display:flex;flex-direction:column;gap:10px;">
                <div class="tp-sentence" onclick="selectStitcherNode('idle')" id="node-idle">
                    <span class="tp-emotion-tag neutral">IDLE</span>
                    Idle state (sitting still, blinking)
                </div>
                <div class="tp-sentence" onclick="selectStitcherNode('nod')" id="node-nod">
                    <span class="tp-emotion-tag enthusiastic">NOD</span>
                    Nodding agreement
                </div>
                <div class="tp-sentence" onclick="selectStitcherNode('laugh')" id="node-laugh">
                    <span class="tp-emotion-tag empathetic">LAUGH</span>
                    Laughing naturally
                </div>
                <div class="tp-sentence" onclick="selectStitcherNode('speak')" id="node-speak">
                    <span class="tp-emotion-tag serious">SPEAK</span>
                    Speaking state (mouth moving)
                </div>
            </div>
            
            <div style="margin-top:16px;padding:12px;background:rgba(78,204,163,.1);border-radius:8px;">
                <div style="font-weight:bold;margin-bottom:8px;color:var(--accent);">Recording Instructions:</div>
                <div style="font-size:.8em;color:var(--muted);">
                    <div style="margin-bottom:4px;">• Click a node to select it</div>
                    <div style="margin-bottom:4px;">• Press "REC" to start WebRTC recording</div>
                    <div style="margin-bottom:4px;">• Record 3-5 seconds for each node</div>
                    <div>• Assets saved to assets/video/stitcher_nodes/</div>
                </div>
            </div>
        </div>
    `;
    
    currentStitcherNode = 'idle';
    highlightStitcherNode('idle');
}

function selectStitcherNode(node) {
    currentStitcherNode = node;
    highlightStitcherNode(node);
}

function highlightStitcherNode(node) {
    // Remove current class from all nodes
    ['idle', 'nod', 'laugh', 'speak'].forEach(n => {
        const el = document.getElementById('node-' + n);
        if (el) el.classList.remove('current');
    });
    
    // Add current class to selected node
    const el = document.getElementById('node-' + node);
    if (el) el.classList.add('current');
}

function renderTeleprompter() {
    const el = document.getElementById('teleprompter');
    if (!teleprompterData.length) { el.innerHTML = '<p style="color:var(--muted)">No items</p>'; return; }
    el.innerHTML = teleprompterData.map((s, i) => {
        const cls = s.done ? 'done' : (i === currentSentenceIdx ? 'current' : '');
        const tag = s.emotion ? `<span class="tp-emotion-tag ${s.emotion}">${s.emotion}</span>` : '';
        const label = s.text || s.name || s.id || '';
        const sub = s.filename ? `<br><small style="color:var(--muted)">${s.filename}</small>` : '';
        return `<div class="tp-sentence ${cls}" onclick="selectSentence(${i})">${tag}${label}${sub}</div>`;
    }).join('');
    // Scroll current into view
    const cur = el.querySelector('.current');
    if (cur) cur.scrollIntoView({ behavior:'smooth', block:'center' });
}

function selectSentence(idx) {
    currentSentenceIdx = idx;
    renderTeleprompter();
}

async function startRecording() {
    if (!mediaStream) { await initStudio(); if (!mediaStream) return; }
    const mode = document.getElementById('studio-mode').value;
    const outfit = document.getElementById('studio-outfit').value;
    const item = teleprompterData[currentSentenceIdx] || {};

    // Tell server to start
    const params = new URLSearchParams({
        recording_type: mode, outfit: outfit,
        clip_id: item.id || item.category || '',
        emotion: item.emotion || '',
        sentence_index: item.emotion_index ?? item.index ?? 0
    });
    const r = await fetch('/api/studio/recording/start?' + params, { method:'POST' });
    const d = await r.json();
    if (d.error) { document.getElementById('rec-status').textContent = d.error; return; }

    // Open WebSocket for binary stream
    const wsProto = location.protocol === 'https:' ? 'wss' : 'ws';
    recordingWs = new WebSocket(`${wsProto}://${location.host}/ws/studio-recording`);
    recordingWs.binaryType = 'arraybuffer';

    // Start MediaRecorder
    const mimeType = mode.startsWith('wardrobe') ? 'video/webm;codecs=vp9,opus' : 'audio/webm;codecs=opus';
    mediaRecorder = new MediaRecorder(mediaStream, { mimeType });
    mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0 && recordingWs && recordingWs.readyState === 1) {
            e.data.arrayBuffer().then(buf => recordingWs.send(buf));
        }
    };
    mediaRecorder.start(250); // 250ms chunks

    // UI
    document.getElementById('rec-badge').style.display = 'block';
    document.getElementById('btn-rec').disabled = true;
    document.getElementById('btn-stop').disabled = false;
    recStartTime = Date.now();
    recInterval = setInterval(() => {
        const s = Math.floor((Date.now() - recStartTime) / 1000);
        document.getElementById('rec-timer').textContent =
            String(Math.floor(s/60)).padStart(2,'0') + ':' + String(s%60).padStart(2,'0');
    }, 200);
    document.getElementById('rec-status').textContent = 'Recording → ' + (d.output_path || '');
}

async function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
    if (recordingWs) { recordingWs.close(); recordingWs = null; }
    clearInterval(recInterval);

    const r = await fetch('/api/studio/recording/stop', { method:'POST' });
    const d = await r.json();

    // Mark sentence complete if voice mode
    const mode = document.getElementById('studio-mode').value;
    const item = teleprompterData[currentSentenceIdx];
    if (mode === 'voice_sentence' && item) {
        await fetch(`/api/studio/recording/mark-sentence?emotion=${item.emotion}&sentence_index=${item.emotion_index}`, { method:'POST' });
        item.done = true;
    }

    // UI reset
    document.getElementById('rec-badge').style.display = 'none';
    document.getElementById('btn-rec').disabled = false;
    document.getElementById('btn-stop').disabled = true;
    document.getElementById('rec-status').textContent = `Saved: ${d.output_path || ''} (${(d.file_size/1024).toFixed(1)} KB, ${d.duration_s?.toFixed(1)}s)`;

    // Advance teleprompter
    if (currentSentenceIdx < teleprompterData.length - 1) { currentSentenceIdx++; }
    renderTeleprompter();
    loadProgress();
}

function toggleGhost() {
    const ghost = document.getElementById('live-ghost');
    ghost.style.display = ghost.style.display === 'none' ? 'block' : 'none';
}

// ═══════════════════════════════════════════════════════════════
// TURING MIRROR (Phase 18)
// ═══════════════════════════════════════════════════════════════
async function setMirrorMode(mode) {
    // Update button states
    document.querySelectorAll('#tab-turing .btn').forEach(btn => btn.classList.remove('btn-accent'));
    event.target.classList.add('btn-accent');
    
    // Update mode display
    const modeNames = {
        'side_by_side': 'Side-by-Side',
        'ghost_overlay': 'Ghost Overlay',
        'lip_sync': 'Lip-Sync Analyzer',
        'uncanny': 'Uncanny Alert'
    };
    document.getElementById('mirror-mode').textContent = modeNames[mode];
    
    // Apply mode-specific UI changes
    const liveGhost = document.getElementById('live-ghost');
    if (mode === 'ghost_overlay') {
        liveGhost.style.display = 'block';
    } else {
        liveGhost.style.display = 'none';
    }
    
    // Call backend to set mode (placeholder)
    try {
        await fetch('/api/turing/mode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode })
        });
    } catch(e) {
        console.error('Failed to set mirror mode:', e);
    }
}

async function runSyncTest() {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Testing...';
    
    const startTime = Date.now();
    
    try {
        // Send test signal to Anton Egon
        const r = await fetch('/api/turing/sync-test', { method: 'POST' });
        const d = await r.json();
        
        const latency = Date.now() - startTime;
        document.getElementById('latency-ms').textContent = latency;
        
        // Color code latency
        const latencyEl = document.getElementById('latency-ms');
        if (latency < 200) {
            latencyEl.style.color = '#4ecca3';
        } else if (latency < 400) {
            latencyEl.style.color = '#ffd700';
        } else {
            latencyEl.style.color = '#e94560';
        }
        
        console.log('Sync test result:', d);
    } catch(e) {
        console.error('Sync test failed:', e);
        document.getElementById('latency-ms').textContent = 'Error';
    }
    
    btn.disabled = false;
    btn.textContent = 'Run Sync Test';
}

// Initialize live camera when Turing Mirror tab is opened
async function initTuringMirror() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        const video = document.getElementById('live-camera');
        video.srcObject = stream;
    } catch(e) {
        console.error('Failed to access camera:', e);
        document.getElementById('live-camera').poster = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" fill="%2316213e"/><text x="50" y="50" text-anchor="middle" fill="%238892b0" font-size="10">Camera unavailable</text></svg>');
    }
}

// ═══════════════════════════════════════════════════════════════
// HUMAN FLAWS (Phase 23)
// ═══════════════════════════════════════════════════════════════
async function toggleFlawsEngine() {
    const enabled = document.getElementById('flaws-enabled').checked;
    const status = document.getElementById('flaws-status');
    
    try {
        const r = await fetch('/api/flaws/toggle', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({enabled})
        });
        const d = await r.json();
        
        if (d.success) {
            status.textContent = enabled ? 'Engine is enabled' : 'Engine is disabled';
            status.style.color = enabled ? '#4ecca3' : '#e94560';
        } else {
            status.textContent = 'Error: ' + d.error;
        }
    } catch(e) {
        console.error('Failed to toggle engine:', e);
        status.textContent = 'Error: ' + e.message;
    }
}

async function saveFlawsConfig() {
    const config = {
        late_joiner_probability: parseInt(document.getElementById('late-joiner-prob').value) / 100,
        mute_glitcher_probability: parseInt(document.getElementById('mute-glitcher-prob').value) / 100,
        phone_caller_probability: parseInt(document.getElementById('phone-caller-prob').value) / 100,
        late_joiner_delay_minutes: parseInt(document.getElementById('late-delay').value),
        early_join_minutes: parseInt(document.getElementById('early-join').value)
    };
    
    // Update total display
    const total = config.late_joiner_probability + config.mute_glitcher_probability + config.phone_caller_probability;
    document.getElementById('prob-total').textContent = `Total: ${(total * 100).toFixed(0)}%`;
    
    try {
        const r = await fetch('/api/flaws/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        const d = await r.json();
        
        if (d.success) {
            alert('Configuration saved successfully');
        } else {
            alert('Error: ' + d.error);
        }
    } catch(e) {
        alert('Error: Failed to save configuration');
    }
}

async function rollJoinDice() {
    try {
        const r = await fetch('/api/flaws/roll-dice', {method: 'POST'});
        const d = await r.json();
        
        const resultDiv = document.getElementById('dice-result');
        resultDiv.textContent = `Rolled ${d.dice_roll}: ${d.scenario}`;
        resultDiv.style.color = '#ffd700';
        
        // Update current scenario
        document.getElementById('current-scenario').textContent = `Active: ${d.scenario} (Description: ${d.description})`;
    } catch(e) {
        document.getElementById('dice-result').textContent = 'Error: Failed to roll dice';
    }
}

// Load config when tab is opened
const originalSwitchTab2 = switchTab;
switchTab = function(tabId) {
    originalSwitchTab2(tabId);
    if (tabId === 'flaws') {
        loadFlawsConfig();
    }
};

async function loadFlawsConfig() {
    try {
        const r = await fetch('/api/flaws/config');
        const d = await r.json();
        
        if (d.config) {
            document.getElementById('flaws-enabled').checked = d.config.enabled;
            document.getElementById('late-joiner-prob').value = Math.round(d.config.late_joiner_probability * 100);
            document.getElementById('mute-glitcher-prob').value = Math.round(d.config.mute_glitcher_probability * 100);
            document.getElementById('phone-caller-prob').value = Math.round(d.config.phone_caller_probability * 100);
            document.getElementById('late-delay').value = d.config.late_joiner_delay_minutes;
            document.getElementById('early-join').value = d.config.early_join_minutes;
            
            const status = document.getElementById('flaws-status');
            status.textContent = d.config.enabled ? 'Engine is enabled' : 'Engine is disabled';
            status.style.color = d.config.enabled ? '#4ecca3' : '#e94560';
        }
    } catch(e) {
        console.error('Failed to load flaws config:', e);
    }
}

// ═══════════════════════════════════════════════════════════════
// SETUP WIZARD (Phase 22)
// ═══════════════════════════════════════════════════════════════
async function detectPlatform() {
    try {
        const r = await fetch('/api/setup/platform');
        const d = await r.json();
        document.getElementById('detected-platform').textContent = d.platform;
        document.getElementById('python-version').textContent = d.python_version;
        document.getElementById('os-info').textContent = d.os;
    } catch(e) {
        console.error('Failed to detect platform:', e);
        document.getElementById('detected-platform').textContent = 'Unknown';
    }
}

function confirmLightingSetup() {
    document.getElementById('lighting-status').textContent = 'Status: ✅ Confirmed';
    document.getElementById('lighting-status').style.color = '#4ecca3';
    console.log('Lighting setup confirmed');
}

async function testSupabaseConnection() {
    const url = document.getElementById('supabase-url').value;
    const key = document.getElementById('supabase-key').value;
    
    if (!url || !key) {
        document.getElementById('supabase-status').textContent = '❌ Please enter URL and Key';
        return;
    }
    
    document.getElementById('supabase-status').textContent = 'Testing connection...';
    
    try {
        const r = await fetch('/api/setup/test-supabase', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url, key})
        });
        const d = await r.json();
        
        if (d.success) {
            document.getElementById('supabase-status').textContent = '✅ Connected successfully!';
            document.getElementById('supabase-status').style.color = '#4ecca3';
        } else {
            document.getElementById('supabase-status').textContent = '❌ Connection failed: ' + (d.error || 'Unknown error');
            document.getElementById('supabase-status').style.color = '#ff6b6b';
        }
    } catch (e) {
        document.getElementById('supabase-status').textContent = '❌ Error: ' + e.message;
        document.getElementById('supabase-status').style.color = '#ff6b6b';
    }
}

function generateSupabaseSQL() {
    const sql = `-- Anton Egon Supabase Database Schema
-- Run this in your Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- People CRM table (contacts and face fingerprints)
CREATE TABLE IF NOT EXISTS people (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(255),
    company VARCHAR(255),
    role VARCHAR(255),
    face_fingerprint JSONB, -- 128-d vector from YOLO
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Meeting logs table
CREATE TABLE IF NOT EXISTS meeting_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform VARCHAR(50) NOT NULL, -- teams, zoom, google_meet, etc.
    meeting_id VARCHAR(255),
    title VARCHAR(255),
    participants JSONB, -- List of participant names
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    transcript TEXT,
    entities_extracted JSONB, -- Decisions, prices, dates, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Inbox messages table
CREATE TABLE IF NOT EXISTS inbox_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform VARCHAR(50) NOT NULL, -- teams, slack, email
    message_id VARCHAR(255),
    sender VARCHAR(255),
    subject VARCHAR(500),
    body TEXT,
    timestamp TIMESTAMP WITH TIME ZONE,
    is_read BOOLEAN DEFAULT FALSE,
    is_processed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Phrase library table
CREATE TABLE IF NOT EXISTS phrase_library (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phrase TEXT NOT NULL,
    category VARCHAR(100),
    usage_count INTEGER DEFAULT 0,
    last_used TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_people_email ON people(email);
CREATE INDEX IF NOT EXISTS idx_meeting_logs_platform ON meeting_logs(platform);
CREATE INDEX IF NOT EXISTS idx_meeting_logs_start_time ON meeting_logs(start_time);
CREATE INDEX IF NOT EXISTS idx_inbox_platform ON inbox_messages(platform);
CREATE INDEX IF NOT EXISTS idx_inbox_timestamp ON inbox_messages(timestamp);

-- Enable Row Level Security
ALTER TABLE people ENABLE ROW LEVEL SECURITY;
ALTER TABLE meeting_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE inbox_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE phrase_library ENABLE ROW LEVEL SECURITY;

-- Create policies (allow all for now - tighten in production)
CREATE POLICY "Allow all on people" ON people FOR ALL USING (true);
CREATE POLICY "Allow all on meeting_logs" ON meeting_logs FOR ALL USING (true);
CREATE POLICY "Allow all on inbox_messages" ON inbox_messages FOR ALL USING (true);
CREATE POLICY "Allow all on phrase_library" ON phrase_library FOR ALL USING (true);
`;
    
    document.getElementById('sql-script').value = sql;
    document.getElementById('sql-modal').style.display = 'flex';
}

function copySQLScript() {
    const textarea = document.getElementById('sql-script');
    textarea.select();
    document.execCommand('copy');
    alert('SQL script copied to clipboard!');
}

function closeSQLModal() {
    document.getElementById('sql-modal').style.display = 'none';
}

async function testGroqConnection() {
    const key = document.getElementById('groq-key').value;
    
    if (!key) {
        document.getElementById('groq-status').textContent = '❌ Please enter API Key';
        return;
    }
    
    try {
        const r = await fetch('/api/setup/test-groq', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({key})
        });
        const d = await r.json();
        
        if (d.success) {
            document.getElementById('groq-status').textContent = '✅ Connection successful';
            document.getElementById('groq-status').style.color = '#4ecca3';
        } else {
            document.getElementById('groq-status').textContent = '❌ ' + d.error;
            document.getElementById('groq-status').style.color = '#e94560';
        }
    } catch(e) {
        document.getElementById('groq-status').textContent = '❌ Connection failed';
        document.getElementById('groq-status').style.color = '#e94560';
    }
}

async function testTailscaleConnection() {
    const key = document.getElementById('tailscale-key').value;
    const ip = document.getElementById('cloud-ip').value;
    
    if (!key) {
        document.getElementById('tailscale-status').textContent = '❌ Please enter Auth Key';
        return;
    }
    
    try {
        const r = await fetch('/api/setup/test-tailscale', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({key, ip})
        });
        const d = await r.json();
        
        if (d.success) {
            document.getElementById('tailscale-status').textContent = '✅ Connection successful';
            document.getElementById('tailscale-status').style.color = '#4ecca3';
        } else {
            document.getElementById('tailscale-status').textContent = '❌ ' + d.error;
            document.getElementById('tailscale-status').style.color = '#e94560';
        }
    } catch(e) {
        document.getElementById('tailscale-status').textContent = '❌ Connection failed';
        document.getElementById('tailscale-status').style.color = '#e94560';
    }
}

async function saveConfiguration() {
    const config = {
        SUPABASE_URL: document.getElementById('supabase-url').value,
        SUPABASE_SERVICE_ROLE_KEY: document.getElementById('supabase-key').value,
        SUPABASE_ANON_KEY: document.getElementById('supabase-anon').value,
        GROQ_API_KEY: document.getElementById('groq-key').value,
        TAILSCALE_AUTH_KEY: document.getElementById('tailscale-key').value,
        CLOUD_SERVER_IP: document.getElementById('cloud-ip').value,
        MS_CLIENT_ID: document.getElementById('ms-client-id').value,
        MS_CLIENT_SECRET: document.getElementById('ms-secret').value,
        MS_TENANT_ID: document.getElementById('ms-tenant').value,
        SLACK_BOT_TOKEN: document.getElementById('slack-token').value,
        SMTP_PASSWORD: document.getElementById('smtp-password').value
    };
    
    try {
        const r = await fetch('/api/setup/save-config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        const d = await r.json();
        
        if (d.success) {
            document.getElementById('save-status').textContent = '✅ Configuration saved to .env';
            document.getElementById('save-status').style.color = '#4ecca3';
        } else {
            document.getElementById('save-status').textContent = '❌ ' + d.error;
            document.getElementById('save-status').style.color = '#e94560';
        }
    } catch(e) {
        document.getElementById('save-status').textContent = '❌ Failed to save configuration';
        document.getElementById('save-status').style.color = '#e94560';
    }
}

function downloadConfiguration() {
    const config = `# Anton Egon Environment Configuration
# Generated by Setup Wizard

SUPABASE_URL=${document.getElementById('supabase-url').value}
SUPABASE_SERVICE_ROLE_KEY=${document.getElementById('supabase-key').value}
SUPABASE_ANON_KEY=${document.getElementById('supabase-anon').value}

GROQ_API_KEY=${document.getElementById('groq-key').value}

TAILSCALE_AUTH_KEY=${document.getElementById('tailscale-key').value}
CLOUD_SERVER_IP=${document.getElementById('cloud-ip').value}

# Microsoft Calendar (Optional)
MS_CLIENT_ID=${document.getElementById('ms-client-id').value}
MS_CLIENT_SECRET=${document.getElementById('ms-secret').value}
MS_TENANT_ID=${document.getElementById('ms-tenant').value}

# Communication Platforms (Optional)
SLACK_BOT_TOKEN=${document.getElementById('slack-token').value}
SMTP_PASSWORD=${document.getElementById('smtp-password').value}
`;
    
    const blob = new Blob([config], {type: 'text/plain'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '.env';
    a.click();
    URL.revokeObjectURL(url);
}

async function testAllConnections() {
    await testSupabaseConnection();
    await testGroqConnection();
    await testTailscaleConnection();
}

// Hook into tab switching for all tabs
const originalSwitchTab = switchTab;
switchTab = function(tabId) {
    originalSwitchTab(tabId);
    if (tabId === 'setup') {
        detectPlatform();
    } else if (tabId === 'health') {
        loadQAReport();
    } else if (tabId === 'turing') {
        initTuringMirror();
    }
};

// ═══════════════════════════════════════════════════════════════
// SYSTEM HEALTH (Phase 18)
// ═══════════════════════════════════════════════════════════════
async function loadQAReport() {
    try {
        const r = await fetch('/api/qa/report');
        const d = await r.json();
        
        if (d.error) {
            document.getElementById('qa-report-status').textContent = d.error;
            return;
        }
        
        // Update metrics display
        const averages = d.averages || {};
        document.getElementById('qa-lip-sync').textContent = averages.lip_sync_accuracy?.toFixed(1) || '-';
        document.getElementById('qa-visual-stability').textContent = averages.visual_stability_score?.toFixed(1) || '-';
        document.getElementById('qa-latency').textContent = averages.response_latency_ms?.toFixed(0) || '-';
        document.getElementById('qa-emotion').textContent = averages.emotion_consistency_score?.toFixed(1) || '-';
        document.getElementById('qa-overall').textContent = d.overall_status || '-';
        
        // Update progress bars
        document.getElementById('qa-lip-sync-bar').style.width = (averages.lip_sync_accuracy || 0) + '%';
        document.getElementById('qa-visual-bar').style.width = (averages.visual_stability_score || 0) + '%';
        document.getElementById('qa-emotion-bar').style.width = (averages.emotion_consistency_score || 0) + '%';
        
        // Color code progress bars
        const lipSyncBar = document.getElementById('qa-lip-sync-bar');
        lipSyncBar.className = 'progress-fill ' + (averages.lip_sync_accuracy >= 90 ? 'green' : averages.lip_sync_accuracy >= 70 ? 'orange' : 'red');
        
        const visualBar = document.getElementById('qa-visual-bar');
        visualBar.className = 'progress-fill ' + (averages.visual_stability_score >= 95 ? 'green' : averages.visual_stability_score >= 80 ? 'orange' : 'red');
        
        const emotionBar = document.getElementById('qa-emotion-bar');
        emotionBar.className = 'progress-fill ' + (averages.emotion_consistency_score >= 85 ? 'green' : averages.emotion_consistency_score >= 70 ? 'orange' : 'red');
        
        // Update overall status color
        const overallEl = document.getElementById('qa-overall');
        overallEl.style.color = d.overall_status === 'pass' ? '#4ecca3' : d.overall_status === 'warning' ? '#ffd700' : '#e94560';
        
        document.getElementById('qa-report-status').textContent = `Report loaded: ${d.generated_at} (${d.total_samples} samples)`;
        
    } catch(e) {
        console.error('Failed to load QA report:', e);
        document.getElementById('qa-report-status').textContent = 'Failed to load report';
    }
}

async function runStressTest() {
    const btn = event.target;
    btn.disabled = true;
    document.getElementById('btn-stop-stress').disabled = false;
    document.getElementById('qa-report-status').textContent = 'Running stress test...';
    
    try {
        const r = await fetch('/api/qa/stress-test', { method: 'POST' });
        const d = await r.json();
        
        if (d.error) {
            document.getElementById('qa-report-status').textContent = d.error;
        } else {
            document.getElementById('qa-report-status').textContent = 'Stress test started';
        }
    } catch(e) {
        console.error('Failed to start stress test:', e);
        document.getElementById('qa-report-status').textContent = 'Failed to start stress test';
    }
    
    btn.disabled = false;
}

async function stopStressTest() {
    try {
        const r = await fetch('/api/qa/stop-test', { method: 'POST' });
        const d = await r.json();
        
        document.getElementById('qa-report-status').textContent = d.status || 'Test stopped';
        document.getElementById('btn-stop-stress').disabled = true;
        
        // Reload report after stopping
        await loadQAReport();
    } catch(e) {
        console.error('Failed to stop stress test:', e);
    }
}

// Hook into tab switching
const originalSwitchTab = switchTab;
switchTab = function(tabId) {
    originalSwitchTab(tabId);
    if (tabId === 'health') {
        loadQAReport();
    }
};

// Update ghost opacity in real-time
document.addEventListener('DOMContentLoaded', () => {
    const ghostOpacity = document.getElementById('ghost-opacity');
    if (ghostOpacity) {
        ghostOpacity.addEventListener('input', () => {
            const aiPreview = document.getElementById('ai-twin-preview');
            if (aiPreview) {
                aiPreview.style.opacity = ghostOpacity.value / 100;
            }
        });
    }
});

// PHYSICAL SETUP GUIDE (Sprint 5: Onboarding)
// ═══════════════════════════════════════════════════════════════
let completedSetupSteps = new Set();
const totalSetupSteps = 4;

function completeSetupStep(stepNumber) {
    completedSetupSteps.add(stepNumber);
    updateSetupProgress();
    
    // Mark step as completed visually
    const stepElement = document.querySelector(`.setup-step[data-step="${stepNumber}"]`);
    if (stepElement) {
        stepElement.style.opacity = '1';
        stepElement.style.borderLeftColor = '#4ecca3';
        const completeBtn = stepElement.querySelector('.btn-accent');
        if (completeBtn) {
            completeBtn.textContent = '✓ Completed';
            completeBtn.disabled = true;
        }
    }
    
    // Activate next step
    const nextStep = stepNumber + 1;
    const nextStepElement = document.querySelector(`.setup-step[data-step="${nextStep}"]`);
    if (nextStepElement) {
        nextStepElement.style.opacity = '1';
    }
}

function skipSetupStep(stepNumber) {
    updateSetupProgress();
    
    // Mark step as skipped
    const stepElement = document.querySelector(`.setup-step[data-step="${stepNumber}"]`);
    if (stepElement) {
        stepElement.style.opacity = '0.5';
        stepElement.style.borderLeftColor = '#666';
    }
    
    // Activate next step
    const nextStep = stepNumber + 1;
    const nextStepElement = document.querySelector(`.setup-step[data-step="${nextStep}"]`);
    if (nextStepElement) {
        nextStepElement.style.opacity = '1';
    }
}

function updateSetupProgress() {
    const progress = (completedSetupSteps.size / totalSetupSteps) * 100;
    const progressBar = document.getElementById('setup-progress-bar');
    const progressText = document.getElementById('setup-progress-text');
    
    if (progressBar) {
        progressBar.style.width = `${progress}%`;
    }
    
    if (progressText) {
        progressText.textContent = `${completedSetupSteps.size}/${totalSetupSteps} Complete`;
    }
}

// ANTON STORE (Fas 22: Billing Engine & Marketplace)
// ═══════════════════════════════════════════════════════════════
async function loadStoreBalance() {
    try {
        const r = await fetch('/api/billing/balance');
        const data = await r.json();
        
        document.getElementById('anton-credits').textContent = data.anton_credits || 0;
        document.getElementById('gpu-credits').textContent = `$${(data.gpu_credits || 0).toFixed(2)}`;
        document.getElementById('subscription-tier').textContent = data.subscription_tier || 'Freemium';
    } catch (e) {
        console.error(e);
    }
}

async function purchasePackage(packageId) {
    try {
        const r = await fetch('/api/billing/purchase', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({package: packageId})
        });
        const data = await r.json();
        
        if (data.success) {
            alert(`Successfully purchased ${packageId} package! ${data.credits} credits added.`);
            loadStoreBalance();
        } else {
            alert('Purchase failed: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function unlockPremiumWardrobe() {
    try {
        const r = await fetch('/api/billing/subscribe', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({tier: 'premium', feature: 'wardrobe'})
        });
        const data = await r.json();
        
        if (data.success) {
            alert('Premium Wardrobe unlocked! Enjoy your new items.');
            loadStoreBalance();
        } else {
            alert('Failed to unlock: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function unlockPremiumPranks() {
    try {
        const r = await fetch('/api/billing/subscribe', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({tier: 'premium', feature: 'pranks'})
        });
        const data = await r.json();
        
        if (data.success) {
            alert('Premium Pranks unlocked! Enjoy your new pranks.');
            loadStoreBalance();
        } else {
            alert('Failed to unlock: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

// Load store balance when tab is opened
document.addEventListener('DOMContentLoaded', () => {
    const storeTab = document.querySelector('button[onclick="switchTab(\'store\')"]');
    if (storeTab) {
        storeTab.addEventListener('click', loadStoreBalance);
    }
});

// SHADOWING UI (Fas 23: Ghostwriter Mode)
// ═══════════════════════════════════════════════════════════════
async function setGhostwriterMode(mode) {
    try {
        const r = await fetch('/api/ghostwriter/mode', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({mode})
        });
        const data = await r.json();
        
        if (data.success) {
            console.log(`Ghostwriter mode set to ${mode}`);
        }
    } catch (e) {
        console.error(e);
    }
}

async function activateGhostwriter() {
    try {
        const r = await fetch('/api/ghostwriter/activate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const data = await r.json();
        
        if (data.success) {
            document.getElementById('ghostwriter-status').textContent = 'Active';
            document.getElementById('ghostwriter-status').style.color = '#4ecca3';
            document.getElementById('meeting-id').textContent = data.meeting_id;
            console.log('Ghostwriter activated');
        }
    } catch (e) {
        alert('Error activating Ghostwriter: ' + e.message);
    }
}

async function deactivateGhostwriter() {
    try {
        const r = await fetch('/api/ghostwriter/deactivate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const data = await r.json();
        
        if (data.success) {
            document.getElementById('ghostwriter-status').textContent = 'Inactive';
            document.getElementById('ghostwriter-status').style.color = '#ff6b6b';
            document.getElementById('meeting-id').textContent = 'Not active';
            console.log('Ghostwriter deactivated');
        }
    } catch (e) {
        alert('Error deactivating Ghostwriter: ' + e.message);
    }
}

async function vetoIntervention() {
    try {
        const r = await fetch('/api/ghostwriter/veto', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({intervention_id: 'latest'})
        });
        const data = await r.json();
        
        if (data.success) {
            alert('Response vetoed');
            loadInterventions();
        }
    } catch (e) {
        alert('Error vetoing: ' + e.message);
    }
}

async function approveIntervention() {
    try {
        const r = await fetch('/api/ghostwriter/approve', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({intervention_id: 'latest'})
        });
        const data = await r.json();
        
        if (data.success) {
            alert('Response approved and sent');
            loadInterventions();
        }
    } catch (e) {
        alert('Error approving: ' + e.message);
    }
}

async function takeoverControl() {
    try {
        const r = await fetch('/api/ghostwriter/takeover', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const data = await r.json();
        
        if (data.success) {
            alert('Manual control activated');
            document.getElementById('ghostwriter-mode').value = 'passive';
        }
    } catch (e) {
        alert('Error taking control: ' + e.message);
    }
}

async function loadInterventions() {
    try {
        const r = await fetch('/api/ghostwriter/interventions');
        const data = await r.json();
        
        const container = document.getElementById('interventions-list');
        if (data.interventions && data.interventions.length > 0) {
            container.innerHTML = data.interventions.map(i => `
                <div class="card" style="padding:12px;border-left:3px solid var(--accent);">
                    <div style="font-weight:bold;margin-bottom:4px;">${i.trigger}</div>
                    <div style="font-size:.9em;margin-bottom:8px;">${i.suggested_response}</div>
                    <div style="font-size:.8em;color:var(--muted);">Confidence: ${Math.round(i.confidence * 100)}%</div>
                </div>
            `).join('');
        } else {
            container.innerHTML = '<div style="color:var(--muted);text-align:center;padding:24px;">No pending interventions</div>';
        }
    } catch (e) {
        console.error(e);
    }
}

// TURING PORTAL (Fas 24: Ground Truth Feedback)
// ═══════════════════════════════════════════════════════════════
let currentTuringSession = null;

// Update confidence display
document.addEventListener('DOMContentLoaded', () => {
    const confidenceSlider = document.getElementById('feedback-confidence');
    if (confidenceSlider) {
        confidenceSlider.addEventListener('input', () => {
            document.getElementById('confidence-value').textContent = confidenceSlider.value;
        });
    }
});

async function startNewTuringTest() {
    try {
        const r = await fetch('/api/turing/create-session', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const data = await r.json();
        
        if (data.success) {
            currentTuringSession = data.session_id;
            document.getElementById('feedback-session-id').value = data.session_id;
            document.getElementById('feedback-status').textContent = 'New test session started';
            document.getElementById('feedback-status').style.color = '#4ecca3';
        }
    } catch (e) {
        alert('Error starting test: ' + e.message);
    }
}

async function submitGroundTruthFeedback() {
    try {
        const sessionId = document.getElementById('feedback-session-id').value;
        const guess = document.getElementById('feedback-guess').value;
        const confidence = document.getElementById('feedback-confidence').value / 100;
        const feedback = document.getElementById('feedback-text').value;
        
        if (!sessionId || !guess) {
            alert('Please start a test and select your guess');
            return;
        }
        
        const r = await fetch('/api/turing/submit-feedback', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                session_id: sessionId,
                guess: guess,
                confidence: confidence,
                feedback: feedback
            })
        });
        const data = await r.json();
        
        if (data.success) {
            document.getElementById('feedback-status').textContent = 'Feedback submitted successfully!';
            document.getElementById('feedback-status').style.color = '#4ecca3';
            
            // Clear form
            document.getElementById('feedback-guess').value = '';
            document.getElementById('feedback-text').value = '';
        } else {
            alert('Failed to submit feedback: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

// BIOMETRICS & AI VIDEO GENERATION
// ═══════════════════════════════════════════════════════════════
let biometricsCameraStream = null;
let selectedVideoProvider = null;
let selectedCreditPackage = null;

// Provider selection
async function selectProvider(providerId) {
    try {
        const r = await fetch('/api/video-providers/set-active', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ provider: providerId })
        });
        const data = await r.json();
        
        if (data.success) {
            selectedVideoProvider = providerId;
            document.getElementById('selected-provider-info').style.display = 'block';
            document.getElementById('selected-provider-name').textContent = data.provider_name;
            document.getElementById('selected-provider-credits').textContent = data.credits;
            document.getElementById('selected-provider-price').textContent = data.price_per_second;
            
            document.getElementById('purchase-provider').textContent = data.provider_name;
            console.log('Provider selected:', providerId);
        } else {
            alert('Failed to select provider: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

// Credit package selection
function selectCreditPackage(credits) {
    selectedCreditPackage = credits;
    
    const prices = { 10: 1.00, 50: 4.50, 100: 8.00, 500: 35.00 };
    const price = prices[credits];
    
    document.getElementById('selected-package').textContent = credits;
    document.getElementById('package-price').textContent = price.toFixed(2);
    
    // Estimate video time based on average $0.05/sec
    const estSeconds = credits / 0.05;
    document.getElementById('est-video-time').textContent = Math.round(estSeconds) + 's';
    
    console.log('Credit package selected:', credits);
}

// Purchase credits
async function purchaseCredits() {
    if (!selectedVideoProvider || !selectedCreditPackage) {
        alert('Please select a provider and credit package');
        return;
    }
    
    try {
        const r = await fetch('/api/video-providers/purchase-credits', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                provider: selectedVideoProvider,
                credits: selectedCreditPackage
            })
        });
        const data = await r.json();
        
        if (data.success) {
            alert('Credits purchased successfully!');
            
            // Update UI
            document.getElementById('selected-provider-credits').textContent = data.new_balance;
            document.getElementById(`${selectedVideoProvider}-credits`).textContent = data.new_balance;
            
            // Clear selection
            selectedCreditPackage = null;
            document.getElementById('selected-package').textContent = '-';
            document.getElementById('package-price').textContent = '-';
            document.getElementById('est-video-time').textContent = '-';
        } else {
            alert('Failed to purchase credits: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

let biometricsCameraStream = null;

async function startBiometricsCamera() {
    try {
        biometricsCameraStream = await navigator.mediaDevices.getUserMedia({ video: true });
        const videoElement = document.getElementById('biometrics-camera');
        videoElement.srcObject = biometricsCameraStream;
        
        document.getElementById('scan-overlay').style.display = 'none';
        console.log('Biometrics camera started');
    } catch (e) {
        alert('Error starting camera: ' + e.message);
    }
}

function stopBiometricsCamera() {
    if (biometricsCameraStream) {
        biometricsCameraStream.getTracks().forEach(track => track.stop());
        biometricsCameraStream = null;
        document.getElementById('biometrics-camera').srcObject = null;
        document.getElementById('scan-overlay').style.display = 'flex';
        console.log('Biometrics camera stopped');
    }
}

async function startBiometricsScan() {
    try {
        document.getElementById('biometrics-status').textContent = 'Scanning...';
        
        const r = await fetch('/api/biometrics/scan', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });
        const data = await r.json();
        
        if (data.success) {
            document.getElementById('biometrics-status').textContent = 'Completed';
            document.getElementById('biometrics-status').style.color = '#4ecca3';
            document.getElementById('face-data-status').textContent = 'Scanned';
            document.getElementById('outfit-data-status').textContent = 'Scanned';
            document.getElementById('profile-id').textContent = data.profile_id;
            console.log('Biometrics scan completed:', data.profile_id);
        } else {
            alert('Failed to scan: ' + (data.error || 'Unknown error'));
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

async function generateAIVideo() {
    try {
        if (!selectedVideoProvider) {
            alert('Please select a video provider first');
            return;
        }
        
        const prompt = document.getElementById('ai-video-prompt').value;
        const duration = document.getElementById('video-duration').value;
        const quality = document.getElementById('video-quality').value;
        
        if (!prompt) {
            alert('Please enter a prompt');
            return;
        }
        
        document.getElementById('gen-status').textContent = 'Generating...';
        document.getElementById('gen-progress').textContent = '0%';
        
        const r = await fetch('/api/video-providers/generate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                prompt: prompt,
                duration: duration,
                quality: quality
            })
        });
        const data = await r.json();
        
        if (data.success) {
            document.getElementById('gen-status').textContent = 'Completed';
            document.getElementById('gen-progress').textContent = '100%';
            document.getElementById('gen-output').textContent = data.output_file;
            console.log('Video generated:', data.output_file);
            
            // Update credits display
            const r2 = await fetch('/api/video-providers/status');
            const status = await r2.json();
            if (status[selectedVideoProvider]) {
                document.getElementById('selected-provider-credits').textContent = status[selectedVideoProvider].credits;
                document.getElementById(`${selectedVideoProvider}-credits`).textContent = status[selectedVideoProvider].credits;
            }
        } else {
            alert('Failed to generate video: ' + (data.error || 'Unknown error'));
            document.getElementById('gen-status').textContent = 'Failed';
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

function useTemplate(templateId) {
    const templates = {
        'water_pour': 'Person reaches for a glass of water on the table and accidentally pours it over themselves',
        'clown_nose': 'Person picks up a red clown nose and puts it on their face',
        'surprised': 'Person suddenly looks surprised with mouth open and eyes wide',
        'yawn': 'Person lets out a big yawn during the meeting'
    };
    
    document.getElementById('ai-video-prompt').value = templates[templateId] || '';
}

// ═══════════════════════════════════════════════════════════════
async function loadProgress() {
    try {
        const r = await fetch('/api/studio/progress');
        const d = await r.json();
        // Video
        const vp = d.video || {};
        let vh = '';
        for (const [outfit, info] of Object.entries(vp.per_outfit || {})) {
            const pct = info.total ? Math.round(info.done / info.total * 100) : 0;
            vh += `<div style="margin-bottom:4px;font-size:.82em;">${outfit.replace('outfit_','')}</div>
                   <div class="progress-bar"><div class="progress-fill ${pct>=100?'green':'orange'}" style="width:${pct}%">${info.done}/${info.total}</div></div>`;
        }
        document.getElementById('video-progress').innerHTML = vh || 'No data';

        // Audio
        const ap = d.audio || {};
        let ah = '';
        for (const [emo, info] of Object.entries(ap.per_emotion || {})) {
            const pct = info.total ? Math.round(info.done / info.total * 100) : 0;
            ah += `<div style="margin-bottom:4px;font-size:.82em;">${emo}</div>
                   <div class="progress-bar"><div class="progress-fill ${pct>=100?'green':'orange'}" style="width:${pct}%">${info.done}/${info.total}</div></div>`;
        }
        document.getElementById('audio-progress').innerHTML = ah || 'No data';

        // Preroll
        const pp = d.preroll || {};
        const ppct = pp.total ? Math.round(pp.done / pp.total * 100) : 0;
        document.getElementById('preroll-progress').innerHTML =
            `<div class="progress-bar"><div class="progress-fill ${ppct>=100?'green':'orange'}" style="width:${ppct}%">${pp.done}/${pp.total}</div></div>`;
    } catch(e) { console.error(e); }
}

// ═══════════════════════════════════════════════════════════════
// HARVESTER
// ═══════════════════════════════════════════════════════════════
let selectedPlatform = null;

function selectPlatform(p) {
    selectedPlatform = p;
    document.querySelectorAll('.platform-card').forEach(c => c.classList.remove('active'));
    event.currentTarget.classList.add('active');
}

async function startHarvester() {
    if (!selectedPlatform) { document.getElementById('harvest-status').textContent = 'Select a platform first'; return; }
    const mode = document.getElementById('harvest-mode').value;
    const r = await fetch(`/api/studio/harvester/start?platform=${selectedPlatform}&mode=${mode}`, { method:'POST' });
    const d = await r.json();
    document.getElementById('harvest-status').textContent = d.message || 'Started';
    document.getElementById('btn-harvest-start').disabled = true;
    document.getElementById('btn-harvest-stop').disabled = false;
    loadHarvesterStatus();
}

async function stopHarvester() {
    await fetch('/api/studio/harvester/stop', { method:'POST' });
    document.getElementById('harvest-status').textContent = 'Stopped';
    document.getElementById('btn-harvest-start').disabled = false;
    document.getElementById('btn-harvest-stop').disabled = true;
    loadHarvesterStatus();
}

async function loadHarvesterStatus() {
    try {
        const r = await fetch('/api/studio/harvester/status');
        const d = await r.json();
        document.getElementById('h-platform').textContent = d.platform || 'None';
        document.getElementById('h-status').textContent = d.active ? 'Active' : 'Inactive';
        document.getElementById('h-mode').textContent = d.mode || '-';
    } catch(e){}
}

// ═══════════════════════════════════════════════════════════════
// UNIFIED INBOX
// ═══════════════════════════════════════════════════════════════
let currentInboxFilter = 'all';

async function loadInboxStats() {
    try {
        const r = await fetch('/api/inbox/stats');
        const d = await r.json();
        document.getElementById('inbox-stats').innerHTML = `
            <div class="status-item">Total: <span>${d.total_messages}</span></div>
            <div class="status-item">Unread: <span>${d.unread_messages}</span></div>
            <div class="status-item">Flagged: <span>${d.flagged_messages}</span></div>
            <div class="status-item">Drafts: <span>${d.pending_drafts}</span></div>
        `;
    } catch(e) {}
}

async function filterInbox(filter) {
    currentInboxFilter = filter;
    try {
        const r = await fetch(`/api/inbox/messages?filter=${filter}`);
        const d = await r.json();
        renderInboxMessages(d);
    } catch(e) {}
}

function renderInboxMessages(messages) {
    const container = document.getElementById('inbox-messages');
    if (!messages || messages.length === 0) {
        container.innerHTML = '<p style="color:var(--muted);">No messages found</p>';
        return;
    }
    
    container.innerHTML = messages.map(m => `
        <div class="inbox-message" style="padding:12px;border-bottom:1px solid var(--border);${m.is_read ? 'opacity:0.6;' : ''}">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                    <strong>${m.sender}</strong>
                    <span style="font-size:.8em;color:var(--muted);margin-left:8px;">${m.platform}</span>
                    ${m.priority === 'URGENT' ? '<span style="background:var(--danger);color:#fff;padding:2px 6px;border-radius:4px;font-size:.7em;margin-left:8px;">URGENT</span>' : ''}
                </div>
                <div style="font-size:.8em;color:var(--muted);">${new Date(m.timestamp).toLocaleString()}</div>
            </div>
            <div style="margin-top:8px;">${m.content}</div>
            ${m.ai_summary ? `<div style="margin-top:8px;font-size:.85em;color:var(--muted);">AI Summary: ${m.ai_summary}</div>` : ''}
            <div style="margin-top:8px;display:flex;gap:8px;">
                <button class="btn" style="padding:4px 8px;font-size:.8em;" onclick="replyToMessage('${m.message_id}')">Reply</button>
                <button class="btn" style="padding:4px 8px;font-size:.8em;" onclick="markAsRead('${m.message_id}')">${m.is_read ? 'Mark Unread' : 'Mark Read'}</button>
                <button class="btn" style="padding:4px 8px;font-size:.8em;" onclick="flagMessage('${m.message_id}')">${m.is_flagged ? 'Unflag' : 'Flag'}</button>
            </div>
        </div>
    `).join('');
}

async function markAsRead(messageId) {
    await fetch(`/api/inbox/messages/${messageId}/read`, { method:'POST' });
    loadInboxStats();
    filterInbox(currentInboxFilter);
}

async function flagMessage(messageId) {
    await fetch(`/api/inbox/messages/${messageId}/flag`, { method:'POST' });
    loadInboxStats();
    filterInbox(currentInboxFilter);
}

async function replyToMessage(messageId) {
    // TODO: Open reply modal
    alert('Reply modal coming soon');
}

// Load inbox when tab is activated
function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    event.target.classList.add('active');
    if (name === 'studio') { initStudio(); loadProgress(); }
    if (name === 'inbox') { loadInboxStats(); filterInbox('all'); }
    if (name === 'phrases') { loadPhraseStats(); loadPhrases(); }
    if (name === 'chaos') { loadProps(); loadOverlays(); }
}

// ═══════════════════════════════════════════════════════════════
// PHRASE LIBRARY
// ═══════════════════════════════════════════════════════════════
let currentPhraseFilter = 'all';

async function loadPhraseStats() {
    try {
        const r = await fetch('/api/phrases/stats');
        const d = await r.json();
        document.getElementById('phrase-stats').innerHTML = `
            <div class="status-item">Total: <span>${d.total_phrases}</span></div>
            <div class="status-item">Categories: <span>${Object.keys(d.categories).length}</span></div>
        `;
    } catch(e) {}
}

async function loadPhrases(filter = 'all') {
    currentPhraseFilter = filter;
    try {
        const r = await fetch(`/api/phrases?filter=${filter}`);
        const d = await r.json();
        renderPhrases(d);
    } catch(e) {}
}

function renderPhrases(phrases) {
    const container = document.getElementById('phrase-list');
    if (!phrases || phrases.length === 0) {
        container.innerHTML = '<p style="color:var(--muted);">No phrases found</p>';
        return;
    }
    
    container.innerHTML = phrases.map(p => `
        <div class="inbox-message" style="padding:12px;border-bottom:1px solid var(--border);">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                    <strong>${p.text}</strong>
                    <span style="font-size:.8em;color:var(--muted);margin-left:8px;">${p.category}</span>
                    <span style="font-size:.8em;color:var(--muted);margin-left:8px;">${p.trigger_mood}</span>
                </div>
                <div style="font-size:.8em;color:var(--muted);">Freq: ${p.frequency}</div>
            </div>
            ${p.notes ? `<div style="margin-top:8px;font-size:.85em;color:var(--muted);">${p.notes}</div>` : ''}
            <div style="margin-top:8px;display:flex;gap:8px;">
                <button class="btn" style="padding:4px 8px;font-size:.8em;" onclick="editPhrase('${p.id}')">Edit</button>
                <button class="btn" style="padding:4px 8px;font-size:.8em;" onclick="deletePhrase('${p.id}')">Delete</button>
            </div>
        </div>
    `).join('');
}

async function addPhrase() {
    const phrase = {
        text: document.getElementById('phrase-text').value,
        category: document.getElementById('phrase-category').value,
        trigger_mood: document.getElementById('phrase-mood').value,
        frequency: parseFloat(document.getElementById('phrase-frequency').value),
        notes: document.getElementById('phrase-notes').value
    };
    
    await fetch('/api/phrases', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(phrase)
    });
    
    loadPhraseStats();
    loadPhrases(currentPhraseFilter);
}

async function importDefaultPhrases() {
    await fetch('/api/phrases/import', { method: 'POST' });
    loadPhraseStats();
    loadPhrases(currentPhraseFilter);
}

async function deletePhrase(id) {
    await fetch(`/api/phrases/${id}`, { method: 'DELETE' });
    loadPhraseStats();
    loadPhrases(currentPhraseFilter);
}

async function editPhrase(id) {
    alert('Edit modal coming soon');
}

function filterPhrases(filter) {
    loadPhrases(filter);
}

// ═══════════════════════════════════════════════════════════════
// CHAOS DASHBOARD
// ═══════════════════════════════════════════════════════════════
async function loadProps() {
    try {
        const r = await fetch('/api/props');
        const d = await r.json();
        const container = document.getElementById('prop-controls');
        container.innerHTML = d.map(p => `
            <div class="card" style="padding:12px;cursor:pointer;${p.enabled ? 'border:2px solid var(--accent);' : ''}" onclick="toggleProp('${p.id}')">
                <strong>${p.name}</strong>
                <div style="font-size:.8em;color:var(--muted);margin-top:4px;">${p.prop_type}</div>
            </div>
        `).join('');
    } catch(e) {}
}

async function loadOverlays() {
    try {
        const r = await fetch('/api/overlays');
        const d = await r.json();
        const container = document.getElementById('overlay-controls');
        container.innerHTML = d.map(o => `
            <div class="card" style="padding:12px;">
                <strong>${o.name}</strong>
                <div style="font-size:.8em;color:var(--muted);margin-top:4px;">${o.overlay_type}</div>
                <button class="btn" style="margin-top:8px;width:100%;" onclick="triggerOverlay('${o.id}')">Trigger</button>
            </div>
        `).join('');
    } catch(e) {}
}

async function toggleProp(id) {
    await fetch(`/api/props/${id}/toggle`, { method: 'POST' });
    loadProps();
}

async function triggerOverlay(id) {
    await fetch(`/api/overlays/${id}/trigger`, { method: 'POST' });
}

async function clearAllProps() {
    await fetch('/api/props/clear', { method: 'POST' });
    loadProps();
}

async function stopAllOverlays() {
    await fetch('/api/overlays/clear', { method: 'POST' });
}

// ═══════════════════════════════════════════════════════════════
// SETTINGS
// ═══════════════════════════════════════════════════════════════
async function switchRenderEngine() {
    const engine = document.getElementById('render-engine').value;
    const stitcherInfo = document.getElementById('stitcher-info');
    const generativeInfo = document.getElementById('generative-info');
    
    if (engine === 'stitcher') {
        stitcherInfo.style.display = 'block';
        generativeInfo.style.display = 'none';
    } else {
        stitcherInfo.style.display = 'none';
        generativeInfo.style.display = 'block';
    }
}

async function saveRenderEngine() {
    const engine = document.getElementById('render-engine').value;
    try {
        const r = await fetch('/api/render-engine', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({engine})
        });
        const d = await r.json();
        if (d.success) {
            alert(`Render engine set to ${engine}`);
        } else {
            alert('Error: ' + d.error);
        }
    } catch(e) {
        console.error('Failed to save render engine:', e);
        alert('Failed to save render engine (backend not connected)');
    }
}

async function saveSystemConfig() {
    const config = {
        render_mode: document.getElementById('render-mode').value,
        performance_mode: document.getElementById('perf-mode').value,
        thermal_guard: document.getElementById('thermal-guard').value === 'enabled'
    };
    // TODO: Send to backend
    alert('Configuration saved (placeholder - backend integration needed)');
}

async function saveAPISettings() {
    const settings = {
        supabase_url: document.getElementById('api-supabase-url').value,
        supabase_key: document.getElementById('api-supabase-key').value,
        openai_key: document.getElementById('api-openai-key').value,
        groq_key: document.getElementById('api-groq-key').value
    };
    
    try {
        const r = await fetch('/api/settings/save', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(settings)
        });
        const d = await r.json();
        
        const statusEl = document.getElementById('api-status');
        if (d.success) {
            statusEl.textContent = '✅ API settings saved to .env file';
            statusEl.style.color = '#4ecca3';
        } else {
            statusEl.textContent = '❌ Error: ' + d.error;
            statusEl.style.color = '#e94560';
        }
    } catch(e) {
        console.error('Failed to save API settings:', e);
        const statusEl = document.getElementById('api-status');
        statusEl.textContent = '❌ Failed to save (backend not connected)';
        statusEl.style.color = '#e94560';
    }
}

async function loadAPISettings() {
    try {
        const r = await fetch('/api/settings/load');
        const d = await r.json();
        
        if (d.success) {
            document.getElementById('api-supabase-url').value = d.settings.supabase_url || '';
            document.getElementById('api-supabase-key').value = d.settings.supabase_key || '';
            document.getElementById('api-openai-key').value = d.settings.openai_key || '';
            document.getElementById('api-groq-key').value = d.settings.groq_key || '';
            
            const statusEl = document.getElementById('api-status');
            statusEl.textContent = '✅ API settings loaded from .env file';
            statusEl.style.color = '#4ecca3';
        } else {
            const statusEl = document.getElementById('api-status');
            statusEl.textContent = '❌ Error: ' + d.error;
            statusEl.style.color = '#e94560';
        }
    } catch(e) {
        console.error('Failed to load API settings:', e);
        const statusEl = document.getElementById('api-status');
        statusEl.textContent = '❌ Failed to load (backend not connected)';
        statusEl.style.color = '#e94560';
    }
}

async function addPrompt(type) {
    const input = document.getElementById(type + '-prompt');
    const value = input.value.trim();
    if (!value) return;
    // TODO: Send to backend
    const list = document.getElementById('prompts-list');
    const tag = document.createElement('div');
    tag.style.cssText = 'margin:4px 0;padding:6px;background:var(--border);border-radius:4px;font-size:.85em;';
    tag.innerHTML = `<span style="color:${type==='positive'?'var(--accent)':'var(--danger)'}">[${type.toUpperCase()}]</span> ${value}`;
    list.appendChild(tag);
    input.value = '';
}

async function switchAnimationMode() {
    const mode = document.getElementById('anim-mode').value;
    // TODO: Send to backend
    alert(`Animation mode switched to ${mode} (placeholder - backend integration needed)`);
}

async function setPlatform() {
    const platform = document.getElementById('platform-select').value;
    // TODO: Send to backend
    alert(`Platform set to ${platform} (placeholder - backend integration needed)`);
}

async function saveModelSettings() {
    const settings = {
        model: document.getElementById('llm-model').value,
        temperature: parseFloat(document.getElementById('llm-temp').value)
    };
    // TODO: Send to backend
    alert('Model settings saved (placeholder - backend integration needed)');
}

async function saveFeatureToggles() {
    const toggles = {
        speculative_ingest: document.getElementById('feat-speculative-ingest').checked,
        streaming: document.getElementById('feat-streaming').checked,
        audio_preroll: document.getElementById('feat-audio-preroll').checked,
        fact_verifier: document.getElementById('feat-fact-verifier').checked,
        active_steering: document.getElementById('feat-active-steering').checked,
        swenglish: document.getElementById('feat-swenglish').checked,
        strategic_lag: document.getElementById('feat-strategic-lag').checked,
        interruption: document.getElementById('feat-interruption').checked
    };
    // TODO: Send to backend
    alert('Feature toggles saved (placeholder - backend integration needed)');
}

// Initialize first tab on page load
document.addEventListener('DOMContentLoaded', function() {
    switchTab('dashboard');
});
</script>
</body>
</html>
        """
    
    def update_status(self, status_data: Dict[str, Any]):
        """Update status data"""
        self.status_data = status_data
        logger.debug(f"Status updated: {status_data.get('state', 'unknown')}")
    
    def update_daily_agenda(self, agenda: List[Dict[str, Any]]):
        """Update daily agenda"""
        self.daily_agenda = agenda
        logger.debug(f"Agenda updated: {len(agenda)} meetings")
    
    def update_emotions(self, emotions: Dict[str, str]):
        """Update emotion data"""
        self.emotions = emotions
    
    def add_log(self, level: str, message: str):
        """Add log entry"""
        self.logs.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message
        })
        
        if len(self.logs) > 100:
            self.logs.pop(0)
    
    async def start(self):
        """Start web dashboard server"""
        logger.info(f"Starting web dashboard on {self.host}:{self.port}")
        
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
    
    async def stop(self):
        """Stop web dashboard server"""
        logger.info("Stopping web dashboard")


async def main():
    """Test web dashboard"""
    dashboard = WebDashboard(host="127.0.0.1", port=8000)
    
    # Test data
    dashboard.update_status({
        "state": "listening",
        "active_speaker": "John Doe",
        "emotion": "neutral",
        "last_keyword": "budget",
        "names": ["John Doe", "Jane Smith"],
        "platform": "teams",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    dashboard.update_daily_agenda([
        {
            "time": "09:00",
            "title": "Kundmöte",
            "status": "agent_ready",
            "type": "digital",
            "outfit": "skjorta"
        },
        {
            "time": "13:00",
            "title": "Lunchmöte City",
            "status": "human_required",
            "type": "physical",
            "outfit": "N/A"
        }
    ])
    
    dashboard.update_emotions({"John Doe": "neutral", "Jane Smith": "happy"})
    
    await dashboard.start()


if __name__ == "__main__":
    asyncio.run(main())
