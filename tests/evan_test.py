#!/usr/bin/env python3
"""
Test script for locally testing the ChatBot pipeline functionality
without making HTTP requests to the actual endpoints.

This script simulates the endpoints defined in endpoints.py and 
allows testing the conversation flow from prompt to output while
maintaining chat history.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import the necessary modules
from chat_bot.conversation_handler import ConversationHandler
from backend.data_retrieval.data_handler import DataHandler
from vectordb.db import VectorDatabase
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Improved class to convert dictionaries to objects with subscript support
class DictToObj:
    def __init__(self, d):
        # If d is already a DictToObj, extract its _data
        if isinstance(d, DictToObj):
            d = d._data
        
        self._data = d  # Store original data
        
        # Only process if d has an items method (is dict-like)
        if hasattr(d, 'items'):
            for key, value in d.items():
                if isinstance(value, dict):
                    setattr(self, key, DictToObj(value))
                elif isinstance(value, list):
                    # Convert each item in the list if it's a dict
                    new_list = []
                    for item in value:
                        if isinstance(item, dict):
                            new_list.append(DictToObj(item))
                        else:
                            new_list.append(item)
                    setattr(self, key, new_list)
                else:
                    setattr(self, key, value)
    
    # Support for dictionary-style access with ["key"]
    def __getitem__(self, key):
        if hasattr(self, key):
            return getattr(self, key)
        return self._data[key]
    
    # Support for dictionary-style setting with ["key"] = value
    def __setitem__(self, key, value):
        setattr(self, key, value)
        self._data[key] = value
    
    # Support for 'in' operator
    def __contains__(self, key):
        return key in self._data
    
    # Return the underlying dictionary by reconstructing it from attributes
    def to_dict(self):
        reconstructed_dict = {}
        for key, value in self.__dict__.items():
            if key == '_data':  # Skip the internal reference to the original dict
                continue
            
            # Recursively call to_dict if the value is another DictToObj
            if isinstance(value, DictToObj):
                reconstructed_dict[key] = value.to_dict()
            # Handle lists: recursively call to_dict for DictToObj items
            elif isinstance(value, list):
                new_list = []
                for item in value:
                    if isinstance(item, DictToObj):
                        new_list.append(item.to_dict())
                    else:
                        new_list.append(item)
                reconstructed_dict[key] = new_list
            # Otherwise, just use the value
            else:
                reconstructed_dict[key] = value
        return reconstructed_dict
    
    # Support for dictionary methods
    def items(self):
        return self._data.items()
    
    def keys(self):
        return self._data.keys()
    
    def values(self):
        return self._data.values()

class TestChatbot:
    def __init__(self, user_id: str, domain: str = "psu.instructure.com"):
        """Initialize the test chatbot with user ID and domain."""
        self.user_id = user_id
        self.domain = domain
        self.chat_history_dict = None  # Store the dictionary version
        self.data_handler = DataHandler(user_id, domain)
        
        # Check if user data exists, if not initialize it
        if not self.data_handler.has_saved_data():
            print("No saved data found. Initializing user data...")
            token = os.getenv("CANVAS_API_TOKEN")
            self.data_handler = DataHandler(user_id, domain, token)
            self.data_handler.initiate_user_data()
        
        # Get selected courses
        self.selected_courses = self._get_selected_courses()
        
        # Initialize chat history
        self._init_chat_history()
    
    def _get_selected_courses(self) -> Dict[str, str]:
        """Get the selected courses from user data."""
        user_data = self.data_handler.grab_user_data()
        return user_data["user_metadata"]["courses_selected"]
    
    def _init_chat_history(self):
        """Initialize the chat history."""
        # Create the initial context structure
        assistant_entry = {
            "role": "assistant",
            "content": [{"message": "", "function": [""]}]
        }
        
        # Create class objects for each selected course
        classes = []
        for course_id, course_name in self.selected_courses.items():
            class_dict = {
                "id": course_id,
                "name": course_name,
                "selected": True
            }
            classes.append(class_dict)
        
        # Create user entry
        user_entry = {
            "role": "user",
            "user_id": self.user_id,
            "domain": self.domain,
            "recentDocs": [],
            "content": [],
            "classes": classes
        }
        
        # Create the full context object
        self.chat_history_dict = {"context": [assistant_entry, user_entry]}
    
    async def process_message(self, message: str) -> str:
        """
        Process a user message and return the response.
        
        Args:
            message: The user's input message
            
        Returns:
            The assistant's response
        """
        # Check if chat_history_dict is a DictToObj and convert to dict if needed
        if isinstance(self.chat_history_dict, DictToObj):
            self.chat_history_dict = self.chat_history_dict.to_dict()
        
        # Add user message to chat history
        self.chat_history_dict["context"][1]["content"] = [message]
        
        # Check if we should update local data
        if message.lower().startswith(("refresh data", "update data")):
            print("Updating user data...")
            self.data_handler.update_user_data()
            return "User data is being updated in the background. This may take a few minutes."
        
        # Process the message through the conversation handler
        print(f"\n=== STAGE 1: Starting conversation processing ===")
        user_data = self.data_handler.grab_user_data()
        user_name = user_data["user_metadata"]["name"]
        user_token = user_data["user_metadata"]["token"]
        
        # Extract selected courses
        courses = {}
        for class_info in self.chat_history_dict["context"][1]["classes"]:
            if class_info["selected"]:
                course_id = class_info["id"].replace('course_', '')
                courses[class_info["name"]] = course_id
        
        print("=== STAGE 2: Initializing ConversationHandler ===")
        # Convert chat history to object format
        chat_history_obj = DictToObj(self.chat_history_dict)
        
        conversation_handler = ConversationHandler(
            student_name=user_name, 
            student_id=f"user_{self.user_id}", 
            courses=courses,
            domain=self.domain,
            chat_history=chat_history_obj,  # Pass object here
            canvas_api_token=user_token
        )
        
        print("=== STAGE 3: Transforming user message ===")
        transformed_history = conversation_handler.transform_user_message(chat_history_obj)
        
        print("=== STAGE 4: Processing chat history ===")
        response = await conversation_handler.process_user_message(transformed_history)
        
        # Make sure the response is converted back to a dictionary
        if isinstance(response, DictToObj):
            self.chat_history_dict = response.to_dict()
        else:
            self.chat_history_dict = response
        
        # --- BEGIN ADDED DEBUGGING ---
        print("\n--- Debugging Response Extraction ---")
        print("Type of chat_history_dict:", type(self.chat_history_dict))
        try:
            print("Full chat_history_dict received from process_user_message:")
            # Use json.dumps for clean printing, handle potential errors
            try:
                print(json.dumps(self.chat_history_dict, indent=2))
            except TypeError as e:
                print(f"Could not serialize chat_history_dict to JSON: {e}")
                print("Raw structure:", self.chat_history_dict)

            if isinstance(self.chat_history_dict, dict) and "context" in self.chat_history_dict and isinstance(self.chat_history_dict["context"], list) and len(self.chat_history_dict["context"]) > 0:
                assistant_context = self.chat_history_dict["context"][0]
                print("\nAssistant context entry (context[0]):")
                print("Type:", type(assistant_context))
                print("Value:", assistant_context)

                if isinstance(assistant_context, dict) and "content" in assistant_context:
                    content = assistant_context["content"]
                    print("\nAssistant content (context[0]['content']):")
                    print("Type:", type(content))
                    print("Value:", content)
                else:
                    print("\n'content' key missing or assistant_context is not a dict.")
            else:
                print("\n'context' key missing, not a list, or empty in chat_history_dict.")

        except Exception as e:
            print(f"\nError during preliminary debugging: {e}")
        # --- END ADDED DEBUGGING ---

        # Extract the assistant's response
        assistant_response = ""
        try:
            # Existing extraction logic (slightly modified with prints)
            content = self.chat_history_dict["context"][0]["content"]
            print("\nAttempting extraction from content:", content) # Added print
            if isinstance(content, list):
                for i, content_item in enumerate(content):
                    print(f"  Checking item {i}: {content_item}") # Added print
                    if isinstance(content_item, dict) and "message" in content_item:
                        print(f"  Found message: {content_item['message']}") # Added print
                        assistant_response += content_item["message"] + " "
            elif isinstance(content, dict) and "message" in content:
                 print(f"  Content is dict, found message: {content['message']}") # Added print
                 assistant_response = content["message"]
            else:
                print(f"  Unknown content format or message key missing.") # Added print

        except KeyError as e:
             print(f"KeyError during extraction: 'context', 0, or 'content' likely missing. Error: {e}")
             assistant_response = "Error extracting response (KeyError)."
        except Exception as e:
            print(f"Error extracting assistant response: {e}")
            assistant_response = "An error occurred while processing your message."

        print("Final assistant_response before strip:", repr(assistant_response)) # Use repr
        print("--- Extraction Attempt Complete ---")
        # --- END MODIFIED EXTRACTION BLOCK ---

        print("=== STAGE 5: Response generated ===")
        return assistant_response.strip()
    
    async def load_vector_db(self, force_reload: bool = False):
        """
        Load the vector database.
        
        Args:
            force_reload: Whether to force reload data
        """
        print("Loading vector database...")
        try:
            # Get HF API token from environment variables
            hf_api_token = os.getenv("HUGGINGFACE_API_KEY")
            if not hf_api_token:
                print("Error: HUGGINGFACE_API_KEY not found in environment variables")
                return
            
            # Get the path to user data
            user_data_path = self.data_handler._get_user_data_path()
            
            # Initialize vector database
            db = VectorDatabase(
                json_file_path=user_data_path, 
                hf_api_token=hf_api_token, 
                cache_dir="chroma_data/"
            )
            
            # Process data - IMPORTANT: await the async function
            if force_reload:
                await db.clear_collection()
                await db.process_data()
            else:
                await db.process_data()
            print("Vector database loaded successfully!")
            
        except Exception as e:
            print(f"Error loading vector database: {e}")
    
    async def get_available_courses(self):
        """
        Get all available courses for the user.
        """
        try:
            # Get current selected courses
            current_selected = self._get_selected_courses()
            
            # Print current selected courses
            print("Currently selected courses:")
            for course_id, course_name in current_selected.items():
                print(f"  - {course_name} (ID: {course_id})")
            
        except Exception as e:
            print(f"Error getting available courses: {e}")

async def main():
    """Run an interactive test session."""
    # Replace with your Canvas user ID
    USER_ID = "7214035"
    
    # Initialize test chatbot
    chatbot = TestChatbot(USER_ID)
    
    # Print selected courses
    await chatbot.get_available_courses()
    
    # Ask if the user wants to load the vector database
    load_db = "y"
    if load_db == "y":
        force_reload = input("Force reload data? (y/n): ").lower() == "y"
        await chatbot.load_vector_db(force_reload=force_reload)
    
    print("\n=== Chat session started ===")
    print("Type 'exit', 'quit', or 'q' to end the session")
    print("Type 'refresh data' to update your Canvas data")
    print("-----------------------------")
    
    # Start chat loop
    while True:
        # Get user input
        user_input = input("\nYou: ")
        
        # Check for exit commands
        if user_input.lower() in ["exit", "quit", "q"]:
            print("Ending chat session.")
            break
        
        # Process the message
        print("\nProcessing your message...")
        response = await chatbot.process_message(user_input)
        
        # Display the response
        print(f"\nAssistant: {response}")

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())