#!/usr/bin/env python3
"""
Canvas Copilot Module
--------------------
Main class that integrates all components of the Canvas Copilot system.

This module provides the central orchestration logic for the Canvas Copilot application,
integrating various components to process user queries about Canvas LMS data and generate
relevant responses. Key functionality includes:

1. Initializing the system by fetching data from Canvas API
2. Processing user queries through categorization, keyword extraction, and time frame detection
3. Retrieving relevant information from Canvas based on query analysis
4. Managing a vector database for efficient context retrieval
5. Generating natural language responses using LLM
6. Maintaining conversation context for multi-turn interactions

The CanvasCopilot class serves as the main entry point for the application, handling
the end-to-end pipeline from query input to response generation.
"""

import os
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from dotenv import load_dotenv

# Import from other modules
from canvas_api import CanvasAPI, CanvasItem, TimeFrame
from categorization import KeywordExtractor, QueryClassifier, QueryCategory, TimeFrameDetector
from vectordatabase import VectorDatabase

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger("canvas_copilot")

# Constants
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


class CanvasCopilot:
    """
    Main pipeline for Canvas Copilot.
    
    This class orchestrates the end-to-end process of handling user queries about Canvas LMS,
    from initial query processing through data retrieval and response generation. It maintains
    conversation context across multiple interactions and optimizes retrieval based on query
    categorization and time frame analysis.
    """
    
    def __init__(self, max_db_items=50):
        """
        Initialize the Canvas Copilot system.
        
        Args:
            max_db_items (int, optional): Maximum number of items to store in the vector database.
                                         Defaults to 50.
        """
        self.keyword_extractor = KeywordExtractor()
        self.canvas_api = CanvasAPI()
        self.vector_db = VectorDatabase(max_items=max_db_items)
        self.query_classifier = QueryClassifier()
        self.time_frame_detector = TimeFrameDetector()
        self.initialized = False
        # Add a class-level logger reference to avoid "no attribute 'logger'" errors
        self.logger = logger
        # Add conversation context tracking
        self.conversation_context = {
            "last_course_code": None,
            "last_course_name": None,
            "last_category": None,
            "last_query": None
        }
        logger.info("CanvasCopilot initialized with logger")
    
    def initialize(self) -> None:
        """
        Initialize the pipeline by fetching and indexing Canvas data.
        
        This method retrieves course data from Canvas, including assignments, announcements,
        and other relevant items, and stores them in the vector database for efficient retrieval.
        It only performs initialization if not already done, and can use cached data from a
        previous run if available.
        """
        if self.initialized:
            return
        
        logger.info("Initializing Canvas Copilot...")
        
        # Check if we already have data
        if self.vector_db.items:
            logger.info(f"Using {len(self.vector_db.items)} existing items from persistence cache")
            self.initialized = True
            return
            
        # Get active courses only (excluding courses older than 4 months)
        courses = self.canvas_api.get_courses(include_old_courses=False)
        
        # For each course, get assignments, announcements, etc.
        canvas_items = []
        
        # Track the number of items to keep within limits
        item_count = 0
        max_items_per_course = min(10, self.vector_db.max_items // max(1, len(courses)))
        
        for course in courses:
            course_id = course["id"]
            course_name = course["name"]
            course_items = []
            
            # Get assignments - these are higher priority
            assignments = self.canvas_api.get_assignments(course_id)
            for assignment in assignments:
                due_date = assignment.get("due_at", "")
                # Parse the due date for comparison
                is_future = False
                if due_date:
                    try:
                        due_datetime = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                        now = datetime.now(due_datetime.tzinfo)
                        is_future = due_datetime > now
                    except (ValueError, AttributeError):
                        pass
                
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
                    metadata={"course_name": course_name, "is_future": is_future}
                ))
            
            # Only add announcements if we haven't reached the limit per course
            if len(course_items) < max_items_per_course:
                # Get only recent announcements
                announcements = self.canvas_api.get_announcements(course_id)
                # Sort by posted date (most recent first), safely handling None values
                try:
                    # First try to sort with a default for None values
                    announcements.sort(
                        key=lambda x: x.get("posted_at", "") or "", 
                        reverse=True
                    )
                except TypeError:
                    # If that fails, just use the announcements as they are
                    logger.warning("Could not sort announcements by date, using default order")
                
                # Take only the most recent ones
                for announcement in announcements[:max_items_per_course - len(course_items)]:
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
        
        # Sort all items by priority (future assignments first, then recent items)
        try:
            canvas_items.sort(key=lambda x: (
                1 if (x.type == 'assignment' and x.metadata and x.metadata.get('is_future', False)) else 0,
                x.updated_at if x.updated_at else ''
            ), reverse=True)
        except TypeError:
            logger.warning("Could not sort canvas items by priority, using default order")
        
        # Add items to vector database (VectorDatabase will handle the max_items limit)
        self.vector_db.add_items(canvas_items)
        
        logger.info(f"Initialized Canvas Copilot with {len(self.vector_db.items)} items")
        self.initialized = True
    
    def process_query(self, query):
        """Process a query from the user and return a response."""
        try:
            # Log the current date when processing a query
            current_date = datetime.now(timezone.utc)
            logger.info(f"Processing query at current date: {current_date.isoformat()}")
            
            # Check vector database size - make sure to access the items property
            if hasattr(self.vector_db, 'items'):
                logger.info(f"Vector database contains {len(self.vector_db.items)} items")
            else:
                logger.info("Vector database is initialized")
            
            # Make sure we're initialized
            if not hasattr(self, 'initialized') or not self.initialized:
                self.initialize()
            
            # Extract keywords and time frame from the query
            keywords, time_frame = self.keyword_extractor.extract_keywords_and_timeframe(query)
            logger.info(f"Extracted keywords: {keywords}, time frame: {time_frame}")
            
            # Check if this is a follow-up question without explicit course mention
            is_followup = self._check_if_followup(query, keywords)
            
            # If this is a follow-up and we have a previous course context, add it to keywords
            if is_followup and self.conversation_context["last_course_code"]:
                logger.info(f"Detected follow-up question. Adding previous course context: {self.conversation_context['last_course_code']}")
                if self.conversation_context["last_course_code"] not in keywords:
                    keywords.append(self.conversation_context["last_course_code"])
            
            # Classify the query into a category
            try:
                category = self.query_classifier.classify(query, keywords)
                logger.info(f"Query classified as category: {category}")
            except Exception as e:
                logger.error(f"Error classifying query: {e}")
                logger.error(f"QueryCategory dir: {dir(QueryCategory)}")
                logger.error(f"QueryCategory vars: {vars(QueryCategory)}")
                category = QueryCategory.GENERAL
                logger.info(f"Defaulting to GENERAL category due to classification error")
            
            # If time frame wasn't detected during keyword extraction, detect it now
            if not time_frame:
                time_frame = self.time_frame_detector.detect_time_frame(query, category)
                logger.info(f"Detected time frame: {time_frame}")
            
            # Add category-specific keywords to enhance search
            try:
                additional_keywords = self.query_classifier.get_additional_keywords(category)
                for keyword in additional_keywords:
                    if keyword not in keywords:
                        keywords.append(keyword)
                logger.info(f"Enhanced keywords with category-specific terms: {keywords}")
            except Exception as e:
                logger.error(f"Error getting additional keywords: {e}")
                logger.info("Continuing with original keywords")
            
            # Get data based on query category and time frame
            try:
                logger.info("Calling _get_category_specific_data...")
                canvas_items = self._get_category_specific_data(category, keywords, time_frame, query)
                logger.info(f"Retrieved {len(canvas_items)} Canvas items for category: {category}, time frame: {time_frame}")
            except Exception as e:
                logger.error(f"Error getting category-specific data: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                canvas_items = []
                logger.info("No canvas items retrieved due to error")
            
            # Handle empty results with fallback strategies
            if not canvas_items:
                try:
                    logger.info("Using fallback search strategy...")
                    canvas_items = self._fallback_search(query, keywords, category, time_frame)
                    logger.info(f"Fallback search returned {len(canvas_items)} Canvas items")
                except Exception as e:
                    logger.error(f"Error in fallback search: {e}")
                    canvas_items = []
                    logger.info("No canvas items retrieved from fallback search")
            
            # Get context for the query
            try:
                context = self._get_context(query, canvas_items)
                logger.info(f"Generated context with length {len(context)}")
            except Exception as e:
                logger.error(f"Error getting context: {e}")
                context = "Error retrieving context information."
            
            # Generate the response with the context and any future assignments (if applicable)
            try:
                future_assignments = self._get_future_assignments(canvas_items, category)
                logger.info(f"Found {len(future_assignments)} future assignments")
                logger.info("Calling _generate_response...")
                response = self._generate_response(query, context, future_assignments, category, time_frame)
                logger.info("Response generated successfully")
            except Exception as e:
                logger.error(f"Error generating response: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                response = f"I apologize, but I encountered an error while generating a response: {str(e)}"
            
            return response
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return f"I apologize, but I encountered an error while processing your query: {str(e)}"
    
    def _get_category_specific_data(self, category: str, keywords: List[str], time_frame: str, query: str) -> List[CanvasItem]:
        """
        Get data specific to a query category
        
        Args:
            category: The query category
            keywords: List of keywords for filtering
            time_frame: The time frame for the query
            query: The original query text
            
        Returns:
            List of CanvasItems relevant to the query
        """
        canvas_items = []
        logger.info(f"_get_category_specific_data: Starting for category={category}, keywords={keywords}")
        
        # Check if this is an office hours query
        is_office_hours_query = "office hours" in query.lower() or "office hour" in query.lower()
        
        # Extract course identifiers from keywords and query
        try:
            course_identifiers = self._extract_course_identifiers(keywords, query)
            logger.info(f"Extracted course identifiers: {course_identifiers}")
            
            # If this is an office hours query and we have a last course context but no course identifiers,
            # use the last course context
            if is_office_hours_query and not course_identifiers and self.conversation_context["last_course_code"]:
                course_identifiers = [self.conversation_context["last_course_code"]]
                logger.info(f"Office hours query: Using last course context: {course_identifiers}")
        except Exception as e:
            logger.error(f"Error extracting course identifiers: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            course_identifiers = []
        
        # If we have specific course identifiers, prioritize those for all categories
        if course_identifiers:
            logger.info(f"Prioritizing retrieval for specific courses: {course_identifiers}")
            
            # Try each course identifier until we find a match
            for course_id in course_identifiers:
                # Store the current course in conversation context
                self.conversation_context["last_course_code"] = course_id
                
                # For syllabus queries with specific course identifiers
                if category == QueryCategory.SYLLABUS:
                    try:
                        logger.info(f"Attempting to get syllabus for course {course_id}")
                        syllabus = self.canvas_api.get_syllabus_for_course_code(course_id)
                        if syllabus:
                            canvas_items.append(syllabus)
                            logger.info(f"Retrieved syllabus for course {course_id}")
                            
                            # If this is a syllabus query, also check for office hours information
                            if is_office_hours_query:
                                logger.info(f"Office hours query detected, checking syllabus content for office hours")
                                # The syllabus is already included, so we don't need to do anything else here
                    except Exception as e:
                        logger.error(f"Error getting syllabus for course {course_id}: {e}")
                
                # For assignment queries with specific course identifiers
                elif category == QueryCategory.ASSIGNMENTS:
                    try:
                        logger.info(f"Attempting to get assignments for course {course_id}")
                        assignments = self.canvas_api.get_assignments_for_course_code(course_id)
                        if assignments:
                            canvas_items.extend(assignments)
                            logger.info(f"Retrieved {len(assignments)} assignments for course {course_id}")
                    except Exception as e:
                        logger.error(f"Error getting assignments for course {course_id}: {e}")
                
                # For file queries with specific course identifiers
                elif category == QueryCategory.FILES:
                    try:
                        logger.info(f"Attempting to get files for course {course_id}")
                        files = self.canvas_api.get_files_for_course_code(course_id)
                        if files:
                            canvas_items.extend(files)
                            logger.info(f"Retrieved {len(files)} files for course {course_id}")
                    except Exception as e:
                        logger.error(f"Error getting files for course {course_id}: {e}")
                
                # For announcement queries with specific course identifiers
                elif category == QueryCategory.ANNOUNCEMENTS:
                    try:
                        logger.info(f"Attempting to get announcements for course {course_id}")
                        announcements = self.canvas_api.get_announcements_for_course_code(course_id)
                        if announcements:
                            canvas_items.extend(announcements)
                            logger.info(f"Retrieved {len(announcements)} announcements for course {course_id}")
                    except Exception as e:
                        logger.error(f"Error getting announcements for course {course_id}: {e}")
                
                # For course content queries with specific course identifiers
                elif category == QueryCategory.COURSE_CONTENT:
                    try:
                        logger.info(f"Attempting to get modules for course {course_id}")
                        modules = self.canvas_api.get_modules_for_course_code(course_id)
                        if modules:
                            canvas_items.extend(modules)
                            logger.info(f"Retrieved {len(modules)} modules for course {course_id}")
                    except Exception as e:
                        logger.error(f"Error getting modules for course {course_id}: {e}")
                
                # For calendar event queries with specific course identifiers
                elif category == QueryCategory.CALENDAR_EVENTS:
                    try:
                        # Get date range based on time frame
                        start_date, end_date = TimeFrame.get_date_range(time_frame)
                        start_date_str = start_date.isoformat() if start_date else None
                        end_date_str = end_date.isoformat() if end_date else None
                        
                        logger.info(f"Attempting to get calendar events for course {course_id}")
                        events = self.canvas_api.get_calendar_events_for_course_code(
                            course_id, start_date_str, end_date_str
                        )
                        if events:
                            canvas_items.extend(events)
                            logger.info(f"Retrieved {len(events)} calendar events for course {course_id}")
                    except Exception as e:
                        logger.error(f"Error getting calendar events for course {course_id}: {e}")
                
                # For events queries (exams, office hours, lectures) with specific course identifiers
                elif category == QueryCategory.EVENTS:
                    try:
                        # First, get the syllabus which often contains exam and office hours info
                        logger.info(f"Attempting to get syllabus for course {course_id} for events info")
                        syllabus = self.canvas_api.get_syllabus_for_course_code(course_id)
                        if syllabus:
                            canvas_items.append(syllabus)
                            logger.info(f"Retrieved syllabus for course {course_id} for events info")
                        
                        # Then, get announcements which might contain updated event information
                        logger.info(f"Attempting to get announcements for course {course_id} for events info")
                        announcements = self.canvas_api.get_announcements_for_course_code(course_id)
                        if announcements:
                            canvas_items.extend(announcements)
                            logger.info(f"Retrieved {len(announcements)} announcements for course {course_id} for events info")
                    except Exception as e:
                        logger.error(f"Error getting events information for course {course_id}: {e}")
                
                # For other categories, use the search_by_keywords method
                else:
                    logger.info(f"No specific course data retrieval for category: {category}")
                    # We'll let the search_by_keywords method handle the filtering
                    # as we've already improved it to prioritize course filtering
                    pass
                
                # If we found items for this course identifier, stop trying others
                if canvas_items:
                    logger.info(f"Found {len(canvas_items)} items for course {course_id}, stopping further course search")
                    break
        
        # If we found course-specific items, filter them by other keywords if needed
        if canvas_items and keywords:
            try:
                # Get non-course keywords
                non_course_keywords = [k for k in keywords if k.lower() not in [c.lower() for c in course_identifiers]]
                
                if non_course_keywords:
                    logger.info(f"Filtering course-specific items by additional keywords: {non_course_keywords}")
                    filtered_items = []
                    
                    for item in canvas_items:
                        content = f"{item.title} {item.content}"
                        if any(keyword.lower() in content.lower() for keyword in non_course_keywords):
                            filtered_items.append(item)
                    
                    if filtered_items:
                        logger.info(f"Filtered to {len(filtered_items)} items matching additional keywords")
                        canvas_items = filtered_items
            except Exception as e:
                logger.error(f"Error filtering by non-course keywords: {e}")
        
        # If we didn't find specific course data or for other categories, proceed with normal retrieval
        if not canvas_items:
            logger.info("No course-specific items found, proceeding with general category search")
            if category == QueryCategory.SYLLABUS:
                try:
                    # Get all syllabi
                    logger.info("Retrieving all syllabi")
                    canvas_items = self.canvas_api.get_all_syllabi()
                    logger.info(f"Retrieved {len(canvas_items)} syllabi")
                    
                    # Filter by keywords if we have any
                    if keywords:
                        filtered_items = []
                        for item in canvas_items:
                            content = f"{item.title} {item.content}"
                            if any(keyword.lower() in content.lower() for keyword in keywords):
                                filtered_items.append(item)
                        canvas_items = filtered_items
                        logger.info(f"Filtered to {len(canvas_items)} syllabi matching keywords")
                except Exception as e:
                    logger.error(f"Error retrieving syllabi: {e}")
                    
            elif category == QueryCategory.ASSIGNMENTS:
                try:
                    # Check if this is a "next assignment" type of query
                    is_next_assignment_query = any(phrase in query.lower() for phrase in 
                                                ["next assignment", "upcoming assignment", "due soon", "next assignemnt"])
                    
                    if is_next_assignment_query:
                        logger.info(f"Detected 'next assignment' query, including all upcoming assignments")
                        # For "next assignment" queries, get all upcoming assignments without filtering by keywords
                        upcoming_assignments = self.canvas_api.get_upcoming_assignments(time_frame)
                        
                        # Log all retrieved assignments for debugging
                        logger.info(f"Retrieved {len(upcoming_assignments)} upcoming assignments")
                        for item in upcoming_assignments:
                            logger.info(f"Upcoming assignment: {item.title}, due: {item.due_date}")
                        
                        # Add all upcoming assignments to the results
                        canvas_items.extend(upcoming_assignments)
                    else:
                        # For other assignment queries, use keyword search
                        logger.info(f"Regular assignment query, using keyword search")
                        canvas_items = self.canvas_api.search_by_keywords(keywords, query, time_frame)
                except Exception as e:
                    logger.error(f"Error retrieving assignments: {e}")
                    
            elif category == QueryCategory.ANNOUNCEMENTS:
                try:
                    # Get announcements matching keywords
                    logger.info("Retrieving announcements")
                    canvas_items = self.canvas_api.search_by_keywords(keywords, query, time_frame)
                except Exception as e:
                    logger.error(f"Error retrieving announcements: {e}")
                
            elif category == QueryCategory.CALENDAR_EVENTS:
                try:
                    # Get calendar events
                    logger.info("Retrieving calendar events")
                    canvas_items = self.canvas_api.get_upcoming_assignments(time_frame)
                    
                    # Filter by keywords if we have any
                    if keywords:
                        filtered_items = []
                        for item in canvas_items:
                            content = f"{item.title} {item.content}"
                            if any(keyword.lower() in content.lower() for keyword in keywords):
                                filtered_items.append(item)
                        canvas_items = filtered_items
                except Exception as e:
                    logger.error(f"Error retrieving calendar events: {e}")
                    
            elif category == QueryCategory.COURSE_CONTENT:
                try:
                    # Get course content matching keywords
                    logger.info("Retrieving course content")
                    canvas_items = self.canvas_api.search_by_keywords(keywords, query, time_frame)
                except Exception as e:
                    logger.error(f"Error retrieving course content: {e}")
                
            elif category == QueryCategory.FILES:
                try:
                    # Get files matching keywords
                    logger.info("Retrieving files")
                    canvas_items = self.canvas_api.search_by_keywords(keywords, query, time_frame)
                except Exception as e:
                    logger.error(f"Error retrieving files: {e}")
                
            elif category == QueryCategory.GRADES:
                try:
                    # Get grades matching keywords
                    logger.info("Retrieving grades")
                    canvas_items = self.canvas_api.search_by_keywords(keywords, query, time_frame)
                except Exception as e:
                    logger.error(f"Error retrieving grades: {e}")
                
            elif category == QueryCategory.EVENTS:
                try:
                    # For events, we need to look at both syllabi and announcements
                    logger.info("Retrieving events information from syllabi and announcements")
                    
                    # First, get all syllabi which often contain exam and office hours info
                    syllabi = self.canvas_api.get_all_syllabi()
                    logger.info(f"Retrieved {len(syllabi)} syllabi for events information")
                    
                    # Filter syllabi by keywords
                    filtered_syllabi = []
                    for item in syllabi:
                        content = f"{item.title} {item.content}"
                        if any(keyword.lower() in content.lower() for keyword in keywords):
                            filtered_syllabi.append(item)
                    
                    logger.info(f"Filtered to {len(filtered_syllabi)} syllabi matching event keywords")
                    canvas_items.extend(filtered_syllabi)
                    
                    # Then, get announcements which might contain updated event information
                    # Use a broader time frame for announcements to catch all relevant ones
                    announcement_time_frame = TimeFrame.EXTENDED_PAST
                    announcements = self.canvas_api.search_by_keywords(keywords, query, announcement_time_frame)
                    
                    # Filter to only include announcements
                    announcement_items = [item for item in announcements if item.type == "announcement"]
                    logger.info(f"Retrieved {len(announcement_items)} announcements for events information")
                    
                    canvas_items.extend(announcement_items)
                except Exception as e:
                    logger.error(f"Error retrieving events information: {e}")
                
            else:  # General category or fallback
                try:
                    # Get any content matching keywords
                    logger.info("Using general keyword search")
                    canvas_items = self.canvas_api.search_by_keywords(keywords, query, time_frame)
                except Exception as e:
                    logger.error(f"Error with general keyword search: {e}")
        
        logger.info(f"Retrieved {len(canvas_items)} Canvas items for category: {category}, time frame: {time_frame}")
        
        # For future assignments, also log how many are in the future
        if time_frame == TimeFrame.FUTURE:
            future_assignments = []
            now = datetime.now(timezone.utc)
            
            for item in canvas_items:
                if item.due_date:
                    try:
                        due_date_str = item.due_date.replace('Z', '+00:00')
                        due_date = datetime.fromisoformat(due_date_str)
                        if due_date > now:
                            future_assignments.append(item)
                    except Exception as e:
                        logger.debug(f"Couldn't parse due date for {item.title}: {e}")
            
            logger.info(f"Found {len(future_assignments)} future assignments")
        
        return canvas_items
    
    def _extract_course_identifiers(self, keywords: List[str], query: str) -> List[str]:
        """
        Extract course identifiers from keywords and query
        
        Args:
            keywords: List of keywords
            query: Original query text
            
        Returns:
            List of potential course identifiers
        """
        course_identifiers = []
        logger.info(f"Extracting course identifiers from keywords {keywords} and query: {query}")
        
        # Pattern for course codes like "CMPSC 311"
        course_code_pattern = re.compile(r'([a-zA-Z]{2,6})\s*(\d{2,4}[a-zA-Z]*)', re.IGNORECASE)
        
        # Pattern for just course numbers like "311"
        course_number_pattern = re.compile(r'\b(\d{3})\b')
        
        # Extract course codes from keywords
        for keyword in keywords:
            match = course_code_pattern.search(keyword)
            if match:
                course_code = match.group(0)
                course_identifiers.append(course_code)
                logger.info(f"Detected course code in keywords: {course_code}")
                
                # Update conversation context with the course code
                self.conversation_context["last_course_code"] = course_code
        
        # Extract course codes from query
        for match in course_code_pattern.finditer(query):
            course_code = match.group(0)
            if course_code not in course_identifiers:
                course_identifiers.append(course_code)
                logger.info(f"Detected course code in query: {course_code}")
                
                # Update conversation context with the course code
                self.conversation_context["last_course_code"] = course_code
        
        # Extract just course numbers if no full course codes were found
        if not course_identifiers:
            # From keywords
            for keyword in keywords:
                match = course_number_pattern.search(keyword)
                if match:
                    course_number = match.group(0)
                    course_identifiers.append(course_number)
                    logger.info(f"Detected course number in keywords: {course_number}")
                    
                    # Update conversation context with the course number
                    self.conversation_context["last_course_code"] = course_number
            
            # From query
            for match in course_number_pattern.finditer(query):
                course_number = match.group(0)
                if course_number not in course_identifiers:
                    course_identifiers.append(course_number)
                    logger.info(f"Detected course number in query: {course_number}")
                    
                    # Update conversation context with the course number
                    self.conversation_context["last_course_code"] = course_number
        
        # Check for descriptive course names
        descriptive_names = [
            "systems programming",
            "intro to systems",
            "system programming",
            "data structures",
            "algorithms",
            "computer science",
            "programming",
            "software engineering",
            "database",
            "operating systems",
            "networks",
            "artificial intelligence",
            "machine learning"
        ]
        
        query_lower = query.lower()
        for name in descriptive_names:
            if name in query_lower and name not in course_identifiers:
                course_identifiers.append(name)
                logger.info(f"Detected descriptive course name in query: {name}")
        
        return course_identifiers
    
    def _fallback_search(self, query: str, keywords: List[str], category: str, time_frame: str = TimeFrame.RECENT_PAST) -> List[CanvasItem]:
        """
        Fallback search strategy when category-specific search returns no results
        
        Args:
            query: Original query text
            keywords: Extracted keywords
            category: Query category
            time_frame: Time frame to search within
        """
        canvas_items = []
        
        # First try vector search
        search_results = self.vector_db.search(query)
        canvas_items = [item for item, _ in search_results]
        
        # Apply time frame filtering to vector search results
        if canvas_items:
            start_date, end_date = TimeFrame.get_date_range(time_frame)
            
            if start_date or end_date:
                filtered_items = []
                for item in canvas_items:
                    # Only apply filtering to types with relevant dates
                    if item.type in ['assignment', 'announcement'] and hasattr(item, 'due_date') and item.due_date:
                        try:
                            item_date_str = item.due_date.replace('Z', '+00:00')
                            item_date = datetime.fromisoformat(item_date_str)
                            
                            # Check time frame
                            if start_date and end_date:
                                if start_date <= item_date <= end_date:
                                    filtered_items.append(item)
                            elif start_date and item_date >= start_date:
                                filtered_items.append(item)
                            elif end_date and item_date <= end_date:
                                filtered_items.append(item)
                        except Exception:
                            # If we can't parse the date, include the item
                            filtered_items.append(item)
                    else:
                        # Include items without date fields
                        filtered_items.append(item)
                
                canvas_items = filtered_items
        
        # If still no results, try broader keyword search with time frame
        if not canvas_items:
            # Use a broader search with time frame
            for keyword in keywords:
                items = self.canvas_api.search_by_keywords([keyword], "", time_frame)
                canvas_items.extend(items)
        
        return canvas_items
    
    def _get_future_assignments(self, canvas_items: List[CanvasItem], category: str) -> List[CanvasItem]:
        """Extract future assignments from canvas items or fetch them if needed."""
        future_assignments = []
        
        # For assignments category with FUTURE time frame, we're already focused on future assignments
        if category == QueryCategory.ASSIGNMENTS:
            # Filter for those that are in the future
            assignment_items = [item for item in canvas_items if 
                              (item.type == 'assignment' or item.type == 'quiz') and 
                              hasattr(item, 'due_date') and 
                              item.due_date]
            
            # Find which ones are in the future but within 3 weeks
            now = datetime.now(timezone.utc)
            max_date = now + timedelta(days=21)
            
            for item in assignment_items:
                try:
                    due_date_str = item.due_date.replace('Z', '+00:00')
                    due_date = datetime.fromisoformat(due_date_str)
                    if due_date > now:
                        future_assignments.append(item)
                        logger.info(f"Added future assignment: {item.title}, due: {item.due_date}")
                except Exception as e:
                    logger.error(f"Error parsing date for {item.title}: {e}")
        else:
            # Filter for assignment items with due dates in the future
            assignment_items = [item for item in canvas_items if 
                              (item.type == 'assignment' or item.type == 'quiz') and 
                              hasattr(item, 'due_date') and 
                              item.due_date]
            
            # Find which ones are in the future but within 3 weeks
            now = datetime.now(timezone.utc)
            max_date = now + timedelta(days=21)
            
            for item in assignment_items:
                try:
                    due_date_str = item.due_date.replace('Z', '+00:00')
                    due_date = datetime.fromisoformat(due_date_str)
                    if due_date > now:
                        future_assignments.append(item)
                        logger.info(f"Added future assignment: {item.title}, due: {item.due_date}")
                except Exception as e:
                    logger.error(f"Error parsing date for {item.title}: {e}")
        
        return future_assignments

    def _format_context(self, items: List[CanvasItem]) -> str:
        """Format Canvas items into context for LLM"""
        if not items:
            return "No relevant Canvas information found."
        
        context_parts = ["Here is the relevant information from your Canvas courses:"]
        
        for i, item in enumerate(items):
            context_parts.append(f"\n--- Item {i+1}: {item.title} ({item.type}) ---")
            if item.metadata and "course_name" in item.metadata:
                context_parts.append(f"Course: {item.metadata['course_name']}")
            context_parts.append(f"Last Updated: {item.updated_at}")
            if item.due_date:
                context_parts.append(f"Due Date: {item.due_date}")
            context_parts.append(f"\nContent:\n{item.content}")
        
        return "\n".join(context_parts)
    
    def _generate_response(self, query, context, future_assignments=None, category: str = QueryCategory.GENERAL, time_frame: str = TimeFrame.RECENT_PAST):
        """
        Generate a response from the LLM based on the query, retrieved context, category, and time frame
        
        Args:
            query: Original query text
            context: Retrieved context information
            future_assignments: List of future assignments
            category: Query category
            time_frame: Time frame that was searched
        """
        try:
            logger.info(f"Generating response with context length: {len(context)}")
            
            # Update conversation context with the current category
            self.conversation_context["last_category"] = category
            
            # Initialize future_assignments if None
            if future_assignments is None:
                future_assignments = []
            
            # Convert tuples to CanvasItem objects if needed
            processed_assignments = []
            for item in future_assignments:
                if isinstance(item, tuple):
                    # If it's a tuple (item, score), extract just the item
                    processed_assignments.append(item[0])
                else:
                    # If it's already a CanvasItem, use it directly
                    processed_assignments.append(item)
            
            # Sort assignments by due date
            def parse_due_date(item):
                if not item.due_date:
                    return datetime.max
                try:
                    # Handle different date formats
                    due_date_str = item.due_date.replace('Z', '+00:00') if 'Z' in item.due_date else item.due_date
                    return datetime.fromisoformat(due_date_str)
                except Exception as e:
                    logger.error(f"Error parsing date for sorting: {e}, item: {item.title}, date: {item.due_date}")
                    return datetime.max
            
            # Sort by due date (earliest first)
            processed_assignments.sort(key=parse_due_date)
            
            # Log the sorted assignments for debugging
            if processed_assignments:
                logger.info(f"Sorted assignments by due date:")
                for item in processed_assignments:
                    logger.info(f"  - {item.title}: {item.due_date}")
                
                # Use the first assignment (earliest due date) for "next assignment" queries
                is_next_assignment_query = any(phrase in query.lower() for phrase in 
                                            ["next assignment", "upcoming assignment", "due soon", "next assignemnt"])
                if is_next_assignment_query and processed_assignments:
                    # Create a new list with just the earliest assignment
                    next_assignment = processed_assignments[0]
                    logger.info(f"For 'next assignment' query, using only the earliest assignment: {next_assignment.title}")
                    processed_assignments = [next_assignment]
            
            # Format the assignments for display
            formatted_assignments = ""
            if processed_assignments:
                formatted_assignments = "Upcoming assignments:\n\n"
                for item in processed_assignments:
                    due_date = item.due_date
                    if due_date:
                        # Convert to a more readable format
                        try:
                            dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                            formatted_date = dt.strftime("%B %d, %Y at %I:%M %p")
                        except:
                            formatted_date = due_date
                    else:
                        formatted_date = "No due date specified"
                    
                    formatted_assignments += f"- **{item.title}**\n"
                    course_name = item.course_name if hasattr(item, 'course_name') else item.metadata.get('course_name', 'Unknown Course')
                    formatted_assignments += f"  - **Course:** {course_name}\n"
                    formatted_assignments += f"  - **Due Date:** {formatted_date}\n\n"
            else:
                formatted_assignments = "There are no upcoming assignments with future due dates.\n"

            # Create the system prompt with the current date, category, and time frame
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # Create time frame description for the prompt
            time_frame_descriptions = {
                TimeFrame.FUTURE: "future assignments and events from now until the end of the semester",
                TimeFrame.RECENT_PAST: "recent items from the past two weeks",
                TimeFrame.EXTENDED_PAST: "items from the past month",
                TimeFrame.FULL_SEMESTER: "items from the entire current semester",
                TimeFrame.ALL_TIME: "items across all time periods"
            }
            
            time_frame_desc = time_frame_descriptions.get(time_frame, "recent items")
            
            # Add conversation context to the system prompt
            conversation_context_str = ""
            if self.conversation_context["last_course_code"]:
                conversation_context_str = f"\nYou are currently discussing the course: {self.conversation_context['last_course_code']}."
                
                # If this is an office hours query, add specific instructions
                if "office hours" in query.lower() or "office hour" in query.lower():
                    conversation_context_str += f" Focus only on office hours information for {self.conversation_context['last_course_code']}."
            
            system_prompt = f"""You are Canvas Copilot, an AI assistant for students using Canvas LMS.
Today's date is {current_date}.
The user's query was categorized as {category} and you searched for {time_frame_desc}.{conversation_context_str}
Provide helpful, accurate, and concise information based on the Canvas data provided.
Focus on directly answering the student's question.
If discussing assignments or due dates, be very clear about timeframes (use specific dates rather than relative time).
Format your response in a clear, organized manner using Markdown.
If no information is available, state that clearly without making up details.
"""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
                {"role": "assistant", "content": f"I'll help you with information about your Canvas courses.\n\n{formatted_assignments}"},
                {"role": "user", "content": f"Here's additional context from your Canvas account: {context}\n\nCan you provide a complete response to my question: {query}"}
            ]

            logger.debug(f"Messages: {messages}")

            import openai
            response = openai.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                temperature=0.3,
                max_tokens=2000
            )

            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"I apologize, but I encountered an error while generating a response: {str(e)}"

    def _get_context(self, query, canvas_items):
        """Get context for the query from canvas items."""
        try:
            # Convert the query and Canvas items to formatted context
            context_parts = []
            
            # Sort items by type
            sorted_items = sorted(canvas_items, key=lambda x: x.type)
            
            # Include item details in context
            for item in sorted_items:
                context_part = f"--- {item.type.upper()}: {item.title} ---\n"
                
                if hasattr(item, 'course_name') and item.course_name:
                    context_part += f"Course: {item.course_name}\n"
                elif hasattr(item, 'metadata') and item.metadata.get('course_name'):
                    context_part += f"Course: {item.metadata.get('course_name')}\n"
                    
                if hasattr(item, 'due_date') and item.due_date:
                    context_part += f"Due Date: {item.due_date}\n"
                    
                if hasattr(item, 'content') and item.content:
                    # Truncate content if too long
                    content = item.content[:2000] + "..." if len(item.content) > 2000 else item.content
                    context_part += f"Content: {content}\n"
                    
                context_parts.append(context_part)
                
            return "\n".join(context_parts)
        except Exception as e:
            logger.error(f"Error getting context: {e}")
            return f"Error retrieving context: {str(e)}"

    def clear_cache(self) -> None:
        """
        Clear the vector database cache and reset initialization status.
        This forces the system to fetch fresh data from Canvas on the next query.
        
        Returns:
            None
        """
        logger.info("Clearing vector database cache...")
        
        # Clear the vector database items
        if hasattr(self.vector_db, 'items'):
            self.vector_db.items = []
            
        # Clear any embeddings
        if hasattr(self.vector_db, 'embeddings'):
            self.vector_db.embeddings = []
            
        # Reset the persistence cache if the method exists
        if hasattr(self.vector_db, 'clear_persistence_cache') and callable(getattr(self.vector_db, 'clear_persistence_cache')):
            self.vector_db.clear_persistence_cache()
            
        # Reset initialization status
        self.initialized = False
        
        logger.info("Vector database cache cleared. System will re-initialize on next query.")

    def _check_if_followup(self, query: str, keywords: List[str]) -> bool:
        """
        Check if the current query is a follow-up question without explicit course mention
        
        Args:
            query: The current query
            keywords: Extracted keywords from the query
            
        Returns:
            Boolean indicating if this is likely a follow-up question
        """
        # If we don't have previous context, it can't be a follow-up
        if not self.conversation_context["last_query"]:
            self.conversation_context["last_query"] = query
            return False
            
        # Check if the query contains course identifiers
        course_code_pattern = re.compile(r'([a-zA-Z]{2,6})\s*(\d{2,4}[a-zA-Z]*)', re.IGNORECASE)
        course_number_pattern = re.compile(r'\b(\d{3})\b')
        
        has_course_identifier = bool(course_code_pattern.search(query) or course_number_pattern.search(query))
        
        # If the query already has a course identifier, it's not a follow-up that needs context
        if has_course_identifier:
            self.conversation_context["last_query"] = query
            return False
            
        # Check if this is a short follow-up question
        is_short_query = len(query.split()) < 10
        
        # Check for follow-up indicators
        followup_indicators = [
            "when", "where", "what time", "how", "who", "office hours", 
            "syllabus", "assignment", "due", "deadline", "exam", "quiz",
            "lecture", "class", "professor", "instructor", "ta", "teaching assistant"
        ]
        
        has_followup_indicator = any(indicator in query.lower() for indicator in followup_indicators)
        
        # Update last query
        self.conversation_context["last_query"] = query
        
        # It's a follow-up if it's short, has follow-up indicators, and doesn't specify a course
        return is_short_query and has_followup_indicator and not has_course_identifier 