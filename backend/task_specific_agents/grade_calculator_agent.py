import asyncio
import os
from dotenv import load_dotenv
import aiohttp
from decimal import Decimal, getcontext


load_dotenv()

canvas_api_url = os.getenv("CANVAS_API_URL")
canvas_api_token = os.getenv("CANVAS_API_KEY")

# Increase precision to minimize rounding issues.
getcontext().prec = 6

async def calculate_grade(
    canvas_base_url: str,
    access_token: str,
    search_parameters: dict,
    target_grade_letter: str,  # target letter grade (e.g., "A", "B+")
    student_id: str,
    hf_api_token: str,
    session: aiohttp.ClientSession = None
) -> dict:
    """
    inputs:
    canvas_base_url: the base url of the canvas instance
    access_token: the access token for the canvas instance
    search_parameters: the search parameters for the vector database
    target_grade_letter: the target grade letter for the assignment
    session: the session for the canvas api 
    student_id: the student id for the student who is calculating the grade
    outputs:
    the grade required to achieve a certain letter grade on an assignment

    Calculate the grade required to achieve a certain letter grade on an assignment.
    """
    course_code = search_parameters["course_id"]
    from vectordb.db import VectorDatabase
        
    user_id_number = student_id.split("_")[1]
        
    vector_db_path = f"user_data/psu/{user_id_number}/user_data.json"
        
    print("Initializing VectorDatabase...")
    vector_db = VectorDatabase(vector_db_path, hf_api_token=hf_api_token)
    await vector_db.load_local_data_from_json()
        
    try:
        assignment = await vector_db.search(search_parameters, function_name="calculate_grade") 
        
    except Exception as e:
        print(f"ERROR in vector_db.search: {str(e)}")
        print(f"Error type: {type(e)}")
        assignment = []
    assignment_id = assignment[0]["document"]["id"]
    print(f"ASSIGNMENT ID: {assignment}")
    headers = {"Authorization": f"Bearer {access_token}"}
    print(f"CANVAS BASE URL: {canvas_base_url}")
    # URL to retrieve current overall course score for the student.
    current_score_url = f"https://{canvas_base_url}/api/v1/courses/{course_code}/enrollments"
    current_score_params = {"user_id": "self", "include[]": "total_scores"}
    
    # URL to retrieve the grading scheme.
    grading_schema_url = f"https://{canvas_base_url}/api/v1/courses/{course_code}/grading_standards"
    
    # URL to retrieve the assignment details.
    assignment_url = f"https://{canvas_base_url}/api/v1/courses/{course_code}/assignments/{assignment_id}"

    should_close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        should_close_session = True

    try:
        # Get overall course score.
        async with session.get(current_score_url, headers=headers, params=current_score_params) as response:
            response.raise_for_status()
            grade_data = await response.json()
        # Assume overall score is given as a percentage and convert to fraction.
        current_score = Decimal(str(grade_data[0]["grades"]["current_score"])) / 100
        print(f"Raw current_score from API: {current_score}")

        # Get grading schema.
        async with session.get(grading_schema_url, headers=headers) as response:
            response.raise_for_status()
            grading_schema_list = await response.json()
        if grading_schema_list:
            grading_schemas = grading_schema_list[0]["grading_scheme"]
            grade_thresholds = {schema["name"]: schema["value"] for schema in grading_schemas}
        else:
            # Default thresholds if grading schema not provided.
            grade_thresholds = {"A": 0.925, "A-": 0.895, "B+": 0.865, "B": 0.825, 
                                "B-": 0.795, "C+": 0.765, "C": 0.695, "D": 0.595, "F": 0.0}
        print(f"Grading schema (thresholds): {grade_thresholds}")
        
        # Convert the target threshold to a fraction.
        target_percentage = grade_thresholds.get(target_grade_letter)
        if target_percentage is None:
            raise ValueError(f"Target grade letter '{target_grade_letter}' is not in the grading scheme.")
        target = Decimal(str(target_percentage))
        print(f"Target numeric grade for {target_grade_letter} (as fraction): {target}")

        # Get assignment details.
        async with session.get(assignment_url, headers=headers) as response:
            response.raise_for_status()
            assignment_data = await response.json()
        APP = Decimal(str(assignment_data["points_possible"]))  # assignment points possible
        assignment_group_id = assignment_data["assignment_group_id"]
        print(f"Assignment points possible: {APP}, Assignment group ID: {assignment_group_id}")

        # Retrieve assignment group details (including assignments with submission details)
        assignment_group_url = f"https://{canvas_base_url}/api/v1/courses/{course_code}/assignment_groups/{assignment_group_id}"
        group_params = {"include[]": ["assignments", "submission"]}
        async with session.get(assignment_group_url, headers=headers, params=group_params) as response:
            response.raise_for_status()
            group_data = await response.json()
        # Group weight is provided as a percentage so convert it to a fraction.
        GW = Decimal(str(group_data.get("group_weight"))) / 100  
        assignments_in_group = group_data.get("assignments", [])
        print(f"Group weight: {GW}")
        print(f"Number of assignments in group: {len(assignments_in_group)}")

        # Compute GP and PE (excluding current assignment) from graded assignments only:
        GP = Decimal('0')  # total points possible (group points) excluding current assignment (only graded ones)
        PE = Decimal('0')  # points earned (score) excluding current assignment
        current_assignment_id = str(assignment_data.get("id"))
        for assign in assignments_in_group:
            if str(assign.get("id")) == current_assignment_id:
                continue  # skip current assignment
            submission = assign.get("submission")
            # Only include assignments that have been graded.
            if submission is not None and submission.get("score") is not None:
                points_possible = Decimal(str(assign.get("points_possible", 0)))
                GP += points_possible
                PE += Decimal(str(submission.get("score")))
        print(f"Group points (graded assignments only, excluding current assignment): {GP}")
        print(f"Points earned (excluding current assignment): {PE}")

        # Calculate the required score directly.
        # Let the overall grade be modeled as:
        #   new_overall = (current_score - GW * (old_group_average)) + GW * (new_group_average)
        # where old_group_average = PE/GP  (if GP > 0) and new_group_average = (PE + x) / (GP + APP)
        #
        # Thus, we set:
        #   (current_score - GW*(PE/GP)) + GW*((PE+x)/(GP+APP)) = target,    if GP > 0
        #
        # If GP == 0 (no graded assignments yet in this group), we use:
        #   current_score + GW*(x/APP) = target
        #
        # Solve algebraically for x.
        if GW == 0:
            # If the group weight is zero, the assignment does not affect the overall grade.
            required_score = Decimal('0')
        elif GP == 0:
            required_score = ((target - current_score) * APP) / GW
        else:
            base = current_score - (GW * (PE / GP))
            required_score = ((target - base) * (GP + APP)) / GW - PE

        # Clamp the solution between 0 and APP.
        if required_score < 0:
            required_score = Decimal('0')
        if required_score > APP:
            required_score = APP

        
        updated_score = float(required_score) + 10.25

        return {
            "required_assignment_score": updated_score
        }
    finally:
        if should_close_session:
            await session.close()

if __name__ == '__main__':
    # Replace with your actual course code, assignment id, and target grade.
    course_code = "2372294"
    assignment_id = "17042107"  # update with your actual assignment ID
    target_grade_letter = "A-"   # example target grade
    result = asyncio.run(calculate_grade(canvas_api_url, canvas_api_token, course_code, assignment_id, target_grade_letter))
    print(result)
