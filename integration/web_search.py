#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Anton Egon - Phase 7.3: Real-time Web Search
Provides real-time web search when RAG vault doesn't have the answer
Supports Tavily, DuckDuckGo, and Perplexity APIs
"""

import sys
import os
import json
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

# Fix Windows encoding issue
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


class SearchProvider(Enum):
    """Search API providers"""
    TAVILY = "tavily"
    DUCKDUCKGO = "duckduckgo"
    PERPLEXITY = "perplexity"


class SearchResult(BaseModel):
    """A single search result"""
    title: str
    url: str
    snippet: str
    score: float = Field(default=0.0, description="Relevance score (0-1)")
    source: str = Field(default="web", description="Source provider")


class WebSearchConfig(BaseModel):
    """Configuration for Web Search"""
    primary_provider: SearchProvider = Field(default=SearchProvider.DUCKDUCKGO, description="Primary search provider")
    fallback_provider: Optional[SearchProvider] = Field(default=None, description="Fallback search provider")
    tavily_api_key: Optional[str] = Field(default=None, description="Tavily API key (from env)")
    perplexity_api_key: Optional[str] = Field(default=None, description="Perplexity API key (from env)")
    max_results: int = Field(default=5, description="Maximum search results")
    timeout_seconds: float = Field(default=5.0, description="Search timeout in seconds")
    cache_results: bool = Field(default=True, description="Cache search results")
    cache_ttl_minutes: int = Field(default=30, description="Cache TTL in minutes")


class WebSearch:
    """
    Real-time Web Search
    Searches the web when RAG vault doesn't have the answer
    """
    
    def __init__(self, config: WebSearchConfig):
        """
        Initialize Web Search
        
        Args:
            config: Web Search configuration
        """
        self.config = config
        
        # Load API keys from environment
        self.tavily_api_key = config.tavily_api_key or os.environ.get("TAVILY_API_KEY")
        self.perplexity_api_key = config.perplexity_api_key or os.environ.get("PERPLEXITY_API_KEY")
        
        # Cache
        self.cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"Web Search initialized (provider: {config.primary_provider.value})")
    
    async def search(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """
        Search the web
        
        Args:
            query: Search query
            max_results: Maximum results (optional, uses config default)
        
        Returns:
            List of search results
        """
        if max_results is None:
            max_results = self.config.max_results
        
        # Check cache
        if self.config.cache_results:
            cached = self._get_cached(query)
            if cached:
                logger.debug(f"Cache hit for: {query}")
                return cached
        
        # Try primary provider
        results = await self._search_with_provider(
            self.config.primary_provider,
            query,
            max_results
        )
        
        # Try fallback if primary fails
        if not results and self.config.fallback_provider:
            logger.warning(f"Primary provider failed, trying fallback: {self.config.fallback_provider.value}")
            results = await self._search_with_provider(
                self.config.fallback_provider,
                query,
                max_results
            )
        
        # Cache results
        if results and self.config.cache_results:
            self._cache_results(query, results)
        
        return results
    
    async def _search_with_provider(
        self,
        provider: SearchProvider,
        query: str,
        max_results: int
    ) -> List[SearchResult]:
        """
        Search with specific provider
        
        Args:
            provider: Search provider
            query: Search query
            max_results: Maximum results
        
        Returns:
            List of search results
        """
        try:
            if provider == SearchProvider.TAVILY:
                return await self._search_tavily(query, max_results)
            elif provider == SearchProvider.DUCKDUCKGO:
                return await self._search_duckduckgo(query, max_results)
            elif provider == SearchProvider.PERPLEXITY:
                return await self._search_perplexity(query, max_results)
            else:
                logger.error(f"Unknown provider: {provider}")
                return []
        except Exception as e:
            logger.error(f"Search error ({provider.value}): {e}")
            return []
    
    async def _search_tavily(self, query: str, max_results: int) -> List[SearchResult]:
        """Search using Tavily API"""
        if not self.tavily_api_key:
            logger.warning("Tavily API key not set. Set TAVILY_API_KEY environment variable.")
            return []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic"
                    },
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = []
                        
                        for item in data.get("results", [])[:max_results]:
                            results.append(SearchResult(
                                title=item.get("title", ""),
                                url=item.get("url", ""),
                                snippet=item.get("content", "")[:300],
                                score=item.get("score", 0.0),
                                source="tavily"
                            ))
                        
                        logger.info(f"Tavily: {len(results)} results for '{query}'")
                        return results
                    else:
                        logger.error(f"Tavily API error: {response.status}")
                        return []
        except asyncio.TimeoutError:
            logger.warning(f"Tavily search timed out for: {query}")
            return []
        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return []
    
    async def _search_duckduckgo(self, query: str, max_results: int) -> List[SearchResult]:
        """Search using DuckDuckGo (no API key needed)"""
        try:
            # Use DuckDuckGo Instant Answer API (free, no key needed)
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.duckduckgo.com/",
                    params={
                        "q": query,
                        "format": "json",
                        "no_html": 1,
                        "skip_disambig": 1
                    },
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                ) as response:
                    if response.status == 200:
                        data = await response.json(content_type=None)
                        results = []
                        
                        # Abstract result
                        if data.get("Abstract"):
                            results.append(SearchResult(
                                title=data.get("Heading", query),
                                url=data.get("AbstractURL", ""),
                                snippet=data.get("Abstract", "")[:300],
                                score=1.0,
                                source="duckduckgo"
                            ))
                        
                        # Related topics
                        for topic in data.get("RelatedTopics", [])[:max_results - len(results)]:
                            if isinstance(topic, dict) and "Text" in topic:
                                results.append(SearchResult(
                                    title=topic.get("Text", "")[:100],
                                    url=topic.get("FirstURL", ""),
                                    snippet=topic.get("Text", "")[:300],
                                    score=0.7,
                                    source="duckduckgo"
                                ))
                        
                        logger.info(f"DuckDuckGo: {len(results)} results for '{query}'")
                        return results
                    else:
                        logger.error(f"DuckDuckGo API error: {response.status}")
                        return []
        except asyncio.TimeoutError:
            logger.warning(f"DuckDuckGo search timed out for: {query}")
            return []
        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return []
    
    async def _search_perplexity(self, query: str, max_results: int) -> List[SearchResult]:
        """Search using Perplexity API"""
        if not self.perplexity_api_key:
            logger.warning("Perplexity API key not set. Set PERPLEXITY_API_KEY environment variable.")
            return []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.perplexity.ai/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.perplexity_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.1-sonar-small-128k-online",
                        "messages": [
                            {"role": "user", "content": query}
                        ]
                    },
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        
                        if content:
                            results = [SearchResult(
                                title=f"Perplexity: {query}",
                                url="https://perplexity.ai",
                                snippet=content[:500],
                                score=0.9,
                                source="perplexity"
                            )]
                            
                            logger.info(f"Perplexity: 1 result for '{query}'")
                            return results
                        
                        return []
                    else:
                        logger.error(f"Perplexity API error: {response.status}")
                        return []
        except asyncio.TimeoutError:
            logger.warning(f"Perplexity search timed out for: {query}")
            return []
        except Exception as e:
            logger.error(f"Perplexity search error: {e}")
            return []
    
    def _get_cached(self, query: str) -> Optional[List[SearchResult]]:
        """
        Get cached results
        
        Args:
            query: Search query
        
        Returns:
            Cached results or None
        """
        query_key = query.lower().strip()
        
        if query_key in self.cache:
            cached = self.cache[query_key]
            cached_time = datetime.fromisoformat(cached["timestamp"])
            elapsed_minutes = (datetime.now(timezone.utc) - cached_time).total_seconds() / 60
            
            if elapsed_minutes < self.config.cache_ttl_minutes:
                return [SearchResult(**r) for r in cached["results"]]
            else:
                del self.cache[query_key]
        
        return None
    
    def _cache_results(self, query: str, results: List[SearchResult]):
        """
        Cache search results
        
        Args:
            query: Search query
            results: Search results
        """
        query_key = query.lower().strip()
        self.cache[query_key] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": [r.dict() for r in results]
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get search status
        
        Returns:
            Status dictionary
        """
        return {
            "primary_provider": self.config.primary_provider.value,
            "fallback_provider": self.config.fallback_provider.value if self.config.fallback_provider else None,
            "tavily_configured": bool(self.tavily_api_key),
            "perplexity_configured": bool(self.perplexity_api_key),
            "cached_queries": len(self.cache)
        }


async def main():
    """Test the Web Search"""
    from loguru import logger
    
    logger.add("logs/web_search_{time}.log", rotation="10 MB")
    
    # Create search (DuckDuckGo - no API key needed)
    config = WebSearchConfig(primary_provider=SearchProvider.DUCKDUCKGO)
    search = WebSearch(config)
    
    # Test search
    results = await search.search("DHL aktie idag")
    
    for result in results:
        logger.info(f"Result: {result.title}")
        logger.info(f"  URL: {result.url}")
        logger.info(f"  Snippet: {result.snippet[:100]}...")
    
    # Get status
    status = search.get_status()
    logger.info(f"Search status: {status}")
    
    logger.info("Web Search test complete")


if __name__ == "__main__":
    asyncio.run(main())
