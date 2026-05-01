#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Billing Manager
Stripe integration for Anton Credits and GPU rental billing
Phase 22: Billing Engine & Marketplace
"""

import asyncio
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path

from loguru import logger

# Stripe integration
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False

# Supabase integration for storing billing records
try:
    from integration.supabase_client import supabase_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False


class CreditPackage(Enum):
    """Anton Credit packages"""
    STARTER = "starter"  # $10 = 100 credits
    PRO = "pro"  # $50 = 600 credits
    ENTERPRISE = "enterprise"  # $100 = 1500 credits


class SubscriptionTier(Enum):
    """Subscription tiers"""
    FREEMIUM = "freemium"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


@dataclass
class CreditBalance:
    """User credit balance"""
    user_id: str
    anton_credits: float
    gpu_credits: float  # GPU-specific credits
    last_updated: datetime
    subscription_tier: SubscriptionTier = SubscriptionTier.FREEMIUM
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "anton_credits": self.anton_credits,
            "gpu_credits": self.gpu_credits,
            "last_updated": self.last_updated.isoformat(),
            "subscription_tier": self.subscription_tier.value
        }


@dataclass
class Transaction:
    """Billing transaction record"""
    transaction_id: str
    user_id: str
    amount: float
    currency: str
    credits_purchased: float
    payment_method: str  # stripe, paypal, etc.
    status: str  # pending, completed, failed
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "currency": self.currency,
            "credits_purchased": self.credits_purchased,
            "payment_method": self.payment_method,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }


class BillingManagerConfig:
    """Billing Manager configuration"""
    stripe_secret_key: Optional[str] = None
    stripe_publishable_key: Optional[str] = None
    enable_wallet_guard: bool = True
    auto_shutdown_threshold: float = 0.0  # Auto-shutdown when balance reaches this
    cost_warning_threshold: float = 10.0  # Warn when session cost exceeds this


class BillingManager:
    """
    Billing Manager
    Handles Anton Credits, Stripe payments, and GPU cost tracking
    """
    
    def __init__(self, config: BillingManagerConfig):
        """
        Initialize Billing Manager
        
        Args:
            config: Billing Manager configuration
        """
        self.config = config
        self.credit_balances: Dict[str, CreditBalance] = {}
        self.transactions: List[Transaction] = []
        
        # Initialize Stripe if available
        if STRIPE_AVAILABLE and config.stripe_secret_key:
            stripe.api_key = config.stripe_secret_key
            logger.info("Stripe initialized")
        else:
            logger.warning("Stripe not available or not configured")
        
        logger.info("Billing Manager initialized")
    
    def get_user_balance(self, user_id: str) -> Optional[CreditBalance]:
        """
        Get user's credit balance
        
        Args:
            user_id: User identifier
        
        Returns:
            Credit balance or None
        """
        # Check local cache first
        if user_id in self.credit_balances:
            return self.credit_balances[user_id]
        
        # Fetch from Supabase if available
        if SUPABASE_AVAILABLE:
            try:
                response = supabase_client.table('credit_balances').select('*').eq('user_id', user_id).execute()
                if response.data:
                    data = response.data[0]
                    balance = CreditBalance(
                        user_id=data['user_id'],
                        anton_credits=data['anton_credits'],
                        gpu_credits=data['gpu_credits'],
                        last_updated=datetime.fromisoformat(data['last_updated']),
                        subscription_tier=SubscriptionTier(data.get('subscription_tier', 'freemium'))
                    )
                    self.credit_balances[user_id] = balance
                    return balance
            except Exception as e:
                logger.error(f"Failed to fetch balance from Supabase: {e}")
        
        # Return default balance
        default_balance = CreditBalance(
            user_id=user_id,
            anton_credits=0.0,
            gpu_credits=0.0,
            last_updated=datetime.now(timezone.utc)
        )
        self.credit_balances[user_id] = default_balance
        return default_balance
    
    def update_balance(self, user_id: str, anton_credits: float = 0.0, gpu_credits: float = 0.0):
        """
        Update user's credit balance
        
        Args:
            user_id: User identifier
            anton_credits: Anton credits to add (can be negative)
            gpu_credits: GPU credits to add (can be negative)
        """
        balance = self.get_user_balance(user_id)
        if balance:
            balance.anton_credits += anton_credits
            balance.gpu_credits += gpu_credits
            balance.last_updated = datetime.now(timezone.utc)
            
            # Sync to Supabase if available
            if SUPABASE_AVAILABLE:
                try:
                    supabase_client.table('credit_balances').upsert(balance.to_dict()).execute()
                    logger.info(f"Balance updated for {user_id}: {balance.anton_credits} Anton credits")
                except Exception as e:
                    logger.error(f"Failed to sync balance to Supabase: {e}")
    
    async def purchase_credits(self, user_id: str, package: CreditPackage, payment_method_id: str) -> Dict[str, Any]:
        """
        Purchase Anton Credits via Stripe
        
        Args:
            user_id: User identifier
            package: Credit package to purchase
            payment_method_id: Stripe payment method ID
        
        Returns:
            Transaction result
        """
        if not STRIPE_AVAILABLE:
            return {"success": False, "error": "Stripe not available"}
        
        # Define package details
        package_details = {
            CreditPackage.STARTER: {"amount": 10.00, "credits": 100},
            CreditPackage.PRO: {"amount": 50.00, "credits": 600},
            CreditPackage.ENTERPRISE: {"amount": 100.00, "credits": 1500}
        }
        
        details = package_details.get(package)
        if not details:
            return {"success": False, "error": "Invalid package"}
        
        try:
            # Create Stripe payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(details["amount"] * 100),  # Convert to cents
                currency="usd",
                payment_method=payment_method_id,
                confirm=True,
                description=f"Anton Credits - {package.value}",
                metadata={"user_id": user_id, "package": package.value}
            )
            
            if intent.status == "succeeded":
                # Create transaction record
                transaction = Transaction(
                    transaction_id=intent.id,
                    user_id=user_id,
                    amount=details["amount"],
                    currency="usd",
                    credits_purchased=details["credits"],
                    payment_method="stripe",
                    status="completed",
                    created_at=datetime.now(timezone.utc),
                    metadata={"package": package.value}
                )
                self.transactions.append(transaction)
                
                # Update user balance
                self.update_balance(user_id, anton_credits=details["credits"])
                
                logger.info(f"Credit purchase successful: {user_id} purchased {details['credits']} credits")
                return {"success": True, "transaction_id": intent.id, "credits": details["credits"]}
            else:
                return {"success": False, "error": f"Payment failed: {intent.status}"}
                
        except Exception as e:
            logger.error(f"Credit purchase failed: {e}")
            return {"success": False, "error": str(e)}
    
    def deduct_gpu_credits(self, user_id: str, cost: float) -> bool:
        """
        Deduct GPU credits for session cost
        
        Args:
            user_id: User identifier
            cost: Cost to deduct
        
        Returns:
            True if deduction successful, False if insufficient balance
        """
        balance = self.get_user_balance(user_id)
        if not balance:
            return False
        
        if balance.gpu_credits < cost:
            logger.warning(f"Insufficient GPU credits for {user_id}: {balance.gpu_credits} < {cost}")
            return False
        
        balance.gpu_credits -= cost
        balance.last_updated = datetime.now(timezone.utc)
        
        # Sync to Supabase if available
        if SUPABASE_AVAILABLE:
            try:
                supabase_client.table('credit_balances').upsert(balance.to_dict()).execute()
            except Exception as e:
                logger.error(f"Failed to sync balance to Supabase: {e}")
        
        logger.info(f"GPU credits deducted: {user_id} -${cost:.2f}")
        
        # Check wallet guard
        if self.config.enable_wallet_guard and balance.gpu_credits <= self.config.auto_shutdown_threshold:
            logger.warning(f"Wallet Guard triggered for {user_id}: Balance at ${balance.gpu_credits:.2f}")
            # This would trigger auto-shutdown in the infrastructure manager
        
        return True
    
    def get_transaction_history(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get transaction history for user
        
        Args:
            user_id: User identifier
            limit: Maximum number of transactions to return
        
        Returns:
            List of transactions
        """
        user_transactions = [t for t in self.transactions if t.user_id == user_id]
        return [t.to_dict() for t in user_transactions[-limit:]]
    
    def get_credit_packages(self) -> List[Dict[str, Any]]:
        """
        Get available credit packages
        
        Returns:
            List of package details
        """
        return [
            {
                "id": CreditPackage.STARTER.value,
                "name": "Starter",
                "amount": 10.00,
                "credits": 100,
                "description": "Perfect for trying out Anton Egon"
            },
            {
                "id": CreditPackage.PRO.value,
                "name": "Pro",
                "amount": 50.00,
                "credits": 600,
                "description": "Best value for regular users"
            },
            {
                "id": CreditPackage.ENTERPRISE.value,
                "name": "Enterprise",
                "amount": 100.00,
                "credits": 1500,
                "description": "For teams and power users"
            }
        ]


# Singleton instance
billing_manager: Optional[BillingManager] = None


def initialize_billing_manager(stripe_secret_key: Optional[str] = None, stripe_publishable_key: Optional[str] = None):
    """Initialize Billing Manager singleton"""
    global billing_manager
    config = BillingManagerConfig(
        stripe_secret_key=stripe_secret_key,
        stripe_publishable_key=stripe_publishable_key
    )
    billing_manager = BillingManager(config)
    return billing_manager
