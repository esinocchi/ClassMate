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

# Constants
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
                # HNSW algorithm for approximate nearest neighbor in high dimensional spaces
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
        # Get common fields
        doc_type = doc.get('type', '').lower()
        doc_id = doc.get('id', '')
        course_id = doc.get('course_id', '')
        
        # Build a rich text representation with all relevant fields
        text_parts = []
        
        # Basic identification
        if doc_id:
            text_parts.append(f"ID: {doc_id}")
        if doc_type:
            text_parts.append(f"Type: {doc_type.capitalize()}")
        if course_id:
            text_parts.append(f"Course ID: {course_id}")
        
        # Handle different document types
        match doc_type:
            case 'file':
                # Add file-specific fields
                for field in ['folder_id', 'display_name', 'filename', 'url', 'size', 
                             'updated_at', 'locked', 'lock_explanation']:
                    if field in doc and doc[field] is not None:
                        text_parts.append(f"{field.replace('_', ' ').title()}: {doc[field]}")
                
            case 'assignment':
                # Add assignment-specific fields
                for field in ['name', 'description', 'created_at', 'updated_at', 'due_at', 
                             'submission_types', 'can_submit', 'graded_submissions_exist']:
                    if field in doc and doc[field] is not None:
                        if field == 'submission_types' and isinstance(doc[field], list):
                            text_parts.append(f"Submission Types: {', '.join(doc[field])}")
                        else:
                            text_parts.append(f"{field.replace('_', ' ').title()}: {doc[field]}")
                
                # Handle content field which might contain extracted links
                content = doc.get('content', [])
                if content and isinstance(content, list):
                    for item in content:
                        if isinstance(item, str):
                            text_parts.append(f"Content Link: {item}")
                
            case 'announcement':
                # Add announcement-specific fields
                for field in ['title', 'message', 'posted_at', 'course_id']:
                    if field in doc and doc[field] is not None:
                        text_parts.append(f"{field.replace('_', ' ').title()}: {doc[field]}")
                
            case 'quiz':
                # Add quiz-specific fields
                for field in ['title', 'preview_url', 'description', 'quiz_type', 'time_limit', 
                             'allowed_attempts', 'points_possible', 'due_at', 
                             'locked_for_user', 'lock_explanation']:
                    if field in doc and doc[field] is not None:
                        text_parts.append(f"{field.replace('_', ' ').title()}: {doc[field]}")
                
            case 'event':
                # Add event-specific fields
                for field in ['title', 'start_at', 'end_at', 'description', 'location_name', 
                             'location_address', 'context_code', 'context_name', 
                             'all_context_codes', 'url']:
                    if field in doc and doc[field] is not None:
                        text_parts.append(f"{field.replace('_', ' ').title()}: {doc[field]}")
        
        # Add module information
        module_id = doc.get('module_id')
        if module_id:
            text_parts.append(f"Module ID: {module_id}")
        
        module_name = doc.get('module_name')
        if module_name:
            text_parts.append(f"Module Name: {module_name}")
        
        # Join all parts with newlines for better separation
        return "\n".join(text_parts)
    
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
        logger.info(f"Processing data for user ID: {user_metadata.get('id')}")
        
        # Extract courses and build course map
        courses = data.get('courses', [])
        for course in courses:
            course_id = str(course.get('id'))
            if course_id:
                self.course_map[course_id] = course
        
        # Prepare data for ChromaDB
        ids = []
        texts = []
        metadatas = []
        
        # Process files
        files = data.get('files', [])
        for file in files:
            file_id = file.get('id')
            if not file_id:
                continue
            
            # Make sure type is set
            if 'type' not in file:
                file['type'] = 'file'
                
            # Store document in memory
            self.documents.append(file)
            self.document_map[str(file_id)] = file
            
            # Prepare for ChromaDB
            ids.append(str(file_id))
            texts.append(self._preprocess_text_for_embedding(file))
            
            # Extract metadata for filtering
            metadata = {
                'id': str(file_id),
                'type': 'file',
                'course_id': str(file.get('course_id', '')),
                'folder_id': str(file.get('folder_id', ''))
            }
            metadatas.append(metadata)
        
        # Process announcements
        announcements = data.get('announcements', [])
        for announcement in announcements:
            announcement_id = announcement.get('id')
            if not announcement_id:
                continue
            
            # Make sure type is set
            if 'type' not in announcement:
                announcement['type'] = 'announcement'
                
            # Store document in memory
            self.documents.append(announcement)
            self.document_map[str(announcement_id)] = announcement
            
            # Prepare for ChromaDB
            ids.append(str(announcement_id))
            texts.append(self._preprocess_text_for_embedding(announcement))
            
            # Extract metadata for filtering
            metadata = {
                'id': str(announcement_id),
                'type': 'announcement',
                'course_id': str(announcement.get('course_id', ''))
            }
            metadatas.append(metadata)
        
        # Process assignments
        assignments = data.get('assignments', [])
        for assignment in assignments:
            assignment_id = assignment.get('id')
            if not assignment_id:
                continue
            
            # Make sure type is set
            if 'type' not in assignment:
                assignment['type'] = 'assignment'
                
            # Store document in memory
            self.documents.append(assignment)
            self.document_map[str(assignment_id)] = assignment
            
            # Prepare for ChromaDB
            ids.append(str(assignment_id))
            texts.append(self._preprocess_text_for_embedding(assignment))
            
            # Extract metadata for filtering
            metadata = {
                'id': str(assignment_id),
                'type': 'assignment',
                'course_id': str(assignment.get('course_id', '')),
                'module_id': str(assignment.get('module_id', ''))
            }
            metadatas.append(metadata)
        
        # Process quizzes
        quizzes = data.get('quizzes', [])
        for quiz in quizzes:
            quiz_id = quiz.get('id')
            if not quiz_id:
                continue
            
            # Make sure type is set
            if 'type' not in quiz:
                quiz['type'] = 'quiz'
                
            # Store document in memory
            self.documents.append(quiz)
            self.document_map[str(quiz_id)] = quiz
            
            # Prepare for ChromaDB
            ids.append(str(quiz_id))
            texts.append(self._preprocess_text_for_embedding(quiz))
            
            # Extract metadata for filtering
            metadata = {
                'id': str(quiz_id),
                'type': 'quiz',
                'course_id': str(quiz.get('course_id', '')),
                'module_id': str(quiz.get('module_id', ''))
            }
            metadatas.append(metadata)
        
        # Process calendar events
        events = data.get('calendar_events', [])
        for event in events:
            event_id = event.get('id')
            if not event_id:
                continue
            
            # Make sure type is set
            if 'type' not in event:
                event['type'] = 'event'
                
            # Parse course_id from context_code if available
            if 'context_code' in event and event['context_code'].startswith('course_'):
                event['course_id'] = event['context_code'].replace('course_', '')
                
            # Store document in memory
            self.documents.append(event)
            self.document_map[str(event_id)] = event
            
            # Prepare for ChromaDB
            ids.append(str(event_id))
            texts.append(self._preprocess_text_for_embedding(event))
            
            # Extract metadata for filtering
            metadata = {
                'id': str(event_id),
                'type': 'event',
                'course_id': str(event.get('course_id', ''))
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
            logger.info(f"Loading metadata for user ID: {user_metadata.get('id')}")
            
            # Extract courses and build course map
            courses = data.get('courses', [])
            for course in courses:
                course_id = str(course.get('id'))
                if course_id:
                    self.course_map[course_id] = course
            
            # Process all document types
            document_types = {
                'files': 'file',
                'announcements': 'announcement',
                'assignments': 'assignment',
                'quizzes': 'quiz',
                'calendar_events': 'event'
            }
            
            for key, doc_type in document_types.items():
                items = data.get(key, [])
                for item in items:
                    item_id = item.get('id')
                    if not item_id:
                        continue
                    
                    # Make sure type is set
                    if 'type' not in item:
                        item['type'] = doc_type
                    
                    # Store document in memory for reference
                    self.documents.append(item)
                    self.document_map[str(item_id)] = item
            
            # Build document relations
            self._build_document_relations(self.documents)
            
            logger.info(f"Successfully loaded metadata for {len(self.documents)} items")
            
        except Exception as e:
            logger.error(f"Error loading document metadata: {e}")
    
    def _build_document_relations(self, documents: List[Dict[str, Any]]) -> None:
        """
        Build relations between documents.
        
        Args:
            documents: List of document dictionaries.
        """
        # Build relations based on course_id and module_id
        for doc in documents:
            doc_id = doc.get('id')
            if not doc_id:
                continue
                
            # Add related documents based on module_id and course_id
            doc['related_docs'] = []
            module_id = doc.get('module_id')
            course_id = doc.get('course_id')
            
            if module_id and course_id:
                for other_doc in documents:
                    if (other_doc.get('module_id') == module_id and 
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
    
    def _save_to_cache(self):
        """
        Save document metadata and course map to cache.
        """
        # This is a placeholder for future implementation
        # If you want to implement caching beyond ChromaDB's persistence,
        # you could save the document map and course map to a file
        pass
    
    def _load_from_cache(self):
        """
        Load document metadata and course map from cache.
        
        Returns:
            True if data was loaded from cache, False otherwise.
        """
        # This is a placeholder for future implementation
        # If you've implemented caching beyond ChromaDB's persistence,
        # you could load the document map and course map from a file
        
        # For now, we'll just check if the ChromaDB collection has any items
        try:
            count = self.collection.count()
            if count > 0:
                # Load document metadata
                self._load_document_metadata()
                logger.info(f"Loaded {count} documents from ChromaDB cache")
                return True
        except Exception as e:
            logger.error(f"Error checking ChromaDB cache: {e}")
        
        return False
    
    def _get_related_documents(self, doc_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Get related documents for a list of document IDs.
        
        Args:
            doc_ids: List of document IDs.
            
        Returns:
            List of related document dictionaries.
        """
        related_docs = []
        seen_ids = set(doc_ids)
        
        for doc_id in doc_ids:
            doc = self.document_map.get(doc_id)
            if not doc:
                continue
            
            # Get related document IDs
            doc_related_ids = doc.get('related_docs', [])
            
            for related_id in doc_related_ids:
                # Avoid duplicates
                if related_id in seen_ids:
                    continue
                
                related_doc = self.document_map.get(str(related_id))
                if related_doc:
                    related_docs.append(related_doc)
                    seen_ids.add(related_id)
        
        return related_docs
    
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
                'code': course.get('course_code', ''),
                'description': course.get('public_description', ''),
                'default_view': course.get('default_view', ''),
                'syllabus_body': course.get('syllabus_body', '')
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
        
        # Event-related terms
        if any(term in query_lower for term in ["event", "meeting", "schedule", "calendar", "when", "time", "date"]):
            doc_types.append("event")
        
        return doc_types if doc_types else None


# Example usage
if __name__ == "__main__":
    # Initialize the vector database with the path to your JSON data file
    vector_db = VectorDatabase("user_data.json")
    vector_db.process_data()
    
    # Search for documents
    results = vector_db.search("When is the next assignment due?", top_k=3)
    
    # Print results
    for result in results:
        print(f"Document: {result['document'].get('name', 'Unnamed')} ({result['document'].get('type')})")
        print(f"Similarity: {result['similarity']:.4f}")
        print("---")