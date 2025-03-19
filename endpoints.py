from fastapi import FastAPI
import os
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Union
from chat_bot.conversation_handler import ConversationHandler
from backend.data_retrieval.data_handler import DataHandler
import asyncio
from backend.data_retrieval.data_handler import DataHandler
from dotenv import load_dotenv
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

    chat_history = conversation_handler.transform_user_message(contextArray)
    
    handler = DataHandler()
    user_data = handler.grab_data()
    user_name = user_data["user_metadata"]["name"]
    user_id = contextArray.context["content"][1]["id"]
    courses = []

    for i in range(len(contextArray.context["content"][1]["classes"])):
        if contextArray.context["content"][1]["classes"][i]["selected"] == 'true':
            courses.append({contextArray.context["content"][1]["classes"][i]["name"]: contextArray.context["content"][1]["classes"][i]["id"]})
    
    conversation_handler = ConversationHandler(student_name=user_name, student_id=user_id, courses=courses)
    
    response = conversation_handler.process_chat_history(chat_history)

    return response  # Return the modified Context


@app.get('/endpoints/pullClasses')
async def returnPromptContext(studentID, college):
    #pull access token from database given parameters
    #pull classes from canvas api and return for display
    
    #pull user data from database given parameters
    handler = DataHandler(studentID, college)
    user_data = handler.grab_user_data()
    
    #pull classes from user data
    classes = user_data["user_metadata"]["courses_selected"]

    return {'classes': classes}


@app.get('/endpoints/oauth2')
async def oauth2():
    #hardcode token until we have access to developer keys to run oauth2
    token = os.getenv("CANVAS_API_TOKEN")
    return {'token': token}


@app.get('/endpoints/pullUser')
async def returnUserID(token):

    return 

@app.get('/endpoints/mainPipelineEntry/getPDF')
async def  pdfPull(pdfID):

    return 