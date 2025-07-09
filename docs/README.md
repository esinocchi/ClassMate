# ClassMate: AI-Powered Canvas Assistant

ClassMate is an AI-powered assistant designed to enhance the learning experience for students using the Canvas Learning Management System (LMS). It leverages advanced natural language processing techniques, including large language models (LLMs) and vector databases, to provide intelligent search, question answering, content summarization, and personalized study planning capabilities.

## Project Overview

The system processes Canvas course data (assignments, announcements, files, quizzes, syllabus, etc.) and makes it searchable using semantic similarity. This allows students to ask natural language questions about their course materials and receive relevant, concise answers. The core technology involves creating vector embeddings of course content using local Sentence Transformer models and storing them in a Qdrant vector database for efficient retrieval.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Chrome         │    │  FastAPI         │    │  Qdrant Vector  │
│  Extension      │◄──►│  Backend         │◄──►│  Database       │
│  (Frontend)     │    │  (API Layer)     │    │  (Storage)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
        │                        │                        │
        │                        ▼                        │
        │              ┌──────────────────┐               │
        │              │  Task-Specific   │               │
        │              │  Agents          │               │
        │              └──────────────────┘               │
        │                        │                        │
        ▼                        ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Canvas LMS     │    │  OpenAI API      │    │  Sentence       │
│  (Data Source)  │    │  (LLM Services)  │    │  Transformers   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Data Flow

1. **Data Retrieval (`src/backend/data_retrieval/`):**
   - The `data_retrieval` module fetches data from the Canvas API using user-provided API tokens
   - Retrieves courses, assignments, announcements, files, quizzes, and syllabus content
   - Data is structured into JSON format and stored locally for processing
   - `get_all_user_data.py` orchestrates the data collection process
   - `data_handler.py` manages user data lifecycle and background updates

2. **Content Extraction (`src/database/vectordb/content_extraction.py`):**
   - Handles extraction of text and images from various file types (PDF, DOCX, PPTX, HTML)
   - Downloads files from Canvas URLs and parses content
   - Resolves HTML links to actual filenames and extracts structured text
   - Handles both Canvas and external URLs with error recovery

3. **Vector Database and Embedding (`src/database/vectordb/`):**
   - **Core Database (`db.py`)**: Manages Qdrant vector database connections and operations
   - **Embedding Model (`embedding_model.py`)**: Uses local Sentence Transformer model (`intfloat/e5-small-v2`) for generating embeddings
   - **BM25 Scoring (`bm25_scorer.py`)**: Implements BM25 algorithm for keyword-based search, fused with semantic search
   - **Text Processing (`text_processing.py`)**: Handles text normalization and preprocessing for embeddings
   - **Filtering (`filters.py`)**: Builds complex query filters for time ranges, courses, and content types
   - **Post-processing (`post_process.py`)**: Augments results with metadata and relevance scoring

4. **Conversational Interface (`src/backend/chat_bot/conversation_handler.py`):**
   - `ConversationHandler` manages multi-turn conversations and context
   - Integrates with OpenAI API for natural language understanding
   - Validates and sanitizes search parameters
   - Coordinates between vector database and task-specific agents

5. **Task-Specific Agents (`src/backend/task_specific_agents/`):**
   - **Calendar Agent (`calendar_agent.py`)**: Retrieves and manages calendar events
   - **Grade Calculator (`grade_calculator_agent.py`)**: Calculates required grades and provides academic insights
   - **Lecture-to-Notes (`lecture_to_notes_agent.py`)**: Converts lecture files to structured PDF notes using fine-tuned GPT models

6. **Dashboard System (`src/backend/dashboard/`):**
   - **Data Provider (`data/canvas_data_provider.py`)**: Abstracts vector database operations for dashboard use
   - **Core Service (`core/dashboard_service.py`)**: Orchestrates dashboard data aggregation
   - **Analysis Components (`analysis/`)**: Provides time estimation, difficulty assessment, and priority ranking
   - **Generators (`generators/`)**: Creates personalized study plans and todo lists

7. **Chrome Extension (`src/extension/`):**
   - **Frontend Script (`Front_End_Script.js`)**: Handles user interactions and API communication
   - **Styling (`Front_End_Style.css`)**: Provides responsive UI styling
   - **Manifest (`manifest.json`)**: Defines extension permissions and resources
   - **Images (`images/`)**: Contains UI icons and graphics
   - Communicates with backend via HTTPS requests to `canvasclassmate.me`

8. **Backend API (`src/backend/endpoints.py`):**
   - Built with FastAPI framework for high-performance async operations
   - Handles authentication and request validation using Pydantic models
   - Implements CORS for cross-origin requests from Canvas domains
   - Coordinates all backend components and provides RESTful endpoints

## Key Features

### Core Functionality
- **Semantic Search**: Find relevant course materials using natural language queries
- **Hybrid Search**: Combines semantic similarity with BM25 keyword matching for comprehensive results
- **Advanced Filtering**: Filter by course, document type, time range, and specific dates
- **Content Extraction**: Extract and process text from PDF, DOCX, PPTX, and HTML files
- **Multi-turn Conversations**: Maintain context across conversation sessions

### AI-Powered Features
- **Intelligent Study Planning**: Generate personalized study schedules based on upcoming deadlines
- **Grade Calculation**: Calculate required scores to achieve target grades
- **Lecture-to-Notes**: Convert lecture files into structured, academic-style PDF notes
- **Assignment Analysis**: Assess difficulty and time requirements for assignments

### Technical Features
- **Qdrant Vector Database**: High-performance vector storage and retrieval
- **Local Embeddings**: Uses Sentence Transformers for privacy-preserving embeddings
- **Async Processing**: Non-blocking operations for improved performance
- **Chrome Extension**: Seamless integration within Canvas interface
- **Cloud Hosting**: Reliable backend hosted on AWS EC2

## Technology Stack

### Backend
- **Framework**: FastAPI (Python)
- **Vector Database**: Qdrant Cloud
- **Embeddings**: Sentence Transformers (`intfloat/e5-small-v2`)
- **LLM Integration**: OpenAI API (GPT-4), Groq, Ollama
- **Search**: BM25 + Semantic Search Fusion
- **File Processing**: PyMuPDF, python-docx, python-pptx
- **Async Operations**: aiohttp, asyncio

### Frontend
- **Platform**: Chrome Extension (Manifest V3)
- **Languages**: JavaScript, CSS, HTML
- **Storage**: Chrome Storage API
- **Communication**: Fetch API with CORS

### Infrastructure
- **Hosting**: AWS EC2
- **Domain**: `canvasclassmate.me`
- **Database**: Qdrant Cloud
- **Package Management**: uv (Python)

## Project Structure

```
ClassMate/
├── src/
│   ├── backend/
│   │   ├── chat_bot/
│   │   │   └── conversation_handler.py
│   │   ├── data_retrieval/
│   │   │   ├── data_handler.py
│   │   │   └── get_all_user_data.py
│   │   ├── dashboard/
│   │   │   ├── analysis/
│   │   │   ├── core/
│   │   │   ├── data/
│   │   │   └── generators/
│   │   ├── task_specific_agents/
│   │   │   ├── calendar_agent.py
│   │   │   ├── grade_calculator_agent.py
│   │   │   └── lecture_to_notes_agent.py
│   │   └── endpoints.py
│   ├── database/
│   │   └── vectordb/
│   │       ├── db.py
│   │       ├── embedding_model.py
│   │       ├── bm25_scorer.py
│   │       ├── content_extraction.py
│   │       ├── text_processing.py
│   │       ├── filters.py
│   │       ├── post_process.py
│   │       └── testing/
│   └── extension/
│       ├── Front_End_Script.js
│       ├── Front_End_Style.css
│       ├── manifest.json
│       └── images/
├── docs/
│   └── README.md
├── tests/
├── pyproject.toml
└── requirements.txt
```

## Module Reference

### Core Database (`src/database/vectordb/db.py`)
- **`VectorDatabase`**: Main class for Qdrant vector database management
  - `connect_to_qdrant()`: Establishes connection to Qdrant cloud instance
  - `process_data()`: Loads JSON data, creates embeddings, and stores in Qdrant
  - `search()`: Performs hybrid semantic and keyword search
  - `filter_search()`: Executes filter-only queries for dashboard components
  - `build_qdrant_query()`: Constructs Qdrant query filters
  - `_execute_qdrant_query()`: Executes queries against Qdrant collection

### Embedding Model (`src/database/vectordb/embedding_model.py`)
- **`SentenceTransformerEmbeddingFunction`**: Local embedding generation
  - Uses `intfloat/e5-small-v2` model for privacy-preserving embeddings
  - Supports batch processing for efficient embedding generation
  - Provides 384-dimensional embeddings optimized for educational content

### BM25 Scorer (`src/database/vectordb/bm25_scorer.py`)
- **`CanvasBM25`**: Keyword-based search implementation
  - Optimized for educational content and academic terminology
  - Supports result fusion with semantic search
  - Configurable parameters for different content types

### Conversation Handler (`src/backend/chat_bot/conversation_handler.py`)
- **`ConversationHandler`**: Manages conversational AI interactions
  - `process_user_message()`: Processes user queries and generates responses
  - `find_events_and_assignments()`: Searches for upcoming tasks and events
  - `find_course_information()`: Retrieves course materials and information
  - `create_notes()`: Generates structured notes from lecture content

### Task-Specific Agents
- **Calendar Agent**: Manages Canvas calendar integration and event retrieval
- **Grade Calculator**: Calculates required scores and provides academic insights
- **Lecture-to-Notes**: Converts lecture files to structured PDF notes using LaTeX

### Data Management (`src/backend/data_retrieval/`)
- **`DataHandler`**: Manages user data lifecycle and Canvas API integration
- **`get_all_user_data()`**: Orchestrates comprehensive data collection from Canvas

### Chrome Extension (`src/extension/`)
- **Frontend Script**: Handles UI interactions and backend communication
- **Styling**: Provides responsive design for Canvas integration
- **Manifest**: Defines extension permissions and resources

## API Endpoints

### Main Pipeline
- `POST /endpoints/mainPipelineEntry` - Main chatbot interaction endpoint
- `GET /endpoints/initiate_user` - Initialize user session
- `POST /endpoints/pushCourses` - Update user course selections
- `GET /endpoints/pullCourses` - Retrieve user courses
- `GET /endpoints/pullNotes` - Download generated PDF notes

### Dashboard (In Development)
- `GET /dashboard/today` - Get today's tasks and deadlines
- `GET /dashboard/study-plan` - Generate personalized study plan
- `GET /dashboard/overview` - Get comprehensive dashboard data

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Authors

- Jacob Meert
- Arshawn Vossoughi  
- Evan Sinocchi
- Kasra Ghadimi

## Acknowledgments

- Canvas LMS for providing comprehensive API access
- Qdrant for high-performance vector database services
- Sentence Transformers for local embedding generation
- OpenAI for advanced language model capabilities
```
