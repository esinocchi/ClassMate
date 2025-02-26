#!/usr/bin/env python3
"""
Canvas API Module
----------------
Handles all interactions with the Canvas LMS API.

This module provides a structured interface for communicating with the Canvas Learning
Management System API. It includes classes for representing Canvas items (assignments,
announcements, files, etc.), defining time frames for contextual queries, and a
comprehensive API client for retrieving data from Canvas.

The module handles authentication, request formatting, response parsing, rate limiting,
and error handling when interacting with the Canvas API. It provides a unified interface
for other components of the Canvas Copilot system to access Canvas data without
needing to understand the underlying API details.
"""

import os
import requests
import logging
import re
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger("canvas_copilot")

# Constants
CANVAS_API_TOKEN = os.getenv("CANVAS_API_TOKEN")
CANVAS_DOMAIN = os.getenv("CANVAS_DOMAIN", "psu.instructure.com")


@dataclass
class CanvasItem:
    """
    Represents an item from Canvas LMS.
    
    This class provides a standardized structure for various types of content
    retrieved from Canvas, such as assignments, announcements, files, etc.
    It is designed to be used throughout the Canvas Copilot system to ensure
    consistent handling of Canvas data.
    
    Attributes:
        id (str): Unique identifier for the item
        type (str): Type of the item ('assignment', 'announcement', 'file', etc.)
        title (str): Title or name of the item
        content (str): Textual content of the item
        course_id (str): ID of the course the item belongs to
        created_at (str): ISO format timestamp when the item was created
        updated_at (str): ISO format timestamp when the item was last updated
        url (Optional[str]): URL to access the item in Canvas (if available)
        due_date (Optional[str]): Due date for assignments (if applicable)
        metadata (Optional[Dict[str, Any]]): Additional metadata for the item
    """
    id: str
    type: str  # 'assignment', 'announcement', 'file', etc.
    title: str
    content: str
    course_id: str
    created_at: str
    updated_at: str
    url: Optional[str] = None
    due_date: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TimeFrame:
    """
    Enumeration of time frames for query context.
    
    This class defines constants to represent different time periods that can be used
    to filter Canvas data by date. It also provides methods to convert these abstract
    time frames into concrete date ranges.
    
    Constants:
        FUTURE: From now until the end of the semester
        RECENT_PAST: From two weeks ago until now
        EXTENDED_PAST: From one month ago until now
        FULL_SEMESTER: From the beginning of the semester until now
        ALL_TIME: No time restriction
    """
    FUTURE = "future"                   # NOW to END_SEMESTER
    RECENT_PAST = "recent_past"         # 2 WEEKS PRIOR to NOW
    EXTENDED_PAST = "extended_past"     # MONTH PRIOR to NOW
    FULL_SEMESTER = "full_semester"     # BEGINNING_SEMESTER to NOW
    ALL_TIME = "all_time"               # No time restriction

    @staticmethod
    def get_date_range(time_frame: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Get the start and end dates for a time frame.
        
        This method converts a time frame constant into actual datetime objects
        representing the start and end of the time period.
        
        Args:
            time_frame (str): One of the TimeFrame constants
            
        Returns:
            Tuple[Optional[datetime], Optional[datetime]]: A tuple containing the start 
            and end dates as datetime objects. Returns (None, None) for ALL_TIME to 
            indicate no date restrictions.
        """
        now = datetime.now(timezone.utc)
        
        if time_frame == TimeFrame.FUTURE:
            # Estimate end of semester as 4 months from now
            return now, now + timedelta(days=120)
        
        elif time_frame == TimeFrame.RECENT_PAST:
            return now - timedelta(days=14), now
        
        elif time_frame == TimeFrame.EXTENDED_PAST:
            return now - timedelta(days=30), now
        
        elif time_frame == TimeFrame.FULL_SEMESTER:
            # Estimate beginning of semester as 4 months ago
            return now - timedelta(days=120), now
        
        elif time_frame == TimeFrame.ALL_TIME:
            return None, None
        
        # Default to recent items
        return now - timedelta(days=14), now


class CanvasAPI:
    """
    Interface with Canvas LMS API.
    
    This class provides methods to authenticate and communicate with the Canvas API,
    handling pagination, error handling, and rate limiting. It includes methods to
    retrieve various types of Canvas data such as courses, assignments, announcements,
    and files.
    """
    
    def __init__(self, domain: str = CANVAS_DOMAIN, token: str = CANVAS_API_TOKEN):
        """
        Initialize the Canvas API client.
        
        Args:
            domain (str, optional): The Canvas domain to connect to. Defaults to value from environment.
            token (str, optional): API token for authentication. Defaults to value from environment.
        """
        self.domain = domain
        self.token = token
        self.base_url = f"https://{domain}/api/v1"
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make a request to the Canvas API"""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Canvas API request failed: {e}")
            return {}
    
    def get_courses(self, include_old_courses=False) -> List[Dict]:
        """
        Get list of courses for the current user
        
        Args:
            include_old_courses: If False, only returns courses updated within the last 4 months
        """
        courses = self._make_request("courses", {"enrollment_state": "active"})
        
        if not include_old_courses:
            # Filter out courses older than 4 months
            current_time = datetime.now(timezone.utc)
            four_months_ago = current_time - timedelta(days=120)  # Approximately 4 months
            
            filtered_courses = []
            for course in courses:
                # Check if the course has been updated recently
                if "updated_at" in course and course["updated_at"]:
                    try:
                        # Parse the updated_at date
                        updated_at_str = course["updated_at"].replace('Z', '+00:00')
                        updated_at = datetime.fromisoformat(updated_at_str)
                        
                        # Only include courses updated within the last 4 months
                        if updated_at > four_months_ago:
                            filtered_courses.append(course)
                            logger.info(f"Including recent course: {course.get('name', 'Unknown')} (updated: {updated_at.strftime('%Y-%m-%d')})")
                        else:
                            logger.info(f"Excluding old course: {course.get('name', 'Unknown')} (updated: {updated_at.strftime('%Y-%m-%d')})")
                    except Exception as e:
                        # If we can't parse the date, include the course by default
                        logger.warning(f"Couldn't parse date for course {course.get('name', 'Unknown')}: {e}")
                        filtered_courses.append(course)
                else:
                    # If there's no updated_at field, include the course by default
                    filtered_courses.append(course)
            
            logger.info(f"Filtered out {len(courses) - len(filtered_courses)} courses older than 4 months")
            return filtered_courses
        
        return courses

    def is_recent_course(self, course_id: str) -> bool:
        """Check if a course is recent (updated within the last 4 months)"""
        try:
            course_details = self._make_request(f"courses/{course_id}")
            
            if "updated_at" in course_details and course_details["updated_at"]:
                # Parse the updated_at date
                updated_at_str = course_details["updated_at"].replace('Z', '+00:00')
                updated_at = datetime.fromisoformat(updated_at_str)
                
                # Check if the course was updated within the last 4 months
                current_time = datetime.now(timezone.utc)
                four_months_ago = current_time - timedelta(days=120)
                
                return updated_at > four_months_ago
            
            # If we can't determine the age, assume it's recent
            return True
        except Exception as e:
            logger.error(f"Error checking if course {course_id} is recent: {e}")
            # If there's an error, assume it's recent to be safe
            return True
    
    def get_assignments(self, course_id: str) -> List[Dict]:
        """Get assignments for a course"""
        # First check if this is a recent course
        if not self.is_recent_course(course_id):
            logger.info(f"Skipping assignments for old course {course_id}")
            return []
            
        assignments = self._make_request(f"courses/{course_id}/assignments")
        logger.info(f"Retrieved {len(assignments)} assignments for course {course_id}")
        for assignment in assignments[:3]:  # Log first few for debugging
            due_date = assignment.get("due_at", "None")
            title = assignment.get("name", "Untitled")
            logger.info(f"Assignment: {title}, due: {due_date}")
        return assignments
    
    def get_calendar_events(self, start_date=None, end_date=None, event_types=None) -> List[Dict]:
        """
        Get calendar events for the current user
        
        Args:
            start_date: Start date for filtering events
            end_date: End date for filtering events
            event_types: Type of events to retrieve (e.g., 'assignment', 'event')
        """
        params = {
            "per_page": 100  # Get more results per page
        }
        
        # Add date range if provided
        if start_date:
            if isinstance(start_date, datetime):
                params["start_date"] = start_date.isoformat()
            else:
                params["start_date"] = start_date
                
        if end_date:
            if isinstance(end_date, datetime):
                params["end_date"] = end_date.isoformat()
            else:
                params["end_date"] = end_date
        
        # Add event types if provided
        if event_types:
            params["type"] = event_types
        else:
            params["type"] = "assignment"  # Default to assignments
            
        logger.info(f"Fetching calendar events with params: {params}")
        events = self._make_request("calendar_events", params)
        logger.info(f"Retrieved {len(events)} calendar events")
        
        return events
    
    def get_planning_calendar(self, start_date=None) -> List[Dict]:
        """
        Get all planning items (calendar view) from Canvas
        
        Args:
            start_date: Start date for filtering events
        """
        try:
            # This gets the planner items which should match what's in the calendar UI
            params = {
                "per_page": 100
            }
            
            # Add start date if provided
            if start_date:
                if isinstance(start_date, datetime):
                    params["start_date"] = start_date.strftime("%Y-%m-%d")
                else:
                    params["start_date"] = start_date
            else:
                params["start_date"] = datetime.now().strftime("%Y-%m-%d")
                
            planner_items = self._make_request("planner/items", params)
            logger.info(f"Retrieved {len(planner_items)} planner items")
            
            # Log a few items for debugging
            for item in planner_items[:5]:
                if 'plannable' in item and 'title' in item['plannable']:
                    logger.info(f"Planner item: {item['plannable']['title']}, due: {item.get('plannable_date', 'Unknown')}")
            
            return planner_items
        except Exception as e:
            logger.error(f"Error getting planner calendar: {e}")
            return []
    
    def get_upcoming_assignments(self, time_frame=TimeFrame.FUTURE) -> List[CanvasItem]:
        """
        Get upcoming assignments from the calendar
        
        Args:
            time_frame: Time frame to search within
        """
        # Get date range based on time frame
        start_date, end_date = TimeFrame.get_date_range(time_frame)
        
        # Default to 3 weeks in the future if we're using the FUTURE time frame
        if time_frame == TimeFrame.FUTURE and start_date and end_date:
            end_date = start_date + timedelta(days=21)
        
        # Convert to ISO format for API calls
        start_date_str = start_date.isoformat() if start_date else datetime.now().isoformat()
        end_date_str = end_date.isoformat() if end_date else (datetime.now() + timedelta(days=21)).isoformat()
        
        logger.info(f"Fetching assignments from {start_date_str} to {end_date_str} (time frame: {time_frame})")
        
        # Try multiple sources of upcoming assignments
        canvas_items = []
        
        # 1. Get calendar events
        events = self.get_calendar_events(start_date_str, end_date_str, "assignment")
        logger.info(f"Retrieved {len(events)} calendar events")
        
        for event in events:
            if event.get("assignment", None):
                course_id = event.get("context_code", "").replace("course_", "") if event.get("context_code") else ""
                
                # Skip if this is from an old course
                if course_id and not self.is_recent_course(course_id):
                    logger.debug(f"Skipping calendar event from old course: {event.get('title', 'Untitled')}")
                    continue
                    
                course_name = event.get("context_name", "Unknown Course")
                
                canvas_items.append(CanvasItem(
                    id=f"cal_{event.get('id', '')}",
                    type="assignment",
                    title=event.get("title", "Untitled Assignment"),
                    content=event.get("description", ""),
                    course_id=course_id,
                    created_at=event.get("created_at", ""),
                    updated_at=event.get("updated_at", ""),
                    due_date=event.get("start_at", ""),  # Calendar events use start_at for due date
                    url=event.get("html_url", ""),
                    metadata={"course_name": course_name, "calendar_event": True}
                ))
        
        # 2. Get planner items (this should match what's in the calendar UI)
        planner_items = self.get_planning_calendar(start_date_str)
        
        for item in planner_items:
            if 'plannable_type' in item and item['plannable_type'] in ['assignment', 'quiz', 'discussion_topic']:
                plannable = item.get('plannable', {})
                course_id = str(item.get('course_id', ''))
                
                # Skip if this is from an old course
                if course_id and not self.is_recent_course(course_id):
                    logger.debug(f"Skipping planner item from old course: {plannable.get('title', 'Untitled')}")
                    continue
                
                # Try to get course name
                course_name = "Unknown Course"
                if 'context_name' in item:
                    course_name = item['context_name']
                
                # Use different date field based on what's available
                due_date = item.get('plannable_date', '')
                if not due_date and 'due_at' in plannable:
                    due_date = plannable['due_at']
                
                # Filter by end date if applicable
                if end_date and due_date:
                    try:
                        due_date_str = due_date.replace('Z', '+00:00') if 'Z' in due_date else due_date
                        due_date_obj = datetime.fromisoformat(due_date_str)
                        
                        if due_date_obj > end_date:
                            logger.debug(f"Skipping item due after specified end date: {plannable.get('title', 'Untitled')}")
                            continue
                    except Exception as e:
                        # If we can't parse the date, include it anyway
                        logger.debug(f"Couldn't parse date for {plannable.get('title', 'Untitled')}: {e}")
                
                canvas_items.append(CanvasItem(
                    id=f"plan_{item.get('plannable_id', '')}",
                    type=item.get('plannable_type', 'assignment'),
                    title=plannable.get('title', 'Untitled Item'),
                    content=plannable.get('description', ''),
                    course_id=course_id,
                    created_at=plannable.get('created_at', ''),
                    updated_at=plannable.get('updated_at', ''),
                    due_date=due_date,
                    url=item.get('html_url', ''),
                    metadata={"course_name": course_name, "planner_item": True}
                ))
                
        logger.info(f"Created {len(canvas_items)} CanvasItems from calendar and planner sources")
        return canvas_items
    
    def get_announcements(self, course_id: str) -> List[Dict]:
        """Get announcements for a course"""
        return self._make_request(f"courses/{course_id}/discussion_topics", 
                                 {"only_announcements": True})
    
    def get_files(self, course_id: str) -> List[Dict]:
        """Get files for a course"""
        return self._make_request(f"courses/{course_id}/files")
    
    def get_modules(self, course_id: str) -> List[Dict]:
        """Get modules for a course"""
        return self._make_request(f"courses/{course_id}/modules")
    
    def get_module_items(self, course_id: str, module_id: str) -> List[Dict]:
        """Get items in a module"""
        return self._make_request(f"courses/{course_id}/modules/{module_id}/items")
    
    def get_syllabus(self, course_id: str) -> Optional[CanvasItem]:
        """Get syllabus for a course"""
        try:
            # Get course details including syllabus
            course_details = self._make_request(f"courses/{course_id}", {"include[]": "syllabus_body"})
            
            if not course_details or "syllabus_body" not in course_details or not course_details["syllabus_body"]:
                logger.info(f"No syllabus found for course {course_id}")
                return None
            
            # Create a CanvasItem for the syllabus
            syllabus_item = CanvasItem(
                id=f"syllabus_{course_id}",
                type="syllabus",
                title=f"Syllabus for {course_details.get('name', 'Unknown Course')}",
                content=course_details.get("syllabus_body", ""),
                course_id=str(course_id),
                created_at=course_details.get("created_at", ""),
                updated_at=course_details.get("updated_at", ""),
                url=f"https://{self.domain}/courses/{course_id}/assignments/syllabus",
                metadata={"course_name": course_details.get("name", "Unknown Course")}
            )
            
            logger.info(f"Retrieved syllabus for course {course_id}")
            return syllabus_item
            
        except Exception as e:
            logger.error(f"Error retrieving syllabus for course {course_id}: {e}")
            return None
    
    def get_all_syllabi(self) -> List[CanvasItem]:
        """Get syllabi for all active courses"""
        syllabi = []
        # Only get syllabi for recent courses
        courses = self.get_courses(include_old_courses=False)
        
        for course in courses:
            course_id = course["id"]
            syllabus = self.get_syllabus(course_id)
            if syllabus:
                syllabi.append(syllabus)
        
        logger.info(f"Retrieved {len(syllabi)} syllabi from recent courses")
        return syllabi
    
    def search_by_keywords(self, keywords: List[str], query_text: str = "", time_frame: str = TimeFrame.RECENT_PAST) -> List[CanvasItem]:
        """
        Search Canvas for content matching keywords within a specified time frame
        
        Args:
            keywords: List of keywords to search for
            query_text: Original query text for context
            time_frame: Time frame to search within
        """
        results = []
        
        # Get date range based on time frame
        start_date, end_date = TimeFrame.get_date_range(time_frame)
        
        # Check if this is a query about upcoming work
        is_upcoming_query = query_text and any(phrase in query_text.lower() for phrase in 
                                              ["next assignment", "work on today", "due soon", 
                                               "upcoming", "this week", "next week", "calendar"])
        
        # Check if this is a query about syllabi
        is_syllabus_query = query_text and any(phrase in query_text.lower() for phrase in 
                                              ["syllabus", "course outline", "course schedule", 
                                               "course policy", "course policies", "course requirements"])
        
        # First, check if a specific course is mentioned in the keywords
        specific_course_keywords = []
        course_code_pattern = re.compile(r'([a-zA-Z]{2,6})\s*(\d{2,4}[a-zA-Z]*)', re.IGNORECASE)
        
        for keyword in keywords:
            match = course_code_pattern.search(keyword)
            if match:
                specific_course_keywords.append(keyword)
                logger.info(f"Detected specific course in keywords: {keyword}")
        
        # Get all courses (only recent courses)
        courses = self.get_courses(include_old_courses=False)
        
        # If specific course keywords were found, filter courses by those keywords
        filtered_courses = []
        if specific_course_keywords:
            for course in courses:
                course_name = course.get("name", "").lower()
                course_code = course.get("course_code", "").lower()
                
                # Check if any of the specific course keywords match this course
                if any(keyword.lower() in course_name or keyword.lower() in course_code for keyword in specific_course_keywords):
                    filtered_courses.append(course)
                    logger.info(f"Found matching course: {course.get('name')} for keywords {specific_course_keywords}")
            
            # If we found matching courses, use only those for the search
            if filtered_courses:
                logger.info(f"Filtered to {len(filtered_courses)} courses based on specific course keywords")
                courses = filtered_courses
        
        # If it's a syllabus query, prioritize getting syllabi from the filtered courses
        if is_syllabus_query:
            logger.info(f"Detected syllabus-related query, fetching syllabi from {len(courses)} courses")
            
            for course in courses:
                course_id = course["id"]
                syllabus = self.get_syllabus(course_id)
                
                if syllabus:
                    # Only add if it matches any remaining keywords (if any)
                    remaining_keywords = [k for k in keywords if k not in specific_course_keywords]
                    
                    # If there are no remaining keywords or if the syllabus matches them
                    if not remaining_keywords or any(keyword.lower() in (syllabus.title + " " + syllabus.content).lower() for keyword in remaining_keywords):
                        results.append(syllabus)
            
            logger.info(f"Found {len(results)} syllabi matching course and keyword criteria")
            
            # If we found syllabi, return them immediately
            if results:
                return results
        
        # If it's an upcoming assignments query, prioritize calendar events with time frame
        if is_upcoming_query or time_frame == TimeFrame.FUTURE:
            logger.info(f"Detected upcoming assignments query with time frame {time_frame}, fetching calendar events")
            calendar_items = self.get_upcoming_assignments(time_frame)
            
            # Filter by course first if we have specific course keywords
            if filtered_courses:
                course_ids = [str(course["id"]) for course in filtered_courses]
                calendar_items = [item for item in calendar_items if item.course_id in course_ids]
                logger.info(f"Filtered calendar items to {len(calendar_items)} items from specified courses")
            
            # Then filter by remaining keywords if needed
            remaining_keywords = [k for k in keywords if k not in specific_course_keywords]
            if remaining_keywords:
                filtered_items = []
                for cal_item in calendar_items:
                    content = f"{cal_item.title} {cal_item.content}"
                    if any(keyword.lower() in content.lower() for keyword in remaining_keywords):
                        filtered_items.append(cal_item)
                calendar_items = filtered_items
            
            results.extend(calendar_items)
            logger.info(f"Found {len(results)} calendar items matching course and keyword criteria")
            
            # If we found calendar items, return them immediately
            if results:
                return results
        
        # For other types of queries, search through the filtered courses
        for course in courses:
            course_id = course["id"]
            course_name = course["name"]
            
            # Search assignments
            assignments = self.get_assignments(course_id)
            for assignment in assignments:
                content = f"{assignment.get('name', '')} {assignment.get('description', '')}"
                
                # Check if the assignment matches remaining keywords
                remaining_keywords = [k for k in keywords if k not in specific_course_keywords]
                if not remaining_keywords or any(keyword.lower() in content.lower() for keyword in remaining_keywords):
                    # Apply time frame filtering
                    if assignment.get("due_at"):
                        try:
                            due_date_str = assignment.get("due_at").replace('Z', '+00:00')
                            due_date = datetime.fromisoformat(due_date_str)
                            
                            # Check if the assignment is within the time frame
                            if start_date and end_date:
                                if due_date < start_date or due_date > end_date:
                                    logger.debug(f"Skipping assignment outside time frame: {assignment.get('name', 'Untitled')}")
                                    continue
                            elif start_date and due_date < start_date:
                                logger.debug(f"Skipping assignment before start date: {assignment.get('name', 'Untitled')}")
                                continue
                            elif end_date and due_date > end_date:
                                logger.debug(f"Skipping assignment after end date: {assignment.get('name', 'Untitled')}")
                                continue
                                
                        except Exception as e:
                            logger.debug(f"Couldn't parse date for {assignment.get('name', 'Untitled')}: {e}")
                    
                    results.append(CanvasItem(
                        id=str(assignment["id"]),
                        type="assignment",
                        title=assignment.get("name", "Untitled Assignment"),
                        content=assignment.get("description", ""),
                        course_id=str(course_id),
                        created_at=assignment.get("created_at", ""),
                        updated_at=assignment.get("updated_at", ""),
                        due_date=assignment.get("due_at", ""),
                        url=assignment.get("html_url", ""),
                        metadata={"course_name": course_name}
                    ))
            
            # Only search announcements if not specifically looking for upcoming work or syllabi
            if not (is_upcoming_query or is_syllabus_query):
                # Search announcements with time frame filter
                announcements = self.get_announcements(course_id)
                for announcement in announcements:
                    content = f"{announcement.get('title', '')} {announcement.get('message', '')}"
                    
                    # Check if the announcement matches remaining keywords
                    remaining_keywords = [k for k in keywords if k not in specific_course_keywords]
                    if not remaining_keywords or any(keyword.lower() in content.lower() for keyword in remaining_keywords):
                        # Apply time frame filtering
                        if announcement.get("posted_at"):
                            try:
                                posted_at_str = announcement.get("posted_at").replace('Z', '+00:00')
                                posted_at = datetime.fromisoformat(posted_at_str)
                                
                                # Apply time frame filtering
                                if start_date and end_date:
                                    if posted_at < start_date or posted_at > end_date:
                                        logger.debug(f"Skipping announcement outside time frame: {announcement.get('title', 'Untitled')}")
                                        continue
                                elif start_date and posted_at < start_date:
                                    logger.debug(f"Skipping announcement before start date: {announcement.get('title', 'Untitled')}")
                                    continue
                                elif end_date and posted_at > end_date:
                                    logger.debug(f"Skipping announcement after end date: {announcement.get('title', 'Untitled')}")
                                    continue
                                    
                            except Exception as e:
                                logger.debug(f"Couldn't parse date for announcement {announcement.get('title', 'Untitled')}: {e}")
                        
                        results.append(CanvasItem(
                            id=str(announcement["id"]),
                            type="announcement",
                            title=announcement.get("title", "Untitled Announcement"),
                            content=announcement.get("message", ""),
                            course_id=str(course_id),
                            created_at=announcement.get("created_at", ""),
                            updated_at=announcement.get("updated_at", ""),
                            url=announcement.get("html_url", ""),
                            metadata={"course_name": course_name}
                        ))
        
        # If we still haven't found anything and it's a calendar query, try getting all upcoming assignments
        if not results and is_upcoming_query:
            calendar_items = self.get_upcoming_assignments(time_frame)
            
            # Filter by course if we have specific course keywords
            if filtered_courses:
                course_ids = [str(course["id"]) for course in filtered_courses]
                calendar_items = [item for item in calendar_items if item.course_id in course_ids]
                logger.info(f"Filtered fallback calendar items to {len(calendar_items)} items from specified courses")
            
            results.extend(calendar_items)
            logger.info(f"Added {len(calendar_items)} calendar items as fallback for upcoming query")
        
        logger.info(f"Found {len(results)} Canvas items matching keywords within time frame {time_frame}")
        return results

    def get_calendar_events_for_course(self, course_id, start_date=None, end_date=None, event_types=None):
        """Get calendar events for a specific course"""
        params = {
            "context_codes[]": f"course_{course_id}",
            "per_page": 100
        }
        
        # Add date range if provided
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        
        # Add event types if provided
        if event_types:
            params["type"] = event_types  # e.g., 'assignment', 'event', 'quiz'
        
        return self._make_request("calendar_events", params)

    def get_course_by_code(self, course_code: str) -> Optional[Dict]:
        """Find a course by its code."""
        logger.info(f"get_course_by_code called for code: {course_code}")
        
        try:
            # Get all courses
            courses = self.get_courses()
            if not courses:
                logger.warning("No courses found")
                return None
            
            # First try exact match on course code
            for course in courses:
                course_name = course.get("name", "").lower()
                if course_code.lower() in course_name:
                    logger.info(f"Found course by exact match: {course['name']}")
                    return course
            
            # Then try partial match on course code (handle cases like "311" matching "CMPSC 311")
            for course in courses:
                course_name = course.get("name", "").lower()
                # Extract just the number part
                matches = re.findall(r'\b(\d{3})\b', course_code)
                if matches and any(match in course_name for match in matches):
                    logger.info(f"Found course by partial match: {course['name']}")
                    return course
                
            # Try matching on course name
            course_code_lower = course_code.lower()
            for course in courses:
                course_name = course.get("name", "").lower()
                if course_code_lower in course_name:
                    logger.info(f"Found course by name match: {course['name']}")
                    return course
            
            logger.warning(f"No course found for code {course_code}")
            return None
        except Exception as e:
            logger.error(f"Error in get_course_by_code: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def get_syllabus_for_course_code(self, course_code: str) -> Optional[CanvasItem]:
        """Get the syllabus for a specific course by code."""
        logger.info(f"get_syllabus_for_course_code called for code: {course_code}")
        
        try:
            # Find the course first
            course = self.get_course_by_code(course_code)
            if not course:
                logger.warning(f"No course found for code {course_code}")
                return None
            
            course_id = str(course["id"])
            course_name = course["name"]
            logger.info(f"Found course: {course_name} (ID: {course_id})")
            
            # Get the syllabus for this course
            syllabus = self.get_syllabus(course_id)
            if syllabus:
                logger.info(f"Retrieved syllabus for course {course_name}")
                return syllabus
            else:
                logger.warning(f"No syllabus found for course {course_name}")
                return None
        except Exception as e:
            logger.error(f"Error in get_syllabus_for_course_code: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def get_assignments_for_course_code(self, course_code: str) -> List[CanvasItem]:
        """
        Get assignments for a specific course by course code
        
        Args:
            course_code: The course identifier to search for (e.g., 'CMPSC 311', '311', 'systems programming')
            
        Returns:
            List of CanvasItem objects for assignments
        """
        course = self.get_course_by_code(course_code)
        if not course:
            logger.info(f"No course found matching '{course_code}' for assignments")
            return []
            
        course_id = course["id"]
        course_name = course.get("name", "Unknown Course")
        
        assignments = self.get_assignments(course_id)
        canvas_items = []
        
        for assignment in assignments:
            canvas_items.append(CanvasItem(
                id=str(assignment["id"]),
                type="assignment",
                title=assignment.get("name", "Untitled Assignment"),
                content=assignment.get("description", ""),
                course_id=str(course_id),
                created_at=assignment.get("created_at", ""),
                updated_at=assignment.get("updated_at", ""),
                due_date=assignment.get("due_at", ""),
                url=assignment.get("html_url", ""),
                metadata={"course_name": course_name}
            ))
        
        logger.info(f"Retrieved {len(canvas_items)} assignments for course '{course_name}'")
        return canvas_items
    
    def get_files_for_course_code(self, course_code: str) -> List[CanvasItem]:
        """
        Get files for a specific course by course code
        
        Args:
            course_code: The course identifier to search for (e.g., 'CMPSC 311', '311', 'systems programming')
            
        Returns:
            List of CanvasItem objects for files
        """
        course = self.get_course_by_code(course_code)
        if not course:
            logger.info(f"No course found matching '{course_code}' for files")
            return []
            
        course_id = course["id"]
        course_name = course.get("name", "Unknown Course")
        
        files = self.get_files(course_id)
        canvas_items = []
        
        for file in files:
            canvas_items.append(CanvasItem(
                id=str(file["id"]),
                type="file",
                title=file.get("display_name", "Untitled File"),
                content=f"File: {file.get('display_name', '')}\nSize: {file.get('size', 0)} bytes\nType: {file.get('content-type', 'unknown')}",
                course_id=str(course_id),
                created_at=file.get("created_at", ""),
                updated_at=file.get("updated_at", ""),
                url=file.get("url", ""),
                metadata={"course_name": course_name, "mime_type": file.get("content-type", "")}
            ))
        
        logger.info(f"Retrieved {len(canvas_items)} files for course '{course_name}'")
        return canvas_items
    
    def get_announcements_for_course_code(self, course_code: str) -> List[CanvasItem]:
        """
        Get announcements for a specific course by course code
        
        Args:
            course_code: The course identifier to search for (e.g., 'CMPSC 311', '311', 'systems programming')
            
        Returns:
            List of CanvasItem objects for announcements
        """
        course = self.get_course_by_code(course_code)
        if not course:
            logger.info(f"No course found matching '{course_code}' for announcements")
            return []
            
        course_id = course["id"]
        course_name = course.get("name", "Unknown Course")
        
        announcements = self.get_announcements(course_id)
        canvas_items = []
        
        for announcement in announcements:
            canvas_items.append(CanvasItem(
                id=str(announcement["id"]),
                type="announcement",
                title=announcement.get("title", "Untitled Announcement"),
                content=announcement.get("message", ""),
                course_id=str(course_id),
                created_at=announcement.get("created_at", ""),
                updated_at=announcement.get("updated_at", ""),
                url=announcement.get("html_url", ""),
                metadata={"course_name": course_name}
            ))
        
        logger.info(f"Retrieved {len(canvas_items)} announcements for course '{course_name}'")
        return canvas_items
    
    def get_modules_for_course_code(self, course_code: str) -> List[CanvasItem]:
        """
        Get modules for a specific course by course code
        
        Args:
            course_code: The course identifier to search for (e.g., 'CMPSC 311', '311', 'systems programming')
            
        Returns:
            List of CanvasItem objects for modules
        """
        course = self.get_course_by_code(course_code)
        if not course:
            logger.info(f"No course found matching '{course_code}' for modules")
            return []
            
        course_id = course["id"]
        course_name = course.get("name", "Unknown Course")
        
        modules = self.get_modules(course_id)
        canvas_items = []
        
        for module in modules:
            # Get module items
            module_items = self.get_module_items(course_id, module["id"])
            items_content = "\n".join([f"- {item.get('title', 'Untitled Item')}" for item in module_items])
            
            canvas_items.append(CanvasItem(
                id=str(module["id"]),
                type="module",
                title=module.get("name", "Untitled Module"),
                content=f"Module: {module.get('name', '')}\n\nItems:\n{items_content}",
                course_id=str(course_id),
                created_at="",  # Modules don't have created_at
                updated_at="",  # Modules don't have updated_at
                url=f"https://{self.domain}/courses/{course_id}/modules/{module['id']}",
                metadata={"course_name": course_name, "items_count": len(module_items)}
            ))
        
        logger.info(f"Retrieved {len(canvas_items)} modules for course '{course_name}'")
        return canvas_items
    
    def get_calendar_events_for_course_code(self, course_code: str, start_date=None, end_date=None) -> List[CanvasItem]:
        """
        Get calendar events for a specific course by course code
        
        Args:
            course_code: The course identifier to search for (e.g., 'CMPSC 311', '311', 'systems programming')
            start_date: Start date for filtering events
            end_date: End date for filtering events
            
        Returns:
            List of CanvasItem objects for calendar events
        """
        course = self.get_course_by_code(course_code)
        if not course:
            logger.info(f"No course found matching '{course_code}' for calendar events")
            return []
            
        course_id = course["id"]
        course_name = course.get("name", "Unknown Course")
        
        events = self.get_calendar_events_for_course(course_id, start_date, end_date)
        canvas_items = []
        
        for event in events:
            canvas_items.append(CanvasItem(
                id=str(event["id"]),
                type="calendar_event",
                title=event.get("title", "Untitled Event"),
                content=event.get("description", ""),
                course_id=str(course_id),
                created_at=event.get("created_at", ""),
                updated_at=event.get("updated_at", ""),
                due_date=event.get("start_at", ""),  # Calendar events use start_at for due date
                url=event.get("html_url", ""),
                metadata={"course_name": course_name, "end_at": event.get("end_at", "")}
            ))
        
        logger.info(f"Retrieved {len(canvas_items)} calendar events for course '{course_name}'")
        return canvas_items 