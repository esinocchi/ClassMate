import asyncio
import os 
from dotenv import load_dotenv
import aiohttp
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal, getcontext

load_dotenv()

canvas_api_url = os.getenv("CANVAS_API_URL")
canvas_api_token = os.getenv("CANVAS_API_KEY")

# Increase precision to minimize rounding issues.
getcontext().prec = 6

async def calculate_grade(
    canvas_base_url: str,
    access_token: str,
    course_code: str,
    assignment_id: str,
    target_grade_letter: str,  # target letter grade (e.g., "A", "B+")
    session: aiohttp.ClientSession = None
) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # URL to retrieve current score for the student.
    current_score_url = f"{canvas_base_url}/courses/{course_code}/enrollments"
    current_score_params = {
        "user_id": "self",
        "include[]": "total_scores"
    }
    
    # URL to retrieve the grading scheme.
    grading_schema_url = f"{canvas_base_url}/courses/{course_code}/grading_standards"
    
    # URL to retrieve the assignment details.
    assignment_url = f"{canvas_base_url}/courses/{course_code}/assignments/{assignment_id}"

    # Create session if not provided.
    should_close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        should_close_session = True

    try:
        # Get current score.
        async with session.get(current_score_url, headers=headers, params=current_score_params) as response:
            response.raise_for_status()
            grade_data = await response.json()
        current_score = grade_data[0]["grades"]["current_score"]
        
        # Get grading schema.
        async with session.get(grading_schema_url, headers=headers) as response:
            response.raise_for_status()
            grading_schema_list = await response.json()
        if grading_schema_list:
            grading_schemas = grading_schema_list[0]["grading_scheme"]
            grade_thresholds = {schema["name"]: schema["value"] for schema in grading_schemas}
        else:
            grade_thresholds = {"A": 93, "A-": 90, "B+": 87, "B": 83, "B-": 80, "C+": 77, "C": 70, "D": 60, "F": 0}
            
        # Get assignment details.
        async with session.get(assignment_url, headers=headers) as response:
            response.raise_for_status()
            assignment_data = await response.json()
        assignment_points = assignment_data["points_possible"]
        assignment_group_id = assignment_data["assignment_group_id"]

        # Retrieve assignment group details (including assignments with submission details)
        assignment_group_url = f"{canvas_base_url}/courses/{course_code}/assignment_groups/{assignment_group_id}"
        # Include both assignments and submission details for the current user.
        params = {"include[]": ["assignments", "submission"]}
        async with session.get(assignment_group_url, headers=headers, params=params) as response:
            response.raise_for_status()
            group_data = await response.json()
        # Extract group weight from the group data.
        group_weight = group_data.get("group_weight")
        assignments_in_group = group_data.get("assignments", [])

        # Filter assignments that have been graded.
        graded_assignments = [
            assignment for assignment in assignments_in_group
            if assignment.get("submission") and assignment["submission"].get("score") is not None
        ]

        # Sum the points from graded assignments and add the upcoming assignment's points.
        total_points_in_group = sum(item.get("points_possible", 0) for item in graded_assignments) + assignment_points

        # Compute effective weight if group weight exists and total points are > 0.
        effective_weight = None
        if group_weight is not None and total_points_in_group > 0:
            effective_weight = (assignment_points / total_points_in_group) * group_weight

        # Check that effective_weight is valid.
        if effective_weight is None or effective_weight <= 0:
            required_assignment_score = None  # Cannot compute without effective weight.
        else:
            target_numeric = grade_thresholds.get(target_grade_letter)
            if target_numeric is None:
                raise ValueError(f"Target grade letter '{target_grade_letter}' is not in the grading scheme.")

            # Convert values to Decimal for precise calculations.
            current_score_dec = Decimal(str(current_score))
            target_numeric_dec = Decimal(str(target_numeric))
            assignment_points_dec = Decimal(str(assignment_points))
            effective_weight_dec = Decimal(str(effective_weight))
            
            # Weighted final grade model:
            # final_grade = current_score*(1 - effective_weight/100) + (assignment_score/assignment_points)*effective_weight
            # Solve for assignment_score:
            required_assignment_score = assignment_points_dec * (
                target_numeric_dec - current_score_dec * (Decimal('1') - effective_weight_dec / Decimal('100'))
            ) / effective_weight_dec

            # Ensure the required score is within the assignment bounds.
            if required_assignment_score < 0:
                required_assignment_score = Decimal('0')
            if required_assignment_score > assignment_points_dec:
                required_assignment_score = assignment_points_dec

        # Return all relevant values.
        return {
            "current_score": current_score,
            "grade_thresholds": grade_thresholds,
            "assignment_points": assignment_points,
            "total_points_in_group": total_points_in_group,
            "group_weight": group_weight,
            "effective_weight": effective_weight,
            "target_grade_letter": target_grade_letter,
            "target_numeric": grade_thresholds.get(target_grade_letter),
            "required_assignment_score": float(required_assignment_score) if required_assignment_score is not None else None
        }
    finally:
        if should_close_session:
            await session.close()


if __name__ == '__main__':
    # Replace with your actual course code, assignment id, and target grade.
    course_code = "2372294"
    assignment_id = "16704242"  # update with your actual assignment ID
    target_grade_letter = "A"   # example target grade
    result = asyncio.run(calculate_grade(canvas_api_url, canvas_api_token, course_code, assignment_id, target_grade_letter))
    print(result)
