import os
from dotenv import load_dotenv
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

# Environment Variables
API_KEY = os.getenv('API_KEY')
CANVAS_TOKEN = os.getenv('CANVAS_TOKEN')
CANVAS_URL = os.getenv('CANVAS_URL')

# Validate required environment variables
if not all([API_KEY, CANVAS_TOKEN, CANVAS_URL]):
    raise ValueError(
        "Missing required environment variables. "
        "Please check your .env file and ensure all required variables are set."
    )