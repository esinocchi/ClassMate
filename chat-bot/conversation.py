import os 
from dotenv import load_dotenv
import openai
from openai import OpenAI
import requests
import json
from backend.task_specific_agents.calendar_agent import find_events
from backend.task_specific_agents.calendar_agent import create_event





load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
canvas_api_url= os.getenv("CANVAS_API_URL")
canvas_api_token = os.getenv("CANVAS_API_KEY")




#These need variable need to be pulled dynamically for the system context.
student_name = "Arshawn Vossoughi"
students_id = "user_7210330"
courses = {"physics":"course_2372294","statistics":"course_2381676", "Earth 101":"course_2361510","Apocalyptic Geographies":"course_2361723"}

#Needs to be updated as needed
system_context = f"""You are a highly professional and task-focused AI assistant for {student_name} (User ID: {students_id}). You have access to a dictionary of {student_name}'s courses, where each key is the course name and each value is the corresponding course ID: {courses}. Your role is to assist with a variety of school-related tasks including coursework help, study note creation, video transcription, and retrieving specific information from the Canvas LMS (such as syllabus details, assignment deadlines, and course updates).

When a user's question requires additional information that is not immediately available, you must call the appropriate retrieval function. In such cases, extract a concise list of keywords from the user's prompt that captures the essential details needed for the search. The list must include:
- **Item Types:** Terms such as "assignment", "calendar events", "syllabus", etc.
- **Date Ranges:** Convert any dates provided into ISO8601 format (e.g., "2012-07-01T23:59:00-06:00").
- **Course Names with IDs:** For any course mentioned by the user, include both the course name and its corresponding course ID (e.g., "physics course_2372294").
- **Synonyms or Related Terms:** For example, if the user mentions "exam", also include "midterm" and "final".

Aim to generate a focused keyword list of about 10 items. These guidelines must be applied consistently across all retrieval functions.

The current year is 2025.
Adhere to the following principles:
- **Professionalism:** Maintain a strictly professional tone and disregard nonsensical or irrelevant queries.
- **Accuracy:** Deliver precise, reliable, and well-structured responses.
- **Ethics:** Do not assist with any requests that could enable academic dishonesty.
- **Clarity:** Use plain and accessible language suitable for all academic levels.
"""


#Needs to be pulled dynamically in order to properly handle conversations
#chat content for the api
chat = [
    {'role': 'system', 'content': system_context },
    {"role":"user","content": "What assignments do I have in all my classes the last week of March?"}]

#Descriptions of functions that may need to be called. This is being used to give context to api for how to call the functions
functions = [
    {
        "name": "find_events_and_assignments",
        "description": "Retrieve calendar events and assignments from the Canvas API using the specified parameters.",
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items":{
                        "type": "string"
                    },
                    "description": "A list of keywords derived from the user's prompt to guide the vector database search. This list must include:\n\n- **Item Types:** e.g., 'assignment', 'calendar events', 'syllabus'.\n- **Date Ranges:** Dates converted to ISO8601 format (e.g., '2012-07-01T23:59:00-06:00', '2012-07-08T16:00:00-06:00').\n- **Course Names with IDs:** Include both the course name and its course ID (e.g., 'physics course_2372294', 'statistics course_2381676').\n- **Synonyms or Related Terms:** For example, if 'exam' is mentioned, also include 'midterm' and 'final'.\n\nKeep the list concise (around 10 items) to ensure focused retrieval."}
            },
            "required": [
                "keywords"
            ]
        }
    },
    {
        "name": "create_event",
        "description": "Create a calendar event or multiple events using the Canvas API.",
        "parameters": {
            "type": "object",
            "properties": {
                "context_code": {
                    "type": "string",
                    "description": "The context code (e.g., 'course_123' or 'user_456') for the event."
                },
                "title": {
                    "type": "string",
                    "description": "Title of the event."
                },
                "start_at": {
                    "type": "string",
                    "description": "Start date/time in ISO8601 format."
                },
                "end_at": {
                    "type": "string",
                    "description": "End date/time in ISO8601 format."
                },
                "description": {
                    "type": "string",
                    "description": "Description of the event."
                },
                "location_name": {
                    "type": "string",
                    "description": "Name of the location."
                },
                "location_address": {
                    "type": "string",
                    "description": "Address of the location."
                },
                "all_day": {
                    "type": "boolean",
                    "description": "Indicates if the event lasts all day.",
                    "default": False
                },
                "duplicate_count": {
                    "type": "integer",
                    "description": "Number of times to duplicate the event (max 200)."
                },
                "duplicate_interval": {
                    "type": "integer",
                    "description": "Interval between duplicates; defaults to 1."
                },
                "duplicate_frequency": {
                    "type": "string",
                    "enum": ["daily", "weekly", "monthly"],
                    "description": "Frequency at which to duplicate the event."
                },
                "duplicate_append_iterator": {
                    "type": "boolean",
                    "description": "If true, an increasing counter will be appended to the event title for each duplicate (e.g., Event 1, Event 2, etc.)."
                }
            },
            "required": [
                "canvas_base_url",
                "access_token",
                "context_code",
                "title",
                "start_at"
            ]
        }
    }
]


#Mapping of actual functions to name of functions
function_mapping = {
    "find_events": find_events,
    "create_event": create_event
}

client = OpenAI(
    api_key=openai_api_key
)


chat_completion = client.chat.completions.create(
    model = 'gpt-4o-mini',
    messages = chat,
    functions = functions,
    function_call = "auto",
    temperature = .3,
    max_tokens = 1024

)
print(chat_completion)
response_message = chat_completion.choices[0].message

#Checks to see if a function call is needed in order to answer the user's prompt
if response_message.function_call:
    #Funciton is called and output used for api context
    function_call = response_message.function_call
    function_name = function_call.name
    arguments = json.loads(function_call.arguments)
    arguments["canvas_base_url"] = canvas_api_url
    arguments["access_token"] = canvas_api_token

    if function_name in function_mapping:
        result = function_mapping[function_name](**arguments)
    else:
        result = json.dumps({"error": f"Function '{function_name}' not implemented."})

    chat.append({
        'role':"function",
        "name":function_name,
        "content": json.dumps(result)
    })
    
    #Context is then passed back to the api in order for it to respond to the user
    final_completion = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=chat,
        functions=functions,
        function_call="auto",
        temperature=0.3,
        max_tokens=1024
    )

    #Final response after funciton call
    final_message = final_completion.choices[0].message.content
    print(final_message)
else:
    #If no function was called then the api's response to the user's prompt is returned
    print(chat_completion)