import asyncio
import os 
from dotenv import load_dotenv
import aiohttp
from datetime import datetime
from dateutil.relativedelta import relativedelta

load_dotenv()

canvas_api_url = os.getenv("CANVAS_API_URL")
canvas_api_token = os.getenv("CANVAS_API_KEY")


async def calculate_grade(
    canvas_base_url: str,
    access_token: str,
    course_code: str,

    session: aiohttp.ClientSession = None
) -> list:
    """
    Retrieve calendar events from the Canvas API for a specific course code from now until the next 3 months.

    Parameters:
        canvas_base_url (str): The base URL of the Canvas instance 
                               (e.g., 'https://canvas.instructure.com').
        access_token (str): Your Canvas API access token.
        course_code (str): The course code to filter the calendar events (e.g., 'course_123').
        session (aiohttp.ClientSession, optional): An existing aiohttp session to use.

    Returns:
        list: Raw calendar events from the Canvas API
    """
    
    url = f"{canvas_base_url}/courses/{course_code}/enrollments"

    # Prepare the headers with the access token
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # Set up the query parameters
    params = {
        "user_id": "self",
        "include[]": "total_scores"
    }

    # Make the API call
    should_close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        should_close_session = True

    try:
        async with session.get(url, headers=headers, params=params) as response:
            response.raise_for_status()
            grade_data = await response.json()
    finally:
        if should_close_session:
            await session.close()
    
    
    return grade_data



if __name__ == '__main__':
    # Replace '2372294' with your actual course code
    course_code = "2372294"
    result = asyncio.run(calculate_grade(canvas_api_url, canvas_api_token, course_code))
    print(result)