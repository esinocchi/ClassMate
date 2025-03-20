#!/usr/bin/env python3
"""
Vector Database Test Module
--------------------------
This script tests the functionality of the VectorDatabase class by:
1. Using DataHandler to retrieve Canvas user data
2. Initializing a VectorDatabase with the retrieved data
3. Processing the data to create embeddings
4. Testing search functionality with various parameters

Usage:
    python test_vectordb.py
"""

import os
import json
import argparse
import logging
import time
from dotenv import load_dotenv
from datetime import datetime
import sys
from pathlib import Path
import requests
import certifi


# Add the project root directory to Python path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

# Import our modules
from db import VectorDatabase
from backend.data_retrieval.data_handler import DataHandler

def get_canvas_data():


    # Load environment variables
    load_dotenv()
    user_id = "7210330"
    domain = os.getenv("CANVAS_DOMAIN")
    token = os.getenv("CANVAS_API_TOKEN")
    courses_selected = {
    2372294: "PHYS 211",
    2381676: "STAT ",
    2361723: "APOCCOLYPTIC GEO"
}

    handler = DataHandler(user_id, domain, token, courses_selected=courses_selected)

    handler.initiate_user_data()
    handler.update_user_data()

    time.sleep(180)

def search_db():
    db = VectorDatabase('user_data/psu/7210330/user_data.json')
    db.clear_cache()
    db.process_data(force_reload=True)
    output = db.search({
                "course_id": "all_courses",
                "time_range": "FUTURE",
                "item_types": ["assignment", "event", "announcement"],
                "specific_dates": ["2025-03-20"],
                "keywords": ["tomorrow"],
                "generality": "LOW",
                "query": "Do I have any assingments due tomorrow?"
            }, top_k=3)
    return output

print(search_db())