import os 
from dotenv import load_dotenv
import requests

load_dotenv()

canvas_api_url= os.getenv("CANVAS_API_URL")
canvas_api_token = os.getenv("CANVAS_API_KEY")

def find_events(
   canvas_base_url: str,
   access_token: str,
   start_date: str,
   end_date: str,
   context_codes: list
) -> dict:
    """
    Retrieve calendar events from the Canvas API.

    Parameters:
        canvas_base_url (str): The base URL of the Canvas instance 
                               (e.g., 'https://canvas.instructure.com').
        access_token (str): Your Canvas API access token.
        start_date (str): Start date (ISO8601 format) to filter events.
        end_date (str): End date (ISO8601 format) to filter events.
        context_codes (list): List of context codes (e.g., ['course_123', 'user_456'])
                              to filter the calendar events.

    Returns:
        dict: The JSON response from the Canvas API containing the events.

    Raises:
        requests.exceptions.HTTPError: If the API returns an unsuccessful status code.
    """

    url = f"{canvas_base_url}/calendar_events"

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    # Construct query parameters.
    params = {
        "start_date": start_date,
        "end_date": end_date,
    }

    # Canvas expects multiple context_codes using the parameter name 'context_codes[]'
    # so we add each code as part of the query parameters.
    for code in context_codes:
        params.setdefault("context_codes[]", []).append(code)

    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def create_event(
        canvas_base_url: str,
        access_token: str,
        context_code: str,
        title: str,
        start_at: str,
        end_at: str = None,
        description: str = None,
        location_name: str = None,
        location_address: str = None,
        all_day: bool = False,
        duplicate_count: int = None,
        duplicate_interval: int = None,
        duplicate_frequency: str = None,
        duplicate_append_iterator: bool = None,

    ) -> dict:
    """
    Create a calendar event using the Canvas API.

    Parameters:
        canvas_base_url (str): The base URL of the Canvas instance 
                               (e.g., 'https://canvas.instructure.com').
        access_token (str): Your Canvas API access token.
        context_code (str): The context code (e.g., 'course_123' or 'user_456').
        title (str): Title of the event.
        start_at (str): Start date/time in ISO8601 format.
        end_at (str, optional): End date/time in ISO8601 format.
        description (str, optional): Description of the event.
        location_name (str, optional): Name of the location.
        location_address (str, optional): Address of the location.
        all_day (bool, optional): Indicates if the event lasts all day. Defaults to False.
        duplicate_count (int, optional): Number of times to duplicate the event (max 200).
        duplicate_interval (int, optional): Interval between duplicates; defaults to 1.
        duplicate_frequency (str, optional): Frequency ('daily', 'weekly', or 'monthly'); defaults to "weekly".
        duplicate_append_iterator (bool, optional): If True, appends an increasing counter to the title.

    Returns:
        dict: The JSON response from the Canvas API if the request is successful.

    Raises:
        requests.exceptions.HTTPError: If the Canvas API returns an unsuccessful status code.
    """
    if end_at is None:
        all_day = True

    url = f"{canvas_api_url}/calendar_events"

    headers = {
        "Authorization": f"Bearer {canvas_api_token}"
    }

    data = {
        "calendar_event[context_code]": context_code,
        "calendar_event[title]": title,
        "calendar_event[start_at]": start_at,
        "calendar_event[all_day]": "true" if all_day else "false"
    }

    if end_at:
        data["calendar_event[end_at]"] = end_at
    if description:
        data["calendar_event[description]"] = description
    if location_name:
        data["calendar_event[location_name]"] = location_name
    if location_address:
        data["calendar_event[location_address]"] = location_address

     # Add duplicate event options if provided
    if duplicate_count is not None:
        data["calendar_event[duplicate][count]"] = duplicate_count
    if duplicate_interval is not None:
        data["calendar_event[duplicate][interval]"] = duplicate_interval
    if duplicate_frequency is not None:
        data["calendar_event[duplicate][frequency]"] = duplicate_frequency
    if duplicate_append_iterator is not None:
        data["calendar_event[duplicate][append_iterator]"] = "true" if duplicate_append_iterator else "false"

    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    return response.json()



if __name__ == "__main__":
    # Example usage:
    canvas_base_url = canvas_api_url  # Replace with your Canvas domain.
    access_token = canvas_api_token
    start_date = "2025-03-01T00:00:00Z"
    end_date = "2025-03-03T23:59:59Z"
    context_codes = [ "course_2372294","user_7210330"]

    try:
        events = find_events(
            canvas_base_url=canvas_base_url,
            access_token=access_token,
            start_date=start_date,
            end_date=end_date,
            context_code=context_codes
        )
        print("Retrieved events:")
        print(events)
    except requests.exceptions.HTTPError as e:
        print("Failed to retrieve events:")
        print(e)