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
import requests
from datetime import datetime, timedelta, timezone
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
import asyncio
import aiohttp
import re  # Adding import for re module used in _parse_html_content

# Add the project root directory to Python path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from backend.data_retrieval.get_all_user_data import extract_text_and_images
from vectordb.embedding_model import create_hf_embedding_function


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
    def __init__(self, json_file_path: str, cache_dir: str = DEFAULT_CACHE_DIR, collection_name: str = None, hf_api_token: str = None):
        """
        Initialize the vector database with ChromaDB.
        
        Args:
            json_file_path: Path to the JSON file containing the documents.
            cache_dir: Directory to store ChromaDB data.
            collection_name: Name of the ChromaDB collection. If None, will use user_id from the json file.
            hf_api_token: Hugging Face API token for accessing the embedding model.
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
        
        # Use Hugging Face API for embeddings with multilingual-e5-large-instruct model
        self.hf_api_token = hf_api_token
        if not self.hf_api_token:
            raise ValueError("Hugging Face API token is required. Provide it as a parameter or set HUGGINGFACE_API_TOKEN environment variable.")
        
        # Custom embedding function using Hugging Face API
        self.embedding_function = create_hf_embedding_function(self.hf_api_token)
        
        self.documents = [] # stores documents
        self.document_map = {} # Allows O(1) lookup of documents by ID
        self.course_map = {} # information about courses
        self.syllabus_map = {} # information about syllabi
        
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
        #       https://www.example.co 
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
    
    
        
    async def process_data(self, force_reload: bool = False) -> bool:
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
        
        # Extract courses and build course and syllabus maps
        courses = data.get('courses', [])
        for course in courses:
            course_id = str(course.get('id'))
            syllabus = str(course.get('syllabus_body'))
            if course_id:
                self.course_map[course_id] = course
            if syllabus:
                self.syllabus_map[course_id] = syllabus

        ids = [] # list of document IDs
        texts = [] # list of preprocessed text for each document
        metadatas = [] # list of metadata for each document
        
        # Add syllabi as documents
        for course_id, syllabus in self.syllabus_map.items():
            if not syllabus or syllabus == "None":
                continue
            
            # Parse the HTML content to extract plain text
            parsed_syllabus = self._parse_html_content(syllabus)
            if not parsed_syllabus:
                logger.warning(f"No content extracted from syllabus for course {course_id}")
                continue
            
            # Generate a unique ID for the syllabus
            syllabus_id = f"syllabus_{course_id}"
            
            # Create a syllabus document
            syllabus_doc = {
                'id': syllabus_id,
                'type': 'syllabus',
                'course_id': course_id,
                'title': f"Syllabus for {self.course_map[course_id].get('name', f'Course {course_id}')}",
                'content': parsed_syllabus  # Use the parsed content
            }
            
            # Store document in memory
            self.documents.append(syllabus_doc)
            self.document_map[syllabus_id] = syllabus_doc
            
            # Prepare for ChromaDB
            ids.append(syllabus_id)
            texts.append(self._preprocess_text_for_embedding(syllabus_doc))
            
            # Create metadata
            metadata = {
                'id': syllabus_id,
                'type': 'syllabus',
                'course_id': course_id
            }
            
            metadatas.append(metadata)
            logger.info(f"Added syllabus for course {course_id}")
        
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
                
                # Handle event course_id from context_code
                if doc_type == 'event' and 'context_code' in item and item['context_code'].startswith('course_'):
                    course_id = item['context_code'].replace('course_', '')
                    item['course_id'] = course_id
                    metadata['course_id'] = str(course_id)
                
                # Add date fields to metadata based on document type
                date_field_mapping = {
                    'assignment': ('due_at', 'due_timestamp'),
                    'announcement': ('posted_at', 'posted_timestamp'),
                    'quiz': ('due_at', 'due_timestamp'),
                    'event': ('start_at', 'start_timestamp'),
                    'file': ('updated_at', 'updated_timestamp')
                }
                
                if doc_type in date_field_mapping:
                    source_field, target_field = date_field_mapping[doc_type]
                    if item.get(source_field):
                        try:
                            date_obj = datetime.fromisoformat(item[source_field].replace('Z', '+00:00'))
                            metadata[target_field] = int(date_obj.timestamp())
                        except (ValueError, AttributeError):
                            pass
                
                # Add file-specific metadata
                if doc_type == 'file':
                    metadata['folder_id'] = str(item.get('folder_id', ''))
                
                metadatas.append(metadata)
        
        # Build document relations
        self._build_document_relations(self.documents)
        
        # Generate embeddings first
        embeddings = self.embedding_function(texts)
        logger.info(f"Generated embeddings with shape: {embeddings.shape}")

        # Then add to collection with explicit embeddings
        self.collection.add(
            ids=ids,
            embeddings=embeddings,  # Pass pre-computed embeddings
            documents=texts,
            metadatas=metadatas
        )
        
        # Save to cache
        self._save_to_cache()
        
        return True
    
    async def _load_document_metadata(self):
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
    
    async def extract_file_content(self, doc: Dict[str, Any]) -> str:
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
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to download file {url}: {response.status}")
                        return ""
                    
                    # Get the raw file content as bytes
                    file_bytes = await response.read()
            
            # Use the imported extract_text_and_images function
            extracted_text = extract_text_and_images(file_bytes, file_extension)
            return extracted_text
                
        except Exception as e:
            logger.error(f"Error downloading or processing file {url}: {e}")
            return "" 
    
    

    def _build_time_range_filter(self, search_parameters):
        """
        Build time range filter conditions for ChromaDB query.
        
        Args:
            search_parameters: Dictionary containing search parameters
            
        Returns:
            List of time range filter conditions to be added to the main where clause
        """
        if not search_parameters or "time_range" not in search_parameters or not search_parameters["time_range"]:
            return []
        
        time_range = search_parameters["time_range"]

        current_time = datetime.now(timezone.utc)
        current_timestamp = int(current_time.timestamp())
        
        # List of all possible timestamp fields across different document types
        timestamp_fields = ["due_timestamp", "posted_timestamp", "start_timestamp", "updated_timestamp"]
        
        range_conditions = []

        ten_days_from_now = current_time + timedelta(days=10)
        ten_days_from_now_timestamp = int(ten_days_from_now.timestamp())
        
        if time_range == "NEAR_FUTURE":
            for field in timestamp_fields:
                range_conditions.append({
                    "$and": [
                        {field: {"$gte": current_timestamp}},  # Now
                        {field: {"$lte": ten_days_from_now_timestamp}}  # Now + 10 days
                    ]
                })
        
        elif time_range == "FUTURE":
            for field in timestamp_fields:
                range_conditions.append({field: {"$gte": ten_days_from_now_timestamp}})  # Future items only
        
        elif time_range == "RECENT_PAST":
            for field in timestamp_fields:
                range_conditions.append({
                    "$and": [
                        {field: {"$gte": ten_days_from_now_timestamp}},  # Now - 10 days
                        {field: {"$lte": current_timestamp}}  # Now
                    ]
                })
        
        elif time_range == "PAST":
            for field in timestamp_fields:
                range_conditions.append({field: {"$lte": ten_days_from_now_timestamp}})  # Past items only
        
        elif time_range == "ALL_TIME":
            # No filtering needed, return empty list
            return []
        
        # Return time range condition or empty list if no valid range
        return [{"$or": range_conditions}] if range_conditions else []

    def _build_specific_dates_filter(self, search_parameters):
        """
        Build specific dates filter conditions for ChromaDB query.
        
        Args:
            search_parameters: Dictionary containing search parameters
            
        Returns:
            List of specific dates filter conditions to be added to the main where clause
        """
        if not search_parameters or "specific_dates" not in search_parameters or not search_parameters["specific_dates"]:
            return []
        
        specific_dates = []
        for date_str in search_parameters["specific_dates"]:
            try:
                specific_date = datetime.strptime(date_str, "%Y-%m-%d")
                specific_dates.append(specific_date)
            except ValueError:
                logger.warning(f"Invalid date format: {date_str}, expected YYYY-MM-DD")
        
        if not specific_dates:
            return []  # No valid specific dates to filter on
        
        timestamp_fields = ["due_timestamp", "posted_timestamp", "start_timestamp", "updated_timestamp"]
        date_conditions = []
        
        if len(specific_dates) == 1:
            # Single date = exact match (within day)
            specific_date = specific_dates[0]
            start_timestamp = int(specific_date.replace(hour=0, minute=0, second=0).timestamp())
            end_timestamp = int(specific_date.replace(hour=23, minute=59, second=59).timestamp())
            
            for field in timestamp_fields:
                date_conditions.append({
                    "$and": [
                        {field: {"$gte": start_timestamp}}, # $gte: >=
                        {field: {"$lte": end_timestamp}} # $lte: <=
                    ]
                })
                # filter: item >= start_timestamp AND item <= end_timestamp
                # item must be on EXACT specific_date when filtering by a single date

        elif len(specific_dates) >= 2:
            # Date range
            start_date = min(specific_dates)
            end_date = max(specific_dates)
            
            start_timestamp = int(start_date.replace(hour=0, minute=0, second=0).timestamp())
            end_timestamp = int(end_date.replace(hour=23, minute=59, second=59).timestamp())
            
            for field in timestamp_fields:
                date_conditions.append({
                    "$and": [
                        {field: {"$gte": start_timestamp}}, # $gte: >=
                        {field: {"$lte": end_timestamp}} # $lte: <=
                    ]
                })
                # filter: item >= start_timestamp AND item <= end_timestamp
                # item must be between start_date and end_date when filtering by a date range
        
        # Return date condition or empty list if no valid conditions
        return [{"$or": date_conditions}] if date_conditions else []

    def _build_course_and_type_filter(self, search_parameters):
        """
        Build course and document type filter conditions for ChromaDB query.
        
        Args:
            search_parameters: Dictionary containing search parameters
            
        Returns:
            List of course and type filter conditions to be added to the main where clause
        """
        conditions = []
        
        # Add course filter
        if "course_id" in search_parameters:
            course_id = search_parameters["course_id"]
            if course_id and course_id != "all_courses":
                conditions.append({"course_id": {"$eq": str(course_id)}}) # $eq: ==
                # filter: item.course_id == course_id
                
        # Add document type filter
        if "item_types" in search_parameters:
            item_types = search_parameters["item_types"]
            if item_types and isinstance(item_types, list) and len(item_types) > 0:
                # Map item types to our internal types
                type_mapping = {
                    "assignment": "assignment",
                    "file": "file",
                    "quiz": "quiz",
                    "announcement": "announcement",
                    "event": "event",
                    "syllabus": "syllabus"
                }
                
                normalized_types = [type_mapping[item_type] for item_type in item_types 
                                    if item_type in type_mapping]
                if normalized_types:
                    conditions.append({"type": {"$in": normalized_types}}) # $in: in
                    # filter: item.type in item_types

        return conditions

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
        
        # Add course and document type filters
        course_type_conditions = self._build_course_and_type_filter(search_parameters)
        conditions.extend(course_type_conditions)
        
        # Add time range filter
        time_range_conditions = self._build_time_range_filter(search_parameters)
        conditions.extend(time_range_conditions)
        
        # Add specific dates filter
        specific_dates_conditions = self._build_specific_dates_filter(search_parameters)
        conditions.extend(specific_dates_conditions)
        
        # Apply the where clause if there are conditions
        query_where = None
        if len(conditions) == 1:
            query_where = conditions[0]  # Single condition
        elif len(conditions) > 1:
            query_where = {"$and": conditions}  # Multiple conditions combined with $and
        
        return query_where, normalized_query

    async def _execute_chromadb_query(self, query_text, query_where, top_k):
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
            logger.info(f"Executing ChromaDB query with query_text: {query_text}")
            # Use asyncio to prevent blocking the event loop during the ChromaDB query
            results = await asyncio.to_thread(
                self.collection.query,
                query_texts=[query_text],
                n_results=top_k,
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
                    results = await asyncio.to_thread(
                        self.collection.query,
                        query_texts=[query_text],
                        n_results=top_k,
                        where=simplified_where,
                        include=["distances", "documents", "metadatas"]
                    )
                    return results
                except Exception as e2:
                    logger.error(f"Course-only filter failed: {e2}")
            
            # Last resort: try with no filters
            try:
                logger.info("Trying query with no filters...")
                results = await asyncio.to_thread(
                    self.collection.query,
                    query_texts=[query_text],
                    n_results=top_k,
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

    def _determine_top_k(self, search_parameters):
        """
        Determine the number of top results to return based on generality
        and other search parameters for optimized retrieval.
        
        Args:
            search_parameters: Dictionary containing filter parameters
            
        Returns:
            Integer representing the top_k value to use for search
        """
        # Default mapping of generality levels to top_k values
        generality_mapping = { 
            "LOW": 5,         # Focused search
            "MEDIUM": 10,     # Balanced approach (default)
            "HIGH": 20        # Comprehensive search
        }
        # Extract generality from parameters, default to MEDIUM
        generality = search_parameters.get("generality", "MEDIUM")
        
        # Check if generality is a numeric value
        if search_parameters.get("specific_amount"):
            top_k = search_parameters.get("specific_amount")
        else:
            # Handle string generality values
            if generality in generality_mapping:
                top_k = generality_mapping[generality]
            else:
                top_k = generality_mapping["MEDIUM"]

        course_id = search_parameters.get("course_id", "all_courses")
        if course_id == "all_courses" and not isinstance(top_k, int):
            top_k = int(top_k * 1.5)
        
        # Adjust for time range - use fewer results for shorter time ranges
        time_range = search_parameters.get("time_range", "ALL_TIME")
        if time_range in ["NEAR_FUTURE", "RECENT_PAST"]:
            top_k = max(3, int(top_k * 0.8))
        
        # Ensure reasonable limits
        return max(1, min(top_k, 30))
    
    def _augment_results(self, search_results):
        """
        Augment search results with additional information.
        
        Args:
            search_results: List of search result dictionaries
        """
        for result in search_results:
            doc = result['document']
            doc_type = doc.get('type', '')
            
            # Add course name
            course_id = doc.get('course_id')
            if course_id and course_id in self.course_map:
                # Get course name and code
                course = self.course_map[course_id]
                course_name, course_code = course.get('name', ''), course.get('course_code', '')

                doc['course_name'] = course_name
                doc['course_code'] = course_code

            # Add time context
            for date_field in ['due_at', 'posted_at', 'start_at', 'updated_at']:
                if date_field in doc and doc[date_field]:
                    try:
                        date_obj = datetime.fromisoformat(doc[date_field].replace('Z', '+00:00'))
                        now = datetime.now(timezone.utc)
                        
                        # Add relative time
                        delta = date_obj - now
                        days = delta.days
                        
                        if days > 0:
                            if days == 0:
                                doc['relative_time'] = "Today"
                            elif days == 1:
                                doc['relative_time'] = "Tomorrow"
                            elif days < 7:
                                doc['relative_time'] = f"In {days} days"
                        else:
                            days = abs(days)
                            if days == 0:
                                doc['relative_time'] = "Today"
                            elif days == 1:
                                doc['relative_time'] = "Yesterday"
                            elif days < 7:
                                doc['relative_time'] = f"{days} days ago"
                        
                        break  # Only process the first date field found
                    except:
                        pass
        
        return search_results


    async def search(self, search_parameters: Optional[dict] = None,
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
        # Build query for ChromaDB including course id, item type, and time-based filters
        query_where, normalized_query = self._build_chromadb_query(search_parameters)
        top_k = self.determine_top_k(search_parameters)
        
        # Log the search parameters for debugging
        logger.debug(f"Search query: '{normalized_query}'")
        logger.debug(f"Search parameters: {search_parameters}")

        task_description = "Given a student query about course materials, retrieve relevant Canvas resources that provide comprehensive information to answer the query."
        formatted_query = f"Instruct: {task_description}\nQuery: {normalized_query}"
        
        # Execute ChromaDB query
        results = await self._execute_chromadb_query(formatted_query, query_where, top_k)
        
        # Process results
        search_results = []
        doc_ids = results.get('ids', [[]])[0]
        distances = results.get('distances', [[]])[0]
        
        # Process each document
        for i, doc_id in enumerate(doc_ids):
            doc = self.document_map.get(doc_id)
            if not doc:
                continue

            logger.info(f"Processing document: {doc.get('name', '')}")
            
            # Calculate similarity score
            similarity = 1.0 - (distances[i] / 2.0)
            
            # Skip results below minimum score
            if similarity < minimum_score:
                logger.info(f"Skipping doc {doc_id} because similarity {similarity} is below threshold {minimum_score}")
                continue
            
            # Extract content for files if needed
            if doc.get('type') == 'file' and ('content' not in doc or not doc['content']):
                try:
                    doc['content'] = await self.extract_file_content(doc)
                    if doc['content']:
                        logger.info(f"Extracted content for file: {doc.get('display_name', '')}")
                except Exception as e:
                    logger.error(f"Failed to extract content: {e}")
            
            # Add to results
            logger.info(f"Adding doc {doc_id} to results with similarity {similarity}")
            search_results.append({
                'document': doc,
                'similarity': similarity
            })
        
        # Include related documents if requested
        if include_related and search_results:
            self._include_related_documents(search_results, search_parameters, minimum_score)
        
        # Post-process to prioritize exact and partial matches
        combined_results = self._post_process_results(search_results, normalized_query)

        # Augment results with additional information
        combined_results = self._augment_results(combined_results)
        
        return combined_results[:top_k]
    
    async def get_available_courses(self) -> List[Dict[str, Any]]:
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
    
    async def clear_cache(self) -> None:
        """
        Clear the ChromaDB collection.
        """
        try:
            await asyncio.to_thread(self.client.delete_collection, self.collection_name)
            logger.info(f"Deleted collection: {self.collection_name}")
            
            # Recreate the collection
            self.collection = await asyncio.to_thread(
                self.client.create_collection,
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

    def _parse_html_content(self, html_content: str) -> str:
        """
        Parse HTML content to extract plain text.
        
        Args:
            html_content: HTML content string to parse
            
        Returns:
            Plain text extracted from HTML content
        """
        if not html_content or html_content == "None":
            return ""
        
        try:
            from html.parser import HTMLParser
            
            class HTMLTextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                    self.in_script = False
                    self.in_style = False
                    
                def handle_starttag(self, tag, attrs):
                    if tag.lower() == "script":
                        self.in_script = True
                    elif tag.lower() == "style":
                        self.in_style = True
                    elif tag.lower() == "br" or tag.lower() == "p":
                        self.text_parts.append("\n")
                    elif tag.lower() == "li":
                        self.text_parts.append("\n• ")
                
                def handle_endtag(self, tag):
                    if tag.lower() == "script":
                        self.in_script = False
                    elif tag.lower() == "style":
                        self.in_style = False
                    elif tag.lower() in ["div", "h1", "h2", "h3", "h4", "h5", "h6", "tr"]:
                        self.text_parts.append("\n")
                
                def handle_data(self, data):
                    if not self.in_script and not self.in_style:
                        # Only append non-empty strings after stripping whitespace
                        text = data.strip()
                        if text:
                            self.text_parts.append(text)
            
                def get_text(self):
                    # Join all text parts and normalize whitespace
                    text = " ".join(self.text_parts)
                    # Replace multiple whitespace with a single space
                    text = re.sub(r'\s+', ' ', text)
                    # Replace multiple newlines with a single newline
                    text = re.sub(r'\n+', '\n', text)
                    return text.strip()
            
            extractor = HTMLTextExtractor()
            extractor.feed(html_content)
            return extractor.get_text()
            
        except Exception as e:
            logger.error(f"Error parsing HTML content: {e}")
            # Fallback to a simple tag stripping approach if the parser fails
            text = re.sub(r'<[^>]*>', ' ', html_content)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()