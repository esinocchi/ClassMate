# CanvasClassmate: AI-Powered Canvas Assistant

CanvasClassmate is an AI-powered assistant designed to enhance the learning experience for students using the Canvas Learning Management System (LMS). It leverages advanced natural language processing techniques, including large language models (LLMs) and vector databases, to provide intelligent search, question answering, and content summarization capabilities.

## Project Overview

The system processes Canvas course data (assignments, announcements, files, quizzes, syllabus, etc.) and makes it searchable using semantic similarity.  This allows students to ask natural language questions about their course materials and receive relevant, concise answers.  The core technology involves creating vector embeddings of course content and using a vector database (ChromaDB) for efficient retrieval.

## Data Flow

1.  **Data Retrieval (backend/data_retrieval):**
    *   The `data_retrieval` module fetches data from the Canvas API using a user-provided API token.  It retrieves information about courses, assignments, announcements, files, quizzes, and the syllabus.
    *   This data is structured into a JSON format and stored locally.
    *   The `get_all_user_data.py` script orchestrates this data retrieval process.
    *   The `data_handler.py` script manages the user data and initiates background updates.

2.  **Content Extraction (vectordb/content_extraction.py):**
    *   The `content_extraction` module handles the extraction of text and images from various file types (PDF, DOCX, PPTX, HTML).
    *   It includes functions to download files from URLs, parse HTML content (including resolving links to actual filenames), and extract text from different document formats.
    *   The `extract_file_content_from_url` function is a key component, handling both Canvas and non-Canvas URLs, and dealing with potential errors like missing files or incorrect URL formats.

3.  **Vector Database and Embedding (vectordb/db.py and vectordb/embedding_model.py):**
    *   The `vectordb/db.py` module is the heart of the semantic search functionality.  It takes the structured JSON data and creates vector embeddings using the Hugging Face Inference API.
    *   It uses ChromaDB, a vector database, to store these embeddings for efficient similarity searches.
    *   The `VectorDatabase` class manages the entire process: loading data, preprocessing text, creating embeddings, storing them in ChromaDB, and performing searches.
    *   The `search` method allows for complex queries with filtering by course ID (single or multiple), time range, item type, specific dates, and keywords. It combines semantic search with keyword matching for comprehensive results.
    *   The `_handle_keywords` method implements keyword-based filtering, supplementing the semantic search.
    *   The `embedding_model.py` file provides the `HFEmbeddingFunction` class, which interfaces with the Hugging Face API to generate embeddings.

4.  **Chatbot Interface (chat_bot/conversation_handler.py):**
    *   The `conversation_handler.py` module provides a conversational interface for interacting with the system.
    *   The `ConversationHandler` class manages the conversation flow, user information, and calls to the vector database.
    *   It includes methods like `find_course_information`, `find_file`, and `create_notes`, which utilize the vector database's search capabilities to answer user queries.
    *   It validates and sanitizes search parameters.

5. **Task Specific Agents (backend/task_specific_agents):**
    * The `task_specific_agents` directory contains modules for specific tasks, such as:
        *   `calendar_agent.py`: Retrieves calendar events from the Canvas API.
        *   `grade_calculator_agent.py`: Calculates grades and provides insights based on assignment data.
        *   `lecture_to_notes_agent.py`: Converts lecture files into notes in PDF format.

6.  **Front-End (Front_End folder):**
    *   The front-end is implemented as a Chrome extension, providing a user interface directly within the Canvas website.
    *   `Front_End_Script.js`: Contains the JavaScript code that handles user interaction, communication with the backend, and dynamic updates to the UI.  It manages the chat interface, settings, and data storage using `chrome.storage.local`.
    *   `Front_End_Style.css`:  Provides the styling for the chat interface and settings panel.
    *   `manifest.json`:  The manifest file for the Chrome extension, defining permissions, resources, and entry points.
    *   `images/`: Contains images used in the extension's UI.
    *   The front-end communicates with the backend via HTTP requests (using `fetch`) to the API endpoints defined in `endpoints.py`.

7.  **Backend and API (endpoints.py):**
    *   The backend is built using the FastAPI framework, providing a RESTful API for the front-end to interact with.
    *   `endpoints.py`: Defines the API endpoints, handling requests for data retrieval, processing, and chatbot interactions.  It uses Pydantic models for request and response validation.
    *   The backend is hosted on an AWS EC2 instance, making it accessible to the Chrome extension.  FastAPI serves the API, handling requests and coordinating the other backend components.
    *   CORS (Cross-Origin Resource Sharing) is configured to allow requests from the Canvas domain (`https://psu.instructure.com`) and the custom domain (`https://canvasclassmate.me`).

## Key Features

*   **Semantic Search:** Find relevant course materials using natural language queries.
*   **Keyword Search:** Refine search results with specific keywords.
*   **Filtering:** Narrow down results by course ID, document type, time range, and specific dates.
*   **Content Extraction:** Extract text and images from various file types (PDF, DOCX, PPTX, HTML).
*   **ChromaDB Integration:** Efficiently store and retrieve vector embeddings.
*   **Hugging Face API:** Utilize a powerful language model for embedding generation.
*   **Data Handling:** Manage user data and background updates.
*   **Task-Specific Agents:** Perform specialized tasks like calendar event retrieval and grade calculation.
*   **Chrome Extension Interface:**  Provides a user-friendly chat interface directly within Canvas.
*   **AWS EC2 Hosting:** The backend is hosted on an AWS EC2 instance for reliable and scalable access.

## Modules and Their Functions

### `vectordb/db.py`

*   **`VectorDatabase`:** The main class for managing the vector database.
    *   `__init__`: Initializes the database, loads data, and sets up the ChromaDB client and embedding function.
    *   `process_data`: Loads data from the JSON file, preprocesses it, creates embeddings, and stores them in ChromaDB.
    *   `search`: Performs semantic and keyword searches based on provided parameters.
    *   `_build_chromadb_query`: Constructs the `where` clause for ChromaDB queries based on search parameters.
    *   `_execute_chromadb_query`: Executes a query against the ChromaDB collection.
    *   `_handle_keywords`: Filters results based on keyword matches.
    *   `_augment_results`: Adds additional information to search results (e.g., local timestamps).
    *   `_post_process_results`: (Placeholder - intended for prioritizing exact/partial matches).
    *   `_include_related_documents`: (Placeholder - intended for adding related documents).

### `vectordb/content_extraction.py`

*   `extract_file_content_from_url`: Downloads and extracts content from a file at a given URL. Handles Canvas and non-Canvas URLs.
*   `parse_file_content`: Parses content from PDF, DOCX, or PPTX files.
*   `get_file_type`: Determines the file type based on the filename extension.
*   `extract_text_and_images`: Extracts text and images from file bytes.

### `chat_bot/conversation_handler.py`

*   **`ConversationHandler`:** Manages the conversation with the user.
    *   `__init__`: Initializes the handler with user information, courses, and API token.
    *   `find_course_information`: Retrieves course information (syllabus, description, materials) using the vector database.
    *   `find_file`: Locates a specific file using the vector database.
    *   `create_notes`: Generates notes from a lecture file.
    *   `validate_search_parameters`: Ensures search parameters are valid.

### `backend/data_retrieval/get_all_user_data.py`

*   `get_all_user_data`: Fetches all relevant user data from the Canvas API and saves it to a JSON file.
*   `get_text_from_links`: Extracts text from links found within Canvas content.

### `backend/data_retrieval/data_handler.py`
*   **`DataHandler`:** Manages user data and background updates.
    *   `__init__`: Initializes the data handler with user ID, domain, and other information.
    *   `update_user_data`: Updates the user's data by fetching from Canvas and updating the vector database.

### `backend/task_specific_agents/*.py`

*   `calendar_agent.py`:
    *   `find_events`: Retrieves calendar events from Canvas.
*   `grade_calculator_agent.py`:
    *   `calculate_grade`: Calculates grades and provides insights.
*   `lecture_to_notes_agent.py`:
    *   `lecture_file_to_notes_pdf`: Converts lecture files to notes.

### `vectordb/embedding_model.py`

*   **`HFEmbeddingFunction`:** Provides an interface to the Hugging Face API for generating embeddings.
    *   `__init__`: Initializes the embedding function with the API URL and token.
    *   `__call__`: Generates embeddings for a batch of text inputs.

### `Front_End/Front_End_Script.js`
*   Handles user interactions within the Chrome extension.
*   Manages the chat interface and settings panel.
*   Sends requests to the backend API (defined in `endpoints.py`).
*   Stores and retrieves user data and conversation history using `chrome.storage.local`.
*   Dynamically updates the UI based on user input and API responses.

### `endpoints.py`
*   Defines the RESTful API endpoints using the FastAPI framework.
*   Handles requests from the front-end (Chrome extension).
*   Coordinates the backend components (data retrieval, vector database, chatbot logic).
*   Uses Pydantic models for request and response validation.
*   Implements CORS (Cross-Origin Resource Sharing) to allow requests from the Canvas domain and the custom domain.

This README provides a comprehensive overview of the CanvasClassmate project, its functionality, data flow, key modules, front-end implementation, and backend hosting. It avoids code snippets and focuses on explaining *what* each part does, making it easy for users and developers to understand the system. The interaction between the front-end and backend is clearly described, along with the relevant files and technologies used.
