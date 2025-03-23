import io
import os
import sys
import requests
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from prompt_to_file_GPT import prompt_to_pdf
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)

sys.path.append(backend_dir)
from data_retrieval.data_handler import DataHandler
from data_retrieval.get_all_user_data import extract_text_and_images, get_file_type

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def lecture_file_to_notes_pdf(file_url: str, file_name: str, user_id, domain):
    handler = DataHandler(user_id, domain)
    API_TOKEN = handler.grab_user_data()["user_metadata"]["token"]
 
    
    response = requests.get(file_url, headers={"Authorization": f"Bearer {API_TOKEN}"}, stream=True).json()

    file_bytes = response.content
    #try to get files raw data to write into a new file on our system
    #if not working return Error

    try:
        file_text = extract_text_and_images(file_bytes, get_file_type(file_name))
    except:
        return "File text could not be extracted"
    print(file_text)
    #try to exctract the text from a file
    #if not working return Error

    try:
        prompt_to_pdf_status = "ERROR: pdf couldn't be created"
        while prompt_to_pdf_status == "ERROR: pdf couldn't be created":
            prompt_to_pdf_status = prompt_to_pdf(file_text)
    except:
        return "ERROR: pdf input not accepted"
    #create a while loop to always keep trying to process the input text into a detailed pdf of notes
    #if not working return Error
    
    return "Lecture file to notes pdf succesful"


example_file_url = "https://psu.instructure.com/files/172233999/download?download_frd=1&verifier=4GWZIU1TX9XhGI7X5nCTeA7uJJQjfbY8a67orirl"
example_file_name = "PoissonBinomialCDFTables.pdf"
example_user_id = 7210330
example_domain = "psu.instructure.com"

lecture_file_to_notes_pdf(example_file_url, example_file_name, example_user_id, example_domain)

