#!/usr/bin/env python3
"""
Realistic Course Data Generator
-------------------------------
This module generates realistic Canvas course data based on actual data patterns
observed in real academic environments.
"""

import random
from datetime import datetime, timedelta
from typing import Dict, List, Any


def generate_realistic_courses() -> List[Dict[str, Any]]:
    """Generate realistic course data based on actual academic patterns."""
    
    # Real course patterns observed in the data
    course_templates = [
        {
            "subject": "CMPSC",
            "numbers": ["311", "465", "221", "132", "331"],
            "titles": [
                "Intro Sys Prog",
                "Data Structures & Algorithms", 
                "Object-Oriented Programming",
                "Programming and Computation II",
                "Computer Organization"
            ],
            "semester": "SP25"
        },
        {
            "subject": "CMPEN", 
            "numbers": ["331", "270", "271"],
            "titles": [
                "Computer Organization and Design",
                "Digital Design Theory",
                "Digital Design Laboratory"
            ],
            "semester": "Spring2025"
        },
        {
            "subject": "EARTH",
            "numbers": ["103N", "104", "105"],
            "titles": [
                "Earth in the Future",
                "Oceanography", 
                "Environmental Geology"
            ],
            "semester": "Spring 2025"
        },
        {
            "subject": "ACCTG",
            "numbers": ["211", "212", "301"],
            "titles": [
                "Financial and Managerial Accounting",
                "Cost Accounting",
                "Intermediate Accounting"
            ],
            "semester": "SP25"
        }
    ]
    
    courses = []
    course_id = 2400000
    
    for template in course_templates:
        for i, (number, title) in enumerate(zip(template["numbers"], template["titles"])):
            # Generate realistic course name patterns
            course_code = f"{template['subject']} {number}"
            if "section" in template.get("variations", ["section"]):
                full_name = f"Section Merge: {course_code}: {title} - {template['semester']}"
                course_code_full = f"Section Merge: {course_code}: {title} - {template['semester']}"
            else:
                full_name = f"{course_code} ({template['semester']})"
                course_code_full = full_name
            
            # Generate detailed syllabus with realistic content
            syllabus = generate_realistic_syllabus(template["subject"], number, title)
            
            course = {
                "id": course_id + i,
                "name": full_name,
                "course_code": course_code_full,
                "original_name": None,
                "default_view": full_name,
                "syllabus_body": syllabus,
                "public_description": None,
                "time_zone": "America/New_York"
            }
            courses.append(course)
    
    return courses


def generate_realistic_syllabus(subject: str, number: str, title: str) -> str:
    """Generate realistic syllabus content with proper HTML formatting."""
    
    if subject == "CMPSC":
        return generate_cs_syllabus(number, title)
    elif subject == "CMPEN":
        return generate_engineering_syllabus(number, title)
    elif subject == "EARTH":
        return generate_earth_science_syllabus(number, title)
    elif subject == "ACCTG":
        return generate_accounting_syllabus(number, title)
    else:
        return generate_generic_syllabus(subject, number, title)


def generate_cs_syllabus(number: str, title: str) -> str:
    """Generate computer science syllabus with realistic content."""
    
    instructors = [
        {"name": "Dr. Suman Saha", "email": "szs339@psu.edu", "title": "Assistant Teaching Professor"},
        {"name": "Dr. Chunhao Wang", "email": "czw5950@psu.edu", "title": "Assistant Professor"},
        {"name": "Dr. John Smith", "email": "jds123@psu.edu", "title": "Professor"}
    ]
    
    instructor = random.choice(instructors)
    
    tas = [
        "Neeraj Karamchandani", "MD Amit Hasan Arovi", "Yilu Dong", 
        "Md Rafi Ur Rashid", "Ashwin Senthil Arumugam"
    ]
    
    selected_tas = random.sample(tas, random.randint(2, 4))
    
    office_hours = generate_office_hours_table(instructor, selected_tas)
    
    syllabus = f'''<div class="ic-Action-header">
<div class="ic-Action-header__Primary">
<h1 class="ic-Action-header__Heading"><span style="font-size: 18pt; color: #e03e2d;">Instructor Information</span></h1>
</div>
</div>
<div id="course_syllabus" class="user_content enhanced">
<p><span><strong>{instructor["name"]}</strong></span><br><span>{instructor["title"]}</span><br><span>Department of Computer Science and Engineering</span><br><strong>Email:</strong><span>&nbsp;<a class="inline_disabled" href="mailto:{instructor["email"]}" target="_blank">{instructor["email"]}</a></span></p>

<h2>Teaching Assistants</h2>
<ul>
{"".join([f'<li><a class="inline_disabled" href="mailto:{ta.lower().replace(" ", "")}@psu.edu" target="_blank">{ta}</a></li>' for ta in selected_tas])}
</ul>

{office_hours}

<h3><span style="color: #e03e2d;">Course Objectives:</span></h3>
<h3><span style="color: var(--ic-brand-font-color-dark); font-family: inherit; font-size: 1rem;">This course explores {title.lower()} concepts and methodologies. Students will gain hands-on experience through lectures, programming assignments, and projects.</span></h3>

<h3><span style="color: #e03e2d;">Grading</span></h3>
<table id="rounded-corner" style="border-collapse: collapse; width: 49.4402%; height: 530px;" border="1" cellpadding="5">
<tbody>
<tr style="height: 34px;">
<th style="width: 96.1369%; height: 34px;">Activity</th>
<th style="width: 3.5461%; height: 34px;">Percentage</th>
</tr>
<tr style="height: 28px;">
<td style="width: 96.1369%; height: 28px;">Course Projects</td>
<td style="width: 3.5461%; height: 28px;">50%</td>
</tr>
<tr style="height: 52px;">
<td style="width: 96.1369%; height: 52px;">Midterm Exams</td>
<td style="width: 3.5461%; height: 52px;">30%</td>
</tr>
<tr style="height: 52px;">
<td style="width: 96.1369%; height: 52px;">Final Exam</td>
<td style="width: 3.5461%; height: 52px;">20%</td>
</tr>
</tbody>
</table>

<h3><span style="color: #e03e2d;">Academic Integrity Statement</span></h3>
<p><strong>The course projects are to be carried out individually.</strong> Students are explicitly not allowed to share information, source code, or even discuss the contents of the projects. Any violation of this policy will be considered cheating and will result in the student receiving an 'F' grade for the project.</p>

<h3><span style="color: #e03e2d;">Lateness Policy</span></h3>
<p>Lab assignments are assessed a 10% per day late penalty, up to a maximum of three days after which a zero grade will be given.</p>

</div>'''
    
    return syllabus


def generate_office_hours_table(instructor: Dict, tas: List[str]) -> str:
    """Generate realistic office hours table."""
    
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    times = ["9:00 AM - 10:00 AM", "11:00 AM - 12:00 PM", "2:00 PM - 3:00 PM", "4:00 PM - 5:00 PM"]
    
    table = '''<h3><span style="color: #e03e2d;">Office Hours</span></h3>
<table style="border-collapse: collapse; width: 99.7897%;" border="1">
<tbody>
<tr>
<td style="width: 21.2961%;"></td>
<td style="width: 11.0934%;"><strong>Monday</strong></td>
<td style="width: 10.6511%;"><strong>Tuesday</strong></td>
<td style="width: 11.3487%;"><strong>Wednesday</strong></td>
<td style="width: 10.9699%;"><strong>Thursday</strong></td>
<td style="width: 11.9213%;"><strong>Friday</strong></td>
</tr>'''
    
    # Add instructor row
    instructor_times = ["", "", "", "", ""]
    selected_days = random.sample(range(5), 2)
    for day in selected_days:
        instructor_times[day] = random.choice(times)
    
    table += f'''<tr>
<td style="width: 21.2961%;">
<p><strong>{instructor["name"]}</strong></p>
<p>Location: W109F Westgate Building</p>
</td>
<td style="width: 11.0934%;">{instructor_times[0]}</td>
<td style="width: 10.6511%;">{instructor_times[1]}</td>
<td style="width: 11.3487%;">{instructor_times[2]}</td>
<td style="width: 10.9699%;">{instructor_times[3]}</td>
<td style="width: 11.9213%;">{instructor_times[4]}</td>
</tr>'''
    
    # Add TA rows
    for ta in tas:
        ta_times = ["", "", "", "", ""]
        selected_days = random.sample(range(5), random.randint(1, 3))
        for day in selected_days:
            ta_times[day] = random.choice(times)
        
        location = random.choice(["300W building", "Zoom Online", "Westgate W136"])
        
        table += f'''<tr>
<td style="width: 21.2961%;">
<p><strong>{ta}</strong></p>
<p>Location: {location}</p>
</td>
<td style="width: 11.0934%;">{ta_times[0]}</td>
<td style="width: 10.6511%;">{ta_times[1]}</td>
<td style="width: 11.3487%;">{ta_times[2]}</td>
<td style="width: 10.9699%;">{ta_times[3]}</td>
<td style="width: 11.9213%;">{ta_times[4]}</td>
</tr>'''
    
    table += '''</tbody>
</table>'''
    
    return table


def generate_engineering_syllabus(number: str, title: str) -> str:
    """Generate engineering syllabus."""
    return f'''<p style="text-align: center;"><strong>Pennsylvania State University</strong></p>
<p style="text-align: center;"><strong>School of Electrical and Computer Science</strong></p>
<p style="text-align: center;"><strong>CMPEN {number} {title}</strong></p>
<p style="text-align: center;"><strong>Spring 2025</strong></p>

<p><strong>Instructor:</strong></p>
<p>Dr. Mohamed Almekkawy</p>
<p>Email: Please Contact me through <strong>"Canvas email"</strong></p>
<p>Office hours: Monday and Tuesday: 9:00 AM – 10:00 AM.</p>

<p><strong>TEXTBOOKS:</strong></p>
<p><strong>REQUIRED:</strong></p>
<ul>
<li>Patterson, David A. and Hennessy, John L. Computer Organization and Design. 5th edition.</li>
</ul>

<p><strong>GRADING:</strong></p>
<p>Homework: 5%</p>
<p>Labs: 20%</p>
<p>Quizzes: 25%</p>
<p>Exams: 45%</p>
<p>Project: 5%</p>'''


def generate_earth_science_syllabus(number: str, title: str) -> str:
    """Generate earth science syllabus."""
    return f'''<p>{title} is an introduction to Earth's systems and environmental challenges. This course explores current issues in earth science and their implications for the future.</p>
<p>The syllabus below is for your convenience. It contains all of the due dates for the assignments, but it does not contain the policies or other details about the course.</p>
<h4><a title="Syllabus" href="#" data-course-type="wikiPages">Earth {number} Complete Syllabus</a></h4>
<p>Please use the Home page to see the course structure, links, and instructions for all of the assignments.</p>'''


def generate_accounting_syllabus(number: str, title: str) -> str:
    """Generate accounting syllabus."""
    return f'''<div style="margin: 0; border: 1px solid #1173CA; display: inline-block;">
<div style="padding: 1.5rem 1.5rem 0 1.5rem;">
<h2 style="font-variant: small-caps; text-align: left;">ACCTG {number} {title}</h2>
</div>
<div style="border: 1px solid #1173CA; background: #1173CA; padding: 0 1rem; clear: both;">
<h3 style="color: #fff; font-variant: small-caps;"><strong>Course Description</strong></h3>
</div>
<div style="padding: 0 1.5rem;">
<p>The objective of this course is to introduce students to the discipline of accounting. This course provides students with an understanding of accounting information and how it is used by various decision-makers.</p>
</div>
</div>'''


def generate_generic_syllabus(subject: str, number: str, title: str) -> str:
    """Generate generic syllabus for other subjects."""
    return f'''<h1>{subject} {number}: {title} Syllabus</h1>
<p>This course covers fundamental concepts in {title.lower()}. Students will learn through lectures, assignments, and hands-on projects.</p>
<p>Prerequisites: Basic understanding of {subject.lower()} concepts.</p>

<h3>Course Objectives</h3>
<p>Upon completion of this course, students will be able to:</p>
<ul>
<li>Understand key concepts in {title.lower()}</li>
<li>Apply theoretical knowledge to practical problems</li>
<li>Demonstrate proficiency in {subject.lower()} methodologies</li>
</ul>

<h3>Grading Policy</h3>
<p>Assignments: 40%</p>
<p>Exams: 40%</p>
<p>Participation: 20%</p>''' 