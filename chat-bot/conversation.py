import os 
from dotenv import load_dotenv
import openai
import requests



load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
canvas_api_url= "https://psu.instructure.com/api/v1"
canvas_api_token = "1050~HWJHRZ27PcuhUQP2D4eNyMeE4rLYxTXHtX6NntVJBHvkEMRu77TUHc88J2Knctef" 

student_name = "Joey Patroni"

#Get list of course objects
headers = {'Authorization': f'Bearer {canvas_api_token}'}
params = {
    "enrollment_state": "active",
    "include[]": "all_courses",
    "per_page": 100  # Fetch more courses per page (optional)
}

course_name_list = []
url = f"{canvas_api_url}/courses"
page_counter = 1

while url:
    print(f"\n--- Page {page_counter} ---")
    print(f"Requesting URL: {url}")

    response = requests.get(url, headers=headers, params=params)
    params = None  # Clear params after the first request

    # Handle errors
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
        break

    # Extract course names
    courses = response.json()
    print(f"Found {len(courses)} courses on this page.")
    for course in courses:
        course_name = course.get('name')
        if course_name:
            course_name_list.append(course_name)

    # Parse the "Link" header for pagination
    link_header = response.headers.get('Link', '')
    next_url = None

    if link_header:
        links = link_header.split(', ')
        for link in links:
            parts = link.split('; ', 1)
            if len(parts) != 2:
                continue
            url_part, rel_part = parts
            url_part = url_part.strip('<>')
            rel_value = rel_part.replace('rel=', '').strip('"').lower()
            
            if 'next' in rel_value.split():
                next_url = url_part
                break  # Found the next page URL

    # Update URL or terminate the loop
    if next_url:
        print(f"Next page URL: {next_url}")
        url = next_url
    else:
        print("No more pages found.")
        url = None  # Exit the loop

    page_counter += 1

    # Safety check to prevent infinite loops
    if page_counter > 50:
        print("\n⚠️ Safety Break: Stopped after 50 pages.")
        break

print(f"\nTotal courses for {student_name}: {len(course_name_list)}")
print(course_name_list)


system_context = f""" You are a highly professional and task-focused AI assistant for {student_name}. You are designed to assist with school-related tasks, such as helping users with coursework, creating study notes, transcribing video content, and retrieving information from the Canvas LMS (e.g., syllabus details, assignment deadlines, and course updates). 
    {student_name}'s course list: is {course}
    You adhere to the following principles:
    Professionalism: Maintain a strictly professional tone and demeanor in all interactions. Do not respond to or engage with nonsensical or irrelevant queries.
    Accuracy: Provide precise, reliable, and well-structured responses to ensure clarity and usefulness.
    Relevance: Only address topics directly related to schoolwork, Canvas information, or productivity. Politely decline to respond to any questions or requests outside these boundaries.
    Clarity: Break down complex topics into clear, concise, and actionable steps tailored to the users needs.
    Ethics: Do not assist with any requests that would involve academic dishonesty (e.g., writing essays, completing tests, or circumventing school policies).
    Use plain and accessible language to support users of all academic levels, ensuring that instructions and explanations are easy to follow."""

chat = [{'role': 'system', 'content': system_context }]

functions = []





response = openai.ChatCompletion.create(
    model = 'gpt-4o-mini',
    messages = chat,
    temperature = .3,
    max_tokens = 1024

)




