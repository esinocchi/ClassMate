#!/usr/bin/env python3
"""
Vector Database Module for Canvas Data
--------------------------------------
This module processes Canvas course data from a JSON file and creates vector embeddings
using the Hugging Face Inference API with the all-MiniLM-L6-v2 model.

Key features:
1. Loads Canvas course data from a structured JSON file (evan_data.json)
2. Creates embeddings via Hugging Face Inference API (no local model required)
3. Stores embeddings in memory with document metadata for efficient retrieval
4. Provides similarity search functionality to find relevant course materials
5. Supports filtering by course ID to narrow search results
6. Includes persistence to avoid recomputing embeddings
7. Optimizes embeddings for Canvas-specific content types
8. Supports contextual search with related documents

The module is designed to be resource-efficient (no local GPU/CPU needed for inference)
while still providing good semantic search capabilities.

Usage:
1. Set your HUGGINGFACE_API_KEY in environment variables
2. Initialize the VectorDatabase with the path to your JSON data file
3. Call process_data() to create embeddings for all documents
4. Use search() to find relevant documents based on a query
"""

import os
import json
import numpy as np
import logging
import requests
import time
from typing import List, Dict, Any, Tuple, Optional, Set
from datetime import datetime
import pickle
from dotenv import load_dotenv
import re
from collections import defaultdict

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("canvas_vector_db")

# Constants
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 384-dimensional embeddings
HUGGINGFACE_API_URL = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{EMBEDDING_MODEL}"
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
CACHE_DIR = "cache"
DEFAULT_CACHE_FILE = os.path.join(CACHE_DIR, "vector_db_cache.pkl")

# Canvas content type weights (for enhancing importance of certain fields)
CONTENT_TYPE_WEIGHTS = {
    "syllabus": 1.5,      # Syllabus is highly important
    "assignment": 1.3,    # Assignments are important
    "quiz": 1.3,          # Quizzes are important
    "discussion": 1.2,    # Discussions are important
    "page": 1.1,          # Pages are moderately important
    "announcement": 1.2,  # Announcements are important
    "module": 1.0,        # Modules are baseline
    "file": 1.0,          # Files are baseline
    "external_tool": 0.8, # External tools are less important
    "external_url": 0.8,  # External URLs are less important
    "home_page": 1.2,     # Home page is important
    "default": 1.0        # Default for unknown types
}

# Check if API key is available
if not HUGGINGFACE_API_KEY:
    logger.warning("HUGGINGFACE_API_KEY not found in environment variables. API calls will likely fail.")


class VectorDatabase:
    """
    Vector database for storing and retrieving embeddings of Canvas course data.
    
    This class processes a JSON file containing Canvas course data, creates embeddings
    via the Hugging Face API, and provides search functionality to find relevant documents
    based on semantic similarity.
    """
    
    def __init__(self, json_file_path: str, cache_file: str = DEFAULT_CACHE_FILE):
        """
        Initialize the vector database.
        
        Args:
            json_file_path (str): Path to the JSON file containing Canvas data
            cache_file (str): Path to save/load the database cache
        """
        self.json_file_path = json_file_path
        self.cache_file = cache_file
        self.documents = []  # Will store document metadata
        self.vectors = []    # Will store corresponding embedding vectors
        self.course_ids = set()  # Track available course IDs
        self.course_info = {}  # Store course information for context enrichment
        self.document_relations = defaultdict(set)  # Track document relationships
        
        # Create cache directory if it doesn't exist
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        
        # Set up API headers
        self.api_headers = {
            "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
            "Content-Type": "application/json"
        }
            
        # Try to load from cache first
        if not self._load_from_cache():
            logger.info("No valid cache found. Will need to process data from JSON.")
    
    def _create_embedding(self, text: str, max_retries: int = 3) -> np.ndarray:
        """
        Create an embedding vector for the given text using Hugging Face API.
        
        Args:
            text (str): The text to embed
            max_retries (int): Maximum number of retry attempts for API calls
            
        Returns:
            np.ndarray: The embedding vector
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            return np.zeros(384)  # Default dimension for MiniLM
            
        # Clean and truncate text if needed
        clean_text = ' '.join(text.split())
        if len(clean_text) > 8192:  # Arbitrary limit to avoid very long texts
            clean_text = clean_text[:8192]
        
        # Try to get embedding from API with retries
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    HUGGINGFACE_API_URL,
                    headers=self.api_headers,
                    json={"inputs": clean_text, "options": {"wait_for_model": True}}
                )
                
                if response.status_code == 200:
                    # Successfully got embedding
                    embedding = np.array(response.json())
                    return embedding
                elif response.status_code == 503:
                    # Model is loading, wait and retry
                    logger.info(f"Model is loading. Waiting before retry {attempt+1}/{max_retries}...")
                    time.sleep(20)  # Wait 20 seconds before retrying
                else:
                    # Other error
                    logger.error(f"API error: {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        time.sleep(5)  # Wait 5 seconds before retrying
            except Exception as e:
                logger.error(f"Error creating embedding: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)  # Wait 5 seconds before retrying
        
        # If we get here, all retries failed
        logger.error(f"Failed to create embedding after {max_retries} attempts")
        return np.zeros(384)  # Return zero vector as fallback
    
    def _batch_create_embeddings(self, texts: List[str], batch_size: int = 8) -> List[np.ndarray]:
        """
        Create embeddings for multiple texts in batches to optimize API usage.
        
        Args:
            texts (List[str]): List of texts to embed
            batch_size (int): Number of texts to process in each API call
            
        Returns:
            List[np.ndarray]: List of embedding vectors
        """
        embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch_texts)} texts)")
            
            try:
                # Clean and prepare texts
                clean_texts = [' '.join(text.split())[:8192] for text in batch_texts]
                
                # Make API call
                response = requests.post(
                    HUGGINGFACE_API_URL,
                    headers=self.api_headers,
                    json={"inputs": clean_texts, "options": {"wait_for_model": True}}
                )
                
                if response.status_code == 200:
                    # Successfully got embeddings
                    batch_embeddings = [np.array(emb) for emb in response.json()]
                    embeddings.extend(batch_embeddings)
                else:
                    # Error, fall back to individual processing
                    logger.warning(f"Batch processing failed with status {response.status_code}. Falling back to individual processing.")
                    for text in batch_texts:
                        embeddings.append(self._create_embedding(text))
            except Exception as e:
                logger.error(f"Error in batch processing: {e}")
                # Fall back to individual processing
                for text in batch_texts:
                    embeddings.append(self._create_embedding(text))
            
            # Add a small delay between batches to avoid rate limiting
            if i + batch_size < len(texts):
                time.sleep(1)
        
        return embeddings
    
    def _preprocess_text_for_embedding(self, doc: Dict[str, Any]) -> str:
        """
        Preprocess text for embedding with Canvas-specific optimizations.
        
        Args:
            doc (Dict[str, Any]): Document metadata
            
        Returns:
            str: Optimized text for embedding
        """
        doc_type = doc.get("type", "unknown")
        title = doc.get("title", "")
        content = doc.get("content", "")
        
        # Basic cleaning - remove HTML tags
        clean_content = re.sub(r'<[^>]+>', ' ', content)
        
        # Add type-specific prefix to help with context
        type_prefix = f"[{doc_type.upper()}] "
        
        # For different content types, optimize differently
        if doc_type == "syllabus":
            # For syllabus, we want to emphasize it's a syllabus 
            processed_text = f"{type_prefix}{title} SYLLABUS: {clean_content}"
        
        elif doc_type == "assignment":
            # For assignments, include due date in the text if available
            due_date = doc.get("due_date", "")
            due_date_text = f" Due: {due_date}" if due_date else ""
            processed_text = f"{type_prefix}{title}{due_date_text}. {clean_content}"
        
        elif doc_type == "quiz":
            # For quizzes, include due date in the text if available
            due_date = doc.get("due_date", "")
            due_date_text = f" Due: {due_date}" if due_date else ""
            processed_text = f"{type_prefix}{title}{due_date_text}. QUIZ: {clean_content}"
        
        elif doc_type == "discussion":
            # For discussions, emphasize it's a discussion
            processed_text = f"{type_prefix}{title}. DISCUSSION: {clean_content}"
        
        elif doc_type == "announcement":
            # For announcements, include date at the beginning for recency
            processed_text = f"{type_prefix}{title}. ANNOUNCEMENT: {clean_content}"
        
        elif doc_type == "file":
            # For files, include file type if available
            file_type = doc.get("file_type", "")
            file_type_text = f" [{file_type}]" if file_type else ""
            processed_text = f"{type_prefix}{title}{file_type_text}. {clean_content}"
        
        else:
            # Default processing for other types
            processed_text = f"{type_prefix}{title}. {clean_content}"
        
        return processed_text
    
    def _extract_additional_keywords(self, doc: Dict[str, Any]) -> List[str]:
        """
        Extract additional keywords from document based on its type and content.
        
        Args:
            doc (Dict[str, Any]): Document metadata
            
        Returns:
            List[str]: List of additional keywords
        """
        keywords = []
        doc_type = doc.get("type", "")
        
        # Add document type as a keyword
        keywords.append(doc_type)
        
        # Add course code if available in course_info
        course_id = doc.get("course_id", "")
        if course_id in self.course_info:
            course_code = self.course_info[course_id].get("code", "")
            if course_code:
                keywords.append(course_code)
        
        # Type-specific keywords
        if doc_type == "assignment":
            keywords.extend(["homework", "assignment", "submit", "due"])
            due_date = doc.get("due_date")
            if due_date:
                keywords.append("deadline")
        
        elif doc_type == "quiz":
            keywords.extend(["test", "quiz", "exam", "assessment"])
        
        elif doc_type == "syllabus":
            keywords.extend(["syllabus", "course policy", "grading", "schedule"])
        
        elif doc_type == "discussion":
            keywords.extend(["discussion", "forum", "post", "reply"])
        
        elif doc_type == "file":
            file_type = doc.get("file_type", "").lower()
            file_name = doc.get("title", "").lower()
            
            # Add file type specific keywords
            if file_type == "pdf" or ".pdf" in file_name:
                keywords.extend(["pdf", "document"])
            elif file_type in ["doc", "docx"] or any(ext in file_name for ext in [".doc", ".docx"]):
                keywords.extend(["word", "document"])
            elif file_type in ["ppt", "pptx"] or any(ext in file_name for ext in [".ppt", ".pptx"]):
                keywords.extend(["powerpoint", "slides", "presentation"])
            elif file_type in ["xls", "xlsx"] or any(ext in file_name for ext in [".xls", ".xlsx"]):
                keywords.extend(["excel", "spreadsheet"])
            
            # Look for common academic file patterns
            if "syllabus" in file_name:
                keywords.extend(["course syllabus", "syllabus"])
            if "lecture" in file_name:
                keywords.extend(["lecture", "notes"])
            if any(hw_term in file_name for hw_term in ["hw", "homework", "assignment"]):
                keywords.extend(["homework", "assignment"])
            if "rubric" in file_name:
                keywords.extend(["rubric", "grading"])
        
        return keywords
    
    def process_data(self, force_reload: bool = False) -> bool:
        """
        Process the JSON data file and create embeddings for all documents.
        
        Args:
            force_reload (bool): If True, reload data even if cache exists
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        if self.vectors and not force_reload:
            logger.info(f"Using cached embeddings for {len(self.vectors)} documents")
            return True
            
        try:
            # Load the JSON data
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            logger.info(f"Loaded JSON data from {self.json_file_path}")
            
            # Reset existing data
            self.documents = []
            self.vectors = []
            self.course_ids = set()
            self.course_info = {}
            self.document_relations = defaultdict(set)
            
            # First, extract course information for context enrichment
            if "courses" in data:
                for course_id, course_data in data["courses"].items():
                    self.course_info[course_id] = {
                        "name": course_data.get("name", ""),
                        "code": course_data.get("code", ""),
                        "description": course_data.get("description", "")
                    }
            
            # Process documents
            if "documents" in data:
                # Filter documents with content
                valid_docs = [doc for doc in data["documents"] if doc.get("content") and doc.get("content").strip()]
                total_docs = len(valid_docs)
                logger.info(f"Processing {total_docs} documents with content")
                
                # First, build document relations for context enrichment
                self._build_document_relations(valid_docs)
                
                # Prepare texts for batch processing with enhanced context
                texts = []
                for doc in valid_docs:
                    # Apply Canvas-specific preprocessing
                    processed_text = self._preprocess_text_for_embedding(doc)
                    
                    # Extract and add additional keywords
                    keywords = self._extract_additional_keywords(doc)
                    if keywords:
                        processed_text = f"{processed_text} KEYWORDS: {', '.join(keywords)}"
                    
                    texts.append(processed_text)
                
                # Get embeddings in batches
                embeddings = self._batch_create_embeddings(texts)
                
                # Post-process embeddings by type weighting
                weighted_embeddings = self._apply_type_weights(valid_docs, embeddings)
                
                # Store document metadata and embeddings
                for i, doc in enumerate(valid_docs):
                    doc_id = doc.get("id", f"doc_{i}")
                    course_id = doc.get("course_id", "unknown")
                    
                    # Store the full document metadata for search results
                    doc_metadata = {
                        "id": doc_id,
                        "course_id": course_id,
                        "type": doc.get("type", "unknown"),
                        "title": doc.get("title", ""),
                        "content": doc.get("content", ""),
                        "url": doc.get("url", ""),
                        "created_at": doc.get("created_at"),
                        "updated_at": doc.get("updated_at"),
                        "due_date": doc.get("due_date")
                    }
                    
                    # Add type-specific fields from original document
                    for key, value in doc.items():
                        if key not in doc_metadata and value is not None:
                            doc_metadata[key] = value
                    
                    # Add related documents
                    if doc_id in self.document_relations:
                        doc_metadata["related_documents"] = list(self.document_relations[doc_id])
                    
                    # Add enriched course context
                    if course_id in self.course_info:
                        doc_metadata["course_name"] = self.course_info[course_id].get("name", "")
                        doc_metadata["course_code"] = self.course_info[course_id].get("code", "")
                    
                    self.documents.append(doc_metadata)
                    self.vectors.append(weighted_embeddings[i])
                    self.course_ids.add(course_id)
            
            # Save to cache
            self._save_to_cache()
            
            logger.info(f"Successfully processed {len(self.documents)} documents with content")
            logger.info(f"Available course IDs: {self.course_ids}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing JSON data: {e}")
            return False
    
    def _build_document_relations(self, documents: List[Dict[str, Any]]) -> None:
        """
        Build relationships between documents based on Canvas-specific connections.
        
        Args:
            documents (List[Dict[str, Any]]): List of document metadata
        """
        # Create a lookup dictionary for documents by ID and by module_id
        doc_by_id = {doc.get("id"): doc for doc in documents if doc.get("id")}
        docs_by_module = defaultdict(list)
        
        for doc in documents:
            # Group documents by module
            module_id = doc.get("module_id")
            if module_id:
                docs_by_module[module_id].append(doc.get("id"))
            
            # Connect based on parent-child relationships
            parent_id = doc.get("parent_id")
            if parent_id and parent_id in doc_by_id:
                self.document_relations[doc.get("id")].add(parent_id)
                self.document_relations[parent_id].add(doc.get("id"))
            
            # Connect based on referenced files
            ref_file = doc.get("references_file")
            if ref_file and ref_file in doc_by_id:
                self.document_relations[doc.get("id")].add(ref_file)
                self.document_relations[ref_file].add(doc.get("id"))
        
        # Connect documents within the same module
        for module_docs in docs_by_module.values():
            for doc_id in module_docs:
                for other_id in module_docs:
                    if doc_id != other_id:
                        self.document_relations[doc_id].add(other_id)
    
    def _apply_type_weights(self, documents: List[Dict[str, Any]], embeddings: List[np.ndarray]) -> List[np.ndarray]:
        """
        Apply type-specific weights to embeddings to enhance certain content types.
        
        Args:
            documents (List[Dict[str, Any]]): List of document metadata
            embeddings (List[np.ndarray]): List of embedding vectors
            
        Returns:
            List[np.ndarray]: List of weighted embedding vectors
        """
        weighted_embeddings = []
        
        for i, doc in enumerate(documents):
            doc_type = doc.get("type", "unknown").lower()
            weight = CONTENT_TYPE_WEIGHTS.get(doc_type, CONTENT_TYPE_WEIGHTS["default"])
            
            # Apply weight but preserve vector magnitude
            if weight != 1.0:
                # Normalize, apply weight, then normalize again
                embedding = embeddings[i]
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    normalized = embedding / norm
                    weighted = normalized * weight
                    # Re-normalize to preserve cosine similarity properties
                    weighted_norm = np.linalg.norm(weighted)
                    if weighted_norm > 0:
                        weighted = weighted / weighted_norm * norm
                    weighted_embeddings.append(weighted)
                else:
                    weighted_embeddings.append(embedding)
            else:
                weighted_embeddings.append(embeddings[i])
        
        return weighted_embeddings
    
    def _save_to_cache(self) -> bool:
        """
        Save the database to a cache file.
        
        Returns:
            bool: True if saving was successful, False otherwise
        """
        try:
            cache_data = {
                "documents": self.documents,
                "vectors": self.vectors,
                "course_ids": self.course_ids,
                "course_info": self.course_info,
                "document_relations": dict(self.document_relations),
                "model_name": EMBEDDING_MODEL,
                "timestamp": datetime.now().isoformat()
            }
            
            with open(self.cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
                
            logger.info(f"Saved vector database to cache: {self.cache_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving to cache: {e}")
            return False
    
    def _load_from_cache(self) -> bool:
        """
        Load the database from a cache file if it exists.
        
        Returns:
            bool: True if loading was successful, False otherwise
        """
        if not os.path.exists(self.cache_file):
            return False
            
        try:
            with open(self.cache_file, 'rb') as f:
                cache_data = pickle.load(f)
                
            # Verify cache data has expected structure
            if not all(key in cache_data for key in ["documents", "vectors", "course_ids"]):
                logger.warning("Cache file has invalid structure")
                return False
                
            # Check if the model matches
            if cache_data.get("model_name") != EMBEDDING_MODEL:
                logger.warning(f"Cache was created with a different model: {cache_data.get('model_name')}")
                return False
                
            # Load the data
            self.documents = cache_data["documents"]
            self.vectors = cache_data["vectors"]
            self.course_ids = cache_data["course_ids"]
            
            # Load new fields or set defaults
            self.course_info = cache_data.get("course_info", {})
            
            if "document_relations" in cache_data:
                self.document_relations = defaultdict(set)
                for doc_id, related in cache_data["document_relations"].items():
                    self.document_relations[doc_id] = set(related)
            
            logger.info(f"Loaded {len(self.documents)} documents from cache")
            return True
        except Exception as e:
            logger.error(f"Error loading from cache: {e}")
            return False
    
    def _enhance_query(self, query: str) -> str:
        """
        Enhance query with Canvas-specific context to improve search results.
        
        Args:
            query (str): Original search query
            
        Returns:
            str: Enhanced search query
        """
        # Look for Canvas-specific keywords and enhance query
        enhanced_query = query
        
        # Handle common Canvas queries
        if re.search(r'\b(hw|homework|assignment)\b', query, re.IGNORECASE):
            enhanced_query = f"assignment {enhanced_query}"
        
        if re.search(r'\b(quiz|test|exam)\b', query, re.IGNORECASE):
            enhanced_query = f"quiz {enhanced_query}"
        
        if re.search(r'\b(syllabus)\b', query, re.IGNORECASE):
            enhanced_query = f"syllabus {enhanced_query}"
        
        if re.search(r'\b(slides|powerpoint|presentation)\b', query, re.IGNORECASE):
            enhanced_query = f"lecture slides {enhanced_query}"
        
        if re.search(r'\b(reading|chapter)\b', query, re.IGNORECASE):
            enhanced_query = f"reading material {enhanced_query}"
        
        # Handle due date queries
        if re.search(r'\b(due|deadline)\b', query, re.IGNORECASE):
            enhanced_query = f"due date deadline {enhanced_query}"
        
        return enhanced_query
    
    def search(self, query: str, course_ids: Optional[List[str]] = None, top_k: int = 5,
               include_related: bool = True, minimum_score: float = 0.3) -> List[Dict[str, Any]]:
        """
        Search for documents similar to the query.
        
        Args:
            query (str): The search query
            course_ids (List[str], optional): List of course IDs to filter results
            top_k (int): Maximum number of results to return
            include_related (bool): Whether to include related documents
            minimum_score (float): Minimum similarity score to include in results
            
        Returns:
            List[Dict[str, Any]]: List of document metadata with similarity scores
        """
        if not self.vectors:
            logger.warning("No vectors available for search. Call process_data() first.")
            return []
            
        # Enhance query with Canvas-specific context
        enhanced_query = self._enhance_query(query)
        
        # Create query embedding
        query_embedding = self._create_embedding(enhanced_query)
        
        # Convert vectors to numpy array for efficient computation
        vectors_array = np.vstack(self.vectors)
        
        # Compute cosine similarity
        similarities = np.dot(vectors_array, query_embedding) / (
            np.linalg.norm(vectors_array, axis=1) * np.linalg.norm(query_embedding)
        )
        
        # Create list of (index, similarity) tuples
        results = [(i, similarities[i]) for i in range(len(similarities))]
        
        # Filter by course ID if specified
        if course_ids:
            results = [
                (i, score) for i, score in results
                if self.documents[i]["course_id"] in course_ids
            ]
        
        # Filter by minimum score
        results = [(i, score) for i, score in results if score >= minimum_score]
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Get top k results
        top_results = results[:top_k]
        
        # Format results
        formatted_results = []
        included_doc_ids = set()
        
        for idx, score in top_results:
            doc = self.documents[idx].copy()
            doc["similarity"] = float(score)
            formatted_results.append(doc)
            included_doc_ids.add(doc["id"])
            
            # Add related documents if requested
            if include_related and "related_documents" in doc:
                remaining_slots = top_k - len(formatted_results)
                if remaining_slots > 0:
                    # Find related documents with their similarity scores
                    related_docs = []
                    for related_id in doc["related_documents"]:
                        if related_id in included_doc_ids:
                            continue  # Skip already included documents
                            
                        # Find the document by ID
                        for rel_idx, rel_doc in enumerate(self.documents):
                            if rel_doc["id"] == related_id:
                                rel_score = similarities[rel_idx]
                                if rel_score >= minimum_score:
                                    related_docs.append((rel_idx, rel_score))
                                break
                    
                    # Sort by similarity and take top remaining_slots
                    related_docs.sort(key=lambda x: x[1], reverse=True)
                    for rel_idx, rel_score in related_docs[:remaining_slots]:
                        rel_doc = self.documents[rel_idx].copy()
                        rel_doc["similarity"] = float(rel_score)
                        rel_doc["included_as_related"] = True
                        formatted_results.append(rel_doc)
                        included_doc_ids.add(rel_doc["id"])
        
        return formatted_results
    
    def get_available_courses(self) -> List[Dict[str, Any]]:
        """
        Get a list of available courses with details.
        
        Returns:
            List[Dict[str, Any]]: List of course details
        """
        courses = []
        for course_id in self.course_ids:
            course_info = self.course_info.get(course_id, {})
            courses.append({
                "id": course_id,
                "name": course_info.get("name", ""),
                "code": course_info.get("code", "")
            })
        return courses
    
    def clear_cache(self) -> None:
        """
        Clear the cache file.
        """
        if os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
                logger.info(f"Cleared cache file: {self.cache_file}")
            except Exception as e:
                logger.error(f"Error clearing cache: {e}")


# Example usage
if __name__ == "__main__":
    # Initialize the vector database with the path to your JSON data file
    db = VectorDatabase("user_data/CanvasAI/UserData/psu.instructure.com/1234/evan_data.json")
        
    # Process the data to create embeddings for all documents
    if db.process_data():
        # Example search query
        query = "Lab 2"
        
        # Example of filtering by course ID
        course_id = "2379517"  # The course ID for CMPSC 311
        results = db.search(query, course_ids=[course_id], top_k=5, include_related=True, minimum_score=0.3)
        
        # Print results
        print(f"Found {len(results)} results for query '{query}':")
        for i, result in enumerate(results):
            print(f"{i + 1}. {result['title']} (Score: {result['similarity']:.4f})")
            print(f"   Type: {result['type']}, Course: {result['course_id']}")
            print(f"   URL: {result['url']}")
            print(f"   Content preview: {result['content'][:100]}...")
            if 'included_as_related' in result:
                print("   This document is related to another document.")
            print()
    else:
        print("Failed to process data.") 