#!/usr/bin/env python3
"""
Canvas Copilot Pipeline
-----------------------
A complete implementation of the Canvas Copilot pipeline that:

1. Processes user queries about Canvas LMS data
2. Extracts keywords and identifies query categories
3. Retrieves relevant information from Canvas API
4. Creates a vector database for context storage
5. Generates context-aware responses using LLM

This module serves as the entry point for the Canvas Copilot application and coordinates
the interaction between various components of the system. It handles command-line arguments,
initializes the necessary components, and processes user queries to generate responses.
"""

import os
import sys
import logging
import PyPDF2
from datetime import datetime
from dotenv import load_dotenv

# Import components from other modules
from canvas_api import CanvasAPI, CanvasItem, TimeFrame
from categorization import KeywordExtractor, QueryClassifier, QueryCategory, TimeFrameDetector
from vectordatabase import VectorDatabase
from canvas_copilot import CanvasCopilot

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("canvas_copilot")

# Constants
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CANVAS_API_TOKEN = os.getenv("CANVAS_API_TOKEN")


def pdf_to_canvas_item(pdf_path: str, course_id: str = "unknown", course_name: str = "Unknown Course") -> CanvasItem:
    """
    Convert a PDF file to a CanvasItem object for use in the Canvas Copilot system.
    
    This function reads a PDF file, extracts its text content, and creates a CanvasItem
    that can be processed by the vector database and LLM components of the system.
    
    Args:
        pdf_path (str): Path to the PDF file to convert
        course_id (str, optional): Course ID to associate with the PDF. Defaults to "unknown".
        course_name (str, optional): Course name to associate with the PDF. Defaults to "Unknown Course".
        
    Returns:
        CanvasItem: A CanvasItem object containing the PDF content and metadata,
                   or None if an error occurs during processing.
    """
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            
            for page in reader.pages:
                text += page.extract_text() + " "
        
        filename = os.path.basename(pdf_path)
        title = os.path.splitext(filename)[0]
        
        return CanvasItem(
            id=f"pdf_{title}",
            type="file",
            title=title,
            content=text,
            course_id=course_id,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            metadata={"course_name": course_name, "file_type": "pdf"}
        )
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        return None


# Example usage
if __name__ == "__main__":
    # Check if API keys are set
    if not OPENAI_API_KEY:
        print("Warning: OPENAI_API_KEY not set. Please set it in .env file.")
    
    if not CANVAS_API_TOKEN:
        print("Warning: CANVAS_API_TOKEN not set. Using PDF mode only.")
    else:
        # Full Canvas API example
        copilot = CanvasCopilot()
        
        # Check for command line arguments
        debug_mode = False
        if "--debug" in sys.argv:
            debug_mode = True
            logger.setLevel(logging.DEBUG)
            print("Running in DEBUG mode - verbose logging enabled")
        
        if "--clear-cache" in sys.argv:
            print("Clearing vector database cache...")
            copilot.clear_cache()
            print("Cache cleared. Initializing with fresh data...")
        
        try:
            print("Initializing Canvas Copilot...")
            copilot.initialize()
            print("Initialization complete")
            
            # Test query
            query = "what is my next assignment"
            
            # Override query from command line if provided
            for i, arg in enumerate(sys.argv):
                if arg == "--query" and i + 1 < len(sys.argv):
                    query = sys.argv[i + 1]
                    break
            
            print(f"\nProcessing query: \"{query}\"")
            
            try:
                response = copilot.process_query(query)
                print("\n--- RESPONSE ---")
                print(response)
                print("----------------\n")
            except Exception as e:
                print(f"Error processing query: {e}")
                if debug_mode:
                    import traceback
                    traceback.print_exc()
                    
        except Exception as e:
            print(f"Error initializing Canvas Copilot: {e}")
            if debug_mode:
                import traceback
                traceback.print_exc()