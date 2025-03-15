from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

app = FastAPI()

# Pydantic JSON models
class ContextEntry(BaseModel):
    role: str
    content: List[str]
    classes: List[str]  # Added 'classes' field

class ContextEntry2(BaseModel):
    role: str
    content: List[str]


class ContextObject(BaseModel):
    context: List[ContextEntry, ContextEntry2]

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
    return contextArray  # Return the modified ContextObject

@app.get('/endpoints/pullClasses')
async def returnPromptContext(studentID, college):
    #pull access token from database given parameters
    #pull classes from canvas api and return for display
    classes = []
    return {'classes': classes}
