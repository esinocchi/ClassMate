import requests
import os
import json
from dotenv import load_dotenv 
from bs4 import BeautifulSoup


BASE_DIR = "Desktop/Projects/"
#Update on your own to before the actual CanvasAI directory e.g. mine is f"{BASE_DIR}CanvasAI/" to access anything

API_URL = "https://psu.instructure.com/api/v1" #Base URL 
load_dotenv()


API_TOKEN = os.getenv("CANVAS_API_TOKEN")

def test():
   users = requests.get(f"{API_URL}/user", headers = {"Authorization": f"Bearer {API_TOKEN}"}).json() 
   for user in users:
      print(user.get("id"))

def extract_links_from_html(html_string: str):
   soup = BeautifulSoup(html_string, "html.parser")
   links_found = []
   for a in soup.find_all("a", href=True):
      url_found = a["href"]
      url_name = a.text
      
   if ".pdf" in url_name or ".txt" in url_name or ".rtf" in url_name or ".odt" in url_name or ".doc" in url_name or ".docx" in url_name or ".xlsx" in url_name or ".html" in url_name or ".md" in url_name or ".jpg" in url_name or ".png" in url_name or ".epub" in url_name or ".csv" in url_name or ".pptx" in url_name:
      links_found += [{url_name: url_found}]
   return links_found

def turn_urls_into_large_string(url_list_of_dicts: list):
   url_data_string = ""

   for file_dict in url_list_of_dicts:
         
         response = requests.get(url, headers={"Authorization": f"Bearer {API_TOKEN}"}, stream=True)
         file_type = get_file_type_from_file_name()
         with open(f"{BASE_DIR}CanvasAI/media_output/lecture_file.pdf", "wb") as file:
            for data in response.iter_content(chunk_size=4096):
                file.write(data)
   return

def get_file_type_from_file_name(file_name: str):
   file_type = ""
   i = len(file_name)
   
   while file_name[i] != ".":
      file_type = file_name[i] + file_type
      i -= 1
   file_type = "." + file_type
   
   return file_type

def get_all_user_data():  
   """
   no input --> returns a "user_data" dictionary in this format: {"course_name": {"course_ID": course_ID#, "course_files": { "file_name" : file_URL}}, "course_syllabus": complete_syllabus_string}
   
   """

   user_data = {} 
   page_number = 1
   #data in Canvas API is pagenated, so you have to manually go through multiple pages in case there are more items of the type needed
   
   while True: 
   #any "while True" function is always meant to go through multiple pages over and over until there's no more data left to retrieve
      user_courses = requests.get(f"{API_URL}/courses/", params={"enrollment_state": "active", "include[]": ["all_courses", "syllabus_body"], "page": page_number, "access_token": {API_TOKEN}}).json() 
      if user_courses == []:
         break

      for i in range(len(user_courses)):
         user_data[user_courses[i].get("name")] = {"course_ID": user_courses[i].get("id"), "course_files": {}, "course_syllabus": user_courses[i].get("syllabus_body")}
      page_number += 1
   #all courses that have a syllabus section have now been added to the "user_data" dictionary

   page_number = 1
   
   while True: 
   #go back and add courses that don't have their syllabus explicitly posted
      user_courses = requests.get(f"{API_URL}/courses/", params={"enrollment_state": "active", "include[]": "all_courses", "page": page_number, "access_token": {API_TOKEN}}).json() 
      if user_courses == []:
         break

      for i in range(len(user_courses)):
         if user_courses[i].get("name") not in user_data:
            user_data[user_courses[i].get("name")] = {"course_ID": user_courses[i].get("id"), "course_files": {}, "course_syllabus": []}
      page_number += 1
   #all courses have now been added to the "user_data" dictionary

   for course in user_data:
      course_ID = user_data[course]["course_ID"]
      page_number = 1
      
      if user_data[course]["course_syllabus"] is None:
         user_data[course]["course_syllabus"] = []

      while True:
         user_course_files = requests.get(f"{API_URL}/courses/{course_ID}/files", params={"enrollment_state": "active", "include[]": "all_courses", "page": page_number, "access_token": {API_TOKEN}}).json()
         
         if type(user_data[course]["course_syllabus"]) is list and type(user_course_files) is list and user_course_files != []:
            user_data[course]["course_syllabus"] += [user_course_files[0].get("url")]

         if type(user_course_files) is list and user_course_files != []:
            for i in range(len(user_course_files)):
               
               if type(user_data[course]["course_syllabus"]) is list and user_course_files[i].get("name") and "syllabus" in user_course_files[i].get("name"):
                  user_data[course]["course_syllabus"] += [user_course_files[i].get("url")]
               #stores the file_name and file_URL of the syllabus if found
               
               user_data[course]["course_files"][user_course_files[i].get("name")] = user_course_files[i].get("url")
         else:
            break
         page_number += 1
   #for each course, look through every page of files if allowed access (checked by "type(user_course_files) is list") and add them to user_data
      page_number = 1

      while True:
         user_course_modules = requests.get(f"{API_URL}/courses/{course_ID}/modules", params={"enrollment_state": "active", "include[]": "all_courses", "page": page_number, "access_token": {API_TOKEN}}).json()
         
         if type(user_course_modules) is list and user_course_modules != []:
         #gets the users modules

            for i in range(len(user_course_modules)):
               module_ID = user_course_modules[i].get("id")
               module_item_page_number = 1
               
               while True:
                  module_items = requests.get(f"{API_URL}/courses/{course_ID}/modules/{module_ID}/items", params={"enrollment_state": "active", "include[]": "all_courses", "page": module_item_page_number, "access_token": {API_TOKEN}}).json()
                  
                  if type(module_items) is list and module_items != []:
                     if type(user_data[course]["course_syllabus"]) is list and len(module_items) > 0:
                        user_data[course]["course_syllabus"] += [module_items[0].get("url")]

                  if type(module_items) is list and module_items != []:
                  #for each module, there are module items, so we have to iterate within each module as well

                     for i in range(len(module_items)):
                       
                        if module_items[i].get("type") == "File":
                        #if the module item is a file, store the file_name and file_URL
                           module_item_name = module_items[i].get("title")
                           
                           if module_item_name not in user_data[course]["course_files"]:
                              
                              if type(user_data[course]["course_syllabus"]) is list and "syllabus" in module_items[i].get("title"):
                                 user_data[course]["course_syllabus"] += [module_items[i].get("url")]
                              user_data[course]["course_files"][module_items[i].get("title")] = module_items[i].get("url")
                  else:
                     break
                  module_item_page_number += 1
         else:
            break
         page_number += 1

      
      #user_course_front_page = requests.get(f"{API_URL}/courses/{course_ID}/front_page", params={"enrollment_state": "active", "include[]": "all_courses", "access_token": {API_TOKEN}}).json()
      #print(course)
      #print(user_course_front_page)

   for course in user_data:
      print(type(user_data[course]["course_syllabus"]))
      if type(user_data[course]["course_syllabus"]) == str:
         print(extract_links_from_html(user_data[course]["course_syllabus"]))
      else:
         print(user_data[course]["course_syllabus"])

   json_string = json.dumps(user_data)
   #converts dictionary object into a JSON string  
   
   user_id = "1234"  # Replace with the actual user ID if needed
   user_data_path = f"{BASE_DIR}CanvasAI/UserData/{API_URL}/{user_id}/user_data.json"  
   os.makedirs(os.path.dirname(user_data_path), exist_ok=True)
   #"creates" a directory per user in the UserData directory: School URL then User ID

   with open(user_data_path, "w", encoding="utf-8") as f:
      f.write(json_string)
   #succesfully updates the user_data
   
   return "succesful"

print(get_all_user_data())


   
