# Canvas Copilot

Canvas Copilot is an AI-powered assistant that helps students navigate their Canvas LMS courses, assignments, and other content.

## Project Structure

The project is organized into several modules:

- **canvas_api.py**: Contains the `CanvasAPI` class for interacting with the Canvas LMS API and the `CanvasItem` data model.
- **categorization.py**: Contains components for query categorization, keyword extraction, and time frame detection.
- **vectordatabase.py**: Implements the vector database for storing and retrieving embeddings.
- **canvas_copilot.py**: Contains the main `CanvasCopilot` class that integrates all components.
- **pipeline.py**: The main entry point that pulls everything together.

## Setup

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file with the following variables:
   ```
   OPENAI_API_KEY=your_openai_api_key
   CANVAS_API_TOKEN=your_canvas_api_token
   CANVAS_DOMAIN=your_canvas_domain (default: psu.instructure.com)
   EMBEDDING_MODEL=your_embedding_model (default: all-MiniLM-L6-v2)
   LLM_MODEL=your_llm_model (default: gpt-4o-mini)
   ```

## Usage

### Basic Usage

```python
from canvas_copilot import CanvasCopilot

# Initialize the copilot
copilot = CanvasCopilot()
copilot.initialize()

# Process a query
response = copilot.process_query("When is my next assignment due?")
print(response)
```

### Clearing the Cache

You can clear the vector database cache to force the system to fetch fresh data from Canvas:

```python
# Clear the cache
copilot.clear_cache()

# Re-initialize with fresh data
copilot.initialize()
```

You can also clear the cache from the command line:

```bash
python pipeline.py --clear-cache
```

### PDF Mode

If you don't have a Canvas API token, you can still use Canvas Copilot with PDF files:

```python
from canvas_copilot import CanvasCopilot
from pipeline import pdf_to_canvas_item

# Initialize the copilot
copilot = CanvasCopilot()

# Process a PDF file
pdf_item = pdf_to_canvas_item("assignment.pdf", course_id="CS101", course_name="Computer Science 101")
if pdf_item:
    copilot.vector_db.add_item(pdf_item)
    copilot.initialized = True
    
    # Process a query about the PDF
    response = copilot.process_query("What is the deadline for the assignment?")
    print(response)
```

## Features

- **Query Classification**: Automatically categorizes user queries into relevant categories (assignments, syllabus, announcements, etc.)
- **Time Frame Detection**: Identifies the appropriate time frame for queries (future, recent past, extended past, full semester)
- **Keyword Extraction**: Extracts relevant keywords from user prompts for targeted searches
- **Vector Search**: Utilizes embeddings to find the most relevant information
- **Context-Aware Responses**: Generates helpful responses based on retrieved Canvas data
- **Course Filtering**: Automatically excludes courses older than 4 months to focus on current and recent courses

## License

This project is licensed under the MIT License - see the LICENSE file for details. 