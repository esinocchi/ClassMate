import os 
from dotenv import load_dotenv
import openai
from openai import OpenAI
import requests
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add the project root directory to Python path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

# from backend.task_specific_agents.calendar_agent import find_events
from backend.task_specific_agents.calendar_agent import create_event
import chat_bot.context_retrieval

load_dotenv()


openai_api_key = os.getenv("OPENAI_API_KEY")
canvas_api_url = os.getenv("CANVAS_API_URL")
canvas_api_token = os.getenv("CANVAS_API_KEY")

class ConversationHandler:
    def __init__(self, student_name, student_id, courses):
        self.student_name = student_name
        self.student_id = student_id
        self.courses = courses
        self.canvas_api_url = canvas_api_url
        self.canvas_api_token = canvas_api_token
        self.openai_api_key = openai_api_key

    def define_functions(self):
        """Returns a list of function definitions for the OpenAI API"""
        functions = [
            # {
            #     "name": "find_events_and_assignments",
            #     "description": "Retrieve calendar events and assignments from the Canvas API using the specified parameters.",
            #     "parameters": {
            #         "type": "object",
            #         "properties": {
            #             "keywords": {
            #                 "type": "array",
            #                 "items": {
            #                     "type": "string"
            #                 },
            #                 "description": """A list of keywords derived from the user's prompt to guide the vector database search.
            #                   This list must include:
            #                   - **Item Types:** e.g., 'assignment', 'calendar events', 'syllabus'.
            #                   - **Date Ranges:** Dates converted to ISO8601 format (e.g., '2012-07-01T23:59:00-06:00', '2012-07-08T16:00:00-06:00').
            #                   - **Course Names with IDs:** Include both the course name and its course ID (e.g., 'physics course_2372294', 'statistics course_2381676').
            #                   - **Synonyms or Related Terms:** For example, if 'exam' is mentioned, also include 'midterm' and 'final'.
            #                   Keep the list concise (around 10 items) to ensure focused retrieval."""
            #             }
            #         },
            #         "required": ["keywords"]
            #     }
            # },
            # {
            #     "name": "find_syllabus",
            #     "description": "Retrieve syllabus from the Canvas API using the specified parameters.",
            #     "parameters": {
            #         "type": "object",
            #         "properties": {
            #             "keywords": {
            #                 "type": "array",
            #                 "items": {
            #                     "type": "string"
            #                 },
            #                 "description": "A list of keywords derived from the user's prompt to guide the vector database search. This list must include:\n\n- **Item Types:** e.g., 'assignment', 'calendar events', 'syllabus'.\n- **Date Ranges:** Dates converted to ISO8601 format (e.g., '2012-07-01T23:59:00-06:00', '2012-07-08T16:00:00-06:00').\n- **Course Names with IDs:** Include both the course name and its course ID (e.g., 'physics course_2372294', 'statistics course_2381676').\n- **Synonyms or Related Terms:** For example, if 'exam' is mentioned, also include 'midterm' and 'final'.\n\nKeep the list concise (around 10 items) to ensure focused retrieval."
            #             }
            #         },
            #         "required": ["keywords"]
            #     }
            # },
            {
                "name": "create_event",
                "description": "Create a calendar event or multiple events using the Canvas API.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "context_code": {
                            "type": "string",
                            "description": "This should always be the students user id."
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
                        "context_code",
                        "title",
                        "start_at"
                    ]
                }
            }
        ]
        return functions
    
    def retrieve_chat_history(self):
        """Retrieve chat history using the context_retrieval module"""
        return chat_bot.context_retrieval.retrieve_chat_history()

    # def find_events_and_assignments(self, query: str):
    #     """Find events and assignments using the context_retrieval module"""
    #     # Convert course IDs to strings
    #     course_ids = [str(course_id) for course_id in self.courses.values()]
    #     return chat_bot.context_retrieval.retrieve_events_and_assignments(query, course_ids)

    # def find_syllabus(self, query: str):
    #     """Find syllabus using the context_retrieval module"""
    #     course_ids = [str(course_id) for course_id in self.courses.values()]
    #     return chat_bot.context_retrieval.retrieve_syllabus(query, course_ids)


    def process_user_message(self, chat_history: str):
        """Process a user message and return the appropriate response"""
        current_time = datetime.now(timezone.utc).isoformat()
        system_context = f"""You are a highly professional and task-focused AI assistant for {self.student_name} (User ID: {self.student_id}). You have access to a dictionary of {self.student_name}'s courses, where each key is the course name and each value is the corresponding course ID: {self.courses}. 
            Your role is to assist with a variety of school-related tasks including coursework help, study note creation, video transcription, and retrieving specific information from the Canvas LMS (such as syllabus details, assignment deadlines, and course updates).

            The current UTC time is: {current_time}
            When creating events or working with dates, use this as your reference point for "now".
            All dates and times should be in ISO8601 format.

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
            - **Clarity:** Use plain and accessible language suitable for all academic levels."""

        functions = self.define_functions()
        
        client = OpenAI(
            api_key=self.openai_api_key
        )

        function_mapping = {
            # "find_events_and_assignments": self.find_events_and_assignments,
            # "find_syllabus": self.find_syllabus,
            "create_event": create_event
        }

        chat = [
            {"role": "system", "content": system_context},
        ]
        
        chat.extend(json.loads(chat_history))

        chat_completion = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=chat,
            functions=functions,
            function_call="auto",
            temperature=.3,
            max_tokens=1024
        )
        response_message = chat_completion.choices[0].message

        # Checks to see if a function call is needed in order to answer the user's prompt
        if response_message.function_call:
            # Function is called and output used for api context
            function_call = response_message.function_call
            function_name = function_call.name
            arguments = json.loads(function_call.arguments)
            arguments["canvas_base_url"] = self.canvas_api_url
            arguments["access_token"] = self.canvas_api_token

            print("\n=== Debug Information ===")
            print(f"Function being called: {function_name}")
            print(f"Arguments being passed:")
            print(json.dumps(arguments, indent=2))
            print(f"Canvas API URL: {self.canvas_api_url}")
            print("Access Token: " + "*" * len(self.canvas_api_token))  # Don't print actual token for security
            print("========================\n")

            if function_name in function_mapping:
                try:
                    result = function_mapping[function_name](**arguments)
                except Exception as e:
                    print("\n=== Error Details ===")
                    print(f"Error Type: {type(e).__name__}")
                    print(f"Error Message: {str(e)}")
                    print("===================\n")
                    raise
            else:
                result = json.dumps({"error": f"Function '{function_name}' not implemented."})

            chat.append({
                'role': "function",
                "name": function_name,
                "content": json.dumps(result)
            })
            chat_to_return = json.loads(chat_history)

            chat_to_return.append({
                'role': "function",
                "name": function_name,
                "content": json.dumps(result)
            })
    
            # Context is then passed back to the api in order for it to respond to the user
            final_completion = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=chat,
                functions=functions,
                function_call="auto",
                temperature=0.3,
                max_tokens=1024
            )

            # Final response after function call
            final_message = final_completion.choices[0].message.content
            
            if len(chat_to_return) ==20:
                chat_to_return.pop(0)
            
            chat_to_return.append({
                'role': "user",
                "content": final_message
            })
            return chat_to_return
        else:
            # If no function was called then the api's response to the user's prompt is returned
             
            chat_to_return = json.loads(chat_history)
            if len(chat_to_return) ==20:
                chat_to_return.pop(0)
            
            chat_to_return.append({
                'role': "user",
                "content": response_message.content
            })
            return chat_to_return





