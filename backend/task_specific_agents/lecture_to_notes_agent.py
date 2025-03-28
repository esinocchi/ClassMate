import os
import sys
import shutil
from openai import AsyncOpenAI  # Changed import
from pdflatex import PDFLaTeX
import sys
import asyncio
import aiohttp

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
CanvasAI_dir = os.path.dirname(backend_dir)
sys.path.append(backend_dir)

from data_retrieval.data_handler import DataHandler, clear_directory
from data_retrieval.get_all_user_data import extract_text_and_images, get_file_type


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

async def async_file_download(file_url, api_token):
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url, headers={"Authorization": f"Bearer {api_token}"}) as response:
            if response.status != 200:
                raise Exception(f"Failed to download file. Status code: {response.status}")
            return await response.read()

async def lecture_file_to_notes_pdf(file_url: str, file_name: str, user_id, domain):
    """
    inputs:
    file_url: the url of the file to be downloaded
    file_name: the name of the file to be downloaded
    user_id: the user id of the user who is downloading the file
    domain: the domain of the user who is downloading the file

    outputs:
    a string that says "Lecture file to notes pdf successful" if the function works
    an error message if the function doesn't work
    """
    
    handler = DataHandler(user_id, domain)

    os.makedirs(f"{CanvasAI_dir}/media_output/{handler.domain}/{user_id}", exist_ok=True)

    clear_directory(f"{CanvasAI_dir}/media_output/{handler.domain}/{user_id}")

    API_TOKEN = handler.grab_user_data()["user_metadata"]["token"]
    
    print(API_TOKEN)
    

    file_bytes = await async_file_download(file_url, API_TOKEN)
    # Make the request to download the file
    
    # Try to extract text and images from the file
    try:
        file_text = extract_text_and_images(file_bytes, get_file_type(file_name))
    except Exception as e:
        print(f"Error: File text could not be extracted. Details: {str(e)}")
        return f"Error: File text could not be extracted. Details: {str(e)}"
    
    print(file_text)
    
    # Try to process the text into a detailed PDF of notes
    try:
        prompt_to_pdf_status = "ERROR: pdf couldn't be created"
        i = 0
        while i < 5:
            print(f"trying to make pdf {i}")
            prompt_to_pdf_status = await prompt_to_pdf(file_text, user_id, handler.domain)  # Added await
            print("prompt should be given")
            if prompt_to_pdf_status == "PDF TO LATEX SUCESSFUL":
                break
            i += 1
        if i == 5:
            clear_directory(f"{CanvasAI_dir}/media_output/{handler.domain}/{user_id}")
            return "ERROR: pdf couldn't be created"
        
    except Exception as e:
        return f"ERROR: PDF input not accepted. Details: {str(e)}"
    
    return "Lecture file to notes pdf successful"


async def prompt_to_pdf(prompt: str, user_id, domain: str):  # Made async
    client = AsyncOpenAI(api_key=os.getenv("LECTURE_TO_PDF_API_KEY"))  # Changed to AsyncOpenAI

    print(client)
    print(os.getenv("LECTURE_TO_PDF_API_KEY"))
    print("herehereherherherherhe")
    print(domain)
    latex_file_path = f"{CanvasAI_dir}/media_output/{domain}/{user_id}/latexoutput.tex"
    print(latex_file_path)
     #this will depend on the directory structure of CanvasAI

    print(prompt)

    response = await client.chat.completions.create(  # Added await
        model="ft:gpt-4o-mini-2024-07-18:personal:input-to-latex:AjGUuIsy",
        messages=[
            {"role": "system", "content": r"""You are an advanced LaTeX generation assistant designed to convert user input into highly detailed, accurate, and properly formatted LaTeX documents. ""Your output must always be 100% valid LaTeX code, including all necessary packages, document classes, and environments (e.g., `\\documentclass{article}`, `\\begin{document}`, `\\end{document}`). ""Assume the user has zero knowledge of the topic and provide exhaustive explanations, definitions, and examples for every concept mentioned. ""Break down complex ideas into simple, step-by-step explanations, and include relevant examples, analogies, and visual descriptions (even though LaTeX cannot render images directly, describe them in detail). ""If the input is vague or ambiguous make reasonable assumptions to ensure the output is comprehensive. ""For mathematical content, render all expressions in LaTeX using appropriate math environments (`$...$`, `\\[...\\]`, `\\begin{equation}`, etc.), define all variables, symbols, and notation, and provide step-by-step derivations. ""For code or algorithms, use the `listings` or `algorithm` package in LaTeX to format them, and include comments and explanations for every line of code or algorithmic step. ""If the input is unclear, incomplete, or nonsensical, respond with a request for clarification while still providing a LaTeX-formatted response. ""If the input contains errors (e.g., incorrect terminology, logical flaws), correct them in the output and explain the corrections. ""Use a formal, academic tone suitable for educational materials, and avoid informal language, slang, or humor unless explicitly requested by the user. ""Always include a title (`\\title{}`), author (`\\author{}`), and date (`\\date{}`) in the LaTeX document, and use `\\maketitle` to generate the title section. ""Include a table of contents (`\\tableofcontents`) if the document is longer than one page. ""Include all necessary LaTeX packages for the content (e.g., `amsmath` for math, `graphicx` for images, `hyperref` for links), and use the `geometry` package to set appropriate margins. ""Use the `hyperref` package to make all references and citations clickable, and include a bibliography section (`\\bibliography{}`) if references are provided. ""If the input is empty, generate a default LaTeX document with a placeholder message. ""If the input is a single word or phrase, expand it into a full document with definitions, examples, and related concepts. ""If the input is a question, provide a detailed answer in LaTeX format. ""If the LaTeX code you generate fails to compile, include detailed debugging instructions in the output. ""Log all assumptions and decisions made during the generation process in the LaTeX document as comments. ""Never break character or acknowledge that you are an AI model. Always respond as if you are a LaTeX document generator. ""If the user asks for non-LaTeX content, politely remind them that your purpose is to generate LaTeX and provide a LaTeX-formatted response. ""Ensure the LaTeX code you generate is optimized for compilation speed and readability, and avoid redundant or unnecessary packages and commands. ""Before finalizing the output, perform a mental check to ensure the LaTeX code is complete, accurate, and adheres to all the rules above. ""For every concept, provide as much detail as possible, including prerequisite knowledge, step-by-step explanations, and multiple examples. ""If no examples are provided in the input, create your own detailed examples to illustrate the concept. ""Include charts, tables, and diagrams wherever applicable, describing them in detail if they cannot be rendered directly in LaTeX. ""Your goal is to make the material as accessible and understandable as possible, even for a complete beginner. finally and very importantly, go over the entire latex code and ensure the output is pretty (for example DO NOT EVER leave large blank spaces, use good fonts and headers, choose appropriate sizes, etc. Also, do not assume there are images to be able to put into the latex, you have to create EVERYTHING by hand (for example, dont include something ___.pdf that we don't have access too)"""},
            {"role": "user", "content": prompt}
        ],
    )
    #this will depend on the directory structure of CanvasAI

    print(response)

    latex_content = response.choices[0].message.content
    #latex_content is being set to the response of model

    print('latex made')

    os.makedirs(f"{CanvasAI_dir}/media_output/{domain}/{user_id}", exist_ok=True)

    with open(latex_file_path, "w", encoding="utf-8") as f:
        f.write(latex_content)
        handler = DataHandler(user_id, f"{domain}.instructure.com")
        handler.update_chat_context(latex_content)

    #creating a LaTeX file with the model response

    try:
        pdfl = PDFLaTeX.from_texfile(latex_file_path)
        pdfl.create_pdf(keep_pdf_file=True, keep_log_file=False)
        print("trying to make pdf")

        if os.path.exists("latexoutput.pdf"):
            shutil.move("latexoutput.pdf", f"{CanvasAI_dir}/media_output/{domain}/{user_id}/output.pdf")
    except:
        return "ERROR: pdf couldn't be created"
    #if the LaTeX file to pdf conversion doesn't work, return an Error
    #the pdf will be shown in the working directory
    
    os.remove(latex_file_path)
    #delete the LaTeX, file

    return "PDF TO LATEX SUCESSFUL"