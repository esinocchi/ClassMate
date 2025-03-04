import io
import os
import requests
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from prompt_to_file_GPT import prompt_to_pdf
from dotenv import load_dotenv

BASE_DIR = "Penn State/Projects/CanvasAI/"
#Update on your own to before the actual CanvasAI directory e.g. mine is f"{BASE_DIR}CanvasAI/" to access anything

load_dotenv(f"{BASE_DIR}CanvasAI/.env")

API_URL = "https://psu.instructure.com/api/v1" #Base URL 
API_TOKEN = os.getenv("CANVAS_API_TOKEN")

def extract_text_and_images(pdf_file_URL: str):
    total_text = ""
    doc = fitz.open(pdf_file_URL)
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # Extract text

        text = page.get_text()
        total_text += f"Text from page :\n{text}\n"

        # Extract images
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image = Image.open(io.BytesIO(image_bytes))
            # Perform OCR on the image
            ocr_text = pytesseract.image_to_string(image)
            total_text += f"image {img_index}:\n{ocr_text}\n"
    return total_text
    


def lecture_file_to_notes_pdf(course: str, lecture_file: str):
    """
    (course name, lecture file name)

    """
    courses_found = find_course(course)
    if len(courses_found) > 1:
        return "Multiple courses matched to user input"
    if len(courses_found) < 1:
        return "No courses matched to user input"
    for course in courses_found:
        course_id = courses_found[course]
    #first find the course_id of the matched course
    #then use the course_id to find the lecture file

    item_found = find_module_item(course_id, lecture_file)
    if type(item_found) == str:
        item_found = find_file_from_course(course_id, lecture_file)
        if type(item_found) == str:
            return "ERROR: item couldn't be found"
    #looks for file in modules first and if type(item_found) is a string, then it's equal to "ERROR: cannot access modules from course" and not a dictionary
    #so, it instead looks through the courses files for the file
    #if type(item_found) is yet again a string, then it's equal to "ERROR: cannot access files from course" and not a dictionary

    if len(item_found) > 1:
        return "Multiple items matched to user input"
    if len(item_found) < 1:
        return "No items matched to user input"
    for item in item_found:
        if item_found[item][1] != "File":
            return "Item not a file"
        item_found_url = item_found[item][0]
    #after finding the item, if the item is a file, save its URL (checking becuase we might've also searched through modules)
    
    try:
        file_content = requests.get(item_found_url, headers={"Authorization": f"Bearer {API_TOKEN}"}).json()
        file_url = file_content.get("url")
    except:
        return "ERROR: file content cannot be received"
    #try to retrieve the files content, then save its URL
    #if not working return Error

    try:
        response = requests.get(file_url, headers={"Authorization": f"Bearer {API_TOKEN}"}, stream=True)
        with open(f"{BASE_DIR}CanvasAI/media_output/lecture_file.pdf", "wb") as file:
            for data in response.iter_content(chunk_size=4096):
                file.write(data)
    except:
        return "ERROR: file cannot be downloaded"
    #try to get files raw data to write into a new file on our system
    #if not working return Error

    try:
        file_text = extract_text_and_images(f"{BASE_DIR}CanvasAI/media_output/lecture_file.pdf")
        os.remove(f"{BASE_DIR}CanvasAI/media_output/lecture_file.pdf")
    except:
        return "File text could not be extracted"
    print(file_text)
    #try to exctract the text from a file
    #if not working return Error

    try:
        prompt_to_pdf_status = "ERROR: pdf couldn't be created"
        while prompt_to_pdf_status == "ERROR: pdf couldn't be created":
            prompt_to_pdf_status = prompt_to_pdf(file_text)
    except:
        return "ERROR: pdf input not accepted"
    #create a while loop to always keep trying to process the input text into a detailed pdf of notes
    #if not working return Error
    
    return "Lecture file to notes pdf succesful"
    
def find_courses(): 
    """
    (potential course name)

    """
    headers = {'Authorization': f'Bearer {canvas_api_token}'}
params = {
    "enrollment_state": "active",
    "include[]": "all_courses",
    "per_page": 100  # Fetch more courses per page (optional)
}

course_name_list = []
url = f"{canvas_api_url}/courses"
page_counter = 1

while url:
    print(f"\n--- Page {page_counter} ---")
    print(f"Requesting URL: {url}")

    response = requests.get(url, headers=headers, params=params)
    params = None  # Clear params after the first request

    # Handle errors
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        break

    # Extract course names
    courses = response.json()
    print(f"Found {len(courses)} courses on this page.")
    for course in courses:
        course_name = course.get('name')
        if course_name:
            course_name_list.append(course_name)

    # Parse the "Link" header for pagination
    link_header = response.headers.get('Link', '')
    next_url = None

    if link_header:
        links = link_header.split(', ')
        for link in links:
            parts = link.split('; ', 1)
            if len(parts) != 2:
                continue
            url_part, rel_part = parts
            url_part = url_part.strip('<>')
            rel_value = rel_part.replace('rel=', '').strip('"').lower()
            
            if 'next' in rel_value.split():
                next_url = url_part
                break  # Found the next page URL

    # Update URL or terminate the loop
    if next_url:
        print(f"Next page URL: {next_url}")
        url = next_url
    else:
        print("No more pages found.")
        url = None  # Exit the loop

    page_counter += 1

    # Safety check to prevent infinite loops
    if page_counter > 50:
        print("\n Safety Break: Stopped after 50 pages.")
        break

    return 

def find_module_item(course_id: str, input_file_name: str):
    """
    (7 digit # course id, potential file name)

    """
    try:
        modules_list = requests.get(f"{API_URL}/courses/{course_id}/modules", headers = {"Authorization": f"Bearer {API_TOKEN}"}).json()
    except:
        return "ERROR: cannot access modules from course"
    #jsons a list object of module objects into modules_list

    potential_module_items = {}
    for i in range(len(modules_list)):
        module_items_list = requests.get(f"{API_URL}/courses/{course_id}/modules/{modules_list[i].get('id')}/items", headers = {"Authorization": f"Bearer {API_TOKEN}"}).json()
    #uses the module id from each module object to get a list of module item objects

        for j in range(len(module_items_list)):
            module_item_name = module_items_list[j].get("title")
            if text_formatter_for_simplicity(input_file_name) in text_formatter_for_simplicity(module_item_name):
                potential_module_items[module_items_list[j].get("title")] = [module_items_list[j].get("url"), module_items_list[j].get("type")]
                print(f"module items: {potential_module_items}")
        #for each module item object in a module, if the module item name is close enough to the input_file_name given, it saves it
        #saves it as {"title": ["URL", "type"]} into potential_module_items

    return potential_module_items

def text_formatter_for_simplicity(input: str):
    """
    (input to simplify)
    
    """
    formatted_str = input.replace(" ", "").replace("-", "").lower()
    #removes spaces, underscores, and lowercases every letter
    
    return formatted_str

def find_file_from_course(course_id: str, potential_file_name: str):
    """
    (7 digit # course id, potential file name)

    """
    try:
        file_list = requests.get(f"{API_URL}/courses/{course_id}/files/", headers={"Authorization": f"Bearer {API_TOKEN}"}).json()
        potential_files = {}
        for i in range(len(file_list)):
            print(f"files: {potential_file_name}")
            print(f"{file_list[i].get('filename')}")
            if text_formatter_for_simplicity(potential_file_name) in text_formatter_for_simplicity(file_list[i].get("filename")):
                potential_files[file_list[i].get("filename")] = [file_list[i].get("url"), "File"]
        return potential_files
    except:
        return "ERROR: cannot access files from course"
    #try to access files section in a course. If working, list files that are close to input
    #if files cannot be accessed, return Error
