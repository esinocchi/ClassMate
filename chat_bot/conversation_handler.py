import os 
from dotenv import load_dotenv
from openai import OpenAI
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Literal, Union
from pydantic import BaseModel, Field
import asyncio
import concurrent.futures

# Add the project root directory to Python path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

# from backend.task_specific_agents.calendar_agent import find_events
from backend.task_specific_agents.calendar_agent import create_event
import chat_bot.context_retrieval
from vectordb.db import VectorDatabase

# Define the context models locally
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

load_dotenv()


openai_api_key = os.getenv("OPENAI_API_KEY")
canvas_api_url = os.getenv("CANVAS_API_URL")
canvas_api_token = os.getenv("CANVAS_API_KEY")

# Pydantic classes for structured output

# Define the complete function response model

class ConversationHandler:
    def __init__(self, student_name, student_id, courses, domain, course_history):
        self.student_name = student_name
        self.student_id = f"user_{student_id}"
        self.courses = courses
        self.domain = domain
        self.course_history = course_history
        self.canvas_api_url = canvas_api_url
        self.canvas_api_token = canvas_api_token
        self.openai_api_key = openai_api_key
        
        # Define valid types and time range definitions
        self.valid_types = ["assignment", "file", "quiz", "announcement", "event", "syllabus"]
        self.time_range_definitions = {
            "FUTURE": {
                "description": "Upcoming items",
                "logic": "item > now",
                "weight": 1.2
            },
            "RECENT_PAST": {
                "description": "Past 7 days",
                "logic": "now - 7d <= item <= now",
                "weight": 1.1
            },
            "EXTENDED_PAST": {
                "description": "Past 30 days",
                "logic": "now - 30d <= item <= now", 
                "weight": 0.95
            },
            "ALL_TIME": {
                "description": "Any time",
                "logic": "item exists",
                "weight": 1.0
            }
        }
        self.generality = "HIGH"


    def define_functions(self):
        """Returns a list of function definitions for the OpenAI API"""
        functions = [
            {
                "name": "find_events_and_assignments",
                "description": "Search for Canvas materials using vector embeddings for semantic retrieval.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_parameters": {
                            "type": "object",
                            "properties": {
                                "course_id": {
                                    "type": "string",
                                    "description": "Course ID or 'all_courses'"
                                },
                                "time_range": {
                                    "type": "string", 
                                    "enum": ["FUTURE", "RECENT_PAST", "EXTENDED_PAST", "ALL_TIME"],
                                    "description": "Temporal context for search"
                                },
                                "item_types": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "enum": ["assignment", "file", "quiz", "announcement", "event", "syllabus"]
                                    },
                                    "description": "This should always be [assignment,events,announcement]"
                                },
                                "specific_dates": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "format": "date"
                                    },
                                    "description": "ISO8601 format dates mentioned in query if a specific date is mentioned. If no specific date is mentioned,this should be today's date in ISO8601 format"
                                },
                                "keywords": {
                                    "type": "array",
                                    "items": {
                                        "type": "string" 
                                    },
                                    "description": "Additional search terms like 'midterm', 'HW2', 'Quiz 3'"
                                },
                                "query": {
                                    "type": "string",
                                    "description": "User's original query for semantic search"
                                }
                            },
                        },
                        
                    },
                    "required": ["search_parameters"]
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
                            "description": "This should always be the students user id. This should be in the form user_idnumbe"
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
    
    def define_system_context(self):
        current_time = datetime.now(timezone.utc).isoformat()
        
        system_context = f"""You are a highly professional and task-focused AI assistant for {self.student_name} (User ID: {self.student_id}). You have access to a dictionary of {self.student_name}'s courses, where each key is the course name and each value is the corresponding course ID: {self.courses}. 
            
        Your role is to assist with a variety of school-related tasks including coursework help, study note creation, video transcription, and retrieving specific information from the Canvas LMS (such as syllabus details, assignment deadlines, and course updates).
        Adhere to the following principles:
            - **Professionalism:** Maintain a strictly professional tone and disregard nonsensical or irrelevant queries.
            - **Accuracy:** Deliver precise, reliable, and well-structured responses.
            - **Ethics:** Do not assist with any requests that could enable academic dishonesty.
            - **Clarity:** Use plain and accessible language suitable for all academic levels.

            The current UTC time is: {current_time}
            When creating events or working with dates, use this as your reference point for "now".
            All dates and times should be in ISO8601 format.

            When a user's question requires additional information that is not immediately available, you must call the appropriate retrieval function that is listed in the function list given to you. In the case that a function call is needed, extract a concise list of keywords from the user's prompt that captures the essential details needed for the search. Here are the guidelines for the keywords:

            1. Extract these COMPULSORY elements:
                - **Item Types:** Assign an item type or types from the following options: {self.valid_types}
                - **Time Range:** Assign a time range from the following options: {self.time_range_definitions}
                - **Course:** For any course mentioned by the user, include both the course name and its corresponding course ID. The course name and ids are found in {self.courses}.
                - **Synonyms or Related Terms:** For example, if the user mentions "exam", also include "midterm" and "final".
                - **Specific Dates:** If the user mentions a specific date, include that date. If no specific date is mentioned, this should be today's date.
            2. Keyword List Rules:
                - Keyword list should contain keywords that are relevant to the user's query, but should not be the same as any of the Compulsory elemnts mentioned in step 1. 
                - For example: If somebody asks you to retrieve all assignments related to Hooke's law, the keyword list should be ['Hooke's law']
                - Include synonyms or related terms if applicable
                - Max 10 items in the list

            3. Specific Cases:
                **Time Range Examples:**
                    - 'Due tomorrow' → FUTURE
                    - 'Posted yesterday' → RECENT_PAST
                    - 'From two weeks ago' or if they mention that it is in the past without a time range. For example(What was my last quiz?) → EXTENDED_PAST
                    - 'Any syllabus for the course' → ALL_TIME

            4. Fail-Safes:
                **Time Range FAIL-SAFE:**
                    - If uncertain for the time range, use ALL_TIME for the time range.
                **Course FAIL-SAFE:**
                    - If no course is mentioned for the course keyword, use "all_courses" for the course keyword. An example prompt where this would be applicable is "What assignments do I have in all my classes the last week of March?"
                    - If a course is mentioned but does not match up exactly with the courses in {self.courses}, match it to the closest course.

            For Canvas material search queries, you MUST respond with a valid JSON object in this exact format:

            Example: "What physics assignments are due next week?"
            Arguments must be:
            {{
            "parameters": {{
                "search_parameters": {{
                    "course_id": "2372294",
                    "time_range": "FUTURE",
                    "item_types": ["assignment"],
                    "specific_dates": ["2025-04-01", "2025-04-07"],
                    "keywords": ["physics", "homework"],
                    "query": "What physics assignments are due next week?"
                    }},
                    
            }}
            }}

            Your JSON response MUST be valid and conform exactly to this structure.

            If you do not need to use a retrieval function, but they ask you to create an event,
            the arguments to be generated are defined in the description of the function list. 

            If you do not need to call a function, then respond to the user accordingly. 
            If the last item in the chat history is a function call, then respond to the user's previous message using . 
        """
        return system_context
    

    async def find_events_and_assignments(self, search_parameters: dict):
        """Find events and assignments using the vector search function"""
        print("\n=== FIND_EVENTS_AND_ASSIGNMENTS: Starting ===")
        print(f"Search parameters received: {json.dumps(search_parameters, indent=2)}")
        
        from vectordb.db import VectorDatabase
        print("Imported VectorDatabase")
        
        user_id_number = self.student_id.split("_")[1]
        print(f"User ID number: {user_id_number}")
        
        vector_db_path = f"user_data/psu/{user_id_number}/user_data.json"
        print(f"Vector DB path: {vector_db_path}")
        
        print("Initializing VectorDatabase...")
        vector_db = VectorDatabase(vector_db_path)
        print("VectorDatabase initialized")
        
        print("Calling vector_db.search...")
        try:
            events_and_assignments = await vector_db.search(search_parameters)
        except Exception as e:
            print(f"ERROR in vector_db.search: {str(e)}")
            print(f"Error type: {type(e)}")
            events_and_assignments = []
        
        return events_and_assignments

    def find_syllabus(self, query: str):
        """Find syllabus using the context_retrieval module"""
        course_ids = [str(course_id) for course_id in self.courses.values()]
        return chat_bot.context_retrieval.retrieve_syllabus(query, course_ids)

    def validate_keywords(self, keywords):
        """Validates keywords and enables fail-safes"""
        # Course ID check
        if keywords[0] not in self.courses.values() and keywords[0] != "all_courses":
            keywords[0] = "all_courses"
        
        # Time range update
        valid_ranges = ["FUTURE", "RECENT_PAST", "EXTENDED_PAST", "ALL_TIME"]
        if len(keywords) > 1 and keywords[1] not in valid_ranges:
            keywords[1] = "ALL_TIME"
        if len(keywords) > 2 and keywords[2] not in self.valid_types:
            keywords[2] = "all_types"
        return keywords[:10]
    

    def transform_user_message(self, contextArray: ContextObject):
        print("\n=== TRANSFORM USER MESSAGE: Starting ===")
        chat_history = []
        
        print("=== TRANSFORM USER MESSAGE: Parsing context array ===")
        print(f"Context Array Structure:")
        print(json.dumps(contextArray, indent=2))
        print(f"\nNumber of user messages: {len(contextArray['context'][1]['content'])}")
        print(f"Number of assistant responses: {len(contextArray['context'][0]['content'])}")
        
        print("\n=== TRANSFORM USER MESSAGE: Processing messages ===")
        for i in range(len(contextArray["context"][1]["content"])-1,-1,-1):
            print(f"\nProcessing message pair {i + 1}:")
            print(f"User message: {contextArray['context'][1]['content'][i]}")
            chat_history.append({"role": "user", "content":contextArray["context"][1]["content"][i]})
            
            print(f"Assistant content: {json.dumps(contextArray['context'][0]['content'][i], indent=2)}")
            if contextArray["context"][0]["content"][i]["function"] and contextArray["context"][0]["content"][i]["function"] != [""]:
                print(f"Function detected: {contextArray['context'][0]['content'][i]['function']}")
                chat_history.append({"role": "function","name":contextArray["context"][0]["content"][i]["function"][0], "content": contextArray["context"][0]["content"][i]["function"][1]})
            if i == 0:
                chat_history.append({"role": "assistant", "content":contextArray["context"][0]["content"][i]["message"]})
        
        print("\n=== TRANSFORM USER MESSAGE: Final chat history ===")
        print(json.dumps(chat_history, indent=2))
        print("=== TRANSFORM USER MESSAGE: Complete ===\n")
        return chat_history
    
    async def process_user_message(self, chat_history: dict):
        """Process a user message and return the appropriate response"""
        print("\n=== PROCESS USER MESSAGE: Starting ===")
        print(f"Chat history received: {json.dumps(chat_history, indent=2)}")
        
        print("=== PROCESS USER MESSAGE: Generating system context ===")
        # Generate the system context with enhanced instructions
        system_context = self.define_system_context()
        functions = self.define_functions()
        print(f"System context length: {len(system_context)}")
        print(f"Functions defined: {[f['name'] for f in functions]}")
        
        client = OpenAI(
            api_key=self.openai_api_key
        )
        print(f"OpenAI client initialized with key: {'*'*len(self.openai_api_key)}")

        function_mapping = {
            "find_events_and_assignments": self.find_events_and_assignments,
            # "find_syllabus": self.find_syllabus,
            #"vectordb_search": self.vector_db.search,
            "create_event": create_event
        }
        print(f"Function mapping: {list(function_mapping.keys())}")

        chat = [
            {"role": "system", "content": system_context},
        ]
        
        chat.extend(chat_history)
        print(f"Full chat context length: {len(chat)}")
        print("=== PROCESS USER MESSAGE: Making first API call ===")
        
        try:
            # First API call to get function call or direct response
            print("About to make OpenAI API call with model: 'gpt-4o-mini'")
            chat_completion = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=chat,
                functions=functions,
                function_call = "auto",
                temperature=.3,
                max_tokens=1024
            )
            print("API call completed successfully")
            
            response_message = chat_completion.choices[0].message
            response_content = response_message.content
            print("\n=== First API Response Details ===")
            print("Complete response object:")
            print(f"Response message: {response_message}")
            print(f"Response content: {response_content}")
            print(f"Response message dict: {response_message.__dict__}")
            print("================================\n")
        except Exception as e:
            print(f"ERROR during API call: {str(e)}")
            print(f"Error type: {type(e)}")
            return [{"message": f"Error processing request: {str(e)}", "function": [""]}]
        
        print("\n=== PROCESS USER MESSAGE: Processing API response ===")
        # Check if there's a function call in the response
        function_call = response_message.function_call
        print(f"Function call present: {function_call is not None}")

        if function_call:
            function_name = function_call.name
            print(f"Function call detected: {function_call.name}")
            try:
                arguments = json.loads(function_call.arguments)
                arguments["canvas_base_url"] = self.canvas_api_url
                arguments["access_token"] = self.canvas_api_token
                print(f"Function arguments: {json.dumps(arguments, indent=2)}")
            except json.JSONDecodeError as e:
                print(f"ERROR decoding function arguments: {str(e)}")
                print(f"Raw arguments: {function_call.arguments}")
                return [{"message": "Error processing function arguments", "function": [""]}]
            
            print("=== PROCESS USER MESSAGE: Preparing function call ===")
            if function_name == "vectordb_search":
                if "search_parameters" in arguments and "keywords" in arguments["search_parameters"]:
                    before_keywords = arguments["search_parameters"]["keywords"]
                    arguments["search_parameters"]["keywords"] = self.validate_keywords(
                        arguments["search_parameters"]["keywords"]
                    )
                    print(f"Keywords before validation: {before_keywords}")
                    print(f"Keywords after validation: {arguments['search_parameters']['keywords']}")
            
            print(f"Final arguments: {json.dumps(arguments, indent=2)}")

            print("\n=== PROCESS USER MESSAGE: Executing function ===")
            if function_name in function_mapping:
                print(f"Executing function: {function_name}")
                print(f"Function object: {function_mapping[function_name]}")
                try:
                    print(f"Arguments: {arguments}")
                    result = await function_mapping[function_name](**arguments)
                    print(f"Function execution completed")
                    print(f"Function result type: {type(result)}")
                    print(f"Function result: {json.dumps(result, indent=2) if result is not None else 'None'}")
                    if result is None:
                        print("WARNING: Function returned None")
                except Exception as e:
                    print(f"ERROR during function execution: {str(e)}")
                    print(f"Error type: {type(e)}")
                    result = {"error": f"Error executing function: {str(e)}"}
            else:
                print(f"ERROR: Function '{function_name}' not found in function_mapping")
                result = {"error": f"Function '{function_name}' not implemented."}

            print("\n=== PROCESS USER MESSAGE: Making second API call with function result ===")
            chat.append({
                'role': "function",
                "name": function_name,
                "content": json.dumps(result)
            })
            print(f"Updated chat context with function result. New length: {len(chat)}")

            try:
                # Context is then passed back to the api in order for it to respond to the user
                print("About to make second OpenAI API call")
                final_completion = client.chat.completions.create(
                    model='gpt-4o-mini',
                    messages=chat,
                    functions=functions,
                    temperature=0.3,
                    max_tokens=1024
                )
                print("Second API call completed successfully")
                
                print("\n=== Second API Response Details ===")
                print("Complete response object:")
                print(f"Response message: {final_completion.choices[0].message}")
                print(f"Response content: {final_completion.choices[0].message.content}")
                print(f"Response message dict: {vars(final_completion.choices[0].message)}")
                print("================================\n")

                final_message = final_completion.choices[0].message.content
                return_value = [{"message": final_message, "function": [function_name, json.dumps(result)]}]
            except Exception as e:
                print(f"ERROR during second API call: {str(e)}")
                print(f"Error type: {type(e)}")
                return_value = [{"message": f"Error processing function result: {str(e)}", "function": [function_name, json.dumps(result)]}]
        else:
            print("=== PROCESS USER MESSAGE: No function call needed ===")
            return_value = [{"message": response_content , "function": [""]}]
        
        print(f"=== PROCESS USER MESSAGE: Returning value ===")
        print(f"Return value: {json.dumps(return_value, indent=2)}")
        print("=== PROCESS USER MESSAGE: Complete ===\n")
        return return_value
            