"""
Embedding Model Module for Vector Database
------------------------------------------
This module provides embedding functions for ChromaDB using the Hugging Face API.
It supports various embedding models including the multilingual-e5-large-instruct model.

The main class HFEmbeddingFunction implements the ChromaDB embedding function interface,
ensuring proper formatting of input texts for specific models like E5 (which requires a "passage:" prefix).
"""

import logging
import numpy as np
import aiohttp
import requests  # Keep for backward compatibility
import asyncio
from typing import List, Optional, Union

# Configure logging
logger = logging.getLogger("canvas_vector_db.embedding")

class HFEmbeddingFunction:
    """
    Embedding function class for Hugging Face models that implements
    the ChromaDB embedding function interface.
    """
    
    def __init__(self, api_token, model_id="intfloat/multilingual-e5-large-instruct"):
        """
        Initialize the embedding function with the Hugging Face API token and model ID.
        
        Args:
            api_token: Hugging Face API token
            model_id: Model ID to use for embeddings (default: "intfloat/multilingual-e5-large-instruct")
        """
        self.model_id = model_id
        self.api_url = f"https://api-inference.huggingface.co/models/{model_id}"
        self.headers = {"Authorization": f"Bearer {api_token}"}
        
        # Determine embedding dimensions based on model
        if "large" in model_id.lower():
            self.embedding_dims = 1024
        elif "base" in model_id.lower():
            self.embedding_dims = 768
        elif "small" in model_id.lower():
            self.embedding_dims = 384
        else:
            self.embedding_dims = 1024  # default to large model dimensions
            
        logger.info(f"Initialized HF embedding function with model: {model_id}")
        
    def __call__(self, input):
        """
        Generate embeddings for the input texts.
        This signature matches what ChromaDB expects.
        
        Args:
            input: List of text strings to embed
            
        Returns:
            Numpy array of embeddings
        """
        # For ChromaDB compatibility, provide a synchronous interface
        # but using requests instead of aiohttp
        
        # Handle empty input case
        if not input:
            return []
        
        # Constants
        max_chars = 2000  # Estimate for ~512 tokens
        batch_size = 32   # Process in smaller batches
        
        result_embeddings = []
        
        # Process in batches
        for i in range(0, len(input), batch_size):
            batch = input[i:i+batch_size]
            
            # Truncate long texts and add prefix
            formatted_texts = [f"passage: {text[:max_chars]}" for text in batch]
            
            try:
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json={"inputs": formatted_texts, "options": {"wait_for_model": True}}
                )
                
                if response.status_code != 200:
                    logger.error(f"API request failed with status code {response.status_code}: {response.text}")
                    # Add placeholders for this batch
                    for _ in batch:
                        result_embeddings.append(np.zeros(self.embedding_dims, dtype=np.float32))
                    continue
                
                batch_embeddings = response.json()
                
                if isinstance(batch_embeddings, list):
                    result_embeddings.extend(batch_embeddings)
                else:
                    # Handle error by adding placeholder embeddings
                    logger.error(f"Unexpected API response format: {batch_embeddings}")
                    for _ in batch:
                        result_embeddings.append(np.zeros(self.embedding_dims))
                
            except Exception as e:
                logger.error(f"Error calling Hugging Face API for batch {i//batch_size}: {e}")
                # Add placeholder embeddings for the entire batch
                for _ in batch:
                    result_embeddings.append(np.zeros(self.embedding_dims, dtype=np.float32))
        
        # Important: We must ensure we have exactly one embedding per input document
        if len(result_embeddings) != len(input):
            logger.error(f"Embedding count mismatch: {len(result_embeddings)} embeddings for {len(input)} inputs")
            # Ensure we have the right number of embeddings
            if len(result_embeddings) < len(input):
                # Add missing embeddings
                for _ in range(len(input) - len(result_embeddings)):
                    result_embeddings.append(np.zeros(self.embedding_dims, dtype=np.float32))
            else:
                # Truncate extra embeddings
                result_embeddings = result_embeddings[:len(input)]
        
        # Convert to numpy array with correct shape
        final_embeddings = np.array(result_embeddings, dtype=np.float32)
        logger.info(f"Generated embeddings with shape: {final_embeddings.shape}")
        
        # Final check to ensure non-empty output
        if final_embeddings.size == 0:
            logger.error("Generated empty embeddings array! Returning placeholder.")
            return np.zeros((len(input), self.embedding_dims), dtype=np.float32)
        
        return final_embeddings.tolist()
    
    # For backward compatibility: synchronous method that calls the async one
    def generate_embeddings_sync(self, input: List[str]) -> np.ndarray:
        """
        Synchronously generate embeddings for the input texts.
        
        Args:
            input: List of text strings to embed
            
        Returns:
            Numpy array of embeddings
        """
        return asyncio.run(self.generate_embeddings(input))

async def create_async_hf_embedding_function(api_token, model_id="intfloat/multilingual-e5-large-instruct"):
    """
    Create and return an async Hugging Face embedding function.
    
    Args:
        api_token: Hugging Face API token
        model_id: Model ID to use for embeddings
        
    Returns:
        HFEmbeddingFunction instance
    """
    return HFEmbeddingFunction(api_token, model_id)

def create_hf_embedding_function(api_token, model_id="intfloat/multilingual-e5-large-instruct"):
    """
    Create and return a Hugging Face embedding function for ChromaDB.
    
    Args:
        api_token: Hugging Face API token
        model_id: Model ID to use for embeddings
        
    Returns:
        HFEmbeddingFunction instance
    """
    return HFEmbeddingFunction(api_token, model_id) 