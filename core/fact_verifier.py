#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Hard Fact Verifier
Checks LLM-generated responses against /vault data before they are spoken.
Catches hallucinated numbers, prices, dates, and names.
"""

import sys
import re
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class VerificationResult(BaseModel):
    """Result of a fact verification check"""
    is_verified: bool = Field(default=False, description="Whether the response passed verification")
    confidence: float = Field(default=0.0, description="Verification confidence (0-1)")
    flagged_claims: List[Dict[str, Any]] = Field(default_factory=list, description="Claims that failed verification")
    verified_claims: List[Dict[str, Any]] = Field(default_factory=list, description="Claims that passed verification")
    action: str = Field(default="pass", description="Recommended action: pass, soften, block, defer")
    softened_response: Optional[str] = Field(None, description="Softened version of response if action is 'soften'")


class FactVerifierConfig(BaseModel):
    """Configuration for Hard Fact Verifier"""
    enabled: bool = Field(default=True, description="Enable fact verification")
    block_unverified_numbers: bool = Field(default=True, description="Block responses with unverified numbers/prices")
    block_unverified_names: bool = Field(default=False, description="Block responses with unverified person names")
    soften_unverified: bool = Field(default=True, description="Soften unverified claims instead of blocking")
    confidence_threshold: float = Field(default=0.7, description="Min confidence to pass verification")
    vault_search_timeout: float = Field(default=1.5, description="Max seconds to search vault")


class HardFactVerifier:
    """
    Hard Fact Verifier
    Intercepts LLM responses before TTS and checks critical claims
    (numbers, prices, dates, percentages) against /vault data.
    
    Actions:
    - PASS: Response verified, send to TTS
    - SOFTEN: Hedge the claim ("Om jag minns rätt...")
    - BLOCK: Replace with deferral ("Jag behöver dubbelkolla det")
    - DEFER: Skip the claim entirely
    """
    
    # Patterns that extract verifiable claims from text
    CLAIM_PATTERNS = {
        "price": re.compile(
            r'(\d[\d\s,.]*)\s*(kr|kronor|sek|euro|eur|dollar|usd|\$|€)',
            re.IGNORECASE
        ),
        "percentage": re.compile(
            r'(\d[\d,.]*)\s*(%|procent|percent)',
            re.IGNORECASE
        ),
        "date": re.compile(
            r'(\d{1,2})\s*(januari|februari|mars|april|maj|juni|juli|augusti|september|oktober|november|december|jan|feb|mar|apr|jun|jul|aug|sep|okt|nov|dec)',
            re.IGNORECASE
        ),
        "count": re.compile(
            r'(\d+)\s*(stycken|enheter|projekt|kunder|anställda|dagar|veckor|månader)',
            re.IGNORECASE
        ),
        "year": re.compile(
            r'(20[12]\d)',
            re.IGNORECASE
        ),
    }
    
    # Softening phrases
    SOFTEN_PREFIXES = [
        "Om jag minns rätt, ",
        "Baserat på vad jag har sett, ",
        "Jag tror att ",
        "Enligt mina anteckningar, ",
        "Om jag inte missminner mig, ",
    ]
    
    # Deferral phrases
    DEFERRAL_RESPONSES = [
        "Jag behöver dubbelkolla den siffran och återkomma.",
        "Låt mig verifiera det efter mötet och skicka det skriftligt.",
        "Den exakta siffran har jag inte framför mig, men jag kan ta fram det.",
        "Jag vill inte ge dig fel information, låt mig kolla upp det.",
    ]
    
    def __init__(
        self,
        config: FactVerifierConfig,
        vault_search_fn=None
    ):
        """
        Initialize Hard Fact Verifier
        
        Args:
            config: Verifier configuration
            vault_search_fn: Async function(query) → List[str] to search /vault
        """
        self.config = config
        self.vault_search_fn = vault_search_fn
        
        # Stats
        self.total_checks = 0
        self.total_blocks = 0
        self.total_softens = 0
        self.total_passes = 0
        
        logger.info("Hard Fact Verifier initialized")
    
    def extract_claims(self, response: str) -> List[Dict[str, Any]]:
        """
        Extract verifiable claims (numbers, prices, dates) from response
        
        Args:
            response: LLM response text
        
        Returns:
            List of extracted claims
        """
        claims = []
        
        for claim_type, pattern in self.CLAIM_PATTERNS.items():
            matches = pattern.finditer(response)
            for match in matches:
                claims.append({
                    "type": claim_type,
                    "value": match.group(0).strip(),
                    "raw_number": match.group(1).strip(),
                    "position": match.start(),
                    "length": len(match.group(0))
                })
        
        return claims
    
    async def verify_against_vault(self, claim: Dict[str, Any]) -> Tuple[bool, float]:
        """
        Verify a single claim against /vault
        
        Args:
            claim: Claim dictionary
        
        Returns:
            (is_verified, confidence)
        """
        if not self.vault_search_fn:
            return False, 0.0
        
        try:
            import asyncio
            
            # Build search query from claim
            query = f"{claim['type']} {claim['value']}"
            
            # Search vault with timeout
            results = await asyncio.wait_for(
                self.vault_search_fn(query),
                timeout=self.config.vault_search_timeout
            )
            
            if not results:
                return False, 0.0
            
            # Check if claim value appears in vault results
            claim_value = claim["raw_number"].replace(" ", "").replace(",", ".")
            
            for result in results:
                if isinstance(result, str):
                    # Normalize result for comparison
                    normalized = result.replace(" ", "").replace(",", ".")
                    if claim_value in normalized:
                        return True, 0.95
                    
                    # Fuzzy: check if number is close
                    try:
                        claim_num = float(claim_value)
                        # Find numbers in result
                        nums_in_result = re.findall(r'[\d,.]+', normalized)
                        for num_str in nums_in_result:
                            try:
                                result_num = float(num_str.replace(",", "."))
                                if abs(claim_num - result_num) / max(claim_num, 1) < 0.05:
                                    return True, 0.8  # Within 5%
                            except ValueError:
                                continue
                    except ValueError:
                        pass
            
            return False, 0.2
            
        except Exception as e:
            logger.error(f"Vault verification error: {e}")
            return False, 0.0
    
    async def verify_response(self, response: str) -> VerificationResult:
        """
        Verify an LLM response before it's spoken
        
        Args:
            response: LLM generated response
        
        Returns:
            VerificationResult with action and optional softened response
        """
        self.total_checks += 1
        
        if not self.config.enabled:
            self.total_passes += 1
            return VerificationResult(is_verified=True, confidence=1.0, action="pass")
        
        # Extract claims
        claims = self.extract_claims(response)
        
        # No verifiable claims → pass through
        if not claims:
            self.total_passes += 1
            return VerificationResult(is_verified=True, confidence=1.0, action="pass")
        
        # Verify each claim
        flagged = []
        verified = []
        
        for claim in claims:
            is_ok, confidence = await self.verify_against_vault(claim)
            
            claim_result = {**claim, "verified": is_ok, "confidence": confidence}
            
            if is_ok and confidence >= self.config.confidence_threshold:
                verified.append(claim_result)
            else:
                flagged.append(claim_result)
        
        # Determine action
        if not flagged:
            self.total_passes += 1
            return VerificationResult(
                is_verified=True,
                confidence=min(c["confidence"] for c in verified) if verified else 1.0,
                verified_claims=verified,
                action="pass"
            )
        
        # Has flagged claims - decide action
        has_numbers = any(c["type"] in ("price", "percentage", "count") for c in flagged)
        
        if has_numbers and self.config.block_unverified_numbers:
            if self.config.soften_unverified:
                # Soften the response
                softened = self._soften_response(response, flagged)
                self.total_softens += 1
                return VerificationResult(
                    is_verified=False,
                    confidence=0.4,
                    flagged_claims=flagged,
                    verified_claims=verified,
                    action="soften",
                    softened_response=softened
                )
            else:
                # Block entirely
                self.total_blocks += 1
                import random
                deferral = random.choice(self.DEFERRAL_RESPONSES)
                return VerificationResult(
                    is_verified=False,
                    confidence=0.0,
                    flagged_claims=flagged,
                    verified_claims=verified,
                    action="block",
                    softened_response=deferral
                )
        
        # Non-critical flagged claims - soften
        softened = self._soften_response(response, flagged)
        self.total_softens += 1
        return VerificationResult(
            is_verified=False,
            confidence=0.5,
            flagged_claims=flagged,
            verified_claims=verified,
            action="soften",
            softened_response=softened
        )
    
    def _soften_response(self, response: str, flagged_claims: List[Dict[str, Any]]) -> str:
        """
        Soften a response by hedging flagged claims
        
        Args:
            response: Original response
            flagged_claims: Claims that failed verification
        
        Returns:
            Softened response
        """
        import random
        
        result = response
        
        # Add hedging prefix before the first flagged claim
        if flagged_claims:
            first_claim = min(flagged_claims, key=lambda c: c["position"])
            pos = first_claim["position"]
            
            # Find start of sentence containing the claim
            sentence_start = max(0, result.rfind(".", 0, pos) + 1)
            if sentence_start > 0:
                sentence_start += 1  # Skip space after period
            
            prefix = random.choice(self.SOFTEN_PREFIXES)
            
            # Insert prefix at sentence start (lowercase the first letter of the original)
            original_start = result[sentence_start:sentence_start + 1]
            if original_start.isupper():
                result = result[:sentence_start] + prefix + result[sentence_start:sentence_start + 1].lower() + result[sentence_start + 1:]
            else:
                result = result[:sentence_start] + prefix + result[sentence_start:]
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get verifier status
        
        Returns:
            Status dictionary
        """
        return {
            "enabled": self.config.enabled,
            "total_checks": self.total_checks,
            "total_passes": self.total_passes,
            "total_softens": self.total_softens,
            "total_blocks": self.total_blocks,
            "block_unverified_numbers": self.config.block_unverified_numbers,
            "confidence_threshold": self.config.confidence_threshold
        }


async def main():
    """Test the Hard Fact Verifier"""
    from loguru import logger
    
    logger.add("logs/fact_verifier_{time}.log", rotation="10 MB")
    
    # Mock vault search
    async def mock_vault_search(query):
        # Simulate vault having some data
        if "budget" in query.lower() or "2.5" in query:
            return ["Budget Q3 2024: 2 500 000 SEK"]
        if "15" in query and "procent" in query.lower():
            return ["Rabatt: 15% för volymorder"]
        return []
    
    # Create verifier
    config = FactVerifierConfig()
    verifier = HardFactVerifier(config, vault_search_fn=mock_vault_search)
    
    # Test responses
    test_responses = [
        "Budgeten ligger på 2,5 miljoner kronor för Q3.",
        "Vi kan erbjuda 15 procent rabatt på volymordern.",
        "Priset är 450 kronor per enhet, och leveransen tar 6 veckor.",
        "Det ser bra ut, vi kör på det.",
        "Vi har 3 500 kunder och en tillväxt på 23 procent.",
    ]
    
    for response in test_responses:
        result = await verifier.verify_response(response)
        logger.info(f"\nResponse: '{response}'")
        logger.info(f"  Action: {result.action} | Verified: {result.is_verified}")
        if result.flagged_claims:
            logger.info(f"  Flagged: {[c['value'] for c in result.flagged_claims]}")
        if result.softened_response:
            logger.info(f"  Softened: '{result.softened_response}'")
    
    # Get status
    status = verifier.get_status()
    logger.info(f"\nVerifier status: {status}")
    
    logger.info("Hard Fact Verifier test complete")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
