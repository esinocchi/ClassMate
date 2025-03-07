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

student_name = "Arshawn Vossoughi"

client = OpenAI(
    api_key=openai_api_key
)
#Get list of course objects
headers = {'Authorization': f'Bearer {canvas_api_token}'}

url = f"{canvas_api_url}/courses"



categorization_context = f""" d
"""
chat = [
    {'role': 'system', 'content': 'system_context' },
    {"role":"user","content": "What assignments do I have on March 6th?"}]


functions = [
    {
        "name": "find_events",
        "description": "Retrieve calendar events from the Canvas API using the specified parameters.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date (ISO8601 format) to filter events."
                },
                "end_date": {
                    "type": "string",
                    "description": "End date (ISO8601 format) to filter events."
                },
                "context_codes": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of context codes (e.g., ['course_123', 'user_456']) to filter the calendar events. Use "
                }
            },
            "required": [
                "start_date",
                "end_date",
                "context_codes"
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

function_mapping = {
    "find_events": find_events,
    "create_event": create_event
}



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

if response_message.function_call:
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

    final_completion = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=chat,
        functions=functions,
        function_call="auto",
        temperature=0.3,
        max_tokens=1024
    )

    final_message = final_completion.choices[0].message.content
    print(final_message)

else:
    print(chat_completion)