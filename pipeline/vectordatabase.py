#!/usr/bin/env python3
"""
Vector Database Module for Canvas Data
--------------------------------------
This module processes Canvas course data from a structured JSON file and creates vector embeddings
using the Hugging Face Inference API with the all-MiniLM-L6-v2 model, leveraging ChromaDB for storage.

Key features:
1. **Data Loading**: Loads Canvas course data from a structured JSON file (user_data2.json) containing user metadata, courses, files, announcements, assignments, quizzes, and calendar events.
2. **ChromaDB Integration**: Utilizes ChromaDB for efficient storage and retrieval of embeddings, ensuring persistence and avoiding recomputation.
3. **Similarity Search**: Provides functionality to search for relevant course materials based on a query, with support for filtering by course ID and document type.
4. **Document Relations**: Builds relationships between documents based on course and module IDs, allowing for contextual search results that include related documents.
5. **Text Preprocessing**: Normalizes and preprocesses document text to enhance embedding quality and search relevance, handling various document types (files, assignments, announcements, quizzes, events).
6. **Caching Mechanism**: Implements a caching mechanism to avoid reprocessing data if it has already been loaded, improving efficiency.
7. **Logging**: Configures logging to provide insights into the processing steps and any errors encountered during execution.

The module is designed to be resource-efficient (no local GPU/CPU needed for inference) while still providing good semantic search capabilities.

Usage:
1. Initialize the VectorDatabase with the path to your JSON data file.
2. Call process_data() to create embeddings for all documents.
3. Use search() to find relevant documents based on a query.

Note: Ensure that the JSON data file is structured correctly, containing user metadata, courses, files, announcements, assignments, quizzes, and calendar events.




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
        
        # Initialize ChromaDB client to store files in disk in cache_dir
        self.client = chromadb.PersistentClient(path=cache_dir)
        
        # Initialize embedding function (using the same model as before: all-MiniLM-L6-v2)
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        self.documents = [] # stores documents
        self.document_map = {} # Allows O(1) lookup of documents by ID
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
                # hnsw:space defined the distance function of the embedding space
                # cosine is currently selected
                metadata={"hnsw:space": "cosine"}
            )
            '''
            Other hyperparameters to be changed in testing:
            hnsw:space: euclidean, manhattan, cosine, dot
            hnsw:ef_construction: determines the size of the candidate list (default: 100)
            hnsw:search_ef: determines the size of the dynamic list (default: 100)
            hnsw:m: determines the number of neighbors (edges) each node in the graph can have (default: 16)
            '''
    
    def _preprocess_text_for_embedding(self, doc: Dict[str, Any]) -> str:
        """
        Preprocess document text for embedding.
        
        Args:
            doc: Singular Item dictionary from user_data
            
        Returns:
            Preprocessed text string that is sent to chromadb for embedding
        """
        # Fields in each type
        doc_type = doc.get('type', '').capitalize()
        doc_id = doc.get('id', '')
        course_id = doc.get('course_id', '')
        
        # Build a rich text representation with all relevant fields
        text_parts = []
        
        # Basic identification
        if doc_id:
            text_parts.append(f"ID: {doc_id}")
        if doc_type:
            text_parts.append(f"Type: {doc_type}")
        if course_id:
            text_parts.append(f"Course ID: {course_id}")
        
        # Handle different document types
        match doc_type:
            case 'File':
                # For files, prioritize the display_name by placing it at the beginning
                display_name = doc.get('display_name', '')
                if display_name:
                    # Normalize the display name to improve matching
                    normalized_name = self._normalize_text(display_name)
                    # Add the name at the beginning for emphasis
                    text_parts.insert(0, f"Filename: {normalized_name}")
                    # Also add it as a title for better matching
                    text_parts.insert(0, f"Title: {normalized_name}")
                
                for field in ['folder_id', 'display_name', 'filename', 'url', 'size', 
                             'updated_at', 'locked', 'lock_explanation']:
                    if field in doc and doc[field] is not None: # error prevention
                        # Normalize any text fields to handle special characters
                        if isinstance(doc[field], str):
                            value = self._normalize_text(doc[field])
                        else:
                            value = doc[field]
                        text_parts.append(f"{field.replace('_', ' ').title()}: {value}")
                
            case 'Assignment':
                # For assignments, prioritize the name by placing it at the beginning
                name = doc.get('name', '')
                if name:
                    # Normalize the name to improve matching
                    normalized_name = self._normalize_text(name)
                    # Add the name at the beginning for emphasis
                    text_parts.insert(0, f"Assignment: {normalized_name}")
                    text_parts.insert(0, f"Title: {normalized_name}")
                
                for field in ['name', 'description', 'created_at', 'updated_at', 'due_at', 
                             'submission_types', 'can_submit', 'graded_submissions_exist']:
                    if field in doc and doc[field] is not None: # error prevention
                        if field == 'submission_types' and isinstance(doc[field], list):
                            # e.g. [online_text_entry, online_upload] -> Submission Types: Online Text Entry, Online Upload
                            text_parts.append(f"Submission Types: {', '.join(doc[field])}")
                        else:
                            # Normalize any text fields
                            if isinstance(doc[field], str):
                                value = self._normalize_text(doc[field])
                            else:
                                value = doc[field]
                            # e.g. HW2 (name) -> Name: HW2
                            text_parts.append(f"{field.replace('_', ' ').title()}: {value}")
                
                # Handle content field which might contain extracted links
                content = doc.get('content', [])
                if content and isinstance(content, list):
                    text_parts.append("Content Link(s): \n")
                    for item in content:
                        if isinstance(item, str):
                            text_parts.append(f'\t{item}\n')
                
            case 'Announcement':
                # For announcements, prioritize the title by placing it at the beginning
                title = doc.get('title', '')
                if title:
                    # Normalize the title to improve matching
                    normalized_title = self._normalize_text(title)
                    # Add the title at the beginning for emphasis
                    text_parts.insert(0, f"Announcement: {normalized_title}")
                    text_parts.insert(0, f"Title: {normalized_title}")
                
                for field in ['title', 'message', 'posted_at', 'course_id']:
                    if field in doc and doc[field] is not None: # error prevention
                        # Normalize any text fields
                        if isinstance(doc[field], str):
                            value = self._normalize_text(doc[field])
                        else:
                            value = doc[field]
                        text_parts.append(f"{field.replace('_', ' ').title()}: {value}")
                
            case 'Quiz':
                # For quizzes, prioritize the title by placing it at the beginning
                title = doc.get('title', '')
                if title:
                    # Normalize the title to improve matching
                    normalized_title = self._normalize_text(title)
                    # Add the title at the beginning for emphasis
                    text_parts.insert(0, f"Quiz: {normalized_title}")
                    text_parts.insert(0, f"Title: {normalized_title}")
                
                for field in ['title', 'preview_url', 'description', 'quiz_type', 'time_limit', 
                             'allowed_attempts', 'points_possible', 'due_at', 
                             'locked_for_user', 'lock_explanation']:
                    if field == 'time_limit' and isinstance(doc[field], int):
                        text_parts.append(f"Time Limit: {doc[field]} minutes")
                    elif field in doc and doc[field] is not None:
                        # Normalize any text fields
                        if isinstance(doc[field], str):
                            value = self._normalize_text(doc[field])
                        else:
                            value = doc[field]
                        text_parts.append(f"{field.replace('_', ' ').title()}: {value}")
                
            case 'Event':
                # For events, prioritize the title by placing it at the beginning
                title = doc.get('title', '')
                if title:
                    # Normalize the title to improve matching
                    normalized_title = self._normalize_text(title)
                    # Add the title at the beginning for emphasis
                    text_parts.insert(0, f"Event: {normalized_title}")
                    text_parts.insert(0, f"Title: {normalized_title}")
                
                for field in ['title', 'start_at', 'end_at', 'description', 'location_name', 
                             'location_address', 'context_code', 'context_name', 
                             'all_context_codes', 'url']:
                    if field in doc and doc[field] is not None:
                        # Normalize any text fields
                        if isinstance(doc[field], str):
                            value = self._normalize_text(doc[field])
                        else:
                            value = doc[field]
                        text_parts.append(f"{field.replace('_', ' ').title()}: {value}")
        
        # Add module information
        module_id = doc.get('module_id')
        if module_id:
            text_parts.append(f"Module ID: {module_id}")
        
        module_name = doc.get('module_name')
        if module_name:
            # Normalize module name
            if isinstance(module_name, str):
                module_name = self._normalize_text(module_name)
            text_parts.append(f"Module Name: {module_name}")
        
        # Join all parts with newlines for better separation
        # After processing, the text_parts list for a singule assingment item will have the following format:
        # [
        #     "ID: 123",
        #     "Type: Assignment",
        #     "Course ID: 456",
        #     "Name: HW2",
        #     "Description: This is a description of the assignment",
        #     "Created At: 2021-01-01",
        #     "Updated At: 2021-01-02",
        #     "Due At: 2021-01-03",
        #     "Submission Types: Online Text Entry, Online Upload",
        #     "Graded Submissions Exist: True",
        #     "Module ID: 123",
        #     "Module Name: Module 1",
        #     "Content Link(s):
        #       https://www.example.com
        #       https://www.example.com
        #       https://www.example.com
        #       https://www.example.com
        #       https://www.example.com
        #       https://www.example.com
        # ]
        return "\n".join(text_parts)
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text by handling special characters and standardizing formats.
        
        Args:
            text: Text to normalize.
            
        Returns:
            Normalized text.
        """
        if not isinstance(text, str):
            return text
            
        # Replace various types of quotes and apostrophes with standard ones
        normalized = text.replace('\u2019', "'").replace('\u2018', "'")
        normalized = normalized.replace('\u201c', '"').replace('\u201d', '"')
        
        # Replace other common special characters
        normalized = normalized.replace('\u2013', '-').replace('\u2014', '-')
        
        return normalized
        
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
        
        # Extract user metadata
        user_metadata = data.get('user_metadata', {})
        logger.info(f"Processing data for user ID: {user_metadata.get('id')}")
        
        # Extract courses and build course map
        courses = data.get('courses', [])
        for course in courses:
            course_id = str(course.get('id'))
            if course_id:
                self.course_map[course_id] = course
        
        ids = [] # list of document IDs
        texts = [] # list of preprocessed text for each document
        metadatas = [] # list of metadata for each document
        
        # Process all document types
        document_types = {
            'files': 'file',
            'announcements': 'announcement',
            'assignments': 'assignment',
            'quizzes': 'quiz',
            'calendar_events': 'event'
        }

        # collection_key is the key of the dictionary in the JSON file that contains list documents
        # doc_type is the type of document
        
        for collection_key, doc_type in document_types.items():
            items = data.get(collection_key, [])
            
            for item in items:
                item_id = item.get('id')
                if not item_id:
                    continue
                
                # Make sure type is set
                if 'type' not in item:
                    item['type'] = doc_type
                    
                # Store document in memory
                self.documents.append(item)
                self.document_map[str(item_id)] = item
                
                # Prepare for ChromaDB
                ids.append(str(item_id))
                texts.append(self._preprocess_text_for_embedding(item))
                
                # Create base metadata
                metadata = {
                    'id': str(item_id),
                    'type': doc_type,
                    'course_id': str(item.get('course_id', ''))
                }

                # Add module_id to metadata if it exists
                if item.get('module_id'):
                    metadata['module_id'] = str(item['module_id'])
                
                # Add type-specific metadata fields
                match doc_type:
                    case 'file':
                        metadata['folder_id'] = str(item.get('folder_id', ''))
                    
                    case 'announcement' | 'assignment' | 'quiz':
                        if item.get('module_id'):
                            metadata['module_id'] = str(item.get('module_id', ''))
                    
                    case 'event':
                        # Parse course_id from context_code if available
                        if 'context_code' in item and item['context_code'].startswith('course_'):
                            course_id = item['context_code'].replace('course_', '')
                            item['course_id'] = course_id
                            metadata['course_id'] = str(course_id)
                
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
        # doc is a dictionary of a single document
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
        # Normalize the query to handle special characters
        normalized_query = self._normalize_text(query)
        
        # Holds filtering conditions for the search
        where_clause = {}
        
        # Filter by course_id if provided
        if course_ids:
            where_clause["course_id"] = {"$in": course_ids} # $in is used to filter by a list of values
        
        # Filter by document type if provided
        if doc_types:
            where_clause["type"] = {"$in": doc_types}
        
        # If no filters are applied, set where_clause to None
        if not where_clause:
            where_clause = None
        
        # Query ChromaDB
        results = self.collection.query(
            query_texts=[normalized_query],  # Use the normalized query
            n_results=top_k * 2,  # Get more results than needed to account for filtering
            where=where_clause, # Apply filters if any
            include=["distances", "documents"]
        )
        
        # Process results
        search_results = []
        doc_ids = results.get('ids', [[]])[0] # access the first (and only) list in the results
        distances = results.get('distances', [[]])[0] # access the first (and only) list in the results
        
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
            related_docs = self._get_related_documents([r['document'].get('id') for r in search_results])
            for doc in related_docs:
                # Add related document with a slightly lower similarity score
                if not any(r['document'].get('id') == doc.get('id') for r in search_results):
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


# Example usage
if __name__ == "__main__":
    # Define the path to the user data JSON file
    user_id = "1234"  # Replace with actual user ID if needed
    json_file_path = f"user_data/CanvasAI/UserData/psu.instructure.com/{user_id}/user_data2.json"
    
    # Check if the file exists, if not, try to find it in the current directory
    if not os.path.exists(json_file_path):
        logger.warning(f"File not found at {json_file_path}, checking current directory")
        if os.path.exists("user_data2.json"):
            json_file_path = "user_data2.json"
        else:
            # Look for any JSON files in the current directory
            json_files = [f for f in os.listdir('.') if f.endswith('.json')]
            if json_files:
                json_file_path = json_files[0]
                logger.info(f"Using JSON file found in current directory: {json_file_path}")
            else:
                logger.error("No JSON files found. Please provide a valid path to the user data JSON file.")
                exit(1)
    
    # Initialize the vector database with the path to your JSON data file
    vector_db = VectorDatabase(json_file_path)
    
    # Clear the cache to ensure we're starting fresh
    vector_db.clear_cache()
    
    # Process the data
    processed = vector_db.process_data(force_reload=True)  # Force reload to apply the new preprocessing
    if processed:
        logger.info("Successfully processed data")
    else:
        logger.info("Using cached data")
    
    # Search for documents
    results = vector_db.search("Bit Byte", top_k=10)
    
    # Print results
    for result in results:
        print(f"Document: {result['document'].get('name', result['document'].get('title', result['document'].get('display_name', 'Unnamed')))} ({result['document'].get('type')})")
        print(f"Similarity: {result['similarity']:.4f}")
        print("---")