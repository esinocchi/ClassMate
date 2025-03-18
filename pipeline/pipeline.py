import os
from dotenv import load_dotenv
from openai import OpenAI
import json
import logging
from vectordb.vectordatabase import VectorDatabase
from chatbot.conversation import system_context, functions, function_mapping
import inspect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("classmate_prompt")

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# Initialize Vector Database
vector_db = VectorDatabase(
    json_file_path="user_data/psu/7214035/user_data.json"
)

# Process data and create embeddings if not already done
vector_db.process_data()

# Add vector search function to function mapping
def find_vector_documents(keywords):
    """
    Search the vector database for relevant documents based on keywords.
    
    Args:
        keywords (list): List of keywords for the search
        
    Returns:
        dict: Dictionary containing search results
    """
    # Log the original keywords for debugging
    logger.info(f"Original keywords: {keywords}")
    
    # Load course information for better course ID extraction
    course_map = {}
    course_name_to_id = {}
    try:
        with open("user_data/psu/7214035/user_data.json", "r") as file:
            user_data = json.load(file)
        
        # Build course maps (ID → course and name → ID)
        for course in user_data.get("courses", []):
            course_id = str(course.get("id", ""))
            course_name = course.get("name", "")
            course_code = course.get("course_code", "")
            
            if course_id:
                course_map[course_id] = course
                
                # Map different variations of course names to IDs
                if course_name:
                    course_name_to_id[course_name.lower()] = course_id
                    
                    # Handle common variations like "CMPSC465" or "465"
                    if course_code:
                        course_name_to_id[course_code.lower()] = course_id
                        
                        # Extract just the number if it's like "CMPSC 465"
                        parts = course_code.split()
                        if len(parts) > 1 and parts[-1].isdigit():
                            course_name_to_id[parts[-1]] = course_id
                            # Also add variant with no space
                            course_name_to_id[course_code.replace(" ", "").lower()] = course_id
        
        logger.info(f"Loaded {len(course_map)} courses with {len(course_name_to_id)} name variations")
    except Exception as e:
        logger.error(f"Error loading course information: {e}")
    
    # Extract course IDs and build a clean query
    course_ids = []
    cleaned_keywords = []
    
    for keyword in keywords:
        # Direct match for course_ID format
        if keyword.startswith("course_") and keyword[7:].isdigit():
            course_ids.append(keyword[7:])
            continue
            
        # Direct match for full numeric IDs
        elif keyword.isdigit() and len(keyword) > 5:  # Likely a course ID
            course_ids.append(keyword)
            continue
            
        # Check for "course_ID" in the middle of text
        elif "course_" in keyword:
            parts = keyword.split("course_")
            if len(parts) > 1 and parts[1].isdigit():
                course_id = parts[1]
                course_ids.append(course_id)
                cleaned_keywords.append(parts[0].strip())
                continue
        
        # Check if the keyword matches any course name variations
        keyword_lower = keyword.lower()
        if keyword_lower in course_name_to_id:
            course_ids.append(course_name_to_id[keyword_lower])
            continue
        
        # Check for partial matches in course names (like "465" in "CMPSC 465")
        # This is less precise but helps with queries like "HW2 for 465"
        matched = False
        for name, id in course_name_to_id.items():
            if keyword_lower in name and not matched:
                course_ids.append(id)
                matched = True
                break
        
        if matched:
            continue
            
        # If no match, keep the keyword for the search query
        cleaned_keywords.append(keyword)
    
    # Remove duplicates while preserving order
    course_ids = list(dict.fromkeys(course_ids))
    
    # Create the main query from cleaned keywords
    query = " ".join(cleaned_keywords)
    
    # Log the extracted information
    logger.info(f"Extracted course_ids: {course_ids}")
    logger.info(f"Cleaned keywords: {cleaned_keywords}")
    logger.info(f"Query: {query}")
    
    # Perform the search
    try:
        results = []
        
        # Always try with course filtering first if we have course IDs
        if course_ids:
            logger.info(f"Searching with course filtering using IDs: {course_ids}")
            filtered_results = vector_db.search(
                query=query,
                course_ids=course_ids,
                top_k=5,
                include_related=True,
                minimum_score=0.3
            )
            
            # If we found results with filtering, use them
            if filtered_results:
                logger.info(f"Found {len(filtered_results)} results with course filtering")
                results = filtered_results
            else:
                logger.info("No results found with course filtering")
        
        # Fall back to no filtering only if necessary
        if not results:
            logger.info("Searching without course filtering")
            unfiltered_results = vector_db.search(
                query=query,
                top_k=5,
                include_related=True,
                minimum_score=0.3
            )
            
            if unfiltered_results:
                logger.info(f"Found {len(unfiltered_results)} results without filtering")
                results = unfiltered_results
        
        # If we still have no results, return an empty set
        if not results:
            logger.info("No results found in either search phase")
            return {"results": [], "message": "No matching documents found"}
        
        # Log the search results for debugging
        logger.info(f"Final results count: {len(results)}")
        for i, result in enumerate(results):
            doc = result['document']
            doc_type = doc.get('type', 'unknown')
            doc_name = doc.get('display_name', doc.get('name', doc.get('title', 'unknown')))
            course_id = doc.get('course_id', 'unknown')
            course_name = "Unknown"
            if course_id in course_map:
                course_name = course_map[course_id].get("name", "Unknown")
            logger.info(f"Result {i+1}: Type={doc_type}, Name={doc_name}, Course={course_name} (ID: {course_id}), Score={result['similarity']}")
        
        # Format results for the API
        formatted_results = []
        for result in results:
            doc = result['document']
            
            # Get course name from course_id
            course_id = doc.get('course_id', '')
            course_name = ''
            if course_id and course_id in vector_db.course_map:
                course_name = vector_db.course_map[course_id].get('name', '')
            
            # Extract content and name based on document type
            content = ''
            doc_type = doc.get('type', '')
            
            if doc_type == 'assignment':
                content = doc.get('description', '')
                doc_name = doc.get('name', '')
            elif doc_type == 'announcement':
                content = doc.get('message', '')
                doc_name = doc.get('title', '')
            elif doc_type == 'file':
                # Use the extracted content if available
                content = doc.get('content', doc.get('display_name', ''))
                doc_name = doc.get('display_name', '')
            elif doc_type == 'quiz':
                content = doc.get('description', '')
                doc_name = doc.get('title', '')
            elif doc_type == 'event':
                content = doc.get('description', '')
                doc_name = doc.get('title', '')
            else:
                doc_name = ''
            
            # Make sure we only include JSON-serializable data
            formatted_doc = {
                "type": str(doc_type),
                "name": str(doc_name),
                "course_name": str(course_name),
                "content": str(content),
                "score": float(result['similarity'])
            }
            formatted_results.append(formatted_doc)
            
        return {"results": formatted_results}
    except Exception as e:
        logger.error(f"Error performing vector search: {e}")
        return {"error": str(e), "results": []}

# Add the vector search function to the function mapping
function_mapping["find_vector_documents"] = find_vector_documents

# Add vector search function to functions list
vector_search_function = {
    "name": "find_vector_documents",
    "description": "Search for relevant documents in the Canvas data using vector search.",
    "parameters": {
        "type": "object",
        "properties": {
            "keywords": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "A list of keywords derived from the user's prompt to guide the vector database search. This list must include:\n\n- **Item Types:** e.g., 'assignment', 'calendar events', 'syllabus'.\n- **Date Ranges:** Dates converted to ISO8601 format (e.g., '2012-07-01T23:59:00-06:00', '2012-07-08T16:00:00-06:00').\n- **Course Names with IDs:** Include both the course name and its course ID (e.g., 'physics course_2372294', 'statistics course_2381676').\n- **Synonyms or Related Terms:** For example, if 'exam' is mentioned, also include 'midterm' and 'final'.\n\nKeep the list concise (around 10 items) to ensure focused retrieval."
            }
        },
        "required": [
            "keywords"
        ]
    }
}

# Add the vector search function to the functions list
functions.append(vector_search_function)

# Check if functions is serializable
try:
    json.dumps(functions)
    print("functions is serializable")
except TypeError as e:
    print(f"functions is NOT serializable: {e}")
    # Print each function to find the problematic one
    for i, func in enumerate(functions):
        try:
            json.dumps(func)
            print(f"Function {i} is serializable")
        except TypeError as e:
            print(f"Function {i} is NOT serializable: {e}")
            print(f"Function {i} content: {func}")

# User prompt function
def process_user_prompt(user_query):
    """
    Process a user prompt using the conversation flow from conversation.py
    with added vector search capability.
    
    Args:
        user_query (str): The user's question or request
        
    Returns:
        str: The AI's response
    """
    # Create chat messages
    chat = [
        {'role': 'system', 'content': system_context},
        {'role': 'user', 'content': user_query}
    ]

    # hardcoded function call for now
    available_functions = [vector_search_function]
    
    # Initial API call
    chat_completion = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=chat,
        functions=available_functions,
        function_call={"name": "find_vector_documents"},  # Force this specific function
        temperature=0.3,
        max_tokens=1024
    )
    
    response_message = chat_completion.choices[0].message
    logger.info(f"Initial response: {response_message}")
    
    # Since we're forcing the function call, we can assume it will always be called
    # Extract the arguments from the function call
    function_call = response_message.function_call
    arguments = json.loads(function_call.arguments)
    logger.info(f"Function arguments: {arguments}")
    
    # Call the vector search function directly
    result = find_vector_documents(arguments.get("keywords", []))
    
    # First ensure result is JSON-serializable
    serializable_result = json.loads(json.dumps(result))
    print(serializable_result)
    
    # Add function result to chat history
    chat.append({
        'role': "function",
        "name": "find_vector_documents",
        "content": json.dumps(serializable_result)
    })
    
    # Add a system message to guide the model to use the retrieved information
    chat.append({
        'role': 'system',
        'content': "Use the information retrieved from the vector database to provide a detailed answer to the user's query. If the retrieved information is insufficient, acknowledge this and provide the best response possible with the available data."
    })
    
    # Context is then passed back to the API for final response
    final_completion = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=chat,
        temperature=0.3,
        max_tokens=1024
    )
    
    # Final response after function call
    final_message = final_completion.choices[0].message.content
    return final_message

# Example usage
if __name__ == "__main__":
    user_query = "Summarize HW2 for CMPSC 465 for me"
    response = process_user_prompt(user_query)
    print("\nFINAL RESPONSE:")
    print(response)