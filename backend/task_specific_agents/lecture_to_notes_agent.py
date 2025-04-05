import os
import sys
import shutil
import logging
import threading
import asyncio
import aiohttp
import subprocess
from openai import AsyncOpenAI

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
CanvasAI_dir = os.path.dirname(backend_dir)
sys.path.append(backend_dir)

from data_retrieval.data_handler import DataHandler, clear_directory
from data_retrieval.get_all_user_data import extract_text_and_images, get_file_type

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# === Utility: Download a file asynchronously ===
async def async_file_download(file_url, api_token):
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url, headers={"Authorization": f"Bearer {api_token}"}) as response:
            if response.status != 200:
                logger.error(f"Failed to download file. Status code: {response.status}")
                raise Exception(f"Failed to download file. Status code: {response.status}")
            return await response.read()

# === Utility: Compile LaTeX using tectonic ===
def compile_with_tectonic(tex_path, output_dir):
    try:
        subprocess.run(
            ["tectonic", tex_path, "--outdir", output_dir],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info("✅ PDF created successfully using Tectonic.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error("❌ Tectonic compilation failed:\n" + e.stderr.decode())
        return False

# === Core Function: Convert prompt to PDF ===
async def prompt_to_pdf(prompt: str, user_id, domain: str):
    client = AsyncOpenAI(api_key=os.getenv("LECTURE_TO_PDF_API_KEY"))
    output_dir = f"{CanvasAI_dir}/media_output/{domain}/{user_id}"
    latex_file_path = os.path.join(output_dir, "latexoutput.tex")

    os.makedirs(output_dir, exist_ok=True)

    response = await client.chat.completions.create(
        model="ft:gpt-4o-mini-2024-07-18:personal:input-to-latex:AjGUuIsy",
        messages=[
            {
                "role": "system",
                "content": r"""
                            You are an advanced LaTeX generation assistant designed to convert user input into highly detailed, accurate, and properly formatted LaTeX documents.

                            Your output must follow **all** of these strict rules:

                            ---

                            🧾 **Document Structure**
                            - Output must be a **complete** and **fully compilable** LaTeX document.
                            - Always include:
                              - `\documentclass{article}`
                              - `\begin{document}` and `\end{document}`
                              - `\title{}`, `\author{}`, and `\date{}` (use meaningful defaults if not specified)
                              - `\maketitle`
                              - `\tableofcontents` if the document is longer than one page

                            ---

                            📦 **Required Packages**
                            - Always include the following packages as needed:
                              - `amsmath`, `amssymb`, `geometry`, `graphicx`, `hyperref`, `listings`, `algorithm`, `caption`, `fancyhdr`, `xcolor`
                            - Set reasonable `geometry` margins (e.g., 1in)
                            - Use `hyperref` to ensure links and references are clickable
                            - Never reference image or file names that do not exist (e.g., do NOT include `somefigure.pdf`)

                            ---

                            🧠 **Content Expectations**
                            - Assume the reader is a **beginner** with zero prior knowledge
                            - Break down **every concept** into step-by-step explanations
                            - Include **definitions**, **examples**, and **commented LaTeX code blocks**
                            - Use a formal academic tone; no slang or casual language

                            ---

                            🧮 **Math Content**
                            - Always use proper math environments:
                              - Inline math: `$...$`
                              - Display math: `\[...\]` or `\begin{equation}...\end{equation}`
                            - Define **every variable and symbol** before use
                            - Walk through **step-by-step derivations** for formulas

                            ---

                            💻 **Code and Algorithms**
                            - Use the `listings` or `algorithm` + `algorithmic` packages
                            - Include **explanatory comments** for every line
                            - Ensure all LaTeX environments compile correctly

                            ---

                            ⚠️ **When Input Is Problematic**
                            - If input is vague: make reasonable assumptions and note them in comments
                            - If input is unclear, incomplete, or nonsensical:
                              - Return a helpful LaTeX document with a clarification request
                            - If the input contains technical or conceptual errors:
                              - Correct them in your LaTeX output and **explain the corrections**

                            ---

                            🧼 **Final Polish**
                            - Ensure the LaTeX code is beautiful and efficient:
                              - No redundant packages or commands
                              - No excessive whitespace or awkward formatting
                              - Use good font sizing, spacing, and header formatting
                            - Never leave large blank sections
                            - Use LaTeX comments (`%`) to document logic and assumptions
                            - Never include placeholders for missing images or files (e.g., avoid `\includegraphics{somefile.pdf}` unless it’s defined in code)

                            ---

                            📌 **Additional Rules**
                            - If the input is a single word or phrase, expand it into a full academic document
                            - If the input is a question, write a fully developed LaTeX answer
                            - If no content is provided, return a default placeholder LaTeX file
                            - If references are given, include a `\bibliography{}` section
                            - If LaTeX code you generate fails to compile, include helpful debugging instructions in LaTeX comments
                            - Never acknowledge that you are an AI; respond solely as a LaTeX document generator
                            - Don't include any professor names unless directly relevant to the material (e.g. if in the notes it says "come to professor __ for more information" or of similar nature)

                            ---

                            🎯 Your Goal:
                            Make every LaTeX document as accessible, instructive, and visually clean as possible — even for total beginners. Err on the side of clarity, completeness, and correctness.
                            """
            },
            {"role": "user", "content": prompt}
        ],
    )

    latex_content = response.choices[0].message.content
    with open(latex_file_path, "w", encoding="utf-8") as f:
        f.write(latex_content)

    handler = DataHandler(user_id, f"{domain}.instructure.com")
    handler.update_chat_context(latex_content)

    if compile_with_tectonic(latex_file_path, output_dir):
        output_pdf_path = os.path.join(output_dir, "latexoutput.pdf")
        if os.path.exists(output_pdf_path):
            final_pdf_path = os.path.join(output_dir, "output.pdf")
            shutil.move(output_pdf_path, final_pdf_path)
        os.remove(latex_file_path)
        return "PDF TO LATEX SUCCESSFUL"
    else:
        return "ERROR: pdf couldn't be created"

# === Async flow to process file ===
async def _real_processing(file_url, file_name, user_id, domain):
    handler = DataHandler(user_id, domain)
    output_dir = f"{CanvasAI_dir}/media_output/{handler.domain}/{user_id}"
    os.makedirs(output_dir, exist_ok=True)
    clear_directory(output_dir)

    logger.info("\n=== STAGE 1: Downloading File ===")
    API_TOKEN = handler.grab_user_data()["user_metadata"]["token"]
    file_bytes = await async_file_download(file_url, API_TOKEN)

    logger.info("\n=== STAGE 2: Extracting Text/Images ===")
    try:
        file_text = extract_text_and_images(file_bytes, get_file_type(file_name))
    except Exception as e:
        logger.error(f"Extraction failed: {str(e)}")
        return f"Error: File text could not be extracted. Details: {str(e)}"

    logger.info("\n=== STAGE 3: Generating PDF (5 attempts max) ===")
    for i in range(5):
        logger.info(f"\nAttempt {i + 1}/5:")
        try:
            status = await prompt_to_pdf(file_text, user_id, handler.domain)
            if status == "PDF TO LATEX SUCCESSFUL":
                logger.info("\n=== SUCCESS ===")
                return "Lecture file to notes pdf successful"
        except Exception as e:
            logger.error(f"Attempt failed: {str(e)}")
            if i == 4:
                clear_directory(output_dir)
                logger.error("\n=== FAILED AFTER 5 ATTEMPTS ===")
                return "ERROR: pdf couldn't be created"

    return "ERROR: pdf couldn't be created after 5 attempts"

# === Entry Point for Threaded Use ===
def lecture_file_to_notes_pdf(file_url, file_name, user_id, domain):
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_real_processing(file_url, file_name, user_id, domain))
        finally:
            loop.close()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    logger.info("\n=== BACKGROUND PROCESS STARTED ===")
    return {"status": "started", "thread_id": thread.ident}
