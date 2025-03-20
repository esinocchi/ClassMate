import os 
from dotenv import load_dotenv
from openai import OpenAI
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Literal, Union
from pydantic import BaseModel, Field

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
    def __init__(self, student_name, student_id, courses,domain):
        self.student_name = student_name
        self.student_id = f"user_{student_id}"
        self.courses = courses
        self.domain = domain
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
                                "generality": {
                                    "type": "string",
                                    "enum": ["HIGH"],
                                    "description": "Generality of the search"
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
                                    "description": "ISO format dates (YYYY-MM-DD) mentioned in query"
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
                "name": "vectordb_search",
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
                                "generality": {
                                    "type": "string",
                                    "enum": ["HIGH"],
                                    "description": "Generality of the search"
                                },
                                "item_types": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "enum": ["assignment", "file", "quiz", "announcement", "event", "syllabus"]
                                    },
                                    "description": "Types of Canvas items to search for"
                                },
                                "specific_dates": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "format": "date"
                                    },
                                    "description": "ISO format dates (YYYY-MM-DD) mentioned in query"
                                },
                                "keywords": {
                                    "type": "array",
                                    "items": {
                                        "type": "string" 
                                    },
                                    "description": "Additional search terms like 'midterm', 'HW2', 'Quiz 3'"
                                }
                            },
                            "required": ["course_id", "time_range", "item_types"]
                        },
                        "query": {
                            "type": "string",
                            "description": "User's original query for semantic search"
                        }
                    },
                    "required": ["search_parameters", "query"]
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

            2. Keyword List Rules:
                - Keyword list should contain keywords that are relevant to the user's query, but should not be the same as any of the Compulsory elemnts mentioned in step 1. 
                - For example: If somebody asks you to retrieve all assignments related to Hooke's law, the keyword list should be ['Hooke's law']
                - Include synonyms or related terms if applicable
                - Max 10 items in the list

            3. Specific Cases:
                **Time Range Examples:**
                    - 'Due tomorrow' → FUTURE
                    - 'Posted yesterday' → RECENT_PAST
                    - 'From two weeks ago' → EXTENDED_PAST
                    - 'Any syllabus for the course' → ALL_TIME

                **When specific dates are mentioned:**
                    - Include both time range AND ISO date
                    - Example: 'What assignments have March 25th as a deadline' → ['all_courses', 'FUTURE', '[assignment]', '2025-03-25']
                    - Example: 'What is due in the last week of March' → ['all_courses', 'FUTURE', '[assignment]', '2025-03-25', '2025-03-31']

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
                    "generality": "HIGH"
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
    

    def find_events_and_assignments(self, search_parameters: dict):
        """Find events and assignments using the vector search function"""
        from backend.vectordb.vectordatabase import search
        user_id_number = self.student_id.split("_")[1]

        vector_db = VectorDatabase(f"user_data/psu/{user_id_number}/user_data.json")
        events_and_assignments = vector_db.search(search_parameters)
        
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
        for i in range(len(contextArray["context"][1]["content"])-1):
            print(f"\nProcessing message pair {i + 1}:")
            print(f"User message: {contextArray['context'][1]['content'][i]}")
            chat_history.append({"role": "user", "content":contextArray["context"][1]["content"][i]})
            
            print(f"Assistant content: {json.dumps(contextArray['context'][0]['content'][i], indent=2)}")
            if contextArray["context"][0]["content"][i]["function"] and contextArray["context"][0]["content"][i]["function"] != [""]:
                print(f"Function detected: {contextArray['context'][0]['content'][i]['function']}")
                chat_history.append({"role": "function","name":contextArray["context"][0]["content"][i]["function"][0], "content": contextArray["context"][0]["content"][i]["function"][1]})
            if len(contextArray["context"][0]["content"])-1 != i:
                chat_history.append({"role": "assistant", "content":contextArray["context"][0]["content"][i]["message"]})
        
        print("\n=== TRANSFORM USER MESSAGE: Final chat history ===")
        print(json.dumps(chat_history, indent=2))
        print("=== TRANSFORM USER MESSAGE: Complete ===\n")
        return chat_history
    
    async def process_user_message(self, chat_history: dict):
        """Process a user message and return the appropriate response"""
        print("\n=== PROCESS USER MESSAGE: Starting ===")
        
        print("=== PROCESS USER MESSAGE: Generating system context ===")
        # Generate the system context with enhanced instructions
        system_context = self.define_system_context()
        functions = self.define_functions()
        
        client = OpenAI(
            api_key=self.openai_api_key
        )

        function_mapping = {
            # "find_events_and_assignments": self.find_events_and_assignments,
            # "find_syllabus": self.find_syllabus,
            #"vectordb_search": self.vector_db.search,
            "create_event": create_event
        }

        chat = [
            {"role": "system", "content": system_context},
        ]
        
        chat.extend(chat_history)
        print(chat)
        print("=== PROCESS USER MESSAGE: Making first API call ===")
        # First API call to get function call or direct response
        chat_completion = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=chat,
            functions=functions,
            function_call = "auto",
            temperature=.3,
            max_tokens=1024
        )
        
        response_message = chat_completion.choices[0].message
        response_content = response_message.content
        print("\n=== First API Response Details ===")
        print("Complete response object:")
        print(f"Response message: {response_message}")
        print(f"Response content: {response_content}")
        print(f"Response message dict: {response_message.__dict__}")
        print("================================\n")
        
        print("\n=== PROCESS USER MESSAGE: Processing API response ===")
        # Check if there's a function call in the response
        function_call = response_message.function_call

        if function_call:
            print(f"Function call detected: {function_call.name}")
            function_name = function_call.name
            arguments = json.loads(function_call.arguments)
            
            print("=== PROCESS USER MESSAGE: Preparing function call ===")
            if function_name == "vectordb_search":
                if "search_parameters" in arguments and "keywords" in arguments["search_parameters"]:
                    arguments["search_parameters"]["keywords"] = self.validate_keywords(
                        arguments["search_parameters"]["keywords"]
                    )
            
            arguments["canvas_base_url"] = self.canvas_api_url
            arguments["access_token"] = self.canvas_api_token

            print("\n=== PROCESS USER MESSAGE: Executing function ===")
            if function_name in function_mapping:
                result = await function_mapping[function_name](**arguments)
                print(f"Function result: {json.dumps(result, indent=2)}")
            else:
                result = json.dumps({"error": f"Function '{function_name}' not implemented."})

            print("\n=== PROCESS USER MESSAGE: Making second API call with function result ===")
            chat.append({
                'role': "function",
                "name": function_name,
                "content": json.dumps(result)
            })
            print(chat)

            # Context is then passed back to the api in order for it to respond to the user
            final_completion = client.chat.completions.create(
                model='gpt-4o-mini',
                messages=chat,
                functions=functions,
                temperature=0.3,
                max_tokens=1024
            )
            print("\n=== First API Response Details ===")
            print("Complete response object:")
            print(f"Response message: {final_completion.choices[0].message}")
            print(f"Response content: {final_completion.choices[0].message.content}")
            print(f"Response message dict: {vars(final_completion.choices[0].message)}")
            print("================================\n")

            final_message = final_completion.choices[0].message.content
            return_value = [{"message": final_message, "function": [function_name, json.dumps(result)]}]
        else:
            print("=== PROCESS USER MESSAGE: No function call needed ===")
            return_value = [{"message": response_content , "function": [""]}]
        
        print("=== PROCESS USER MESSAGE: Complete ===\n")
        return return_value
            