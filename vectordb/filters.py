import tzlocal
from datetime import datetime, timedelta
from typing import List, Dict, Any
import re
from vectordb.text_processing import normalize_text

def build_time_range_filter(search_parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
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
        
        # At the end of the function
        print("\n=== TIME RANGE FILTER DEBUG ===")
        print(f"Time range: {time_range}")
        print(f"Current timestamp: {current_timestamp} ({datetime.fromtimestamp(current_timestamp)})")
        print(f"Fields being checked: {timestamp_fields}")
        print(f"Generated conditions: {range_conditions}")
        print(f"Final filter: {[{'$or': range_conditions}] if range_conditions else []}")
        print("================================\n")
        
        return [{"$or": range_conditions}] if range_conditions else []

def build_specific_dates_filter(search_parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Build specific dates filter conditions for ChromaDB query, working with
        formatted date strings in the format "YYYY-MM-DD hh:mm AM/PM".
        
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
                specific_date = naive_date.replace(tzinfo=local_timezone)
                
                specific_dates.append(specific_date)
            except ValueError:
                print(f"Invalid date format: {date_str}, expected YYYY-MM-DD")
        
        if not specific_dates:
            return []  # No valid specific dates to filter on
        
        # Fields that contain formatted date strings
        timestamp_fields = ["due_date", "posted_date", "start_date", "updated_date"]
        date_conditions = []
        
        if len(specific_dates) == 1:
            # Single date = exact match (within day)
            specific_date = specific_dates[0]
            
            # Format the start and end times for the specific date
            start_time = specific_date.replace(hour=0, minute=0, second=0)
            end_time = specific_date.replace(hour=23, minute=59, second=59)
            
            start_time_str = start_time.strftime("%Y-%m-%d %I:%M %p")
            end_time_str = end_time.strftime("%Y-%m-%d %I:%M %p")
            
            for field in timestamp_fields:
                date_conditions.append({
                    "$and": [
                        {field: {"$gte": start_time_str}},  # Start of day (as string)
                        {field: {"$lte": end_time_str}}     # End of day (as string)
                    ]
                })

        elif len(specific_dates) >= 2:
            # Date range
            start_date = min(specific_dates)
            end_date = max(specific_dates)
            
            # Format the start and end times for the date range
            start_time = start_date.replace(hour=0, minute=0, second=0)
            end_time = end_date.replace(hour=23, minute=59, second=59)
            
            start_time_str = start_time.strftime("%Y-%m-%d %I:%M %p")
            end_time_str = end_time.strftime("%Y-%m-%d %I:%M %p")
            
            for field in timestamp_fields:
                date_conditions.append({
                    "$and": [
                        {field: {"$gte": start_time_str}},  # Start of first day (as string)
                        {field: {"$lte": end_time_str}}     # End of last day (as string)
                    ]
                })
        
        # Debug logging to verify string format
        print(f"Filtering for specific dates: {[d.strftime('%Y-%m-%d') for d in specific_dates]}")
        if len(specific_dates) == 1:
            print(f"Start time string: {start_time_str}")
            print(f"End time string: {end_time_str}")
        elif len(specific_dates) >= 2:
            print(f"Range start string: {start_time_str}")
            print(f"Range end string: {end_time_str}")
        
        # Return date condition or empty list if no valid conditions
        return [{"$or": date_conditions}] if date_conditions else []

def build_course_and_type_filter(search_parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
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
        names = {
            'file': 'display_name',
            'assignment': 'name',
            'announcement': 'title',
            'quiz': 'title',
            'event': 'title'
        }

        for doc_id, doc in document_map.items():
            if doc_id in doc_ids:  # Skip documents already found by semantic search
                continue

            doc_type = doc.get('type')
            if not doc_type or doc_type not in item_types:
                #print(f"Warning: Document {doc_id} has no type.")
                continue  # Skip documents with no type

            if doc_type == 'syllabus':
                continue

            if courses != "all_courses" and str(doc.get('course_id')) not in courses:
                #print(f"Skipping doc {doc_id} (course filter)")
                continue

            doc_name_field = names.get(doc_type)  # Use .get() to handle unknown types
            if not doc_name_field:
                #print(f"Warning: Unknown document type '{doc_type}' for doc {doc_id}")
                continue  # Skip documents with unknown types

            doc_name = doc.get(doc_name_field, '').lower()

            for keyword in keywords:
                keyword_lower = keyword.lower()

                # Direct substring match
                if keyword_lower in doc_name:
                    keyword_matches.append({'document': doc})
                    print(f"Added doc {doc_id} to keyword matches (direct match)")
                    break  # Move to the next document after a match

                # Removing file extensions
                doc_name_no_ext = re.sub(r'\.\w+$', '', doc_name)
                keyword_no_ext = re.sub(r'\.\w+$', '', keyword_lower)

                # Removing special characters
                doc_name_clean = re.sub(r'[_\-\s.]', '', doc_name_no_ext)
                keyword_clean = re.sub(r'[_\-\s.]', '', keyword_no_ext)

                # Check if any normalized version matches
                if (keyword_no_ext in doc_name_no_ext or doc_name_no_ext in keyword_no_ext or
                    keyword_clean in doc_name_clean or doc_name_clean in keyword_clean):
                    keyword_matches.append({'document': doc})
                    print(f"Added doc {doc_id} to keyword matches (normalized match)")
                    break  # Move to the next document after a match

        return keyword_matches

async def build_chromadb_query(search_parameters):
        """
        Build a ChromaDB query from search parameters.
        
        Args:
            search_parameters: Dictionary containing search parameters
            
        Returns:
            Tuple of (query_where, query_text)
        """
        # Normalize the query
        query = search_parameters["query"]
        normalized_query = normalize_text(text=query)
        
        # Build ChromaDB where clause with proper operator
        conditions = []
        
        # Add course and document type filters
        course_type_conditions = build_course_and_type_filter(search_parameters)   
        conditions.extend(course_type_conditions)
        
        # Add time range filter
        time_range_conditions = build_time_range_filter(search_parameters)
        conditions.extend(time_range_conditions)
        
        # Add specific dates filter
        specific_dates_conditions = build_specific_dates_filter(search_parameters)
        conditions.extend(specific_dates_conditions)
        
        # Apply the where clause if there are conditions
        query_where = None
        if len(conditions) == 1:
            query_where = conditions[0]  # Single condition
        elif len(conditions) > 1:
            query_where = {"$and": conditions}  # Multiple conditions combined with $and
        
        return query_where, normalized_query