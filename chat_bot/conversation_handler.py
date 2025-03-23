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
    def __init__(self, student_name, student_id, courses, domain, chat_history):
        self.student_name = student_name
        self.student_id = f"user_{student_id}"
        self.courses = courses
        self.domain = domain
        self.chat_history = chat_history
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
        self.generality_definitions = {
            "SPECIFIC": {
                "description": "Used when the user is looking for a single, clearly identified number of items with specific details",
                "examples": ["Get my assignment due tomorrow in CMPSC 465", "What are my next 3 assingnemnts"],
                "result_type": "Very targeted set of results"
            },
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
                                    "description": "Course ID or 'all_courses'"
                                },
                                "time_range": {
                                    "type": "string", 
                                    "enum": ["FUTURE", "RECENT_PAST", "EXTENDED_PAST", "ALL_TIME"],
                                    "description": "Temporal context for search"
                                },
                                 "generality": {
                                    "type": "string", 
                                    "enum": ["LOW", "MEDIUM", "HIGH", "SPECIFIC"],
                                    "description": "Context for how many items to retrieve"
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
                                    "description": "Additional search terms (e.g., 'midterm', 'HW2', 'Quiz 3')."
                                },
                                "query": {
                                    "type": "string",
                                    "description": "User's original query for semantic search"
                                }
                            },
                            "required": ["course_id", "time_range", "item_types", "specific_dates", "keywords", "query"]
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
                                    "description": "Specific Course ID(s) (e.g. 2372294) when mentioned by the user. 'all_courses': if the user asks for information about all courses or they don't mention a specific course"
                                },
                                "time_range": {
                                    "type": "string", 
                                    "enum": ["FUTURE", "RECENT_PAST", "EXTENDED_PAST", "ALL_TIME"],
                                    "description": "Temporal context for search"
                                },
                                "generality": {
                                    "type": "string", 
                                    "enum": ["LOW", "MEDIUM", "HIGH", "SPECIFIC"],
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
                                    "description": "ISO8601 format dates mentioned in query if a specific date is mentioned. If no specific date is mentioned,this should be today's date in ISO8601 format (e.g. 2025-03-21)"
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
                            "required": ["course_id", "time_range", "item_types", "specific_dates", "keywords", "query"]
                        },
                        
                    },
                    "required": ["search_parameters"]
                }
            },
            {
                "name": "create_notes",
                "description": "Create a note using the vector search function",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
            
        ]
        return functions
    
    def define_system_context(self):
        current_time = datetime.now(timezone.utc).isoformat()
        system_context = f"""
            [ROLE & IDENTITY]
            You are a highly professional, task-focused AI assistant for {self.student_name} (User ID: {self.student_id}). You are dedicated to providing academic support while upholding the highest standards of academic integrity. You only assist with tasks that are ethically appropriate.

            [STUDENT INFORMATION & RESOURCES]
            - Courses: {self.courses} (Each key is the course name, each value is the corresponding course ID)
            - Valid Item Types: {self.valid_types}
            - Time Range Definitions: {self.time_range_definitions}

            [GENERAL TASKS]
            You assist with:
            - Coursework help
            - Study note creation
            - Video transcription
            - Retrieving Canvas LMS information (e.g., syllabus details, assignment deadlines, course updates)
            - Creating events when requested

            [DATE & TIME]
            - Current UTC Time: {current_time}
            - All dates and times must be in ISO8601 format.
            - Use the current UTC time as your reference for “now.”

            [INSTRUCTIONS FOR FUNCTION CALLS]
            1. **When to Call a Function:**
            - If the user’s query requires additional information or action (e.g., retrieving Canvas data or creating an event), you must call the appropriate function from the provided function list.

            2. **Keyword Extraction for Retrieval:**
            - Extract a concise list of keywords from the user’s prompt, ensuring the following elements are captured:
                - **Course:** Include both the course name and its course ID (from {self.courses}). If a course is not mentioned, default to "all_courses".
                - **Time Range:** Select from {self.time_range_definitions} (e.g., FUTURE, RECENT_PAST, EXTENDED_PAST, ALL_TIME).
                - **Generality:** Select from {self.generality_definitions} (e.g., LOW, MEDIUM, HIGH, SPECIFIC).
                - **Item Types:** Choose from {self.valid_types}.
                - **Specific Dates:** Use date or date range mentioned by the user.
                - **Synonyms/Related Terms:** Include relevant synonyms (e.g., for "exam", include "midterm" and "final").
            - **Rules:**
                - The keyword list must contain a maximum of 10 items.
                - Do not duplicate the compulsory elements; include only additional relevant keywords.

            3. **JSON Response Structure for Function Calls:**
            - For Canvas search queries, respond with a valid JSON object in the following exact format:
                ```
                {{
                "parameters": {{
                    "search_parameters": {{
                    "course_id": "<course_id>",
                    "time_range": "<FUTURE|RECENT_PAST|EXTENDED_PAST|ALL_TIME>",
                    "generality": "<LOW|MEDIUM|HIGH|SPECIFIC>",
                    "item_types": ["assignment", "quiz", ...],
                    "specific_dates": ["YYYY-MM-DD", "YYYY-MM-DD"],
                    "keywords": ["keyword1", "keyword2", ...],
                    "query": "<original user query>"
                    }}
                }}
                }}
                ```
            - For event creation requests, generate arguments as defined in the function list. Once the event is created, respond with a clear confirmation message such as “The event has been created.”

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
            
            Remember, your final response to the user must always be clear, confirming the action taken (e.g., “I have created the event”) if a function call was executed, or directly addressing the query if not.
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
            course_information = await vector_db.search(search_parameters) 
        except Exception as e:
            print(f"ERROR in vector_db.search: {str(e)}")
            print(f"Error type: {type(e)}")
            course_information = []
        
        return course_information
          
    async def create_notes(self, search_parameters: dict):
        
        return
    
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
    

    def transform_user_message(self, context: ContextObject):
        print("\n=== TRANSFORM USER MESSAGE: Starting ===")
        chat_history = []
        
        print("=== TRANSFORM USER MESSAGE: Parsing context array ===")
        print(f"Context Array Structure:")
        context_array = context
        print(json.dumps(context_array, indent=2))
        
        print("\n=== TRANSFORM USER MESSAGE: Processing messages ===")

        for i in range(len(context_array[1]["content"])-1,-1,-1):
            print(f"\nProcessing message pair {i + 1}:")
            chat_history.append({"role": "user", "content":context_array[1]["content"][i]})
            
            print(f"Assistant content: {json.dumps(context_array[0]['content'][i], indent=2)}")
            if context_array[0]["content"][i]["function"] and context_array[0]["content"][i]["function"] != [""]:
                print(f"Function detected: {context_array['context'][0]['content'][i]['function']}")
                chat_history.append({"role": "function","name":context_array[0]["content"][i]["function"][0], "content": context_array[0]["content"][i]["function"][1]})
            if i != 0:
                chat_history.append({"role": "assistant", "content":context_array[0]["content"][i]["message"]})
        
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
            "find_course_information": self.find_course_information,
            "create_notes": self.create_notes,
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
            print("goon")
            print(chat)
            try:
                # Context is then passed back to the api in order for it to respond to the user
                print("About to make second OpenAI API call")
                final_completion = client.chat.completions.create(
                    model='gpt-4o-mini',
                    messages=chat,
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
                print(final_message)
                return_value = {"message": final_message, "function": [function_name, json.dumps(result)]}
                self.chat_history["context"][0]["content"][0] = return_value
                
            except Exception as e:
                print(f"ERROR during second API call: {str(e)}")
                print(f"Error type: {type(e)}")
                return_value = [{"message": f"Error processing function result: {str(e)}", "function": [function_name, json.dumps(result)]}]
                self.chat_history["context"][0]["content"][0] = return_value
        else:
            print("=== PROCESS USER MESSAGE: No function call needed ===")
            content = {"message": response_content , "function": [""]}
            self.chat_history["context"][0]["content"][0] = content
       
        return self.chat_history
            