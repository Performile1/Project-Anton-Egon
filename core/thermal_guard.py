#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Phase 7.1: Thermal Guard
Monitors CPU/GPU temperature and system resources
Auto-switches to HYBRID_PLACEHOLDER if system is overheating
"""

import sys
import asyncio
import platform
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timezone
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class ThermalState(Enum):
    """System thermal states"""
    COOL = "cool"            # < 60°C - All systems go
    WARM = "warm"            # 60-75°C - Normal operation
    HOT = "hot"              # 75-85°C - Reduce workload
    CRITICAL = "critical"    # > 85°C - Emergency measures


class ThermalGuardConfig(BaseModel):
    """Configuration for Thermal Guard"""
    check_interval: float = Field(default=5.0, description="Temperature check interval in seconds")
    cpu_warm_threshold: float = Field(default=60.0, description="CPU warm threshold (°C)")
    cpu_hot_threshold: float = Field(default=75.0, description="CPU hot threshold (°C)")
    cpu_critical_threshold: float = Field(default=85.0, description="CPU critical threshold (°C)")
    gpu_warm_threshold: float = Field(default=65.0, description="GPU warm threshold (°C)")
    gpu_hot_threshold: float = Field(default=80.0, description="GPU hot threshold (°C)")
    gpu_critical_threshold: float = Field(default=90.0, description="GPU critical threshold (°C)")
    ram_warning_percent: float = Field(default=85.0, description="RAM usage warning threshold (%)")
    auto_switch_placeholder: bool = Field(default=True, description="Auto-switch to placeholder on critical")


class ThermalGuard:
    """
    Thermal Guard - Hardware Health Monitor
    Monitors CPU/GPU temperature, RAM usage, and system resources
    Triggers automatic mode switching when system is under stress
    """
    
    def __init__(self, config: ThermalGuardConfig, on_thermal_event: Optional[Callable] = None):
        """
        Initialize Thermal Guard
        
        Args:
            config: Thermal Guard configuration
            on_thermal_event: Callback when thermal state changes
        """
        self.config = config
        self.on_thermal_event = on_thermal_event
        
        # State
        self.running = False
        self.monitor_task = None
        self.current_state = ThermalState.COOL
        self.previous_state = ThermalState.COOL
        
        # Readings
        self.cpu_temp: float = 0.0
        self.gpu_temp: float = 0.0
        self.cpu_percent: float = 0.0
        self.ram_percent: float = 0.0
        self.ram_used_gb: float = 0.0
        
        # Excuses for switching to placeholder
        self.thermal_excuses = [
            "Ursäkta, min dator kämpar lite med video-strömmen, jag stänger av kameran så ni hör mig bättre.",
            "Jag har lite problem med anslutningen, jag stänger av videon tillfälligt.",
            "Min fläkt låter som en jetmotor, jag pausar videon en stund.",
            "Lite teknikstrul här, jag kör utan video en stund."
        ]
        self._excuse_index = 0
        
        # Check if psutil is available
        self._psutil_available = False
        try:
            import psutil
            self._psutil_available = True
        except ImportError:
            logger.warning("psutil not available - CPU/RAM monitoring disabled. Install: pip install psutil")
        
        # Check if GPUtil is available
        self._gputil_available = False
        try:
            import GPUtil
            self._gputil_available = True
        except ImportError:
            logger.warning("GPUtil not available - GPU monitoring disabled. Install: pip install gputil")
        
        logger.info(f"Thermal Guard initialized (psutil: {self._psutil_available}, GPUtil: {self._gputil_available})")
    
    def _read_cpu_temperature(self) -> float:
        """
        Read CPU temperature
        
        Returns:
            CPU temperature in °C (0.0 if unavailable)
        """
        if not self._psutil_available:
            return 0.0
        
        try:
            import psutil
            
            # Try to get CPU temperature
            temps = psutil.sensors_temperatures()
            
            if not temps:
                return 0.0
            
            # Different systems report temps under different keys
            for key in ['coretemp', 'cpu_thermal', 'k10temp', 'acpitz']:
                if key in temps:
                    entries = temps[key]
                    if entries:
                        # Return highest temperature
                        return max(entry.current for entry in entries)
            
            # Fallback: use first available sensor
            for key, entries in temps.items():
                if entries:
                    return max(entry.current for entry in entries)
            
            return 0.0
            
        except Exception as e:
            logger.debug(f"CPU temperature read error: {e}")
            return 0.0
    
    def _read_gpu_temperature(self) -> float:
        """
        Read GPU temperature
        
        Returns:
            GPU temperature in °C (0.0 if unavailable)
        """
        if not self._gputil_available:
            return 0.0
        
        try:
            import GPUtil
            
            gpus = GPUtil.getGPUs()
            if gpus:
                return max(gpu.temperature for gpu in gpus)
            
            return 0.0
            
        except Exception as e:
            logger.debug(f"GPU temperature read error: {e}")
            return 0.0
    
    def _read_system_resources(self) -> Dict[str, float]:
        """
        Read CPU and RAM usage
        
        Returns:
            Dictionary with cpu_percent, ram_percent, ram_used_gb
        """
        if not self._psutil_available:
            return {"cpu_percent": 0.0, "ram_percent": 0.0, "ram_used_gb": 0.0}
        
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory()
            
            return {
                "cpu_percent": cpu_percent,
                "ram_percent": ram.percent,
                "ram_used_gb": ram.used / (1024 ** 3)
            }
            
        except Exception as e:
            logger.debug(f"System resources read error: {e}")
            return {"cpu_percent": 0.0, "ram_percent": 0.0, "ram_used_gb": 0.0}
    
    def _determine_thermal_state(self) -> ThermalState:
        """
        Determine current thermal state based on readings
        
        Returns:
            Current thermal state
        """
        # Check CPU temperature
        if self.cpu_temp >= self.config.cpu_critical_threshold:
            return ThermalState.CRITICAL
        elif self.cpu_temp >= self.config.cpu_hot_threshold:
            return ThermalState.HOT
        elif self.cpu_temp >= self.config.cpu_warm_threshold:
            return ThermalState.WARM
        
        # Check GPU temperature
        if self.gpu_temp >= self.config.gpu_critical_threshold:
            return ThermalState.CRITICAL
        elif self.gpu_temp >= self.config.gpu_hot_threshold:
            return ThermalState.HOT
        elif self.gpu_temp >= self.config.gpu_warm_threshold:
            return ThermalState.WARM
        
        # Check RAM usage
        if self.ram_percent >= self.config.ram_warning_percent:
            return ThermalState.HOT
        
        return ThermalState.COOL
    
    def get_thermal_excuse(self) -> str:
        """
        Get a natural excuse for switching to placeholder mode
        
        Returns:
            Excuse text
        """
        excuse = self.thermal_excuses[self._excuse_index % len(self.thermal_excuses)]
        self._excuse_index += 1
        return excuse
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Thermal Guard monitoring started")
        
        while self.running:
            try:
                # Read temperatures
                self.cpu_temp = self._read_cpu_temperature()
                self.gpu_temp = self._read_gpu_temperature()
                
                # Read system resources
                resources = self._read_system_resources()
                self.cpu_percent = resources["cpu_percent"]
                self.ram_percent = resources["ram_percent"]
                self.ram_used_gb = resources["ram_used_gb"]
                
                # Determine thermal state
                new_state = self._determine_thermal_state()
                
                # Check for state change
                if new_state != self.current_state:
                    self.previous_state = self.current_state
                    self.current_state = new_state
                    
                    logger.info(f"Thermal state changed: {self.previous_state.value} -> {new_state.value}")
                    logger.info(f"  CPU: {self.cpu_temp:.1f}°C | GPU: {self.gpu_temp:.1f}°C | RAM: {self.ram_percent:.1f}%")
                    
                    # Trigger callback
                    if self.on_thermal_event:
                        event_data = {
                            "state": new_state.value,
                            "previous_state": self.previous_state.value,
                            "cpu_temp": self.cpu_temp,
                            "gpu_temp": self.gpu_temp,
                            "cpu_percent": self.cpu_percent,
                            "ram_percent": self.ram_percent,
                            "ram_used_gb": self.ram_used_gb,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                        
                        # Add excuse if critical
                        if new_state == ThermalState.CRITICAL:
                            event_data["excuse"] = self.get_thermal_excuse()
                            event_data["action"] = "switch_to_placeholder"
                        elif new_state == ThermalState.HOT:
                            event_data["action"] = "reduce_workload"
                        
                        self.on_thermal_event(event_data)
                
                # Wait before next check
                await asyncio.sleep(self.config.check_interval)
                
            except Exception as e:
                logger.error(f"Thermal monitoring error: {e}")
                await asyncio.sleep(self.config.check_interval)
    
    async def start(self):
        """Start thermal monitoring"""
        if self.running:
            return
        
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Thermal Guard started")
    
    async def stop(self):
        """Stop thermal monitoring"""
        self.running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Thermal Guard stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current thermal status
        
        Returns:
            Status dictionary
        """
        return {
            "thermal_state": self.current_state.value,
            "cpu_temp": self.cpu_temp,
            "gpu_temp": self.gpu_temp,
            "cpu_percent": self.cpu_percent,
            "ram_percent": self.ram_percent,
            "ram_used_gb": round(self.ram_used_gb, 2),
            "psutil_available": self._psutil_available,
            "gputil_available": self._gputil_available,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


async def main():
    """Test the Thermal Guard"""
    from loguru import logger
    
    logger.add("logs/thermal_guard_{time}.log", rotation="10 MB")
    
    def on_thermal_event(event_data):
        logger.info(f"Thermal event: {event_data}")
    
    # Create guard
    config = ThermalGuardConfig()
    guard = ThermalGuard(config, on_thermal_event=on_thermal_event)
    
    # Start monitoring
    await guard.start()
    
    # Run for 15 seconds
    logger.info("Monitoring for 15 seconds...")
    await asyncio.sleep(15)
    
    # Get status
    status = guard.get_status()
    logger.info(f"Thermal status: {status}")
    
    # Stop monitoring
    await guard.stop()
    
    logger.info("Thermal Guard test complete")


if __name__ == "__main__":
    asyncio.run(main())
