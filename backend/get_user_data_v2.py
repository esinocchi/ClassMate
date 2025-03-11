"""
get_user_info_v2.py

This script retrieves user data from the Canvas LMS API for selected courses. It fetches various content types, including course metadata, assignments, discussions, announcements, modules, pages, quizzes, and external tools. The data is structured in a JSON format that is optimized for further processing, such as embedding for search algorithms.

### Output Format:
The output is a structured JSON object with the following key sections:
- **user_metadata**: Contains information about the user, API token, domain, API version, and synchronization details.
- **courses**: A list of course objects containing details such as name, code, description, and syllabus.
- **files**: A list of file objects related to the courses.
- **announcements**: A list of announcement objects from the courses.
- **assignments**: A list of assignment objects with details and submission status.
- **quizzes**: A list of quiz objects with details and settings.
- **calendar_events**: A list of calendar event objects.

### Usage:
1. Ensure that the `CANVAS_TOKEN` environment variable is set with a valid Canvas API token.
2. Update the `selected_courses` list with the desired course IDs.
3. Run the script to fetch and save the user data to a JSON file.

The resulting JSON file will be saved in the specified directory structure under `user_data/CanvasAI/UserData/psu.instructure.com/{user_id}/user_data2.json`.

"""
import requests
import os
import json
import datetime
import hashlib
import re
from dotenv import load_dotenv

BASE_DIR = "user_data/"
API_URL = "https://psu.instructure.com/api/v1"
load_dotenv()
API_TOKEN = os.getenv("CANVAS_TOKEN")
print(f"Token starts with: {API_TOKEN[:5]}..." if API_TOKEN else "No token found")

selected_courses = ['2379517', '2361957', '2361815', '2364485', '2361972']

def get_all_user_data():
    """
    Returns a structured JSON format with all Canvas content types for selected courses,
    handling various course structures and including grades.
    """
    start_time = datetime.datetime.now()
    
    # Initialize the structured data format according to the new schema
    user_data = {
        "user_metadata": {
            "id": "1234",  # Replace with actual user ID
            "name": "Canvas User",  # Replace with actual user name
            "token": API_TOKEN[-12:] if API_TOKEN else "",  # Store part of token
            "domain": API_URL.replace("https://", "").split("/")[0],
            "updated_at": int(datetime.datetime.now().timestamp()),
            "update_duration": 0,  # Will be calculated at the end
            "courses_selected": [int(course_id) for course_id in selected_courses]
        },
        "courses": [],
        "files": [],
        "announcements": [],
        "assignments": [],
        "quizzes": [],
        "calendar_events": []
    }
    
    # Use proper headers for authentication
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    
    # Track content hashes to avoid duplicates
    content_hashes = set()
    
    # First, directly fetch each selected course by ID to ensure we get all of them
    for course_id in selected_courses:
        try:
            print(f"Fetching course {course_id}...")
            response = requests.get(
                f"{API_URL}/courses/{course_id}", 
                headers=headers,
                params={"include[]": ["syllabus_body", "term", "course_progress", "total_scores"]}
            )
            
            if response.status_code == 200:
                course = response.json()
                
                # Add to courses list
                course_data = {
                    "id": int(course_id),
                    "name": course.get("name", ""),
                    "course_code": course.get("course_code", ""),
                    "original_name": course.get("original_name", course.get("name", "")),
                    "default_view": course.get("default_view", ""),
                    "syllabus_body": course.get("syllabus_body", ""),
                    "public_description": course.get("public_description", ""),
                    "time_zone": course.get("time_zone", "America/Denver")
                }
                user_data["courses"].append(course_data)
                
                # Add syllabus as a file if it exists
                syllabus_body = course.get("syllabus_body")
                if syllabus_body and len(syllabus_body.strip()) > 0:
                    content_hash = hashlib.md5(syllabus_body.encode()).hexdigest()
                    if content_hash not in content_hashes:
                        content_hashes.add(content_hash)
                        syllabus_file = {
                            "id": int(f"9{course_id}")[:9],  # Generate a unique ID
                            "type": "file",
                            "course_id": int(course_id),  # Ensure course_id is included
                            "folder_id": None,
                            "display_name": f"Syllabus - {course.get('name', '')}",
                            "filename": f"syllabus_{course_id}.html",
                            "url": f"{API_URL.replace('/api/v1', '')}/courses/{course_id}/assignments/syllabus",
                            "size": len(syllabus_body),
                            "updated_at": datetime.datetime.now().isoformat(),
                            "locked": False,
                            "lock_explanation": "",
                            "module_id": None,
                            "module_name": None
                        }
                        user_data["files"].append(syllabus_file)
            else:
                print(f"Error fetching course {course_id}: {response.status_code}")
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"Exception fetching course {course_id}: {str(e)}")
    
    # Now fetch all courses to ensure we didn't miss any
    all_courses = []
    page = 1
    while True:
        try:
            response = requests.get(
                f"{API_URL}/courses", 
                headers=headers,
                params={
                    "per_page": 100,
                    "page": page,
                    "include[]": ["syllabus_body", "term", "course_progress", "total_scores"]
                }
            )
            
            if response.status_code == 200:
                page_courses = response.json()
                if not page_courses:
                    break  # No more courses
                
                all_courses.extend(page_courses)
                page += 1
            else:
                print(f"Error fetching courses page {page}: {response.status_code}")
                break
        except Exception as e:
            print(f"Exception fetching courses page {page}: {str(e)}")
            break
    
    # Add any selected courses that weren't already added
    for course in all_courses:
        course_id = str(course.get("id"))
        if course_id in selected_courses and not any(c["id"] == int(course_id) for c in user_data["courses"]):
            print(f"Adding course {course_id} from all courses list")
            # Add to courses list
            course_data = {
                "id": int(course_id),
                "name": course.get("name", ""),
                "course_code": course.get("course_code", ""),
                "original_name": course.get("original_name", course.get("name", "")),
                "default_view": course.get("default_view", ""),
                "syllabus_body": course.get("syllabus_body", ""),
                "public_description": course.get("public_description", ""),
                "time_zone": course.get("time_zone", "America/Denver")
            }
            user_data["courses"].append(course_data)
            
            # Add syllabus as a file if it exists
            syllabus_body = course.get("syllabus_body")
            if syllabus_body and len(syllabus_body.strip()) > 0:
                content_hash = hashlib.md5(syllabus_body.encode()).hexdigest()
                if content_hash not in content_hashes:
                    content_hashes.add(content_hash)
                    syllabus_file = {
                        "id": int(f"9{course_id}")[:9],  # Generate a unique ID
                        "type": "file",
                        "course_id": int(course_id),  # Ensure course_id is included
                        "folder_id": None,
                        "display_name": f"Syllabus - {course.get('name', '')}",
                        "filename": f"syllabus_{course_id}.html",
                        "url": f"{API_URL.replace('/api/v1', '')}/courses/{course_id}/assignments/syllabus",
                        "size": len(syllabus_body),
                        "updated_at": datetime.datetime.now().isoformat(),
                        "locked": False,
                        "lock_explanation": "",
                        "module_id": None,
                        "module_name": None
                    }
                    user_data["files"].append(syllabus_file)
    
    # Print diagnostic information
    print(f"Selected courses: {selected_courses}")
    print(f"Courses found: {[str(c['id']) for c in user_data['courses']]}")
    missing_courses = [c for c in selected_courses if not any(int(c) == course["id"] for course in user_data["courses"])]
    if missing_courses:
        print(f"Missing courses: {missing_courses}")
    
    # For each selected course, get all content types
    for course_id in selected_courses:
        if not any(c["id"] == int(course_id) for c in user_data["courses"]):
            print(f"Skipping content fetch for missing course {course_id}")
            continue
            
        course_name = next((c["name"] for c in user_data["courses"] if c["id"] == int(course_id)), "")
        print(f"Fetching content for course {course_id}: {course_name}")
        
        # 1. Get course files
        fetch_files(API_URL, headers, course_id, course_name, user_data, content_hashes)
        
        # 2. Get assignments
        fetch_assignments(API_URL, headers, course_id, course_name, user_data, content_hashes)
        
        # 3. Get announcements (which are a type of discussion)
        fetch_announcements(API_URL, headers, course_id, course_name, user_data, content_hashes)
        
        # 4. Get modules and their items
        fetch_modules_with_items(API_URL, headers, course_id, course_name, user_data, content_hashes)
        
        # 5. Get quizzes
        fetch_quizzes(API_URL, headers, course_id, course_name, user_data, content_hashes)
        
        # 6. Get calendar events
        fetch_calendar_events(API_URL, headers, course_id, course_name, user_data, content_hashes)
    
    # Update metadata with final stats
    end_time = datetime.datetime.now()
    user_data["user_metadata"]["update_duration"] = int((end_time - start_time).total_seconds())
    
    # Save the data to a JSON file
    user_id = "1234"  # Replace with actual user ID
    file_path = f"{BASE_DIR}/CanvasAI/UserData/psu.instructure.com/{user_id}/user_data2.json"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(user_data, f, indent=2)
    
    print(f"Successfully saved data for {len(user_data['courses'])} courses")
    print(f"Files: {len(user_data['files'])}")
    print(f"Announcements: {len(user_data['announcements'])}")
    print(f"Assignments: {len(user_data['assignments'])}")
    print(f"Quizzes: {len(user_data['quizzes'])}")
    print(f"Calendar Events: {len(user_data['calendar_events'])}")

    return user_data

def extract_links_from_html(html_content):
    """Extract links from HTML content for assignment content"""
    if not html_content:
        return []
    
    # Simple regex to find href links
    links = re.findall(r'href=[\'"]?([^\'" >]+)', html_content)
    return links

def fetch_files(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch files for a course and add to files list"""
    try:
        response = requests.get(
            f"{api_url}/courses/{course_id}/files", 
            headers=headers,
            params={"per_page": 100}
        )
        
        if response.status_code == 200:
            files = response.json()
            
            for file in files:
                file_id = file.get("id")
                file_name = file.get("display_name", "")
                file_url = file.get("url", "")
                file_size = file.get("size", 0)
                file_updated = file.get("updated_at", datetime.datetime.now().isoformat())
                
                # Generate a content identifier for the file
                content_id = f"file_{file_id}_{file_size}"
                
                if content_id not in content_hashes:
                    content_hashes.add(content_id)
                    
                    # Add to files list
                    file_data = {
                        "id": file_id,
                        "type": "file",
                        "course_id": int(course_id),  # Ensure course_id is included
                        "folder_id": file.get("folder_id"),
                        "display_name": file_name,
                        "filename": file.get("filename", file_name),
                        "url": file_url,
                        "size": file_size,
                        "updated_at": file_updated,
                        "locked": file.get("locked", False),
                        "lock_explanation": file.get("lock_explanation", ""),
                        "module_id": None,  # Will be updated when processing modules
                        "module_name": None  # Will be updated when processing modules
                    }
                    user_data["files"].append(file_data)
    except Exception as e:
        print(f"Error fetching files for course {course_id}: {str(e)}")

def fetch_assignments(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch assignments for a course"""
    try:
        # Get assignments
        response = requests.get(
            f"{api_url}/courses/{course_id}/assignments", 
            headers=headers,
            params={"per_page": 100}
        )
        
        if response.status_code == 200:
            assignments = response.json()
            
            for assignment in assignments:
                assignment_id = assignment.get("id")
                assignment_name = assignment.get("name", "")
                assignment_desc = assignment.get("description", "")
                assignment_url = assignment.get("html_url", "")
                due_date = assignment.get("due_at")
                
                # Extract links from description for content
                content_links = extract_links_from_html(assignment_desc)
                
                # Generate content hash for deduplication
                content_hash = None
                if assignment_desc:
                    content_hash = hashlib.md5(assignment_desc.encode()).hexdigest()
                    
                # Add to assignments list if not a duplicate
                if not content_hash or content_hash not in content_hashes:
                    if content_hash:
                        content_hashes.add(content_hash)
                        
                    # Get submission status
                    can_submit = True
                    graded_submissions_exist = False
                    try:
                        submission_response = requests.get(
                            f"{api_url}/courses/{course_id}/assignments/{assignment_id}/submissions/self", 
                            headers=headers
                        )
                        
                        if submission_response.status_code == 200:
                            submission = submission_response.json()
                            can_submit = submission.get("workflow_state") not in ["submitted", "graded"]
                            graded_submissions_exist = submission.get("workflow_state") == "graded"
                    except Exception as e:
                        print(f"Error fetching submission for assignment {assignment_id}: {str(e)}")
                    
                    assignment_data = {
                        "id": assignment_id,
                        "type": "assignment",
                        "name": assignment_name,
                        "description": assignment_desc,
                        "created_at": assignment.get("created_at", datetime.datetime.now().isoformat()),
                        "updated_at": assignment.get("updated_at", datetime.datetime.now().isoformat()),
                        "due_at": due_date,
                        "course_id": int(course_id),
                        "submission_types": assignment.get("submission_types", []),
                        "can_submit": can_submit,
                        "graded_submissions_exist": graded_submissions_exist,
                        "module_id": None,  # Will be updated when processing modules
                        "module_name": None,  # Will be updated when processing modules
                        "content": content_links
                    }
                    user_data["assignments"].append(assignment_data)
    except Exception as e:
        print(f"Error fetching assignments for course {course_id}: {str(e)}")

def fetch_announcements(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch announcements for a course"""
    try:
        response = requests.get(
            f"{api_url}/courses/{course_id}/discussion_topics", 
            headers=headers,
            params={"per_page": 100, "only_announcements": True}
        )
        
        if response.status_code == 200:
            announcements = response.json()
            
            for announcement in announcements:
                announcement_id = announcement.get("id")
                announcement_title = announcement.get("title", "")
                announcement_message = announcement.get("message", "")
                
                # Generate content hash for deduplication
                content_hash = None
                if announcement_message:
                    content_hash = hashlib.md5(announcement_message.encode()).hexdigest()
                
                # Add to announcements list if not a duplicate
                if not content_hash or content_hash not in content_hashes:
                    if content_hash:
                        content_hashes.add(content_hash)
                        
                    announcement_data = {
                        "id": announcement_id,
                        "type": "announcement",
                        "title": announcement_title,
                        "message": announcement_message,
                        "course_id": int(course_id),
                        "posted_at": announcement.get("posted_at", announcement.get("created_at", datetime.datetime.now().isoformat()))
                    }
                    user_data["announcements"].append(announcement_data)
    except Exception as e:
        print(f"Error fetching announcements for course {course_id}: {str(e)}")

def fetch_modules_with_items(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch modules and update module information for items"""
    try:
        # Get modules
        response = requests.get(
            f"{api_url}/courses/{course_id}/modules", 
            headers=headers,
            params={"per_page": 100}
        )
        
        if response.status_code == 200:
            modules = response.json()
            
            for module in modules:
                module_id = module.get("id")
                module_name = module.get("name", "")
                
                # Get module items
                try:
                    items_response = requests.get(
                        f"{api_url}/courses/{course_id}/modules/{module_id}/items", 
                        headers=headers,
                        params={"per_page": 100}
                    )
                    
                    if items_response.status_code == 200:
                        items = items_response.json()
                        
                        for item in items:
                            item_id = item.get("id")
                            item_type = item.get("type", "")
                            content_id = item.get("content_id")
                            
                            # Update module information for different content types
                            if item_type == "File" and content_id:
                                for file in user_data["files"]:
                                    if file["id"] == content_id:
                                        file["module_id"] = module_id
                                        file["module_name"] = module_name
                                        break
                            
                            elif item_type == "Assignment" and content_id:
                                for assignment in user_data["assignments"]:
                                    if assignment["id"] == content_id:
                                        assignment["module_id"] = module_id
                                        assignment["module_name"] = module_name
                                        break
                            
                            elif item_type == "Quiz" and content_id:
                                for quiz in user_data["quizzes"]:
                                    if quiz["id"] == content_id:
                                        quiz["module_id"] = module_id
                                        quiz["module_name"] = module_name
                                        break
                except Exception as e:
                    print(f"Error fetching items for module {module_id}: {str(e)}")
    except Exception as e:
        print(f"Error fetching modules for course {course_id}: {str(e)}")

def fetch_quizzes(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch quizzes for a course"""
    try:
        response = requests.get(
            f"{api_url}/courses/{course_id}/quizzes", 
            headers=headers,
            params={"per_page": 100}
        )
        
        if response.status_code == 200:
            quizzes = response.json()
            
            for quiz in quizzes:
                quiz_id = quiz.get("id")
                quiz_title = quiz.get("title", "")
                quiz_desc = quiz.get("description", "")
                quiz_url = quiz.get("html_url", "")
                
                # Generate content hash for deduplication
                content_hash = None
                if quiz_desc:
                    content_hash = hashlib.md5(quiz_desc.encode()).hexdigest()
                
                # Add to quizzes list if not a duplicate
                if not content_hash or content_hash not in content_hashes:
                    if content_hash:
                        content_hashes.add(content_hash)
                        
                    quiz_data = {
                        "id": quiz_id,
                        "title": quiz_title,
                        "course_id": int(course_id),  # Ensure course_id is included
                        "preview_url": quiz_url,
                        "description": quiz_desc,
                        "quiz_type": quiz.get("quiz_type", ""),
                        "time_limit": quiz.get("time_limit"),
                        "allowed_attempts": quiz.get("allowed_attempts"),
                        "points_possible": quiz.get("points_possible"),
                        "due_at": quiz.get("due_at"),
                        "locked_for_user": quiz.get("locked_for_user", False),
                        "lock_explanation": quiz.get("lock_explanation", ""),
                        "module_id": None,  # Will be updated when processing modules
                        "module_name": None  # Will be updated when processing modules
                    }
                    user_data["quizzes"].append(quiz_data)
    except Exception as e:
        print(f"Error fetching quizzes for course {course_id}: {str(e)}")

def fetch_calendar_events(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch calendar events for a course"""
    try:
        # Get calendar events for this course
        response = requests.get(
            f"{api_url}/calendar_events", 
            headers=headers,
            params={
                "context_codes[]": f"course_{course_id}",
                "per_page": 100
            }
        )
        
        if response.status_code == 200:
            events = response.json()
            
            for event in events:
                event_id = event.get("id")
                event_title = event.get("title", "")
                event_desc = event.get("description", "")
                
                # Generate content hash for deduplication
                content_hash = None
                if event_desc:
                    content_hash = hashlib.md5(event_desc.encode()).hexdigest()
                
                # Add to calendar_events list if not a duplicate
                if not content_hash or content_hash not in content_hashes:
                    if content_hash:
                        content_hashes.add(content_hash)
                        
                    # Extract course_id from context_code if available
                    event_course_id = int(course_id)
                    if event.get("context_code", "").startswith("course_"):
                        extracted_course_id = event.get("context_code").replace("course_", "")
                        try:
                            event_course_id = int(extracted_course_id)
                        except ValueError:
                            # If conversion fails, use the original course_id
                            pass
                        
                    event_data = {
                        "id": event_id,
                        "title": event_title,
                        "course_id": event_course_id,  # Ensure course_id is included
                        "start_at": event.get("start_at"),
                        "end_at": event.get("end_at"),
                        "description": event_desc,
                        "location_name": event.get("location_name", ""),
                        "location_address": event.get("location_address", ""),
                        "context_code": event.get("context_code", f"course_{course_id}"),
                        "context_name": course_name,
                        "all_context_codes": event.get("all_context_codes", f"course_{course_id}"),
                        "url": event.get("url", f"{api_url.replace('/api/v1', '')}/calendar?event_id={event_id}&include_contexts=course_{course_id}")
                    }
                    user_data["calendar_events"].append(event_data)
    except Exception as e:
        print(f"Error fetching calendar events for course {course_id}: {str(e)}")

def debug_course_access(course_id):
    """Debug why a specific course might not be accessible"""
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    
    # Try different API endpoints to diagnose the issue
    endpoints = [
        f"{API_URL}/courses/{course_id}",
        f"{API_URL}/courses/{course_id}/assignments",
        f"{API_URL}/courses/{course_id}/users",
        f"{API_URL}/courses/{course_id}/files"
    ]
    
    print(f"\n--- Debugging access to course {course_id} ---")
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, headers=headers)
            print(f"Endpoint: {endpoint}")
            print(f"Status: {response.status_code}")
            if response.status_code != 200:
                print(f"Error: {response.text}")
            else:
                print("Success!")
        except Exception as e:
            print(f"Exception: {str(e)}")
    print("--- End debugging ---\n")

# Main execution
if __name__ == "__main__":
    user_data = get_all_user_data()
    
    # Debug any missing courses
    missing_courses = [c for c in selected_courses if not any(int(c) == course["id"] for course in user_data['courses'])]
    if missing_courses:
        print(f"\nDebugging missing courses: {missing_courses}")
        for course_id in missing_courses:
            debug_course_access(course_id)
    
    print(f"Successfully processed data from {len(user_data['courses'])} courses.")