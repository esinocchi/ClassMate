"""
{ 
user_metadata: {user_id: __int__, canvas_token_id: __int___, canvas_domain: __str___, data_last_updated: ___str___, update_duration _ float__, courses_selected: []},

 courses : {
course_id:  {name: ___str__, code: _____, description: _____, workflow_state:______, syllabus_body: _____, default_view: ______, course_format: _____}}

items: [{id: ____, name:  _____, course_id: ____, type: ___, content: _____, url: ____, file_type: ____, size_kb: ___, created_at: ______, updated_at: ______, due_date: ______, points_possible: _____, points_earned: _____ , module_name: _____, start_date: ______, end_date: ______}, ]


}

Items: files, assignment, announcement, quiz, page, event

"""


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

def get_all_user_data():  
    """
    { 
    user_metadata: {user_id: __int__, canvas_token_id: __int___, canvas_domain: __str___, data_last_updated: ___str___, update_duration _ float__, courses_selected},

    courses : {
    course_id:  {id: __int__, name: ___str__, code: _____, description: _____, workflow_state:______, syllabus_body: _____, default_view: ______, course_format: _____}}

    items: [id: ____, Course_id: ____, type: ___, content: _____, url: ____, file_type: ____, size_kb: ___, content_id: _____, created_at: ______, updated_at: ______, due_date: ______, points_possible: _____, points_earned: _____ ]
    
    calendar_events: []
    }
    
    """

    user_data = {"user_metadata" : {}, "courses": {}, "items": []}
    page_number = 1
    #data in Canvas API is pagenated, so you have to manually go through multiple pages in case there are more items of the type needed
    
    while True: 
    #any "while True" function is always meant to go through multiple pages over and over until there's no more data left to retrieve
        user_courses = requests.get(f"{API_URL}/courses/", params={"enrollment_state": "active", "include[]": ["all_courses", "syllabus_body"], "page": page_number, "access_token": {API_TOKEN}}).json() 
        if user_courses == []:
            break

        for i in range(len(user_courses)):
            user_data["courses"][user_courses[i].get("id")] = {
                "id": user_courses[i].get("id"),
                "name": user_courses[i].get("name"),
                "code": user_courses[i].get("code"),
                "description": user_courses[i].get("description"),
                
                }
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
    
    return

def test():
    announcements = requests.get(f"{API_URL}/announcements", headers={"Authorization": f"Bearer: {API_TOKEN}"}, params=[]).json() 
    print(announcements)
    return "yo"

test()