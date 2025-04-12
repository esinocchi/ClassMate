from datetime import datetime
from typing import Dict, Any
import tzlocal


def preprocess_text_for_embedding(doc: Dict[str, Any]) -> str:
        """
        Preprocess document text for embedding.
        
        Args:
            doc: Singular Item dictionary from user_data
            
        Returns:
            Preprocessed text string that is sent to chromadb for embedding
        """
        # Fields in each type
        if doc.get('type'):
            doc_type = doc.get('type', '').upper()
        else:
            doc_type = 'File'
        doc_id = doc.get('id', '')
        course_id = doc.get('course_id', '')

        
        # Build a rich text representation with all relevant fields
        priority_parts = []
        regular_parts = []
        
        # Basic identification
        if doc_id:
            regular_parts.append(f"ID: {doc_id}")
        if doc_type:
            regular_parts.append(f"Type: {doc_type}")
        if course_id:
            regular_parts.append(f"Course ID: {course_id}")

        '''for field in time_fields:
            if field in doc and doc[field] is not None:
                # Convert UTC time to local time
                utc_time = datetime.fromisoformat(doc[field].replace('Z', '+00:00'))
                local_timezone = tzlocal.get_localzone()
                value = utc_time.astimezone(local_timezone).strftime("%Y-%m-%d %I:%M %p")
                doc[field] = value'''
        
        # Handle different document types
        if doc_type == 'File':
            # For files, prioritize the display_name by placing it at the beginning
            display_name = doc.get('display_name', '')
            if display_name:
                # Normalize the display name to improve matching
                normalized_name = normalize_text(display_name)
                # Add the name at the beginning for emphasis
                priority_parts.insert(0, f"Filename: {normalized_name}")
                # Also add it as a title for better matching
                priority_parts.insert(0, f"Title: {normalized_name}")
            
            for field in ['folder_id', 'display_name', 'filename', 'url', 'size', 
                            'updated_at', 'locked', 'lock_explanation']:
                if field in doc and doc[field] is not None: # error prevention
                    # Normalize any text fields to handle special characters
                    if isinstance(doc[field], str):
                        value = normalize_text(doc[field])
                    else:
                        value = doc[field]
                    regular_parts.append(f"{field.replace('_', ' ').title()}: {value}")
            
        elif doc_type == 'Assignment':
            # For assignments, prioritize the name by placing it at the beginning
            name = doc.get('name', '')
            if name:
                # Normalize the name to improve matching
                normalized_name = normalize_text(name)
                # Add the name at the beginning for emphasis
                priority_parts.insert(0, f"Assignment: {normalized_name}")
                priority_parts.insert(0, f"Title: {normalized_name}")
            
            for field in ['name', 'description', 'created_at', 'updated_at', 'due_at', 
                            'submission_types', 'can_submit', 'graded_submissions_exist']:
                if field in doc and doc[field] is not None: # error prevention
                    if field == 'submission_types' and isinstance(doc[field], list):
                        # e.g. [online_text_entry, online_upload] -> Submission Types: Online Text Entry, Online Upload
                        regular_parts.append(f"Submission Types: {', '.join(doc[field])}")
                    else:
                        # Normalize any text fields
                        if isinstance(doc[field], str):
                            value = normalize_text(doc[field])
                        else:
                            value = doc[field]
                        # e.g. HW2 (name) -> Name: HW2
                        regular_parts.append(f"{field.replace('_', ' ').title()}: {value}")
            
            # Handle content field which might contain extracted links
            content = doc.get('content', [])
            if content and isinstance(content, list):
                regular_parts.append("Content Link(s): \n")
                for item in content:
                    if isinstance(item, str):
                        regular_parts.append(f'\t{item}\n')
            
        elif doc_type == 'Announcement':
            # For announcements, prioritize the title by placing it at the beginning
            title = doc.get('title', '')
            if title:
                # Normalize the title to improve matching
                normalized_title = normalize_text(title)
                # Add the title at the beginning for emphasis
                priority_parts.insert(0, f"Announcement: {normalized_title}")
                priority_parts.insert(0, f"Title: {normalized_title}")
            
            for field in ['title', 'message', 'posted_at', 'course_id']:
                if field in doc and doc[field] is not None: # error prevention
                    # Normalize any text fields
                    if isinstance(doc[field], str):
                        value = normalize_text(doc[field])
                    else:
                        value = doc[field]
                    regular_parts.append(f"{field.replace('_', ' ').title()}: {value}")
            
        elif doc_type == 'Quiz':
            # For quizzes, prioritize the title by placing it at the beginning
            title = doc.get('title', '')
            if title:
                # Normalize the title to improve matching
                normalized_title = normalize_text(title)
                # Add the title at the beginning for emphasis
                priority_parts.insert(0, f"Quiz: {normalized_title}")
                priority_parts.insert(0, f"Title: {normalized_title}")
            
            for field in ['title', 'preview_url', 'description', 'quiz_type', 'time_limit', 
                            'allowed_attempts', 'points_possible', 'due_at', 
                            'locked_for_user', 'lock_explanation']:
                if field == 'time_limit' and isinstance(doc[field], int):
                    regular_parts.append(f"Time Limit: {doc[field]} minutes")
                elif field in doc and doc[field] is not None:
                    # Normalize any text fields
                    if isinstance(doc[field], str):
                        value = normalize_text(doc[field])
                    else:
                        value = doc[field]
                    regular_parts.append(f"{field.replace('_', ' ').title()}: {value}")
            
        elif doc_type == 'Event':
            # For events, prioritize the title by placing it at the beginning
            title = doc.get('title', '')
            if title:
                # Normalize the title to improve matching
                normalized_title = normalize_text(title)
                # Add the title at the beginning for emphasis
                priority_parts.insert(0, f"Event: {normalized_title}")
                priority_parts.insert(0, f"Title: {normalized_title}")
            
            for field in ['title', 'start_at', 'end_at', 'description', 'location_name', 
                            'location_address', 'context_code', 'context_name', 
                            'all_context_codes', 'url']:
                if field in doc and doc[field] is not None:
                    # Normalize any text fields
                    if isinstance(doc[field], str):
                        value = normalize_text(doc[field])
                    else:
                        value = doc[field]
                    regular_parts.append(f"{field.replace('_', ' ').title()}: {value}")
        
        # Add module information
        module_id = doc.get('module_id')
        if module_id:
            regular_parts.append(f"Module ID: {module_id}")
        
        module_name = doc.get('module_name')
        if module_name:
            # Normalize module name
            if isinstance(module_name, str):
                module_name = normalize_text(module_name)
            regular_parts.append(f"Module Name: {module_name}")


        # Add local time to doc
        local_time = datetime.now().strftime('%Y-%m-%d %I:%M %p')
        doc['local_time'] = local_time

        # Join all parts with newlines for better separation
        # After processing, the text_parts list for a singule assingment item will have the following format:
        # [
        #     "ID: 123",
        #     "Type: Assignment",
        #     "Course ID: 456",
        #     "Name: HW2",
        #     "Description: This is a description of the assignment",
        #     "Created At: 2021-01-01",
        #     "Updated At: 2021-01-02",
        #     "Due At: 2021-01-03",
        #     "Submission Types: Online Text Entry, Online Upload",
        #     "Graded Submissions Exist: True",
        #     "Module ID: 123",
        #     "Module Name: Module 1",
        #     "Content Link(s):
        #       https://www.example.com
        #       https://www.example.co 
        #       https://www.example.com
        #       https://www.example.com
        #       https://www.example.com
        #       https://www.example.com
        # ]
        # The priority parts are at the beginning of the list, and the regular parts are at the end
        output = "\n".join(priority_parts) + "\n" + "\n".join(regular_parts)
        return output

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