import asyncio
import os 
from dotenv import load_dotenv
from openai import OpenAI
import json
import sys
from pathlib import Path
import tzlocal
from datetime import datetime
from typing import List, Union
from pydantic import BaseModel
from backend.task_specific_agents.lecture_to_notes_agent import lecture_file_to_notes_pdf
from backend.task_specific_agents.grade_calculator_agent import calculate_grade

# Add the project root directory to Python path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from backend.task_specific_agents.calendar_agent import create_event

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
canvas_api_token = os.getenv("CANVAS_API_KEY")



class ConversationHandler:
    def __init__(self, student_name, student_id, courses, domain, chat_history,canvas_api_token):
        self.student_name = student_name
        self.student_id = student_id
        self.courses = courses
        self.domain = domain
        self.chat_history = chat_history
        self.canvas_api_url = domain
        self.canvas_api_token = canvas_api_token
        self.openai_api_key = openai_api_key
        self.hf_api_token = os.getenv("HUGGINGFACE_API_KEY")
        # Define valid types and time range definitions
        self.valid_types = ["assignment", "file", "quiz", "announcement", "event", "syllabus"]
        self.time_range_definitions = {
            "NEAR_FUTURE": {
                "description": "Items within the next 10 days, including upcoming assignments.",
                "logic": "now <= item <= now + 10d"
            },
            "FUTURE": {
                "description": "Items to occur after the next 10 days.",
                "logic": "now + 10d <= item"
            },
            "RECENT_PAST": {
                "description": "Items occurred within the past 10 days.",
                "logic": "now - 10d <= item <= now"
            },
            "PAST": {
                "description": "Items occurred before the past 10 days.",
                "logic": "item <= now - 10d"
            },
            "ALL_TIME": {
                "description": "Items that exist at any point in time, regardless of when.",
                "logic": "item exists"
            }
        }
        self.generality_definitions = {
            
            "LOW": {
                "description": "Used when the user is looking for a small set of focused results about a narrow topic",
                "examples": ["Find quizzes about neural networks in CMPSC 444", "Show me this week's assignments"],
                "result_type": "Focused set of results"
            },
            "MEDIUM": {
                "description": "Default level. Used for balanced queries that need a moderate number of results",
                "examples": ["What assignments do I have?", "Show my upcoming deadlines"],
                "result_type": "Balanced set of results"
            },
            "HIGH": {
                "description": "Used for broad, exploratory queries or when comprehensiveness is important",
                "examples": ["Show me everything for my Biology class", "What are the assignments for this semester in Physics?"],
                "result_type": "Comprehensive set of results"
            }
        }


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
                                    "description": "Specific Course ID(s) (e.g. 2372294) when mentioned by the user. 'all_courses': if the user asks for information about all courses or they don't mention a specific course"
                                },
                                "time_range": {
                                    "type": "string", 
                                    "enum": ["NEAR_FUTURE", "FUTURE", "RECENT_PAST", "PAST", "ALL_TIME"],
                                    "description": "Temporal context for search"
                                },
                                "generality": {
                                    "type": "string", 
                                    "enum": ["LOW", "MEDIUM", "HIGH"],
                                    "description": "Context for how many items to retrieve"
                                },
                                "item_types": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "enum": ["assignment","quiz","event", "syllabus"]
                                    },
                                    "description": "This should always be ['assignments','events']"
                                },
                                "specific_dates": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "format": "date"
                                    },
                                    "description": "ISO8601 format dates mentioned in query if a specific date is mentioned."
                                },
                                "keywords": {
                                    "type": "array",
                                    "items": {
                                        "type": "string" 
                                    },
                                    "description": "keywords from the user's query to help with semantic search"
                                },
                                "query": {
                                    "type": "string",
                                    "description": "User's original query for semantic search"
                                }
                            },
                            "required": ["course_id", "time_range", "item_types","generality","keywords", "query"]
                        }
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
                            "description": "This should always be the students user id. This should be in the form "
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
                        },
                        "canvas_base_url": {
                            "type": "string",
                            "description": "This should the provided domain of the user"
                        }
                    },
                    "required": [
                        "context_code",
                        "title",
                        "start_at",
                        "canvas_base_url"
                    ]
                }
            },
            {
                "name": "find_course_information",
                "description": "Find course information using the vector search function",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_parameters": {
                            "type": "object",
                            "properties": {
                                "course_id": {
                                    "type": "string",
                                    "description": "Specific Course ID(s) (e.g. 2372294) when mentioned by the user. 'all_courses': if the user asks for information about all courses"
                                },
                                "time_range": {
                                    "type": "string", 
                                    "enum": ["NEAR_FUTURE", "FUTURE", "RECENT_PAST", "PAST", "ALL_TIME"],
                                    "description": "Temporal context for search"
                                },
                                "generality": {
                                    "type": "string", 
                                    "enum": ["LOW", "MEDIUM", "HIGH"],
                                    "description": "Context for how many items to retrieve"
                                },
                                "item_types": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "enum": ["assignment", "file", "quiz", "announcement", "event", "syllabus"]
                                    },
                                    "description": "This should always be ['syllabus']"
                                },
                               "specific_dates": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "format": "date"
                                    },
                                    "description": "ISO8601 format dates mentioned in query if a specific date is mentioned."
                                },
                                "keywords": {
                                    "type": "array",
                                    "items": {
                                        "type": "string" 
                                    },
                                    "description": "This should always be ['course information','course materials'] l"
                                },
                                "query": {
                                    "type": "string",
                                    "description": "User's original query for semantic search"
                                }
                            },
                            "required": ["course_id", "time_range", "item_types","generality","keywords", "query"]
                        }
                    },
                    "required": ["search_parameters"]
                }
            },
            {
                "name": "create_notes",
                "description": "Create notes for a file found in the vector search function",
                "parameters": {
                  "type": "object",
                    "properties": {
                       "user_id": {
                       "type": "string",
                            "description": "The user's ID number"
                       },
                       "domain": {
                            "type": "string",
                            "description": "The user's canvas base url"
                        },
                           "search_parameters": {
                            "type": "object",
                            "properties": {
                            "course_id": {
                                    "type": "string",
                                    "description": "Specific Course ID"
                                },
                                "time_range": {
                                    "type": "string", 
                                    "enum": ["NEAR_FUTURE", "FUTURE", "RECENT_PAST", "PAST", "ALL_TIME"],
                                    "description": "Temporal context for search"
                                },
                                "generality": {
                                    "type": "string", 
                                    "enum": ["LOW", "MEDIUM", "HIGH",],
                                    "description": "Context for how many items to retrieve"
                                },
                            "item_types": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "enum": ["assignment", "file", "quiz", "announcement", "event", "syllabus"]
                                    },
                                    "description": "This should always be ['file']"
                                },
                                "specific_dates": {
                                "type": "array",
                                    "items": {
                                        "type": "string",
                                        "format": "date"
                                    },
                                    "description": "ISO8601 format dates mentioned in query if a specific date is mentioned."
                                },
                                "keywords": {
                                "type": "array",
                                    "items": {
                                        "type": "string" 
                                    },
                                    "description": "This should always be ['lecture','notes','slides']"
                                },
                                "query": {
                                    "type": "string",
                                    "description": "User's original query for semantic search"
                                }
                            },
                            "required": ["course_id", "time_range", "item_types", "generality", "keywords", "query"]
                        }
                    },
                       "required": ["user_id", "domain", "search_parameters"]
                }
            },
            {
                "name": "calculate_grade",
                "description": "Calculate the grade required to achieve a certain letter grade on an assignment",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_grade_letter": {
                            "type": "string",
                            "description": "The target grade letter of the assignment"
                        },
                        "student_id": {
                            "type": "string",
                            "description": "The user's ID number"
                        },
                        "search_parameters": {
                            "type": "object",
                            "properties": {
                                "course_id": {
                                    "type": "string",
                                    "description": "Specific Course ID"
                                },
                                "time_range": {
                                    "type": "string", 
                                    "enum": ["NEAR_FUTURE", "FUTURE", "RECENT_PAST", "PAST", "ALL_TIME"],
                                    "description": "Temporal context for search"
                                },
                                "generality": {
                                    "type": "string", 
                                    "enum": ["LOW", "MEDIUM", "HIGH",],
                                    "description": "Context for how many items to retrieve"
                                },
                                "item_types": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "enum": ["assignment", "file", "quiz", "announcement", "event", "syllabus"]
                                    },
                                    "description": "This should always be ['assignment']"
                                },
                                "specific_dates": {
                                    "type": "array",
                                    "items": {
                                        "type": "string",
                                        "format": "date"
                                    },
                                    "description": "ISO8601 format dates mentioned in query if a specific date is mentioned."
                                },
                                "keywords": {
                                    "type": "array",
                                    "items": {
                                        "type": "string" 
                                    },
                                    "description": "this should always be ['assignment']"
                                },
                                "query": {
                                    "type": "string",
                                    "description": "User's original query for semantic search"
                                }
                            },
                            "required": ["course_id", "time_range", "item_types", "generality", "keywords", "query"]
                        }
                    }   
                },
                "required": ["target_grade_letter","student_id", "search_parameters"]
            }
        ]
        return functions
    
    def define_system_context(self):
        local_tz = tzlocal.get_localzone()
        current_time = datetime.now(local_tz).strftime("%Y-%m-%d %I:%M %p")
        system_context = f"""
            [ROLE & IDENTITY]
            You are a highly professional, task-focused AI assistant for {self.student_name!s} (User ID: {self.student_id!s}). You are dedicated to providing academic support while upholding the highest standards of academic integrity. You only assist with tasks that are ethically appropriate.

            [STUDENT INFORMATION & RESOURCES]
            - Courses: {self.courses!r} (Each key is the course name, each value is the corresponding course ID)
            - The user's canvas base url: {self.domain!s}
            - Valid Item Types: {self.valid_types!r}
            - Time Range Definitions: {self.time_range_definitions!r}

            [GENERAL TASKS]
            You assist with:
            - Coursework help
            - Study note creation
            - Video transcription
            - Retrieving Canvas LMS information (e.g., syllabus details, assignment deadlines, course updates)
            - Creating events when requested

            [DATE & TIME]
            - Current Time: {current_time!s}
            - All dates and times must be in ISO8601 format.
            - Use the current time as your reference for "now."

            [INSTRUCTIONS FOR FUNCTION CALLS]
            1. **When to Call a Function:**
            - If the user's query requires additional information or action (e.g., retrieving Canvas data or creating an event), you must call the appropriate function from the provided function list.
            - Call the create_notes function if the user specifically asks to create notes from a file
            - Call the calculate_grade function if the user wants to know the grade required to achieve a certain letter grade on an assignment.
            - Call the create_event function if the user wants to create an event.
            - Call the find_course_information function if the user wants to know information about a course from the syllabus. (Note: this could be about office hours, grading scale, etc.)
            - Call the find_events_and_assignments function if the user wants to know about any other information that would not be on the syllabus. (Note: this could be about finding an assignment, event, announcement, file, etc.)


            2. **Search Parameter Extraction for Retrieval:**
            - Extract a concise search parameters from the user's prompt, ensuring the following elements are captured:
                - **Course:** The course ID (from {self.courses!r}). If a course is not mentioned or if somebody mentions all courses, default to "all_courses".
                - **Time Range:** Select from {self.time_range_definitions!r} (e.g., FUTURE, RECENT_PAST, EXTENDED_PAST, ALL_TIME).
                - **Generality:** Select from {self.generality_definitions!r} (e.g., LOW, MEDIUM, HIGH, SPECIFIC).
                - **Item Types:** Choose from {self.valid_types!r}.
                - **Specific Dates:** Use date mentioned by the user. Only ever include dates if the user mentions a specific date. Do no try and infer dates.
                - **Keywords:** Extract a concise list of keywords from the user's prompt. Keywords should be specific and unique to the user's query.
                - **Synonyms/Related Terms:** Include relevant synonyms (e.g., for "exam", include "midterm" and "final").
            - **Rules:**
                - Search parameters must be specific and unique to the user's query.
                - Do not duplicate the compulsory elements; include only additional relevant search parameters.

            3. **JSON Response Structure for Function Calls:**
            - For Canvas search queries, respond with a valid JSON object in the following exact format, but only include the parameters that are needed for the function call:
                
                {{
                    "search_parameters": {{
                    "course_id": "<course_id>",
                    "time_range": "<FUTURE|RECENT_PAST|EXTENDED_PAST|ALL_TIME>",
                    "generality": "<LOW|MEDIUM|HIGH|SPECIFIC#>",
                    "item_types": ["assignment", "quiz", ...],
                    "specific_dates": ["YYYY-MM-DD", "YYYY-MM-DD"],
                    "keywords": ["keyword1", "keyword2", ...],
                    "query": "<original user query>"
                    }}
                }}
                
                
            - For event and assignment retrieval requests, generate arguments as defined in the function list. 
            - For event creation requests, generate arguments as defined in the function list. 
            - For course information requests, generate arguments as defined in the function list.
            - For grade calculation requests, the arguments should be student_id, target_grade_letter, and search_parameters. Make sure the search parameters are based on the format outlined above. The course_id for this funciton should always be a specific classes course id. Never imput "all courses" for this function.

            4. Specific Instructions for function calls:

            **Create Notes Function:**
                - In order to create notes, you must find the exact file that the user wants to create notes from
                - Keywords for this function is very important. Look at the user's query and try to find any indicators of a file name. Include that file name as a keyword.
                - Call this function only if the user specifically asks to create notes from a file

            **Calculate Grade Function:**
                - In order to calculate the grade, you must find the exact assignment that the user wants to calculate the grade for.
                - Keywords for this function is very important. Look at the user's query and try to find any indicators of an assignment name. Include that assignment name as a keyword.

            [RESPONSE GUIDELINES]
            - **If No Function Call Is Needed:**  
            Respond directly to the user in plain language with a clear, concise message.

            - **Tone & Style:**
            - Maintain professionalism and clarity.
            - Use plain, accessible language suitable for academic settings.
            - Be precise, reliable, and structured in your responses.
            
            [FAIL-SAFE MEASURES]
            - **Time Range Fail-Safe:** If unsure, default to "ALL_TIME".
            - **Course Fail-Safe:** If the course mentioned does not match exactly, select the closest course based on string similarity.
            - **Generality Fail-Safe:** If the user does not specify a generality, default to "MEDIUM".
            - **Function Fail-Safe:** If unsure about which function to call, default to "find_assignments_and_events".   
            """
        
        return system_context
    
    def define_system_context_for_function_output(self):
        local_tz = tzlocal.get_localzone()
        current_time = datetime.now(local_tz).strftime("%Y-%m-%d %I:%M %p")
        system_context = f"""
            [ROLE & IDENTITY]
            You are a highly professional, task-focused AI assistant for {self.student_name} (User ID: {self.student_id}). You are dedicated to providing academic support while upholding the highest standards of academic integrity. You only assist with tasks that are ethically appropriate.
            
            [STUDENT INFORMATION & RESOURCES]
            - Courses: {self.courses} (Each key is the course name, each value is the corresponding course ID)
            
            [DATE & TIME]
            - Current UTC Time: {current_time}
            - Use the current UTC time as your reference for "now."
            - When reviewing the search results in the chat context, ensure to reference 'local time' for the timestamps of the documents. For example, a due date would be "Due Date: April 10, 2025, at 11:59 PM EST", when EST is the local time.

            [Instructions for Function Output]
            - For event creation requests, respond with a clear confirmation message such as "The event has been created."
            - For course information requests, you are going to be given a string of text containing the course syllabus. Retrieve information from the text based on the user's query.
            - For assignment and event retrieval requests, you are going to be given a list of assignments and events. Retrieve the information from the list based on the user's query. 
            -For calculating grade requirements, you are going to be ouptuted a required score. This is the score that the user needs to achieve on an assignment to get a certain letter grade. Output with a message like "You need this required score to maintain an A in the class."

        """
        return system_context
    
    async def find_events_and_assignments(self, search_parameters: dict):
        """Find events and assignments using the vector search function"""
        print("\n=== FIND_EVENTS_AND_ASSIGNMENTS: Starting ===")
        print(f"Search parameters received: {json.dumps(search_parameters, indent=2)}")
        
        from vectordb.db import VectorDatabase
        
        user_id_number = self.student_id.split("_")[1]
        
        vector_db_path = f"user_data/psu/{user_id_number}/user_data.json"
        
        print("Initializing VectorDatabase...")
        vector_db = VectorDatabase(vector_db_path, hf_api_token=self.hf_api_token)
        await vector_db.load_local_data_from_json()
        
        print("Calling vector_db.search...")
        try:
            events_and_assignments = await vector_db.search(search_parameters=search_parameters)
        except Exception as e:
            print(f"ERROR in vector_db.search: {str(e)}")
            print(f"Error type: {type(e)}")
            events_and_assignments = []
        print(f"Retrieval: {events_and_assignments}")
        return events_and_assignments

    async def find_course_information(self, search_parameters: dict):
        """Find course information using the vector search function
           Pulls syllabus, course description, and course materials from the vector database.
           Extracts text from the syllabus and course description and returns it to the openai api.
           The search parameters are:
            - course_id
            - time_range
            - item_types
            - specific_dates
            - keywords
            - generality
            - query
        """
        from vectordb.db import VectorDatabase
        
        user_id_number = self.student_id.split("_")[1]
        
        vector_db_path = f"user_data/psu/{user_id_number}/user_data.json"
        
        vector_db = VectorDatabase(vector_db_path, hf_api_token=self.hf_api_token)
        await vector_db.load_local_data_from_json()
        
        print("Calling vector_db.search...")

        try:
            course_information = await vector_db.search(search_parameters) 
        except Exception as e:
            print(f"ERROR in vector_db.search: {str(e)}")
            print(f"Error type: {type(e)}")
            course_information = []
        
        return course_information

    async def find_file(self, search_parameters: dict):
        """Find a file using the vector search function"""
        print("\n=== FIND_FILE: Starting ===")
        print(f"Search parameters received: {json.dumps(search_parameters, indent=2)}")
        from vectordb.db import VectorDatabase
        
        user_id_number = self.student_id.split("_")[1]
        
        vector_db_path = f"user_data/psu/{user_id_number}/user_data.json"
        
        print("Initializing VectorDatabase...")
        vector_db = VectorDatabase(vector_db_path, hf_api_token=self.hf_api_token)
        await vector_db.load_local_data_from_json()
        
        try:
            file = await vector_db.search(search_parameters, function_name="find_file") 
        except Exception as e:
            print(f"ERROR in vector_db.search: {str(e)}")
            print(f"Error type: {type(e)}")
            file = []
        
        file_description = [file[0]["document"]["filename"], file[0]["document"]["url"]]
        return file_description

    async def create_notes(self, user_id: str, domain: str, search_parameters: dict):
        """Create notes for a file using the vector search function"""
        from backend.task_specific_agents.lecture_to_notes_agent import get_file_name_without_type
        search_parameters["specific_dates"] = [""]
        search_parameters["item_types"] = ["file"]
        file_description = await self.find_file(search_parameters)
        file_name = file_description[0]
        file_url = file_description[1]
        return_value = get_file_name_without_type(file_name)

        print("=== CREATE NOTES: Starting ===")
        print(f"File URL: {file_url}")
        print(f"File Name: {file_name}")
        print(f"User ID: {user_id}")
        print(f"Domain: {domain}")

        lecture_file_to_notes_pdf(file_url = file_url, file_name = file_name, user_id = user_id.split("_")[1], domain = domain, canvas_api_token = self.canvas_api_token)
        return return_value

    
    def validate_search_parameters(self, search_parameters):
        """Validates search parameters and enables fail-safes"""
        # Course ID check
        if search_parameters["course_id"] not in self.courses.values() and search_parameters["course_id"] != "all_courses":
            search_parameters["course_id"] = "all_courses"
        
        return search_parameters
    

    def transform_user_message(self, context: ContextObject):
        print("\n=== TRANSFORM USER MESSAGE: Starting ===")
        chat_history = []
        
        print("=== TRANSFORM USER MESSAGE: Parsing context array ===")
        print(f"Context Array Structure:")
        context_array = context
        
        print("\n=== TRANSFORM USER MESSAGE: Processing messages ===")

        for i in range(len(context_array.context[1].content)-1,-1,-1):
            print(f"\nProcessing message pair {i + 1}:")
            chat_history.append({"role": "user", "content":context_array.context[1].content[i]})
            
            if context_array.context[0].content[i].function and context_array.context[0].content[i].function != [""]:
                print(f"Function detected: {context_array.context[0].content[i].function}")
                chat_history.append({"role": "function","name":context_array.context[0].content[i].function[0], "content": context_array.context[0].content[i].function[1]})
            if i != 0:
                chat_history.append({"role": "assistant", "content":context_array.context[0].content[i].message})
        
        print("\n=== TRANSFORM USER MESSAGE: Final chat history ===")
        print("=== TRANSFORM USER MESSAGE: Complete ===\n")
        return chat_history
    
    async def process_user_message(self, chat_history: dict):
        """Process a user message and return the appropriate response"""
        print("\n=== PROCESS USER MESSAGE: Starting ===")
        
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
            "find_course_information": self.find_course_information,
            "create_notes": self.create_notes,
            "create_event": create_event,
            "calculate_grade": calculate_grade
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
            chat_completion = client.chat.completions.create(
                model='gpt-4o',
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
                if function_name == "create_event" or function_name == "calculate_grade":
                    arguments["canvas_base_url"] = self.canvas_api_url
                    arguments["access_token"] = self.canvas_api_token
                    if function_name == "calculate_grade":
                        arguments["hf_api_token"] = self.hf_api_token

            except json.JSONDecodeError as e:
                print(f"ERROR decoding function arguments: {str(e)}")
                print(f"Raw arguments: {function_call.arguments}")
                return [{"message": "Error processing function arguments", "function": [""]}]
            
            print("=== PROCESS USER MESSAGE: Preparing function call ===")
                    
            

            print("\n=== PROCESS USER MESSAGE: Executing function ===")
            if function_name in function_mapping:
                print(f"Executing function: {function_name}")
                print(f"Function object: {function_mapping[function_name]}")
                try:
                    print(f"Arguments: {arguments}")
                    if function_name != "create_notes":
                        result = await function_mapping[function_name](**arguments)
                    print(f"Function execution completed")
                    print(f"Function result type: {type(result)}")
                    if result is None:
                        print("WARNING: Function returned None")
                except Exception as e:
                    print(f"ERROR during function execution: {str(e)}")
                    print(f"Error type: {type(e)}")
                    result = {"error": f"Error executing function: {str(e)}"}
            else:
                print(f"ERROR: Function '{function_name}' not found in function_mapping")
                result = {"error": f"Function '{function_name}' not implemented."}

            print("\n=== PROCESS USER MESSAGE: Makixng second API call with function result ===")

            if function_name == "create_notes":
                return_value = {"message": "Your PDF has been created.", "function": [function_name, json.dumps(arguments), "arrays-pointers"]}
                self.chat_history.context[0].content[0] = return_value
                return self.chat_history

            
            chat.append({
                'role': "function",
                "name": function_name,
                "content": json.dumps(result)
            })

            
           
            try:
                # Context is then passed back to the api in order for it to respond to the user
                system_context_for_function_output = self.define_system_context_for_function_output()
                chat[0]["content"] = system_context_for_function_output
                print("About to make second OpenAI API call")
                final_completion = client.chat.completions.create(
                    model='gpt-4o',
                    messages=chat,
                    temperature=0.3,
                    max_tokens=1024
                )
                print("Second API call completed successfully")
                
                """print("\n=== Second API Response Details ===")
                print("Complete response object:")
                print(f"Response message: {final_completion.choices[0].message}")
                print(f"Response content: {final_completion.choices[0].message.content}")
                print(f"Response message dict: {vars(final_completion.choices[0].message)}")
                print("================================\n")"""
                final_message = final_completion.choices[0].message.content
                print(final_message)
                return_value = {"message": final_message, "function": [function_name, json.dumps(result)]}
                self.chat_history.context[0].content[0] = return_value
                
            except Exception as e:
                print(f"ERROR during second API call: {str(e)}")
                print(f"Error type: {type(e)}")
                return_value = [{"message": f"Error processing function result: {str(e)}", "function": [function_name, json.dumps(result)]}]
                self.chat_history.context[0].content[0] = return_value
        else:
            print("=== PROCESS USER MESSAGE: No function call needed ===")
            content = {"message": response_content , "function": [""]}
            self.chat_history.context[0].content[0] = content
       
        return self.chat_history

            