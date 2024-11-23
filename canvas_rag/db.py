# db.py
import sqlite3
import chromadb
from datetime import datetime
from typing import Dict, List, Any, Optional


class CanvasDatabase:
    def __init__(self):
        # Initialize SQLite
        self.sqlite_conn = sqlite3.connect('canvas.db')
        self.cursor = self.sqlite_conn.cursor()
        
        # Initialize ChromaDB for vector search
        self.chroma_client = chromadb.Client()
        self.collection = self.chroma_client.get_or_create_collection(
            name="canvas_content"
        )
        
        # Create all tables
        self.init_tables()

    def init_tables(self):
        """Initialize comprehensive database structure for all Canvas data"""
        self.cursor.executescript('''
        -- Courses table
        CREATE TABLE IF NOT EXISTS courses (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            code TEXT,
            term_id TEXT,
            start_date TEXT,
            end_date TEXT,
            description TEXT,
            syllabus_content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Assignments table
        CREATE TABLE IF NOT EXISTS assignments (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            title TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            points_possible REAL,
            submission_types TEXT,
            grading_type TEXT,
            position INTEGER,
            group_category_id TEXT,
            allowed_attempts INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        );

        -- Modules table
        CREATE TABLE IF NOT EXISTS modules (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            name TEXT NOT NULL,
            position INTEGER,
            prerequisites TEXT,
            unlock_date TEXT,
            require_sequential_progress BOOLEAN,
            published BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        );

        -- Module Items table
        CREATE TABLE IF NOT EXISTS module_items (
            id TEXT PRIMARY KEY,
            module_id TEXT,
            title TEXT NOT NULL,
            type TEXT,
            content_id TEXT,
            position INTEGER,
            indent_level INTEGER,
            external_url TEXT,
            completion_requirement TEXT,
            published BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (module_id) REFERENCES modules (id)
        );

        -- Announcements table
        CREATE TABLE IF NOT EXISTS announcements (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            title TEXT NOT NULL,
            message TEXT,
            author_id TEXT,
            posted_date TEXT,
            delayed_post_date TEXT,
            published BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        );

        -- Discussion Topics table
        CREATE TABLE IF NOT EXISTS discussions (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            title TEXT NOT NULL,
            message TEXT,
            author_id TEXT,
            posted_date TEXT,
            due_date TEXT,
            lock_date TEXT,
            pinned BOOLEAN,
            locked BOOLEAN,
            allow_rating BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        );

        -- Discussion Posts table
        CREATE TABLE IF NOT EXISTS discussion_posts (
            id TEXT PRIMARY KEY,
            discussion_id TEXT,
            user_id TEXT,
            parent_id TEXT,
            message TEXT,
            posted_date TEXT,
            edited_date TEXT,
            rating_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (discussion_id) REFERENCES discussions (id),
            FOREIGN KEY (parent_id) REFERENCES discussion_posts (id)
        );

        -- Files table
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            filename TEXT NOT NULL,
            display_name TEXT,
            content_type TEXT,
            file_size INTEGER,
            folder_path TEXT,
            file_data BLOB,
            extracted_text TEXT,
            url TEXT,
            thumbnail_url TEXT,
            modified_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        );

        -- Pages table
        CREATE TABLE IF NOT EXISTS pages (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            title TEXT NOT NULL,
            body TEXT,
            editing_roles TEXT,
            published BOOLEAN,
            front_page BOOLEAN,
            todo_date TEXT,
            edited_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        );

        -- Submissions table
        CREATE TABLE IF NOT EXISTS submissions (
            id TEXT PRIMARY KEY,
            assignment_id TEXT,
            user_id TEXT,
            submitted_date TEXT,
            grade TEXT,
            score REAL,
            feedback TEXT,
            submission_type TEXT,
            submission_data TEXT,
            late BOOLEAN,
            missing BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assignment_id) REFERENCES assignments (id)
        );

        -- Calendar Events table
        CREATE TABLE IF NOT EXISTS calendar_events (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            title TEXT NOT NULL,
            description TEXT,
            start_date TEXT,
            end_date TEXT,
            location TEXT,
            all_day BOOLEAN,
            recurring BOOLEAN,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        );

        -- Grades table
        CREATE TABLE IF NOT EXISTS grades (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            assignment_id TEXT,
            user_id TEXT,
            score REAL,
            grade TEXT,
            graded_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id),
            FOREIGN KEY (assignment_id) REFERENCES assignments (id)
        );

        -- Rubrics table
        CREATE TABLE IF NOT EXISTS rubrics (
            id TEXT PRIMARY KEY,
            course_id TEXT,
            title TEXT NOT NULL,
            description TEXT,
            points_possible REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        );

        -- Rubric Criteria table
        CREATE TABLE IF NOT EXISTS rubric_criteria (
            id TEXT PRIMARY KEY,
            rubric_id TEXT,
            description TEXT,
            points REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (rubric_id) REFERENCES rubrics (id)
        );

        -- Create necessary indices for better performance
        CREATE INDEX IF NOT EXISTS idx_assignments_course 
        ON assignments (course_id);
        
        CREATE INDEX IF NOT EXISTS idx_modules_course 
        ON modules (course_id);
        
        CREATE INDEX IF NOT EXISTS idx_discussions_course 
        ON discussions (course_id);
        
        CREATE INDEX IF NOT EXISTS idx_pages_course 
        ON pages (course_id);
        
        CREATE INDEX IF NOT EXISTS idx_files_course 
        ON files (course_id);
        
        CREATE INDEX IF NOT EXISTS idx_submissions_assignment 
        ON submissions (assignment_id);
        
        CREATE INDEX IF NOT EXISTS idx_grades_course 
        ON grades (course_id);
        
        CREATE INDEX IF NOT EXISTS idx_grades_assignment 
        ON grades (assignment_id);
        
        CREATE INDEX IF NOT EXISTS idx_calendar_events_course 
        ON calendar_events (course_id);
        
        CREATE INDEX IF NOT EXISTS idx_announcements_course 
        ON announcements (course_id);
    ''')
        self.sqlite_conn.commit()

    def store_canvas_item(self, item_type: str, data: Dict[str, Any]) -> bool:
        """Store any type of Canvas item"""
        try:
            # Store in SQLite
            self._store_in_sqlite(item_type, data)

            # Prepare content for ChromaDB
            content = self._prepare_content(item_type, data)
            if content:
                self.collection.add(
                    documents=[content],
                    metadatas=[{
                        "type": item_type,
                        "item_id": data['id'],
                        "course_id": data.get('course_id'),
                        "timestamp": datetime.now().isoformat()
                    }],
                    ids=[f"{item_type}_{data['id']}"]
                )

            self.sqlite_conn.commit()
            return True

        except Exception as e:
            print(f"Error storing {item_type}: {e}")
            self.sqlite_conn.rollback()
            return False

    def store_file(self, course_id: str, file_name: str, file_data: bytes, content_type: str) -> Optional[str]:
        """Store file with extracted text"""
        try:
            file_id = f"file_{course_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            extracted_text = self._extract_file_text(file_data, content_type)

            self.cursor.execute('''
                INSERT INTO files (id, course_id, filename, content_type, file_size, file_data, extracted_text)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_id,
                course_id,
                file_name,
                content_type,
                len(file_data),
                file_data,
                extracted_text
            ))

            if extracted_text:
                self.collection.add(
                    documents=[extracted_text],
                    metadatas=[{
                        "type": "file",
                        "file_id": file_id,
                        "course_id": course_id,
                        "filename": file_name,
                        "content_type": content_type,
                        "timestamp": datetime.now().isoformat()
                    }],
                    ids=[file_id]
                )

            self.sqlite_conn.commit()
            return file_id

        except Exception as e:
            print(f"Error storing file: {e}")
            self.sqlite_conn.rollback()
            return None

    def query_content(self, query_text: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Query content using ChromaDB's similarity search"""
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            
            formatted_results = []
            for i in range(len(results['documents'][0])):
                metadata = results['metadatas'][0][i]
                
                # Get additional details from SQLite
                details = self._get_item_details(
                    metadata['type'],
                    metadata.get('item_id') or metadata.get('file_id')
                )
                
                formatted_results.append({
                    'content': results['documents'][0][i],
                    'metadata': metadata,
                    'details': details,
                    'id': results['ids'][0][i]
                })
            
            return formatted_results

        except Exception as e:
            print(f"Error querying content: {e}")
            return []

    # Add all your other methods from the original db.py...

    def close(self):
        """Close database connections"""
        self.sqlite_conn.close()

if __name__ == "__main__":
    # Test code here
    db = CanvasDatabase()
    print("Database initialized successfully")