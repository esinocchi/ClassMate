from docx import Document 
import aiohttp
import os
import time
import json
from .get_all_user_data import get_all_user_data
from urllib.parse import urlparse
import asyncio
import threading
from dotenv import load_dotenv

load_dotenv()


class DataHandler:
    def __init__(self, id, domain, token = "", short_name="", courses_selected={}):
        """
        Initialize DataHandler with user credentials and settings.

        ================================================

        The minimum required parameters are `id`, `domain`, and `token`. 
        The `short_name` and `courses_selected` parameters are optional.

        ================================================

        Parameters:
        -----------
        id : int
            The unique identifier for the user (Canvas user ID).
        domain : str
            The domain of the Canvas instance (e.g., "psu.instructure.com").
        token : str, optional
            The API token for authenticating with the Canvas API. If not provided, 
            it will be retrieved from the environment variables.
        short_name : str, optional
            A short name or display name for the user (e.g., "John Doe").
        courses_selected : dictionary, optional
            A list of course IDs that the user has selected for data retrieval.

        ================================================

        Examples of parameters:
        -----------------------
        id = 1234567890
        domain = "psu.instructure.com"
        token = "1234567890"
        short_name = "John Doe"
        courses_selected = {1234567890: "Course 1", 1234567891: "Course 2", 1234567892: "Course 3"}

        ================================================

        Notes:
        ------
        - If this is the first time a user is added, initialize with `courses_selected` as a dictionary of course IDs paired with course names.
        - If this isn't the first time, the `courses_selected` will be loaded from the user's data file.
        - The `domain` should be the full domain (e.g., "psu.instructure.com"), but only the subdomain (e.g., "psu") will be used internally.

        ================================================

        Methods:
        --------
        _get_user_data_path():
            - Returns the full path to the user's data file.
            - If the user's data file doesn't exist, it will be created.

        save_user_data():
            - Saves the current user data to the user's data file synchronously.
            - Returns a success message or an error message if the save fails.

        initiate_user_data():
            - Initializes the user_data dictionary with basic structure.
            - Retrieves user info from the Canvas API and populates the user_data dictionary.
            - Saves the initialized user data to the user's data file.

        grab_user_data():
            - Loads the user_data from the user's data file.
            - Updates the instance variables with the loaded user_data.
            - Returns the loaded user_data or an error message if the file is not found.

        update_user_data():
            - Updates the user data from the Canvas API asynchronously in the background.
            - Starts the update process and returns immediately, allowing the update to run in the background.
            - Updates the user_data dictionary with fresh data from the Canvas API and saves it to the user's data file.

        update_chat_context(chat_context: str):
            - Updates the `current_chat_context` field in the user_data dictionary with the provided chat context.
            - Saves the updated user data to the user's data file.

        delete_chat_context():
            - Clears the `current_chat_context` field in the user_data dictionary.
            - Saves the updated user data to the user's data file.

        ================================================

        Example Usage:
        --------------
        # Initialize the DataHandler with user credentials
        handler = DataHandler(user_id, domain, API_TOKEN, courses_selected=courses_selected)

        # Initiate user data (first-time setup)
        handler.initiate_user_data()

        # Grab user data from the file
        user_data = handler.grab_user_data()

        # Update user data in the background
        handler.update_user_data()

        # Update chat context
        handler.update_chat_context("Current chat context")

        # Delete chat context 
        handler.delete_chat_context()

        ================================================
        """
        self.id = id
        self.name = short_name
        self.API_TOKEN = token
        self.domain = domain.split('.')[0]  # Just get 'psu' from 'psu.instructure.com'
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.API_URL = f"https://{domain}/api/v1"
        self.courses_selected = courses_selected
        self.time_token_updated = time.time()
        self.is_updating = False
        self.update_lock = threading.Lock() 
        
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

    def save_user_data(self, user_data):
        """
        Save user data to file synchronously
        """
        file_path = self._get_user_data_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with open(file_path, "w") as f:
                json.dump(user_data, f, indent=4)
            return "User data saved successfully"
        except Exception as e:
            return f"Error saving user data: {str(e)}"
    
    def initiate_user_data(self):
        """
        Initiates the user_data dictionary with basic structure
        """

        try:
            # Define the async function for the API call
            async def get_user_info():
                async with aiohttp.ClientSession() as session:
                    headers = {"Authorization": f"Bearer {self.API_TOKEN}"}
                    async with session.get(f"{self.API_URL}/users/self", headers=headers) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            raise ValueError(f"Failed to get user info: {error_text}")
                        
                        return await response.json()
            
            # Run the async function in a new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                user_info = loop.run_until_complete(get_user_info())
            finally:
                loop.close()
            
            # Process the results synchronously
            self.name = user_info["short_name"]
            user_data = {
                "user_metadata": {
                    "id": self.id,
                    "name": self.name,
                    "token": self.API_TOKEN,
                    "domain": self.domain,
                    "updated_at": time.time(),
                    "token_updated_at": time.time(),
                    "courses_selected": self.courses_selected,
                    "is_updating": self.is_updating
                },
                "courses": [],
                "files": [],
                "announcements": [],
                "assignments": [],
                "quizzes": [],
                "calendar_events": [],
                "current_chat_context": ""
            }
            
            return self.save_user_data(user_data)
        except Exception as e:
            print(f"Error details: {str(e)}")
            return f"Error initiating user data: {str(e)}"

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
            self.API_TOKEN = metadata["token"]
            self.is_updating = metadata["is_updating"]
            return user_data
        except Exception as e:
            return f"Error grabbing user data: {str(e)}"

    def update_user_data(self):
        """
        Updates the user data from Canvas by running get_all_user_data asynchronously in the background.
        This function starts the update process and returns immediately, allowing the update to run in the background.
        """
        print(f"courses_selected: {self.courses_selected}")
        print("not updating yet cuh")
        if self.is_updating:
            print("Update already in progress")
            return "Update already in progress"
        self.set_is_updating(True)

        print("updating now")
        try:
            # Define the background update coroutine
            
            
            async def background_update():
                try:
                    print("\n=== Starting Background Update ===")
                    start_time = time.time()

                    user_data = self.grab_user_data()
                    
                    # Verify we have valid courses selected
                    if not self.courses_selected:
                        print("⚠️ No courses are selected for update")
                        return
                        
                    print(f"Updating data for {len(self.courses_selected)} courses: {self.courses_selected}")
                    
                    # Get fresh data from Canvas
                    updated_user_data = await get_all_user_data(
                        self.base_dir,
                        self.API_URL,
                        self.API_TOKEN,
                        user_data,
                        courses_selected=self.courses_selected
                    )
                    
                    # Update the user data and timestamp
                    updated_user_data["user_metadata"]["updated_at"] = time.time()
                    
                    # Save the updated data
                    self.save_user_data(updated_user_data)
                    self.set_is_updating(False)
                    
                    end_time = time.time()
                    duration = end_time - start_time
                    print(f"\n=== Background Update Complete ===")
                    print(f"Duration: {duration:.2f} seconds")
                    print(f"Successfully updated data for {len(self.courses_selected)} courses")
                    
                except ValueError as ve:
                    self.set_is_updating(False)
                    print(f"\n⚠️ Update failed: {str(ve)}")
                    print("Your courses_selected list may need to be updated with current course IDs.")
                    
                except Exception as e:
                    self.set_is_updating(False)
                    print(f"\n❌ Error in background update: {str(e)}")
                    raise

            def run_async_update():
                """Run the async update in a new event loop in a separate thread"""
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(background_update())
                finally:
                    loop.close()

            # Start the background update in a separate thread
            update_thread = threading.Thread(target=run_async_update)
            update_thread.daemon = True  # Allow the program to exit even if thread is running
            update_thread.start()
            
        except Exception as e:
            self.set_is_updating(False)
            
            print(f"Error starting background update: {str(e)}")

    def update_chat_context(self, chat_context: str):
        """
        Updates the chat_context in the user_data dictionary
        """
        user_data = self.grab_user_data()
        
        user_data["current_chat_context"] = chat_context
        return self.save_user_data(user_data)

    def delete_chat_context(self):
        """
        Deletes the chat_context in the user_data dictionary
        """
        user_data = self.grab_user_data()
            
        user_data["current_chat_context"] = ""
        return self.save_user_data(user_data)
    
    def update_courses_selected(self, courses_selected: dict):
        """
        Updates the courses_selected in the user_data dictionary
        """
        user_data = self.grab_user_data()
        user_data["user_metadata"]["courses_selected"] = courses_selected

        return self.save_user_data(user_data)
    
    def update_token(self, token: str):
        """
        Updates the token in the user_data dictionary
        """
        user_data = self.grab_user_data()
        user_data["user_metadata"]["token"] = token
        user_data["user_metadata"]["token_updated_at"] = time.time()
        
        return self.save_user_data(user_data)

    def has_saved_data(self):
        """
        Checks if the user has saved data
        """
        file_path = self._get_user_data_path()
        
        return os.path.exists(file_path)

    def set_is_updating(self, is_updating: bool):
        """
        Returns the is_updating value
        """
        with self.update_lock:
            user_data = self.grab_user_data()
            user_data["user_metadata"]["is_updating"] = is_updating
            self.is_updating = is_updating
            
        return self.save_user_data(user_data)





