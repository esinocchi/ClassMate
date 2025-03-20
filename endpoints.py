from fastapi import FastAPI
import os
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Union
from chat_bot.conversation_handler import ConversationHandler
from backend.data_retrieval.data_handler import DataHandler
import asyncio
from dotenv import load_dotenv
import requests
import os
import time
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


class ContextPair(BaseModel):
    message: str
    function: List[str]

class ContextEntry(BaseModel):
    role: str
    content: List[ContextPair]

class ClassesDict(BaseModel):
    id: str
    name: str
    selected: str

class ContextEntry2(BaseModel):
    role: str
    id: str
    domain: str
    recentDOCS: List[str]
    content: List[str]
    classes: List[ClassesDict]

class ContextObject(BaseModel):
    context: List[Union[ContextEntry, ContextEntry2]]


# Root directory for testing connection
@app.get('/')
async def root():
    return {'response': 'Sample API Return'}

# Enter main prompt pipeline and return response
@app.post('/endpoints/mainPipelineEntry')
async def mainPipelineEntry(contextArray: ContextObject): 
    #[{"role": "assistant", "content": [{"message":"", "function": ""}]},
    # {"role": "user", "id": "", "domain": "","recentDocs": [], "content": [], "classes": []}];
    #chat_requirements = check_chat_requirements(contextArray)
    chat_requirements = "None"
    if chat_requirements == "None":
            

        print("\n=== STAGE 1: Starting mainPipelineEntry ===")
        context_data = contextArray.dict() if hasattr(contextArray, 'dict') else contextArray
        user_context = context_data['context'][1]
        user_id = user_context['id']
        user_domain = user_context['domain']
        
        handler = DataHandler(user_id, user_domain)
        user_data = handler.grab_user_data()
        user_name = user_data["user_metadata"]["name"]
        
        print("=== STAGE 2: Processing context data ===")
        # Handle both dictionary and Pydantic model access
        
        courses = {}  # Changed to a single dictionary

        for class_info in user_context['classes']:
            if class_info['selected'] == 'true':
                # Remove 'course_' prefix from ID and store as a simple key-value pair
                course_id = class_info['id'].replace('course_', '')
                courses[class_info['name']] = course_id
        
        print("=== STAGE 3: Initializing ConversationHandler ===")
        conversation_handler = ConversationHandler(student_name=user_name, student_id=user_id, courses=courses,domain=user_domain)
        
        print("=== STAGE 4: Transforming user message ===")
        chat_history = conversation_handler.transform_user_message(context_data)
        
        print("=== STAGE 5: Processing chat history ===")
        response = await conversation_handler.process_user_message(chat_history)
        
        print("=== STAGE 6: Returning response ===\n")
        return response  # Return the modified Context
    else:
        return[{"message": chat_requirements,"function":""}]



@app.get('/endpoints/pullClasses')
async def returnPromptContext(studentID, college):
    #pull access token from database given parameters
    #pull classes from canvas api and return for display
    
    #pull user data from database given parameters
    handler = DataHandler(studentID, college)
    user_data = handler.grab_user_data()
    
    #pull classes from user data
    classes = user_data["user_metadata"]["courses_selected"]

    return {'classes': classes.keys()}


@app.put('/endpoints/initate_user')
async def initate_user(domain: str):
    #hardcode token until we have access to developer keys to run oauth2
    #we will redirect to oauth page later
    token = os.getenv("CANVAS_API_TOKEN")

    #get user id from canvas api
    user_info = requests.get(f"https://{domain}/api/v1/users/self", headers={"Authorization": f"Bearer {token}"})
    user_id = user_info.json()["id"]

    #initialize a new data handler with the token
    handler = DataHandler(user_id, domain)
    
    #if user has saved data, update the token
    if handler.has_saved_data():
        handler.update_token(token)
    
    #if user has no saved data, initiate user data
    else:
        handler = DataHandler(user_id, domain, token)
        handler.initiate_user_data()
        handler.update_user_data()

    return {'response': 'User initiated'}


@app.get('/endpoints/pullUser')
async def returnUserID(token):

    return 

@app.get('/endpoints/mainPipelineEntry/getPDF')
async def  pdfPull(pdfID):

    return 