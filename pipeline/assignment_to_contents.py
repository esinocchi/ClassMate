import requests
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import io
import fitz

load_dotenv()
# Define your Canvas instance URL and IDs
canvas_base_url = 'https://psu.instructure.com'
course_id = '2361957'
assignment_id = '17026375'
access_token = os.getenv("CANVAS_TOKEN")

# Construct the API URL
api_url = f'{canvas_base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}'

# Set up the request headers with the access token
headers = {
    'Authorization': f'Bearer {access_token}'
}

# Canvas API endpoints
assignment_api_url = f"https://psu.instructure.com/api/v1/courses/{course_id}/assignments/{assignment_id}"
headers = {"Authorization": f"Bearer {access_token}"}

# Step 1: Get the Assignment details
assignment_response = requests.get(assignment_api_url, headers=headers)

if assignment_response.status_code == 200:
    assignment_data = assignment_response.json()
    description_html = assignment_data.get("description", "")

    # Step 2: Extract PDF link from the assignment description
    soup = BeautifulSoup(description_html, "html.parser")
    pdf_link = soup.find("a", href=True)

    if pdf_link:
        file_api_url = pdf_link.get("data-api-endpoint")  # Extract Canvas file API URL
        print(f"Extracted File API URL: {file_api_url}")

        # Step 3: Get the actual file download URL
        file_response = requests.get(file_api_url, headers=headers)

        if file_response.status_code == 200:
            file_data = file_response.json()
            download_url = file_data["url"]

            # Step 4: Download and Process the PDF in-memory
            pdf_response = requests.get(download_url, headers=headers)

            if pdf_response.status_code == 200:
                pdf_bytes = io.BytesIO(pdf_response.content)  # Store PDF in memory

                # Extract text from PDF
                pdf_text = []
                with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
                    for page in doc:
                        pdf_text.append(page.get_text())

                full_text = "\n".join(pdf_text)
                print("\nExtracted PDF Text:\n", full_text)
            else:
                print(f"Failed to download PDF. Status Code: {pdf_response.status_code}")
        else:
            print(f"Failed to retrieve file details. Status Code: {file_response.status_code}")
    else:
        print("No PDF link found in the assignment description.")
else:
    print(f"Failed to retrieve assignment details. Status Code: {assignment_response.status_code}")
