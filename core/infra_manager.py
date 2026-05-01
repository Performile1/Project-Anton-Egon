#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Cloud Infrastructure Manager
Manages external GPU resources from multiple providers (RunPod, Vast.ai, Lambda Labs, Paperspace, etc.)
"""

import os
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
import aiohttp
import json

from loguru import logger
from pydantic import BaseModel

# Cloud Bridge integration
try:
    from core.cloud_bridge import TailscaleManager
    CLOUD_BRIDGE_AVAILABLE = True
except ImportError:
    CLOUD_BRIDGE_AVAILABLE = False


class GPUProvider(Enum):
    """GPU Provider options"""
    RUNPOD = "runpod"
    VAST_AI = "vast_ai"
    LAMBDA_LABS = "lambda_labs"
    PAPERSPACE = "paperspace"
    MODAL = "modal"
    TENSORDOCK = "tensordock"
    GOOGLE_VERTEX = "google_vertex"
    LOCAL = "local"


class GPUType(Enum):
    """GPU Types with recommended use cases"""
    RTX_4090 = "rtx_4090"  # 1080p, high quality
    RTX_4080 = "rtx_4080"  # 1080p, good quality
    RTX_3090 = "rtx_3090"  # 1080p, good value
    RTX_3060 = "rtx_3060"  # 720p, budget
    A100 = "a100"  # Enterprise, 4K
    H100 = "h100"  # Enterprise, 4K+


class ProviderConfig(BaseModel):
    """Configuration for a GPU provider"""
    provider: GPUProvider
    api_key: str
    region: Optional[str] = None
    enabled: bool = True


class InstanceStatus(Enum):
    """Instance status"""
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    READY = "ready"


class GPUInstance:
    """GPU Instance representation"""
    def __init__(
        self,
        instance_id: str,
        provider: GPUProvider,
        gpu_type: GPUType,
        status: InstanceStatus,
        ip_address: Optional[str] = None,
        hourly_cost: float = 0.0,
        region: str = "us-east-1"
    ):
        self.instance_id = instance_id
        self.provider = provider
        self.gpu_type = gpu_type
        self.status = status
        self.ip_address = ip_address
        self.hourly_cost = hourly_cost
        self.region = region
        self.created_at = datetime.now(timezone.utc)
        self.session_cost = 0.0  # Running cost for current session


class InfraManagerConfig:
    """Configuration for Infrastructure Manager"""
    AUTO_SHUTDOWN_HOURS = 4.0  # Auto-shutdown after 4 hours of inactivity
    COST_WARNING_THRESHOLD = 10.0  # Warning when session cost exceeds $10
    MAX_SESSION_COST = 50.0  # Auto-shutdown when session cost exceeds $50


class InfraManager:
    """
    Cloud Infrastructure Manager
    Manages GPU instances across multiple providers
    """
    
    def __init__(self):
        """Initialize Infrastructure Manager"""
        self.providers: Dict[GPUProvider, ProviderConfig] = {}
        self.active_instances: Dict[str, GPUInstance] = {}
        self.session_start_time: Optional[datetime] = None
        self.last_activity_time: Optional[datetime] = None
        self.auto_shutdown_enabled = True
        
        # Cloud Bridge for secure tunneling
        self.cloud_bridge: Optional[TailscaleManager] = None
        if CLOUD_BRIDGE_AVAILABLE:
            self.cloud_bridge = TailscaleManager()
        
        # Fas 22: Wallet Guard - Billing Manager integration
        self.billing_manager = None
        try:
            from core.billing_manager import billing_manager
            self.billing_manager = billing_manager
        except ImportError:
            logger.warning("Billing Manager not available for Wallet Guard")
        
        logger.info("Infrastructure Manager initialized")
    
    def register_provider(self, provider: GPUProvider, api_key: str, region: str = None):
        """
        Register a GPU provider with API key
        
        Args:
            provider: GPU provider
            api_key: API key for the provider
            region: Preferred region (optional)
        """
        self.providers[provider] = ProviderConfig(
            provider=provider,
            api_key=api_key,
            region=region,
            enabled=True
        )
        logger.info(f"Registered provider: {provider.value}")
    
    # ═══════════════════════════════════════════════════════════════
    # GPU PROVIDER API INTEGRATIONS
    # ═══════════════════════════════════════════════════════════════
    async def check_balance(self, provider: GPUProvider) -> Optional[float]:
        """
        Check balance/credits for a provider
        
        Args:
            provider: GPU provider
        
        Returns:
            Balance amount or None if error
        """
        if provider not in self.providers:
            logger.warning(f"Provider not registered: {provider.value}")
            return None
        
        config = self.providers[provider]
        
        try:
            if provider == GPUProvider.RUNPOD:
                return await self._check_runpod_balance(config)
            elif provider == GPUProvider.VAST_AI:
                return await self._check_vast_balance(config)
            elif provider == GPUProvider.LAMBDA_LABS:
                return await self._check_lambda_balance(config)
            elif provider == GPUProvider.PAPERSPACE:
                return await self._check_paperspace_balance(config)
            else:
                logger.warning(f"Balance check not implemented for: {provider.value}")
                return None
        except Exception as e:
            logger.error(f"Error checking balance for {provider.value}: {e}")
            return None
    
    async def get_available_instances(
        self,
        provider: GPUProvider,
        gpu_type: GPUType = None,
        region: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get available instances from provider
        
        Args:
            provider: GPU provider
            gpu_type: Filter by GPU type (optional)
            region: Filter by region (optional)
        
        Returns:
            List of available instances
        """
        if provider not in self.providers:
            logger.warning(f"Provider not registered: {provider.value}")
            return []
        
        config = self.providers[provider]
        
        try:
            if provider == GPUProvider.RUNPOD:
                return await self._get_runpod_instances(config, gpu_type, region)
            elif provider == GPUProvider.VAST_AI:
                return await self._get_vast_instances(config, gpu_type, region)
            elif provider == GPUProvider.LAMBDA_LABS:
                return await self._get_lambda_instances(config, gpu_type, region)
            elif provider == GPUProvider.PAPERSPACE:
                return await self._get_paperspace_instances(config, gpu_type, region)
            else:
                logger.warning(f"Instance listing not implemented for: {provider.value}")
                return []
        except Exception as e:
            logger.error(f"Error getting instances from {provider.value}: {e}")
            return []
    
    async def start_instance(
        self,
        provider: GPUProvider,
        gpu_type: GPUType,
        region: str = None
    ) -> Optional[GPUInstance]:
        """
        Start a new GPU instance
        
        Args:
            provider: GPU provider
            gpu_type: GPU type to use
            region: Region to deploy (optional)
        
        Returns:
            GPU instance or None if error
        """
        if provider not in self.providers:
            logger.warning(f"Provider not registered: {provider.value}")
            return None
        
        config = self.providers[provider]
        
        try:
            if provider == GPUProvider.RUNPOD:
                return await self._start_runpod_instance(config, gpu_type, region)
            elif provider == GPUProvider.VAST_AI:
                return await self._start_vast_instance(config, gpu_type, region)
            elif provider == GPUProvider.LAMBDA_LABS:
                return await self._start_lambda_instance(config, gpu_type, region)
            elif provider == GPUProvider.PAPERSPACE:
                return await self._start_paperspace_instance(config, gpu_type, region)
            else:
                logger.warning(f"Instance start not implemented for: {provider.value}")
                return None
        except Exception as e:
            logger.error(f"Error starting instance on {provider.value}: {e}")
            return None
    
    async def stop_instance(self, instance_id: str) -> bool:
        """
        Stop a GPU instance
        
        Args:
            instance_id: Instance ID to stop
        
        Returns:
            True if successful
        """
        instance = self.active_instances.get(instance_id)
        if not instance:
            logger.warning(f"Instance not found: {instance_id}")
            return False
        
        try:
            if instance.provider == GPUProvider.RUNPOD:
                return await self._stop_runpod_instance(instance)
            elif instance.provider == GPUProvider.VAST_AI:
                return await self._stop_vast_instance(instance)
            elif instance.provider == GPUProvider.LAMBDA_LABS:
                return await self._stop_lambda_instance(instance)
            elif instance.provider == GPUProvider.PAPERSPACE:
                return await self._stop_paperspace_instance(instance)
            else:
                logger.warning(f"Instance stop not implemented for: {instance.provider.value}")
                return False
        except Exception as e:
            logger.error(f"Error stopping instance {instance_id}: {e}")
            return False
    
    async def get_instance_status(self, instance_id: str) -> Optional[InstanceStatus]:
        """
        Get real-time status of an instance
        
        Args:
            instance_id: Instance ID
        
        Returns:
            Instance status or None if error
        """
        instance = self.active_instances.get(instance_id)
        if not instance:
            return None
        
        try:
            if instance.provider == GPUProvider.RUNPOD:
                return await self._get_runpod_status(instance)
            elif instance.provider == GPUProvider.VAST_AI:
                return await self._get_vast_status(instance)
            elif instance.provider == GPUProvider.LAMBDA_LABS:
                return await self._get_lambda_status(instance)
            elif instance.provider == GPUProvider.PAPERSPACE:
                return await self._get_paperspace_status(instance)
            else:
                return instance.status
        except Exception as e:
            logger.error(f"Error getting status for {instance_id}: {e}")
            return InstanceStatus.ERROR
    
    async def wait_for_instance_ready(self, instance_id: str, timeout: int = 300) -> bool:
        """
        Wait for instance to be ready and connect via cloud bridge
        
        Args:
            instance_id: Instance ID
            timeout: Timeout in seconds (default: 5 minutes)
        
        Returns:
            True if instance is ready and connected
        """
        instance = self.active_instances.get(instance_id)
        if not instance:
            logger.error(f"Instance not found: {instance_id}")
            return False
        
        logger.info(f"Waiting for instance {instance_id} to be ready...")
        start_time = datetime.now(timezone.utc)
        
        while (datetime.now(timezone.utc) - start_time).total_seconds() < timeout:
            status = await self.get_instance_status(instance_id)
            
            if status == InstanceStatus.READY:
                logger.info(f"Instance {instance_id} is ready!")
                
                # Connect via cloud bridge if available
                if self.cloud_bridge and instance.ip_address:
                    logger.info(f"Connecting via cloud bridge to {instance.ip_address}...")
                    connected = await self.cloud_bridge.connect()
                    if connected:
                        logger.info(f"Cloud bridge connected successfully")
                        return True
                    else:
                        logger.warning(f"Cloud bridge connection failed, but instance is ready")
                        return True
                else:
                    logger.info(f"Instance ready (no cloud bridge available or no IP address)")
                    return True
            
            # Wait before next check
            await asyncio.sleep(5)
        
        logger.error(f"Instance {instance_id} did not become ready within timeout")
        return False
    
    # ═══════════════════════════════════════════════════════════════
    # RUNPOD API INTEGRATION
    # ═══════════════════════════════════════════════════════════════
    async def _check_runpod_balance(self, config: ProviderConfig) -> Optional[float]:
        """Check RunPod balance"""
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {config.api_key}"}
            async with session.get("https://api.runpod.io/v2/user/balance", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return float(data.get("balance", 0.0))
        return None
    
    async def _get_runpod_instances(
        self,
        config: ProviderConfig,
        gpu_type: GPUType = None,
        region: str = None
    ) -> List[Dict[str, Any]]:
        """Get available RunPod instances"""
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {config.api_key}"}
            async with session.get("https://api.runpod.io/v2/pods", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("pods", [])
        return []
    
    async def _start_runpod_instance(
        self,
        config: ProviderConfig,
        gpu_type: GPUType,
        region: str = None
    ) -> Optional[GPUInstance]:
        """Start RunPod instance"""
        # GPU type mapping
        gpu_map = {
            GPUType.RTX_4090: "NVIDIA GeForce RTX 4090",
            GPUType.RTX_4080: "NVIDIA GeForce RTX 4080",
            GPUType.RTX_3090: "NVIDIA GeForce RTX 3090",
            GPUType.RTX_3060: "NVIDIA GeForce RTX 3060"
        }
        
        gpu_name = gpu_map.get(gpu_type, "NVIDIA GeForce RTX 4090")
        
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}
            
            payload = {
                "imageName": "runpod/pytorch:2.4.0-py3.11-cuda12.1.0-devel",
                "gpuType": gpu_name,
                "containerDiskInGb": 50,
                "minCpuInGb": 16,
                "minMemoryInGb": 32,
                "env": [
                    {"key": "ANTON_EGON_MODE", "value": "production"}
                ]
            }
            
            async with session.post("https://api.runpod.io/v2/pods", headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    instance = GPUInstance(
                        instance_id=data.get("id"),
                        provider=GPUProvider.RUNPOD,
                        gpu_type=gpu_type,
                        status=InstanceStatus.PENDING,
                        hourly_cost=0.44  # RTX 4090 average cost
                    )
                    self.active_instances[instance.instance_id] = instance
                    return instance
        return None
    
    async def _stop_runpod_instance(self, instance: GPUInstance) -> bool:
        """Stop RunPod instance"""
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.providers[instance.provider].api_key}"}
            async with session.post(f"https://api.runpod.io/v2/pods/{instance.instance_id}/stop", headers=headers) as resp:
                return resp.status == 200
        return False
    
    async def _get_runpod_status(self, instance: GPUInstance) -> InstanceStatus:
        """Get RunPod instance status"""
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.providers[instance.provider].api_key}"}
            async with session.get(f"https://api.runpod.io/v2/pods/{instance.instance_id}", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    status_map = {
                        "RUNNING": InstanceStatus.RUNNING,
                        "STOPPED": InstanceStatus.STOPPED,
                        "READY": InstanceStatus.READY
                    }
                    return status_map.get(data.get("status"), InstanceStatus.PENDING)
        return InstanceStatus.ERROR
    
    # ═══════════════════════════════════════════════════════════════
    # VAST.AI API INTEGRATION (Placeholder)
    # ═══════════════════════════════════════════════════════════════
    async def _check_vast_balance(self, config: ProviderConfig) -> Optional[float]:
        """Check Vast.ai balance (placeholder)"""
        logger.info("Vast.ai balance check - placeholder")
        return 0.0
    
    async def _get_vast_instances(self, config: ProviderConfig, gpu_type: GPUType = None, region: str = None) -> List[Dict[str, Any]]:
        """Get Vast.ai instances (placeholder)"""
        logger.info("Vast.ai instance listing - placeholder")
        return []
    
    async def _start_vast_instance(self, config: ProviderConfig, gpu_type: GPUType, region: str = None) -> Optional[GPUInstance]:
        """Start Vast.ai instance (placeholder)"""
        logger.info("Vast.ai instance start - placeholder")
        return None
    
    async def _stop_vast_instance(self, instance: GPUInstance) -> bool:
        """Stop Vast.ai instance (placeholder)"""
        logger.info("Vast.ai instance stop - placeholder")
        return False
    
    async def _get_vast_status(self, instance: GPUInstance) -> InstanceStatus:
        """Get Vast.ai status (placeholder)"""
        return InstanceStatus.PENDING
    
    # ═══════════════════════════════════════════════════════════════
    # LAMBDA LABS API INTEGRATION (Placeholder)
    # ═══════════════════════════════════════════════════════════════
    async def _check_lambda_balance(self, config: ProviderConfig) -> Optional[float]:
        """Check Lambda Labs balance (placeholder)"""
        logger.info("Lambda Labs balance check - placeholder")
        return 0.0
    
    async def _get_lambda_instances(self, config: ProviderConfig, gpu_type: GPUType = None, region: str = None) -> List[Dict[str, Any]]:
        """Get Lambda Labs instances (placeholder)"""
        logger.info("Lambda Labs instance listing - placeholder")
        return []
    
    async def _start_lambda_instance(self, config: ProviderConfig, gpu_type: GPUType, region: str = None) -> Optional[GPUInstance]:
        """Start Lambda Labs instance (placeholder)"""
        logger.info("Lambda Labs instance start - placeholder")
        return None
    
    async def _stop_lambda_instance(self, instance: GPUInstance) -> bool:
        """Stop Lambda Labs instance (placeholder)"""
        logger.info("Lambda Labs instance stop - placeholder")
        return False
    
    async def _get_lambda_status(self, instance: GPUInstance) -> InstanceStatus:
        """Get Lambda Labs status (placeholder)"""
        return InstanceStatus.PENDING
    
    # ═══════════════════════════════════════════════════════════════
    # PAPERSPACE API INTEGRATION (Placeholder)
    # ═══════════════════════════════════════════════════════════════
    async def _check_paperspace_balance(self, config: ProviderConfig) -> Optional[float]:
        """Check Paperspace balance (placeholder)"""
        logger.info("Paperspace balance check - placeholder")
        return 0.0
    
    async def _get_paperspace_instances(self, config: ProviderConfig, gpu_type: GPUType = None, region: str = None) -> List[Dict[str, Any]]:
        """Get Paperspace instances (placeholder)"""
        logger.info("Paperspace instance listing - placeholder")
        return []
    
    async def _start_paperspace_instance(self, config: ProviderConfig, gpu_type: GPUType, region: str = None) -> Optional[GPUInstance]:
        """Start Paperspace instance (placeholder)"""
        logger.info("Paperspace instance start - placeholder")
        return None
    
    async def _stop_paperspace_instance(self, instance: GPUInstance) -> bool:
        """Stop Paperspace instance (placeholder)"""
        logger.info("Paperspace instance stop - placeholder")
        return False
    
    async def _get_paperspace_status(self, instance: GPUInstance) -> InstanceStatus:
        """Get Paperspace status (placeholder)"""
        return InstanceStatus.PENDING
    
    # ═══════════════════════════════════════════════════════════════
    # COST TRACKING & AUTO-SHUTDOWN
    # ═══════════════════════════════════════════════════════════════
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity_time = datetime.now(timezone.utc)
        if self.session_start_time is None:
            self.session_start_time = self.last_activity_time
    
    def calculate_session_cost(self) -> float:
        """
        Calculate current session cost
        
        Returns:
            Cost in USD
        """
        if not self.session_start_time:
            return 0.0
        
        elapsed_hours = (datetime.now(timezone.utc) - self.session_start_time).total_seconds() / 3600
        total_cost = 0.0
        
        for instance in self.active_instances.values():
            total_cost += instance.hourly_cost * elapsed_hours
            instance.session_cost = total_cost
        
        return total_cost
    
    async def check_auto_shutdown(self) -> bool:
        """
        Check if auto-shutdown should trigger
        
        Returns:
            True if shutdown triggered
        """
        if not self.auto_shutdown_enabled:
            return False
        
        session_cost = self.calculate_session_cost()
        
        # Check cost thresholds
        if session_cost > InfraManagerConfig.MAX_SESSION_COST:
            logger.warning(f"Max session cost exceeded: ${session_cost:.2f} - triggering auto-shutdown")
            await self.stop_all_instances()
            return True
        
        # Check inactivity
        if self.last_activity_time:
            inactive_hours = (datetime.now(timezone.utc) - self.last_activity_time).total_seconds() / 3600
            if inactive_hours > InfraManagerConfig.AUTO_SHUTDOWN_HOURS:
                logger.warning(f"Inactivity timeout: {inactive_hours:.1f}h - triggering auto-shutdown")
                await self.stop_all_instances()
                return True
        
        return False
    
    async def check_wallet_guard(self, user_id: str = "default_user") -> bool:
        """
        Fas 22: Wallet Guard - Check if auto-shutdown should trigger
        Stops instances when balance reaches zero or exceeds max session cost
        
        Args:
            user_id: User identifier
        
        Returns:
            True if safe to continue, False if shutdown triggered
        """
        # Check credit balance if billing manager is available
        if self.billing_manager:
            balance = self.billing_manager.get_user_balance(user_id)
            if balance and balance.gpu_credits <= 0:
                logger.warning(f"Wallet Guard: GPU credits exhausted for {user_id}. Triggering auto-shutdown.")
                await self.stop_all_instances()
                return False
        
        # Check session cost
        session_cost = self.calculate_session_cost()
        if session_cost >= self.config.MAX_SESSION_COST:
            logger.warning(f"Wallet Guard: Session cost ${session_cost:.2f} exceeds max ${self.config.MAX_SESSION_COST}. Triggering auto-shutdown.")
            await self.stop_all_instances()
            return False
        
        # Check inactivity
        if self.config.auto_shutdown_enabled:
            if self.last_activity_time:
                inactive_hours = (datetime.now(timezone.utc) - self.last_activity_time).total_seconds() / 3600
                if inactive_hours >= self.config.AUTO_SHUTDOWN_HOURS:
                    logger.warning(f"Wallet Guard: Inactive for {inactive_hours:.1f} hours. Triggering auto-shutdown.")
                    await self.stop_all_instances()
                    return False
        
        return True
    
    async def stop_all_instances(self):
        """Stop all active instances"""
        for instance_id in list(self.active_instances.keys()):
            await self.stop_instance(instance_id)
        
        self.session_start_time = None
        self.last_activity_time = None
        logger.info("All instances stopped")
    
    def get_status(self) -> Dict[str, Any]:
        """Get Infrastructure Manager status"""
        return {
            "active_instances": len(self.active_instances),
            "session_cost": self.calculate_session_cost(),
            "session_start_time": self.session_start_time.isoformat() if self.session_start_time else None,
            "last_activity": self.last_activity_time.isoformat() if self.last_activity_time else None,
            "registered_providers": len(self.providers),
            "auto_shutdown_enabled": self.auto_shutdown_enabled
        }


# Singleton instance
infra_manager = InfraManager()
