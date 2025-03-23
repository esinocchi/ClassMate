import io
import os
import sys
import requests
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from prompt_to_file_GPT import prompt_to_pdf
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)
from task_specific_agents.calendar_agent import find_events

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


