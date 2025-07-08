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
from vectordb.testing.create_test_courses import generate_realistic_courses


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

    # Generate realistic course data using the realistic_course_data module
    course_subjects = generate_realistic_courses()

    # Realistic assignment templates based on actual Canvas data patterns
    assignment_templates = {
        "CMPSC": [
            {
                "type": "lab",
                "names": ["Lab", "Programming Lab", "Coding Assignment"],
                "descriptions": [
                    "<p>This assignment involves implementing key concepts in systems programming.</p><p><strong>GitHub Classroom Link:</strong> <a href='https://classroom.github.com/a/example'>Accept Assignment</a></p><p><strong>Due Date:</strong> Submit via GitHub by the deadline.</p>",
                    "<p>Complete the programming exercise focusing on data structures and algorithms.</p><p><strong>Submission Requirements:</strong></p><ul><li>Submit source code files</li><li>Include documentation</li><li>Test your implementation</li></ul>",
                    "<p>Implement the required functionality as specified in the assignment description.</p><p><strong>Grading Criteria:</strong></p><ul><li>Correctness: 60%</li><li>Code Quality: 25%</li><li>Documentation: 15%</li></ul>"
                ],
                "submission_types": ["online_upload", "external_tool"]
            },
            {
                "type": "project",
                "names": ["Project", "Final Project", "Course Project"],
                "descriptions": [
                    "<p>This is a comprehensive project that demonstrates your understanding of the course material.</p><p><strong>Project Requirements:</strong></p><ul><li>Implement core functionality</li><li>Write comprehensive tests</li><li>Create user documentation</li><li>Present your solution</li></ul>",
                    "<p>Develop a complete application incorporating multiple course concepts.</p><p><strong>Deliverables:</strong></p><ol><li>Source code repository</li><li>Technical documentation</li><li>Demo video</li><li>Final presentation</li></ol>"
                ],
                "submission_types": ["online_upload", "online_text_entry"]
            }
        ],
        "CMPEN": [
            {
                "type": "homework",
                "names": ["Homework", "Problem Set", "Assignment"],
                "descriptions": [
                    "<p>Complete the assigned problems from the textbook.</p><p><strong>Instructions:</strong></p><ul><li>Show all work</li><li>Provide clear explanations</li><li>Submit as PDF</li></ul>",
                    "<p>Solve the engineering problems related to digital design.</p><p><strong>Submission Format:</strong> Upload a single PDF file with all solutions.</p>"
                ],
                "submission_types": ["online_upload"]
            },
            {
                "type": "lab",
                "names": ["Lab Report", "Laboratory Exercise", "Practical"],
                "descriptions": [
                    "<p>Complete the laboratory exercise and submit a detailed report.</p><p><strong>Report Requirements:</strong></p><ul><li>Experimental procedure</li><li>Data analysis</li><li>Conclusions</li></ul>",
                    "<p>Perform the assigned laboratory work and document your findings.</p><p><strong>Due Date:</strong> Submit within one week of lab session.</p>"
                ],
                "submission_types": ["online_upload"]
            }
        ],
        "EARTH": [
            {
                "type": "assignment",
                "names": ["Assignment", "Research Assignment", "Case Study"],
                "descriptions": [
                    "<p>Analyze the environmental case study and provide your assessment.</p><p><strong>Requirements:</strong></p><ul><li>2-3 page analysis</li><li>Use course concepts</li><li>Cite relevant sources</li></ul>",
                    "<p>Complete the earth science research project on the assigned topic.</p><p><strong>Format:</strong> Submit as Word document or PDF.</p>"
                ],
                "submission_types": ["online_upload", "online_text_entry"]
            }
        ],
        "ACCTG": [
            {
                "type": "homework",
                "names": ["Homework", "Problem Set", "Practice Problems"],
                "descriptions": [
                    "<p>Complete the accounting problems from Chapter {chapter}.</p><p><strong>Instructions:</strong></p><ul><li>Show all calculations</li><li>Use proper accounting format</li><li>Submit Excel file or PDF</li></ul>",
                    "<p>Solve the financial accounting exercises.</p><p><strong>Grading:</strong> Based on accuracy and presentation.</p>"
                ],
                "submission_types": ["online_upload"]
            }
        ]
    }

    # Generate assignments
    assignments = []
    assignment_id = 20000000
    base_date = datetime(2024, 8, 15)

    for course in course_subjects:
        # Extract subject from course code for template selection
        course_code = course.get("course_code", "")
        subject = course_code.split()[0] if course_code else "GENERIC"
        
        # Get appropriate templates for this subject
        subject_templates = assignment_templates.get(subject, assignment_templates.get("CMPSC", []))
        if not subject_templates:
            # Fallback to generic templates
            subject_templates = [
                {
                    "type": "assignment",
                    "names": ["Assignment", "Homework", "Exercise"],
                    "descriptions": ["<p>Complete the assigned work for this course.</p>"],
                    "submission_types": ["online_upload"]
                }
            ]

        # Generate 15-20 assignments per course (more realistic number)
        num_assignments = random.randint(15, 20)
        for i in range(num_assignments):
            template = random.choice(subject_templates)
            name_base = random.choice(template["names"])
            description = random.choice(template["descriptions"])

            # Add variety to names and descriptions
            if template["type"] in ["homework", "lab", "assignment"]:
                name = f"{name_base} {i + 1}"
            else:
                name = f"{name_base}"
                
            # Format description with chapter numbers for accounting
            if subject == "ACCTG" and "{chapter}" in description:
                chapter_num = random.randint(1, 15)
                description = description.format(chapter=chapter_num)

            # Vary due dates realistically (spread over semester)
            days_offset = random.randint(7, 120)  # Start assignments after first week
            due_date = base_date + timedelta(days=days_offset)

            assignments.append(
                {
                    "id": str(assignment_id),
                    "type": None,
                    "name": name,
                    "description": description,
                    "due_at": due_date.strftime("%Y-%m-%dT23:59:00Z"),
                    "course_id": course["id"],
                    "submission_types": template.get("submission_types", ["online_text_entry", "online_upload"]),
                    "can_submit": None,
                    "graded_submission_exist": None,
                    "graded_submissions_exist": None,
                    "module_id": 5475163 + i,
                    "module_name": f"Week {(i // 3) + 1}",
                    "content": [],
                }
            )
            assignment_id += 1

    # Realistic file templates based on actual Canvas data patterns
    file_templates = {
        "CMPSC": [
            {
                "type": "lecture",
                "names": ["Lecture", "Slides", "Notes"],
                "patterns": ["Lecture {num}", "Week {week} Slides", "Chapter {chapter} Notes"],
                "extensions": [".pdf", ".pptx"],
                "folders": ["Lectures", "Course Materials", "Slides"]
            },
            {
                "type": "lab",
                "names": ["Lab", "Assignment", "Exercise"],
                "patterns": ["Lab {num}", "Programming Assignment {num}", "Exercise {num}"],
                "extensions": [".pdf", ".zip", ".md"],
                "folders": ["Labs", "Assignments", "Programming"]
            },
            {
                "type": "code",
                "names": ["Code", "Template", "Example"],
                "patterns": ["starter_code_{num}", "template_{name}", "example_{topic}"],
                "extensions": [".c", ".cpp", ".py", ".java", ".zip"],
                "folders": ["Code Examples", "Templates", "Resources"]
            }
        ],
        "CMPEN": [
            {
                "type": "lecture",
                "names": ["Lecture", "Notes", "Slides"],
                "patterns": ["Lecture {num}", "Chapter {chapter}", "Topic {num}"],
                "extensions": [".pdf", ".pptx"],
                "folders": ["Lectures", "Course Notes"]
            },
            {
                "type": "lab",
                "names": ["Lab", "Manual", "Guide"],
                "patterns": ["Lab {num} Manual", "Lab Guide {num}", "Experiment {num}"],
                "extensions": [".pdf", ".docx"],
                "folders": ["Lab Manuals", "Experiments"]
            }
        ],
        "EARTH": [
            {
                "type": "reading",
                "names": ["Reading", "Article", "Chapter"],
                "patterns": ["Chapter {chapter}", "Reading {num}", "Article {num}"],
                "extensions": [".pdf", ".docx"],
                "folders": ["Readings", "Course Materials"]
            },
            {
                "type": "data",
                "names": ["Data", "Dataset", "Case Study"],
                "patterns": ["Dataset {num}", "Case Study {num}", "Data Analysis {num}"],
                "extensions": [".csv", ".xlsx", ".pdf"],
                "folders": ["Data", "Case Studies"]
            }
        ],
        "ACCTG": [
            {
                "type": "reading",
                "names": ["Chapter", "Reading", "Material"],
                "patterns": ["Chapter {chapter}", "Reading Assignment {num}", "Study Material {num}"],
                "extensions": [".pdf", ".docx"],
                "folders": ["Textbook", "Readings"]
            },
            {
                "type": "practice",
                "names": ["Practice", "Problems", "Exercises"],
                "patterns": ["Practice Problems {num}", "Chapter {chapter} Exercises", "Problem Set {num}"],
                "extensions": [".pdf", ".xlsx"],
                "folders": ["Practice Problems", "Exercises"]
            }
        ]
    }

    # Generate files
    files = []
    file_id = 30000000

    for course in course_subjects:
        # Extract subject from course code for template selection
        course_code = course.get("course_code", "")
        subject = course_code.split()[0] if course_code else "GENERIC"
        
        # Get appropriate file templates for this subject
        subject_file_templates = file_templates.get(subject, file_templates.get("CMPSC", []))
        if not subject_file_templates:
            # Fallback to generic templates
            subject_file_templates = [
                {
                    "type": "document",
                    "names": ["Document", "File", "Material"],
                    "patterns": ["Document {num}"],
                    "extensions": [".pdf", ".docx"],
                    "folders": ["Course Materials"]
                }
            ]

        # Generate 12-18 files per course (more realistic number)
        num_files = random.randint(12, 18)
        for i in range(num_files):
            template = random.choice(subject_file_templates)
            pattern = random.choice(template["patterns"])
            extension = random.choice(template["extensions"])
            folder = random.choice(template["folders"])

            # Generate realistic file names using patterns
            if "{num}" in pattern:
                display_name = pattern.format(num=i + 1) + extension
            elif "{week}" in pattern:
                week_num = (i // 2) + 1  # 2 files per week roughly
                display_name = pattern.format(week=week_num) + extension
            elif "{chapter}" in pattern:
                chapter_num = (i // 3) + 1  # 3 files per chapter roughly
                display_name = pattern.format(chapter=chapter_num) + extension
            elif "{name}" in pattern:
                names = ["basics", "advanced", "practice", "review", "final"]
                name = random.choice(names)
                display_name = pattern.format(name=name) + extension
            elif "{topic}" in pattern:
                topics = ["intro", "algorithms", "structures", "systems", "design"]
                topic = random.choice(topics)
                display_name = pattern.format(topic=topic) + extension
            else:
                display_name = f"{pattern} {i + 1}{extension}"

            filename = display_name.lower().replace(" ", "_")

            # Realistic file sizes based on type
            if extension in [".pdf", ".pptx"]:
                file_size = random.randint(512000, 10485760)  # 512KB to 10MB
            elif extension in [".zip"]:
                file_size = random.randint(1048576, 52428800)  # 1MB to 50MB
            elif extension in [".c", ".cpp", ".py", ".java"]:
                file_size = random.randint(1024, 102400)  # 1KB to 100KB
            elif extension in [".csv", ".xlsx"]:
                file_size = random.randint(10240, 1048576)  # 10KB to 1MB
            else:
                file_size = random.randint(10240, 5242880)  # 10KB to 5MB

            files.append(
                {
                    "course_id": course["id"],
                    "id": str(file_id),
                    "type": None,
                    "folder_id": f"folder_{subject.lower()}_{folder.lower().replace(' ', '_')}",
                    "display_name": display_name,
                    "filename": filename,
                    "url": f"http://example.com/files/{file_id}/download?download_frd=1",
                    "size": file_size,
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

    # Generate announcements with realistic HTML content
    announcements = []
    announcement_id = 40000000
    announcement_templates = [
        {
            "title": "Welcome to {course_name}",
            "message": "<p>Welcome to <strong>{course_name}</strong>!</p><p>Please take some time to review the syllabus and familiarize yourself with the course structure. All course materials are available in Canvas.</p><p>If you have any questions, please don't hesitate to reach out during office hours or via email.</p><p>Looking forward to a great semester!</p><p>Best regards,<br>Your Instructor</p>"
        },
        {
            "title": "Assignment Reminder - {assignment_type}",
            "message": "<p><strong>Reminder:</strong> {assignment_type} is due <strong>next week</strong>.</p><p>Please make sure to:</p><ul><li>Submit your work on time</li><li>Follow the submission guidelines</li><li>Check your work before submitting</li></ul><p>Late submissions will be penalized according to the course policy.</p>"
        },
        {
            "title": "New Course Materials Posted",
            "message": "<p>New lecture materials have been posted for <strong>{course_name}</strong>.</p><p>You can find them in the <em>Files</em> section under the appropriate week folder.</p><p>Please review these materials before our next class session.</p>"
        },
        {
            "title": "Office Hours Update",
            "message": "<p><strong>Office Hours This Week:</strong></p><p>I will be holding office hours on <strong>{day} from 2:00 PM - 4:00 PM</strong> in my office.</p><p>Feel free to drop by if you have questions about the course material, assignments, or need clarification on any topics.</p><p>You can also schedule an appointment if these times don't work for you.</p>"
        },
        {
            "title": "Exam Information - {exam_type}",
            "message": "<p><strong>Important Update:</strong> Information about the upcoming <strong>{exam_type}</strong> in {course_name}.</p><p><strong>Exam Details:</strong></p><ul><li>Date: [To be announced]</li><li>Time: During regular class time</li><li>Format: In-person written exam</li><li>Coverage: Chapters 1-{chapter_num}</li></ul><p>Study guide will be posted next week.</p>"
        },
        {
            "title": "Group Project Assignments",
            "message": "<p><strong>Group Project Teams</strong> have been posted!</p><p>Please check the <em>People</em> section to see your team assignments.</p><p><strong>Next Steps:</strong></p><ol><li>Contact your team members</li><li>Schedule your first team meeting</li><li>Review the project requirements</li><li>Submit your project proposal by the deadline</li></ol>"
        },
        {
            "title": "Lab Session Schedule Change",
            "message": "<p><strong>Schedule Update:</strong> Lab session for <strong>{course_name}</strong> has been moved.</p><p><strong>New Time:</strong> {new_time}</p><p><strong>Location:</strong> Same lab room</p><p>Please update your calendars accordingly. If you have conflicts with the new time, please contact me as soon as possible.</p>"
        },
        {
            "title": "Reading Assignment - Chapter {chapter_num}",
            "message": "<p><strong>Reading Assignment for Next Week:</strong></p><p>Please read <strong>Chapter {chapter_num}</strong> from the textbook before our next class.</p><p><strong>Focus Areas:</strong></p><ul><li>Key concepts and definitions</li><li>Examples and case studies</li><li>End-of-chapter questions</li></ul><p>We will discuss this material in class and it will be covered on the next exam.</p>"
        },
        {
            "title": "Midterm Exam Results Available",
            "message": "<p><strong>Midterm Exam Results</strong> are now available in the gradebook.</p><p>Overall, the class performed well with an average score of 82%.</p><p><strong>If you have questions about your grade:</strong></p><ul><li>Review the answer key (posted in Files)</li><li>Come to office hours for discussion</li><li>Email me if you need clarification</li></ul><p>Remember, this is just one component of your final grade.</p>"
        },
        {
            "title": "Final Project Presentations",
            "message": "<p><strong>Final Project Presentations</strong> will be held during the last week of class.</p><p><strong>Presentation Schedule:</strong></p><ul><li>Each team will have 10 minutes to present</li><li>5 minutes for questions and discussion</li><li>All team members must participate</li></ul><p><strong>Presentation Requirements:</strong></p><ul><li>Demonstrate your working solution</li><li>Explain your design decisions</li><li>Discuss challenges and solutions</li></ul><p>Detailed rubric will be posted soon.</p>"
        }
    ]

    for course in course_subjects:
        # Generate 8-10 announcements per course (more realistic number)
        num_announcements = random.randint(8, 10)
        for i in range(num_announcements):
            template = random.choice(announcement_templates)

            # Fill in template variables safely
            format_vars = {
                "course_name": course["name"],
                "assignment_type": random.choice(
                    ["Assignment", "Homework", "Lab", "Project"]
                ),
                "exam_type": random.choice(["Midterm Exam", "Final Exam", "Quiz"]),
                "day": random.choice(
                    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                ),
                "new_time": random.choice(["10:00 AM", "2:00 PM", "3:00 PM"]),
                "chapter_num": random.randint(1, 15),
            }
            
            # Format title and message, handling missing variables gracefully
            try:
                title = template["title"].format(**format_vars)
            except KeyError as e:
                title = template["title"]  # Use original if formatting fails
                
            try:
                message = template["message"].format(**format_vars)
            except KeyError as e:
                message = template["message"]  # Use original if formatting fails

            posted_date = base_date + timedelta(days=random.randint(1, 100))

            announcements.append(
                {
                    "id": str(announcement_id),
                    "title": title,
                    "message": message,
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
                    "title": f"{template['title']} - {course.get('course_code', course['name'])}",
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

    # Create courses_selected dictionary from generated courses
    courses_selected = {str(course["id"]): course["name"] for course in course_subjects}
    
    # Set courses variable for data compilation
    courses = course_subjects

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


def generate_test_search_queries(json_file_path: Path = None) -> List[Dict[str, Any]]:
    """Generate a comprehensive list of test search queries based on actual data in the JSON file.
    
    This function reads the extensive test JSON file and creates queries based on the actual
    courses, assignments, files, announcements, quizzes, and events that were generated.
    This ensures every query will return relevant results.

    Note: This function generates realistic search queries that mimic how students would
    actually interact with an AI assistant in Canvas. The queries are conversational
    and natural, like "Can you find my homework for CS 101?" rather than technical
    search parameters.


    Args:
        json_file_path: Path to the extensive test JSON file. If None, creates temp file.

    Returns:
        List of search parameter dictionaries covering various search scenarios.

    Raises:
        FileNotFoundError: If the JSON file doesn't exist.
        json.JSONDecodeError: If the JSON file is malformed.
    """
    
    # If no path provided, create a temporary file
    if json_file_path is None:
        import tempfile
        temp_dir = Path(tempfile.mkdtemp())
        json_file_path = temp_dir / "temp_extensive_data.json"
        create_extensive_test_json(json_file_path)
    
    # Read the actual generated data
    if not json_file_path.exists():
        raise FileNotFoundError(f"JSON file not found: {json_file_path}")
    
    with open(json_file_path, 'r') as f:
        data = json.load(f)
    
    courses = data.get("courses", [])
    assignments = data.get("assignments", [])
    files = data.get("files", [])
    announcements = data.get("announcements", [])
    quizzes = data.get("quizzes", [])
    calendar_events = data.get("calendar_events", [])
    
    search_queries = []
    
    # Extract actual course IDs and subjects
    actual_course_ids = [str(course["id"]) for course in courses]
    
    # 1. Course/Syllabus searches based on actual courses
    for course in courses[:3]:  # Limit to first 3 courses to avoid too many queries
        course_id = str(course["id"])
        course_name = course.get("name", "")
        course_code = course.get("course_code", "")
        
        search_queries.append({
            "search_parameters": {
                "course_id": course_id,
                "time_range": "ALL_TIME",
                "generality": "MEDIUM",
                "item_types": ["syllabus"],
                "specific_dates": [],
                "keywords": ["syllabus", "course", "instructor"],
                "query": f"Can you show me the syllabus for {course_name}?",
            }
        })

    # 2. Assignment searches based on actual assignment names and descriptions
    for assignment in random.sample(assignments, min(20, len(assignments))):  # Sample 20 assignments
        assignment_name = assignment.get("name", "")
        assignment_description = assignment.get("description", "")
        course_id = str(assignment.get("course_id", ""))
        
        # Create queries based on assignment names
        if assignment_name:
            # Extract key terms from assignment name
            name_words = [word.lower() for word in assignment_name.split() if len(word) > 2]
            search_queries.append({
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME", 
                    "generality": "MEDIUM",
                    "item_types": ["assignment"],
                    "specific_dates": [],
                    "keywords": name_words[:3],  # Use first 3 meaningful words
                    "query": f"Where can I find the {assignment_name} assignment?",
                }
            })
        
        # Create queries based on assignment types/content
        if "lab" in assignment_name.lower():
            search_queries.append({
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM", 
                    "item_types": ["assignment"],
                    "specific_dates": [],
                    "keywords": ["lab"],
                    "query": "What lab assignments do I have?",
                }
            })
        elif "project" in assignment_name.lower():
            search_queries.append({
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["assignment"], 
                    "specific_dates": [],
                    "keywords": ["project"],
                    "query": "Can you show me my project assignments?",
                }
            })
        elif "homework" in assignment_name.lower():
            search_queries.append({
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["assignment"],
                    "specific_dates": [],
                    "keywords": ["homework"],
                    "query": "What homework do I need to complete?",
                }
            })

    # 3. File searches based on actual file names
    for file_item in random.sample(files, min(15, len(files))):  # Sample 15 files
        file_name = file_item.get("display_name", "")
        course_id = str(file_item.get("course_id", ""))
        
        if file_name:
            # Extract meaningful terms from filename
            name_parts = file_name.replace("_", " ").replace("-", " ").split()
            keywords = [part.lower() for part in name_parts if len(part) > 2 and not part.isdigit()]
            
            search_queries.append({
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["file"],
                    "specific_dates": [],
                    "keywords": keywords[:3],  # Use first 3 meaningful words
                    "query": f"Do you have the {file_name} file?",
                }
            })
        
        # Create generic file type queries
        if ".pdf" in file_name.lower():
            search_queries.append({
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["file"],
                    "specific_dates": [],
                    "keywords": ["pdf", "document"],
                    "query": "Can you find PDF documents for this course?",
                }
            })
        elif "lecture" in file_name.lower():
            search_queries.append({
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["file"],
                    "specific_dates": [],
                    "keywords": ["lecture"],
                    "query": "Where are the lecture materials?",
                }
            })

    # 4. Quiz searches based on actual quiz titles
    for quiz in random.sample(quizzes, min(10, len(quizzes))):  # Sample 10 quizzes
        quiz_title = quiz.get("title", "")
        course_id = str(quiz.get("course_id", ""))
        
        if quiz_title:
            # Extract key terms from quiz title
            title_words = [word.lower() for word in quiz_title.split() if len(word) > 2]
            search_queries.append({
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["quiz"],
                    "specific_dates": [],
                    "keywords": title_words[:3],
                    "query": f"When is the {quiz_title}?",
                }
            })
        
        # Create queries based on quiz types
        if "midterm" in quiz_title.lower():
            search_queries.append({
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["quiz"],
                    "specific_dates": [],
                    "keywords": ["midterm", "exam"],
                    "query": "When are my midterm exams scheduled?",
                }
            })
        elif "final" in quiz_title.lower():
            search_queries.append({
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["quiz"],
                    "specific_dates": [],
                    "keywords": ["final", "exam"],
                    "query": "What are the dates for my final exams?",
                }
            })

    # 5. Calendar event searches based on actual events
    for event in random.sample(calendar_events, min(10, len(calendar_events))):  # Sample 10 events
        event_title = event.get("title", "")
        course_id = str(event.get("course_id", ""))
        
        if event_title:
            # Extract key terms from event title
            title_words = [word.lower() for word in event_title.split() if len(word) > 2]
            search_queries.append({
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["calendar_events"],
                    "specific_dates": [],
                    "keywords": title_words[:3],
                    "query": f"When is the next {event_title}?",
                }
            })
        
        # Create queries based on event types
        if "lecture" in event_title.lower():
            search_queries.append({
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["calendar_events"],
                    "specific_dates": [],
                    "keywords": ["lecture"],
                    "query": "What are my lecture times?",
                }
            })
        elif "office hours" in event_title.lower():
            search_queries.append({
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["calendar_events"],
                    "specific_dates": [],
                    "keywords": ["office", "hours"],
                    "query": "When are office hours available?",
                }
            })

    # 6. Announcement searches based on actual announcements
    for announcement in random.sample(announcements, min(10, len(announcements))):  # Sample 10 announcements
        announcement_title = announcement.get("title", "")
        course_id = str(announcement.get("course_id", ""))
        
        if announcement_title:
            # Extract key terms from announcement title
            title_words = [word.lower() for word in announcement_title.split() if len(word) > 2]
            search_queries.append({
                "search_parameters": {
                    "course_id": course_id,
                    "time_range": "ALL_TIME",
                    "generality": "MEDIUM",
                    "item_types": ["announcement"],
                    "specific_dates": [],
                    "keywords": title_words[:3],
                    "query": f"Can you show me the announcement about {announcement_title}?",
                }
            })
    
    # 7. Multi-type searches based on actual course subjects
    course_subjects_map = {}
    for course in courses:
        course_code = course.get("course_code", "")
        subject = course_code.split()[0] if course_code else "GENERIC"
        course_id = str(course["id"])
        if subject not in course_subjects_map:
            course_subjects_map[subject] = course_id
    
    multi_type_queries = []
    if "CMPSC" in course_subjects_map:
        multi_type_queries.extend([
            {"query": "programming", "types": ["assignment", "file"], "course_id": course_subjects_map["CMPSC"]},
            {"query": "lab", "types": ["assignment", "file"], "course_id": course_subjects_map["CMPSC"]},
            {"query": "project", "types": ["assignment", "calendar_events"], "course_id": course_subjects_map["CMPSC"]},
        ])
    if "CMPEN" in course_subjects_map:
        multi_type_queries.extend([
            {"query": "engineering", "types": ["assignment", "file"], "course_id": course_subjects_map["CMPEN"]},
            {"query": "design", "types": ["assignment", "quiz"], "course_id": course_subjects_map["CMPEN"]},
        ])
    if "EARTH" in course_subjects_map:
        multi_type_queries.extend([
            {"query": "environmental", "types": ["assignment", "file"], "course_id": course_subjects_map["EARTH"]},
            {"query": "case study", "types": ["assignment", "file"], "course_id": course_subjects_map["EARTH"]},
        ])
    if "ACCTG" in course_subjects_map:
        multi_type_queries.extend([
            {"query": "accounting", "types": ["assignment", "quiz"], "course_id": course_subjects_map["ACCTG"]},
            {"query": "financial", "types": ["assignment", "file"], "course_id": course_subjects_map["ACCTG"]},
        ])

    for multi_query in multi_type_queries:
        search_queries.append({
            "search_parameters": {
                "course_id": multi_query["course_id"],
                "time_range": "ALL_TIME",
                "generality": "HIGH",
                "item_types": multi_query["types"],
                "specific_dates": [],
                "keywords": multi_query["query"].split(),
                "query": f"What {multi_query['query']} materials do I have?",
            }
        })

    # 8. Cross-course searches based on realistic student queries
    # Create natural cross-course queries that students would actually ask
    cross_course_queries = [
        {
            "keywords": ["homework", "assignment"],
            "query": "What homework do I have across all my classes?",
            "types": ["assignment"]
        },
        {
            "keywords": ["quiz", "test", "exam"],
            "query": "Do I have any upcoming tests or quizzes?",
            "types": ["quiz", "assignment"]
        },
        {
            "keywords": ["project", "final"],
            "query": "What projects are due soon in any of my courses?",
            "types": ["assignment"]
        },
        {
            "keywords": ["pdf", "reading"],
            "query": "Can you find reading materials I need to review?",
            "types": ["file"]
        },
        {
            "keywords": ["lab", "laboratory"],
            "query": "What lab work do I have coming up?",
            "types": ["assignment", "file"]
        },
        {
            "keywords": ["presentation", "slides"],
            "query": "Do I have any presentations to prepare for?",
            "types": ["assignment", "file"]
        },
        {
            "keywords": ["study", "guide", "review"],
            "query": "Are there any study guides available for my courses?",
            "types": ["file", "assignment"]
        }
    ]
    
    # Create cross-course queries using realistic student language
    for cross_query in cross_course_queries:
        search_queries.append({
            "search_parameters": {
                "course_id": "all_courses",
                "time_range": "ALL_TIME",
                "generality": "HIGH",
                "item_types": cross_query["types"],
                "specific_dates": [],
                "keywords": cross_query["keywords"],
                "query": cross_query["query"],
            }
        })

    # 9. Time-based searches using actual due dates from data
    time_based_queries = [
        {"query": "assignments", "time_range": "RECENT_PAST", "types": ["assignment"]},
        {"query": "quizzes", "time_range": "FUTURE", "types": ["quiz"]},
        {"query": "events", "time_range": "RECENT_PAST", "types": ["calendar_events"]},
    ]

    for time_query in time_based_queries:
        # Use a random course for time-based searches
        course_id = random.choice(actual_course_ids) if actual_course_ids else "all_courses"
        search_queries.append({
            "search_parameters": {
                "course_id": course_id,
                "time_range": time_query["time_range"],
                "generality": "MEDIUM",
                "item_types": time_query["types"],
                "specific_dates": [],
                "keywords": [time_query["query"]],
                "query": f"What {time_query['query']} do I have {time_query['time_range'].lower().replace('_', ' ')}?",
            }
        })

    # 10. Specific date searches based on actual due dates in the data
    # Extract some actual dates from assignments and quizzes
    actual_dates = []
    for assignment in assignments[:5]:
        due_date = assignment.get("due_at", "")
        if due_date:
            # Extract just the date part
            date_part = due_date.split("T")[0]
            actual_dates.append(date_part)
    
    for quiz in quizzes[:3]:
        due_date = quiz.get("due_at", "")
        if due_date:
            date_part = due_date.split("T")[0]
            actual_dates.append(date_part)
    
    # Create queries for actual dates found in the data
    for date in actual_dates[:5]:  # Limit to 5 date queries
        course_id = random.choice(actual_course_ids) if actual_course_ids else "all_courses"
        search_queries.append({
            "search_parameters": {
                "course_id": course_id,
                "time_range": "ALL_TIME",
                "generality": "SPECIFIC",
                "item_types": ["assignment", "quiz", "calendar_events"],
                "specific_dates": [date],
                "keywords": ["due", "assignment", "quiz"],
                "query": f"What's due on {date}?",
            }
        })

    # Clean up temporary file if we created one
    if json_file_path and "temp_extensive_data.json" in str(json_file_path):
        try:
            json_file_path.unlink()
            json_file_path.parent.rmdir()
        except:
            pass  # Ignore cleanup errors
    
    print(f"Generated {len(search_queries)} test search queries based on actual data")
    return search_queries
