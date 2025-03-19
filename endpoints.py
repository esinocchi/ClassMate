from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Union
from chat_bot.conversation_handler import ConversationHandler
from backend.data_retrieval.data_handler import DataHandler

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
    #[{"role": "assistant", "content": [{"message":"", "function": ""}]},
    # {"role": "user", "id": "", "domain": "","recentDocs": [], "content": [], "classes": []}];


    chat_history = []
    for i in range(len(contextArray.context["content"][1]["content"])):
        chat_history.append({"role": "user", "content":contextArray.context["content"][1]["content"][i]})
        if contextArray.context["content"][0]["content"][i]["function"] != [""]:
            chat_history.append({"role": "function","name":contextArray.context["content"][0]["content"][i]["function"][0], "content": contextArray.context["content"][0]["content"][i]["function"][1]})
        chat_history.append({"role": "assistant", "content":contextArray.context["content"][0]["content"][i]["message"]})
    
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
    classes = ["cmpsc311", "cmpeng270", "math250"] #create sample list
    return {'classes': classes}
