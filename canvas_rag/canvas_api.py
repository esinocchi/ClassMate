
from config import CANVAS_URL, CANVAS_TOKEN   # Fall back to direct import
from canvasapi import Canvas

canvas = Canvas(CANVAS_URL, CANVAS_TOKEN)

def list_courses():
    user = canvas.get_current_user()
    courses = user.get_courses(enrollment_state='active', include=['favorites'])
    print("Your Canvas Courses:")
    for course in courses:
        try:
            print(f"Course ID: {course.id}, Course Name: {course.name}")
        except Exception as e:
            print(f"An error occured for {course}: {e}")
            continue


# Call the function to list courses
if __name__ == "__main__":
    list_courses()