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
import logging
import numpy as np
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("canvas_vector_db")

# Constants"
DEFAULT_CACHE_DIR = "chroma_data/"
DEFAULT_COLLECTION_NAME = "canvas_embeddings"
class VectorDatabase:
    def __init__(self, json_file_path: str, cache_dir: str = DEFAULT_CACHE_DIR, collection_name: str = DEFAULT_COLLECTION_NAME):
        """
        Initialize the vector database with ChromaDB.
        
        Args:
            json_file_path: Path to the JSON file containing the documents.
            cache_dir: Directory to store ChromaDB data.
            collection_name: Name of the ChromaDB collection.
        """
        self.json_file_path = json_file_path
        self.cache_dir = cache_dir
        self.collection_name = collection_name
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(path=cache_dir)
        
        # Initialize embedding function (using the same model as before: all-MiniLM-L6-v2)
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        # Initialize documents and metadata
        self.documents = [] # stores documents
        self.document_map = {} # maps documents with document ID
        self.course_map = {} # information about courses
        
        
        try: # Attempts to retrieve existing collection
            self.collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            logger.info(f"Using existing collection: {collection_name}")
        
        except Exception: # If no existing collection, collection is created
            logger.info(f"Creating new collection: {collection_name}")
            self.collection = self.client.create_collection(
                name=collection_name,
                embedding_function=self.embedding_function,
                # HNSW algorithm for apporximate nearest neighbor in high dimensional spaces
                # using cosine similarity
                metadata={"hnsw:space": "cosine"}
            )
    
    def _preprocess_text_for_embedding(self, doc: Dict[str, Any]) -> str:
        """
        Preprocess document text for embedding.
        
        Args:
            doc: Singular Item dictionary from user_data
            
        Returns:
            Preprocessed text string that is sent to chromadb for embedding
        """
        doc_type = doc.get('type', '').lower()
        course_id = doc.get('course_id', '')
        doc_id = doc.get('id', '')
        content = doc.get('content', '')

        types = ['file', 'assignment', 'announcement', 'quiz', 'event']
        
        # Build a rich text representation with all relevant fields
        text_parts = [f"Type: {doc_type.capitalize()}"]
        
        if course_id:
            text_parts.append(f"Course ID: {course_id}")
        
        if doc_id:
            text_parts.append(f"ID: {doc_id}")
        
        # Add different fields based on document type
        match doc_type:
            case 'file':
                file_type = doc.get('file_type', '') # e.g. pdf, docx, etc.
                size = doc.get('size_kb', '')
                if file_type:
                    text_parts.append(f"File Type: {file_type}")
                if size:
                    text_parts.append(f"Size: {size} KB")
                
            case 'assignment':
                due_date = doc.get('due_date', '')
                points = doc.get('points_possible', '')
                points_possible = doc.get('points_possible', '')
                if due_date:
                    text_parts.append(f"Due Date: {due_date}")
                if points:
                    text_parts.append(f"Points: {points}")
                if points_possible:
                    text_parts.append(f"Points Possible: {points_possible}")
                
            case 'announcement':
                created_at = doc.get('created_at', '')
                if created_at:
                    text_parts.append(f"Posted: {created_at}")
                
            case 'quiz':
                due_date = doc.get('due_date', '')
                points = doc.get('points_possible', '')
                if due_date:
                    text_parts.append(f"Due Date: {due_date}")
                if points:
                    text_parts.append(f"Points: {points}")
                
            case 'event':
                start_date = doc.get('created_at', '')
                if start_date:
                    text_parts.append(f"Date: {start_date}")
        
        # Add metadata timestamps if available
        created = doc.get('created_at', '')
        updated = doc.get('updated_at', '')
        if created:
            text_parts.append(f"Created: {created}")
        if updated:
            text_parts.append(f"Updated: {updated}")

        module = doc.get('module_name', '')
        if module:
            text_parts.append(f"Module: {module}")
        
        # Add the content at the end
        if content:
            text_parts.append(f"Content: {content}")
        
        # Join all parts with newlines for better separation
        return "\n".join(text_parts)
    
    def _extract_additional_keywords(self, doc: Dict[str, Any]) -> List[str]:
        """
        Extract additional keywords from document metadata.
        
        Args:
            doc: Document dictionary.
            
        Returns:
            List of additional keywords.
        """
        # Keep your existing keyword extraction logic
        keywords = []
        
        # Add course name if available
        course_id = doc.get('course_id')
        if course_id and course_id in self.course_map:
            course_name = self.course_map[course_id].get('name', '')
            if course_name:
                keywords.append(f"Course: {course_name}")
        
        # Add module name if available
        module_id = doc.get('module_id')
        if module_id and course_id in self.course_map:
            for module in self.course_map[course_id].get('modules', []):
                if module.get('id') == module_id:
                    keywords.append(f"Module: {module.get('name', '')}")
                    break
        
        return keywords
    
    def process_data(self, force_reload: bool = False) -> bool:
        """
        Process data from JSON file and load into ChromaDB.
        
        Args:
            force_reload: Whether to force reload data even if cache exists.
            
        Returns:
            True if data was processed, False if using cached data.
        """
        # Check if we can use cached data
        if not force_reload and self._load_from_cache():
            return False
        
        # Load documents from JSON file
        try:
            with open(self.json_file_path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error loading JSON file: {e}")
            return False
        
        # Process documents
        self.documents = []
        self.document_map = {}
        
        # Extract user metadata
        user_metadata = data.get('user_metadata', {})
        logger.info(f"Processing data for user ID: {user_metadata.get('user_id')}")
        
        # Extract courses and build course map
        courses = data.get('courses', {})
        for course_id, course_info in courses.items():
            self.course_map[course_id] = course_info
        
        # Prepare data for ChromaDB
        ids = []
        texts = []
        metadatas = []
        
        # Process items (documents)
        items = data.get('items', [])
        
        for item in items:
            item_id = item.get('id')
            if not item_id:
                continue
            
            # Standardize document type if needed
            if 'type' in item:
                item_type = item['type'].lower()
                
                # Map to standard types if needed
                if item_type in ['homework', 'lab', 'quiz', 'exam', 'project']:
                    item['type'] = 'assignment'
                elif item_type in ['document', 'attachment', 'resource', 'material']:
                    item['type'] = 'file'
                elif item_type in ['notification', 'update', 'news']:
                    item['type'] = 'announcement'
                elif item_type in ['meeting', 'schedule', 'calendar']:
                    item['type'] = 'event'
                
            # Store document in memory
            self.documents.append(item)
            self.document_map[str(item_id)] = item
            
            # Prepare for ChromaDB
            ids.append(str(item_id))
            texts.append(self._preprocess_text_for_embedding(item))
            
            # Extract metadata for filtering
            metadata = {
                'id': str(item_id),
                'type': item.get('type', ''),
                'course_id': str(item.get('course_id', '')),
                'content_id': str(item.get('content_id', '')) if item.get('content_id') else None
            }
            metadatas.append(metadata)
        
        # Build document relations
        self._build_document_relations(self.documents)
        
        # Add documents to ChromaDB
        if ids:
            try:
                self.collection.add(
                    ids=ids,
                    documents=texts,
                    metadatas=metadatas
                )
                logger.info(f"Added {len(ids)} documents to ChromaDB")
            except Exception as e:
                logger.error(f"Error adding documents to ChromaDB: {e}")
                return False
        
        # Save to cache
        self._save_to_cache()
        
        return True
    
    def _load_document_metadata(self):
        """
        Load document metadata from JSON file without reprocessing embeddings.
        """
        try:
            # Load JSON data
            with open(self.json_file_path, 'r') as f:
                data = json.load(f)
            
            # Extract user metadata
            user_metadata = data.get('user_metadata', {})
            logger.info(f"Loading metadata for user ID: {user_metadata.get('user_id')}")
            
            # Extract courses and build course map
            courses = data.get('courses', {})
            for course_id, course_info in courses.items():
                self.course_map[course_id] = course_info
            
            # Process items (documents)
            items = data.get('items', [])
            
            for item in items:
                item_id = item.get('id')
                if not item_id:
                    continue
                
                # Store document in memory for reference
                self.documents.append(item)
                self.document_map[str(item_id)] = item
            
            # Build document relations
            self._build_document_relations(self.documents)
            
            logger.info(f"Successfully loaded metadata for {len(items)} items")
            
        except Exception as e:
            logger.error(f"Error loading document metadata: {e}")
    
    def _build_document_relations(self, documents: List[Dict[str, Any]]) -> None:
        """
        Build relations between documents.
        
        Args:
            documents: List of document dictionaries.
        """
        # Build relations based on course_id and content_id
        for doc in documents:
            doc_id = doc.get('id')
            if not doc_id:
                continue
                
            # Add related documents based on content_id and course_id
            doc['related_docs'] = []
            content_id = doc.get('content_id')
            course_id = doc.get('course_id')
            
            if content_id and course_id:
                for other_doc in documents:
                    if (other_doc.get('content_id') == content_id and 
                        other_doc.get('course_id') == course_id and 
                        other_doc.get('id') != doc_id):
                        doc['related_docs'].append(other_doc.get('id'))
            
            # Also relate items of the same type within the same course
            doc_type = doc.get('type')
            if doc_type and course_id:
                for other_doc in documents:
                    if (other_doc.get('type') == doc_type and 
                        other_doc.get('course_id') == course_id and 
                        other_doc.get('id') != doc_id and
                        other_doc.get('id') not in doc['related_docs']):
                        # Add with lower priority (we'll add these at the end of the list)
                        doc['related_docs'].append(other_doc.get('id'))
    
    def _enhance_query(self, query: str) -> str:
        """
        Enhance the query with additional context based on query content.
        
        Args:
            query: Original query string.
            
        Returns:
            Enhanced query string.
        """
        query_lower = query.lower()
        enhanced_terms = []
        
        # Add document type-specific terms based on query content
        if any(term in query_lower for term in ["due", "submit", "homework", "lab", "project"]):
            enhanced_terms.extend(["assignment", "due date", "submission", "deadline"])
        
        if any(term in query_lower for term in ["file", "document", "download", "upload", "pdf", "docx"]):
            enhanced_terms.extend(["file", "document", "attachment", "download"])
        
        if any(term in query_lower for term in ["announce", "notification", "update", "news"]):
            enhanced_terms.extend(["announcement", "notification", "update", "important"])
        
        if any(term in query_lower for term in ["event", "meeting", "schedule", "calendar", "when", "time", "date"]):
            enhanced_terms.extend(["event", "calendar", "schedule", "time", "date", "location"])
        
        # Add the enhanced terms to the query if any were generated
        if enhanced_terms:
            enhanced_query = f"{query} {' '.join(enhanced_terms)}"
        else:
            enhanced_query = query
        
        return enhanced_query
    
    def search(self, query: str, course_ids: Optional[List[str]] = None, top_k: int = 5,
               include_related: bool = True, minimum_score: float = 0.3, 
               doc_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search for documents similar to the query.
        
        Args:
            query: Query string (already enhanced and formatted).
            course_ids: Optional list of course IDs to filter by.
            top_k: Number of top results to return.
            include_related: Whether to include related documents.
            minimum_score: Minimum similarity score to include in results.
            doc_types: Optional list of document types to filter by (e.g., ["assignment", "file", "announcement", "event"]).
            
        Returns:
            List of search results.
        """
        # Prepare where clause for filtering by course_id and/or document type
        where_clause = {}
        
        if course_ids:
            where_clause["course_id"] = {"$in": course_ids}
        
        if doc_types:
            where_clause["type"] = {"$in": doc_types}
        
        # If no filters are applied, set where_clause to None
        if not where_clause:
            where_clause = None
        
        # Query ChromaDB
        results = self.collection.query(
            query_texts=[query],  # Use the query as-is, no enhancement
            n_results=top_k * 2,  # Get more results than needed to account for filtering
            where=where_clause
        )
        
        # Process results
        search_results = []
        doc_ids = results.get('ids', [[]])[0]
        distances = results.get('distances', [[]])[0]
        
        for i, doc_id in enumerate(doc_ids):
            doc = self.document_map.get(doc_id)
            if not doc:
                continue
            
            # Calculate similarity score (convert distance to similarity)
            similarity = 1.0 - (distances[i] / 2.0)  # Convert cosine distance to similarity
            
            # Skip results below minimum score
            if similarity < minimum_score:
                continue
            
            # Add to results
            search_results.append({
                'document': doc,
                'similarity': similarity
            })
        
        # Include related documents if requested
        if include_related and search_results:
            related_docs = self._get_related_documents([r['document']['id'] for r in search_results])
            for doc in related_docs:
                # Add related document with a slightly lower similarity score
                search_results.append({
                    'document': doc,
                    'similarity': minimum_score,  # Use minimum score for related docs
                    'is_related': True
                })
        
        # Sort by similarity score
        search_results.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Limit to top_k results
        return search_results[:top_k]
    
    def get_available_courses(self) -> List[Dict[str, Any]]:
        """
        Get list of available courses.
        
        Returns:
            List of course dictionaries.
        """
        courses = []
        for course_id, course in self.course_map.items():
            courses.append({
                'id': course_id,
                'name': course.get('name', ''),
                'code': course.get('code', ''),
                'description': course.get('description', ''),
                'workflow_state': course.get('workflow_state', ''),
                'default_view': course.get('default_view', ''),
                'course_format': course.get('course_format', '')
            })
        return courses
    
    def clear_cache(self) -> None:
        """
        Clear the ChromaDB collection.
        """
        try:
            self.client.delete_collection(self.collection_name)
            logger.info(f"Deleted collection: {self.collection_name}")
            
            # Recreate the collection
            self.collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Created new collection: {self.collection_name}")
            
            # Reset in-memory data
            self.documents = []
            self.document_map = {}
            self.course_map = {}
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

    def _detect_document_type(self, query: str) -> Optional[List[str]]:
        """
        Detect likely document types based on query content.
        
        Args:
            query: Query string.
            
        Returns:
            List of likely document types or None if no specific type is detected.
        """
        query_lower = query.lower()
        doc_types = []
        
        # Assignment-related terms
        if any(term in query_lower for term in ["assignment", "homework", "due", "submit", "deadline", "lab", "project"]):
            doc_types.append("assignment")
        
        # File-related terms
        if any(term in query_lower for term in ["file", "document", "download", "upload", "pdf", "docx", "presentation"]):
            doc_types.append("file")
        
        # Announcement-related terms
        if any(term in query_lower for term in ["announcement", "announce", "notification", "update", "news", "important"]):
            doc_types.append("announcement")
        
        # Quiz-related terms
        if any(term in query_lower for term in ["quiz", "test", "exam", "assessment", "question"]):
            doc_types.append("quiz")
        
        # Page-related terms
        if any(term in query_lower for term in ["page", "content", "information", "read"]):
            doc_types.append("page")
        
        return doc_types if doc_types else None


# Example usage
if __name__ == "__main__":
    # Initialize the vector database with the path to your JSON data file
    dic = {}
    x = dic.get("id")
    print(x)