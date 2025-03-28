from fastapi import FastAPI
import os
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Union
from chat_bot.conversation_handler import ConversationHandler
from backend.data_retrieval.data_handler import DataHandler
from fastapi.responses import FileResponse
import aiohttp
from dotenv import load_dotenv
import time
import json
import asyncio

load_dotenv()

app = FastAPI()

# Add CORSMiddleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://psu.instructure.com", 
                   "https://canvasclassmate.me"],  # Allowed origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

#pydantic models for pipeline
class ContextPair(BaseModel):
    message: str
    function: List[str]

class ContextEntry(BaseModel):
    role: str
    content: List[ContextPair]

class ClassesDict(BaseModel):
    id: str
    name: str
    selected: bool

class ContextEntry2(BaseModel):
    role: str
    user_id: str
    domain: str
    recentDocs: List[str]
    content: List[str]
    classes: List[ClassesDict]

class ContextObject(BaseModel):
    context: List[Union[ContextEntry, ContextEntry2]]

#pydantic models for class updates
class PushClassesObject(BaseModel):
    user_id: str
    domain: str
    classes: List[ClassesDict]


# Root directory for testing connection
@app.get('/')
async def root():
    return {'response': 'Sample API Return'}

# Enter main prompt pipeline and return response
@app.post('/endpoints/mainPipelineEntry', response_model=ContextObject)
async def mainPipelineEntry(contextArray: ContextObject): 
    """
    This endpoint is the main entry point for the chatbot.
    It will check if the user has any chat requirements, and if not, it will process the user's message.
    If the user has chat requirements, it will return an error message.

    ===============================================
    
    inputs:
    contextArray: ContextObject

    outputs:
    ContextObject or {"message": str}

    ===============================================

    This endpoint is called when the user sends a message to the chatbot.
    """
   
    #[{"role": "assistant", "content": [{"message":"", "function": [""]}]},
    # {"role": "user", "id": "", "domain": "","recentDocs": [], "content": [], "classes": []}];
    chat_requirements = await check_chat_requirements(contextArray)
    print("these are the chat requirements: ", chat_requirements)
    if chat_requirements == "None":
            

        print("\n=== STAGE 1: Starting mainPipelineEntry ===")
        context_data = contextArray.context
        user_context = context_data[1]
        user_id = user_context.user_id
        user_domain = user_context.domain

        
        handler = DataHandler(user_id, user_domain)
        user_data = handler.grab_user_data()
        user_name = user_data["user_metadata"]["name"]
        user_token = user_data["user_metadata"]["token"]
        
        print("=== STAGE 2: Processing context data ===")
        # Handle both dictionary and Pydantic model access
        
        courses = {}  # Changed to a single dictionary

        for class_info in user_context.classes:
            if class_info.selected == True:
                # Remove 'course_' prefix from ID and store as a simple key-value pair
                course_id = class_info.id.replace('course_', '')
                courses[class_info.name] = course_id
        
        print("=== STAGE 3: Initializing ConversationHandler ===")
        conversation_handler = ConversationHandler(student_name=user_name, student_id=f"user_{user_id}", courses=courses,domain=user_domain,chat_history=contextArray,canvas_api_token=user_token)
        
        print("=== STAGE 4: Transforming user message ===")
        chat_history = conversation_handler.transform_user_message(contextArray)
        
        print("=== STAGE 5: Processing chat history ===")
        response = await conversation_handler.process_user_message(chat_history)
        
        print("=== STAGE 6: Returning response ===\n")
        return response  # Return the modified Context
    else:
        contextArray.context[0].content[0] = {"message": chat_requirements,"function":[""]}
        return contextArray



@app.get('/endpoints/pullCourses')
async def pullCourses(user_id, domain):
    """
    This endpoint is used to pull courses from the canvas api and return for display.

    ===============================================

    inputs:
    user_id: int eg. 1242323
    domain: str eg. "psu.instructure.com"

    outputs:
    {"courses": List[ClassesDict]}

    ===============================================

    Call this endpoint when the user first loads the settings page.
    """
    #pull access token from database given parameters
    #pull classes from canvas api and return for display
    
    #pull user data from database given parameters
    handler = DataHandler(user_id, domain)

    user_data = handler.grab_user_data()
    
    #pull courses selected from user data
    courses_selected = user_data["user_metadata"]["courses_selected"]
    all_courses = []
    courses_added = []    
    
    #only one course is in each course object, but we still need to iterate through the course object to get the course id and course name
    for course_id, course_name in courses_selected.items():
            course_formatted = ClassesDict(id=course_id, name=course_name, selected=True)
            all_courses += [course_formatted]
            courses_added += [course_id]
    
    courses = []
    
    #pull all classes from canvas api

    page_number = 1
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {handler.grab_user_data()['user_metadata']['token']}"}
        while True:
            async with session.get(
                f"{handler.API_URL}/courses/",
                params={"enrollment_state": "active", "include[]": ["all_courses", "syllabus_body"], "page": page_number},
                headers=headers
            ) as response:
                if response.status == 200:
                    courses_data = await response.json()
                    if not courses_data:  # Break if no more courses are returned
                        break
                    courses += courses_data
                else:
                    return {"message": "Error pulling courses from Canvas API"}
            page_number += 1
    
    #iterate through all classes and if not in courses_added, add to all_classes
    for course in courses:

        if str(course.get("id")) not in courses_added and course.get("name"):
            course_formatted = ClassesDict(id=course.get("id"), name=course.get("name"), selected=False)
            all_courses += [course_formatted]
            courses_added += [str(course.get("id"))]

    #classes are returned in the format {course_id: course_name}
    return {'courses': all_courses}

@app.post('/endpoints/pushCourses')
async def pushCourses(classesData: PushClassesObject):
    """
    This endpoint is used to push courses to the database.

    ===============================================

    inputs:
    user_id: int
    domain: str
    courses: List[ClassesDict]

    outputs:
    {"message": str}

    ===============================================

    Call this endpoint when the user selects or deselects a course then clicks the save button.
    """
    #push courses to database
    #courses are returned in the format {course_id: course_name}
    courses_selected = {}
    #for each ClassesDict object, if selected is true, add to courses_selected dictionary
    for course in classesData.classes:
        
        if course.selected == True:
            courses_selected[course.id] = course.name
    
    handler = DataHandler(classesData.user_id, classesData.domain)
    
    handler.update_courses_selected(courses_selected)
    #after updating courses_selected, update the user data to ensure all data only exists if the user has selected the course
    handler.update_user_data()

    return {'message': "Courses pushed to database"}


# call this endpoint to force a user to re-authenticate whenever browser cache is empty
@app.get('/endpoints/initiate_user')
async def initate_user(domain: str):
    """
    This endpoint is used to force a user to re-authenticate and generate a new token.
    
    call this endpoint when the token is expired, or when the user_id is not found in the database.

    ===============================================
    
    inputs:
    domain: str

    outputs:
    {"user_id": int}
    
    ===============================================

    check on reload of page if user_id --IS NOT-- found in database, and if so, call this endpoint.
    """
    try:
        token = await oauthTokenGenerator()

        # Get user info (async)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://{domain}/api/v1/users/self",
                headers={"Authorization": f"Bearer {token}"}
            ) as response:
                response.raise_for_status()
                user_info = await response.json()
                user_id = user_info["id"]

        handler = DataHandler(user_id, domain, token)

        if handler.has_saved_data():
            handler.update_token(token)
        else:
            result = handler.initiate_user_data()  # Synchronous call
            if "Error" in result:
                return {"message": result}

        return {'user_id': user_id}

    except aiohttp.ClientError as e:
        return {"message": f"Canvas API error: {str(e)}"}
    except Exception as e:
        return {"message": f"Initialization failed: {str(e)}"}

@app.put('/endpoints/checkAndUpdateUserData')
async def checkAndUpdateUserData(user_id, domain):
    """
    This endpoint is used to check if the user data is outdated and update it if necessary.

    ===============================================

    inputs:
    user_id: int
    domain: str

    outputs:
    {"message": str}

    ===============================================

    check on reload of page if user_id --IS-- found in database, and if so, call this endpoint.
    """
    handler = DataHandler(user_id, domain)
    user_data = handler.grab_user_data()

    #check if token is expired
    if time.time() - user_data["user_metadata"]["token_updated_at"] > 3600:
        token = await oauthTokenGenerator()
        handler.update_token(token)

    #check if user data is outdated
    if time.time() - user_data["user_metadata"]["last_updated"] > 21600:
        handler.update_user_data()
        return {"message": "User data updated"}
    
    else:
        return {"message": "User data not updated"}

async def check_chat_requirements(contextArray: ContextObject):
    """
    This function is used to check if the user has any chat requirements missing

    ===============================================

    inputs:
    contextArray: ContextObject

    outputs:
    message: str

    ===============================================

    this function is called in the mainPipelineEntry endpoint.
    """
    #check if user has selected any courses
    #check if user has a valid user id
    user_context = contextArray.context[1]

    #if user data update is currently in progress, return error message
    #if await check_update_status(user_context.user_id, user_context.domain):
    #    return "User data update currently in progress, please try again in a few minutes"
    
    #if there are no courses selected, tell user to select courses in the settings page by returning error message

    for i in range(len(user_context.classes)):
        if user_context.classes[i].selected == True:
            return "None"
    
    return "Please select at least one course in the settings page to continue"
    

@app.get('/endpoints/check_update_status')
async def check_update_status(user_id, domain):
    """
    This endpoint is used to check if the user data is currently being updated.

    ===============================================

    inputs:
    user_id: int
    domain: str

    outputs:
    is_updating: bool

    ===============================================

    call this endpoint whenever a user tries to update courses_selected by hitting the save button, 
    main pipline entry handles the case of when user tries to chat while update is in progress.
    """
    handler = DataHandler(user_id, domain)
    user_data = handler.grab_user_data()
    return user_data["user_metadata"]["is_updating"]

async def oauthTokenGenerator():
    """
    token generator for oauth2
    
    ===============================================

    hardcoded token until we have access to developer keys to run oauth2
    """
    #we will use oauth2 to generate a token
    #for now, we will use a hardcoded token
    token = os.getenv("CANVAS_API_TOKEN")
    return token

#returns the stored pdf
@app.get("/endpoints/pullNotes")
async def pullPDF(domain, user_id):
    handler = DataHandler(user_id, domain)
    pdf_path = f"media_output/{handler.domain}/{user_id}/output.pdf"
    return FileResponse(pdf_path, media_type='application/pdf', filename="your_file.pdf")
