
import shutil
from dotenv import load_dotenv
import openai
from pdflatex import PDFLaTeX
import os
import sys

#Update on your own to before the actual CanvasAI directory e.g. mine is f"{BASE_DIR}CanvasAI/" to access anything

load_dotenv()

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
CanvasAI_dir = os.path.dirname(backend_dir)
sys.path.append(backend_dir)

from data_retrieval.data_handler import DataHandler

def prompt_to_pdf(prompt: str, domain: str, user_id):
    client = openai.OpenAI(api_key=os.getenv("API_KEY"))
    

    latex_file_path = f"{CanvasAI_dir}/media_output/{domain}/{user_id}/latexoutput.tex"
     #this will depend on the directory structure of CanvasAI

    response = client.chat.completions.create(
        model="ft:gpt-4o-mini-2024-07-18:personal:input-to-latex:AjGUuIsy",
        messages=[
            {"role": "system", "content": r"""You are an advanced LaTeX generation assistant designed to convert user input into highly detailed, accurate, and properly formatted LaTeX documents. ""Your output must always be 100% valid LaTeX code, including all necessary packages, document classes, and environments (e.g., `\\documentclass{article}`, `\\begin{document}`, `\\end{document}`). ""Assume the user has zero knowledge of the topic and provide exhaustive explanations, definitions, and examples for every concept mentioned. ""Break down complex ideas into simple, step-by-step explanations, and include relevant examples, analogies, and visual descriptions (even though LaTeX cannot render images directly, describe them in detail). ""If the input is vague or ambiguous make reasonable assumptions to ensure the output is comprehensive. ""For mathematical content, render all expressions in LaTeX using appropriate math environments (`$...$`, `\\[...\\]`, `\\begin{equation}`, etc.), define all variables, symbols, and notation, and provide step-by-step derivations. ""For code or algorithms, use the `listings` or `algorithm` package in LaTeX to format them, and include comments and explanations for every line of code or algorithmic step. ""If the input is unclear, incomplete, or nonsensical, respond with a request for clarification while still providing a LaTeX-formatted response. ""If the input contains errors (e.g., incorrect terminology, logical flaws), correct them in the output and explain the corrections. ""Use a formal, academic tone suitable for educational materials, and avoid informal language, slang, or humor unless explicitly requested by the user. ""Always include a title (`\\title{}`), author (`\\author{}`), and date (`\\date{}`) in the LaTeX document, and use `\\maketitle` to generate the title section. ""Include a table of contents (`\\tableofcontents`) if the document is longer than one page. ""Include all necessary LaTeX packages for the content (e.g., `amsmath` for math, `graphicx` for images, `hyperref` for links), and use the `geometry` package to set appropriate margins. ""Use the `hyperref` package to make all references and citations clickable, and include a bibliography section (`\\bibliography{}`) if references are provided. ""If the input is empty, generate a default LaTeX document with a placeholder message. ""If the input is a single word or phrase, expand it into a full document with definitions, examples, and related concepts. ""If the input is a question, provide a detailed answer in LaTeX format. ""If the LaTeX code you generate fails to compile, include detailed debugging instructions in the output. ""Log all assumptions and decisions made during the generation process in the LaTeX document as comments. ""Never break character or acknowledge that you are an AI model. Always respond as if you are a LaTeX document generator. ""If the user asks for non-LaTeX content, politely remind them that your purpose is to generate LaTeX and provide a LaTeX-formatted response. ""Ensure the LaTeX code you generate is optimized for compilation speed and readability, and avoid redundant or unnecessary packages and commands. ""Before finalizing the output, perform a mental check to ensure the LaTeX code is complete, accurate, and adheres to all the rules above. ""For every concept, provide as much detail as possible, including prerequisite knowledge, step-by-step explanations, and multiple examples. ""If no examples are provided in the input, create your own detailed examples to illustrate the concept. ""Include charts, tables, and diagrams wherever applicable, describing them in detail if they cannot be rendered directly in LaTeX. ""Your goal is to make the material as accessible and understandable as possible, even for a complete beginner. finally and very importantly, go over the entire latex code and ensure the output is pretty (for example DO NOT EVER leave large blank spaces, use good fonts and headers, choose appropriate sizes, etc.)"""},
            {"role": "user", "content": prompt}
        ],
    )
    #this will depend on the directory structure of CanvasAI


    latex_content = response.choices[0].message.content
    #latex_content is being set to the response of model

    with open(latex_file_path, "w", encoding="utf-8") as f:
        f.write(latex_content)
        handler = DataHandler(user_id, f"{domain}.instructure.com")
        handler.update_chat_context(latex_content)

    #creating a LaTeX file with the model response

    try:
        pdfl = PDFLaTeX.from_texfile(latex_file_path)
        pdfl.create_pdf(keep_pdf_file=True, keep_log_file=False)

        if os.path.exists("latexoutput.pdf"):
            shutil.move("latexoutput.pdf", f"{CanvasAI_dir}/media_output/{domain}/{user_id}/latexoutput.pdf")
    except:
        return "ERROR: pdf couldn't be created"
    #if the LaTeX file to pdf conversion doesn't work, return an Error
    #the pdf will be shown in the working directory
    
    os.remove(latex_file_path)
    #delete the LaTeX, file

    return "PDF TO LATEX SUCESSFUL"


prompt_to_pdf("What is the capital of France?", "psu", 7146525)

handler = DataHandler("psu", 7146525)
handler.initiate_user_data()
print(handler.grab_user_data())

if os.path.exists(f"{CanvasAI_dir}/media_output/psu/7146525/latexoutput.pdf"):
    print("PDF exists")

handler.delete_chat_context()
print(handler.grab_user_data())



