import io
from docx import Document
import requests
import os
import time
import json
import fitz  # PyMuPDF
import pytesseract
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from PIL import Image
import sys
import aiohttp
import asyncio

# Import calendar_agent directly from task_specific_agents (sibling directory)
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)
from task_specific_agents.calendar_agent import find_events

load_dotenv()

async def get_text_from_links(links: list, API_URL: str, API_TOKEN: str):
    """
    Process a list of links and extracts text.

    ================================================

    examples of input parameters:
    links = [{filename: fileurl}]
    API_URL = "https://psu.instructure.com/api/v1"
    API_TOKEN = "1234567890"

    ================================================

    examples of output:
    complete_text = "this text is from multiple files obtained through the links provided"

    ================================================
    
    """
    complete_text = ""
    async with aiohttp.ClientSession() as session:
        for link_dict in links:
            for filename, fileurl in link_dict.items():
                try:
                    # Extract file ID and course ID from the Canvas URL
                    # Example URL: https://psu.instructure.com/courses/123456/files/789012
                    file_id = fileurl.split('/')[-1].split('?')[0]  # Get file ID (789012)
                    course_id = fileurl.split('/courses/')[1].split('/')[0]  # Get course ID (123456)
                    
                    # Construct the Canvas API endpoint for file metadata
                    api_url = f"{API_URL}/courses/{course_id}/files/{file_id}"

                    # First request: Get file metadata including the actual download URL
                    headers = {"Authorization": f"Bearer {API_TOKEN}"}
                    async with session.get(api_url, headers=headers) as response:
                        if response.status != 200:
                            continue

                        # Extract the actual download URL from the file metadata
                        file_data = await response.json()
                        download_url = file_data.get('url')
                        
                        if not download_url:
                            continue

                        # Second request: Download the actual file content
                        async with session.get(download_url, headers=headers) as file_response:
                            if file_response.status != 200:
                                continue

                            # Get the raw file content as bytes
                            file_bytes = await file_response.read()

                            # Determine the file type from the filename extension
                            file_type = get_file_type(filename)

                            # Process the file based on its type and extract text
                            extracted_text = extract_text_and_images(file_bytes, file_type)
                            complete_text += f"\nText from {filename}:\n{extracted_text}\n\n"
                except Exception as e:
                    print(f"Error processing file {filename}: {str(e)}")
                    continue
    return complete_text

def get_file_type(filename: str):
    """
    Determine the file type based on the filename extension.
    Returns the lowercase extension (e.g., "pdf", "docx", "png")

    ================================================

    examples of input parameters:
    filename = "example.pdf"

    ================================================

    examples of output:
    file_type = "pdf"

    ================================================
    
    """
    # Extract the file extension (e.g., "pdf", "docx", "png")
    file_extension = filename.split(".")[-1].lower()
    return file_extension

def extract_text_and_images(file_bytes: bytes, file_type: str):
    """
    Extract text and images from a file.

    ================================================

    examples of input parameters:
    file_bytes = b"this is the raw bytes of a file"
    file_type = "pdf"

    ================================================

    examples of output:
    total_text = "this is the text from the file"

    ================================================
    
    """
    total_text = ""

    try:
        if file_type == "pdf":
            # Handle PDF files
            try:
                # Create a memory stream from the PDF bytes
                pdf_stream = io.BytesIO(file_bytes)
                # Open the PDF document
                doc = fitz.open(stream=pdf_stream, filetype="pdf")
                print(f"\nSuccessfully opened PDF with {len(doc)} pages")

                # Check if PDF is password protected
                if doc.is_encrypted:
                    return "PDF is encrypted and cannot be processed."

                # Process each page of the PDF
                for page_num in range(len(doc)):
                    try:
                        # Extract text from the page
                        page = doc.load_page(page_num)
                        text = page.get_text()
                        if text:
                            print(f"Successfully extracted text from page {page_num + 1}")
                            total_text += f"Text from page {page_num + 1}:\n{text}\n"

                        # Extract and process images from the page
                        image_list = page.get_images(full=True)
                        if image_list:
                            print(f"Found {len(image_list)} images on page {page_num + 1}")
                        for img_index, img in enumerate(image_list):
                            try:
                                # Extract image data and perform OCR
                                xref = img[0]
                                base_image = doc.extract_image(xref)
                                if base_image and "image" in base_image:
                                    image_bytes = base_image["image"]
                                    image = Image.open(io.BytesIO(image_bytes))
                                    ocr_text = pytesseract.image_to_string(image)
                                    if ocr_text:
                                        print(f"Successfully extracted text from image {img_index + 1} on page {page_num + 1}")
                                        total_text += f"Image {img_index + 1} from page {page_num + 1}:\n{ocr_text}\n"
                            except Exception:
                                continue
                    except Exception:
                        continue

                # Clean up resources
                doc.close()
                pdf_stream.close()

            except Exception as pdf_error:
                return f"Error processing PDF: {pdf_error}"

        elif file_type == "docx":
            # Handle DOCX files
            try:
                # Open DOCX file from memory and extract text from paragraphs
                doc = Document(io.BytesIO(file_bytes))
                for paragraph in doc.paragraphs:
                    if paragraph.text:
                        total_text += paragraph.text + "\n"
            except Exception as docx_error:
                return f"Error processing DOCX: {docx_error}"

        elif file_type == "txt":
            # Handle TXT files
            try:
                # Try different text encodings to handle various text file formats
                encodings = ['utf-8', 'latin-1', 'ascii', 'iso-8859-1']
                for encoding in encodings:
                    try:
                        text = file_bytes.decode(encoding)
                        if text:
                            total_text = text
                            break
                    except UnicodeDecodeError:
                        continue
            except Exception as txt_error:
                return f"Error processing TXT: {txt_error}"

        elif file_type in ["jpg", "jpeg", "png"]:
            # Handle image files using OCR
            try:
                # Open image and perform OCR to extract text
                image = Image.open(io.BytesIO(file_bytes))
                ocr_text = pytesseract.image_to_string(image)
                if ocr_text:
                    total_text = ocr_text
            except Exception as img_error:
                return f"Error processing image: {img_error}"

    except Exception as e:
        return f"Unexpected error: {e}"

    return total_text

def extract_links_from_html(html_string: str):
    """
    Extract file links from HTML content.

    ================================================

    examples of input parameters:
    html_string = "<div><a href='https://example.com/file.pdf'>File</a></div>"

    ================================================

    examples of output:
    links_found = [{filename: fileurl}]

    ================================================
    
    """
    soup = BeautifulSoup(html_string, "html.parser")
    links_found = []
    for a in soup.find_all("a", href=True):
        url_found = a["href"]
        url_name = a.text or ""
        # Check if the link points to a supported file type
        if ".pdf" in url_name or ".txt" in url_name or ".rtf" in url_name or ".odt" in url_name or ".doc" in url_name or ".docx" in url_name or ".xlsx" in url_name or ".html" in url_name or ".md" in url_name or ".jpg" in url_name or ".png" in url_name or ".epub" in url_name or ".csv" in url_name or ".pptx" in url_name:
            links_found += [{url_name: url_found}]
    return links_found

async def get_all_user_data(BASE_DIR: str, API_URL: str, API_TOKEN: str, user_data: dict, courses_selected: dict):
    """
    Retrieves all user data from Canvas and returns it as a dictionary.

    ================================================

    examples of input parameters:
    BASE_DIR = "this is the base directory of the project"
    API_URL = "this is the api url of the canvas instance"
    API_TOKEN = "this is the api token of the canvas instance"
    user_data = "this is the user data dictionary"
    courses_selected = "this is the dictionary of courses selected by the user, paired with course id as the key and course name as the value"

    ================================================

    examples of output:
    user_data = {} (structure is below)

    ================================================

    dictionary structure:

    more detail within pipeline/user_data_structure.pdf

    user_data = {
        "user_metadata": {
            "user_id": __int__,
            "canvas_token_id": __int___,
            "canvas_domain": __str___,
            "data_last_updated": ___str___,
            "update_duration _ float__, courses_selected: {__int__: __str__}},
        "courses": [{
            COURSE OBJECT
        }],
        "files": [{
            FILE OBJECT
        }],
        "announcements": [{
            ANNOUNCEMENT OBJECT
        }],
        "assignments": [{
            ASSIGNMENT OBJECT
        }],
        "quizzes": [{
            QUIZ OBJECT
        }],
        "calendar_events": [{
            CALENDAR EVENT OBJECT
        }]
    }
    """
    print(f"these are the courses selected: {courses_selected}")
    print("\n=== Starting Data Collection ===")
    user_data = user_data

    # Initialize/reset all data arrays in user_data dictionary
    user_data["courses"] = []
    user_data["files"] = []
    user_data["announcements"] = []
    user_data["assignments"] = []
    user_data["quizzes"] = []
    user_data["calendar_events"] = []
    
    print("\n=== SECTION 1: Fetching Course Information ===")
    page_number = 1
    #data in Canvas API is pagenated, so you have to manually go through multiple pages in case there are more items of the type needed
    
    # getting courses
    #
    async with aiohttp.ClientSession() as session:
        while True: 
        #any "while True" function is always meant to go through multiple pages over and over until there's no more data left to retrieve
            headers = {"Authorization": f"Bearer {API_TOKEN}"}
            async with session.get(
                f"{API_URL}/courses/", 
                params={
                    "enrollment_state": "active", 
                    "include[]": ["all_courses", "syllabus_body"], 
                    "page": page_number
                },
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"Error fetching courses: {error_text}")
                    raise ValueError(f"Failed to fetch courses: {error_text}")
                    
                user_courses = await response.json()
                
                # Check if we got a dictionary with an error message instead of a list
                if isinstance(user_courses, dict) and "errors" in user_courses:
                    print(f"API Error: {user_courses['errors']}")
                    raise ValueError(f"API Error: {user_courses['errors']}")
                
                if not isinstance(user_courses, list):
                    print(f"Unexpected response format: {user_courses}")
                    raise ValueError("Unexpected response format from API")
                    
                if user_courses == []:
                    break
                
                for i in range(len(user_courses)):

                    #if the course is in the dictionary of courses selected by the user, then add it to the user_data dictionary
                    if str(user_courses[i].get("id")) in courses_selected:
                        
                        #if the course has no syllabus, then add an empty syllabus to the user_data dictionary
                        if user_courses[i].get("syllabus_body") is None:
                            user_data["courses"] += [{
                                "id": user_courses[i].get("id"),
                                "name": user_courses[i].get("name"),
                                "course_code": user_courses[i].get("course_code"),
                                "original_name": user_courses[i].get("original_name"),
                                "default_view": user_courses[i].get("course_code"),
                                "syllabus_body": [],
                                "public_description": user_courses[i].get("public_description"),
                                "time_zone": user_courses[i].get("time_zone"),
                                }]
                        #if the course has a syllabus, then add the syllabus to the user_data dictionary
                        else:
                            user_data["courses"] += [{
                                "id": user_courses[i].get("id"),
                                "name": user_courses[i].get("name"),
                                "course_code": user_courses[i].get("course_code"),
                                "original_name": user_courses[i].get("original_name"),
                                "default_view": user_courses[i].get("course_code"),
                                "syllabus_body": user_courses[i].get("syllabus_body"),
                                "public_description": user_courses[i].get("public_description"),
                                "time_zone": user_courses[i].get("time_zone"),
                                }]
                page_number += 1
    #all courses that have a syllabus section have now been added to the "user_data" dictionary

    print(f"\nFound {len(user_data['courses'])} courses to process")
    
    print("\n=== SECTION 2: Processing Individual Courses ===")
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {API_TOKEN}"}
        for course in user_data["courses"]:
            course_id = course.get("id")
            print(f"\nProcessing course: {course.get('name')} (ID: {course_id})")
            
            print("  - Getting modules and items...")
            files_added = []
            assignments_added = []
            quizzes_added = []
            page_number = 1

            while True:
                async with session.get(
                    f"{API_URL}/courses/{course_id}/modules",
                    params={"enrollment_state": "active", "include[]": "all_courses", "page": page_number},
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"Error fetching modules: {error_text}")
                        break
                        
                    course_modules = await response.json()
                
                    if type(course_modules) is list and course_modules != []:
                        for module in course_modules:
                            module_id = module.get("id")
                            module_name = module.get("name")
                            module_page_number = 1

                            while True:
                                async with session.get(
                                    f"{API_URL}/courses/{course_id}/modules/{module_id}/items",
                                    params={"enrollment_state": "active", "include[]": "all_courses", "page": module_page_number},
                                    headers=headers
                                ) as response:
                                    if response.status != 200:
                                        error_text = await response.text()
                                        print(f"Error fetching module items: {error_text}")
                                        break
                                        
                                    course_module_items = await response.json()
                                
                                    if type(course_module_items) is list and course_module_items != []:
                                        for module_item in course_module_items:
                                            item_type = module_item.get("type")
                                            
                                            if item_type == "File":
                                                
                                                if course["syllabus_body"] == []:
                                                    course["syllabus_body"] += [{
                                                        module_item.get("name"): module_item.get("content_id")
                                                    }]
                                                
                                                files_added += [module_item.get("content_id")]
                                                async with session.get(
                                                    f"{API_URL}/files/{module_item.get('content_id')}",
                                                    params={"enrollment_state": "active"},
                                                    headers=headers
                                                ) as response:
                                                    if response.status == 200:
                                                        file = await response.json()
                                                        user_data["files"] += [{
                                                            "course_id": course_id,
                                                            "id": file.get("id"),
                                                            "type": file.get("type"),
                                                            "folder_id": file.get("folder_id"),
                                                            "display_name": file.get("display_name"),
                                                            "filename": file.get("filename"),
                                                            "url": file.get("url"),
                                                            "size": file.get("size"),
                                                            "updated_at": file.get("updated_at"),
                                                            "locked": file.get("locked"),
                                                            "lock_explanation": file.get("lock_explanation"),
                                                            "module_id": module_id,
                                                            "module_name": module_name
                                                        }]
                                            elif item_type == "Assignment":
                                                assignments_added += [module_item.get("content_id")]
                                                async with session.get(
                                                    f"{API_URL}/courses/{course_id}/assignments/{module_item.get('content_id')}",
                                                    params={"enrollment_state": "active"},
                                                    headers=headers
                                                ) as response:
                                                    if response.status == 200:
                                                        assignment = await response.json()
                                                        user_data["assignments"] += [{
                                                            "id": assignment.get("id"),
                                                            "type": assignment.get("type"),
                                                            "name": assignment.get("name"),
                                                            "description": assignment.get("description"),
                                                            "created_at": assignment.get("created_at"),
                                                            "updated_at": assignment.get("updated_at"),
                                                            "due_at": assignment.get("due_at"),
                                                            "course_id": assignment.get("course_id"),
                                                            "submission_types": assignment.get("submission_types"),
                                                            "can_submit": assignment.get("can_submit"),
                                                            "graded_submission_exist": assignment.get("graded_submission_exist"),
                                                            "can_submit": assignment.get("can_submit"),
                                                            "graded_submissions_exist": assignment.get("graded_submission_exist"),
                                                            "module_id": module_id,
                                                            "module_name": module_name,
                                                            "content": extract_links_from_html(assignment.get("description") or "")
                                                        }]
                                            elif item_type == "Quiz":
                                                quizzes_added += [module_item.get("content_id")]
                                                async with session.get(
                                                    f"{API_URL}/courses/{course_id}/quizzes/{module_item.get('content_id')}",
                                                    params={"enrollment_state": "active"},
                                                    headers=headers
                                                ) as response:
                                                    if response.status == 200:
                                                        quiz = await response.json()
                                                        user_data["quizzes"] += [{
                                                            "id": quiz.get("id"),
                                                            "title": quiz.get("title"),
                                                            "preview_url": quiz.get("preview_url"),
                                                            "description": quiz.get("description"),
                                                            "quiz_type": quiz.get("quiz_type"),
                                                            "time_limit": quiz.get("time_limit"),
                                                            "allowed_attempts": quiz.get("allowed_attempts"),
                                                            "points_possible": quiz.get("points_possible"),
                                                            "due_at": quiz.get("due_at"),
                                                            "locked_for_user": quiz.get("locked_for_user"),
                                                            "lock_explanation": quiz.get("lock_explanation"),
                                                            "module_id": module_id,
                                                            "module_name": module_name,
                                                            "course_id": course_id
                                                        }]
                                    else:
                                        break
                                    module_page_number += 1
                    else:
                        break
                    page_number += 1

            # getting extra files
            #
            print("  - Getting additional files...")
            page_number = 1

            while True:
                async with session.get(
                    f"{API_URL}/courses/{course_id}/files",
                    params={"enrollment_state": "active", "include[]": "all_courses", "page": page_number},
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"Error fetching files: {error_text}")
                        break
                        
                    course_files = await response.json()
                
                    
                    if type(course_files) is list and course_files != []:
                        for i in range(len(course_files)):
                            #stores the file_name and file_URL of the syllabus if syllabus_body is a list
                            #syllabus_body is a list if the course has no syllabus_body to begin with
                            if type(course.get("syllabus_body")) is list and course_files[i].get("name") and "syllabus" in course_files[i].get("name"):
                                course["syllabus_body"] += [{
                                    course_files[i].get("name"): course_files[i].get("url")
                                }]
                            
                            if course["syllabus_body"] == [] and type(course.get("syllabus_body")) is list and course_files[i].get("name") and "syllabus" in course_files[i].get("name"):
                                course["syllabus_body"] += [{
                                course_files[i].get("filename"): course_files[i].get("url")
                            }]

                            #stores the file object if the file is not already in the files_added list
                            if course_files[i].get("id") not in files_added:
                                user_data["files"] += [{
                                    "course_id": course_id,
                                    "id": course_files[i].get("id"),
                                    "type": course_files[i].get("type"),
                                    "folder_id": course_files[i].get("folder_id"),
                                    "display_name": course_files[i].get("display_name"),
                                    "filename": course_files[i].get("filename"),
                                    "url": course_files[i].get("url"),
                                    "size": course_files[i].get("size"),
                                    "updated_at": course_files[i].get("updated_at"),
                                    "locked": course_files[i].get("locked"),
                                    "lock_explanation": course_files[i].get("lock_explanation"),
                                    "module_id": None,
                                    "module_name": None
                                }]
                    else:
                        break
                    page_number += 1
            #
            # getting files

            # getting announcements
            #
            print("  - Getting announcements...")
            for i in range(1, 3, 1):
                async with session.get(
                    f"{API_URL}/announcements",
                    params={
                        "pager": i,
                        "context_codes[]": [f"course_{course_id}"],
                        "enrollment_state": "active"
                    },
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"Error fetching announcements: {error_text}")
                        break
                        
                    announcements = await response.json()
                    
                    for announcement in announcements:
                        user_data["announcements"] += [{
                            "id": announcement.get("id"),
                            "title": announcement.get("title"),
                            "message": announcement.get("message"),
                            "course_id": course_id,
                            "posted_at": announcement.get("posted_at"),
                            "discussion_type": announcement.get("discussion_type"),
                            "course_name": course.get("name")
                        }]

            # getting calendar events
            #
            print("  - Getting calendar events...")
            calendar_events = await find_events(API_URL, API_TOKEN, f"course_{course_id}", session)
            
            if calendar_events:
                for event in calendar_events:
                    user_data["calendar_events"] += [{
                        "id": event.get("id"),
                        "title": event.get("title"),
                        "start_at": event.get("start_at"),
                        "end_at": event.get("end_at"),
                        "description": event.get("description"),
                        "location_name": event.get("location_name"),
                        "location_address": event.get("location_address"),
                        "context_code": event.get("context_code"),
                        "context_name": event.get("context_name"),
                        "all_context_codes": event.get("all_context_codes"),
                        "url": event.get("url"),
                        "course_id": course_id
                    }]

            # getting home page
            #
            print("  - Checking for home page...")
            if course.get("syllabus_body") == [] or course.get("syllabus_body") is None or course.get("syllabus_body") == "":
                try:
                    async with session.get(
                        f"{API_URL}/courses/{course_id}/front_page",
                        params={"enrollment_state": "active"},
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            home_page = await response.json()
                            course.update({"syllabus_body": home_page.get("front_page")})
                except Exception as e:
                    print(f"Error fetching home page: {str(e)}")
                    pass
            #
            # getting home page
           
            # updating syllabi
            #
            print("  - Processing syllabus content...")
            course_syllabus = course.get("syllabus_body")
            if course_syllabus:  
                
                if isinstance(course_syllabus, str):
                    # Handle case where syllabus is HTML content with embedded links
                    links = extract_links_from_html(course_syllabus)
                    
                    if links:  
                        final_text = await get_text_from_links(links, API_URL, API_TOKEN)
                        course_syllabus += f"\n\n{final_text}"
                
                elif isinstance(course_syllabus, list):
                    # Handle case where syllabus is a list of direct file link objects
                    final_text = ""
                    for link in course_syllabus:
                        final_text += await get_text_from_links(link, API_URL, API_TOKEN)
                    course_syllabus = final_text

                # update the course with the processed syllabus
                course.update({"syllabus_body": course_syllabus})
            #
            # updating syllabi

            # getting assignments
            # 
            print("  - Getting assignments...")
            page_number = 1
            
            while True:
                async with session.get(
                    f"{API_URL}/courses/{course_id}/assignments",
                    params={"enrollment_state": "active", "page": page_number},
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"Error fetching assignments: {error_text}")
                        break
                        
                    course_assignments = await response.json()

                    if type(course_assignments) is list and course_assignments != []:
                        for i in range(len(course_assignments)):
                            if course_assignments[i].get("id") not in assignments_added:
                                user_data["assignments"] += [{
                                    "id": course_assignments[i].get("id"),
                                    "type": course_assignments[i].get("type"),
                                    "name": course_assignments[i].get("name"),
                                    "description": course_assignments[i].get("description"),
                                    "created_at": course_assignments[i].get("created_at"),
                                    "updated_at": course_assignments[i].get("updated_at"),
                                    "due_at": course_assignments[i].get("due_at"),
                                    "course_id": course_id,
                                    "submission_types": course_assignments[i].get("submission_types"),
                                    "can_submit": course_assignments[i].get("can_submit"),
                                    "graded_submission_exist": course_assignments[i].get("graded_submission_exist"),
                                    "can_submit": course_assignments[i].get("can_submit"),
                                    "graded_submissions_exist": course_assignments[i].get("graded_submission_exist"),
                                    "module_id": None,
                                    "module_name": None,
                                    "content": extract_links_from_html(course_assignments[i].get("description") or "")
                                }]
                    else:
                        break
                    page_number += 1

            # getting quizzes
            # 
            print("  - Getting quizzes...")
            page_number = 1
            
            while True:
                async with session.get(
                    f"{API_URL}/courses/{course_id}/quizzes",
                    params={"enrollment_state": "active", "page": page_number},
                    headers=headers
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"Error fetching quizzes: {error_text}")
                        break
                        
                    course_quizzes = await response.json()

                    if type(course_quizzes) is list and course_quizzes != []:
                        for i in range(len(course_quizzes)):
                            if course_quizzes[i].get("id") not in quizzes_added:
                                user_data["quizzes"] += [{
                                    "id": course_quizzes[i].get("id"),
                                    "title": course_quizzes[i].get("title"),
                                    "preview_url": course_quizzes[i].get("preview_url"),
                                    "description": course_quizzes[i].get("description"),
                                    "quiz_type": course_quizzes[i].get("quiz_type"),
                                    "time_limit": course_quizzes[i].get("time_limit"),
                                    "allowed_attempts": course_quizzes[i].get("allowed_attempts"),
                                    "points_possible": course_quizzes[i].get("points_possible"),
                                    "due_at": course_quizzes[i].get("due_at"),
                                    "locked_for_user": course_quizzes[i].get("locked_for_user"),
                                    "lock_explanation": course_quizzes[i].get("lock_explanation"),
                                    "module_id": None,
                                    "module_name": None,
                                    "course_id": course_id
                                }]
                    else:
                        break
                    page_number += 1

    print("\n=== SECTION 3: Finalizing Data Collection ===")
    user_data_json = json.dumps(user_data)
    user_data_size_bytes = len(user_data_json.encode('utf-8'))
    print(f"\nTotal size of user_data: {user_data_size_bytes:,} bytes")
    print(f"Size in MB: {user_data_size_bytes / (1024 * 1024):.2f} MB")
    print("\n=== Data Collection Complete ===")

    duplicates = check_for_duplicates(user_data)
    print(f"\nDuplicates: {duplicates}")

    return user_data


def check_for_duplicates(user_data):
    """
    Checks for duplicate entries in the user_data dictionary.
    
    Parameters:
    -----------
    user_data : dict
        The user data dictionary containing courses, files, announcements, assignments, quizzes, etc.
        
    Returns:
    --------
    dict
        A dictionary containing counts of duplicates found in each category.
    """
    duplicate_counts = {
        "courses": 0,
        "files": 0,
        "announcements": 0,
        "assignments": 0,
        "quizzes": 0,
        "calendar_events": 0
    }
    
    # Check each category for duplicates
    for category in duplicate_counts.keys():
        if category not in user_data or not isinstance(user_data[category], list):
            continue
            
        # Use sets to track IDs we've seen
        seen_ids = set()
        unique_items = []
        
        for item in user_data[category]:
            if not isinstance(item, dict) or "id" not in item:
                unique_items.append(item)
                continue
                
            item_id = item["id"]
            if item_id in seen_ids:
                duplicate_counts[category] += 1
            else:
                seen_ids.add(item_id)
                unique_items.append(item)
        
        # Replace the original list with the deduplicated list
        user_data[category] = unique_items
    
    return duplicate_counts