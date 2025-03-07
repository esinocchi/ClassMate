"""
get_user_info_v2.py

This script retrieves user data from the Canvas LMS API for selected courses. It fetches various content types, including course metadata, assignments, discussions, announcements, modules, pages, quizzes, and external tools. The data is structured in a JSON format that is optimized for further processing, such as embedding for search algorithms.

### Output Format:
The output is a structured JSON object with the following key sections:
- **metadata**: Contains information about the user, API token, domain, API version, and synchronization details.
- **courses**: A dictionary where each key is a course ID, and the value is an object containing course details such as name, code, description, and syllabus.
- **grades**: A dictionary where each key is a course ID, and the value is an object containing assignment grades and scores.
- **documents**: A list of documents related to the courses, including syllabi, assignments, discussions, and more, each with relevant metadata.

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
    
    # Initialize the structured data format
    user_data = {
        "metadata": {
            "user_id": "1234",  # Replace with actual user ID
            "canvas_token_id": API_TOKEN[-12],  # Store part of token
            "canvas_domain": API_URL.replace("https://", "").split("/")[0],
            "api_version": "v1",
            "generated_at": start_time.isoformat(),
            "selected_courses": selected_courses,
            "total_documents": 0,
            "last_sync": start_time.isoformat(),
            "sync_status": "in_progress"
        },
        "courses": {},
        "grades": {},
        "documents": []
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
                
                # Add to courses dictionary
                user_data["courses"][course_id] = {
                    "id": course_id,
                    "name": course.get("name", ""),
                    "code": course.get("course_code", ""),
                    "description": course.get("name", ""),
                    "workflow_state": course.get("workflow_state", ""),
                    "start_at": course.get("start_at"),
                    "end_at": course.get("end_at"),
                    "syllabus_body": course.get("syllabus_body", ""),
                    "default_view": course.get("default_view", ""),
                    "course_format": course.get("course_format", ""),
                    "last_updated": datetime.datetime.now().isoformat()
                }
                
                # Initialize grades for this course
                user_data["grades"][course_id] = {
                    "assignments": []
                }
                
                # Extract grade information if available
                if "enrollments" in course:
                    for enrollment in course.get("enrollments", []):
                        if enrollment.get("type") == "student":
                            user_data["grades"][course_id].update({
                                "current_score": enrollment.get("current_score"),
                                "current_grade": enrollment.get("current_grade"),
                                "final_score": enrollment.get("final_score"),
                                "final_grade": enrollment.get("final_grade"),
                                "unposted_current_score": enrollment.get("unposted_current_score"),
                                "unposted_final_score": enrollment.get("unposted_final_score")
                            })
                            break
                
                # Add syllabus as a document if it exists
                syllabus_body = course.get("syllabus_body")
                if syllabus_body and len(syllabus_body.strip()) > 0:
                    content_hash = hashlib.md5(syllabus_body.encode()).hexdigest()
                    if content_hash not in content_hashes:
                        content_hashes.add(content_hash)
                        doc_id = f"syllabus_{course_id}"
                        user_data["documents"].append({
                            "id": doc_id,
                            "course_id": course_id,
                            "type": "syllabus",
                            "title": f"Syllabus - {course.get('name', '')}",
                            "content": syllabus_body,
                            "url": f"{API_URL.replace('/api/v1', '')}/courses/{course_id}/assignments/syllabus",
                            "content_hash": content_hash,
                            "created_at": datetime.datetime.now().isoformat(),
                            "updated_at": datetime.datetime.now().isoformat()
                        })
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
        if course_id in selected_courses and course_id not in user_data["courses"]:
            print(f"Adding course {course_id} from all courses list")
            # Add to courses dictionary (same code as above)
            user_data["courses"][course_id] = {
                "id": course_id,
                "name": course.get("name", ""),
                "code": course.get("course_code", ""),
                "description": course.get("name", ""),
                "workflow_state": course.get("workflow_state", ""),
                "start_at": course.get("start_at"),
                "end_at": course.get("end_at"),
                "syllabus_body": course.get("syllabus_body", ""),
                "default_view": course.get("default_view", ""),
                "course_format": course.get("course_format", ""),
                "last_updated": datetime.datetime.now().isoformat()
            }
            
            # Initialize grades for this course
            user_data["grades"][course_id] = {
                "assignments": []
            }
            
            # Extract grade information if available
            if "enrollments" in course:
                for enrollment in course.get("enrollments", []):
                    if enrollment.get("type") == "student":
                        user_data["grades"][course_id].update({
                            "current_score": enrollment.get("current_score"),
                            "current_grade": enrollment.get("current_grade"),
                            "final_score": enrollment.get("final_score"),
                            "final_grade": enrollment.get("final_grade"),
                            "unposted_current_score": enrollment.get("unposted_current_score"),
                            "unposted_final_score": enrollment.get("unposted_final_score")
                        })
                        break
            
            # Add syllabus as a document if it exists
            syllabus_body = course.get("syllabus_body")
            if syllabus_body and len(syllabus_body.strip()) > 0:
                content_hash = hashlib.md5(syllabus_body.encode()).hexdigest()
                if content_hash not in content_hashes:
                    content_hashes.add(content_hash)
                    doc_id = f"syllabus_{course_id}"
                    user_data["documents"].append({
                        "id": doc_id,
                        "course_id": course_id,
                        "type": "syllabus",
                        "title": f"Syllabus - {course.get('name', '')}",
                        "content": syllabus_body,
                        "url": f"{API_URL.replace('/api/v1', '')}/courses/{course_id}/assignments/syllabus",
                        "content_hash": content_hash,
                        "created_at": datetime.datetime.now().isoformat(),
                        "updated_at": datetime.datetime.now().isoformat()
                    })
    
    # Print diagnostic information
    print(f"Selected courses: {selected_courses}")
    print(f"Courses found: {list(user_data['courses'].keys())}")
    missing_courses = [c for c in selected_courses if c not in user_data['courses']]
    if missing_courses:
        print(f"Missing courses: {missing_courses}")
    
    # For each selected course, get all content types
    for course_id in selected_courses:
        if course_id not in user_data["courses"]:
            print(f"Skipping content fetch for missing course {course_id}")
            continue
            
        course_name = user_data["courses"][course_id]["name"]
        print(f"Fetching content for course {course_id}: {course_name}")
        
        # 1. Get course files
        fetch_files(API_URL, headers, course_id, course_name, user_data, content_hashes)
        
        # 2. Get assignments with submissions and grades
        fetch_assignments_with_grades(API_URL, headers, course_id, course_name, user_data, content_hashes)
        
        # 3. Get discussions
        fetch_discussions(API_URL, headers, course_id, course_name, user_data, content_hashes)
        
        # 4. Get announcements
        fetch_announcements(API_URL, headers, course_id, course_name, user_data, content_hashes)
        
        # 5. Get modules and their items
        fetch_modules_with_items(API_URL, headers, course_id, course_name, user_data, content_hashes)
        
        # 6. Get pages
        fetch_pages(API_URL, headers, course_id, course_name, user_data, content_hashes)
        
        # 7. Get quizzes
        fetch_quizzes(API_URL, headers, course_id, course_name, user_data, content_hashes)
        
        # 8. Get external tools
        fetch_external_tools(API_URL, headers, course_id, course_name, user_data, content_hashes)
        
        # 9. Get home page if different from syllabus
        fetch_home_page(API_URL, headers, course_id, course_name, user_data, content_hashes)
        
        # 10. Get syllabus as a file if it exists
        fetch_syllabus_file(API_URL, headers, course_id, course_name, user_data, content_hashes)
    
    # Update metadata with final stats
    user_data["metadata"]["total_documents"] = len(user_data["documents"])
    user_data["metadata"]["sync_status"] = "complete"
    user_data["metadata"]["sync_duration_seconds"] = (datetime.datetime.now() - start_time).total_seconds()
    
    # Save the data to a JSON file
    user_id = "1234"  # Replace with actual user ID
    file_path = f"{BASE_DIR}/CanvasAI/UserData/psu.instructure.com/{user_id}/user_data2.json"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(user_data, f, indent=2)
    
    print(f"Successfully saved data for {len(user_data['courses'])} courses with {len(user_data['documents'])} documents")

    # Get all courses with different parameters
    try:
        print("\nTrying to fetch courses with different parameters...")
        response = requests.get(
            f"{API_URL}/courses", 
            headers=headers,
            params={
                "per_page": 100,
                "include[]": ["syllabus_body", "term"],
                "state[]": ["available", "completed", "unpublished"]  # Try different states
            }
        )
        
        if response.status_code == 200:
            additional_courses = response.json()
            print(f"Found {len(additional_courses)} courses with expanded parameters")
            
            # Check if any of our selected courses are in this list
            for course in additional_courses:
                course_id = str(course.get("id"))
                if course_id in selected_courses and course_id not in user_data["courses"]:
                    print(f"Found missing course {course_id} with expanded parameters: {course.get('name')}")
                    print(f"Course state: {course.get('workflow_state')}")
                    # Add this course to our data
                    # (same code as above for adding a course)
        else:
            print(f"Error fetching courses with expanded parameters: {response.status_code}")
    except Exception as e:
        print(f"Exception fetching courses with expanded parameters: {str(e)}")

    return user_data

def fetch_files(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch files for a course and add to documents"""
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
                file_type = file.get("content-type", "").split('/')[-1] if file.get("content-type") else ""
                file_size = file.get("size", 0)
                file_created = file.get("created_at", datetime.datetime.now().isoformat())
                file_updated = file.get("updated_at", datetime.datetime.now().isoformat())
                
                # Generate a content identifier for the file
                content_id = f"file_{file_id}_{file_size}"
                
                if content_id not in content_hashes:
                    content_hashes.add(content_id)
                    
                    # Add as a document
                    doc_id = f"file_{course_id}_{file_id}"
                    user_data["documents"].append({
                        "id": doc_id,
                        "course_id": course_id,
                        "type": "file",
                        "title": file_name,
                        "content": "",  # Empty content - will be fetched on demand
                        "url": file_url,
                        "file_type": file_type,
                        "size_kb": round(file_size / 1024, 2),
                        "content_id": content_id,
                        "created_at": file_created,
                        "updated_at": file_updated
                    })
    except Exception as e:
        print(f"Error fetching files for course {course_id}: {str(e)}")

def fetch_assignments_with_grades(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch assignments with submissions and grades for a course"""
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
                points_possible = assignment.get("points_possible")
                
                # Generate content hash for deduplication
                content_hash = None
                if assignment_desc:
                    content_hash = hashlib.md5(assignment_desc.encode()).hexdigest()
                    
                # Add as a document if we have content and it's not a duplicate
                if assignment_desc and (not content_hash or content_hash not in content_hashes):
                    if content_hash:
                        content_hashes.add(content_hash)
                        
                    doc_id = f"assignment_{course_id}_{assignment_id}"
                    user_data["documents"].append({
                        "id": doc_id,
                        "course_id": course_id,
                        "type": "assignment",
                        "title": assignment_name,
                        "content": assignment_desc,
                        "url": assignment_url,
                        "due_date": due_date,
                        "points_possible": points_possible,
                        "content_hash": content_hash,
                        "created_at": assignment.get("created_at", datetime.datetime.now().isoformat()),
                        "updated_at": assignment.get("updated_at", datetime.datetime.now().isoformat())
                    })
                
                # Get submission and grade for this assignment
                try:
                    submission_response = requests.get(
                        f"{api_url}/courses/{course_id}/assignments/{assignment_id}/submissions/self", 
                        headers=headers
                    )
                    
                    if submission_response.status_code == 200:
                        submission = submission_response.json()
                        
                        # Add to grades
                        user_data["grades"][course_id]["assignments"].append({
                            "id": f"assignment_{course_id}_{assignment_id}",
                            "title": assignment_name,
                            "points_possible": points_possible,
                            "score": submission.get("score"),
                            "grade": submission.get("grade"),
                            "submitted": submission.get("submitted_at") is not None,
                            "submission_date": submission.get("submitted_at"),
                            "late": submission.get("late", False)
                        })
                except Exception as e:
                    print(f"Error fetching submission for assignment {assignment_id}: {str(e)}")
    except Exception as e:
        print(f"Error fetching assignments for course {course_id}: {str(e)}")

def fetch_discussions(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch discussions for a course and add to documents"""
    try:
        response = requests.get(
            f"{api_url}/courses/{course_id}/discussion_topics", 
            headers=headers,
            params={"per_page": 100}
        )
        
        if response.status_code == 200:
            discussions = response.json()
            
            for discussion in discussions:
                # Skip if it's an announcement (we'll handle those separately)
                if discussion.get("is_announcement", False):
                    continue
                    
                discussion_id = discussion.get("id")
                discussion_title = discussion.get("title", "")
                discussion_message = discussion.get("message", "")
                discussion_url = discussion.get("html_url", "")
                reply_count = discussion.get("discussion_subentry_count", 0)
                
                # Generate content hash for deduplication
                content_hash = None
                if discussion_message:
                    content_hash = hashlib.md5(discussion_message.encode()).hexdigest()
                
                # Add as a document if we have content and it's not a duplicate
                if discussion_message and (not content_hash or content_hash not in content_hashes):
                    if content_hash:
                        content_hashes.add(content_hash)
                        
                    doc_id = f"discussion_{course_id}_{discussion_id}"
                    user_data["documents"].append({
                        "id": doc_id,
                        "course_id": course_id,
                        "type": "discussion",
                        "title": discussion_title,
                        "content": discussion_message,
                        "url": discussion_url,
                        "reply_count": reply_count,
                        "content_hash": content_hash,
                        "created_at": discussion.get("created_at", datetime.datetime.now().isoformat()),
                        "updated_at": discussion.get("updated_at", datetime.datetime.now().isoformat())
                    })
    except Exception as e:
        print(f"Error fetching discussions for course {course_id}: {str(e)}")

def fetch_announcements(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch announcements for a course and add to documents"""
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
                announcement_url = announcement.get("html_url", "")
                
                # Generate content hash for deduplication
                content_hash = None
                if announcement_message:
                    content_hash = hashlib.md5(announcement_message.encode()).hexdigest()
                
                # Add as a document if we have content and it's not a duplicate
                if announcement_message and (not content_hash or content_hash not in content_hashes):
                    if content_hash:
                        content_hashes.add(content_hash)
                        
                    doc_id = f"announcement_{course_id}_{announcement_id}"
                    user_data["documents"].append({
                        "id": doc_id,
                        "course_id": course_id,
                        "type": "announcement",
                        "title": announcement_title,
                        "content": announcement_message,
                        "url": announcement_url,
                        "content_hash": content_hash,
                        "created_at": announcement.get("created_at", datetime.datetime.now().isoformat()),
                        "updated_at": announcement.get("updated_at", datetime.datetime.now().isoformat())
                    })
    except Exception as e:
        print(f"Error fetching announcements for course {course_id}: {str(e)}")

def fetch_modules_with_items(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch modules and their items for a course"""
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
                module_title = module.get("name", "")
                module_url = f"{api_url.replace('/api/v1', '')}/courses/{course_id}/modules/{module_id}"
                position = module.get("position")
                
                # Add module as a document
                doc_id = f"module_{course_id}_{module_id}"
                module_content = f"Module: {module_title}"
                
                # Generate content hash for module
                content_hash = hashlib.md5(module_content.encode()).hexdigest()
                
                if content_hash not in content_hashes:
                    content_hashes.add(content_hash)
                    
                    user_data["documents"].append({
                        "id": doc_id,
                        "course_id": course_id,
                        "type": "module",
                        "title": module_title,
                        "content": module_content,
                        "url": module_url,
                        "position": position,
                        "unlock_at": module.get("unlock_at"),
                        "content_hash": content_hash,
                        "created_at": datetime.datetime.now().isoformat(),
                        "updated_at": datetime.datetime.now().isoformat()
                    })
                
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
                            item_title = item.get("title", "")
                            item_type = item.get("type", "")
                            item_url = item.get("html_url", "")
                            content_id = item.get("content_id")
                            
                            # For each item type, we'll handle differently
                            if item_type == "File":
                                # File items are already handled in fetch_files
                                # Just update the module_id for the file if we find it
                                for doc in user_data["documents"]:
                                    if doc["type"] == "file" and doc["course_id"] == course_id and str(content_id) in doc["id"]:
                                        doc["module_id"] = doc_id
                                        break
                            
                            elif item_type == "Page":
                                # We'll fetch the page content
                                try:
                                    page_url = item.get("page_url")
                                    if page_url:
                                        page_response = requests.get(
                                            f"{api_url}/courses/{course_id}/pages/{page_url}", 
                                            headers=headers
                                        )
                                        
                                        if page_response.status_code == 200:
                                            page_data = page_response.json()
                                            page_content = page_data.get("body", "")
                                            
                                            # Generate content hash
                                            content_hash = None
                                            if page_content:
                                                content_hash = hashlib.md5(page_content.encode()).hexdigest()
                                            
                                            # Add as a document if not a duplicate
                                            if page_content and (not content_hash or content_hash not in content_hashes):
                                                if content_hash:
                                                    content_hashes.add(content_hash)
                                                    
                                                page_doc_id = f"page_{course_id}_{page_url}"
                                                user_data["documents"].append({
                                                    "id": page_doc_id,
                                                    "course_id": course_id,
                                                    "type": "page",
                                                    "title": item_title,
                                                    "content": page_content,
                                                    "url": item_url,
                                                    "module_id": doc_id,
                                                    "content_hash": content_hash,
                                                    "created_at": page_data.get("created_at", datetime.datetime.now().isoformat()),
                                                    "updated_at": page_data.get("updated_at", datetime.datetime.now().isoformat())
                                                })
                                except Exception as e:
                                    print(f"Error fetching page for module item {item_id}: {str(e)}")
                            
                            elif item_type == "Assignment":
                                # Assignments are already handled in fetch_assignments_with_grades
                                # Just update the module_id for the assignment if we find it
                                for doc in user_data["documents"]:
                                    if doc["type"] == "assignment" and doc["course_id"] == course_id and str(content_id) in doc["id"]:
                                        doc["module_id"] = doc_id
                                        break
                            
                            elif item_type == "Discussion":
                                # Discussions are already handled in fetch_discussions
                                # Just update the module_id for the discussion if we find it
                                for doc in user_data["documents"]:
                                    if doc["type"] == "discussion" and doc["course_id"] == course_id and str(content_id) in doc["id"]:
                                        doc["module_id"] = doc_id
                                        break
                            
                            elif item_type == "Quiz":
                                # Quizzes are already handled in fetch_quizzes
                                # Just update the module_id for the quiz if we find it
                                for doc in user_data["documents"]:
                                    if doc["type"] == "quiz" and doc["course_id"] == course_id and str(content_id) in doc["id"]:
                                        doc["module_id"] = doc_id
                                        break
                            
                            elif item_type == "ExternalUrl":
                                # Add external URL as a document
                                external_url = item.get("external_url", "")
                                
                                if external_url:
                                    # Generate a unique ID for this URL
                                    url_hash = hashlib.md5(external_url.encode()).hexdigest()
                                    
                                    if url_hash not in content_hashes:
                                        content_hashes.add(url_hash)
                                        
                                        url_doc_id = f"external_url_{course_id}_{item_id}"
                                        user_data["documents"].append({
                                            "id": url_doc_id,
                                            "course_id": course_id,
                                            "type": "external_url",
                                            "title": item_title,
                                            "content": f"External URL: {item_title}",
                                            "url": external_url,
                                            "module_id": doc_id,
                                            "content_hash": url_hash,
                                            "created_at": datetime.datetime.now().isoformat(),
                                            "updated_at": datetime.datetime.now().isoformat()
                                        })
                            
                            elif item_type == "ExternalTool":
                                # External tools are already handled in fetch_external_tools
                                # Just update the module_id for the tool if we find it
                                for doc in user_data["documents"]:
                                    if doc["type"] == "external_tool" and doc["course_id"] == course_id and str(content_id) in doc["id"]:
                                        doc["module_id"] = doc_id
                                        break
                except Exception as e:
                    print(f"Error fetching items for module {module_id}: {str(e)}")
    except Exception as e:
        print(f"Error fetching modules for course {course_id}: {str(e)}")

def fetch_pages(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch pages for a course and add to documents"""
    try:
        response = requests.get(
            f"{api_url}/courses/{course_id}/pages", 
            headers=headers,
            params={"per_page": 100}
        )
        
        if response.status_code == 200:
            pages_list = response.json()
            
            for page in pages_list:
                page_url = page.get("url", "")
                page_title = page.get("title", "")
                
                # Get the full page content with another API call
                try:
                    page_response = requests.get(
                        f"{api_url}/courses/{course_id}/pages/{page_url}", 
                        headers=headers
                    )
                    
                    if page_response.status_code == 200:
                        page_data = page_response.json()
                        page_content = page_data.get("body", "")
                        
                        # Generate content hash for deduplication
                        content_hash = None
                        if page_content:
                            content_hash = hashlib.md5(page_content.encode()).hexdigest()
                        
                        # Add as a document if we have content and it's not a duplicate
                        if page_content and (not content_hash or content_hash not in content_hashes):
                            if content_hash:
                                content_hashes.add(content_hash)
                                
                            doc_id = f"page_{course_id}_{page_url}"
                            user_data["documents"].append({
                                "id": doc_id,
                                "course_id": course_id,
                                "type": "page",
                                "title": page_title,
                                "content": page_content,
                                "url": f"{api_url.replace('/api/v1', '')}/courses/{course_id}/pages/{page_url}",
                                "content_hash": content_hash,
                                "created_at": page_data.get("created_at", datetime.datetime.now().isoformat()),
                                "updated_at": page_data.get("updated_at", datetime.datetime.now().isoformat())
                            })
                except Exception as e:
                    print(f"Error fetching content for page {page_url}: {str(e)}")
    except Exception as e:
        print(f"Error fetching pages for course {course_id}: {str(e)}")

def fetch_quizzes(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch quizzes for a course and add to documents"""
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
                due_date = quiz.get("due_at")
                points_possible = quiz.get("points_possible")
                
                # Generate content hash for deduplication
                content_hash = None
                if quiz_desc:
                    content_hash = hashlib.md5(quiz_desc.encode()).hexdigest()
                
                # Add as a document if we have content and it's not a duplicate
                if quiz_desc and (not content_hash or content_hash not in content_hashes):
                    if content_hash:
                        content_hashes.add(content_hash)
                        
                    doc_id = f"quiz_{course_id}_{quiz_id}"
                    user_data["documents"].append({
                        "id": doc_id,
                        "course_id": course_id,
                        "type": "quiz",
                        "title": quiz_title,
                        "content": quiz_desc,
                        "url": quiz_url,
                        "due_date": due_date,
                        "points_possible": points_possible,
                        "content_hash": content_hash,
                        "created_at": quiz.get("created_at", datetime.datetime.now().isoformat()),
                        "updated_at": quiz.get("updated_at", datetime.datetime.now().isoformat())
                    })
                
                # Get submission and grade for this quiz
                try:
                    submission_response = requests.get(
                        f"{api_url}/courses/{course_id}/quizzes/{quiz_id}/submissions/self", 
                        headers=headers
                    )
                    
                    if submission_response.status_code == 200:
                        submission_data = submission_response.json()
                        if "quiz_submissions" in submission_data and submission_data["quiz_submissions"]:
                            submission = submission_data["quiz_submissions"][0]
                            
                            # Add to grades
                            user_data["grades"][course_id]["assignments"].append({
                                "id": f"quiz_{course_id}_{quiz_id}",
                                "title": quiz_title,
                                "points_possible": points_possible,
                                "score": submission.get("score"),
                                "grade": f"{submission.get('score', 0)}/{points_possible}" if points_possible else None,
                                "submitted": submission.get("finished_at") is not None,
                                "submission_date": submission.get("finished_at"),
                                "late": submission.get("overdue_and_needs_submission", False)
                            })
                except Exception as e:
                    print(f"Error fetching submission for quiz {quiz_id}: {str(e)}")
    except Exception as e:
        print(f"Error fetching quizzes for course {course_id}: {str(e)}")

def fetch_external_tools(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch external tools for a course and add to documents"""
    try:
        response = requests.get(
            f"{api_url}/courses/{course_id}/external_tools", 
            headers=headers,
            params={"per_page": 100}
        )
        
        if response.status_code == 200:
            tools = response.json()
            
            for tool in tools:
                tool_id = tool.get("id")
                tool_name = tool.get("name", "")
                tool_desc = tool.get("description", "")
                tool_url = tool.get("url", "")
                
                # Generate content identifier
                content_id = f"tool_{tool_id}"
                
                if content_id not in content_hashes:
                    content_hashes.add(content_id)
                    
                    # Add as a document
                    doc_id = f"external_tool_{course_id}_{tool_id}"
                    user_data["documents"].append({
                        "id": doc_id,
                        "course_id": course_id,
                        "type": "external_tool",
                        "title": tool_name,
                        "content": tool_desc or f"External tool: {tool_name}",
                        "url": f"{api_url.replace('/api/v1', '')}/courses/{course_id}/external_tools/{tool_id}",
                        "content_id": content_id,
                        "created_at": datetime.datetime.now().isoformat(),
                        "updated_at": datetime.datetime.now().isoformat()
                    })
    except Exception as e:
        print(f"Error fetching external tools for course {course_id}: {str(e)}")

def fetch_home_page(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Fetch home page for a course if it's a wiki page"""
    try:
        response = requests.get(
            f"{api_url}/courses/{course_id}", 
            headers=headers,
            params={"include[]": "default_view"}
        )
        
        if response.status_code == 200:
            course_data = response.json()
            default_view = course_data.get("default_view")
            
            # If the home page is a wiki page, fetch it
            if default_view == "wiki":
                try:
                    front_page_response = requests.get(
                        f"{api_url}/courses/{course_id}/front_page", 
                        headers=headers
                    )
                    
                    if front_page_response.status_code == 200:
                        page_data = front_page_response.json()
                        page_title = page_data.get("title", "")
                        page_content = page_data.get("body", "")
                        
                        # Generate content hash for deduplication
                        content_hash = None
                        if page_content:
                            content_hash = hashlib.md5(page_content.encode()).hexdigest()
                        
                        # Add as a document if we have content and it's not a duplicate
                        if page_content and (not content_hash or content_hash not in content_hashes):
                            if content_hash:
                                content_hashes.add(content_hash)
                                
                            doc_id = f"home_page_{course_id}"
                            user_data["documents"].append({
                                "id": doc_id,
                                "course_id": course_id,
                                "type": "home_page",
                                "title": f"{course_name} Home Page",
                                "content": page_content,
                                "url": f"{api_url.replace('/api/v1', '')}/courses/{course_id}",
                                "content_hash": content_hash,
                                "created_at": page_data.get("created_at", datetime.datetime.now().isoformat()),
                                "updated_at": page_data.get("updated_at", datetime.datetime.now().isoformat())
                            })
                except Exception as e:
                    print(f"Error fetching front page for course {course_id}: {str(e)}")
            
            # If the home page is modules, assignments, or syllabus, we've already fetched that content
            # Just add a reference document for the home page
            elif default_view in ["modules", "assignments", "syllabus"]:
                home_content = f"This course uses {default_view} as its home page."
                content_hash = hashlib.md5(home_content.encode()).hexdigest()
                
                if content_hash not in content_hashes:
                    content_hashes.add(content_hash)
                    
                    doc_id = f"home_page_{course_id}"
                    user_data["documents"].append({
                        "id": doc_id,
                        "course_id": course_id,
                        "type": "home_page_reference",
                        "title": f"{course_name} Home Page",
                        "content": home_content,
                        "url": f"{api_url.replace('/api/v1', '')}/courses/{course_id}",
                        "references": default_view,
                        "content_hash": content_hash,
                        "created_at": datetime.datetime.now().isoformat(),
                        "updated_at": datetime.datetime.now().isoformat()
                    })
    except Exception as e:
        print(f"Error fetching home page for course {course_id}: {str(e)}")

def fetch_syllabus_file(api_url, headers, course_id, course_name, user_data, content_hashes):
    """Look for syllabus files in the course files"""
    try:
        # Check if we already have a syllabus document for this course
        has_syllabus = False
        for doc in user_data["documents"]:
            if doc["course_id"] == course_id and doc["type"] == "syllabus" and doc["content"]:
                has_syllabus = True
                break
        
        # If we don't have a syllabus yet, look for syllabus files
        if not has_syllabus:
            # Search for syllabus in files
            for doc in user_data["documents"]:
                if (doc["course_id"] == course_id and 
                    doc["type"] == "file" and 
                    "syllabus" in doc["title"].lower()):
                    
                    # Mark this file as a potential syllabus
                    doc["is_syllabus_file"] = True
                    
                    # Create a syllabus document that references this file
                    doc_id = f"syllabus_{course_id}"
                    user_data["documents"].append({
                        "id": doc_id,
                        "course_id": course_id,
                        "type": "syllabus",
                        "title": f"Syllabus - {course_name}",
                        "content": f"The syllabus for this course is available as a file: {doc['title']}",
                        "url": doc["url"],
                        "references_file": doc["id"],
                        "created_at": doc["created_at"],
                        "updated_at": doc["updated_at"]
                    })
                    break
    except Exception as e:
        print(f"Error searching for syllabus file in course {course_id}: {str(e)}")

# Optional: Fetch discussion replies (can be resource-intensive)
def fetch_discussion_replies(api_url, headers, course_id, discussion_id, user_data, content_hashes):
    """Fetch replies for a discussion"""
    try:
        response = requests.get(
            f"{api_url}/courses/{course_id}/discussion_topics/{discussion_id}/entries", 
            headers=headers,
            params={"per_page": 100}
        )
        
        if response.status_code == 200:
            replies = response.json()
            
            for reply in replies:
                reply_id = reply.get("id")
                reply_message = reply.get("message", "")
                author_name = reply.get("user_name", "Anonymous")
                
                # Generate content hash for deduplication
                content_hash = None
                if reply_message:
                    content_hash = hashlib.md5(reply_message.encode()).hexdigest()
                
                # Add as a document if we have content and it's not a duplicate
                if reply_message and (not content_hash or content_hash not in content_hashes):
                    if content_hash:
                        content_hashes.add(content_hash)
                        
                    doc_id = f"discussion_reply_{course_id}_{discussion_id}_{reply_id}"
                    user_data["documents"].append({
                        "id": doc_id,
                        "course_id": course_id,
                        "type": "discussion_reply",
                        "parent_id": f"discussion_{course_id}_{discussion_id}",
                        "title": f"Re: {user_data['documents'][next(i for i, d in enumerate(user_data['documents']) if d['id'] == f'discussion_{course_id}_{discussion_id}')]['title']}",
                        "content": reply_message,
                        "url": f"{api_url.replace('/api/v1', '')}/courses/{course_id}/discussion_topics/{discussion_id}#reply_{reply_id}",
                        "author": author_name,
                        "content_hash": content_hash,
                        "created_at": reply.get("created_at", datetime.datetime.now().isoformat()),
                        "updated_at": reply.get("updated_at", datetime.datetime.now().isoformat())
                    })
                
                # Recursively fetch replies to this reply
                if reply.get("has_more_replies", False):
                    try:
                        sub_replies_response = requests.get(
                            f"{api_url}/courses/{course_id}/discussion_topics/{discussion_id}/entries/{reply_id}/replies", 
                            headers=headers,
                            params={"per_page": 100}
                        )
                        
                        if sub_replies_response.status_code == 200:
                            sub_replies = sub_replies_response.json()
                            
                            for sub_reply in sub_replies:
                                sub_reply_id = sub_reply.get("id")
                                sub_reply_message = sub_reply.get("message", "")
                                sub_author_name = sub_reply.get("user_name", "Anonymous")
                                
                                # Generate content hash for deduplication
                                sub_content_hash = None
                                if sub_reply_message:
                                    sub_content_hash = hashlib.md5(sub_reply_message.encode()).hexdigest()
                                
                                # Add as a document if we have content and it's not a duplicate
                                if sub_reply_message and (not sub_content_hash or sub_content_hash not in content_hashes):
                                    if sub_content_hash:
                                        content_hashes.add(sub_content_hash)
                                        
                                    sub_doc_id = f"discussion_reply_{course_id}_{discussion_id}_{reply_id}_{sub_reply_id}"
                                    user_data["documents"].append({
                                        "id": sub_doc_id,
                                        "course_id": course_id,
                                        "type": "discussion_reply",
                                        "parent_id": f"discussion_reply_{course_id}_{discussion_id}_{reply_id}",
                                        "title": f"Re: Re: {user_data['documents'][next(i for i, d in enumerate(user_data['documents']) if d['id'] == f'discussion_{course_id}_{discussion_id}')]['title']}",
                                        "content": sub_reply_message,
                                        "url": f"{api_url.replace('/api/v1', '')}/courses/{course_id}/discussion_topics/{discussion_id}#reply_{sub_reply_id}",
                                        "author": sub_author_name,
                                        "content_hash": sub_content_hash,
                                        "created_at": sub_reply.get("created_at", datetime.datetime.now().isoformat()),
                                        "updated_at": sub_reply.get("updated_at", datetime.datetime.now().isoformat())
                                    })
                    except Exception as e:
                        print(f"Error fetching sub-replies for discussion {discussion_id}, reply {reply_id}: {str(e)}")
    except Exception as e:
        print(f"Error fetching replies for discussion {discussion_id}: {str(e)}")

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
    missing_courses = [c for c in selected_courses if c not in user_data['courses']]
    if missing_courses:
        print(f"\nDebugging missing courses: {missing_courses}")
        for course_id in missing_courses:
            debug_course_access(course_id)
    
    print(f"Successfully processed {len(user_data['documents'])} documents from {len(user_data['courses'])} courses.")