"""
Embedding Model Module for Vector Database
------------------------------------------
This module provides an embedding function using a local Sentence Transformer model.
It currently uses 'intfloat/e5-small-v2'.

The main class SentenceTransformerEmbeddingFunction implements the interface
expected by the vector database module.
"""

import logging
import numpy as np
from typing import List
# Import SentenceTransformer
from sentence_transformers import SentenceTransformer

# Configure logging
logger = logging.getLogger("canvas_vector_db.embedding")

class SentenceTransformerEmbeddingFunction:
    """
    Embedding function class using a local Sentence Transformer model.
    """

    def __init__(self, model_id="intfloat/e5-small-v2"):
        """
        Initialize the embedding function with a Sentence Transformer model ID.

        Args:
            model_id: Model ID to load from sentence-transformers
                      (default: "intfloat/e5-small-v2")
        """
        try:
            # Load the Sentence Transformer model
            self.model = SentenceTransformer(model_id)
            self.model_id = model_id
            # Get embedding dimensions from the loaded model
            self.embedding_dims = self.model.get_sentence_embedding_dimension()
            logger.info(f"Initialized Sentence Transformer embedding function with model: {model_id}")
            logger.info(f"Embedding dimensions: {self.embedding_dims}")
        except Exception as e:
            logger.error(f"Failed to load Sentence Transformer model '{model_id}': {e}")
            raise # Re-raise the exception as the function cannot operate without the model

    def __call__(self, input_texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for the input texts using the local model.

        Args:
            input_texts: List of text strings to embed.

        Returns:
            List of lists of floats representing the embeddings.
        """
        if not input_texts:
            logger.warning("Received empty list for embedding.")
            return []

        try:
            # Encode the texts using the loaded Sentence Transformer model
            # The model handles batching internally.
            # convert_to_numpy=True is default, but explicit for clarity.
            # show_progress_bar can be helpful for large inputs.
            embeddings_np = self.model.encode(
                input_texts,
                convert_to_numpy=True,
                show_progress_bar=False # Set to True for debugging large batches
            )

            # Ensure the output shape is correct
            if embeddings_np.shape[0] != len(input_texts) or embeddings_np.shape[1] != self.embedding_dims:
                 logger.error(f"Embedding shape mismatch: Expected ({len(input_texts)}, {self.embedding_dims}), Got {embeddings_np.shape}")
                 # Handle mismatch - potentially return placeholders or raise error
                 # Returning placeholders for robustness, similar to previous logic
                 return [np.zeros(self.embedding_dims, dtype=np.float32).tolist() for _ in input_texts]


            logger.info(f"Generated embeddings with shape: {embeddings_np.shape}")

            # Convert numpy array to list of lists (as expected by Qdrant client)
            return embeddings_np.tolist()

        except Exception as e:
            logger.error(f"Error during Sentence Transformer encoding: {e}")
            # Return placeholder embeddings on error
            return [np.zeros(self.embedding_dims, dtype=np.float32).tolist() for _ in input_texts]

# Update the factory function name and remove api_token parameter
def create_embedding_function(model_id="intfloat/e5-small-v2"):
    """
    Create and return a Sentence Transformer embedding function.

    Args:
        model_id: Model ID to use for embeddings

    Returns:
        SentenceTransformerEmbeddingFunction instance
    """
    # No API token needed now
    return SentenceTransformerEmbeddingFunction(model_id)
