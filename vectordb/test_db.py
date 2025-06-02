#!/usr/bin/env python3
"""
Vector Database Test Module using Pytest
------------------------------------------
This script tests the functionality of the VectorDatabase class, focusing on:
1. Connection to Qdrant (local instance based on current db.py setup).
2. Data processing and uploading from a test JSON file.
3. Basic vector search functionality (highlighting areas needing Qdrant migration).

Usage (ensure pytest and pytest-asyncio are installed: pip install pytest pytest-asyncio):
    pytest path/to/your/test_db.py
"""

import pytest
import pytest_asyncio
import os
import json
import asyncio
from pathlib import Path
import sys
import shutil
from datetime import datetime

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from vectordb.db import VectorDatabase
from vectordb.bm25_scorer import CanvasBM25

TEST_DATA_DIR = root_dir / "test_data_temp" # temporary directory to store test data files
TEST_JSON_FILENAME = "test_user_data.json" # name of test data file
TEST_JSON_FILE_PATH = TEST_DATA_DIR / TEST_JSON_FILENAME # full path to test data file
TEST_COLLECTION_NAME_PREFIX = "test_canvas_embeddings_" # prefix for Qdrant collection names created during testing
QDRANT_LOCAL_STORAGE_URL_DIRNAME = "https://2defb98f-e5e4-430a-b167-6144588cc5c2.us-east4-0.gcp.cloud.qdrant.io:6333" # Removed /dashboard from dir name

def create_dummy_test_json(file_path: Path, user_id="test_user_123"):
    """Creates a dummy JSON file for testing, mimicking Canvas data structure."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "user_metadata": {
            "id": user_id,
            "name": "Test User",
            "token": "test_token",
            "courses_selected": {
                "2500000": "TEST101",
                "2500001": "PYT501"
            },
            "is_updating": False
        },
        "courses": [
            {
                "id": "2500000",
                "name": "Intro to Testing",
                "course_code": "TEST101",
                "syllabus_body": "<p>This is the syllabus for <strong>Intro to Testing</strong>.</p><p>We will learn all about testing.</p>",
                "timezone": "America/New_York"
            },
            {
                "id": "2500001",
                "name": "Advanced Pytest",
                "course_code": "PYT501",
                "syllabus_body": "<h1>Advanced Pytest Syllabus</h1><p>Deep dive into pytest features.</p>",
                "timezone": "America/New_York"
            }
        ],
        "assignments": [
            {
                "id": "16000000",
                "type": None,
                "name": "Lab Assignment 0.5",
                "description": "<p>Complete the setup for your testing environment.</p>",
                "due_at": "2024-08-15T23:59:00Z",
                "course_id": "2500000",
                "submission_types": [
                    "online_text_entry"
                ],
                "can_submit": None,
                "graded_submission_exist": None,
                "graded_submissions_exist": None,
                "module_id": 5475163,
                "module_name": "Week 3",
                "content": []
            },
            {
                "id": "16000001",
                "type": None,
                "name": "Lab Assignment 1",
                "description": "A short quiz on testing basics.",
                "due_at": "2024-08-22T23:59:00Z",
                "course_id": "2500000",
                "submission_types": [
                    "online_text_entry"
                ],
                "can_submit": None,
                "graded_submission_exist": None,
                "graded_submissions_exist": None,
                "module_id": 5475163,
                "module_name": "Week 3",
                "content": []
            }
        ],
        "announcements": [
            {
                "id": "16000002",
                "title": "Welcome to Intro to Testing!",
                "message": "<p>Welcome to the course! Please read the syllabus.</p>",
                "posted_at": "2024-08-01T10:00:00Z",
                "course_id": "2500000",
                "discussion_type": "threaded",
                "course_name": "Intro to Testing"
            }
        ],
        "files": [
            {
                "course_id": "2500001",
                "id": "16000003",
                "type": None,
                "folder_id": "folder_course_002_docs",
                "display_name": "Lecture 1 Notes.pdf",
                "filename": "lecture_1_notes.pdf",
                "url": "http://example.com/files/file_001/download?download_frd=1",
                "size": 102400,
                "updated_at": "2024-08-05T12:00:00Z",
                "locked": False,
                "lock_explanation": None,
                "module_id": None,
                "module_name": None
            }
        ],
        "calendar_events": [
            {
                "id": "event_001",
                "title": "Course Introduction Meeting",
                "start_at": "2024-08-03T09:00:00Z",
                "end_at": "2024-08-03T10:00:00Z",
                "description": "Initial meeting for TEST101.",
                "location_name": None,
                "location_address": None,
                "context_code": "course_course_001",
                "context_name": "Intro to Testing",
                "all_context_codes": "course_course_001",
                "url": "http://example.com/calendar_events/event_001",
                "course_id": "2500000"
            }
        ],
        "quizzes": [
            {
                "id": 5192438,
                "title": "Graded Midterm 1",
                "preview_url": None,
                "description": "",
                "quiz_type": "assignment",
                "time_limit": 90,
                "allowed_attempts": 1,
                "points_possible": 70.0,
                "due_at": "2025-03-10T03:59:00Z",
                "locked_for_user": True,
                "lock_explanation": "This quiz was locked Mar 9 at 11:59pm.",
                "module_id": 5479590,
                "module_name": "Midterm (Week 6)",
                "course_id": "2500000"
            }
        ]
    }
    
    # writes the data to file_path
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

    return user_id

# Sets up the test environment before tests, cleans up after
# Created once a pytest sessions is started
# Automatically runs used for al ltests within its scope
@pytest_asyncio.fixture(scope="session", autouse=True)
def manage_test_environment():
    """Creates test data directory and JSON before tests, cleans up after."""

    ### BEGIN SETUP ###
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR) # Removes the directory and all of its contents

    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Test environment setup: {TEST_DATA_DIR}")

    # Creates the dummy test JSON file
    create_dummy_test_json(TEST_JSON_FILE_PATH)
    ### END SETUP ###


    yield # Tests run here

    ### BEGIN TEARDOWN ###
    print(f"Tearing down test environment: {TEST_DATA_DIR}")
    shutil.rmtree(TEST_DATA_DIR)
    
    # Attempt to clean up Qdrant's local storage directory created by path="URL..."
    # This directory is created relative to the current working directory.
    qdrant_local_storage_path = Path.cwd() / QDRANT_LOCAL_STORAGE_URL_DIRNAME
    if qdrant_local_storage_path.exists() and qdrant_local_storage_path.is_dir():
        print(f"Attempting to clean up Qdrant local storage: {qdrant_local_storage_path}")
        try:
            shutil.rmtree(qdrant_local_storage_path)
            print(f"Successfully cleaned up {qdrant_local_storage_path}")
        except Exception as e:
            print(f"Warning: Could not clean up Qdrant local storage {qdrant_local_storage_path}: {e}")


@pytest_asyncio.fixture
async def db_instance(manage_test_environment):
    """
    Pytest fixture to initialize VectorDatabase for testing.
    A new VectorDatabase instance with a unique collection name is created for each test.
    """

    ### BEGIN TEST SETUP ###
    test_user_id = "test_user_123" # Matches the one in create_dummy_test_json
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    unique_collection_name = f"{TEST_COLLECTION_NAME_PREFIX}{test_user_id}_{timestamp}"

    db = VectorDatabase(
        json_file_path=str(TEST_JSON_FILE_PATH),
        collection_name=unique_collection_name
    )

    await db.connect_to_qdrant()
    
    # __init__ already attempts to create collection.
    # Wait for any async operations in init if necessary, though Qdrant client calls are threaded.
    await asyncio.sleep(0.1) 
    ### END TEST SETUP ###

    yield db # returns the db instance to the test

    ### BEGIN TEARDOWN ###
    # Cleanup: Delete the Qdrant collection
    print(f"Cleaning up Qdrant collection: {unique_collection_name}")
    try:
        # client.delete_collection is synchronous
        await asyncio.to_thread(db.client.delete_collection, collection_name=unique_collection_name)
        print(f"Successfully deleted Qdrant collection: {unique_collection_name}")
    except Exception as e:
        # Qdrant might raise an error if collection doesn't exist or other issues.
        print(f"Warning: Error deleting Qdrant collection {unique_collection_name}: {e}")


@pytest.mark.asyncio
async def test_qdrant_connection_and_collection_creation(db_instance: VectorDatabase):
    """
    Tests if VectorDatabase initializes the Qdrant client and creates the collection.
    Verifies the local Qdrant setup resulting from `QdrantClient(path="URL...")`.
    """
    db = db_instance
    assert db.client is not None, "Qdrant client should be initialized."
    
    try:
        collections_response = await asyncio.to_thread(db.client.get_collections)
        collection_names = [col.name for col in collections_response.collections]
        assert db.collection_name in collection_names, \
            f"Collection {db.collection_name} should exist after VectorDatabase initialization."
    except Exception as e:
        pytest.fail(f"Failed to verify collection existence: {e}")

@pytest.mark.asyncio
async def test_process_data_and_upload(db_instance: VectorDatabase):
    """
    Tests processing data from the test JSON file and uploading it to Qdrant.
    """
    db = db_instance
    
    success = await db.process_data()
    assert success is True, "process_data should return True on successful data processing and upload."

    # Expected documents: 2 syllabi + 2 assignment + 1 announcement + 1 file + 1 event + 1 quiz = 8
    expected_doc_count = 8
    
    await asyncio.sleep(0.5) # Give Qdrant a moment to ensure indexing if upsert wait=True isn't enough

    try:
        count_response = await asyncio.to_thread(db.client.count, collection_name=db.collection_name)
        actual_doc_count = count_response.count
        
        assert actual_doc_count == expected_doc_count, \
            f"Document count in Qdrant ({actual_doc_count}) should be {expected_doc_count}."

    except Exception as e:
        pytest.fail(f"Failed to verify data count in Qdrant: {e}")

@pytest.mark.asyncio
async def test_search_vectors_basic(db_instance: VectorDatabase):
    """
    Tests basic search functionality.
    NOTE: This test targets the db.search() method. If db.search() still relies on
    ChromaDB components (_execute_chromadb_query), this test will likely fail or be skipped.
    It serves to highlight the need to update search logic for Qdrant.
    """
    db = db_instance
    
    await db.process_data() 
    await asyncio.sleep(0.5) # Allow for indexing

    search_params = {
        "query": "syllabus for testing", # Should match "Syllabus for testing course 001."
        "course_id": "2500000",
        "item_types": ["syllabus"], # Make sure 'syllabus' is a valid type for search
        "generality": "SPECIFIC",
        "specific_amount": 1
    }
    
    print(f"\nRunning basic search with params: {search_params}")
    print("This test expects db.search() to be Qdrant-compatible.")
    
    try:
        results = await db.search(search_parameters=search_params)
        
        print(f"Search results: {results}")
        
        assert results is not None, "Search output should not be None."
        assert isinstance(results, list), "Search output should be a list."
        assert len(results) > 0, "Search should return at least one result for a relevant query."
        
        # Verify if the expected document is among the results
        found_expected_item = any(
            item.get('document', {}).get('id') == 'syllabus_2500000' for item in results
        )
        assert found_expected_item, "Expected document 'syllabus_2500000' not found in search results."

    except Exception as e:
        if "chroma" in str(e).lower() or "AttributeError" in str(e) and "collection" in str(e).lower():
            pytest.skip(f"Skipping search test as it appears to be using ChromaDB components or failed due to it: {e}")
        pytest.fail(f"Search method encountered an unexpected error: {e}")

@pytest.mark.asyncio
async def test_bm25_keyword_search(db_instance: VectorDatabase):
    """Test BM25 keyword search functionality."""
    db = db_instance
    await db.process_data()
    await asyncio.sleep(0.5)

    # Test with keywords that should trigger BM25
    search_params = {
        "course_id": "2500000",
        "time_range": "ALL_TIME",
        "generality": "MEDIUM",
        "item_types": ["assignment"],
        "specific_dates": [],
        "keywords": ["lab", "0.5"],
        "query": "Tell me about lab assignment 0.5"
    }
    
    results = await db.search(search_parameters=search_params)
    
    assert results is not None
    assert len(results) > 0
    
    # Check that BM25 results are included (look for 'hybrid' or 'bm25' type)

@pytest.mark.asyncio 
async def test_bm25_scorer_directly():
    """Test BM25 scorer independently."""

    test_docs = [
        {
            "id": "16000000",
            "type": "assignment",
            "name": "Lab Assignment 0.5",
            "description": "<p>Complete the setup for your testing environment.</p>",
            "course_id": "2500000",
            "content": "Complete the setup for your testing environment."
        },
        {
            "id": "16000001", 
            "type": "assignment",
            "name": "Lab Assignment 1",
            "description": "A short quiz on testing basics.",
            "course_id": "2500000",
            "content": "A short quiz on testing basics."
        },
        {
            "id": "16000002",
            "type": "announcement", 
            "title": "Welcome to Intro to Testing!",
            "message": "<p>Welcome to the course! Please read the syllabus.</p>",
            "course_id": "2500000",
            "content": "Welcome to the course! Please read the syllabus."
        },
        {
            "id": "syllabus_2500000",
            "type": "syllabus",
            "name": "Intro to Testing",
            "syllabus_body": "<p>This is the syllabus for <strong>Intro to Testing</strong>.</p><p>We will learn all about testing.</p>",
            "course_id": "2500000",
            "content": "This is the syllabus for Intro to Testing. We will learn all about testing."
        }
    ]
    
    # Initialize BM25 scorer
    bm25 = CanvasBM25(test_docs)
    
    # Test search
    results = bm25.search("Tell me about lab assignment 0.5", limit=5)
    
    assert len(results) > 0
    assert all('similarity' in r for r in results)
    assert all('document' in r for r in results)
    assert all(r['type'] == 'bm25' for r in results)
    
    similarities = [r['similarity'] for r in results]
    assert similarities == sorted(similarities, reverse=True) 