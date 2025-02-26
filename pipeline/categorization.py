#!/usr/bin/env python3
"""
Categorization Module
--------------------
Contains components for query categorization, keyword extraction, and time frame detection.

This module provides the intelligence for understanding and categorizing user queries about
Canvas LMS data. It contains several key components:

1. QueryCategory: Defines the possible categories for user queries (syllabus, assignments, events, etc.)
2. QueryClassifier: Analyzes user queries to determine the appropriate category
3. TimeFrameDetector: Determines the relevant time period for a query (future, recent past, etc.)
4. KeywordExtractor: Extracts important keywords from user queries for search purposes

The module uses a combination of rule-based pattern matching and machine learning techniques
to accurately categorize queries and extract relevant information, enabling the Canvas Copilot
to retrieve the most appropriate data from Canvas LMS.
"""

import os
import re
import logging
from typing import List, Tuple, Optional
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from dotenv import load_dotenv

# Import TimeFrame from canvas_api
from canvas_api import TimeFrame

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger("canvas_copilot")

# Constants
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


class QueryCategory:
    """
    Enumeration of query categories.
    
    This class defines constants representing different types of queries that users might
    ask about Canvas LMS data. These categories are used to determine how to process
    queries and what data to retrieve from Canvas.
    
    Constants:
        SYLLABUS: Queries about course syllabi
        ASSIGNMENTS: Queries about homework, projects, or other assigned tasks
        COURSE_CONTENT: Queries about lecture materials and course resources
        CALENDAR_EVENTS: Queries about calendar events
        ANNOUNCEMENTS: Queries about course announcements
        FILES: Queries about files and documents
        GRADES: Queries about grades and feedback
        EVENTS: Queries about specific events like exams, office hours, or lectures
        GENERAL: General queries that don't fit into other categories
    """
    SYLLABUS = "syllabus"
    ASSIGNMENTS = "assignments"  # Single category for all assignment types
    COURSE_CONTENT = "course_content"
    CALENDAR_EVENTS = "calendar_events"
    ANNOUNCEMENTS = "announcements"
    FILES = "files"
    GRADES = "grades"
    EVENTS = "events"  # New category for lectures, office hours, exams
    GENERAL = "general"


class QueryClassifier:
    """
    Classifies user queries into categories for specialized handling.
    
    This class analyzes user queries to determine the most appropriate category for processing.
    It uses a weighted scoring system with keyword matching and direct pattern recognition
    to accurately categorize queries, even when they are ambiguous or contain multiple topics.
    """
    
    def __init__(self, model: str = LLM_MODEL):
        """
        Initialize the QueryClassifier.
        
        Args:
            model (str, optional): The LLM model to use for advanced classification.
                                  Defaults to the value specified in environment variables.
        """
        self.model = model
        # Mapping of categories to their related keywords with weights
        # Format: {category: {keyword: weight}}
        self.category_keywords = {
            QueryCategory.SYLLABUS: {
                "syllabus": 5.0,  # Strong indicator for syllabus category
                "course outline": 4.0,
                "course requirements": 3.5,
                "objectives": 3.0,
                "grading policy": 3.5,
                "policy": 3.0, 
                "policies": 3.0,
                "course schedule": 2.0,  # Lower weight because it overlaps with EVENTS
            },
            QueryCategory.ASSIGNMENTS: {
                "assignment": 4.0,
                "homework": 4.0,
                "project": 3.5,
                "quiz": 2.5,  # Lower weight because it overlaps with EVENTS
                "task": 3.0,
                "upcoming": 3.0,
                "next": 2.5,
                "due soon": 3.5,
                "this week": 2.5,
                "next week": 2.5, 
                "calendar": 2.0,
                "schedule": 1.5,  # Lower weight because it's very general
                "due date": 3.5,
                "deadline": 3.5,
                "pending": 3.0,
                "work on": 2.5,
                "past": 2.0,
                "previous": 2.0,
                "completed": 2.5,
                "turned in": 3.0,
                "submitted": 3.0,
                "late": 2.5
            },
            QueryCategory.COURSE_CONTENT: {
                "lecture": 2.5,  # Lower weight because it overlaps with EVENTS
                "content": 4.0,
                "material": 4.0,
                "module": 4.5,
                "resources": 3.5,
                "notes": 3.5
            },
            QueryCategory.CALENDAR_EVENTS: {
                "calendar": 4.0,
                "event": 3.5,
                "schedule": 2.0,  # Lower weight because it's very general
                "upcoming event": 4.0,
                "appointment": 3.5,
                "meeting": 3.0
            },
            QueryCategory.ANNOUNCEMENTS: {
                "announcement": 5.0,
                "news": 3.5,
                "update": 3.0,
                "notification": 3.0,
                "message": 2.5
            },
            QueryCategory.FILES: {
                "file": 4.5,
                "document": 3.5,
                "pdf": 4.0,
                "upload": 3.5,
                "download": 3.5,
                "attachment": 4.0
            },
            QueryCategory.GRADES: {
                "grade": 5.0,
                "score": 4.5,
                "rubric": 4.0,
                "feedback": 3.5,
                "evaluation": 3.5,
                "assessment": 3.5
            },
            QueryCategory.EVENTS: {
                "exam": 5.0,  # Strong indicators for events
                "exams": 5.0,
                "midterm": 5.0,
                "final": 4.5,
                "test": 4.0,
                "quiz": 3.5,  # Lower weight than "exam" but still significant
                "lecture time": 4.5,
                "office hours": 5.0,  # Strong indicator for events
                "office hour": 5.0,
                "class time": 4.5,
                "class schedule": 4.0,  # Higher weight for EVENTS than for SYLLABUS
                "when is": 4.0,  # Time-related queries are strong indicators for EVENTS
                "where is": 4.0,
                "what time": 4.5,
                "meeting time": 4.0,
                "lecture": 3.0  # Lower weight because it overlaps with COURSE_CONTENT
            }
        }
    
    def classify(self, query: str, keywords: List[str]) -> str:
        """
        Classify a query into a category based on its content and extracted keywords.
        
        This method uses a multi-step approach to determine the most appropriate category:
        1. Direct pattern matching for common query types
        2. Weighted keyword scoring for more nuanced classification
        3. Context-specific adjustments for ambiguous queries
        4. Fallback mechanisms for difficult-to-classify queries
        
        Args:
            query (str): The original user query
            keywords (List[str]): List of extracted keywords from the query
            
        Returns:
            str: The identified category from QueryCategory
        """
        # Debug logging
        logger.info(f"Classifying query: '{query}'")
        logger.info(f"Extracted keywords: {keywords}")
        
        # Direct pattern matches (most reliable)
        query_lower = query.lower()
        
        # Detect specific word combinations that strongly indicate certain categories
        if "office hours" in query_lower:
            logger.info(f"Direct match for events (office hours)")
            return QueryCategory.EVENTS
            
        if ("when" in query_lower or "what time" in query_lower) and ("exam" in query_lower or "midterm" in query_lower or "final" in query_lower):
            logger.info(f"Direct match for events (exam timing)")
            return QueryCategory.EVENTS
        
        # Simple direct matches for common queries - ordered by specificity
        if "syllabus" in query_lower and not ("exam" in query_lower or "midterm" in query_lower or 
                                             "final" in query_lower or "office hours" in query_lower or 
                                             "when" in query_lower or "what time" in query_lower):
            logger.info(f"Direct match for syllabus")
            return QueryCategory.SYLLABUS
            
        if any(word in query_lower for word in ["assignment", "homework", "due", "next assignment"]):
            logger.info(f"Direct match for assignments")
            return QueryCategory.ASSIGNMENTS
            
        # Direct match for events category - this is now more nuanced with checks for timing keywords
        if any(phrase in query_lower for phrase in ["exam", "midterm", "final", "office hours", "lecture time", "class time"]):
            # Exams are events, but a pure "syllabus" query shouldn't match here
            if not "syllabus" in query_lower or any(phrase in query_lower for phrase in ["when", "what time", "where", "schedule"]):
                logger.info(f"Direct match for events")
                return QueryCategory.EVENTS
        
        # Weighted keyword-based scoring approach
        try:
            # Initialize scores for each category
            category_scores = {}
            for cat_name in ["SYLLABUS", "ASSIGNMENTS", "COURSE_CONTENT", 
                         "CALENDAR_EVENTS", "ANNOUNCEMENTS", "FILES", 
                         "GRADES", "EVENTS", "GENERAL"]:
                category_scores[getattr(QueryCategory, cat_name)] = 0.0
                
            # Score based on keywords in query and extracted keywords
            for category, keyword_weights in self.category_keywords.items():
                # Check direct matches in query
                for keyword, weight in keyword_weights.items():
                    if keyword.lower() in query_lower:
                        category_scores[category] += weight
                
                # Check matches in extracted keywords
                for extracted_keyword in keywords:
                    for keyword, weight in keyword_weights.items():
                        if keyword.lower() in extracted_keyword.lower():
                            category_scores[category] += weight * 0.8  # Slightly lower weight for extracted keywords
            
            # Apply context-specific adjustments for ambiguous queries
            # If query mentions both syllabus and events, adjust scores based on indicators
            if (category_scores[QueryCategory.SYLLABUS] > 0 and 
                category_scores[QueryCategory.EVENTS] > 0):
                
                # If query contains time-related phrases, boost EVENTS score
                if any(phrase in query_lower for phrase in ["when", "what time", "where", "schedule"]):
                    category_scores[QueryCategory.EVENTS] *= 1.3
                    logger.info(f"Boosted EVENTS score due to time-related phrases")
                
                # If query is specifically looking for a document, boost SYLLABUS score
                if any(phrase in query_lower for phrase in ["show me", "get", "download", "view"]):
                    category_scores[QueryCategory.SYLLABUS] *= 1.3
                    logger.info(f"Boosted SYLLABUS score due to document-related phrases")
            
            # Log all category scores for debugging
            logger.info(f"Category scores: {category_scores}")
            
            # Find highest scoring category
            if category_scores:
                max_score = max(category_scores.values())
                if max_score > 0:
                    max_categories = [c for c, s in category_scores.items() if s == max_score]
                    if max_categories:
                        logger.info(f"Selected category based on scoring: {max_categories[0]}")
                        return max_categories[0]
        except Exception as e:
            logger.error(f"Error in weighted scoring classification: {e}")
            # Continue to fallback approaches
        
        # Fallback to direct keyword matching
        if any(word in query_lower for word in ["syllabus", "course outline"]):
            return QueryCategory.SYLLABUS
        elif any(word in query_lower for word in ["assignment", "homework", "due", "deadline"]):
            return QueryCategory.ASSIGNMENTS
        elif any(word in query_lower for word in ["lecture", "content", "material"]):
            return QueryCategory.COURSE_CONTENT
        elif any(word in query_lower for word in ["calendar", "event", "schedule"]):
            return QueryCategory.CALENDAR_EVENTS
        elif any(word in query_lower for word in ["announcement", "news"]):
            return QueryCategory.ANNOUNCEMENTS
        elif any(word in query_lower for word in ["file", "document"]):
            return QueryCategory.FILES
        elif any(word in query_lower for word in ["grade", "score"]):
            return QueryCategory.GRADES
        elif any(word in query_lower for word in ["exam", "midterm", "final", "office hours", "lecture time", "class time"]):
            return QueryCategory.EVENTS
        
        # Final fallback - default to general
        logger.info("No specific category detected, defaulting to general")
        return QueryCategory.GENERAL
    
    def get_additional_keywords(self, category: str) -> List[str]:
        """
        Get additional keywords for a category to enhance search.
        
        This method returns a list of category-specific keywords that can be used to
        supplement the originally extracted keywords when searching for relevant information.
        
        Args:
            category (str): The query category
            
        Returns:
            List[str]: List of additional keywords for the category
        """
        # Return category-specific additional keywords
        if category == QueryCategory.SYLLABUS:
            return ["syllabus", "course outline", "policy"]
        elif category == QueryCategory.ASSIGNMENTS:
            return ["assignment", "homework", "task", "due"]
        elif category == QueryCategory.COURSE_CONTENT:
            return ["module", "content", "material"]
        elif category == QueryCategory.CALENDAR_EVENTS:
            return ["calendar", "event", "schedule"]
        elif category == QueryCategory.ANNOUNCEMENTS:
            return ["announcement", "update", "news"]
        elif category == QueryCategory.FILES:
            return ["file", "document", "download"]
        elif category == QueryCategory.GRADES:
            return ["grade", "score", "feedback"]
        elif category == QueryCategory.EVENTS:
            return ["exam", "exams", "midterm", "final", "test", "quiz", "lecture", 
                    "office hours", "office hour", "class time", "class schedule",
                    "when is", "where is", "what time", "meeting time", "lecture time"]
        else:
            return []


class TimeFrameDetector:
    """
    Detects the appropriate time frame for a query.
    
    This class analyzes user queries to determine the relevant time period (future, recent past,
    etc.) for retrieving Canvas data. It uses a combination of keyword detection and 
    category-based defaults to identify the appropriate time frame.
    """
    
    def __init__(self, model: str = LLM_MODEL):
        """
        Initialize the TimeFrameDetector.
        
        Args:
            model (str, optional): The LLM model to use for advanced time frame detection.
                                 Defaults to the value specified in environment variables.
        """
        self.model = model
    
    def detect_time_frame(self, query: str, category: str) -> str:
        """
        Detect the appropriate time frame for a query based on its content and category.
        
        This method determines the relevant time period for a query through:
        1. Checking for explicit time indicators in the query text
        2. Using category-specific default time frames
        3. Falling back to LLM-based detection for complex queries
        
        Args:
            query (str): The original user query
            category (str): The query category
            
        Returns:
            str: The appropriate time frame as a string from TimeFrame
        """
        # Debug logging
        logger.info(f"Detecting time frame for query: '{query}', category: {category}")
        
        # Check for explicit time indicators in the query
        query_lower = query.lower()
        
        # Future indicators
        future_indicators = [
            "upcoming", "next", "future", "this week", "next week", 
            "due soon", "coming up", "later", "tomorrow"
        ]
        has_future = any(phrase in query_lower for phrase in future_indicators)
        if has_future:
            logger.info(f"Found future time indicators: {[i for i in future_indicators if i in query_lower]}")
            return TimeFrame.FUTURE
        
        # Recent past indicators
        recent_past_indicators = [
            "recently", "last week", "past few days", "yesterday", 
            "recent", "just", "past week", "last couple of days"
        ]
        has_recent_past = any(phrase in query_lower for phrase in recent_past_indicators)
        if has_recent_past:
            logger.info(f"Found recent past time indicators: {[i for i in recent_past_indicators if i in query_lower]}")
            return TimeFrame.RECENT_PAST
        
        # Extended past indicators
        extended_past_indicators = [
            "last month", "past month", "few weeks ago", "earlier this month",
            "several weeks"
        ]
        has_extended_past = any(phrase in query_lower for phrase in extended_past_indicators)
        if has_extended_past:
            logger.info(f"Found extended past time indicators: {[i for i in extended_past_indicators if i in query_lower]}")
            return TimeFrame.EXTENDED_PAST
        
        # Full semester indicators
        full_semester_indicators = [
            "this semester", "this term", "entire course", "since the beginning",
            "all semester", "throughout the course", "all time", "everything"
        ]
        has_full_semester = any(phrase in query_lower for phrase in full_semester_indicators)
        if has_full_semester:
            logger.info(f"Found full semester time indicators: {[i for i in full_semester_indicators if i in query_lower]}")
            return TimeFrame.FULL_SEMESTER
        
        # For certain categories, default to specific time frames
        category_to_timeframe = {
            QueryCategory.ASSIGNMENTS: TimeFrame.FUTURE,  # Default to future for assignments
            QueryCategory.CALENDAR_EVENTS: TimeFrame.FUTURE,
            QueryCategory.ANNOUNCEMENTS: TimeFrame.RECENT_PAST,
            QueryCategory.SYLLABUS: TimeFrame.FULL_SEMESTER,
            QueryCategory.EVENTS: TimeFrame.FULL_SEMESTER,  # Default to full semester for events
        }
        
        if category in category_to_timeframe:
            default_timeframe = category_to_timeframe[category]
            logger.info(f"Using default time frame for category {category}: {default_timeframe}")
            return default_timeframe
        
        # Fallback to LLM for more nuanced detection
        try:
            system_prompt = """You are a time frame detection assistant. Determine the most appropriate time frame for the user's query about their Canvas LMS courses. Choose exactly one from:

1. FUTURE - For queries about upcoming events, assignments due soon, or anything that happens from now until the end of the semester
2. RECENT_PAST - For queries about events from the last two weeks
3. EXTENDED_PAST - For queries about events from the last month
4. FULL_SEMESTER - For queries about events throughout the entire current semester or when no specific time frame is mentioned

Return ONLY the time frame name (e.g., "FUTURE") without any additional text."""
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                temperature=0.3,
                max_tokens=20
            )
            
            time_frame = response.choices[0].message.content.strip()
            logger.info(f"LLM detected time frame: {time_frame}")
            
            # Map the response to our constants
            if "FUTURE" in time_frame:
                return TimeFrame.FUTURE
            elif "RECENT_PAST" in time_frame:
                return TimeFrame.RECENT_PAST
            elif "EXTENDED_PAST" in time_frame:
                return TimeFrame.EXTENDED_PAST
            else:
                # Default to FULL_SEMESTER for any other response or when no specific time frame is detected
                return TimeFrame.FULL_SEMESTER
                
        except Exception as e:
            logger.error(f"Error using LLM for time frame detection: {e}")
            # Default to FULL_SEMESTER if LLM fails
            return TimeFrame.FULL_SEMESTER


class KeywordExtractor:
    """
    Extracts keywords from user prompts.
    
    This class uses machine learning techniques to identify the most important keywords
    and phrases from user queries. These keywords are used for searching and categorizing
    queries to retrieve the most relevant information from Canvas.
    """
    
    def __init__(self, model: str = LLM_MODEL):
        """
        Initialize the KeywordExtractor.
        
        Args:
            model (str, optional): The LLM model to use for keyword extraction.
                                 Defaults to the value specified in environment variables.
        """
        self.model = model
    
    def extract_keywords_and_timeframe(self, prompt: str) -> Tuple[List[str], str]:
        """
        Extract keywords and time frame from a user prompt using LLM.
        
        This method uses a language model to analyze the user's query and extract:
        1. The most important keywords or phrases for searching in Canvas
        2. The most appropriate time frame for the query
        
        Args:
            prompt (str): The user's query
            
        Returns:
            Tuple[List[str], str]: A tuple containing a list of extracted keywords and
                                  the appropriate time frame as a string from TimeFrame
        """
        try:
            # Add specific instructions for extracting both keywords and time frame
            system_prompt = """You are a query analysis assistant. Extract both:

1. The 3-5 most important keywords or phrases from the user's query that would be useful for searching in a Canvas LMS system.
2. The most appropriate time frame for the query from the following options:
   - FUTURE: From now until the end of semester (for upcoming assignments, events, etc.)
   - RECENT_PAST: From 2 weeks ago until now (for recent announcements, submissions, etc.)
   - EXTENDED_PAST: From a month ago until now (for older assignments, submissions, etc.)
   - FULL_SEMESTER: From the beginning of the semester until now (for full course history or when no specific time frame is mentioned)

For queries about upcoming assignments or calendar events, be sure to include keywords like 'calendar', 'upcoming', or 'due'.
For queries about course syllabi, be sure to include keywords like 'syllabus', 'course outline', 'office hours', or 'course schedule'.

Return your answer in this exact format:
Keywords: keyword1, keyword2, keyword3
TimeFrame: [ONE OF: FUTURE, RECENT_PAST, EXTENDED_PAST, FULL_SEMESTER]"""
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=150
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse the result
            keywords = []
            time_frame = TimeFrame.FULL_SEMESTER  # Default changed to FULL_SEMESTER
            
            # Extract keywords line
            keyword_match = re.search(r"Keywords:(.+?)(?:\n|$)", result_text)
            if keyword_match:
                keywords_text = keyword_match.group(1).strip()
                keywords = [k.strip() for k in keywords_text.split(',')]
            
            # Extract time frame line
            timeframe_match = re.search(r"TimeFrame:\s*(FUTURE|RECENT_PAST|EXTENDED_PAST|FULL_SEMESTER)", result_text)
            if timeframe_match:
                time_frame_text = timeframe_match.group(1).strip()
                if time_frame_text == "FUTURE":
                    time_frame = TimeFrame.FUTURE
                elif time_frame_text == "RECENT_PAST":
                    time_frame = TimeFrame.RECENT_PAST
                elif time_frame_text == "EXTENDED_PAST":
                    time_frame = TimeFrame.EXTENDED_PAST
                elif time_frame_text == "FULL_SEMESTER":
                    time_frame = TimeFrame.FULL_SEMESTER
            
            logger.info(f"Extracted keywords: {keywords}, time frame: {time_frame}")
            return keywords, time_frame
            
        except Exception as e:
            logger.error(f"Error extracting keywords and time frame: {e}")
            # Fallback to simple extraction
            words = prompt.split()
            extracted = [w for w in words if len(w) > 3][:5]
            
            # Add special keywords if they seem relevant
            if any(word.lower() in prompt.lower() for word in ['upcoming', 'calendar', 'schedule', 'due', 'next']):
                if 'calendar' not in extracted:
                    extracted.append('calendar')
                if 'upcoming' not in extracted:
                    extracted.append('upcoming')
                time_frame = TimeFrame.FUTURE
            elif any(word.lower() in prompt.lower() for word in ['syllabus', 'outline', 'policy', 'policies', 'office hours', 'exams']):
                if 'syllabus' not in extracted:
                    extracted.append('syllabus')
                time_frame = TimeFrame.FULL_SEMESTER
            elif any(word.lower() in prompt.lower() for word in ['recent', 'last week', 'yesterday']):
                time_frame = TimeFrame.RECENT_PAST
            elif any(word.lower() in prompt.lower() for word in ['last month', 'few weeks']):
                time_frame = TimeFrame.EXTENDED_PAST
            else:
                # Default to FULL_SEMESTER instead of RECENT_PAST
                time_frame = TimeFrame.FULL_SEMESTER
            
            return extracted, time_frame
    
    # Keep the original method for backward compatibility
    def extract_keywords(self, prompt: str) -> List[str]:
        """
        Extract keywords from a user prompt using LLM.
        
        This is a compatibility method that calls extract_keywords_and_timeframe and
        returns only the keywords component.
        
        Args:
            prompt (str): The user's query
            
        Returns:
            List[str]: A list of extracted keywords
        """
        keywords, _ = self.extract_keywords_and_timeframe(prompt)
        return keywords 