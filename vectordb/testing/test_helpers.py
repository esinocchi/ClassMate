#!/usr/bin/env python3
"""
Test Helper Functions for Vector Database Testing
------------------------------------------------
This module contains helper functions used by the pytest test suite for
the VectorDatabase class. It includes utilities for:
- Search result evaluation and validation
- Test data setup and management
- Progress reporting and result summarization
- Search execution and result processing

These functions are separated from the main test file to improve
code organization and maintainability.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from vectordb.db import VectorDatabase


def evaluate_search_result(results: Any, query_text: str) -> Tuple[bool, str]:
    """Evaluates if a search result is successful.
    
    Args:
        results: The search results to evaluate.
        query_text: The original query text for context.
    
    Returns:
        A tuple of (success_boolean, failure_reason_string).
    """
    if results is None:
        return False, "Search returned None"
    
    if not isinstance(results, list):
        return False, f"Search returned non-list type: {type(results)}"
    
    if len(results) == 0:
        # Empty results are acceptable - search executed without error
        return True, ""
    
    # Validate result structure
    for result in results:
        if not isinstance(result, dict):
            return False, "Result item is not a dictionary"
        
        if 'document' not in result:
            return False, "Result missing 'document' field"
        
        if 'similarity' not in result and 'type' not in result:
            return False, "Result missing 'similarity' or 'type' field"
    
    return True, ""


def create_search_result_summary(
    query_index: int,
    query_text: str,
    search_params: Dict[str, Any],
    is_success: bool,
    result_count: int = 0,
    failure_reason: str = ""
) -> Dict[str, Any]:
    """Creates a standardized search result summary.
    
    Args:
        query_index: The index of the query (1-based).
        query_text: The search query text.
        search_params: The search parameters used.
        is_success: Whether the search was successful.
        result_count: Number of results returned (for successful searches).
        failure_reason: Reason for failure (for failed searches).
    
    Returns:
        A dictionary containing the search result summary.
    """
    base_summary = {
        "query_index": query_index,
        "query": query_text,
        "course_id": search_params.get("course_id", "N/A"),
        "item_types": search_params.get("item_types", [])
    }
    
    if is_success:
        base_summary.update({
            "status": "SUCCESS",
            "result_count": result_count
        })
    else:
        base_summary.update({
            "status": "FAILED" if failure_reason != "Exception" else "ERROR",
            "failure_reason": failure_reason
        })
    
    return base_summary


def print_search_progress(
    current_index: int,
    total_searches: int,
    successful_count: int
) -> None:
    """Prints search progress at regular intervals.
    
    Args:
        current_index: Current search index (0-based).
        total_searches: Total number of searches to perform.
        successful_count: Number of successful searches so far.
    """
    completed = current_index + 1
    if completed % 20 == 0:
        success_rate = (successful_count / completed) * 100
        print(f"Completed {completed}/{total_searches} searches. "
              f"Success rate: {successful_count}/{completed} ({success_rate:.1f}%)")


def print_failed_search_details(failed_results: List[Dict[str, Any]]) -> None:
    """Prints details of failed searches.
    
    Args:
        failed_results: List of failed search result summaries.
    """
    if not failed_results:
        return
    
    print(f"\n=== FAILED SEARCH DETAILS ===")
    for result in failed_results[:10]:  # Show first 10 failures
        print(f"Query {result['query_index']}: {result['query']}")
        print(f"  Status: {result['status']}")
        print(f"  Reason: {result.get('failure_reason', 'N/A')}")
        print(f"  Course: {result['course_id']}")
        print(f"  Types: {result['item_types']}")
        print()


def print_successful_search_examples(
    successful_results: List[Dict[str, Any]]
) -> None:
    """Prints examples of successful searches.
    
    Args:
        successful_results: List of successful search result summaries.
    """
    if not successful_results:
        return
    
    print(f"\n=== SUCCESSFUL SEARCH EXAMPLES ===")
    for result in successful_results[:5]:  # Show first 5 successes
        print(f"Query {result['query_index']}: {result['query']}")
        print(f"  Results found: {result['result_count']}")
        print(f"  Course: {result['course_id']}")
        print(f"  Types: {result['item_types']}")
        print()


def validate_search_diversity(
    search_results_summary: List[Dict[str, Any]]
) -> Tuple[int, int]:
    """Validates that searches covered diverse scenarios.
    
    Args:
        search_results_summary: List of all search result summaries.
    
    Returns:
        A tuple of (course_specific_count, cross_course_count).
    
    Raises:
        AssertionError: If search diversity requirements are not met.
    """
    course_specific_searches = len([
        r for r in search_results_summary 
        if r["course_id"] != "all_courses"
    ])
    cross_course_searches = len([
        r for r in search_results_summary 
        if r["course_id"] == "all_courses"
    ])
    
    assert course_specific_searches > 0, "Should have course-specific searches"
    assert cross_course_searches > 0, "Should have cross-course searches"
    
    return course_specific_searches, cross_course_searches


async def setup_extensive_test_data(
    test_data_dir: Path,
    test_collection_name_prefix: str
) -> Tuple[VectorDatabase, int]:
    """Sets up extensive test data and creates VectorDatabase instance.
    
    Args:
        test_data_dir: Directory where test data files should be created.
        test_collection_name_prefix: Prefix for the test collection name.
    
    Returns:
        A tuple of (VectorDatabase_instance, document_count).
    
    Raises:
        AssertionError: If data setup fails.
    """
    from vectordb.testing.extensive_test_data import create_extensive_test_json
    
    # Create extensive test data
    extensive_data_path = test_data_dir / "extensive_test_data.json"
    extensive_user_id = create_extensive_test_json(extensive_data_path)
    
    # Create VectorDatabase instance with correct parameters
    extensive_db = VectorDatabase(
        json_file_path=str(extensive_data_path),
        collection_name=f"{test_collection_name_prefix}extensive_{extensive_user_id}"
    )
    
    # Connect to Qdrant (required step)
    await extensive_db.connect_to_qdrant()
    
    # Process the data
    print("Processing extensive test data...")
    success = await extensive_db.process_data()
    assert success is True, "process_data should return True for extensive data processing"
    
    # Wait for indexing and verify upload
    await asyncio.sleep(2.0)
    
    count_response = await asyncio.to_thread(
        extensive_db.client.count, 
        collection_name=extensive_db.collection_name
    )
    actual_doc_count = count_response.count
    print(f"Extensive test data uploaded: {actual_doc_count} documents")
    assert actual_doc_count > 100, f"Expected >100 documents, got {actual_doc_count}"
    
    return extensive_db, actual_doc_count


async def perform_single_search(
    db: VectorDatabase,
    query_data: Dict[str, Any],
    query_index: int
) -> Dict[str, Any]:
    """Performs a single search and returns the result summary.
    
    Args:
        db: The VectorDatabase instance to search with.
        query_data: Dictionary containing search parameters.
        query_index: Index of the query (0-based).
    
    Returns:
        A dictionary containing the search result summary.
    """
    search_params = query_data["search_parameters"]
    query_text = search_params["query"]
    
    try:
        results = await db.search(search_parameters=search_params)
        is_success, failure_reason = evaluate_search_result(results, query_text)
        
        return create_search_result_summary(
            query_index=query_index + 1,
            query_text=query_text,
            search_params=search_params,
            is_success=is_success,
            result_count=len(results) if results else 0,
            failure_reason=failure_reason
        )
    
    except Exception as e:
        print(f"Search {query_index + 1} failed with exception: {e}")
        return create_search_result_summary(
            query_index=query_index + 1,
            query_text=query_text,
            search_params=search_params,
            is_success=False,
            failure_reason=f"Exception: {str(e)}"
        )


def create_dummy_test_json(file_path: Path, user_id: str = "test_user_123") -> str:
    """Creates a dummy JSON file for testing, mimicking Canvas data structure.
    
    Args:
        file_path: Path where the dummy JSON file will be created.
        user_id: User ID to be included in the dummy data.
    
    Returns:
        str: The user_id used in the dummy data.
    """
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
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

    return user_id 