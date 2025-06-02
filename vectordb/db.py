#!/usr/bin/env python3
"""
Vector Database Module for Canvas Data Orchestration
----------------------------------------------------
This module defines the `VectorDatabase` class, which serves as the primary interface
for interacting with the Qdrant vector store containing Canvas course data embeddings.
It manages the Qdrant connection, orchestrates data processing and synchronization,
and handles search requests by utilizing helper modules for specific tasks.

Key features:
1. **Qdrant Connection**: Manages the connection to the persistent Qdrant store.
2. **Data Synchronization**: Handles loading data from the source JSON, updating internal
   data structures (`document_map`, `course_map`, etc.), and synchronizing the
   Qdrant collection (upserting new/changed embeddings, deleting stale ones).
3. **Search Orchestration**: Processes search queries, builds appropriate filters
   (via `vectordb.filters`), executes Qdrant vector searches, handles keyword
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
- `vectordb.filters`: Builds Qdrant query filters and performs keyword matching.
- `vectordb.result_processor`: Post-processes and augments search results.
- `vectordb.embedding_model`: Creates the embedding function.
- `vectordb.content_extraction`: Extracts text content from files/HTML (used during processing).

Note: Ensure the source JSON data file is structured correctly.
"""

import os
import json
import sys
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dotenv import load_dotenv
import qdrant_client
from qdrant_client.http import models as qdrant_models
from datetime import datetime, timedelta, timezone
import asyncio
import uuid

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from vectordb.embedding_model import SentenceTransformerEmbeddingFunction
from vectordb.content_extraction import parse_file_content, parse_html_content
from vectordb.text_processing import (
    preprocess_text_for_embedding,
    get_course_dict,
    add_date_metadata,
)
from vectordb.filters import handle_keywords, build_qdrant_filters
from vectordb.post_process import post_process_results, augment_results, verify_doc
from vectordb.text_processing import normalize_text
from vectordb.bm25_scorer import CanvasBM25, fuse_results

load_dotenv()


class VectorDatabase:
    def __init__(
        self, json_file_path: str, cache_dir=None, collection_name: str = None
    ):
        """
        Initialize the vector database with Qdrant.

        Args:
            json_file_path: Path to the JSON file containing the documents.
            cache_dir: Directory to store Qdrant data. If None, will use the directory of the JSON file.
            collection_name: Name of the Qdrant collection. If None, will use user_id from the json file.
        """
        self.json_file_path = json_file_path
        self.client = None
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")
        self.bm25_scorer = None

        # If cache_dir is not provided, use the directory of the JSON file
        if cache_dir is None:
            self.cache_dir = os.path.dirname(json_file_path)
        else:
            # Ensure cache_dir exists for Qdrant persistence
            self.cache_dir = Path(cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load JSON file to extract user_id if collection_name is not provided
        if collection_name is None:
            try:
                with open(json_file_path, "r") as f:
                    data = json.load(f)
                user_id = data.get("user_metadata", {}).get("id", "default")
                self.collection_name = f"canvas_embeddings_{user_id}"
            except Exception as e:
                print(f"Error loading JSON file to get user_id: {e}")
                self.collection_name = "canvas_embeddings"
        else:
            self.collection_name = collection_name

        self.embedding_function = SentenceTransformerEmbeddingFunction()
        self.embedding_size = self.embedding_function.embedding_dims

        self.documents = []
        self.document_map = {}
        self.course_map = {}
        self.syllabus_map = {}

    async def connect_to_qdrant(self):
        """
        Connect to Qdrant.
        """
        self.client = qdrant_client.QdrantClient(
            url="https://2defb98f-e5e4-430a-b167-6144588cc5c2.us-east4-0.gcp.cloud.qdrant.io:6333",
            api_key=self.qdrant_api_key,
        )
        try:
            await asyncio.to_thread(
                self.client.get_collection, collection_name=self.collection_name
            )
            print(f"Using existing Qdrant collection: {self.collection_name}")
        except qdrant_client.http.exceptions.UnexpectedResponse as e:
            if e.status_code == 404:
                await asyncio.to_thread(
                    self.client.create_collection,
                    collection_name=self.collection_name,
                    vectors_config=qdrant_models.VectorParams(
                        size=self.embedding_size, distance=qdrant_models.Distance.COSINE
                    ),
                )
                print(f"Created new Qdrant collection: {self.collection_name}")
            elif e.status_code == 403:
                print(f"API Key error: {e}")
                raise
            else:
                print(f"Unexpected HTTP error: {e.status_code}")
                raise

        except Exception as e:
            print(f"Error connecting to Qdrant: {e}")
            raise

    async def process_data(self) -> bool:
        """
        Process data from JSON file and load into ChromaDB.

        Args:
            force_reload: Whether to force reload data even if cache exists.

        Returns:
            True if data was processed, False if using cached data.
        """
        if not self.client:
            print("Error: Qdrant client not initialized. Call connect_to_qdrant first.")
            return False

        try:
            with open(self.json_file_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading JSON file: {e}")
            return False

        # Extract user metadata
        user_metadata = data.get("user_metadata", {})
        print(f"Processing data for user ID: {user_metadata.get('id')}")

        # Get course dictionary
        course_dict = get_course_dict(data)
        print(course_dict)

        await self._update_local_data_structures(data)
        self.bm25_scorer = CanvasBM25(self.documents)

        # TODO: Determine if this is necessary

        # Get existing document IDs in the collection using scroll
        existing_ids = await self._get_all_collection_ids()
        print(f"Found {len(existing_ids)} existing IDs in Qdrant collection.")

        # Prepare lists for documents to add

        ids_to_add = []  # list of document IDs to add
        texts_to_embed = []  # list of texts to embed
        payloads_to_add = []  # list of metadatas to add

        # Process syllabi
        for course_id, syllabus in self.syllabus_map.items():
            # Generate a unique ID for the syllabus
            syllabus_id = f"syllabus_{course_id}"
            syllabus_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, syllabus_id))

            if syllabus_id in existing_ids:
                print(
                    f"Syllabus for course {course_id} (UUID: {syllabus_uuid}) already exists. Skipping."
                )
                continue

            # Parse the HTML content to extract plain text
            parsed_syllabus = parse_html_content(syllabus)
            if not parsed_syllabus:
                print(f"No content extracted from syllabus for course {course_id}")
                continue

            # Create a syllabus document
            syllabus_doc = {
                "id": syllabus_id,
                "type": "syllabus",
                "course_id": course_id,
                "title": f"Syllabus for {self.course_map[course_id].get('name', f'Course {course_id}')}",
                "content": parsed_syllabus,  # Use the parsed content
            }

            # Store document in memory if not already there
            if syllabus_id not in self.document_map:
                self.documents.append(syllabus_doc)
                self.document_map[syllabus_id] = syllabus_doc

            # Prepare for ChromaDB
            ids_to_add.append(syllabus_id)

            # TODO: Verify that the text is being properly processed, Cursor reccommends setting the output of preprocess_text_for_embedding to a variable, was appending to a list before
            text_to_embed = preprocess_text_for_embedding(syllabus_doc, course_dict)
            texts_to_embed.append(text_to_embed)

            # Create payload for Qdrant (metadata)
            payload = {
                "id": str(syllabus_uuid),
                "type": "syllabus",
                "course_id": course_id,
                "text_content": text_to_embed,
            }
            payloads_to_add.append(payload)
            print(f"Prepared syllabus for course {course_id} for Qdrant")

        # Process all other document types from self.documents
        for item in self.documents:
            item_id = str(item.get("id"))

            # Skip if document already exists
            if item_id in existing_ids:
                # print(f"Skipping existing document: {item_id}")
                continue

            # Skip syllabi (already handled)
            if item.get("type") == "syllabus":
                continue

            # Prepare for ChromaDB
            ids_to_add.append(item_id)

            texts_to_embed.append(preprocess_text_for_embedding(item, course_dict))

            # Debugging to see Local Due Time
            print("\n\n")
            print("Processed text for embedding for item: ", item_id)
            print(texts_to_embed[-1])
            print("\n\n")

            # Create base metadata
            metadata = {
                "id": str(item_id),
                "type": item.get("type"),
                "course_id": str(item.get("course_id", "")),
            }

            # Add module_id to metadata if it exists
            if item.get("module_id"):
                metadata["module_id"] = str(item["module_id"])

            # Handle event course_id from context_code
            if (
                item.get("type") == "event"
                and "context_code" in item
                and item["context_code"].startswith("course_")
            ):
                course_id = item["context_code"].replace("course_", "")
                item["course_id"] = course_id
                metadata["course_id"] = str(course_id)

            # Add date fields to metadata based on document type
            add_date_metadata(item, metadata)

            # Add file-specific metadata
            if item.get("type") == "file":
                metadata["folder_id"] = str(item.get("folder_id", ""))

            payloads_to_add.append(metadata)

        # If there are documents to add, generate embeddings and add to collection
        if ids_to_add:
            print(f"Processing {len(ids_to_add)} documents for collection")

            # Generate embeddings first
            # TODO: Verify that the embeddings are being properly executed
            # Currently the embedding function is being called to a list, make sure that is correct
            embeddings = self.embedding_function(texts_to_embed)
            print(f"Generated embeddings with shape: {np.array(embeddings).shape}")

            # Use upsert instead of add to avoid duplicate ID errors
            try:
                # Prepare points for Qdrant upsert
                points_to_upsert = []
                for i in range(len(ids_to_add)):
                    point_id_str = ids_to_add[i]
                    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, point_id_str))
                    point_vector = embeddings[i]
                    point_payload = payloads_to_add[i]

                    point_payload["text_content"] = texts_to_embed[i]
                    point_payload["canvas_id"] = point_id_str

                    points_to_upsert.append(
                        qdrant_models.PointStruct(
                            id=point_id, vector=point_vector, payload=point_payload
                        )
                    )

                # Perform the upsert operation using the Qdrant client
                await asyncio.to_thread(
                    self.client.upsert,
                    collection_name=self.collection_name,
                    points=points_to_upsert,
                    wait=True,  # Wait for the operation to be indexed
                )

                print(
                    f"Successfully processed {len(ids_to_add)} documents in collection {self.collection_name}"
                )
                return True
            except Exception as e:
                print(f"Error during upsert operation: {e}")
                return False
        else:
            print("No documents to process")
            return False

    """def _include_related_documents(self, search_results, search_parameters, minimum_score):
        
        Include related documents in search results.

        Args:
            search_results: List of search result dictionaries
            search_parameters: Dictionary containing search parameters
            minimum_score: Minimum similarity score to include in results
        related_docs = self._get_related_documents([r['document'].get('id') for r in search_results])
        
        # Map item types to internal types for filtering
        type_mapping = {
            "assignment": "assignment",
            "file": "file",
            "quiz": "quiz",
            "announcement": "announcement",
            "event": "event",
        }

        for doc in related_docs:
            # Apply same filters to related documents
            # Check course filter
            if (
                "course_id" in search_parameters
                and search_parameters["course_id"] != "all_courses"
            ):
                doc_course_id = str(doc.get("course_id", ""))
                if doc_course_id != str(search_parameters["course_id"]):
                    continue

            # Check item type filter
            if "item_types" in search_parameters and search_parameters["item_types"]:
                doc_type = doc.get("type", "")
                if doc_type not in [
                    type_mapping.get(t)
                    for t in search_parameters["item_types"]
                    if t in type_mapping
                ]:
                    continue

            # Only add if not already in results
            if not any(r['document'].get('id') == doc.get('id') for r in search_results):
                search_results.append({
                    'document': doc,
                    'similarity': minimum_score,
                    'is_related': True
                })"""

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
            "LOW": 3,  # Focused search
            "MEDIUM": 7,  # Balanced approach (default)
            "HIGH": 15,  # Comprehensive search
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

    async def build_qdrant_query(self, search_parameters):
        """
        Build a Qdrant query based on search parameters.
        """
        filters = await build_qdrant_filters(search_parameters)
        query_text = search_parameters.get("query", "")
        normalized_query = normalize_text(query_text)
        return filters, normalized_query

    async def _execute_qdrant_query(self, query_text, query_filter, top_k):
        """
        Execute a query against Qdrant.

        Args:
            query_text: Normalized query text
            query_where: Where clause for filtering
            top_k: Number of results to return

        Returns:
            Query results or empty dict on error
        """

        try:
            query_vector = self.embedding_function([query_text])[0]
            results = await asyncio.to_thread(
                self.client.query_points,
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
            )
            return results

            """
            Returns a JSON object that contains:
           {
                "usage": { ... },
                "time": 0.002,
                "status": "ok",
                "result": {
                    "points": [
                    {
                        "id": 42,
                        "version": 3,
                        "score": 0.75,
                        "payload": {
                        "city": "London",
                        "color": "green"
                        },
                        "vector": [...],
                        "shard_key": "region_1",
                        "order_value": 42
                    }
                ]
                }
            }
            """

        except Exception as e:
            print(f"Qdrant query error {e}")
            print(f"Query filter: {query_filter}")
            print(f"Query text: {query_text}")
            return []

    async def search(
        self,
        search_parameters,
        function_name="search",
        include_related=False,
        minimum_score=0.3,
    ):
        """
        Search for documents similar to the query.

        Args:
            search_parameters: Dictionary containing filter parameters.
            include_related: Whether to include related documents.
            minimum_score: Minimum similarity score.

        Returns:
            List of search results.
        """
        query_filter, normalized_query = await self.build_qdrant_query(
            search_parameters
        )
        top_k = self._determine_top_k(search_parameters)

        print("\n\n--------------------------------")
        print(f"Top K: {top_k}")
        print(f"Search query: '{normalized_query}'")
        print(f"Search parameters: {search_parameters}")
        print(f"Query filter: {query_filter}")
        print("--------------------------------\n\n")

        task_description = "Given a student query about course materials, retrieve relevant Canvas resources that provide comprehensive information to answer the query."
        formatted_query = f"Instruct: {task_description}\nQuery: {normalized_query}"

        # Execute ChromaDB query
        results = await self._execute_qdrant_query(formatted_query, query_filter, top_k)

        search_results = []

        # Process initial Qdrant results
        for result in results.points:
            doc_id = result.id
            score = result.score
            doc_from_payload = result.payload

            canvas_id = doc_from_payload.get("canvas_id")
            doc = self.document_map.get(canvas_id)

            if not verify_doc(doc, doc_from_payload, doc_id):
                continue

            if score < minimum_score:
                # print(f"Skipping doc {doc_id} (semantic) - low similarity: {similarity}")
                continue

            search_results.append(
                {
                    "document": doc,
                    "similarity": score,
                    "type": "semantic",  # Indicate source
                }
            )

        # --- Keyword Handling ---

        print(f"Search results")

        courses = search_parameters.get("course_id", "all_courses")
        keywords = search_parameters.get("keywords", [])

        function_type_mapping = {
            "calculate_grade": ["assignment"],
            "find_file": ["file"],
            "search": ["assignment", "file", "quiz", "announcement", "event"],
        }
        item_types = function_type_mapping.get(function_name, [])

        if keywords and self.bm25_scorer:
            keywords = " ".join(keywords)
            filtered_docs = []
            for doc in self.documents:
                doc_course_id = str(doc.get("course_id"))
                if courses != "all_courses" and doc_course_id not in courses:
                    continue
                if item_types and doc.get("type") not in item_types:
                    continue
                filtered_docs.append(doc)

            bm25_results = self.bm25_scorer.search(keywords, filtered_docs, limit=10)
            search_results = fuse_results(search_results, bm25_results, alpha=0.7)

        search_results.sort(key=lambda x: x["similarity"], reverse=True)

        for result in search_results:
            doc = result["document"]
            doc_id = doc["id"]

            print(f"Processing document: {doc_id}, Type: {result.get('type')}")

            if doc.get("type") == "file":
                try:
                    doc["content"] = await parse_file_content(doc.get("url"))
                    print(f"Extracted content for file {doc.get('display_name', '')}")
                except Exception as e:
                    print(
                        f"Failed to extract content for file {doc.get('display_name', '')}: {e}"
                    )

        combined_results = post_process_results(search_results, normalized_query)
        combined_results = augment_results(self.course_map, combined_results)

        for result_item in combined_results:
            result_item.pop("similarity", None)
            result_item.pop("related_docs", None)

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
            print(
                f"Error creating Path object from json_file_path ('{self.json_file_path}'): {e}"
            )
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
            return  # Exit early if file not found

        try:
            # --- Use the Path object to open the file ---
            with open(path_obj, "r") as f:
                data = json.load(f)
            # Populate self.documents, self.document_map, etc. using the existing internal method
            await self._update_local_data_structures(data)
            print(
                f"Successfully loaded local data structures ({len(self.document_map)} docs) from JSON."
            )
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
            if not doc or not isinstance(doc, dict):
                continue

            doc_related_ids = doc.get("related_docs", [])
            if not isinstance(doc_related_ids, list):
                continue

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
        for course in data.get("courses", []):
            course_id = str(course.get("id", ""))
            if course_id and isinstance(course, dict):
                self.course_map[course_id] = course
                syllabus_body = str(course.get("syllabus_body", ""))
                if (
                    syllabus_body
                    and syllabus_body.lower() != "none"
                    and syllabus_body.strip()
                ):
                    self.syllabus_map[course_id] = syllabus_body

        # Process Syllabus
        for course_id, syllabus in self.syllabus_map.items():
            parsed_syllabus = parse_html_content(syllabus)
            if parsed_syllabus:
                syllabus_id = f"syllabus_{course_id}"
                syllabus_doc = {
                    "id": syllabus_id,
                    "type": "syllabus",
                    "course_id": course_id,
                    "title": f"Syllabus for {self.course_map[course_id].get('name', f'Course {course_id}')}",
                    "content": parsed_syllabus,
                }
                self.documents.append(syllabus_doc)
                self.document_map[syllabus_id] = syllabus_doc
            else:
                print(
                    f"Warning: Skipping invalid syllabus for course. parse_html_content failed for course {course_id}"
                )

        # Process Document Types
        document_types_keys = {
            "files": "file",
            "announcements": "announcement",
            "assignments": "assignment",
            "quizzes": "quiz",
            "calendar_events": "event",
        }
        for collection_key, doc_type in document_types_keys.items():
            for item in data.get(collection_key, []):
                if isinstance(item, dict) and "id" in item:
                    item_id_str = str(item["id"])
                    item["type"] = doc_type  # adds type to item
                    if "course_id" in item:
                        item["course_id"] = str(item["course_id"])
                    elif doc_type == "event" and item.get(
                        "context_code", ""
                    ).startswith("course_"):
                        item["course_id"] = item["context_code"].replace("course_", "")

                    self.documents.append(item)
                    self.document_map[item_id_str] = item
                # else: print(f"Warning: Skipping invalid item in '{collection_key}': {item}") # Optional log

        self._build_document_relations()  # Call internal method
        print(
            f"Local data structures updated: {len(self.documents)} docs, {len(self.course_map)} courses."
        )

    def _build_document_relations(self):
        """Build relations between documents based on course/module."""
        # Operates on self.documents
        if not self.documents:
            return

        for doc in self.documents:
            if not isinstance(doc, dict):
                continue
            doc_id = doc.get("id")
            if not doc_id:
                continue

            doc["related_docs"] = []
            module_id = doc.get("module_id")
            course_id = doc.get("course_id")  # Assumed string from _update_local_data

            if module_id and course_id:
                for other_doc in self.documents:
                    if (
                        isinstance(other_doc, dict)
                        and other_doc.get("module_id") == module_id
                        and other_doc.get("course_id") == course_id
                        and other_doc.get("id") != doc_id
                    ):
                        doc["related_docs"].append(other_doc.get("id"))

            doc_type = doc.get("type")
            if doc_type and course_id:
                for other_doc in self.documents:
                    if (
                        isinstance(other_doc, dict)
                        and other_doc.get("type") == doc_type
                        and other_doc.get("course_id") == course_id
                        and other_doc.get("id") != doc_id
                        and other_doc.get("id") not in doc.get("related_docs", [])
                    ):
                        doc["related_docs"].append(other_doc.get("id"))

    '''
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
    '''

    async def clear_collection(self) -> None:
        """Clears all documents from the ChromaDB collection."""
        collection_name_to_clear = self.collection_name
        print(f"Attempting to clear collection: {collection_name_to_clear}")
        try:
            await asyncio.to_thread(
                self.client.delete_collection, collection_name_to_clear
            )
            print(f"Successfully deleted collection: {collection_name_to_clear}")
        except Exception as e:
            print(
                f"Warning: Could not delete collection '{collection_name_to_clear}' (might not exist): {e}"
            )

        try:
            self.collection = await asyncio.to_thread(
                self.client.create_collection,
                name=collection_name_to_clear,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"},
            )
            print(f"Successfully recreated collection: {collection_name_to_clear}")
        except Exception as e:
            print(
                f"FATAL: Failed to recreate collection '{collection_name_to_clear}': {e}"
            )
            raise

    async def _get_all_collection_ids(self) -> set:
        """Retrieves all Canvas document IDs currently in the Qdrant collection."""
        try:
            # First, check if the collection is empty or get its size.
            # The qdrant_client.count() method returns a CountResult object.
            count_result = await asyncio.to_thread(
                self.client.count, collection_name=self.collection_name
            )
            if count_result.count == 0:
                return set()

            all_canvas_ids = set()

            # Qdrant scroll returns a tuple: (points, next_offset)
            scroll_response = await asyncio.to_thread(
                self.client.scroll,
                collection_name=self.collection_name,
                with_payload=True,  # Need payload to get canvas_id
                with_vectors=False,
            )

            # Extract points from the response tuple
            points, next_offset = scroll_response

            for point in points:
                # Get the original Canvas ID from payload
                if hasattr(point, "payload") and point.payload:
                    canvas_id = point.payload.get("canvas_id")
                    if canvas_id:
                        all_canvas_ids.add(canvas_id)

            return all_canvas_ids

        except Exception as e:
            # This will catch errors like collection not found, network issues, etc.
            print(
                f"Error getting existing IDs from Qdrant collection '{self.collection_name}': {e}"
            )
            return set()
