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
import tzlocal
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
from vectordb.content_extraction import parse_file_content

# Load environment variables
load_dotenv()

# Configure logging
# logging.basicConfig(
#     level=logging.DEBUG,
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.StreamHandler()
#     ]
# )
# logger = logging.getLogger("canvas_vector_db")



class VectorDatabase:
    def __init__(self, json_file_path: str, cache_dir = "chroma_data/", collection_name: str = None, hf_api_token: str = None):
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
                print(f"Error loading JSON file to get user_id: {e}")
                self.collection_name = "canvas_embeddings"
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
            print(f"Using existing collection: {self.collection_name}")
        
        except Exception: # If no existing collection, collection is created
            print(f"Creating new collection: {self.collection_name}")
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
                normalized_name = self.normalize_text(display_name)
                # Add the name at the beginning for emphasis
                text_parts.insert(0, f"Filename: {normalized_name}")
                # Also add it as a title for better matching
                text_parts.insert(0, f"Title: {normalized_name}")
            
            for field in ['folder_id', 'display_name', 'filename', 'url', 'size', 
                            'updated_at', 'locked', 'lock_explanation']:
                if field in doc and doc[field] is not None: # error prevention
                    # Normalize any text fields to handle special characters
                    if isinstance(doc[field], str):
                        value = self.normalize_text(doc[field])
                    else:
                        value = doc[field]
                    text_parts.append(f"{field.replace('_', ' ').title()}: {value}")
            
        elif doc_type == 'Assignment':
            # For assignments, prioritize the name by placing it at the beginning
            name = doc.get('name', '')
            if name:
                # Normalize the name to improve matching
                normalized_name = self.normalize_text(name)
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
                            value = self.normalize_text(doc[field])
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
                normalized_title = self.normalize_text(title)
                # Add the title at the beginning for emphasis
                text_parts.insert(0, f"Announcement: {normalized_title}")
                text_parts.insert(0, f"Title: {normalized_title}")
            
            for field in ['title', 'message', 'posted_at', 'course_id']:
                if field in doc and doc[field] is not None: # error prevention
                    # Normalize any text fields
                    if isinstance(doc[field], str):
                        value = self.normalize_text(doc[field])
                    else:
                        value = doc[field]
                    text_parts.append(f"{field.replace('_', ' ').title()}: {value}")
            
        elif doc_type == 'Quiz':
            # For quizzes, prioritize the title by placing it at the beginning
            title = doc.get('title', '')
            if title:
                # Normalize the title to improve matching
                normalized_title = self.normalize_text(title)
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
                        value = self.normalize_text(doc[field])
                    else:
                        value = doc[field]
                    text_parts.append(f"{field.replace('_', ' ').title()}: {value}")
            
        elif doc_type == 'Event':
            # For events, prioritize the title by placing it at the beginning
            title = doc.get('title', '')
            if title:
                # Normalize the title to improve matching
                normalized_title = self.normalize_text(title)
                # Add the title at the beginning for emphasis
                text_parts.insert(0, f"Event: {normalized_title}")
                text_parts.insert(0, f"Title: {normalized_title}")
            
            for field in ['title', 'start_at', 'end_at', 'description', 'location_name', 
                            'location_address', 'context_code', 'context_name', 
                            'all_context_codes', 'url']:
                if field in doc and doc[field] is not None:
                    # Normalize any text fields
                    if isinstance(doc[field], str):
                        value = self.normalize_text(doc[field])
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
                module_name = self.normalize_text(module_name)
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
    
    @staticmethod
    def normalize_text(text: str) -> str:
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
        try:
            with open(self.json_file_path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading JSON file: {e}")
            return False
        
        # Extract user metadata
        user_metadata = data.get('user_metadata', {})
        print(f"Processing data for user ID: {user_metadata.get('id')}")
        
        # Update local data structures regardless of force_reload
        await self._update_local_data_structures(data)
        
        # If force_reload is True, clear the collection and add all documents
        if force_reload:
            await self.clear_collection()
        else:
            # Synchronize ChromaDB by removing stale documents
            await self._synchronize_chromadb_with_local_data()
            pass
        
        # Get existing document IDs in the collection
        existing_ids = set()
        if not force_reload:
            try:
                # Get all IDs currently in the collection
                results = await asyncio.to_thread(
                    self.collection.get,
                    include=["metadatas"]
                )
                # Extract IDs from metadatas
                if 'metadatas' in results and results['metadatas']:
                    existing_ids = set(meta.get('id') for meta in results['metadatas'] if meta and 'id' in meta)
                print(f"Found {len(existing_ids)} existing documents in collection")
            except Exception as e:
                print(f"Error getting existing IDs: {e}")
        
        # Prepare lists for documents to add
        ids_to_add = []
        texts_to_add = []
        metadatas_to_add = []
        
        # Add syllabi as documents if they don't exist or if force_reload
        for course_id, syllabus in self.syllabus_map.items():
            # Generate a unique ID for the syllabus
            syllabus_id = f"syllabus_{course_id}"
            
            # Skip if syllabus already exists and not forcing reload
            if syllabus_id in existing_ids and not force_reload:
                print(f"Syllabus for course {course_id} already exists. Skipping.")
                continue
            
            # Parse the HTML content to extract plain text
            parsed_syllabus = self._parse_html_content(syllabus)
            if not parsed_syllabus:
                print(f"No content extracted from syllabus for course {course_id}")
                continue
            
            # Create a syllabus document
            syllabus_doc = {
                'id': syllabus_id,
                'type': 'syllabus',
                'course_id': course_id,
                'title': f"Syllabus for {self.course_map[course_id].get('name', f'Course {course_id}')}",
                'content': parsed_syllabus  # Use the parsed content
            }
            
            # Store document in memory if not already there
            if syllabus_id not in self.document_map:
                self.documents.append(syllabus_doc)
                self.document_map[syllabus_id] = syllabus_doc
            
            # Prepare for ChromaDB
            ids_to_add.append(syllabus_id)
            texts_to_add.append(self._preprocess_text_for_embedding(syllabus_doc))
            
            # Create metadata
            metadata = {
                'id': str(syllabus_id),
                'type': 'syllabus',
                'course_id': course_id
            }
            
            metadatas_to_add.append(metadata)
            print(f"Added syllabus for course {course_id}")
        
        # Process all document types
        for item in self.documents:
            item_id = str(item.get('id'))
            
            # Skip if document already exists and not forcing reload
            if item_id in existing_ids and not force_reload:
                print(f"Skipping existing document: {item_id}")
                continue
            
            # Skip syllabi (already handled)
            if item.get('type') == 'syllabus':
                continue
                
            # Prepare for ChromaDB
            ids_to_add.append(item_id)
            texts_to_add.append(self._preprocess_text_for_embedding(item))
            
            # Create base metadata
            metadata = {
                'id': str(item_id),
                'type': item.get('type'),
                'course_id': str(item.get('course_id', ''))
            }

            # Add module_id to metadata if it exists
            if item.get('module_id'):
                metadata['module_id'] = str(item['module_id'])
            
            # Handle event course_id from context_code
            if item.get('type') == 'event' and 'context_code' in item and item['context_code'].startswith('course_'):
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
            
            doc_type = item.get('type')
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
            
            metadatas_to_add.append(metadata)
        
        # If there are documents to add, generate embeddings and add to collection
        if ids_to_add:
            print(f"Processing {len(ids_to_add)} documents for collection")
            
            # Generate embeddings first
            embeddings = self.embedding_function(texts_to_add)
            print(f"Generated embeddings with shape: {np.array(embeddings).shape}")

            # Use upsert instead of add to avoid duplicate ID errors
            try:
                await asyncio.to_thread(
                    self.collection.upsert,  # Changed from add to upsert
                    ids=ids_to_add,
                    embeddings=embeddings,
                    documents=texts_to_add,
                    metadatas=metadatas_to_add
                )
                
                print(f"Successfully processed {len(ids_to_add)} documents in collection")
                return True
            except Exception as e:
                print(f"Error during upsert operation: {e}")
                
                # Try processing in smaller batches if the entire batch fails
                batch_size = 50
                success = False
                
                try:
                    print(f"Retrying with smaller batches of {batch_size} documents")
                    for i in range(0, len(ids_to_add), batch_size):
                        batch_ids = ids_to_add[i:i+batch_size]
                        batch_texts = texts_to_add[i:i+batch_size]
                        batch_metadatas = metadatas_to_add[i:i+batch_size]
                        batch_embeddings = embeddings[i:i+batch_size]
                        
                        await asyncio.to_thread(
                            self.collection.upsert,
                            ids=batch_ids,
                            embeddings=batch_embeddings,
                            documents=batch_texts,
                            metadatas=batch_metadatas
                        )
                        print(f"Successfully processed batch {i//batch_size + 1} ({len(batch_ids)} documents)")
                        success = True
                    
                    return success
                except Exception as batch_error:
                    print(f"Error during batch upsert: {batch_error}")
                    return False
        else:
            print("No documents to process")
            return False

    async def _synchronize_chromadb_with_local_data(self):
        """
        Synchronize ChromaDB collection with local data structures by:
        1. Removing documents from ChromaDB that no longer exist in the JSON file
        2. Keeping document embeddings that still exist

        This ensures ChromaDB perfectly reflects current local data without
        requiring a full recomputation of all embeddings.
        """
        try:
            # Get all IDs currently in the collection
            results = await asyncio.to_thread(
                self.collection.get,
                include=["metadatas"]
            )
            # Extract IDs from metadatas
            chromadb_ids = set()
            if 'metadatas' in results and results['metadatas']:
                chromadb_ids = set(meta.get('id') for meta in results['metadatas'] if meta and 'id' in meta)
            
            # Get all IDs in local data
            local_ids = set(self.document_map.keys())
            ids_to_remove = []
            for id in chromadb_ids:
                if id not in local_ids:
                    ids_to_remove.append(id)
            
            if ids_to_remove:
                print(f"Found {len(ids_to_remove)} stale documents in ChromaDB. Removing...")
                
                # Remove stale documents from ChromaDB
                await asyncio.to_thread(
                    self.collection.delete,
                    ids=list(ids_to_remove)
                )
                
                print(f"Successfully removed {len(ids_to_remove)} stale documents from ChromaDB")
            else:
                print("No stale documents found in ChromaDB")
            
            return len(ids_to_remove)
        except Exception as e:
            print(f"Error synchronizing ChromaDB with local data: {e}")
            return 0
        
    async def clear_collection(self) -> None:
        """
        Clear all documents from the ChromaDB collection without affecting local data.
        """
        try:
            # Delete the collection and recreate it
            await asyncio.to_thread(self.client.delete_collection, self.collection_name)
            print(f"Deleted collection: {self.collection_name}")
            
            # Recreate the collection
            self.collection = await asyncio.to_thread(
                self.client.create_collection,
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"}
            )
            print(f"Created new collection: {self.collection_name}")
            
            # Don't reset in-memory data - we'll refill the collection from it
            
        except Exception as e:
            print(f"Error clearing collection: {e}")
            raise

    async def _update_local_data_structures(self, data):
        """
        Update local data structures (documents, document_map, course_map, syllabus_map)
        from the JSON data.
        
        Args:
            data: Parsed JSON data from file
        """
        # Reset data structures
        self.documents = []
        self.document_map = {}
        self.course_map = {}
        self.syllabus_map = {}
        
        # Extract courses and build course and syllabus maps
        courses = data.get('courses', [])
        for course in courses:
            course_id = str(course.get('id'))
            syllabus = str(course.get('syllabus_body'))
            if course_id:
                self.course_map[course_id] = course
            if syllabus and syllabus != "None":
                self.syllabus_map[course_id] = syllabus
        
        # Process all document types
        document_types = {
            'files': 'file',
            'announcements': 'announcement',
            'assignments': 'assignment',
            'quizzes': 'quiz',
            'calendar_events': 'event'
        }
        
        for collection_key, doc_type in document_types.items():
            items = data.get(collection_key, [])
            
            for item in items:
                item_id = item.get('id')
                if not item_id:
                    continue
                
                item['type'] = doc_type
                    
                # Store document in memory
                self.documents.append(item)
                self.document_map[str(item_id)] = item
        
        # Build document relations
        self._build_document_relations(self.documents)
        
        print(f"Local data structures updated with {len(self.documents)} documents")
    
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

        # Get current time in local timezone, then convert to UTC for timestamp comparison
        local_timezone = tzlocal.get_localzone()
        current_time = datetime.now(local_timezone)
        current_timestamp = int(current_time.timestamp())
        
        # List of all possible timestamp fields across different document types
        timestamp_fields = ["due_timestamp", "posted_timestamp", "start_timestamp", "updated_timestamp"]
        
        range_conditions = []

        future_10d = current_time + timedelta(days=10)
        future_10d_timestamp = int(future_10d.timestamp())

        past_10d = current_time - timedelta(days=10)
        past_10d_timestamp = int(past_10d.timestamp())
        
        if time_range == "NEAR_FUTURE":
            for field in timestamp_fields:
                range_conditions.append({
                    "$and": [
                        {field: {"$gte": current_timestamp}},  # Now
                        {field: {"$lte": future_10d_timestamp}}  # Now + 10 days
                    ]
                })
        
        elif time_range == "FUTURE":
            for field in timestamp_fields:
                range_conditions.append({field: {"$gte": future_10d_timestamp}})  # Future items only
        
        elif time_range == "RECENT_PAST":
            for field in timestamp_fields:
                range_conditions.append({
                    "$and": [
                        {field: {"$gte": past_10d_timestamp}},  # Now - 10 days
                        {field: {"$lte": current_timestamp}}  # Now
                    ]
                })
        
        elif time_range == "PAST":
            for field in timestamp_fields:
                range_conditions.append({field: {"$lte": past_10d_timestamp}})  # Past items only
        
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
        
        local_timezone = tzlocal.get_localzone()
        specific_dates = []
        
        for date_str in search_parameters["specific_dates"]:
            try:
                # Parse naive date (without timezone)
                naive_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                # Make it timezone-aware by replacing the tzinfo
                # This is the modern way that works with both pytz and zoneinfo
                specific_date = naive_date.replace(tzinfo=local_timezone)
                
                specific_dates.append(specific_date)
            except ValueError:
                print(f"Invalid date format: {date_str}, expected YYYY-MM-DD")
        
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
        normalized_query = self.normalize_text(text=query)
        
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
            print(f"Executing ChromaDB query with query_text: {query_text}")
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
            print(f"ChromaDB query error with filters: {e}")
            print(f"Failed query where clause: {query_where}")
            
            # If the complex query fails, try with just the course_id filter
            if isinstance(query_where, dict) and "type" in query_where and "course_id" in query_where:
                try:
                    print("Trying query with only course_id filter...")
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
                    print(f"Course-only filter failed: {e2}")
            
            # Last resort: try with no filters
            try:
                print("Trying query with no filters...")
                results = await asyncio.to_thread(
                    self.collection.query,
                    query_texts=[query_text],
                    n_results=top_k,
                    include=["distances", "documents", "metadatas"]
                )
                return results
            except Exception as e3:
                print(f"No-filter query also failed: {e3}")
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
        local_timezone = tzlocal.get_localzone()
        
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
                        # Parse date from UTC and convert to local timezone
                        date_obj = datetime.fromisoformat(doc[date_field].replace('Z', '+00:00'))
                        local_date = date_obj.astimezone(local_timezone)
                        
                        # Add localized time string
                        doc[f'local_{date_field}'] = local_date.strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Now calculate relative time using local time
                        now = datetime.now(local_timezone)
                        
                        # Add relative time
                        delta = local_date - now
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
                    except Exception as e:
                        print(f"Error converting time: {e}")
        
        return search_results

    async def search(self, search_parameters, include_related=False, minimum_score=0.3):
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
            include_related: Whether to include related documents.
            minimum_score: Minimum similarity score to include in results.
            
        Returns:
            List of search results.
        """
        # Build query for ChromaDB including course id, item type, and time-based filters
        query_where, normalized_query = self._build_chromadb_query(search_parameters)
        top_k = self._determine_top_k(search_parameters)
        
        # Log the search parameters for debugging
        print("\n\n--------------------------------")
        print(f"Top K: {top_k}")
        print(f"Search query: '{normalized_query}'")
        print(f"Search parameters: {search_parameters}")
        print(f"Query where: {query_where}")
        print("--------------------------------\n\n")

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

            print(f"Processing document: {doc.get('name', '')}")
            
            # Calculate similarity score
            similarity = 1.0 - (distances[i] / 2.0)
            
            # Skip results below minimum score
            if similarity < minimum_score:
                print(f"Skipping doc {doc_id} because similarity {similarity} is below threshold {minimum_score}")
                continue

            if doc.get('type') == 'file':
                try:
                    doc['content'] = await parse_file_content(doc.get('url'))
                except Exception as e:
                    print(f"Failed to extract content for file {doc.get('display_name', '')}: {e}")

            
            # Add to results
            print(f"Adding doc {doc.get('name', '')} to results with similarity {similarity}")
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

        for result in combined_results:
            result.pop('similarity', None)  # Remove similarity score from each result
            result.pop('related_docs', None) # Remove related docs from each result for now, not currently being used
        
        print(combined_results)
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
            print(f"Deleted collection: {self.collection_name}")
            
            # Recreate the collection
            self.collection = await asyncio.to_thread(
                self.client.create_collection,
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"}
            )
            print(f"Created new collection: {self.collection_name}")
            
            # Reset in-memory data
            self.documents = []
            self.document_map = {}
            self.course_map = {}
            
        except Exception as e:
            print(f"Error clearing cache: {e}")

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
            print(f"Error parsing HTML content: {e}")
            # Fallback to a simple tag stripping approach if the parser fails
            text = re.sub(r'<[^>]*>', ' ', html_content)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()