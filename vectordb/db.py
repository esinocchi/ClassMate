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
import sys
import logging
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv
import chromadb
from chromadb.utils import embedding_functions
import requests
from datetime import datetime, timedelta, timezone

# Add the project root directory to Python path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from backend.data_retrieval.get_all_user_data import extract_text_and_images


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
    def __init__(self, json_file_path: str, cache_dir: str = DEFAULT_CACHE_DIR, collection_name: str = None):
        """
        Initialize the vector database with ChromaDB.
        
        Args:
            json_file_path: Path to the JSON file containing the documents.
            cache_dir: Directory to store ChromaDB data.
            collection_name: Name of the ChromaDB collection. If None, will use user_id from the json file.
        """
        self.json_file_path = json_file_path
        self.cache_dir = cache_dir
        
        # Load JSON file to extract user_id if collection_name is not provided
        if collection_name is None:
            try:
                with open(json_file_path, 'r') as f:
                    data = json.load(f)
                user_id = data.get('user_metadata', {}).get('id', 'default')
                self.collection_name = f"canvas_embeddings_{user_id}"
            except Exception as e:
                logger.error(f"Error loading JSON file to get user_id: {e}")
                self.collection_name = DEFAULT_COLLECTION_NAME
        else:
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
                name=self.collection_name,
                embedding_function=self.embedding_function
            )
            logger.info(f"Using existing collection: {self.collection_name}")
        
        except Exception: # If no existing collection, collection is created
            logger.info(f"Creating new collection: {self.collection_name}")
            self.collection = self.client.create_collection(
                name=self.collection_name,
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
        if doc.get('type'):
            doc_type = doc.get('type', '').upper()
        else:
            doc_type = 'File'
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
        if doc_type == 'File':
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
            
        elif doc_type == 'Assignment':
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
            
        elif doc_type == 'Announcement':
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
            
        elif doc_type == 'Quiz':
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
            
        elif doc_type == 'Event':
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
                
                item['type'] = document_types[collection_key]
                    
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
                if doc_type == 'file':
                        metadata['folder_id'] = str(item.get('folder_id', ''))
                    
                elif doc_type in ['announcement', 'assignment', 'quiz']:
                    if item.get('module_id'):
                        metadata['module_id'] = str(item.get('module_id', ''))
                    
                elif doc_type == 'event':
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
    
    def extract_file_content(self, doc: Dict[str, Any]) -> str:
        """
        Extract content from a file URL when needed.
        
        Args:
            doc: Document dictionary containing file metadata
            
        Returns:
            Extracted text content as a string
        """
        # Skip if no URL
        url = doc.get('url')
        if not url:
            logger.warning(f"No URL found for document: {doc.get('display_name', '')}")
            return ""
        
        # Get file extension
        file_extension = doc.get('file_extension', '')
        if not file_extension:
            display_name = doc.get('display_name', '')
            if display_name and '.' in display_name:
                file_extension = display_name.split('.')[-1].lower()
        
        # Try to download the file
        try:
            logger.info(f"Downloading file: {doc.get('display_name', '')}")
            response = requests.get(url)
            if response.status_code != 200:
                logger.warning(f"Failed to download file {url}: {response.status_code}")
                return ""
            
            # Get the raw file content as bytes
            file_bytes = response.content
            
            # Use the imported extract_text_and_images function
            extracted_text = extract_text_and_images(file_bytes, file_extension)
            return extracted_text
                
        except Exception as e:
            logger.error(f"Error downloading or processing file {url}: {e}")
            return "" 
    
    def _filter_by_time(self, doc, search_parameters):
        """
        Filter a document based on time range from search parameters.
        
        Args:
            doc: Document dictionary to filter
            search_parameters: Dictionary containing search parameters
            
        Returns:
            True if document passes the filter, False if it should be skipped
        """
        if not search_parameters or "time_range" not in search_parameters:
            return True  # No time filter specified, so document passes
        
        time_range = search_parameters["time_range"]
        if not time_range:
            return True  # No time range specified, so document passes
        
        # Get the relevant date field based on document type
        date_field_str = None
        if doc.get('type') == 'assignment':
            date_field_str = doc.get('due_at')
        elif doc.get('type') == 'announcement':
            date_field_str = doc.get('posted_at')
        elif doc.get('type') == 'quiz':
            date_field_str = doc.get('due_at')
        elif doc.get('type') == 'event':
            date_field_str = doc.get('start_at')
        elif doc.get('type') == 'file':
            date_field_str = doc.get('updated_at')
        
        # Skip if no date field available
        if not date_field_str:
            return True
        
        # Convert the date string to datetime object if available
        try:
            # Convert ISO format to datetime (handling the 'Z' UTC indicator)
            date_field = datetime.fromisoformat(date_field_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError) as e:
            logger.warning(f"Error parsing date {date_field_str} for doc {doc.get('id')}: {e}")
            return False
        
        # Ensure date has UTC timezone information for proper comparison
        if date_field.tzinfo is None:
            date_field = date_field.replace(tzinfo=timezone.utc)
        
        # Current time as reference
        current_time = datetime.now(timezone.utc)
        
        # Apply filter based on time_range
        if time_range == "FUTURE":
            if date_field <= current_time:
                logger.info(f"Skipping doc {doc.get('id')} (name: {doc.get('name', '')}) because date {date_field} is not in the future")
                return False
        elif time_range == "RECENT_PAST":
            seven_days_ago = current_time - timedelta(days=7)
            if date_field > current_time or date_field < seven_days_ago:
                logger.info(f"Skipping doc {doc.get('id')} (name: {doc.get('name', '')}) because date {date_field} is not in the recent past")
                return False
        elif time_range == "EXTENDED_PAST":
            thirty_days_ago = current_time - timedelta(days=30)
            if date_field > current_time or date_field < thirty_days_ago:
                logger.info(f"Skipping doc {doc.get('id')} (name: {doc.get('name', '')}) because date {date_field} is not in the extended past")
                return False
        
        return True

    def _filter_by_specific_dates(self, doc, search_parameters):
        """
        Filter a document based on specific dates from search parameters.
        
        Args:
            doc: Document dictionary to filter
            search_parameters: Dictionary containing search parameters
            
        Returns:
            True if document passes the filter, False if it should be skipped
        """
        if not search_parameters or "specific_dates" not in search_parameters or not search_parameters["specific_dates"]:
            return True  # No specific dates filter specified, so document passes
        
        # Get the relevant date field based on document type
        date_field_str = None
        if doc.get('type') == 'assignment':
            date_field_str = doc.get('due_at')
        elif doc.get('type') == 'announcement':
            date_field_str = doc.get('posted_at') 
        elif doc.get('type') == 'quiz':
            date_field_str = doc.get('due_at')
        elif doc.get('type') == 'event':
            date_field_str = doc.get('start_at')
        elif doc.get('type') == 'file':
            date_field_str = doc.get('updated_at')
        
        # Skip if no date field available
        if not date_field_str:
            return True
        
        # Convert the date string to datetime object if available
        try:
            # Convert ISO format to datetime
            date_field = datetime.fromisoformat(date_field_str.replace('Z', '+00:00'))
        except (ValueError, AttributeError) as e:
            logger.warning(f"Error parsing date {date_field_str} for specific date check: {e}")
            return False
        
        # Parse specific dates
        specific_dates = []
        for date_str in search_parameters["specific_dates"]:
            try:
                # Convert specific dates to datetime objects (assuming YYYY-MM-DD format)
                specific_date = datetime.strptime(date_str, "%Y-%m-%d")
                specific_dates.append(specific_date)
            except ValueError:
                logger.warning(f"Invalid date format: {date_str}, expected YYYY-MM-DD")
        
        if not specific_dates:
            return True  # No valid specific dates to filter on
        
        if len(specific_dates) == 1:
            # Single date = exact match
            specific_date = specific_dates[0]
            date_matches = (date_field.year == specific_date.year and 
                            date_field.month == specific_date.month and 
                            date_field.day == specific_date.day)
            
            if not date_matches:
                logger.info(f"Skipping doc {doc.get('id')} (name: {doc.get('name', '')}) because date {date_field} does not match the specific date {specific_date}")
                return False
        
        elif len(specific_dates) >= 2:
            # Multiple dates = range (assume first is start, last is end)
            start_date = min(specific_dates)
            end_date = max(specific_dates)
            
            # Add timezone to match date_field
            if date_field.tzinfo is not None:
                start_date = start_date.replace(tzinfo=date_field.tzinfo)
                end_date = end_date.replace(tzinfo=date_field.tzinfo)
            
            # Set end_date to end of the day (23:59:59)
            end_date = end_date.replace(hour=23, minute=59, second=59)
            
            # Check if date_field is within range
            if date_field < start_date or date_field > end_date:
                logger.info(f"Skipping doc {doc.get('id')} (name: {doc.get('name', '')}) because date {date_field} is not within range {start_date} to {end_date}")
                return False
            else:
                logger.info(f"Doc {doc.get('id')} (name: {doc.get('name', '')}) passed date range filter with date {date_field}")
        
        return True

    def _build_chromadb_query(self, search_parameters):
        """
        Build a ChromaDB query from search parameters.
        
        Args:
            search_parameters: Dictionary containing search parameters
            
        Returns:
            Tuple of (query_where, query_text)
        """
        # Normalize the query
        query = search_parameters["query"]
        normalized_query = self._normalize_text(query)
        
        # Build ChromaDB where clause with proper operator
        conditions = []
        if "course_id" in search_parameters:
            course_id = search_parameters["course_id"]
            if course_id and course_id != "all_courses":
                conditions.append({"course_id": {"$eq": str(course_id)}})
        
        # Handle document type filtering
        if "item_types" in search_parameters:
            item_types = search_parameters["item_types"]
            if item_types and isinstance(item_types, list) and len(item_types) > 0:
                # Map item types to our internal types
                type_mapping = {
                    "assignment": "assignment",
                    "file": "file",
                    "quiz": "quiz",
                    "announcement": "announcement",
                    "event": "event"
                }
                
                normalized_types = [type_mapping[item_type] for item_type in item_types 
                                    if item_type in type_mapping]
                
                if normalized_types:
                    conditions.append({"type": {"$in": normalized_types}})
        
        # Apply the where clause if there are conditions
        query_where = None
        if len(conditions) == 1:
            query_where = conditions[0]  # Single condition
        elif len(conditions) > 1:
            query_where = {"$and": conditions}  # Multiple conditions combined with $and
        
        return query_where, normalized_query

    def _execute_chromadb_query(self, query_text, query_where, top_k):
        """
        Execute a query against ChromaDB.
        
        Args:
            query_text: Normalized query text
            query_where: Where clause for filtering
            top_k: Number of results to return
            
        Returns:
            Query results or empty dict on error
        """
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=top_k * 3,  # Get more results for post-processing
                where=query_where,
                include=["distances", "documents", "metadatas"]
            )
            return results
        except Exception as e:
            logger.error(f"ChromaDB query error with filters: {e}")
            logger.error(f"Failed query where clause: {query_where}")
            
            # If the complex query fails, try with just the course_id filter
            if isinstance(query_where, dict) and "type" in query_where and "course_id" in query_where:
                try:
                    logger.info("Trying query with only course_id filter...")
                    simplified_where = {"course_id": query_where["course_id"]}
                    results = self.collection.query(
                        query_texts=[query_text],
                        n_results=top_k * 3,
                        where=simplified_where,
                        include=["distances", "documents", "metadatas"]
                    )
                    return results
                except Exception as e2:
                    logger.error(f"Course-only filter failed: {e2}")
            
            # Last resort: try with no filters
            try:
                logger.info("Trying query with no filters...")
                results = self.collection.query(
                    query_texts=[query_text],
                    n_results=top_k * 3,
                    include=["distances", "documents", "metadatas"]
                )
                return results
            except Exception as e3:
                logger.error(f"No-filter query also failed: {e3}")
                return {}

    def _post_process_results(self, search_results, normalized_query):
        """
        Post-process search results to prioritize exact and partial matches.
        
        Args:
            search_results: List of search result dictionaries
            normalized_query: Normalized query text
            
        Returns:
            Sorted list of search results
        """
        query_terms = normalized_query.lower().split()
        exact_matches = []
        partial_matches = []
        other_results = []
        
        for result in search_results:
            doc = result['document']
            doc_type = doc.get('type', '')
            
            # Get document name based on type
            if doc_type == 'file':
                doc_name = doc.get('display_name', '').lower()
            elif doc_type == 'assignment':
                doc_name = doc.get('name', '').lower()
            elif doc_type in ['announcement', 'quiz', 'event']:
                doc_name = doc.get('title', '').lower()
            else:
                doc_name = ''
            
            # Check for exact match
            if doc_name == normalized_query.lower():
                result['similarity'] += 0.5  # Boost exact matches
                exact_matches.append(result)
            # Check for partial matches
            elif any(term in doc_name for term in query_terms):
                result['similarity'] += 0.2  # Boost partial matches
                partial_matches.append(result)
            else:
                other_results.append(result)
        
        # Combine and sort results
        combined_results = exact_matches + partial_matches + other_results
        combined_results.sort(key=lambda x: x['similarity'], reverse=True)
        
        return combined_results

    def _include_related_documents(self, search_results, search_parameters, minimum_score):
        """
        Include related documents in search results.
        
        Args:
            search_results: List of search result dictionaries
            search_parameters: Dictionary containing search parameters
            minimum_score: Minimum similarity score to include in results
        """
        related_docs = self._get_related_documents([r['document'].get('id') for r in search_results])
        
        # Map item types to internal types for filtering
        type_mapping = {
            "assignment": "assignment",
            "file": "file",
            "quiz": "quiz",
            "announcement": "announcement",
            "event": "event"
        }
        
        for doc in related_docs:
            # Apply same filters to related documents
            # Check course filter
            if "course_id" in search_parameters and search_parameters["course_id"] != "all_courses":
                doc_course_id = str(doc.get('course_id', ''))
                if doc_course_id != str(search_parameters["course_id"]):
                    continue
            
            # Check item type filter
            if "item_types" in search_parameters and search_parameters["item_types"]:
                doc_type = doc.get('type', '')
                if doc_type not in [type_mapping.get(t) for t in search_parameters["item_types"] if t in type_mapping]:
                    continue
            
            # Only add if not already in results
            if not any(r['document'].get('id') == doc.get('id') for r in search_results):
                search_results.append({
                    'document': doc,
                    'similarity': minimum_score,
                    'is_related': True
                })

    def search(self, search_parameters: Optional[dict] = None, top_k: int = 5,
               include_related: bool = True, minimum_score: float = 0.3) -> List[Dict[str, Any]]:
        """
        Search for documents similar to the query.
        
        Args:
            search_parameters: Dictionary containing filter parameters including:
                - query: The search query string
                - course_id: Course ID or 'all_courses'
                - time_range: One of 'FUTURE', 'RECENT_PAST', 'EXTENDED_PAST', 'ALL_TIME'
                - item_types: List of document types to include
                - specific_dates: Optional list of specific dates to filter by
                - keywords: Optional list of additional keywords
            top_k: Number of top results to return.
            include_related: Whether to include related documents.
            minimum_score: Minimum similarity score to include in results.
            
        Returns:
            List of search results.
        """
        # Build query for ChromaDB
        query_where, normalized_query = self._build_chromadb_query(search_parameters)
        
        # Log the search parameters for debugging
        logger.debug(f"Search query: '{normalized_query}'")
        logger.debug(f"Search parameters: {search_parameters}")
        
        # Execute ChromaDB query
        results = self._execute_chromadb_query(normalized_query, query_where, top_k)
        
        # Process results
        search_results = []
        doc_ids = results.get('ids', [[]])[0]
        distances = results.get('distances', [[]])[0]
        
        # Process each document
        for i, doc_id in enumerate(doc_ids):
            doc = self.document_map.get(doc_id)
            logger.info(f"Processing document: {doc.get('name', '')}")
            if not doc:
                continue
            
            # Apply time-based filtering
            if not self._filter_by_time(doc, search_parameters):
                continue
            
            # Apply specific date filtering
            if not self._filter_by_specific_dates(doc, search_parameters):
                continue
            
            # Calculate similarity score
            similarity = 1.0 - (distances[i] / 2.0)
            
            # Skip results below minimum score
            if similarity < minimum_score:
                logger.info(f"Skipping doc {doc_id} (name: {doc.get('name', '')}) because similarity {similarity} is below threshold {minimum_score}")
                continue
            
            # Extract content for files if needed
            if doc.get('type') == 'file' and ('content' not in doc or not doc['content']):
                try:
                    doc['content'] = self.extract_file_content(doc)
                    if doc['content']:
                        logger.info(f"Extracted content for file: {doc.get('display_name', '')}")
                except Exception as e:
                    logger.error(f"Failed to extract content: {e}")
            
            # Add to results
            logger.info(f"Adding doc {doc_id} (name: {doc.get('name', '')}) to results with similarity {similarity}")
            search_results.append({
                'document': doc,
                'similarity': similarity
            })
        
        # Include related documents if requested
        if include_related and search_results:
            self._include_related_documents(search_results, search_parameters, minimum_score)
        
        # Post-process to prioritize exact and partial matches
        combined_results = self._post_process_results(search_results, normalized_query)
        
        return combined_results[:top_k]
    
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