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
 
 # Import calendar_agent directly from task_specific_agents (sibling directory)
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)
from task_specific_agents.calendar_agent import find_events
 
load_dotenv()
 
def get_text_from_links(links: list, API_URL: str, API_TOKEN: str):
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
                 response = requests.get(api_url, headers=headers)
                 
                 if response.status_code != 200:
                     continue
 
                 # Extract the actual download URL from the file metadata
                 file_data = response.json()
                 download_url = file_data.get('url')
                 
                 if not download_url:
                     continue
 
                 # Second request: Download the actual file content
                 file_response = requests.get(download_url, headers=headers)
 
                 if file_response.status_code != 200:
                     continue
 
                 # Get the raw file content as bytes
                 file_bytes = file_response.content
 
                 # Determine the file type from the filename extension
                 file_type = get_file_type(filename)
 
                 # Process the file based on its type and extract text
                 extracted_text = extract_text_and_images(file_bytes, file_type)
                 complete_text += f"\nText from {filename}:\n{extracted_text}\n\n"
             except Exception:
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
                             total_text += f"Text from page {page_num + 1}:\n{text}\n"
 
                         # Extract and process images from the page
                         image_list = page.get_images(full=True)
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
 
def get_all_user_data(BASE_DIR: str, API_URL: str, API_TOKEN: str, user_data: dict, courses_selected: list):  
     """
     Retrieves all user data from Canvas and returns it as a dictionary.
 
     ================================================
 
     examples of input parameters:
     BASE_DIR = "this is the base directory of the project"
     API_URL = "this is the api url of the canvas instance"
     API_TOKEN = "this is the api token of the canvas instance"
     user_data = "this is the user data dictionary"
     courses_selected = "this is the list of courses selected by the user"
 
     ================================================
 
     examples of output:
     user_data = {} (structure is below)
 
     ================================================
 
     dictionary structure:
     user_data = {
         "user_metadata": {
             "user_id": __int__,
             "canvas_token_id": __int___,
             "canvas_domain": __str___,
             "data_last_updated": ___str___,
             "update_duration _ float__, courses_selected: []},
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
     while True: 
     #any "while True" function is always meant to go through multiple pages over and over until there's no more data left to retrieve
         user_courses = requests.get(f"{API_URL}/courses/", params={"enrollment_state": "active", "include[]": ["all_courses", "syllabus_body"], "page": page_number, "access_token": API_TOKEN}).json() 
         if user_courses == []:
             break
         
         for i in range(len(user_courses)):
             
             #if the course is in the list of courses selected by the user, then add it to the user_data dictionary
             if user_courses[i].get("id") in courses_selected:
                 
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
     for course in user_data["courses"]:
       course_id = course.get("id")
       print(f"\nProcessing course: {course.get('name')} (ID: {course_id})")
       
       print("  - Getting modules and items...")
       files_added = []
       assignments_added = []
       quizzes_added = []
       page_number = 1
 
       while True:
         course_modules = requests.get(f"{API_URL}/courses/{course_id}/modules", params={"enrollment_state": "active", "include[]": "all_courses", "page": page_number, "access_token": API_TOKEN}).json()
         
         #if the course has modules, then add the modules to the user_data dictionary
         if type(course_modules) is list and course_modules != []:
             
             for module in course_modules:
                module_id = module.get("id")
                module_name = module.get("name")
                module_page_number = 1
 
                # getting module items
                #
                while True:
                   course_module_items = requests.get(f"{API_URL}/courses/{course_id}/modules/{module_id}/items", params={"enrollment_state": "active", "include[]": "all_courses", "page": module_page_number, "access_token": API_TOKEN}).json()
                   
                   #if the module within a course has module items, then add the module items to the user_data dictionary
                   if type(course_module_items) is list and course_module_items != []:
                     
                     #for each module item in the course, add the module item to the user_data dictionary according to the type of module item
                     for module_item in course_module_items:
                        
                         item_type = module_item.get("type")
                        
                         if item_type == "File":
                             files_added += [module_item.get("content_id")]
                             file = requests.get(f"{API_URL}/files/{module_item.get('content_id')}", params={"enrollment_state": "active", "access_token": API_TOKEN}).json()
                             user_data["files"] += [{
                                 "course_id": course_id,
                                 "id": file.get("id"),
                                 "type": "file",
                                 "file_extension": get_file_type(file.get("display_name") or ""),
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
                             assignment = requests.get(f"{API_URL}/courses/{course_id}/assignments/{module_item.get('content_id')}", params={"enrollment_state": "active", "access_token": API_TOKEN}).json()
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
                            quiz = requests.get(f"{API_URL}/courses/{course_id}/quizzes/{module_item.get('content_id')}", params={"enrollment_state": "active", "access_token": API_TOKEN}).json()
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
 
                #
                # getting module items
                
         else:
            break
         page_number += 1
       #
       # getting modules
 
 
       # getting extra files
       #
       print("  - Getting additional files...")
       page_number = 1
 
       while True:
          course_files = requests.get(f"{API_URL}/courses/{course_id}/files", params={"enrollment_state": "active", "include[]": "all_courses", "page": page_number, "access_token": API_TOKEN}).json()
          
          if type(course_files) is list and course_files != []:
             
             for i in range(len(course_files)):
                
                #stores the file_name and file_URL of the syllabus if syllabus_body is a list
                #syllabus_body is a list if the course has no syllabus_body to begin with
                if type(course.get("syllabus_body")) is list and course_files[i].get("name") and "syllabus" in course_files[i].get("name"):
                     course["syllabus_body"] += [{
                         course_files[i].get("name"): course_files[i].get("url")
                     }]
                
                
                
                #stores the file object if the file is not already in the files_added list
                if course_files[i].get("id") not in files_added:
                   # Get file extension using your existing function
                   file_extension = get_file_type(course_files[i].get("display_name") or "")
                   
                   user_data["files"] += [{
                         "course_id": course_id,
                         "id": course_files[i].get("id"),
                         "type": "file",  # Explicitly set type to 'file'
                         "file_extension": file_extension,  # Store the extension in a separate field
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
 
       # getting assignments
       # 
       print("  - Getting assignments...")
       page_number = 1
       
       while True:
          course_assignments = requests.get(f"{API_URL}/courses/{course_id}/assignments", params={"enrollment_state": "active", "page": page_number, "access_token": API_TOKEN}).json()
 
          if type(course_assignments) is list and course_assignments != []:
             
             for i in range(len(course_assignments)):
                
                #stores the assignment object if the assignment is not already in the assignments_added list
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
       #
       # getting assignments
 
       # getting quizzes
       # 
       print("  - Getting quizzes...")
       page_number = 1
       
       while True:
          course_quizzes = requests.get(f"{API_URL}/courses/{course_id}/quizzes", params={"enrollment_state": "active", "page": page_number, "access_token": API_TOKEN}).json()
 
          if type(course_quizzes) is list and course_quizzes != []:
             
             for i in range(len(course_quizzes)):
                 
                 #stores the quiz object if the quiz is not already in the quizzes_added list
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
       # 
       # getting quizzes    
 
       # getting announcements
       #
       print("  - Getting announcements...")
       for i in range(1, 3, 1):
         announcements = requests.get(f"{API_URL}/announcements", params={"pager": i, "context_codes[]": [f"course_{course_id}"],"enrollment_state": "active", "access_token": API_TOKEN}).json()
        
         #if the course has announcements, then add the announcements to the user_data dictionary
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
       #
       # getting announcements
 
       # getting calendar events
       #
       print("  - Getting calendar events...")
       page_number = 1
 
       #url_without_api = API_URL.split("/api")[0]
       calendar_events = find_events(API_URL, API_TOKEN, f"course_{course_id}")
             
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
 
       #
       # getting calendar events
       
       # getting home page
       #
       
       print("  - Checking for home page...")
       #if the course has no syllabus, then add the home page as the syllabus_body
       if course.get("syllabus_body") == [] or course.get("syllabus_body") is None or course.get("syllabus_body") == "":
         
         #try to get the home page to update the syllabus_body
         try:
             home_page = requests.get(f"{API_URL}/courses/{course_id}/front_page", params={"enrollment_state": "active", "access_token": API_TOKEN}).json()
             course.update({"syllabus_body": home_page.get("front_page")})
         except:
             #if the home page is not found, then pass
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
                   final_text = get_text_from_links(links, API_URL, API_TOKEN)
                   course_syllabus += f"\n\n{final_text}"
           
           elif isinstance(course_syllabus, list):
             # Handle case where syllabus is a list of direct file link objects
               final_text = ""
               for link in course_syllabus:
                     final_text += get_text_from_links(link, API_URL, API_TOKEN)
               course_syllabus = final_text
 
           # update the course with the processed syllabus
           course.update({"syllabus_body": course_syllabus})
       #
       # updating syllabi
 
     print("\n=== SECTION 3: Finalizing Data Collection ===")
     
     # Remove duplicates from all collections
     print("  - Removing duplicate entries...")
     user_data = remove_duplicates(user_data)
     
     user_data_json = json.dumps(user_data)
     user_data_size_bytes = len(user_data_json.encode('utf-8'))
     print(f"\nTotal size of user_data: {user_data_size_bytes:,} bytes")
     print(f"Size in MB: {user_data_size_bytes / (1024 * 1024):.2f} MB")
     print("\n=== Data Collection Complete ===")
 
     return user_data

def remove_duplicates(user_data: dict) -> dict:
    """
    Remove duplicate items from all collections in the user_data dictionary.
    Items are considered duplicates if they have the same ID.
    
    Args:
        user_data: The complete user data dictionary
        
    Returns:
        The user data dictionary with duplicates removed
    """
    # Collections that need duplicate checking
    collections = ['files', 'assignments', 'announcements', 'quizzes', 'calendar_events']
    
    for collection in collections:
        if collection in user_data:
            # Track seen IDs and unique items
            seen_ids = set()
            unique_items = []
            duplicates_removed = 0
            
            for item in user_data[collection]:
                # Get the ID of the item
                item_id = str(item.get('id'))
                
                # If we haven't seen this ID before, add it to our unique items
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    unique_items.append(item)
                else:
                    duplicates_removed += 1
            
            # Replace the collection with the deduplicated list
            user_data[collection] = unique_items
            
            if duplicates_removed > 0:
                print(f"    - Removed {duplicates_removed} duplicate {collection}")
    
    return user_data