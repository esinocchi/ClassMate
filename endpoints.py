from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Union

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
async def returnPromptContext(studentID, college):
    #pull access token from database given parameters
    #pull classes from canvas api and return for display
    classes = ["cmpsc311", "cmpeng270", "math250"] #create sample list
    return {'classes': classes}
