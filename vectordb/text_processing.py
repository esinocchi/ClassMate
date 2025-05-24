from datetime import datetime, timezone
from typing import Dict, Any
import tzlocal
import re


def get_course_dict(data):
    '''
    Get dictionary of course_id to course_name
    '''
    course_dict = {}
    for course_id in data['user_metadata']['courses_selected']:
        course_dict[course_id] = data['user_metadata']['courses_selected'][course_id]
        print(course_dict[course_id])
    return course_dict

def add_local_times_to_doc(doc: Dict[str, Any]) -> None:
    """
    Adds formatted local time strings directly to the doc dictionary.
    Modifies the input dictionary in-place.
    """
    time_mapping = {
        'due_at': 'local_due_time',
        'start_at': 'local_start_time',
        'end_at': 'local_end_time',
        'posted_at': 'local_posted_time', # Add other relevant fields
        'updated_at': 'local_updated_time'
    }
    local_tz = tzlocal.get_localzone()

    for source_field, target_field in time_mapping.items():
        if doc.get(source_field):
            try:
                # Assuming UTC 'Z' format - adjust if needed
                utc_dt = datetime.fromisoformat(doc[source_field].replace('Z', '+00:00'))
                local_dt = utc_dt.astimezone(local_tz)
                # Store the formatted string in the doc
                doc[target_field] = local_dt.strftime('%Y-%m-%d %I:%M %p %Z')
            except (ValueError, TypeError, AttributeError) as e:
                print(f"Warning: Could not parse or convert time for {source_field} in doc {doc.get('id')}: {e}")
                doc[target_field] = None # Or keep original, or add error string


def preprocess_text_for_embedding(doc: Dict[str, Any], course_dict: Dict[str, str]) -> str:
    """
    Prepares the document dictionary and converts it to natural language
    using the to_natural_language function for embedding.

    Args:
        doc: Singular Item dictionary from user_data.
        course_dict: Dictionary mapping course_id to course_name.

    Returns:
        Natural language text string for embedding, or None if conversion fails.
    """
    if not isinstance(doc, dict):
        print(f"Warning: Invalid document format received: {type(doc)}")
        return None # Return None for invalid input

    # Make a copy to avoid modifying the original dict if it's used elsewhere
    modified_doc = doc.copy()

    # 1. Inject Course Name
    course_id = str(modified_doc.get('course_id', '')) # Ensure course_id is string
    if course_id and course_id in course_dict:
        modified_doc['course_name'] = course_dict[course_id]
    else:
        modified_doc['course_name'] = 'Unknown Course' # Default if not found

    # 2. Inject Local Times (using the modified function)
    add_local_times_to_doc(modified_doc)

    # 3. Call the natural language conversion function
    try:
        natural_language_output = to_natural_language(modified_doc)
        # Optional: Add a check if the output is empty or just "passage: "
        if not natural_language_output or natural_language_output.strip() == "passage:":
             print(f"Warning: to_natural_language produced empty output for doc ID: {modified_doc.get('id')}")
             # Decide how to handle: return empty string, None, or a default message
             return ""
        return natural_language_output
    except Exception as e:
        print(f"Error during to_natural_language conversion for doc ID {modified_doc.get('id')}: {e}")
        # Decide how to handle: return empty string, None, or a default message
        return None # Return None on error to be caught in db.py

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

def add_local_time(doc: Dict[str, Any]) -> Dict[str, Any]:
    '''
    Add local time to doc
    '''
    time_attributes = ['due_at', 'start_at', 'end_at']
    time_attributes_str = {
            'due_at': 'Local Due Time',
            'start_at': 'Local Start Time',
            'end_at': 'Local End Time'
        }
    
    for attribute in time_attributes:
        if doc.get(attribute):
            # Convert due_at (assumed to be in UTC) to local time (e.g., US/Eastern)
            try:
                utc_dt = datetime.strptime(doc[attribute], "%Y-%m-%dT%H:%M:%SZ")
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)
                local_tz = tzlocal.get_localzone()
                local_dt = utc_dt.astimezone(local_tz)
                return f"{time_attributes_str[attribute]}: {local_dt.strftime('%Y-%m-%d %I:%M %p %Z')}"
            except Exception as e:
                return f"{time_attributes_str[attribute]}: Unable to convert ({e})"
            
    return ""
            
def to_natural_language(item):
    """Convert a Canvas item to natural language for embedding."""
    type = item.get("type", "").lower()
    course = item.get("course_name", "")
    title = get_title(item)
    result = f"passage: {title} is a {type} for {course}."

    templates = {
        "quiz": [
            ("points_possible",   f"{title} is worth {{}} points"),
            ("time_limit",        f"{title} has a time limit of {{}} minutes"),
            ("allowed_attempts",  lambda v, t=title: f"{t} allows unlimited attempts" if v == -1 else f"{t} allows {v} attempts"),
            ("local_due_time",    f"{title} is due on {{}}"),
            ("locked_for_user",   lambda v, t=title: f"{t} is locked" if v else f"{t} is available"),
        ],
        "assignment": [
            ("local_due_time",    f"{title} is due on {{}}"),
            ("submission_types",  lambda v, t=title: f"{t} accepts submission types: {{', '.join(v)}}" if isinstance(v, list) else f"{t} accepts submission types: {v}"),
            ("can_submit",        lambda v, t=title: f"{t} can be submitted" if v else f"{t} cannot be submitted"),
        ],
        "announcement": [
            ("local_posted_time", f"{title} was posted on {{}}"),
        ],
        "file": [
            ("size",              f"{title} has a size of {{}}"),
            ("local_updated_time", f"{title} was last updated on {{}}"),
            ("locked",            lambda v, t=title: f"{t} is locked" if v else f"{t} is available"),
        ],
        "event": [
            ("local_start_time",  f"{title} starts on {{}}"),
            ("local_end_time",    f"{title} ends on {{}}"),
            ("location_name",     f"{title} takes place at {{}}"),
        ],
    }

    for field, template in templates.get(type, []):
        val = item.get(field)
        if val is None:
            continue
        part = template(val) if callable(template) else template.format(val)
        result += " " + part + "."

    desc = item.get("description", "")
    if desc:
        clean_desc = re.sub(r'<[^>]+>', '', desc)
        result += f"The description is: {clean_desc}"

    return result

def get_title(item):
    title = item.get("title") or item.get("name") or item.get("display_name") or ""
    return title

def add_date_metadata(item: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    """
    Add date fields to metadata based on document type.
    
    Args:
        item: Document item dictionary
        metadata: Metadata dictionary to update with date fields
    """
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