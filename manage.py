#!/usr/bin/env python3
"""
Project Anton Egon - Phase 1: Memory Management CLI
CLI tool for managing ChromaDB memory and document purging
"""

import sys
import click
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import json

from chromadb import Client, Collection
from chromadb.config import Settings
from loguru import logger

# Configuration
MEMORY_DIR = Path("memory")
CHROMA_PERSIST_DIR = MEMORY_DIR / "chroma_db"


class MemoryManager:
    """Manage ChromaDB memory collections"""
    
    def __init__(self, persist_directory: Path = CHROMA_PERSIST_DIR):
        """Initialize ChromaDB client"""
        self.persist_directory = persist_directory
        
        if not self.persist_directory.exists():
            logger.warning(f"ChromaDB directory not found: {self.persist_directory}")
            logger.info("Run ingest.py first to initialize the database")
            self.chroma_client = None
            return
        
        try:
            self.chroma_client = Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(self.persist_directory)
            ))
            logger.info(f"Connected to ChromaDB at {self.persist_directory}")
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {e}")
            self.chroma_client = None
    
    def get_collections(self) -> dict:
        """Get all collections and their stats"""
        if not self.chroma_client:
            return {}
        
        collections = {}
        for category in ["internal", "client", "general"]:
            collection_name = f"anton_egon_{category}"
            try:
                collection = self.chroma_client.get_collection(name=collection_name)
                count = collection.count()
                collections[category] = {
                    "name": collection_name,
                    "count": count,
                    "exists": True
                }
            except Exception:
                collections[category] = {
                    "name": collection_name,
                    "count": 0,
                    "exists": False
                }
        
        return collections
    
    def purge_old_documents(self, days: int = 30, category: Optional[str] = None) -> int:
        """Remove documents older than specified days"""
        if not self.chroma_client:
            logger.error("ChromaDB not initialized")
            return 0
        
        logger.info(f"Purging documents older than {days} days")
        
        cutoff_date = datetime.now(timezone.utc).timestamp() - (days * 86400)
        total_removed = 0
        
        categories_to_purge = [category] if category else ["internal", "client", "general"]
        
        for cat in categories_to_purge:
            collection_name = f"anton_egon_{cat}"
            try:
                collection = self.chroma_client.get_collection(name=collection_name)
                
                # Get all documents
                results = collection.get()
                
                if not results or not results["ids"]:
                    logger.info(f"No documents found in {cat} collection")
                    continue
                
                ids_to_remove = []
                for doc_id, metadata in zip(results["ids"], results["metadatas"]):
                    ingested_at = metadata.get("ingested_at", "")
                    if ingested_at:
                        try:
                            ingested_timestamp = datetime.fromisoformat(
                                ingested_at.replace("Z", "+00:00")
                            ).timestamp()
                            if ingested_timestamp < cutoff_date:
                                ids_to_remove.append(doc_id)
                                logger.debug(f"Marked for removal: {doc_id} ({ingested_at})")
                        except Exception as e:
                            logger.warning(f"Failed to parse date for {doc_id}: {e}")
                
                if ids_to_remove:
                    collection.delete(ids=ids_to_remove)
                    total_removed += len(ids_to_remove)
                    logger.info(f"Removed {len(ids_to_remove)} documents from {cat} collection")
                else:
                    logger.info(f"No documents to remove from {cat} collection")
            
            except Exception as e:
                logger.error(f"Failed to purge {cat} collection: {e}")
        
        if total_removed > 0:
            self.chroma_client.persist()
        
        logger.info(f"Purge complete: {total_removed} documents removed")
        return total_removed
    
    def clear_collection(self, category: str) -> bool:
        """Clear all documents from a specific collection"""
        if not self.chroma_client:
            logger.error("ChromaDB not initialized")
            return False
        
        collection_name = f"anton_egon_{category}"
        try:
            self.chroma_client.delete_collection(name=collection_name)
            logger.info(f"Cleared collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear collection {collection_name}: {e}")
            return False
    
    def get_collection_stats(self, category: str) -> dict:
        """Get detailed stats for a specific collection"""
        if not self.chroma_client:
            return {}
        
        collection_name = f"anton_egon_{category}"
        try:
            collection = self.chroma_client.get_collection(name=collection_name)
            results = collection.get()
            
            if not results or not results["ids"]:
                return {"count": 0, "files": []}
            
            # Aggregate by source file
            files = {}
            for metadata in results["metadatas"]:
                source_file = metadata.get("source_file", "unknown")
                if source_file not in files:
                    files[source_file] = {
                        "chunks": 0,
                        "ingested_at": metadata.get("ingested_at", "unknown"),
                        "category": metadata.get("category", "unknown")
                    }
                files[source_file]["chunks"] += 1
            
            return {
                "count": len(results["ids"]),
                "files": files
            }
        except Exception as e:
            logger.error(f"Failed to get stats for {category}: {e}")
            return {}


# CLI Commands
@click.group()
def cli():
    """Project Anton Egon - Memory Management CLI"""
    pass


@cli.command()
@click.option('--days', default=30, help='Remove documents older than N days (default: 30)')
@click.option('--category', type=click.Choice(['internal', 'client', 'general']), 
              help='Only purge specific category')
def purge(days: int, category: Optional[str]):
    """Remove documents older than specified days"""
    manager = MemoryManager()
    if not manager.chroma_client:
        click.echo("Error: ChromaDB not initialized. Run ingest.py first.")
        sys.exit(1)
    
    removed = manager.purge_old_documents(days=days, category=category)
    click.echo(f"✓ Purged {removed} documents older than {days} days")


@cli.command()
def status():
    """Show status of all memory collections"""
    manager = MemoryManager()
    if not manager.chroma_client:
        click.echo("ChromaDB not initialized. Run ingest.py first.")
        sys.exit(1)
    
    collections = manager.get_collections()
    
    click.echo("\n" + "="*50)
    click.echo("MEMORY COLLECTIONS STATUS")
    click.echo("="*50 + "\n")
    
    for cat, info in collections.items():
        status = "✓" if info["exists"] else "✗"
        click.echo(f"{status} {cat.upper()}: {info['count']} documents")
    
    click.echo("\n" + "="*50 + "\n")


@cli.command()
@click.option('--category', type=click.Choice(['internal', 'client', 'general']), 
              required=True, help='Category to inspect')
def stats(category: str):
    """Show detailed statistics for a specific category"""
    manager = MemoryManager()
    if not manager.chroma_client:
        click.echo("ChromaDB not initialized. Run ingest.py first.")
        sys.exit(1)
    
    stats = manager.get_collection_stats(category)
    
    click.echo(f"\n{category.upper()} COLLECTION STATS")
    click.echo("="*50)
    click.echo(f"Total chunks: {stats['count']}")
    
    if stats['files']:
        click.echo("\nFiles:")
        for filename, info in stats['files'].items():
            click.echo(f"  • {filename}")
            click.echo(f"    Chunks: {info['chunks']}")
            click.echo(f"    Ingested: {info['ingested_at']}")
            click.echo(f"    Category: {info['category']}")
    
    click.echo("\n")


@cli.command()
@click.option('--category', type=click.Choice(['internal', 'client', 'general']), 
              required=True, help='Category to clear')
@click.option('--confirm', is_flag=True, help='Skip confirmation prompt')
def clear(category: str, confirm: bool):
    """Clear all documents from a specific collection"""
    if not confirm:
        click.echo(f"⚠️  WARNING: This will delete ALL documents from the '{category}' collection.")
        click.echo("This action cannot be undone.")
        if not click.confirm("Are you sure?"):
            click.echo("Aborted.")
            return
    
    manager = MemoryManager()
    if not manager.chroma_client:
        click.echo("ChromaDB not initialized. Run ingest.py first.")
        sys.exit(1)
    
    success = manager.clear_collection(category)
    if success:
        click.echo(f"✓ Cleared {category} collection")
    else:
        click.echo(f"✗ Failed to clear {category} collection")


if __name__ == "__main__":
    cli()
