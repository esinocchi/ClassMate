from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Union
import requests
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

class ContextEntry(BaseModel):
    role: str
    content: List[str]

class ContextEntry2(BaseModel):
    role: str
    id: str
    domain: str
    content: List[str]
    classes: List[str]

class ContextObject(BaseModel):
    context: List[Union[ContextEntry, ContextEntry2]]


# Root directory for testing connection
@app.get('/')
async def root():
    return {'response': 'Sample API Return'}

# Enter main prompt pipeline and return response
@app.post('/endpoints/mainPipelineEntry')
async def mainPipelineEntry(contextArray: ContextObject): 
    # Functionality to update responses
    # Here we assume you want to update the first context entry's content
    if len(contextArray.context) > 0:  # Ensure there's at least one entry
        contextArray.context[0].content[0] = "sample response"  # Update the content of the first entry

    # Go through method routes and include meta-data for output format (pdf out for example)
    return contextArray.context  # Return the modified Context

@app.get('/endpoints/pullClasses')
async def pullClasses(studentID, college="psu.instructure.com"):
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

