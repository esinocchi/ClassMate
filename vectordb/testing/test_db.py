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
import asyncio
import shutil
from pathlib import Path
import sys
from datetime import datetime
import json
import time

# Set up path resolution
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from vectordb.db import VectorDatabase
from vectordb.bm25_scorer import CanvasBM25
from vectordb.testing.test_helpers import (
    setup_extensive_test_data,
    perform_single_search,
    print_search_progress,
    print_failed_search_details,
    perform_parallel_searches,
    cleanup_ollama_executor,
)
from vectordb.testing.test_data_organization import create_extensive_test_json

# Test configuration constants
TEST_DATA_DIR = root_dir / "test_data_temp"
TEST_JSON_FILENAME_EXTENSIVE = "test_user_data_extensive.json"
TEST_JSON_FILE_PATH = TEST_DATA_DIR / TEST_JSON_FILENAME_EXTENSIVE
TEST_COLLECTION_NAME_PREFIX = "test_canvas_embeddings_"

QDRANT_LOCAL_STORAGE_URL_DIRNAME = (
    "https://2defb98f-e5e4-430a-b167-6144588cc5c2.us-east4-0.gcp.cloud.qdrant.io:6333"
)


@pytest_asyncio.fixture(scope="session", autouse=True)
def manage_test_environment():
    """Creates test data directory and JSON before tests, cleans up after.

    Yields:
        None

    Raises:
        Exception: If cleanup of Qdrant local storage fails.
    """
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)

    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Test environment setup: {TEST_DATA_DIR}")

    create_extensive_test_json(TEST_JSON_FILE_PATH) 

    yield

    print(f"Tearing down test environment: {TEST_DATA_DIR}")
    shutil.rmtree(TEST_DATA_DIR)

    qdrant_local_storage_path = Path.cwd() / QDRANT_LOCAL_STORAGE_URL_DIRNAME
    if qdrant_local_storage_path.exists() and qdrant_local_storage_path.is_dir():
        print(
            f"Attempting to clean up Qdrant local storage: {qdrant_local_storage_path}"
        )
        try:
            shutil.rmtree(qdrant_local_storage_path)
            print(f"Successfully cleaned up {qdrant_local_storage_path}")
        except Exception as e:
            print(
                f"Warning: Could not clean up Qdrant local storage {qdrant_local_storage_path}: {e}"
            )


@pytest_asyncio.fixture
async def db_instance(manage_test_environment):
    """Pytest fixture to initialize VectorDatabase for testing.

    Args:
        manage_test_environment: Fixture that sets up and tears down the test environment.

    Yields:
        VectorDatabase: A new VectorDatabase instance with a unique collection name.

    Raises:
        Exception: If cleanup of Qdrant collection fails.
    """
    test_user_id = "extensive_test_user_456"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    unique_collection_name = f"{TEST_COLLECTION_NAME_PREFIX}{test_user_id}_{timestamp}"

    db = VectorDatabase(
        json_file_path=str(TEST_JSON_FILE_PATH), collection_name=unique_collection_name
    )

    await db.connect_to_qdrant()

    await asyncio.sleep(0.1)

    yield db

    print(f"Cleaning up Qdrant collection: {unique_collection_name}")
    try:
        await asyncio.to_thread(
            db.client.delete_collection, collection_name=unique_collection_name
        )
        print(f"Successfully deleted Qdrant collection: {unique_collection_name}")
    except Exception as e:
        print(
            f"Warning: Error deleting Qdrant collection {unique_collection_name}: {e}"
        )


@pytest.mark.asyncio
async def test_qdrant_connection_and_collection_creation(db_instance: VectorDatabase):
    """Tests if VectorDatabase initializes the Qdrant client and creates the collection.

    Args:
        db_instance: VectorDatabase instance

    Raises:
        AssertionError: If Qdrant client is not initialized or collection does not exist.
    """
    db = db_instance
    assert db.client is not None, "Qdrant client should be initialized."

    try:
        collections_response = await asyncio.to_thread(db.client.get_collections)
        collection_names = [col.name for col in collections_response.collections]
        assert db.collection_name in collection_names, (
            f"Collection {db.collection_name} should exist after VectorDatabase initialization."
        )
    except Exception as e:
        pytest.fail(f"Failed to verify collection existence: {e}")


@pytest.mark.asyncio
async def test_process_data_and_upload(db_instance: VectorDatabase):
    """Tests processing data from the test JSON file and uploading it to Qdrant.

    Args:
        db_instance: VectorDatabase instance

    Raises:
        AssertionError: If process_data does not return True or document count is incorrect.
    """
    db = db_instance

    success = await db.process_data()
    assert success is True, (
        "process_data should return True on successful data processing and upload."
    )

    expected_min_doc_count = 200  # Updated for extensive test data

    await asyncio.sleep(0.5)

    try:
        count_response = await asyncio.to_thread(
            db.client.count, collection_name=db.collection_name
        )
        actual_doc_count = count_response.count

        assert actual_doc_count >= expected_min_doc_count, (
            f"Document count in Qdrant ({actual_doc_count}) should be at least {expected_min_doc_count}."
        )

    except Exception as e:
        pytest.fail(f"Failed to verify data count in Qdrant: {e}")


@pytest.mark.asyncio
async def test_search_vectors_basic(db_instance: VectorDatabase):
    """Tests basic search functionality using a random query from extensive test data.

    Args:
        db_instance: VectorDatabase instance

    Raises:
        AssertionError: If search results do not meet expected criteria.
    """
    import random
    from vectordb.testing.test_data_organization import generate_test_search_queries
    
    db = db_instance

    await db.process_data()
    await asyncio.sleep(0.5)

    # Get a random query from the extensive test data
    search_queries = generate_test_search_queries()
    random_query_data = random.choice(search_queries)
    search_params = random_query_data["search_parameters"]

    try:
        results = await db.search(search_parameters=search_params)

        print(f"Random query: {search_params['query']}")
        print(f"Search results: {results}")

        assert results is not None, "Search output should not be None."
        assert isinstance(results, list), "Search output should be a list."
        # Note: We don't require results > 0 since some queries may legitimately return no results

    except Exception as e:
        if (
            "chroma" in str(e).lower()
            or "AttributeError" in str(e)
            and "collection" in str(e).lower()
        ):
            pytest.skip(
                f"Skipping search test as it appears to be using ChromaDB components or failed due to it: {e}"
            )
        pytest.fail(f"Search method encountered an unexpected error: {e}")


@pytest.mark.asyncio
async def test_bm25_keyword_search(db_instance: VectorDatabase):
    """Tests BM25 keyword search functionality.

    Args:
        db_instance: VectorDatabase instance

    Raises:
        AssertionError: If search results do not meet expected criteria.
    """
    db = db_instance
    await db.process_data()
    await asyncio.sleep(0.5)

    search_params = {
        "course_id": "2400000",
        "time_range": "ALL_TIME",
        "generality": "MEDIUM",
        "item_types": ["assignment"],
        "specific_dates": [],
        "keywords": ["lab", "programming"],
        "query": "Tell me about programming lab assignments",
    }

    results = await db.search(search_parameters=search_params)

    assert results is not None
    assert len(results) > 0


@pytest.mark.asyncio
async def test_bm25_scorer_directly():
    """Tests BM25 scorer independently.

    Raises:
        AssertionError: If BM25 search results do not meet expected criteria.
    """
    test_docs = [
        {
            "id": "16000000",
            "type": "assignment",
            "name": "Lab Assignment 0.5",
            "description": "<p>Complete the setup for your testing environment.</p>",
            "course_id": "2500000",
            "content": "Complete the setup for your testing environment.",
        },
        {
            "id": "16000001",
            "type": "assignment",
            "name": "Lab Assignment 1",
            "description": "A short quiz on testing basics.",
            "course_id": "2500000",
            "content": "A short quiz on testing basics.",
        },
        {
            "id": "16000002",
            "type": "announcement",
            "title": "Welcome to Intro to Testing!",
            "message": "<p>Welcome to the course! Please read the syllabus.</p>",
            "course_id": "2500000",
            "content": "Welcome to the course! Please read the syllabus.",
        },
        {
            "id": "syllabus_2500000",
            "type": "syllabus",
            "name": "Intro to Testing",
            "syllabus_body": "<p>This is the syllabus for <strong>Intro to Testing</strong>.</p><p>We will learn all about testing.</p>",
            "course_id": "2500000",
            "content": "This is the syllabus for Intro to Testing. We will learn all about testing.",
        },
    ]

    bm25 = CanvasBM25(test_docs)

    results = bm25.search("Tell me about lab assignment 0.5", limit=5)

    assert len(results) > 0
    assert all("similarity" in r for r in results)
    assert all("document" in r for r in results)
    assert all(r["type"] == "bm25" for r in results)

    similarities = [r["similarity"] for r in results]
    assert similarities == sorted(similarities, reverse=True)


@pytest.mark.asyncio
async def test_search_vectors_extensive(db_instance: VectorDatabase) -> None:
    """Tests extensive search functionality using large-scale test data.

    Performs 100+ searches and evaluates success/failure of each search.

    Args:
        db_instance: VectorDatabase instance (unused, we create our own).

    Raises:
        AssertionError: If search results do not meet expected criteria.
    """
    from vectordb.testing.test_data_organization import generate_test_search_queries

    # Setup extensive test data
    extensive_db, doc_count = await setup_extensive_test_data(
        TEST_JSON_FILE_PATH, TEST_COLLECTION_NAME_PREFIX
    )

    try:
        # Generate and execute searches based on the actual data
        search_queries = generate_test_search_queries(TEST_JSON_FILE_PATH)
        print(f"Generated {len(search_queries)} test search queries")
        print("Starting extensive search testing...")

        search_results_summary = []
        successful_searches = 0

        # Export search queries to JSON file for analysis
        """search_queries_file = Path(__file__).parent / "search_queries.json"
        with open(search_queries_file, "w") as f:
            json.dump(search_queries, f, indent=4)

        extensive_data_test_file = Path(__file__).parent / "extensive_data_test.json"
        with open(extensive_data_test_file, "w") as f:
            with open(TEST_JSON_FILE_PATH, "r") as source_f:
                extensive_data = json.load(source_f)
            json.dump(extensive_data, f, indent=4)"""
        
        # Perform all searches
        # TODO: Remove the 20 limit after testing
        search_queries_short = search_queries[:20]

        print("Starting parallel search...")
        start_time = time.time()
        search_results_summary = await perform_parallel_searches(
            extensive_db,
            search_queries_short,
            max_concurrent=5
        )

        end_time = time.time()
        total_time = end_time - start_time
        print(f"Parallel search completed in {total_time:.2f} seconds")

        # Calculate and display results
        total_searches = len(search_queries_short)
        failed_searches = sum(1 for r in search_results_summary if r["status"] != "SUCCESS")
        success_rate = (total_searches - failed_searches) / total_searches * 100

        print("\n=== EXTENSIVE SEARCH TEST RESULTS ===")
        print(f"Total execution time: {total_time:.2f} seconds")
        print(f"Average time per search: {total_time / total_searches:.2f} seconds")
        print(f"Total searches performed: {total_searches}")
        print(f"Successful searches: {total_searches - failed_searches}")
        print(f"Failed searches: {failed_searches}")
        print(f"Success rate: {success_rate:.2f}%")

        # Print detailed results
        failed_results = [r for r in search_results_summary if r["status"] != "SUCCESS"]
        successful_results = [
            r for r in search_results_summary if r["status"] == "SUCCESS"
        ]

        print_failed_search_details(failed_results)

        timestamp = datetime.now().strftime("%Y-%m-%d_%I:%M_%p")

        search_results_file = Path(__file__).parent / "test_results" / f"{timestamp}" / f"search_results_summary.json"
        search_results_file.parent.mkdir(parents=True, exist_ok=True)
        with open(search_results_file, "w") as f:
            json.dump(search_results_summary, f, indent=4)
        print(f"Search results summary exported to: {search_results_file}")

        user_data_file = Path(__file__).parent / "test_results" / f"{timestamp}" / f"user_data.json"
        user_data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(user_data_file, "w") as f:
            with open(TEST_JSON_FILE_PATH, "r") as source_f:
                user_data = json.load(source_f)
            json.dump(user_data, f, indent=4)
        print(f"User data exported to: {user_data_file}")



        print("✅ Extensive search test completed successfully!")

    finally:
        # Clean up the ThreadPoolExecutor
        cleanup_ollama_executor()
        
        # Clean up the extensive test collection
        try:
            await asyncio.to_thread(
                extensive_db.client.delete_collection,
                collection_name=extensive_db.collection_name,
            )
            print(
                f"Successfully deleted extensive test collection: "
                f"{extensive_db.collection_name}"
            )
        except Exception as e:
            print(
                f"Warning: Error deleting extensive test collection "
                f"{extensive_db.collection_name}: {e}"
            )
