import tzlocal
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import re
from vectordb.text_processing import normalize_text
from qdrant_client import models as qdrant_models


def build_time_range_filter(
    search_parameters: Dict[str, Any],
) -> Optional[qdrant_models.Filter]:
    """
    Build time range filter conditions for ChromaDB query.

    Args:
        search_parameters: Dictionary containing search parameters

    Returns:
        List of time range filter conditions to be added to the main where clause
    """
    if (
        not search_parameters
        or "time_range" not in search_parameters
        or not search_parameters["time_range"]
    ):
        return None

    time_range = search_parameters["time_range"]
    if time_range == "ALL_TIME":
        return None

    # Get current time in local timezone, then convert to UTC for timestamp comparison
    local_timezone = tzlocal.get_localzone()
    current_time = datetime.now(local_timezone)
    current_timestamp = int(current_time.timestamp())

    # List of all possible timestamp fields across different document types
    timestamp_fields = [
        "due_timestamp",
        "posted_timestamp",
        "start_timestamp",
        "updated_timestamp",
    ]

    field_conditions = []

    future_10d = current_time + timedelta(days=10)
    future_10d_timestamp = int(future_10d.timestamp())

    past_10d = current_time - timedelta(days=10)
    past_10d_timestamp = int(past_10d.timestamp())

    if time_range == "NEAR_FUTURE":
        target_range = qdrant_models.Range(
            gte=current_timestamp, lte=future_10d_timestamp
        )

    elif time_range == "FUTURE":
        target_range = qdrant_models.Range(gte=future_10d_timestamp)

    elif time_range == "RECENT_PAST":
        target_range = qdrant_models.Range(
            lte=current_timestamp, gte=past_10d_timestamp
        )

    elif time_range == "PAST":
        target_range = qdrant_models.Range(lte=past_10d_timestamp)

    if target_range:
        for field in timestamp_fields:
            field_conditions.append(
                qdrant_models.FieldCondition(key=field, range=target_range)
            )

    # field_conditions is a list of FieldCondition objects for each timestamp field (e.g. due_timestamp, posted_timestamp, etc.)
    # each assignment type has a different timestamp field, so we need to check each one
    # "should" instead of "must" because we want to include documents that match one of the conditions
    return qdrant_models.Filter(should=field_conditions) if field_conditions else None


def build_specific_dates_filter(
    search_parameters: Dict[str, Any],
) -> Optional[qdrant_models.Filter]:
    """
    Build specific dates filter conditions for ChromaDB query, working with
    formatted date strings in the format "YYYY-MM-DD hh:mm AM/PM".

    Args:
        search_parameters: Dictionary containing search parameters

    Returns:
        List of specific dates filter conditions to be added to the main where clause
    """
    if (
        not search_parameters
        or "specific_dates" not in search_parameters
        or not search_parameters["specific_dates"]
    ):
        return None

    local_timezone = tzlocal.get_localzone()
    specific_dates = []

    for date_str in search_parameters["specific_dates"]:
        try:
            naive_date = datetime.strptime(date_str, "%Y-%m-%d")
            specific_date = naive_date.replace(tzinfo=local_timezone)
            specific_dates.append(specific_date)
        except ValueError:
            print(f"Invalid date format: {date_str}, expected YYYY-MM-DD")
    if not specific_dates:
        return None

    # Fields that contain formatted date strings
    timestamp_fields = [
        "due_timestamp",
        "posted_timestamp",
        "start_timestamp",
        "updated_timestamp",
    ]
    field_conditions = []

    if len(specific_dates) == 1:
        # Single date = exact match (within day)
        specific_date = specific_dates[0]

        # Format the start and end times for the specific date
        start_time = specific_date.replace(hour=0, minute=0, second=0)
        end_time = specific_date.replace(hour=23, minute=59, second=59)
        start_timestamp = int(start_time.timestamp())
        end_timestamp = int(end_time.timestamp())

    elif len(specific_dates) >= 2:
        # Date range = range match (within day)
        start_date = min(specific_dates)
        end_date = max(specific_dates)

        start_time = start_date.replace(hour=0, minute=0, second=0)
        end_time = end_date.replace(hour=23, minute=59, second=59)

        start_timestamp = int(start_time.timestamp())
        end_timestamp = int(end_time.timestamp())

    target_range = qdrant_models.Range(gte=start_timestamp, lte=end_timestamp)

    for field in timestamp_fields:
        field_conditions.append(
            qdrant_models.FieldCondition(key=field, range=target_range)
        )

    return qdrant_models.Filter(should=field_conditions) if field_conditions else None


def build_course_and_type_filter(
    search_parameters: Dict[str, Any],
) -> List[Dict[str, Any]]:
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
            course_condition = qdrant_models.FieldCondition(
                key="course_id", match=qdrant_models.MatchValue(value=str(course_id))
            )
            conditions.append(course_condition)

    # Add document type filter
    if "item_types" in search_parameters:
        item_types = search_parameters["item_types"]
        if item_types and isinstance(item_types, list) and len(item_types) > 0:
            type_condition = qdrant_models.FieldCondition(
                key="type", match=qdrant_models.MatchAny(any=item_types)
            )
            conditions.append(type_condition)

    return conditions


def handle_keywords(document_map, keywords, doc_ids, courses, item_types):
    """
    Handle keyword search by checking if any keyword matches or is very similar to any document name.

    Args:
        keywords: List of keywords to search for
        doc_ids: List of doc_ids already found by semantic search (to avoid duplicates)
        courses: List of courses to filter by
    """

    if isinstance(courses, str) or isinstance(courses, int):
        courses = [courses]

    keyword_matches = []
    title_field_mapping = {
        "file": "display_name",
        "assignment": "name",
        "announcement": "title",
        "quiz": "title",
        "event": "title",
    }

    for doc_id, doc in document_map.items():
        if doc_id in doc_ids:  # Skip documents already found by semantic search
            continue

        doc_type = doc.get("type")
        if not doc_type or doc_type not in item_types:
            # print(f"Warning: Document {doc_id} has no type.")
            continue  # Skip documents with no type

        if doc_type == "syllabus":
            continue

        if courses != "all_courses" and str(doc.get("course_id")) not in courses:
            # print(f"Skipping doc {doc_id} (course filter)")
            continue

        doc_name_field = title_field_mapping.get(
            doc_type
        )  # Use .get() to handle unknown types
        if not doc_name_field:
            # print(f"Warning: Unknown document type '{doc_type}' for doc {doc_id}")
            continue  # Skip documents with unknown types

        doc_name = doc.get(doc_name_field, "").lower()

        for keyword in keywords:
            keyword_lower = keyword.lower()

            # Direct substring match
            if keyword_lower in doc_name:
                keyword_matches.append({"document": doc})
                print(f"Added doc {doc_id} to keyword matches (direct match)")
                break  # Move to the next document after a match

            # Removing file extensions
            doc_name_no_ext = re.sub(r"\.\w+$", "", doc_name)
            keyword_no_ext = re.sub(r"\.\w+$", "", keyword_lower)

            # Removing special characters
            doc_name_clean = re.sub(r"[_\-\s.]", "", doc_name_no_ext)
            keyword_clean = re.sub(r"[_\-\s.]", "", keyword_no_ext)

            # Check if any normalized version matches
            if (
                keyword_no_ext in doc_name_no_ext
                or doc_name_no_ext in keyword_no_ext
                or keyword_clean in doc_name_clean
                or doc_name_clean in keyword_clean
            ):
                keyword_matches.append({"document": doc})
                print(f"Added doc {doc_id} to keyword matches (normalized match)")
                break  # Move to the next document after a match

    return keyword_matches


async def build_qdrant_filters(
    search_parameters: Dict[str, Any],
) -> Optional[qdrant_models.Filter]:
    """
    Build a Qdrant query from search parameters.

    Args:
        search_parameters: Dictionary containing search parameters

    Returns:
        Tuple of (query_where, query_text)
    """
    # Normalize the query
    query = search_parameters.get("query", "")
    normalized_query = normalize_text(text=query)

    search_parameters["_normalized_query"] = normalized_query

    must_conditions = []
    should_conditions = []
    # Add course and document type filters
    course_type_conditions = build_course_and_type_filter(search_parameters)
    must_conditions.extend(course_type_conditions)

    specific_dates_filter = build_specific_dates_filter(search_parameters)
    if specific_dates_filter:
        must_conditions.append(specific_dates_filter)
    else:
        time_range_filter = build_time_range_filter(search_parameters)
        if time_range_filter:
            must_conditions.append(time_range_filter)

    keywords = search_parameters.get("keywords", [])
    if keywords and isinstance(keywords, list) and len(keywords) > 0:
        for keyword in keywords:
            if isinstance(keyword, str) and keyword.strip():
                keyword_condition = qdrant_models.FieldCondition(
                    key="text_content", match=qdrant_models.MatchText(text=keyword)
                )
                should_conditions.append(keyword_condition)

    if not must_conditions and not should_conditions:
        return None

    final_filter = qdrant_models.Filter(
        must=must_conditions if must_conditions else None,
        should=should_conditions if should_conditions else None,
    )

    return final_filter
