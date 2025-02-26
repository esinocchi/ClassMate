#!/usr/bin/env python3
"""
Vector Database Module
---------------------
Handles storing and retrieving embeddings for Canvas items.

This module provides a semantic search capability for the Canvas Copilot system by
converting textual Canvas items (assignments, announcements, syllabi, etc.) into
numeric vector embeddings that can be efficiently searched based on meaning similarity.

Key features:
1. Stores embeddings for Canvas items in memory
2. Provides similarity-based search functionality
3. Maintains a maximum size with priority-based eviction
4. Supports persistence to disk to avoid recomputing embeddings
5. Prioritizes keeping future assignments in the database

The module uses the SentenceTransformer library to create embeddings, with a focus
on optimizing for accurate retrieval of Canvas LMS data in response to user queries.
"""

import os
import re
import numpy as np
import logging
from typing import List, Tuple, Dict, Any
from datetime import datetime, timezone, timedelta
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Import CanvasItem from canvas_api
from canvas_api import CanvasItem

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger("canvas_copilot")

# Constants
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# Initialize embedding model
try:
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    logger.info(f"Loaded embedding model: {EMBEDDING_MODEL}")
except Exception as e:
    logger.error(f"Failed to load embedding model: {e}")
    embedding_model = None


class VectorDatabase:
    """
    Vector database for storing and retrieving embeddings.
    
    This class manages a collection of Canvas items and their corresponding vector 
    embeddings, providing semantic search capabilities for finding relevant items
    based on query text. It maintains a maximum size with intelligent eviction policies
    and supports persistence to avoid recomputing embeddings.
    """
    
    def __init__(self, embedding_model=embedding_model, max_items=50, persistence_file="vector_db_cache.pkl"):
        """
        Initialize the vector database.
        
        Args:
            embedding_model: The model to use for creating embeddings
            max_items (int): Maximum number of items to store in the database
            persistence_file (str): File path for saving/loading the database state
        """
        self.embedding_model = embedding_model
        self.vectors = []  # Will store numpy arrays
        self.items = []    # Will store corresponding CanvasItem objects
        self.index_map = {}  # Maps item IDs to vector indices
        self.max_items = max_items  # Maximum number of items to store
        self.persistence_file = persistence_file
        self._load_from_cache()
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """
        Get embedding vector for text.
        
        This method converts a text string into a numerical vector representation
        using the specified embedding model. It handles empty strings and errors
        by returning a zero vector.
        
        Args:
            text (str): The text to convert to an embedding vector
            
        Returns:
            np.ndarray: The embedding vector
        """
        if not text.strip():
            return np.zeros(384)  # Default embedding dimension
        
        try:
            # Clean text
            text = re.sub(r'\s+', ' ', text).strip()
            # Get embedding
            embedding = self.embedding_model.encode(text)
            return embedding
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            return np.zeros(384)  # Default embedding dimension
    
    def add_item(self, item: CanvasItem) -> None:
        """
        Add an item to the vector database.
        
        This method creates an embedding for the item and adds it to the database.
        If the database is at capacity, it may evict an existing item based on
        priority rules (e.g., keeping future assignments).
        
        Args:
            item (CanvasItem): The Canvas item to add to the database
        """
        # Check if item already exists
        if item.id in self.index_map:
            logger.info(f"Item {item.id} already exists in database")
            return
            
        # Create combined text for embedding
        text = f"{item.title} {item.content}"
        
        # Get embedding
        embedding = self._get_embedding(text)
        
        # Add to database (with size limit)
        if len(self.items) >= self.max_items:
            # Remove oldest item if we're at capacity (assuming items are added in chronological order)
            if not any(i.type == 'assignment' and self._is_future_assignment(i) for i in self.items[:1]):
                # Only remove if it's not a future assignment
                self.vectors.pop(0)
                removed_item = self.items.pop(0)
                del self.index_map[removed_item.id]
                # Update indices in index_map
                for item_id, idx in list(self.index_map.items()):
                    self.index_map[item_id] = idx - 1
                logger.info(f"Removed oldest item from vector database: {removed_item.title}")
            else:
                # If the oldest item is a future assignment, find the oldest non-future assignment
                for i, item_i in enumerate(self.items):
                    if item_i.type != 'assignment' or not self._is_future_assignment(item_i):
                        self.vectors.pop(i)
                        removed_item = self.items.pop(i)
                        del self.index_map[removed_item.id]
                        # Update indices in index_map
                        for item_id, idx in list(self.index_map.items()):
                            if idx > i:
                                self.index_map[item_id] = idx - 1
                        logger.info(f"Removed item from vector database: {removed_item.title}")
                        break
                else:
                    # If all items are future assignments, just remove the oldest one
                    self.vectors.pop(0)
                    removed_item = self.items.pop(0)
                    del self.index_map[removed_item.id]
                    # Update indices in index_map
                    for item_id, idx in list(self.index_map.items()):
                        self.index_map[item_id] = idx - 1
                    logger.info(f"Removed oldest future assignment from vector database: {removed_item.title}")
        
        # Add the new item
        self.vectors.append(embedding)
        self.items.append(item)
        self.index_map[item.id] = len(self.items) - 1
        
        # Save to cache
        self._save_to_cache()
        
        logger.info(f"Added item to vector database: {item.title}")
    
    def _is_future_assignment(self, item: CanvasItem) -> bool:
        """
        Check if an assignment is due in the future.
        
        This helper method determines if an assignment has a future due date,
        which affects its priority for remaining in the database when eviction
        decisions need to be made.
        
        Args:
            item (CanvasItem): The item to check
            
        Returns:
            bool: True if the item is an assignment with a future due date, False otherwise
        """
        if not item.due_date:
            return False
        
        try:
            # Parse the due date, ensuring it's timezone-aware
            # Handle multiple date formats
            due_date_str = item.due_date
            if 'Z' in due_date_str:
                due_date_str = due_date_str.replace('Z', '+00:00')
            elif '+' not in due_date_str and '-' in due_date_str and 'T' in due_date_str:
                # Add timezone if missing
                due_date_str = due_date_str + '+00:00'
                
            due_date = datetime.fromisoformat(due_date_str)
            
            # Get current time as timezone-aware
            now = datetime.now(timezone.utc)
            
            # For debugging
            logger.debug(f"Comparing {due_date.isoformat()} > {now.isoformat()} = {due_date > now}")
            
            return due_date > now
        except (ValueError, AttributeError) as e:
            logger.error(f"Error checking if assignment is in future: {e} (due_date: {item.due_date})")
            # Try a more lenient parsing approach as fallback
            try:
                if item.due_date:
                    # Strip any timezone info and just do naive comparison as last resort
                    if 'T' in item.due_date:
                        date_part = item.due_date.split('T')[0]
                        due_date = datetime.strptime(date_part, '%Y-%m-%d')
                        now = datetime.now()
                        return due_date.date() >= now.date()
            except Exception as e2:
                logger.error(f"Fallback date parsing also failed: {e2}")
            return False
    
    def add_items(self, items: List[CanvasItem]) -> None:
        """Add multiple items to the vector database, prioritizing future assignments"""
        # Sort items to prioritize future assignments
        sorted_items = sorted(
            items,
            key=lambda x: (
                # Priority 1: Future assignments (1 for yes, 0 for no)
                1 if (x.type == 'assignment' and self._is_future_assignment(x)) else 0,
                # Priority 2: Recency (more recent items first)
                x.updated_at if x.updated_at else ''
            ),
            reverse=True  # Descending order
        )
        
        # Add items (most important first)
        for item in sorted_items:
            if len(self.items) < self.max_items or (item.type == 'assignment' and self._is_future_assignment(item)):
                self.add_item(item)
    
    def _save_to_cache(self) -> None:
        """Save the database to a cache file"""
        try:
            cache_data = {
                'items': self.items,
                'vectors': self.vectors,
                'index_map': self.index_map
            }
            with open(self.persistence_file, 'wb') as f:
                import pickle
                pickle.dump(cache_data, f)
            logger.info(f"Saved vector database to cache ({len(self.items)} items)")
        except Exception as e:
            logger.error(f"Error saving vector database to cache: {e}")
    
    def _load_from_cache(self) -> None:
        """Load the database from a cache file if it exists"""
        try:
            if os.path.exists(self.persistence_file):
                with open(self.persistence_file, 'rb') as f:
                    import pickle
                    cache_data = pickle.load(f)
                self.items = cache_data.get('items', [])
                self.vectors = cache_data.get('vectors', [])
                self.index_map = cache_data.get('index_map', {})
                logger.info(f"Loaded vector database from cache ({len(self.items)} items)")
        except Exception as e:
            logger.error(f"Error loading vector database from cache: {e}")
            # Reset to empty state if there's an error
            self.items = []
            self.vectors = []
            self.index_map = {}
    
    def search(self, query: str, top_k: int = 3) -> List[Tuple[CanvasItem, float]]:
        """Search for items similar to query"""
        if not self.vectors:
            return []
        
        # Get query embedding
        query_embedding = self._get_embedding(query)
        
        # Convert vectors to numpy array for efficient computation
        vectors_array = np.vstack(self.vectors)
        
        # Compute cosine similarity
        similarities = np.dot(vectors_array, query_embedding) / (
            np.linalg.norm(vectors_array, axis=1) * np.linalg.norm(query_embedding)
        )
        
        # Get top k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        # Return items and scores
        results = [(self.items[idx], similarities[idx]) for idx in top_indices]
        
        return results 
    
    def clear_persistence_cache(self) -> None:
        """
        Clear any persistent cache files used by the vector database.
        This removes saved embeddings and items from disk.
        
        Returns:
            None
        """
        try:
            # Check if we have a cache directory defined
            cache_dir = getattr(self, 'cache_dir', None)
            if cache_dir and os.path.exists(cache_dir):
                # Get all cache files
                cache_files = [
                    os.path.join(cache_dir, f) 
                    for f in os.listdir(cache_dir) 
                    if f.startswith('vector_db_') and f.endswith('.pkl')
                ]
                
                # Remove each cache file
                for cache_file in cache_files:
                    try:
                        os.remove(cache_file)
                        logging.info(f"Removed cache file: {cache_file}")
                    except Exception as e:
                        logging.error(f"Error removing cache file {cache_file}: {e}")
                
                logging.info(f"Cleared {len(cache_files)} cache files from {cache_dir}")
            else:
                logging.info("No cache directory found or it doesn't exist")
                
            # Clear in-memory cache
            self.items = []
            self.vectors = []
            
            logging.info("Vector database cache cleared successfully")
        except Exception as e:
            logging.error(f"Error clearing vector database cache: {e}") 