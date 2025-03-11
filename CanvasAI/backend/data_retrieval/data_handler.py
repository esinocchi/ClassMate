import io
from docx import Document 
import requests
import os
import time
import json
import fitz  # PyMuPDF
import pytesseract
from dotenv import load_dotenv 
from get_all_user_data import get_all_user_data
from bs4 import BeautifulSoup
from PIL import Image
from urllib.parse import urlparse


load_dotenv()

API_URL = "https://psu.instructure.com/api/v1"
API_TOKEN = os.getenv("CANVAS_API_TOKEN")


class DataHandler:
    def __init__(self, id, domain, token, short_name="", courses_selected=[], base_dir=""):
        """
        Initialize DataHandler with user credentials and settings

        ================================================

        The minimum required parameters are id, domain, token, and base_dir.
        
        ================================================

        Examples of parameters:
        id = 1234567890
        domain = "psu.instructure.com"
        token = "1234567890"
        short_name = "John Doe"
        courses_selected = [1234567890, 1234567891, 1234567892]
        base_dir = "/path/to/base/directory"
        
        ================================================

        if this is the first time a user is added, * initialize with courses_selected: list *

        if this isn't the first time, * grab the courses_selected from the user_data file *
        
        domain example: psu.instructure.com

        ================================================

        get_user_data_path() description:
        - get the path to the user's data file
        - if the user's data file doesn't exist, create it
        - if the user's data file does exist, load it

        upload_data() description:
        - converts user_data into json and uploads it into the individual user's data file

        initiate_user_data() description:
        - grabs user info from canvas api
        - creates user_data dictionary
        - uploads user_data to the user's data file

        grab_user_data() description:   
        - grabs the user_data from the user's data file
        - updates the instance variables with the user_data

        update_user_data() description:
        - grabs the user_data from the user's data file
        - updates the user_data with fresh data from canvas api

        update_chat_context() description:
        - updates the chat_context in the user_data dictionary

        delete_chat_context() description:
        - deletes the chat_context in the user_data dictionary
        
        ================================================

        """
        self.id = id
        self.name = short_name
        self.API_TOKEN = token
        self.domain = domain.split('.')[0]  # Just get 'psu' from 'psu.instructure.com'
        self.base_dir = base_dir
        self.API_URL = f"https://{domain}/api/v1"
        self.courses_selected = courses_selected
        self.time_token_updated = time.time()
        
        # Get the path to the main CanvasAI directory (2 levels up from this file)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        canvasai_dir = os.path.dirname(os.path.dirname(current_dir))
        
        # Use the existing user_data directory
        self.data_dir = os.path.join(canvasai_dir, "user_data")
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_user_data_path(self):
        """
        Get the full path to the user's data file
        """
        return os.path.join(self.data_dir, self.domain, str(self.id), "user_data.json")

    def upload_data(self, user_data: dict):
        """
        Converts user_data into json and uploads it into the individual user's data file
        """
        file_path = self._get_user_data_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with open(file_path, "w") as f:
                json.dump(user_data, f, indent=4)
            return "User data uploaded successfully"
        except:
            return "Error uploading user data"
    
    def initiate_user_data(self):
        """
        Initiates the user_data dictionary with basic structure
        """
        try:
            user_info = requests.get(
                f"{self.API_URL}/users/self",
                headers={"Authorization": f"Bearer {self.API_TOKEN}"}
            )
            user_info.raise_for_status()
            user_info = user_info.json()
            
            self.name = user_info["short_name"]
            user_data = {
                "user_metadata": {
                    "id": self.id,
                    "name": self.name,
                    "token": self.API_TOKEN,
                    "domain": self.domain,
                    "updated_at": time.time(),
                    "courses_selected": self.courses_selected
                },
                "courses": [],
                "files": [],
                "announcements": [],
                "assignments": [],
                "quizzes": [],
                "calendar_events": [],
                "current_chat_context": ""
            }
            
            self.upload_data(user_data)
            return "User data initiated successfully"
        except:
            return "Error initiating user data"

    def grab_user_data(self):
        """
        Grabs the user_data from the user's data file
        """
        file_path = self._get_user_data_path()
        if not os.path.exists(file_path):
            return "User data file not found"
            
        try:
            with open(file_path, "r") as f:
                user_data = json.load(f)
            
            # Update instance variables from loaded data
            metadata = user_data["user_metadata"]
            self.name = metadata["name"]
            self.courses_selected = metadata["courses_selected"]
            
            return user_data
        except:
            return "Error grabbing user data"

    def update_user_data(self):
        """
        Updates the user_data dictionary with fresh data from Canvas
        """
        user_data = self.grab_user_data()
        user_data = get_all_user_data(self.base_dir, self.API_URL, self.API_TOKEN, user_data, self.courses_selected)
        self.upload_data(user_data)
        return "User data updated successfully"
    
    def update_chat_context(self, chat_context: str):
        """
        Updates the chat_context in the user_data dictionary
        """
        user_data = self.grab_user_data()
        user_data["current_chat_context"] = chat_context
        self.upload_data(user_data)
        return "Chat context updated successfully"

    def delete_chat_context(self):
        """
        Deletes the chat_context in the user_data dictionary
        """
        user_data = self.grab_user_data()
        user_data["current_chat_context"] = ""
        self.upload_data(user_data)
        return "Chat context deleted successfully"

def run_tests():
    """
    Test suite simulating real user flow:
    1. First time user setup (new DataHandler with course selection)
    2. Later session (loading existing user data into new DataHandler)
    3. Updating data and testing other functions
    """
    try:
        # Test Setup
        user = requests.get(f"{API_URL}/users/self", headers={"Authorization": f"Bearer {API_TOKEN}"}).json()
        user_id = user.get("id")
        domain = "psu.instructure.com"
        
        # Using actual course IDs from your Canvas courses
        courses_selected = [            
            2372294,
            2381676,
            2361510,
            2361723]
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Set base_dir to CanvasAI root
        
        print("\n=== DataHandler Test Suite ===\n")

        print("=== Scenario 1: First Time User Setup ===")
        
        # Test 1: First Time User Creation
        print("\nTest 1: Creating new DataHandler for first time user...")
        first_handler = DataHandler(
            id=user_id,
            domain=domain,
            token=API_TOKEN,
            short_name="Test User",
            courses_selected=courses_selected,
            base_dir=base_dir  # Using actual base directory
        )
        print("✓ First time DataHandler created")

        # Test 2: Initialize New User Data
        print("\nTest 2: Initializing first time user data...")
        init_result = first_handler.initiate_user_data()
        print(f"Result: {init_result}")
        if "successfully" in init_result:
            print("✓ First time user data initialized")
            print(f"Initialized with {len(courses_selected)} courses: {courses_selected}")
        else:
            print("✗ First time user data initialization failed")
            return

        print("\n=== Scenario 2: Returning User Session ===")

        # Test 3: Create New Handler Instance (simulating new session)
        print("\nTest 3: Creating new DataHandler for existing user...")
        returning_handler = DataHandler(
            id=user_id,
            domain=domain,
            token=API_TOKEN,
            base_dir=base_dir  # Using actual base directory
        )
        print("✓ New session DataHandler created")

        # Test 4: Load Existing User Data
        print("\nTest 4: Loading existing user data...")
        existing_data = returning_handler.grab_user_data()
        if isinstance(existing_data, dict):
            print("✓ Existing user data loaded successfully")
            loaded_courses = existing_data["user_metadata"]["courses_selected"]
            print(f"Found {len(loaded_courses)} selected courses: {loaded_courses}")
            print(f"Last updated: {time.ctime(existing_data['user_metadata']['updated_at'])}")
        else:
            print("✗ Failed to load existing user data")
            return

        print("\n=== Scenario 3: Testing Data Operations ===")

        # Test 5: Update User Data
        print("\nTest 5: Updating user data from Canvas...")
        update_result = returning_handler.update_user_data()
        print(f"Update result: {update_result}")
        if "successfully" in update_result:
            print("✓ User data updated from Canvas")
        else:
            print("✗ User data update failed")

        # Test 6: Chat Context Operations
        print("\nTest 6: Testing chat context operations...")
        
        # 6.1: Set chat context
        test_context = "Test chat context for returning user"
        context_update = returning_handler.update_chat_context(test_context)
        if "successfully" in context_update:
            print("✓ Chat context set successfully")
        else:
            print("✗ Failed to set chat context")

        # 6.2: Verify chat context
        verify_data = returning_handler.grab_user_data()
        if verify_data["current_chat_context"] == test_context:
            print("✓ Chat context verified")
        else:
            print("✗ Chat context verification failed")

        # 6.3: Delete chat context
        delete_result = returning_handler.delete_chat_context()
        if "successfully" in delete_result:
            print("✓ Chat context deleted")
        else:
            print("✗ Failed to delete chat context")

        # Test 7: Verify Final Data Structure
        print("\nTest 7: Verifying data structure integrity...")
        final_data = returning_handler.grab_user_data()
        required_keys = [
            "user_metadata", "courses", "files", "announcements",
            "assignments", "quizzes", "calendar_events", "current_chat_context"
        ]
        missing_keys = [key for key in required_keys if key not in final_data]
        if not missing_keys:
            print("✓ Data structure integrity maintained")
            print("Final courses selected:", final_data["user_metadata"]["courses_selected"])
        else:
            print(f"✗ Missing keys in data structure: {missing_keys}")

        print("\n=== Test Suite Complete ===")
        print("All scenarios tested successfully!")

    except Exception as e:
        print(f"\n❌ Test suite failed with error: {str(e)}")
        raise

if __name__ == "__main__":
    run_tests()








