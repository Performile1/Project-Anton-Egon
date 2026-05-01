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
                env_content = "# Anton Egon Environment Configuration\n"
                env_content += "# Generated by Setup Wizard\n\n"
                
                for key, value in config.items():
                    if value:  # Only add non-empty values
                        env_content += f"{key}={value}\n"
                
                env_path.write_text(env_content)
                
                return {"success": True, "message": "Configuration saved to .env"}
            except Exception as e:
                logger.error(f"Failed to save configuration: {e}")
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
    <button class="tab-btn" onclick="switchTab('turing')">Turing Mirror</button>
    <button class="tab-btn" onclick="switchTab('health')">System Health</button>
    <button class="tab-btn" onclick="switchTab('studio')">The Studio</button>
    <button class="tab-btn" onclick="switchTab('harvester')">Active Harvest</button>
    <button class="tab-btn" onclick="switchTab('settings')">Settings</button>
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
            
            <!-- Setup Steps -->
            <div id="setup-steps">
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

<!-- ══════ TAB 1: DASHBOARD ══════ -->
<div id="tab-dashboard" class="tab-content active">
    <div class="grid">
        <div class="card"><h3>Status</h3><div id="status-content">Loading...</div></div>
        <div class="card"><h3>Daily Agenda</h3><div id="agenda-content">Loading...</div></div>
        <div class="card"><h3>Emotions</h3><div id="emotions-content">Loading...</div></div>
        <div class="card"><h3>Recent Logs</h3><div id="logs-content" style="max-height:300px;overflow-y:auto;">Loading...</div></div>
    </div>
</div>

<!-- ══════ TAB 2: UNIFIED INBOX ══════ -->
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
        <!-- System Configuration -->
        <div class="card">
            <h3>System Configuration</h3>
            <div style="margin-bottom:12px;">
                <label style="font-size:.85em;color:var(--muted);">Render Mode:</label>
                <select id="render-mode">
                    <option value="placeholder">Placeholder (Text only)</option>
                    <option value="liveportrait">LivePortrait (Lip-sync)</option>
                    <option value="warp">WARP (Neural)</option>
                </select>
            </div>
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
    try {
        const r = await fetch('/api/studio/teleprompter/' + mode);
        const d = await r.json();
        teleprompterData = d.items || [];
        currentSentenceIdx = teleprompterData.findIndex(s => !s.done);
        if (currentSentenceIdx < 0) currentSentenceIdx = 0;
        renderTeleprompter();
    } catch(e) { console.error(e); }
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

async function testSupabaseConnection() {
    const url = document.getElementById('supabase-url').value;
    const key = document.getElementById('supabase-key').value;
    
    if (!url || !key) {
        document.getElementById('supabase-status').textContent = '❌ Please enter URL and Key';
        return;
    }
    
    try {
        const r = await fetch('/api/setup/test-supabase', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({url, key})
        });
        const d = await r.json();
        
        if (d.success) {
            document.getElementById('supabase-status').textContent = '✅ Connection successful';
            document.getElementById('supabase-status').style.color = '#4ecca3';
        } else {
            document.getElementById('supabase-status').textContent = '❌ ' + d.error;
            document.getElementById('supabase-status').style.color = '#e94560';
        }
    } catch(e) {
        document.getElementById('supabase-status').textContent = '❌ Connection failed';
        document.getElementById('supabase-status').style.color = '#e94560';
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

function toggleGhost() {
    const img = document.getElementById('ghost-img');
    if (img.style.display === 'none') {
        const outfit = document.getElementById('studio-outfit').value;
        img.src = '/api/studio/ghost/' + outfit;
        img.style.display = 'block';
    } else {
        img.style.display = 'none';
    }
}

// ═══════════════════════════════════════════════════════════════
// STUDIO: Progress
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
async function saveSystemConfig() {
    const config = {
        render_mode: document.getElementById('render-mode').value,
        performance_mode: document.getElementById('perf-mode').value,
        thermal_guard: document.getElementById('thermal-guard').value === 'enabled'
    };
    // TODO: Send to backend
    alert('Configuration saved (placeholder - backend integration needed)');
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
