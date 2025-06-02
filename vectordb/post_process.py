import tzlocal
from datetime import datetime


def post_process_results(search_results, normalized_query):
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
        doc = result["document"]
        doc_type = doc.get("type", "")

        # Get document name based on type
        if doc_type == "file":
            doc_name = doc.get("display_name", "").lower()
        elif doc_type == "assignment":
            doc_name = doc.get("name", "").lower()
        elif doc_type in ["announcement", "quiz", "event"]:
            doc_name = doc.get("title", "").lower()
        else:
            doc_name = ""

        # Check for exact match
        if doc_name == normalized_query.lower():
            result["similarity"] += 0.5  # Boost exact matches
            exact_matches.append(result)
        # Check for partial matches
        elif any(term in doc_name for term in query_terms):
            result["similarity"] += 0.2  # Boost partial matches
            partial_matches.append(result)
        else:
            other_results.append(result)

    # Combine and sort results
    combined_results = exact_matches + partial_matches + other_results
    combined_results.sort(key=lambda x: x["similarity"], reverse=True)

    return combined_results


def augment_results(course_map, search_results):
    """
    Augment search results with additional information.

    Args:
        search_results: List of search result dictionaries
    """
    local_timezone = tzlocal.get_localzone()

    for result in search_results:
        doc = result["document"]
        doc_type = doc.get("type", "")

        # Add course name
        course_id = doc.get("course_id")
        if course_id and course_id in course_map:
            # Get course name and code
            course = course_map[course_id]
            course_name, course_code = (
                course.get("name", ""),
                course.get("course_code", ""),
            )

            doc["course_name"] = course_name
            doc["course_code"] = course_code

        # Add time context
        for date_field in ["due_at", "posted_at", "start_at", "updated_at"]:
            if date_field in doc and doc[date_field]:
                try:
                    # Parse date from UTC and convert to local timezone
                    date_obj = datetime.fromisoformat(
                        doc[date_field].replace("Z", "+00:00")
                    )
                    local_date = date_obj.astimezone(local_timezone)

                    # Add localized time string
                    doc[f"local_{date_field}"] = local_date.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )

                    # Now calculate relative time using local time
                    now = datetime.now(local_timezone)

                    # Add relative time
                    delta = local_date - now
                    days = delta.days

                    if days > 0:
                        if days == 0:
                            doc["relative_time"] = "Today"
                        elif days == 1:
                            doc["relative_time"] = "Tomorrow"
                        elif days < 7:
                            doc["relative_time"] = f"In {days} days"
                    else:
                        days = abs(days)
                        if days == 0:
                            doc["relative_time"] = "Today"
                        elif days == 1:
                            doc["relative_time"] = "Yesterday"
                        elif days < 7:
                            doc["relative_time"] = f"{days} days ago"

                    break  # Only process the first date field found
                except Exception as e:
                    print(f"Error converting time: {e}")

    return search_results


<<<<<<< HEAD
=======
def bm25_score(doc, search_parameters, k1=1.5, b=0.75):
    """
    Calculate educational BM25 score for a document.

    Args:
        doc: Dictionary containing document information
        search_parameters: Dictionary containing search parameters
        k1: Term frequency saturation parameter
        b: Document length normalization parameter

    Returns:
        BM25 score
    """
    field_weights = {"title"}
    pass


>>>>>>> d8c15a0 (made code pretty with ruff linter)
def verify_doc(doc, doc_from_payload, doc_id) -> bool:
    """
    Verify that a document exists in the document_map and Qdrant.
    """
    if not doc and not doc_from_payload:
        print(f"Document not found in Qdrant or document_map for ID: {doc_id}")
        return False

    if not doc:
        print(f"Document not found in document_map for ID: {doc_id}")
        return False

    if not doc_from_payload:
        print(f"Document not found in Qdrant for ID: {doc_id}")
        return False

    return True
