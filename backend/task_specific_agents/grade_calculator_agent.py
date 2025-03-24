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
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    current_score_url = f"{canvas_base_url}/courses/{course_code}/enrollments"
    current_score_params = {
        "user_id": "self",
        "include[]": "total_scores"
    }
    
    grading_schema_url = f"{canvas_base_url}/courses/{course_code}/grading_standards"

    # Create session if not provided
    should_close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        should_close_session = True

    try:
        # First API call: get current score
        async with session.get(current_score_url, headers=headers, params=current_score_params) as response:
            response.raise_for_status()
            grade_data = await response.json()
        current_score = grade_data[0]["grades"]["current_score"]

        # Second API call: get grading schema
        async with session.get(grading_schema_url, headers=headers) as response:
            response.raise_for_status()
            grading_schema_list = await response.json()
        grading_schemas = grading_schema_list[0]["grading_scheme"]
        grade_thresholds = {}
        for schema in grading_schemas:
            grade_thresholds[schema["name"]] = schema["value"]

        print(grade_thresholds)
        # You can now use current_score and grade_thresholds for further calculations.
        return current_score
    finally:
        if should_close_session:
            await session.close()




if __name__ == '__main__':
    # Replace '2372294' with your actual course code
    course_code = "2372294"
    result = asyncio.run(calculate_grade(canvas_api_url, canvas_api_token, course_code))
    print(result)