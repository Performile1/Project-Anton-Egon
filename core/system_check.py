#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - System Check & Capability Detection
Detects system capabilities and determines optimal rendering mode
"""

import os
import sys
import platform
import subprocess
import time
from typing import Dict, Any, Optional
from pathlib import Path
import yaml

from loguru import logger

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class SystemCapabilities:
    """System capability detection"""
    
    def __init__(self):
        self.capabilities: Dict[str, Any] = {}
    
    def detect_all(self) -> Dict[str, Any]:
        """Run all detection checks"""
        logger.info("Running system capability detection...")
        
        self.capabilities = {
            "os": self._detect_os(),
            "cpu": self._detect_cpu(),
            "ram": self._detect_ram(),
            "gpu": self._detect_gpu(),
            "vram": self._detect_vram(),
            "python": self._detect_python(),
            "network": self._detect_network(),
            "disk_space": self._detect_disk_space()
        }
        
        self._determine_render_mode()
        
        return self.capabilities
    
    def _detect_os(self) -> Dict[str, str]:
        """Detect operating system"""
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor()
        }
    
    def _detect_cpu(self) -> Dict[str, Any]:
        """Detect CPU information"""
        try:
            import psutil
            return {
                "cores_physical": psutil.cpu_count(logical=False),
                "cores_logical": psutil.cpu_count(logical=True),
                "frequency_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None
            }
        except ImportError:
            logger.warning("psutil not available, skipping CPU detection")
            return {"error": "psutil not available"}
    
    def _detect_ram(self) -> Dict[str, Any]:
        """Detect RAM information"""
        try:
            import psutil
            ram = psutil.virtual_memory()
            return {
                "total_gb": round(ram.total / (1024**3), 2),
                "available_gb": round(ram.available / (1024**3), 2),
                "percent_used": ram.percent
            }
        except ImportError:
            logger.warning("psutil not available, skipping RAM detection")
            return {"error": "psutil not available"}
    
    def _detect_gpu(self) -> Dict[str, Any]:
        """Detect GPU information"""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                gpus = []
                for i in range(gpu_count):
                    gpus.append({
                        "name": torch.cuda.get_device_name(i),
                        "compute_capability": torch.cuda.get_device_capability(i),
                        "memory_total_gb": round(torch.cuda.get_device_properties(i).total_memory / (1024**3), 2)
                    })
                return {"available": True, "count": gpu_count, "gpus": gpus}
            else:
                return {"available": False, "reason": "CUDA not available"}
        except ImportError:
            logger.warning("torch not available, skipping GPU detection")
            return {"error": "torch not available"}
    
    def _detect_vram(self) -> Dict[str, Any]:
        """Detect VRAM (Video RAM)"""
        try:
            import torch
            if torch.cuda.is_available():
                vram = []
                for i in range(torch.cuda.device_count()):
                    props = torch.cuda.get_device_properties(i)
                    vram.append({
                        "device": i,
                        "total_gb": round(props.total_memory / (1024**3), 2),
                        "free_gb": round(torch.cuda.memory_reserved(i) / (1024**3), 2)
                    })
                return {"available": True, "gpus": vram}
            else:
                return {"available": False}
        except ImportError:
            return {"error": "torch not available"}
    
    def _detect_python(self) -> Dict[str, str]:
        """Detect Python version"""
        return {
            "version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler()
        }
    
    def _detect_network(self) -> Dict[str, Any]:
        """Detect network capabilities"""
        network = {
            "internet": self._check_internet(),
            "ping": None,
            "bandwidth": None
        }
        
        if network["internet"]:
            # Test ping to common server
            try:
                import ping3
                ping_ms = ping3.ping("8.8.8.8", timeout=2)
                if ping_ms:
                    network["ping_ms"] = round(ping_ms * 1000, 2)
            except ImportError:
                logger.warning("ping3 not available, skipping ping test")
        
        return network
    
    def _check_internet(self) -> bool:
        """Check if internet is available"""
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False
    
    def _detect_disk_space(self) -> Dict[str, Any]:
        """Detect disk space"""
        try:
            import shutil
            disk = shutil.disk_usage("/")
            return {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "used_percent": round((disk.used / disk.total) * 100, 2)
            }
        except Exception as e:
            logger.error(f"Error detecting disk space: {e}")
            return {"error": str(e)}
    
    def _determine_render_mode(self) -> str:
        """Determine optimal render mode based on capabilities"""
        gpu_available = self.capabilities.get("gpu", {}).get("available", False)
        vram = self.capabilities.get("vram", {}).get("available", False)
        vram_gb = 0
        if vram:
            gpu_vrams = self.capabilities.get("vram", {}).get("gpus", [])
            if gpu_vrams:
                vram_gb = max([g.get("total_gb", 0) for g in gpu_vrams])
        
        ram_gb = self.capabilities.get("ram", {}).get("total_gb", 0)
        ping_ms = self.capabilities.get("network", {}).get("ping_ms", None)
        
        # Decision logic
        if gpu_available and vram_gb >= 8:
            # Powerful GPU - use local rendering
            render_mode = "LOCAL"
            reason = f"NVIDIA GPU with {vram_gb}GB VRAM detected - Local rendering recommended"
        elif gpu_available and vram_gb >= 4:
            # Mid-range GPU - can use local but might struggle
            render_mode = "LOCAL"
            reason = f"NVIDIA GPU with {vram_gb}GB VRAM detected - Local rendering possible (may be slow)"
        elif ping_ms and ping_ms < 100:
            # Good internet but weak GPU - use cloud
            render_mode = "CLOUD"
            reason = f"Low latency internet ({ping_ms}ms) detected - Cloud rendering recommended"
        else:
            # Fallback to cloud if internet available
            internet = self.capabilities.get("network", {}).get("internet", False)
            if internet:
                render_mode = "CLOUD"
                reason = "Internet available - Cloud rendering as fallback"
            else:
                render_mode = "LOCAL"
                reason = "No internet available - Local rendering (will be slow)"
        
        self.capabilities["render_mode"] = {
            "mode": render_mode,
            "reason": reason
        }
        
        return render_mode
    
    def save_config(self, config_path: str = "config/system_config.yaml"):
        """Save system configuration to YAML file"""
        config_dir = Path(config_path).parent
        if not config_dir.exists():
            config_dir.mkdir(parents=True)
        
        with open(config_path, "w") as f:
            yaml.dump(self.capabilities, f, default_flow_style=False)
        
        logger.info(f"System configuration saved to {config_path}")
    
    def print_summary(self):
        """Print system capability summary"""
        print("\n" + "="*80)
        print("  SYSTEM CAPABILITY SUMMARY")
        print("="*80 + "\n")
        
        print(f"OS: {self.capabilities['os']['system']} {self.capabilities['os']['release']}")
        print(f"Python: {self.capabilities['python']['version']}")
        
        if "error" not in self.capabilities.get("cpu", {}):
            print(f"CPU: {self.capabilities['cpu']['cores_physical']} physical / {self.capabilities['cpu']['cores_logical']} logical cores")
        
        if "error" not in self.capabilities.get("ram", {}):
            print(f"RAM: {self.capabilities['ram']['total_gb']} GB total, {self.capabilities['ram']['available_gb']} GB available")
        
        gpu = self.capabilities.get("gpu", {})
        if gpu.get("available"):
            print(f"GPU: {gpu['count']} GPU(s) detected")
            for i, gpu_info in enumerate(gpu.get("gpus", [])):
                print(f"  GPU {i}: {gpu_info['name']} ({gpu_info['memory_total_gb']} GB VRAM)")
        else:
            print(f"GPU: Not available or CUDA not installed")
        
        network = self.capabilities.get("network", {})
        if network.get("internet"):
            ping = network.get("ping_ms")
            if ping:
                print(f"Network: Internet available (ping: {ping}ms)")
            else:
                print(f"Network: Internet available (ping test failed)")
        else:
            print(f"Network: Internet not available")
        
        print(f"\n{'='*80}")
        render_mode = self.capabilities.get("render_mode", {})
        print(f"  RECOMMENDED RENDER MODE: {render_mode.get('mode', 'UNKNOWN')}")
        print(f"  Reason: {render_mode.get('reason', 'Unknown')}")
        print("="*80 + "\n")


def main():
    """Main function to run system check"""
    from loguru import logger
    
    logger.add("logs/system_check_{time}.log", rotation="10 MB")
    
    print("\n" + "="*80)
    print("  ANTON EGON - SYSTEM CAPABILITY DETECTION")
    print("="*80 + "\n")
    
    checker = SystemCapabilities()
    capabilities = checker.detect_all()
    checker.print_summary()
    
    # Save configuration
    checker.save_config()
    
    logger.info("System check complete")
    
    return capabilities


if __name__ == "__main__":
    main()
