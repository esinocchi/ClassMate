import json
# from pipeline.vectordatabase import search

# def retrieve_events_and_assignments(query:str, course_ids:list[str], include_related:bool = True, minimum_score:float = 0.3):
#     """
#     Retrieve events and assignments from the vector database based on the user's query.

#     Args:
#         query (str): The user's query.
#         course_ids (list[str]): List of course IDs to filter by.
#     """
#     doc_types = ["event", "assignment"]
#     results = search(query, course_ids, doc_types, include_related, minimum_score)
#     funciton_context = {"role": "function", "name": "retrieve_events_and_assignments", "content": json.dumps(results)}
#     return funciton_context


# def retreive_course_info(query:str, course_ids:list[str], include_related:bool = True, minimum_score:float = 0.3):
#     """
#     Retrieve syllabus from the vector database based on the user's query.

#     Args:
#         query (str): The user's query.
#         course_ids (list[str]): List of course IDs to filter by.
#     """
#     doc_types = ["syllabus", "course_info"]
#     results = search(query, course_ids, doc_types, include_related, minimum_score)
#     funciton_context = {"role": "function", "name": "retrieve_course_info", "content": json.dumps(results)}
#     return funciton_context


def retrieve_chat_history():
    """
    Retrieve chat history from cache. 
    Returns a list of last 20 messages from the cache.
    """
    messages = []
    return messages
