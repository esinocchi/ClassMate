import io
import aiohttp
from urllib.parse import urlparse
import os
import fitz  # PyMuPDF
from docx import Document
from pptx import Presentation
    

async def parse_file_content(url: str):
    """Parse content from PDF, DOCX, or PPTX file at the given URL."""
    
    # Download file
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as response:
            if response.status != 200:
                return f"Error downloading file: {response.status}"
            file_bytes = await response.read()
    
    # Check file signature/magic bytes
    file_type = None
    bytes_data = file_bytes[:8]  # First few bytes for signature detection
    
    # PDF signature: %PDF
    if file_bytes[:4] == b'%PDF':
        file_type = 'pdf'
    # DOCX, PPTX (ZIP-based formats)
    elif bytes_data[:2] == b'PK':
        # Further inspect the ZIP contents for Office XML formats
        byte_stream = io.BytesIO(file_bytes)
        
        # Try to load as PPTX first (since you mentioned this specific URL is a PPTX)
        try:
            Presentation(byte_stream)
            file_type = 'pptx'
        except:
            byte_stream.seek(0)
            try:
                Document(byte_stream)
                file_type = 'docx'
            except:
                # If both fail, check for content markers
                if b'ppt/' in file_bytes[:4000] or b'presentation' in file_bytes[:4000]:
                    file_type = 'pptx'
                elif b'word/' in file_bytes[:4000] or b'document.xml' in file_bytes[:4000]:
                    file_type = 'docx'
    
    # Process based on detected file type
    text = ""
    try:
        if file_type == 'pdf':
            doc = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
            for page in doc:
                text += page.get_text() + "\n\n"
            doc.close()
        elif file_type == 'docx':
            doc = Document(io.BytesIO(file_bytes))
            text = "\n".join([p.text for p in doc.paragraphs if p.text])
        elif file_type == 'pptx':
            prs = Presentation(io.BytesIO(file_bytes))
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        text += shape.text + "\n"
                text += "\n"
        else:
            # If still unable to determine, try the most common formats
            try:
                doc = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
                for page in doc:
                    text += page.get_text() + "\n\n"
                doc.close()
                if text.strip():
                    return text
            except:
                pass
                
            try:
                prs = Presentation(io.BytesIO(file_bytes))
                for slide in prs.slides:
                    for shape in slide.shapes:
                        if hasattr(shape, "text") and shape.text.strip():
                            text += shape.text + "\n"
                    text += "\n"
                if text.strip():
                    return text
            except:
                pass
                
            try:
                doc = Document(io.BytesIO(file_bytes))
                text = "\n".join([p.text for p in doc.paragraphs if p.text])
                if text.strip():
                    return text
            except:
                text = "Unable to determine or process file type"
    except Exception as e:
        text = f"Error processing file: {str(e)}"
    
    return text