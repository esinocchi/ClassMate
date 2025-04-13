#!/usr/bin/env python3
"""
Vector Database Module for Canvas Data Orchestration
----------------------------------------------------
This module defines the `VectorDatabase` class, which serves as the primary interface 
for interacting with the ChromaDB vector store containing Canvas course data embeddings. 
It manages the ChromaDB connection, orchestrates data processing and synchronization, 
and handles search requests by utilizing helper modules for specific tasks.

Key features:
1. **ChromaDB Connection**: Manages the connection to the persistent ChromaDB store.
2. **Data Synchronization**: Handles loading data from the source JSON, updating internal 
   data structures (`document_map`, `course_map`, etc.), and synchronizing the 
   ChromaDB collection (upserting new/changed embeddings, deleting stale ones).
3. **Search Orchestration**: Processes search queries, builds appropriate filters 
   (via `vectordb.filters`), executes ChromaDB vector searches, handles keyword 
   matching (via `vectordb.filters`), and processes/augments results 
   (via `vectordb.result_processor`).
4. **Text Preprocessing Integration**: Utilizes `vectordb.text_processor` to prepare 
   document text for embedding during data processing.
5. **Embedding Function**: Manages the Hugging Face embedding function via 
   `vectordb.embedding_model`.

Usage:
1. Initialize `VectorDatabase` with the path to the user's JSON data file and HF token.
2. Call `process_data()` during initial setup or data refresh to populate/sync the DB.
3. Call `search()` to find relevant documents based on search parameters.

Helper Modules:
- `vectordb.text_processor`: Handles text normalization and formatting for embeddings.
- `vectordb.filters`: Builds ChromaDB query filters and performs keyword matching.
- `vectordb.result_processor`: Post-processes and augments search results.
- `vectordb.embedding_model`: Creates the embedding function.
- `vectordb.content_extraction`: Extracts text content from files/HTML (used during processing).

Note: Ensure the source JSON data file is structured correctly.
"""

import os
import json
import sys
import tzlocal
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv
import chromadb
import requests
from datetime import datetime, timedelta, timezone
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
import asyncio
import aiohttp
import re
# Add the project root directory to Python path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from vectordb.embedding_model import create_hf_embedding_function
from vectordb.content_extraction import parse_file_content, parse_html_content
from vectordb.text_processing import preprocess_text_for_embedding
from vectordb.filters import handle_keywords, build_chromadb_query
from vectordb.post_process import post_process_results, augment_results
# Load environment variables
load_dotenv()



class VectorDatabase:
    def __init__(self, json_file_path: str, cache_dir = None, collection_name: str = None, hf_api_token: str = None):
        """
        Initialize the vector database with ChromaDB.
        
        Args:
            json_file_path: Path to the JSON file containing the documents.
            cache_dir: Directory to store ChromaDB data. If None, will use the directory of the JSON file.
            collection_name: Name of the ChromaDB collection. If None, will use user_id from the json file.
            hf_api_token: Hugging Face API token for accessing the embedding model.
        """
        self.json_file_path = json_file_path
        
        # If cache_dir is not provided, use the directory of the JSON file
        if cache_dir is None:
            self.cache_dir = os.path.dirname(json_file_path)
        else:
            self.cache_dir = "chroma_data/"
        
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
        self.client = chromadb.PersistentClient(path=self.cache_dir)
        
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
    
    async def process_data(self) -> bool:
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
        
        # Update local data structures
        await self._update_local_data_structures(data)
        
        removed_count = await self._synchronize_chromadb_with_local_data()
        print(f"Removed {removed_count} stale documents from ChromaDB.")
        
        # Get existing document IDs in the collection
        existing_ids = await self._get_all_collection_ids()
        
        # Prepare lists for documents to add
        ids_to_add = []
        texts_to_add = []
        metadatas_to_add = []
        
        # Process syllabi
        for course_id, syllabus in self.syllabus_map.items():
            # Generate a unique ID for the syllabus
            syllabus_id = f"syllabus_{course_id}"
            
            if syllabus_id in existing_ids:
                print(f"Syllabus for course {course_id} already exists. Skipping.")
                continue
            
            # Parse the HTML content to extract plain text
            parsed_syllabus = parse_html_content(syllabus)
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
            texts_to_add.append(preprocess_text_for_embedding(syllabus_doc))
            
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
            
            # Skip if document already exists
            if item_id in existing_ids:
                #print(f"Skipping existing document: {item_id}")
                continue
            
            # Skip syllabi (already handled)
            if item.get('type') == 'syllabus':
                continue
                
            # Prepare for ChromaDB
            print(f"Processing item: {item_id}")
            ids_to_add.append(item_id)
            texts_to_add.append(preprocess_text_for_embedding(item))
            
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
            print(f"\n=== CHROMADB QUERY DEBUG ===")
            print(f"Query text: {query_text}")
            print(f"Full where clause: {query_where}")
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
            
    async def search(self, search_parameters, function_name='search', include_related=False, minimum_score=0.3):
        """
        Search for documents similar to the query.
        
        Args:
            search_parameters: Dictionary containing filter parameters.
            include_related: Whether to include related documents.
            minimum_score: Minimum similarity score.
            
        Returns:
            List of search results.
        """
        query_where, normalized_query = await build_chromadb_query(search_parameters)
        top_k = self._determine_top_k(search_parameters)

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

        # Initialize lists (handle empty results gracefully)
        doc_ids = results.get('ids', [[]])[0] if results.get('ids') else []
        distances = results.get('distances', [[]])[0] if results.get('distances') else []
        search_results = []

        # Process initial ChromaDB results
        for i in range(len(doc_ids)):
            doc_id = doc_ids[i]
            distance = distances[i]
            doc = self.document_map.get(doc_id)  # Get the document here
            if not doc:
                continue

            similarity = 1.0 - distance  # Calculate similarity

            if similarity < minimum_score:
                #print(f"Skipping doc {doc_id} (semantic) - low similarity: {similarity}")
                continue

            search_results.append({
                'document': doc,
                'similarity': similarity,
                'type': 'semantic'  # Indicate source
            })

        # --- Keyword Handling ---

        print(f"Search results")

        courses = search_parameters.get("course_id", "all_courses")

        keywords = search_parameters.get("keywords", [])

        # assign item types for keyword search based on function name
        if function_name == "calculate_grade":
            item_types = ["assignment"]
        elif function_name == "find_file":
            item_types = ["file"]
        elif function_name == "search":
            item_types = search_parameters.get("item_types", [])

        if keywords:
            keyword_matches = handle_keywords(self.document_map, keywords, doc_ids, courses, item_types)
            print(f"Keyword matches: {keyword_matches}")

            for match in keyword_matches:
                keyword_similarity = 0.93
                search_results.append({
                    'document': match['document'],
                    'similarity': keyword_similarity,
                    'type': match['document'].get('type')
                })
            

        # --- Sort by similarity (descending) ---
        search_results.sort(key=lambda x: x['similarity'], reverse=True)

        # --- Process each document (including file content extraction) ---
        for result in search_results:
            doc = result['document']
            doc_id = doc['id']

            print(f"Processing document: {doc_id}, Type: {result.get('type')}")

            # Check if it's a file and extract content
            if doc.get('type') == 'file':
                try:
                    doc['content'] = await parse_file_content(doc.get('url'))
                    print(f"Extracted content for file {doc.get('display_name', '')}")
                except Exception as e:
                    print(f"Failed to extract content for file {doc.get('display_name', '')}: {e}")

        # Include related documents if requested
        if include_related and search_results:
            self._include_related_documents(search_results, search_parameters, minimum_score)

        # Post-process to prioritize exact and partial matches
        combined_results = post_process_results(search_results, normalized_query)

        # Augment results with additional information
        combined_results = augment_results(self.course_map, combined_results)

        for result_item in combined_results:
            result_item.pop('similarity', None)  # Remove similarity
            result_item.pop('related_docs', None)  # Remove related docs

        return combined_results[:top_k]
    
    async def load_local_data_from_json(self):
        """Loads data from the JSON file into memory (document_map, course_map, etc.)
           without performing any database writes or synchronization. 
           Intended for initializing read-only/search instances.
        """
        # --- Convert string path to Path object ---
        try:
             # If self.json_file_path is already a Path object from __init__, this is harmless.
             # If it's a string, this converts it.
             path_obj = Path(self.json_file_path) 
        except TypeError as e:
             print(f"Error creating Path object from json_file_path ('{self.json_file_path}'): {e}")
             # Handle error state: ensure maps are empty
             self.documents = []
             self.document_map = {}
             self.course_map = {}
             self.syllabus_map = {}
             return

        print(f"Attempting to load local data structures from: {path_obj}")
        
        # --- Use the Path object for the check ---
        if not path_obj.is_file():
            print(f"Error: JSON file not found at {path_obj}. Cannot load local data.")
            self.documents = []
            self.document_map = {}
            self.course_map = {}
            self.syllabus_map = {}
            return # Exit early if file not found

        try:
            # --- Use the Path object to open the file ---
            with open(path_obj, 'r') as f:
                data = json.load(f)
            # Populate self.documents, self.document_map, etc. using the existing internal method
            await self._update_local_data_structures(data) 
            print(f"Successfully loaded local data structures ({len(self.document_map)} docs) from JSON.")
        except FileNotFoundError:
             # This case should be caught by the is_file() check above, but included for safety
             print(f"Error: JSON file not found at {path_obj} during loading.")
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {path_obj}.")
            # Consider resetting maps to empty state on decode error
            self.documents = []
            self.document_map = {}
            self.course_map = {}
            self.syllabus_map = {}
        except Exception as e:
            print(f"Error loading local data from JSON: {e}")
            # Optionally re-raise or handle more gracefully

    def _get_related_documents(self, doc_ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieves related document data based on IDs stored in 'related_docs' key."""
        related_docs = []
        seen_ids = set(doc_ids)
        
        for doc_id in doc_ids:
            doc = self.document_map.get(str(doc_id)) 
            if not doc or not isinstance(doc, dict): continue 
            
            doc_related_ids = doc.get('related_docs', [])
            if not isinstance(doc_related_ids, list): continue 

            for related_id in doc_related_ids:
                 related_id_str = str(related_id) 
                 if related_id_str not in seen_ids:
                     related_doc_data = self.document_map.get(related_id_str)
                     if related_doc_data:
                         related_docs.append(related_doc_data.copy()) 
                         seen_ids.add(related_id_str)
        return related_docs

    async def _update_local_data_structures(self, data: Dict[str, Any]):
        """Updates in-memory maps (documents, document_map, course_map, syllabus_map)."""
        self.documents = []
        self.document_map = {}
        self.course_map = {}
        self.syllabus_map = {}
        
        # Process Courses
        for course in data.get('courses', []):
            course_id = str(course.get('id', ''))
            if course_id and isinstance(course, dict):
                self.course_map[course_id] = course
                syllabus_body = str(course.get('syllabus_body', ''))
                if syllabus_body and syllabus_body.lower() != 'none' and syllabus_body.strip():
                    self.syllabus_map[course_id] = syllabus_body


        # Process Syllabus
        for course_id, syllabus in self.syllabus_map.items():
            parsed_syllabus = parse_html_content(syllabus)
            if parsed_syllabus:
                syllabus_id = f"syllabus_{course_id}"
                syllabus_doc = {
                    'id': syllabus_id,
                    'type': 'syllabus',
                    'course_id': course_id,
                    'title': f"Syllabus for {self.course_map[course_id].get('name', f'Course {course_id}')}",
                    'content': parsed_syllabus
                }
                self.documents.append(syllabus_doc)
                self.document_map[syllabus_id] = syllabus_doc
            else:
                print(f"Warning: Skipping invalid syllabus for course. parse_html_content failed for course {course_id}")

        # Process Document Types
        document_types_keys = {
            'files': 'file', 'announcements': 'announcement', 'assignments': 'assignment',
            'quizzes': 'quiz', 'calendar_events': 'event'
        }
        for collection_key, doc_type in document_types_keys.items():
            for item in data.get(collection_key, []):
                if isinstance(item, dict) and 'id' in item:
                    item_id_str = str(item['id'])
                    item['type'] = doc_type
                    if 'course_id' in item:
                        item['course_id'] = str(item['course_id'])
                    elif doc_type == 'event' and item.get('context_code', '').startswith('course_'):
                        item['course_id'] = item['context_code'].replace('course_', '')
                    
                    self.documents.append(item)
                    self.document_map[item_id_str] = item
                # else: print(f"Warning: Skipping invalid item in '{collection_key}': {item}") # Optional log
        
        self._build_document_relations() # Call internal method
        print(f"Local data structures updated: {len(self.documents)} docs, {len(self.course_map)} courses.")

    def _build_document_relations(self):
        """Build relations between documents based on course/module."""
        # Operates on self.documents
        if not self.documents: return

        for doc in self.documents:
            if not isinstance(doc, dict): continue 
            doc_id = doc.get('id')
            if not doc_id: continue
                
            doc['related_docs'] = [] 
            module_id = doc.get('module_id')
            course_id = doc.get('course_id') # Assumed string from _update_local_data
            
            if module_id and course_id:
                for other_doc in self.documents:
                    if isinstance(other_doc, dict) and \
                       other_doc.get('module_id') == module_id and \
                       other_doc.get('course_id') == course_id and \
                       other_doc.get('id') != doc_id:
                        doc['related_docs'].append(other_doc.get('id'))
            
            doc_type = doc.get('type')
            if doc_type and course_id:
                for other_doc in self.documents:
                     if isinstance(other_doc, dict) and \
                        other_doc.get('type') == doc_type and \
                        other_doc.get('course_id') == course_id and \
                        other_doc.get('id') != doc_id and \
                        other_doc.get('id') not in doc.get('related_docs', []):
                         doc['related_docs'].append(other_doc.get('id'))

    async def _synchronize_chromadb_with_local_data(self):
        """Removes documents from ChromaDB that are no longer in local data."""
        try:
            chromadb_ids = await self._get_all_collection_ids()
            if not chromadb_ids: return 0
                 
            local_ids = set(self.document_map.keys())
            for course_id in self.course_map.keys(): # Add expected syllabus IDs
                 local_ids.add(f"syllabus_{course_id}")

            ids_to_remove = list(chromadb_ids - local_ids)
            
            if ids_to_remove:
                print(f"Found {len(ids_to_remove)} stale documents in ChromaDB. Removing...")
                try:
                    await asyncio.to_thread(self.collection.delete, ids=ids_to_remove)
                    print(f"Successfully removed {len(ids_to_remove)} stale documents.")
                    return len(ids_to_remove)
                except Exception as delete_error:
                     print(f"Error during ChromaDB delete operation: {delete_error}")
                     return 0 
            else:
                return 0
        except Exception as e:
            print(f"Error synchronizing ChromaDB with local data: {e}")
            return 0
        
    async def clear_collection(self) -> None:
        """Clears all documents from the ChromaDB collection."""
        collection_name_to_clear = self.collection_name
        print(f"Attempting to clear collection: {collection_name_to_clear}")
        try:
            await asyncio.to_thread(self.client.delete_collection, collection_name_to_clear)
            print(f"Successfully deleted collection: {collection_name_to_clear}")
        except Exception as e:
            print(f"Warning: Could not delete collection '{collection_name_to_clear}' (might not exist): {e}")

        try:
            self.collection = await asyncio.to_thread(
                self.client.create_collection,
                name=collection_name_to_clear,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"}
            )
            print(f"Successfully recreated collection: {collection_name_to_clear}")
        except Exception as e:
             print(f"FATAL: Failed to recreate collection '{collection_name_to_clear}': {e}")
             raise

    async def _get_all_collection_ids(self) -> set:
        """Retrieves all document IDs currently in the ChromaDB collection."""
        try:
            count = await asyncio.to_thread(self.collection.count)
            if count == 0: return set()
            results = await asyncio.to_thread(self.collection.get, include=[])
            return set(results['ids']) if results and isinstance(results.get('ids'), list) else set()
        except Exception as e:
            print(f"Error getting existing IDs from collection '{self.collection_name}': {e}")
            return set()