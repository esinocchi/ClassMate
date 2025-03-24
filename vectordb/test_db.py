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
import asyncio
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
    user_id = "7214035"
    token = os.getenv("CANVAS_API_TOKEN")
    courses_selected = {
            "2361957": "CMPSC 465",
            "2379517": "CMPSC 311",
            "2361815": "EARTH 103N",
            "2361972": "CMPEN331",
            "2364485": "ACCT 211"
        }

    handler = DataHandler(user_id, domain="psu.instructure.com", token=token, courses_selected=courses_selected)

    handler.initiate_user_data()

    handler.update_user_data()
    

    time.sleep(180)

async def search_db():
    hf_api_token = os.getenv("HUGGINGFACE_API_KEY")
    db = VectorDatabase('user_data/psu/7210330/user_data.json', hf_api_token=hf_api_token)
    await db.process_data(force_reload=False)
    
    output = await db.search({
        "course_id": "2361510",
        "time_range": "RECENT_PAST",
        "item_types": ["assignment"],
        "specific_dates": [],
        "keywords": [],
        "generality": "SPECIFIC",
        "specific_amount": 5,
        "query": "What was my last assignment in EARTH 101?"
    })
    
    return output

# Run the async function using asyncio
if __name__ == "__main__":
    #get_canvas_data()
    results = asyncio.run(search_db())
    print(results)
    