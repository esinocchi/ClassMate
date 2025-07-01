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
import os
import ollama
import time
from concurrent.futures import ThreadPoolExecutor

from vectordb.db import VectorDatabase

# Global thread pool for Ollama calls - enables true multi-threading
_ollama_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="ollama-eval")

def _sync_ollama_evaluation(results: Any, query_text: str) -> bool:
    """Synchronous Ollama evaluation function that runs in a separate thread.
    
    This function will be executed in the ThreadPoolExecutor, allowing
    multiple Ollama API calls to run simultaneously in different threads.
    
    Args:
        results: The search results to evaluate.
        query_text: The original query text for context.
        
    Returns:
        bool: True if the search result is successful, False otherwise.
    """
    system_context = """You are a precise document relevance evaluator for a Canvas Learning Management System. Your role is to assess whether vector database search results appropriately match student queries about their course materials.

    Your task: Determine if the provided document(s) results meaningfully addresses the user's query about their Canvas LMS data (courses, assignments, files, announcements, etc.).

    Output format CRITICAL: Respond with exactly "True" or "False" - no additional text.

    Evaluation criteria for "True":
    - The results directly answers the query with specific, relevant information
    - The results contain course materials, assignments, or announcements that relate to the query topic
    - The results provide useful context that would help the student with their query
    - The semantic meaning aligns with what the student is seeking

    Examples of "True" results:
    - Query: "What assignments are due this week?" → Results: List of assignments with due dates in the current week
    - Query: "Show me the syllabus for CMPSC 221" → Results: Syllabus document for CMPSC 221 course
    - Query: "What are the requirements for the final project?" → Results: Assignment details describing final project requirements
    - Query: "When is the midterm exam?" → Results: Calendar event or announcement about midterm exam date

    Evaluation criteria for "False":
    - The results contain no information related to the query topic
    - The results are from an unrelated course or completely off-topic
    - The results are corrupted, empty, or contains only metadata without useful content
    - The information does not provide any value for answering the student's question

    Examples of "False" results:
    - Query: "What assignments are due this week?" → Results: Syllabus from a course with no assignment information
    - Query: "Show me the syllabus for CMPSC 221" → Results: Assignment from CMPSC 221 course
    - Query: "What are the requirements for the final project?" → Results: Empty document or corrupted content
    - Query: "When is the midterm exam?" → Results: Unrelated announcement about course registration

    Think step-by-step:
    1. What is the student asking for?
    2. What information does the results contain?
    3. Does the results meaningfully address the query?"""

    user_prompt = f"""<query>
    {query_text}
    </query>

    <search_result>
    {results}
    </search_result>

    Evaluate if this search result matches the query."""

    try:
        # This is the actual blocking Ollama call that runs in a separate thread
        response = ollama.chat(
            model="phi4-mini",
            messages=[
                {"role": "system", "content": system_context},
                {"role": "user", "content": user_prompt}
            ],
            options={
                "temperature": 0.0,
                "num_predict": 10,
                "stop": ["\n", ".", "!"]
            }
        )
        
        output = response['message']['content'].strip().lower()
        
        if "true" in output:
            return True
        elif "false" in output:
            return False
        else:
            print(f"Error: Invalid output from Ollama: {output}")
            return False
            
    except Exception as e:
        print(f"Error calling Ollama: {e}")
        return False


async def evaluate_search_result(results: Any, query_text: str) -> bool:
    """Evaluates if a search result is successful using ThreadPoolExecutor.
    
    This function uses a ThreadPoolExecutor to run Ollama calls in separate threads,
    enabling true parallelism for I/O-bound operations.

    Args:
        results: The search results to evaluate.
        query_text: The original query text for context.

    Returns:
        bool: True if the search result is successful, False otherwise.
    """
    # Run the blocking Ollama call in a separate thread
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_ollama_executor, _sync_ollama_evaluation, results, query_text)


def create_search_result_summary(
    query_index: int,
    query_text: str,
    search_params: Dict[str, Any],
    is_success: bool,
    result_count: int = 0,
    failure_reason: str = "",
    results: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Creates a standardized search result summary.

    Args:
        query_index: The index of the query (1-based).
        query_text: The search query text.
        search_params: The search parameters used.
        is_success: Whether the search was successful.
        result_count: Number of results returned (for successful searches).
        failure_reason: Reason for failure (for failed searches, exceptions only).
        results: The search results (for successful searches).
    Returns:
        A dictionary containing the search result summary.
    """
    base_summary = {
        "query_index": query_index,
        "query": query_text,
        "course_id": search_params.get("course_id", "N/A"),
        "item_types": search_params.get("item_types", []),
    }

    if is_success:
        base_summary.update({"status": "SUCCESS", "result_count": result_count})
        if results:
            base_summary["results"] = results
    else:
        status = "ERROR" if failure_reason.startswith("Exception:") else "FAILED"
        base_summary.update({"status": status})
        if failure_reason:  # Only add failure_reason if it exists (for exceptions)
            base_summary["failure_reason"] = failure_reason

    return base_summary


def print_search_progress(
    current_index: int, total_searches: int, successful_count: int
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
        print(
            f"Completed {completed}/{total_searches} searches. "
            f"Success rate: {successful_count}/{completed} ({success_rate:.1f}%)"
        )


def print_failed_search_details(failed_results: List[Dict[str, Any]]) -> None:
    """Prints details of failed searches.

    Args:
        failed_results: List of failed search result summaries.
    """
    if not failed_results:
        return

    print("\n=== FAILED SEARCH DETAILS ===")
    for result in failed_results[:10]:  # Show first 10 failures
        print(f"Query {result['query_index']}: {result['query']}")
        print(f"  Status: {result['status']}")
        print(f"  Reason: {result.get('failure_reason', 'N/A')}")
        print(f"  Course: {result['course_id']}")
        print(f"  Types: {result['item_types']}")
        print()


def print_successful_search_examples(successful_results: List[Dict[str, Any]]) -> None:
    """Prints examples of successful searches.

    Args:
        successful_results: List of successful search result summaries.
    """
    if not successful_results:
        return

    print("\n=== SUCCESSFUL SEARCH EXAMPLES ===")
    for result in successful_results[:5]:  # Show first 5 successes
        print(f"Query {result['query_index']}: {result['query']}")
        print(f"  Results found: {result['result_count']}")
        print(f"  Course: {result['course_id']}")
        print(f"  Types: {result['item_types']}")
        print()


def validate_search_diversity(
    search_results_summary: List[Dict[str, Any]],
) -> Tuple[int, int]:
    """Validates that searches covered diverse scenarios.

    Args:
        search_results_summary: List of all search result summaries.

    Returns:
        A tuple of (course_specific_count, cross_course_count).

    Raises:
        AssertionError: If search diversity requirements are not met.
    """
    course_specific_searches = len(
        [r for r in search_results_summary if r["course_id"] != "all_courses"]
    )
    cross_course_searches = len(
        [r for r in search_results_summary if r["course_id"] == "all_courses"]
    )

    assert course_specific_searches > 0, "Should have course-specific searches"
    assert cross_course_searches > 0, "Should have cross-course searches"

    return course_specific_searches, cross_course_searches


async def setup_extensive_test_data(
    extensive_data_path: Path, test_collection_name_prefix: str
) -> Tuple[VectorDatabase, int]:
    """Sets up extensive test data and creates VectorDatabase instance.

    Args:
        extensive_data_path: Path to the extensive test data JSON file.
        test_collection_name_prefix: Prefix for the test collection name.

    Returns:
        A tuple of (VectorDatabase_instance, document_count).

    Raises:
        AssertionError: If data setup fails.
    """
    # Read user_id from the pre-existing JSON file
    with open(extensive_data_path, "r") as f:
        data = json.load(f)
    extensive_user_id = data["user_metadata"]["id"]

    # Create VectorDatabase instance with correct parameters
    extensive_db = VectorDatabase(
        json_file_path=str(extensive_data_path),
        collection_name=f"{test_collection_name_prefix}extensive_{extensive_user_id}",
    )

    # Connect to Qdrant (required step)
    await extensive_db.connect_to_qdrant()

    # Process the data
    print("Processing extensive test data...")
    success = await extensive_db.process_data()
    assert success is True, (
        "process_data should return True for extensive data processing"
    )

    # Wait for indexing and verify upload
    await asyncio.sleep(2.0)

    count_response = await asyncio.to_thread(
        extensive_db.client.count, collection_name=extensive_db.collection_name
    )
    actual_doc_count = count_response.count
    print(f"Extensive test data uploaded: {actual_doc_count} documents")
    assert actual_doc_count > 100, f"Expected >100 documents, got {actual_doc_count}"

    return extensive_db, actual_doc_count


async def perform_single_search(
    db: VectorDatabase, query_data: Dict[str, Any], query_index: int
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
        is_success = await evaluate_search_result(results, query_text)

        return create_search_result_summary(
            query_index=query_index + 1,
            query_text=query_text,
            search_params=search_params,
            is_success=is_success,
            result_count=len(results) if results else 0,
            results=results,
        )

    except Exception as e:
        print(f"Search {query_index + 1} failed with exception: {e}")
        return create_search_result_summary(
            query_index=query_index + 1,
            query_text=query_text,
            search_params=search_params,
            is_success=False,
            failure_reason=f"Exception: {str(e)}",
        )


def create_simple_user_data(file_path: Path, user_id: str = "test_user_123") -> str:
    """Creates a simple JSON file for testing, mimicking Canvas data structure.

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
            "courses_selected": {"2500000": "TEST101", "2500001": "PYT501"},
            "is_updating": False,
        },
        "courses": [
            {
                "id": "2500000",
                "name": "Intro to Testing",
                "course_code": "TEST101",
                "syllabus_body": "<p>This is the syllabus for <strong>Intro to Testing</strong>.</p><p>We will learn all about testing.</p>",
                "timezone": "America/New_York",
            },
            {
                "id": "2500001",
                "name": "Advanced Pytest",
                "course_code": "PYT501",
                "syllabus_body": "<h1>Advanced Pytest Syllabus</h1><p>Deep dive into pytest features.</p>",
                "timezone": "America/New_York",
            },
        ],
        "assignments": [
            {
                "id": "16000000",
                "type": None,
                "name": "Lab Assignment 0.5",
                "description": "<p>Complete the setup for your testing environment.</p>",
                "due_at": "2024-08-15T23:59:00Z",
                "course_id": "2500000",
                "submission_types": ["online_text_entry"],
                "can_submit": None,
                "graded_submission_exist": None,
                "graded_submissions_exist": None,
                "module_id": 5475163,
                "module_name": "Week 3",
                "content": [],
            },
            {
                "id": "16000001",
                "type": None,
                "name": "Lab Assignment 1",
                "description": "A short quiz on testing basics.",
                "due_at": "2024-08-22T23:59:00Z",
                "course_id": "2500000",
                "submission_types": ["online_text_entry"],
                "can_submit": None,
                "graded_submission_exist": None,
                "graded_submissions_exist": None,
                "module_id": 5475163,
                "module_name": "Week 3",
                "content": [],
            },
        ],
        "announcements": [
            {
                "id": "16000002",
                "title": "Welcome to Intro to Testing!",
                "message": "<p>Welcome to the course! Please read the syllabus.</p>",
                "posted_at": "2024-08-01T10:00:00Z",
                "course_id": "2500000",
                "discussion_type": "threaded",
                "course_name": "Intro to Testing",
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
                "module_name": None,
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
                "course_id": "2500000",
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
                "course_id": "2500000",
            }
        ],
    }

    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

    return user_id

async def perform_parallel_searches(
    db: VectorDatabase, 
    search_queries: List[Dict[str, Any]], 
    max_concurrent: int = 5
) -> List[Dict[str, Any]]:
    """
    Perform multiple searches in parallel with concurrency control.
    
    Args:
        db: VectorDatabase instance
        search_queries: List of search query dictionaries
        max_concurrent: Maximum number of concurrent operations
        
    Returns:
        List of search result summaries
    """
    
    # Create semaphore to limit concurrent operations
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def bounded_search(query_data: Dict[str, Any], index: int) -> Dict[str, Any]:
        """Wrapper that respects concurrency limits."""
        async with semaphore:
            print(f"Starting search {index + 1}/{len(search_queries)}: {query_data['search_parameters']['query'][:50]}...")
            result = await perform_single_search(db, query_data, index)
            print(f"Completed search {index + 1}/{len(search_queries)}")
            return result
    
    # Create all tasks
    tasks = [
        bounded_search(query_data, i) 
        for i, query_data in enumerate(search_queries)
    ]
    
    print(f"Starting {len(tasks)} searches with max {max_concurrent} concurrent operations...")
    start_time = time.time()
    
    # Execute all tasks in parallel (but respecting semaphore limit)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    end_time = time.time()
    print(f"All searches completed in {end_time - start_time:.2f} seconds")
    
    # Handle any exceptions
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Search {i + 1} failed with exception: {result}")
            # Create a failed result summary
            query_data = search_queries[i]
            failed_result = create_search_result_summary(
                query_index=i + 1,
                query_text=query_data["search_parameters"]["query"],
                search_params=query_data["search_parameters"],
                is_success=False,
                failure_reason=f"Exception: {str(result)}",
            )
            processed_results.append(failed_result)
        else:
            processed_results.append(result)
    
    return processed_results

def cleanup_ollama_executor():
    """Cleanup function to properly shutdown the ThreadPoolExecutor.
    
    Call this at the end of your test runs to ensure all threads are properly closed.
    """
    global _ollama_executor
    if _ollama_executor:
        _ollama_executor.shutdown(wait=True)
        print("✅ Ollama ThreadPoolExecutor cleaned up successfully")
