import json
from unittest.mock import patch, MagicMock
from endpoints import mainPipelineEntry

# Mock data for DataHandler
mock_user_data = {
    "user_metadata": {
        "name": "Arshawn Vossoughi"
    }
}

# Sample course dictionary (course_name: course_id)
courses = {
    "physics": "course_2372294",
    "statistics": "course_2381676", 
    "Earth 101": "course_2361510",
    "Apocalyptic Geographies": "course_2361723"
}

def test_create_calendar_event():
    """Test creating a calendar event"""
    test_context = {
        "context": [
            {
                "role": "assistant",
                "content": [
                    {
                        "message": "",
                        "function": []
                    }
                ]
            },
            {
                "role": "user",
                "id": "user_7210330",
                "domain": "psu.instructure.com",
                "content": [
                    "Can you create a study event for Physics 211 next Tuesday at 3pm?"
                ],
                "classes": [
                    {
                        "name": "physics",
                        "id": "course_2372294",
                        "selected": "true"
                    },
                    {
                        "name": "statistics",
                        "id": "course_2381676",
                        "selected": "true"
                    },
                    {
                        "name": "Earth 101",
                        "id": "course_2361510",
                        "selected": "true"
                    },
                    {
                        "name": "Apocalyptic Geographies",
                        "id": "course_2361723",
                        "selected": "true"
                    }
                ]
            }
        ]
    }
    
    with patch('endpoints.DataHandler') as mock_data_handler:
        mock_handler = MagicMock()
        mock_handler.grab_data.return_value = mock_user_data
        mock_data_handler.return_value = mock_handler
        
        response = mainPipelineEntry(test_context)
        print("\n=== Test Create Calendar Event ===")
        print(f"Response: {json.dumps(response, indent=2)}")
        print("===============================\n")

def test_regular_chat():
    """Test regular chat without function calls"""
    test_context = {
        "context": [
            {
                "role": "assistant",
                "content": [
                    {
                        "message": "Hello! How can I help you today?",
                        "function": []
                    }
                ]
            },
            {
                "role": "user",
                "id": "user_7210330",
                "domain": "psu.instructure.com",
                "content": [
                    "Hi! How are you?"
                ],
                "classes": [
                    {
                        "name": "physics",
                        "id": "course_2372294",
                        "selected": "true"
                    },
                    {
                        "name": "statistics",
                        "id": "course_2381676",
                        "selected": "true"
                    },
                    {
                        "name": "Earth 101",
                        "id": "course_2361510",
                        "selected": "true"
                    },
                    {
                        "name": "Apocalyptic Geographies",
                        "id": "course_2361723",
                        "selected": "true"
                    }
                ]
            }
        ]
    }
    
    with patch('endpoints.DataHandler') as mock_data_handler:
        mock_handler = MagicMock()
        mock_handler.grab_data.return_value = mock_user_data
        mock_data_handler.return_value = mock_handler
        
        response = mainPipelineEntry(test_context)
        print("\n=== Test Regular Chat ===")
        print(f"Response: {json.dumps(response, indent=2)}")
        print("========================\n")

def test_multiple_messages():
    """Test conversation with multiple messages"""
    test_context = {
        "context": [
            {
                "role": "assistant",
                "content": [
                    {
                        "message": "Hello! How can I help you today?",
                        "function": []
                    },
                    {
                        "message": "I'll help you create that event.",
                        "function": ["create_event", "{\"status\": \"success\"}"]
                    }
                ]
            },
            {
                "role": "user",
                "id": "user_7210330",
                "domain": "psu.instructure.com",
                "content": [
                    "Hi! How are you?",
                    "Can you create a study event for Physics 211 next Tuesday at 3pm?"
                ],
                "classes": [
                    {
                        "name": "physics",
                        "id": "course_2372294",
                        "selected": "true"
                    },
                    {
                        "name": "statistics",
                        "id": "course_2381676",
                        "selected": "true"
                    },
                    {
                        "name": "Earth 101",
                        "id": "course_2361510",
                        "selected": "true"
                    },
                    {
                        "name": "Apocalyptic Geographies",
                        "id": "course_2361723",
                        "selected": "true"
                    }
                ]
            }
        ]
    }
    
    with patch('endpoints.DataHandler') as mock_data_handler:
        mock_handler = MagicMock()
        mock_handler.grab_data.return_value = mock_user_data
        mock_data_handler.return_value = mock_handler
        
        response = mainPipelineEntry(test_context)
        print("\n=== Test Multiple Messages ===")
        print(f"Response: {json.dumps(response, indent=2)}")
        print("============================\n")

def test_invalid_context():
    """Test handling of invalid context data"""
    test_context = {
        "context": [
            {
                "role": "assistant",
                "content": [
                    {
                        "message": "Invalid test",
                        "function": []
                    }
                ]
            },
            {
                "role": "user",
                "id": "invalid_id",
                "domain": "psu.instructure.com",
                "content": [],
                "classes": [
                    {
                        "name": "physics",
                        "id": "course_2372294",
                        "selected": "true"
                    },
                    {
                        "name": "statistics",
                        "id": "course_2381676",
                        "selected": "true"
                    },
                    {
                        "name": "Earth 101",
                        "id": "course_2361510",
                        "selected": "true"
                    },
                    {
                        "name": "Apocalyptic Geographies",
                        "id": "course_2361723",
                        "selected": "true"
                    }
                ]
            }
        ]
    }
    
    with patch('endpoints.DataHandler') as mock_data_handler:
        mock_handler = MagicMock()
        mock_handler.grab_data.return_value = mock_user_data
        mock_data_handler.return_value = mock_handler
        
        response = mainPipelineEntry(test_context)
        print("\n=== Test Invalid Context ===")
        print(f"Response: {json.dumps(response, indent=2)}")
        print("==========================\n")

if __name__ == "__main__":
    print("Running tests...")
    test_create_calendar_event()
    test_regular_chat()
    test_multiple_messages()
    test_invalid_context()
    print("Tests completed!") 