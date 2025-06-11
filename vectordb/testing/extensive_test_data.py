#!/usr/bin/env python3
"""
Extensive Test Data Generator for Vector Database Testing
--------------------------------------------------------
This module generates large-scale test data for comprehensive vector search testing.
It creates realistic Canvas course data with multiple courses, assignments, files,
announcements, quizzes, and events to enable thorough testing of search functionality.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any


def create_extensive_test_json(
    file_path: Path, user_id="extensive_test_user_456"
) -> str:
    """Creates an extensive JSON file for testing with large amounts of realistic Canvas data.

    Args:
        file_path: Path where the extensive JSON file will be created.
        user_id: User ID to be included in the dummy data.

    Returns:
        str: The user_id used in the dummy data.

    Raises:
        None
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Course subjects and their details
    course_subjects = [
        {
            "id": "3000000",
            "name": "Computer Science Fundamentals",
            "code": "CS101",
            "subject": "computer science",
        },
        {
            "id": "3000001",
            "name": "Advanced Data Structures",
            "code": "CS201",
            "subject": "algorithms",
        },
        {
            "id": "3000002",
            "name": "Database Systems",
            "code": "CS301",
            "subject": "databases",
        },
        {
            "id": "3000003",
            "name": "Machine Learning Basics",
            "code": "ML101",
            "subject": "machine learning",
        },
        {
            "id": "3000004",
            "name": "Web Development",
            "code": "WEB201",
            "subject": "web development",
        },
        {
            "id": "3000005",
            "name": "Software Engineering",
            "code": "SE301",
            "subject": "software engineering",
        },
        {
            "id": "3000006",
            "name": "Calculus I",
            "code": "MATH101",
            "subject": "mathematics",
        },
        {
            "id": "3000007",
            "name": "Statistics and Probability",
            "code": "STAT201",
            "subject": "statistics",
        },
        {"id": "3000008", "name": "Physics I", "code": "PHYS101", "subject": "physics"},
        {
            "id": "3000009",
            "name": "Technical Writing",
            "code": "ENG301",
            "subject": "writing",
        },
    ]

    # Generate courses with syllabi
    courses = []
    courses_selected = {}
    for course in course_subjects:
        courses_selected[course["id"]] = course["code"]
        courses.append(
            {
                "id": course["id"],
                "name": course["name"],
                "course_code": course["code"],
                "syllabus_body": f"<h1>{course['name']} Syllabus</h1><p>This course covers fundamental concepts in {course['subject']}. Students will learn through lectures, assignments, and hands-on projects.</p><p>Prerequisites: Basic understanding of {course['subject']} concepts.</p>",
                "timezone": "America/New_York",
            }
        )

    # Assignment templates for different types
    assignment_templates = [
        {
            "type": "homework",
            "names": ["Homework", "Problem Set", "Exercise", "Practice"],
            "descriptions": [
                "Complete the assigned problems",
                "Solve the given exercises",
                "Work through the practice problems",
            ],
        },
        {
            "type": "lab",
            "names": ["Lab", "Laboratory", "Practical"],
            "descriptions": [
                "Complete the lab assignment",
                "Perform the laboratory exercise",
                "Finish the practical work",
            ],
        },
        {
            "type": "project",
            "names": ["Project", "Final Project", "Group Project"],
            "descriptions": [
                "Complete the project requirements",
                "Develop the assigned project",
                "Build the required application",
            ],
        },
        {
            "type": "quiz",
            "names": ["Quiz", "Short Quiz", "Weekly Quiz"],
            "descriptions": [
                "Take the quiz on course material",
                "Complete the assessment",
                "Answer the quiz questions",
            ],
        },
        {
            "type": "exam",
            "names": ["Exam", "Midterm", "Final Exam"],
            "descriptions": [
                "Take the examination",
                "Complete the test",
                "Finish the assessment",
            ],
        },
    ]

    # Generate assignments
    assignments = []
    assignment_id = 20000000
    base_date = datetime(2024, 8, 15)

    for course in course_subjects:
        # Generate 20-25 assignments per course
        num_assignments = random.randint(20, 25)
        for i in range(num_assignments):
            template = random.choice(assignment_templates)
            name_base = random.choice(template["names"])
            description = random.choice(template["descriptions"])

            # Add variety to names and descriptions
            if template["type"] in ["homework", "lab", "quiz"]:
                name = f"{name_base} {i + 1}"
                description = f"{description} for {course['subject']} concepts."
            else:
                name = f"{name_base}"
                description = f"{description} focusing on {course['subject']}."

            # Vary due dates
            days_offset = random.randint(1, 120)
            due_date = base_date + timedelta(days=days_offset)

            assignments.append(
                {
                    "id": str(assignment_id),
                    "type": None,
                    "name": name,
                    "description": f"<p>{description}</p><p>This assignment covers key topics in {course['name']}.</p>",
                    "due_at": due_date.strftime("%Y-%m-%dT23:59:00Z"),
                    "course_id": course["id"],
                    "submission_types": ["online_text_entry", "online_upload"],
                    "can_submit": None,
                    "graded_submission_exist": None,
                    "graded_submissions_exist": None,
                    "module_id": 5475163 + i,
                    "module_name": f"Week {(i // 3) + 1}",
                    "content": [],
                }
            )
            assignment_id += 1

    # File types and names
    file_templates = [
        {
            "type": "lecture",
            "names": ["Lecture Notes", "Slides", "Presentation"],
            "extensions": [".pdf", ".pptx"],
        },
        {
            "type": "reading",
            "names": ["Reading Material", "Chapter", "Article"],
            "extensions": [".pdf", ".docx"],
        },
        {
            "type": "code",
            "names": ["Code Example", "Sample Code", "Template"],
            "extensions": [".py", ".java", ".cpp"],
        },
        {
            "type": "data",
            "names": ["Dataset", "Data File", "Sample Data"],
            "extensions": [".csv", ".json", ".xlsx"],
        },
    ]

    # Generate files
    files = []
    file_id = 30000000

    for course in course_subjects:
        # Generate 15-20 files per course
        num_files = random.randint(15, 20)
        for i in range(num_files):
            template = random.choice(file_templates)
            name_base = random.choice(template["names"])
            extension = random.choice(template["extensions"])

            display_name = f"{name_base} {i + 1}{extension}"
            filename = display_name.lower().replace(" ", "_")

            files.append(
                {
                    "course_id": course["id"],
                    "id": str(file_id),
                    "type": None,
                    "folder_id": f"folder_{course['code']}_docs",
                    "display_name": display_name,
                    "filename": filename,
                    "url": f"http://example.com/files/{file_id}/download?download_frd=1",
                    "size": random.randint(10240, 5242880),  # 10KB to 5MB
                    "updated_at": (
                        base_date + timedelta(days=random.randint(1, 100))
                    ).strftime("%Y-%m-%dT12:00:00Z"),
                    "locked": False,
                    "lock_explanation": None,
                    "module_id": None,
                    "module_name": None,
                }
            )
            file_id += 1

    # Generate announcements
    announcements = []
    announcement_id = 40000000
    announcement_templates = [
        "Welcome to {course_name}! Please review the syllabus and course materials.",
        "Reminder: {assignment_type} is due next week. Please submit on time.",
        "New lecture materials have been posted for {course_name}.",
        "Office hours this week will be held on {day} from 2-4 PM.",
        "Important update regarding the upcoming {exam_type} in {course_name}.",
        "Group project assignments have been posted. Check your teams.",
        "Lab session for {course_name} has been moved to {new_time}.",
        "Reading assignment for next week: Chapter {chapter_num}.",
        "Midterm exam results are now available in the gradebook.",
        "Final project presentations will be held during the last week of class.",
    ]

    for course in course_subjects:
        # Generate 10-12 announcements per course
        num_announcements = random.randint(10, 12)
        for i in range(num_announcements):
            template = random.choice(announcement_templates)

            # Fill in template variables
            message = template.format(
                course_name=course["name"],
                assignment_type=random.choice(
                    ["Assignment", "Homework", "Lab", "Project"]
                ),
                day=random.choice(
                    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                ),
                exam_type=random.choice(["midterm", "final exam", "quiz"]),
                new_time=random.choice(["10 AM", "2 PM", "3 PM"]),
                chapter_num=random.randint(1, 15),
            )

            posted_date = base_date + timedelta(days=random.randint(1, 100))

            announcements.append(
                {
                    "id": str(announcement_id),
                    "title": f"Course Update - {course['code']}",
                    "message": f"<p>{message}</p>",
                    "posted_at": posted_date.strftime("%Y-%m-%dT10:00:00Z"),
                    "course_id": course["id"],
                    "discussion_type": "threaded",
                    "course_name": course["name"],
                }
            )
            announcement_id += 1

    # Generate calendar events
    calendar_events = []
    event_id = 50000000
    event_templates = [
        {"title": "Lecture", "duration": 90},
        {"title": "Lab Session", "duration": 120},
        {"title": "Office Hours", "duration": 120},
        {"title": "Study Group", "duration": 60},
        {"title": "Exam", "duration": 120},
        {"title": "Project Presentation", "duration": 30},
    ]

    for course in course_subjects:
        # Generate 12-15 events per course
        num_events = random.randint(12, 15)
        for i in range(num_events):
            template = random.choice(event_templates)

            start_date = base_date + timedelta(days=random.randint(1, 120))
            start_time = start_date.replace(
                hour=random.randint(9, 16), minute=random.choice([0, 30])
            )
            end_time = start_time + timedelta(minutes=template["duration"])

            calendar_events.append(
                {
                    "id": f"event_{event_id}",
                    "title": f"{template['title']} - {course['code']}",
                    "start_at": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end_at": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "description": f"{template['title']} for {course['name']}",
                    "location_name": f"Room {random.randint(100, 999)}",
                    "location_address": None,
                    "context_code": f"course_{course['id']}",
                    "context_name": course["name"],
                    "all_context_codes": f"course_{course['id']}",
                    "url": f"http://example.com/calendar_events/event_{event_id}",
                    "course_id": course["id"],
                }
            )
            event_id += 1

    # Generate quizzes
    quizzes = []
    quiz_id = 60000000
    quiz_templates = [
        {
            "title": "Weekly Quiz",
            "type": "practice_quiz",
            "time_limit": 30,
            "points": 10,
        },
        {
            "title": "Chapter Review",
            "type": "assignment",
            "time_limit": 45,
            "points": 25,
        },
        {
            "title": "Midterm Exam",
            "type": "assignment",
            "time_limit": 90,
            "points": 100,
        },
        {"title": "Final Exam", "type": "assignment", "time_limit": 120, "points": 150},
        {"title": "Pop Quiz", "type": "practice_quiz", "time_limit": 15, "points": 5},
    ]

    for course in course_subjects:
        # Generate 8-10 quizzes per course
        num_quizzes = random.randint(8, 10)
        for i in range(num_quizzes):
            template = random.choice(quiz_templates)

            due_date = base_date + timedelta(days=random.randint(1, 120))

            quizzes.append(
                {
                    "id": quiz_id,
                    "title": f"{template['title']} {i + 1}",
                    "preview_url": None,
                    "description": f"Assessment covering material from {course['name']}",
                    "quiz_type": template["type"],
                    "time_limit": template["time_limit"],
                    "allowed_attempts": random.randint(1, 3),
                    "points_possible": float(template["points"]),
                    "due_at": due_date.strftime("%Y-%m-%dT23:59:00Z"),
                    "locked_for_user": random.choice([True, False]),
                    "lock_explanation": "This quiz was locked after the due date."
                    if random.choice([True, False])
                    else None,
                    "module_id": 5479590 + i,
                    "module_name": f"Week {(i // 2) + 1}",
                    "course_id": course["id"],
                }
            )
            quiz_id += 1

    # Compile the complete data structure
    data = {
        "user_metadata": {
            "id": user_id,
            "name": "Extensive Test User",
            "token": "extensive_test_token",
            "courses_selected": courses_selected,
            "is_updating": False,
        },
        "courses": courses,
        "assignments": assignments,
        "announcements": announcements,
        "files": files,
        "calendar_events": calendar_events,
        "quizzes": quizzes,
    }

    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

    print("Generated extensive test data:")
    print(f"  - {len(courses)} courses")
    print(f"  - {len(assignments)} assignments")
    print(f"  - {len(files)} files")
    print(f"  - {len(announcements)} announcements")
    print(f"  - {len(calendar_events)} calendar events")
    print(f"  - {len(quizzes)} quizzes")
    print(
        f"  - Total documents: {len(courses) + len(assignments) + len(files) + len(announcements) + len(calendar_events) + len(quizzes)}"
    )

    return user_id


def generate_test_search_queries() -> List[Dict[str, Any]]:
    """Generate a comprehensive list of test search queries for extensive testing.

    Returns:
        List of search parameter dictionaries covering various search scenarios.

    Raises:
        None
    """

    # Base course IDs from the extensive test data
    course_ids = [
        "3000000",
        "3000001",
        "3000002",
        "3000003",
        "3000004",
        "3000005",
        "3000006",
        "3000007",
        "3000008",
        "3000009",
    ]

    search_queries = []

    # 1. Syllabus searches (10 queries)
    for i, course_id in enumerate(course_ids):
        search_queries.append(
            {
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "SPECIFIC",
                    "item_types": ["assignment", "file", "quiz"],
                    "specific_dates": [],
                    "keywords": ["syllabus"],
                    "query": f"syllabus for course {course_id}",
                }
            }
        )

    # 2. Assignment searches (20 queries)
    assignment_queries = [
        "homework assignment",
        "lab assignment",
        "project assignment",
        "final project",
        "programming assignment",
        "math homework",
        "physics lab",
        "writing assignment",
        "group project",
        "individual assignment",
        "weekly homework",
        "problem set",
        "exercise assignment",
        "practical work",
        "coding project",
        "research project",
        "data analysis",
        "algorithm implementation",
        "database design",
        "web development",
    ]

    for i, query in enumerate(assignment_queries):
        course_id = course_ids[i % len(course_ids)]
        search_queries.append(
            {
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["assignment"],
                    "specific_dates": [],
                    "keywords": query.split(),
                    "query": query,
                }
            }
        )

    # 3. File searches (15 queries)
    file_queries = [
        "lecture notes",
        "slides presentation",
        "reading material",
        "code example",
        "dataset file",
        "sample code",
        "chapter reading",
        "lecture slides",
        "programming template",
        "data file",
        "course materials",
        "study guide",
        "reference document",
        "sample data",
        "code template",
    ]

    for i, query in enumerate(file_queries):
        course_id = course_ids[i % len(course_ids)]
        search_queries.append(
            {
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["file"],
                    "specific_dates": [],
                    "keywords": query.split(),
                    "query": query,
                }
            }
        )

    # 4. Quiz searches (10 queries)
    quiz_queries = [
        "weekly quiz",
        "midterm exam",
        "final exam",
        "chapter review",
        "practice quiz",
        "pop quiz",
        "assessment",
        "test",
        "examination",
        "quiz review",
    ]

    for i, query in enumerate(quiz_queries):
        course_id = course_ids[i % len(course_ids)]
        search_queries.append(
            {
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["quiz"],
                    "specific_dates": [],
                    "keywords": query.split(),
                    "query": query,
                }
            }
        )

    # 5. Event searches (10 queries)
    event_queries = [
        "lecture schedule",
        "lab session",
        "office hours",
        "study group",
        "exam schedule",
        "presentation",
        "class meeting",
        "tutorial",
        "workshop",
        "seminar",
    ]

    for i, query in enumerate(event_queries):
        course_id = course_ids[i % len(course_ids)]
        search_queries.append(
            {
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["calendar_events"],
                    "specific_dates": [],
                    "keywords": query.split(),
                    "query": query,
                }
            }
        )

    # 6. Multi-type searches (15 queries)
    multi_type_queries = [
        {"query": "computer science", "types": ["assignment", "file"]},
        {"query": "machine learning", "types": ["assignment", "file", "quiz"]},
        {"query": "database", "types": ["assignment", "quiz"]},
        {"query": "web development", "types": ["file", "assignment"]},
        {"query": "mathematics", "types": ["assignment", "quiz", "file"]},
        {"query": "physics", "types": ["assignment", "file"]},
        {"query": "statistics", "types": ["assignment", "file", "quiz"]},
        {"query": "programming", "types": ["assignment", "file"]},
        {"query": "software engineering", "types": ["assignment", "file"]},
        {"query": "technical writing", "types": ["assignment", "file"]},
        {"query": "data structures", "types": ["assignment", "quiz"]},
        {"query": "algorithms", "types": ["assignment", "file"]},
        {"query": "calculus", "types": ["assignment", "quiz", "file"]},
        {"query": "project work", "types": ["assignment", "calendar_events"]},
        {"query": "exam preparation", "types": ["quiz", "file", "calendar_events"]},
    ]

    for i, multi_query in enumerate(multi_type_queries):
        course_id = course_ids[i % len(course_ids)]
        search_queries.append(
            {
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "HIGH",
                    "item_types": multi_query["types"],
                    "specific_dates": [],
                    "keywords": multi_query["query"].split(),
                    "query": multi_query["query"],
                }
            }
        )

    # 7. Cross-course searches (10 queries)
    cross_course_queries = [
        "programming assignments",
        "mathematics concepts",
        "project work",
        "exam schedules",
        "lecture materials",
        "lab sessions",
        "homework assignments",
        "study materials",
        "course updates",
        "final projects",
    ]

    for query in cross_course_queries:
        search_queries.append(
            {
                "search_parameters": {
                    "course_id": "all_courses",
                    "time_range": "ALL_TIME",
                    "generality": "HIGH",
                    "item_types": ["assignment", "file", "quiz"],
                    "specific_dates": [],
                    "keywords": query.split(),
                    "query": query,
                }
            }
        )

    # 8. Time-based searches (10 queries)
    time_based_queries = [
        {"query": "recent assignments", "time_range": "RECENT_PAST"},
        {"query": "upcoming quizzes", "time_range": "FUTURE"},
        {"query": "past exams", "time_range": "EXTENDED_PAST"},
        {"query": "current week assignments", "time_range": "RECENT_PAST"},
        {"query": "next week events", "time_range": "FUTURE"},
        {"query": "old lecture notes", "time_range": "EXTENDED_PAST"},
        {"query": "today's schedule", "time_range": "RECENT_PAST"},
        {"query": "future deadlines", "time_range": "FUTURE"},
        {"query": "previous semester work", "time_range": "EXTENDED_PAST"},
        {"query": "this month's tasks", "time_range": "RECENT_PAST"},
    ]

    for i, time_query in enumerate(time_based_queries):
        course_id = course_ids[i % len(course_ids)]
        search_queries.append(
            {
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": time_query["time_range"],
                    "generality": "MEDIUM",
                    "item_types": ["assignment", "quiz", "calendar_events"],
                    "specific_dates": [],
                    "keywords": time_query["query"].split(),
                    "query": time_query["query"],
                }
            }
        )

    # 9. Specific date searches (10 queries)
    specific_date_queries = [
        {"query": "assignments due on 2024-12-15", "dates": ["2024-12-15"]},
        {
            "query": "events between 2024-11-01 and 2024-11-30",
            "dates": ["2024-11-01", "2024-11-30"],
        },
        {"query": "quizzes on 2024-10-20", "dates": ["2024-10-20"]},
        {"query": "deadlines in December 2024", "dates": ["2024-12-01", "2024-12-31"]},
        {"query": "schedule for 2024-09-15", "dates": ["2024-09-15"]},
        {"query": "work due 2024-11-15", "dates": ["2024-11-15"]},
        {"query": "events on 2024-10-31", "dates": ["2024-10-31"]},
        {
            "query": "assignments between 2024-09-01 and 2024-09-15",
            "dates": ["2024-09-01", "2024-09-15"],
        },
        {"query": "exams in January 2025", "dates": ["2025-01-01", "2025-01-31"]},
        {"query": "tasks for 2024-12-01", "dates": ["2024-12-01"]},
    ]

    for i, date_query in enumerate(specific_date_queries):
        course_id = course_ids[i % len(course_ids)]
        search_queries.append(
            {
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "SPECIFIC",
                    "item_types": ["assignment", "quiz", "calendar_events"],
                    "specific_dates": date_query["dates"],
                    "keywords": [
                        word
                        for word in date_query["query"].split()
                        if not any(char.isdigit() for char in word)
                    ],
                    "query": date_query["query"],
                }
            }
        )

    # 10. Keyword-based searches (10 queries)
    keyword_searches = [
        {"query": "find homework assignments", "keywords": ["homework", "assignment"]},
        {"query": "lab work and projects", "keywords": ["lab", "project"]},
        {"query": "exam and quiz materials", "keywords": ["exam", "quiz"]},
        {
            "query": "lecture notes and slides",
            "keywords": ["lecture", "notes", "slides"],
        },
        {"query": "programming and coding", "keywords": ["programming", "coding"]},
        {"query": "data analysis work", "keywords": ["data", "analysis"]},
        {"query": "final project requirements", "keywords": ["final", "project"]},
        {"query": "study guide materials", "keywords": ["study", "guide"]},
        {"query": "course syllabus information", "keywords": ["syllabus", "course"]},
        {"query": "assignment due dates", "keywords": ["assignment", "due"]},
    ]

    for i, keyword_search in enumerate(keyword_searches):
        course_id = course_ids[i % len(course_ids)]
        search_queries.append(
            {
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["assignment", "file", "quiz"],
                    "specific_dates": [],
                    "keywords": keyword_search["keywords"],
                    "query": keyword_search["query"],
                }
            }
        )

    print(f"Generated {len(search_queries)} test search queries")
    return search_queries
