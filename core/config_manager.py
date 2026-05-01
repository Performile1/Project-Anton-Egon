#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Centralized Configuration Manager
Manages all configuration including render mode selection
"""

import json
import sys
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from enum import Enum

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class RenderMode(Enum):
    """Rendering modes"""
    LOCAL_FULL = "LOCAL_FULL"          # RTX mode - LivePortrait on local GPU
    CLOUD_POWER = "CLOUD_POWER"        # Thin client mode - Cloud rendering
    HYBRID_PLACEHOLDER = "HYBRID_PLACEHOLDER"  # Emergency mode - CPU-based placeholder


class ConfigManager:
    """
    Centralized configuration manager
    Handles all configuration loading and updating
    """
    
    def __init__(self):
        self.main_config_path = Path("config/settings.json")
        self.system_config_path = Path("config/system_config.yaml")
        self.mood_config_path = Path("memory/mood/current_mood.json")
        
        self.main_config: Dict[str, Any] = {}
        self.system_config: Dict[str, Any] = {}
        self.mood_config: Dict[str, Any] = {}
        
        self._load_all_configs()
    
    def _load_all_configs(self):
        """Load all configuration files"""
        self._load_main_config()
        self._load_system_config()
        self._load_mood_config()
    
    def _load_main_config(self):
        """Load main configuration"""
        if not self.main_config_path.exists():
            logger.warning(f"Main config not found: {self.main_config_path}")
            self.main_config = self._get_default_main_config()
            return
        
        try:
            with open(self.main_config_path, "r") as f:
                self.main_config = json.load(f)
            logger.info("Main config loaded")
        except Exception as e:
            logger.error(f"Error loading main config: {e}")
            self.main_config = self._get_default_main_config()
    
    def _load_system_config(self):
        """Load system configuration"""
        if not self.system_config_path.exists():
            logger.warning(f"System config not found: {self.system_config_path}")
            self.system_config = {}
            return
        
        try:
            with open(self.system_config_path, "r") as f:
                self.system_config = yaml.safe_load(f)
            logger.info("System config loaded")
        except Exception as e:
            logger.error(f"Error loading system config: {e}")
            self.system_config = {}
    
    def _load_mood_config(self):
        """Load mood configuration"""
        if not self.mood_config_path.exists():
            logger.warning(f"Mood config not found: {self.mood_config_path}")
            self.mood_config = {}
            return
        
        try:
            with open(self.mood_config_path, "r") as f:
                self.mood_config = json.load(f)
            logger.info("Mood config loaded")
        except Exception as e:
            logger.error(f"Error loading mood config: {e}")
            self.mood_config = {}
    
    def _get_default_main_config(self) -> Dict[str, Any]:
        """Get default main configuration"""
        return {
            "project": "Anton Egon",
            "version": "1.0.0",
            "phase": "1",
            "orchestrator": {
                "render_mode": "auto",
                "platform": "teams"
            },
            "cloud_server": {
                "url": "ws://localhost:8080",
                "timeout": 30,
                "max_reconnect_attempts": 5
            }
        }
    
    def get_render_mode(self) -> RenderMode:
        """
        Determine render mode based on configuration and system capabilities
        
        Returns:
            RenderMode enum
        """
        orchestrator_config = self.main_config.get("orchestrator", {})
        render_mode_str = orchestrator_config.get("render_mode", "auto")
        
        if render_mode_str == "auto":
            # Auto-select based on system capabilities
            return self._auto_select_render_mode()
        else:
            # Use specified mode
            try:
                return RenderMode[render_mode_str.upper()]
            except KeyError:
                logger.warning(f"Invalid render mode: {render_mode_str}, using auto")
                return self._auto_select_render_mode()
    
    def _auto_select_render_mode(self) -> RenderMode:
        """
        Auto-select render mode based on system capabilities
        
        Returns:
            RenderMode enum
        """
        gpu_available = self.system_config.get("gpu", {}).get("available", False)
        vram_gb = 0
        
        if gpu_available:
            vrams = self.system_config.get("vram", {}).get("gpus", [])
            if vrams:
                vram_gb = max([g.get("total_gb", 0) for g in vrams])
        
        network = self.system_config.get("network", {})
        ping_ms = network.get("ping_ms", None)
        internet = network.get("internet", False)
        
        # Decision logic
        if gpu_available and vram_gb >= 8:
            # Powerful GPU - use local full power
            logger.info(f"Auto-selected LOCAL_FULL (GPU with {vram_gb}GB VRAM)")
            return RenderMode.LOCAL_FULL
        elif gpu_available and vram_gb >= 4:
            # Mid-range GPU - can use local
            logger.info(f"Auto-selected LOCAL_FULL (GPU with {vram_gb}GB VRAM)")
            return RenderMode.LOCAL_FULL
        elif internet and ping_ms and ping_ms < 100:
            # Good internet - use cloud
            logger.info(f"Auto-selected CLOUD_POWER (ping: {ping_ms}ms)")
            return RenderMode.CLOUD_POWER
        elif internet:
            # Internet available but slow ping - use cloud
            logger.info("Auto-selected CLOUD_POWER (internet available)")
            return RenderMode.CLOUD_POWER
        else:
            # No internet or GPU - use placeholder
            logger.info("Auto-selected HYBRID_PLACEHOLDER (no GPU or internet)")
            return RenderMode.HYBRID_PLACEHOLDER
    
    def set_render_mode(self, mode: RenderMode):
        """
        Set render mode in configuration
        
        Args:
            mode: RenderMode to set
        """
        orchestrator_config = self.main_config.get("orchestrator", {})
        orchestrator_config["render_mode"] = mode.value
        self.main_config["orchestrator"] = orchestrator_config
        
        self._save_main_config()
        logger.info(f"Render mode set to {mode.value}")
    
    def _save_main_config(self):
        """Save main configuration"""
        with open(self.main_config_path, "w") as f:
            json.dump(self.main_config, f, indent=2)
        logger.info("Main config saved")
    
    def get_cloud_server_config(self) -> Dict[str, Any]:
        """Get cloud server configuration"""
        return self.main_config.get("cloud_server", {})
    
    def get_orchestrator_config(self) -> Dict[str, Any]:
        """Get orchestrator configuration"""
        return self.main_config.get("orchestrator", {})
    
    def get_mood(self) -> str:
        """Get current mood"""
        return self.mood_config.get("current_mood", "neutral")
    
    def get_all_configs(self) -> Dict[str, Any]:
        """Get all configurations"""
        return {
            "main": self.main_config,
            "system": self.system_config,
            "mood": self.mood_config,
            "render_mode": self.get_render_mode().value
        }
    
    def reload_configs(self):
        """Reload all configurations"""
        logger.info("Reloading all configurations...")
        self._load_all_configs()
        logger.info("Configurations reloaded")


def main():
    """Test config manager"""
    from loguru import logger
    
    logger.add("logs/config_manager_{time}.log", rotation="10 MB")
    
    # Create config manager
    manager = ConfigManager()
    
    # Get render mode
    render_mode = manager.get_render_mode()
    logger.info(f"Render mode: {render_mode.value}")
    
    # Get all configs
    configs = manager.get_all_configs()
    logger.info(f"Configs loaded: {list(configs.keys())}")
    
    logger.info("Config manager test complete")


if __name__ == "__main__":
    main()
