"""
Content Extraction Module
-------------------------
This module provides functionality to extract text content from various file types,
particularly PDFs embedded in Canvas assignments.
"""

import os
import tempfile
import requests
from pathlib import Path
import logging
import PyPDF2
import re
from typing import Dict, Any, Optional, Union, List, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("content_extraction")

class ContentExtractor:
    def __init__(self, canvas_api_token: Optional[str] = None):
        """
        Initialize the content extractor.
        
        Args:
            canvas_api_token: Optional Canvas API token for authenticated requests
        """
        self.canvas_api_token = canvas_api_token
        self.temp_dir = tempfile.TemporaryDirectory()
        self.document_finder = None  # Will be set by set_document_finder
    
    def __del__(self):
        """Clean up temporary directory when object is destroyed"""
        try:
            self.temp_dir.cleanup()
        except:
            pass
    
    def set_document_finder(self, finder_function: Callable):
        """
        Set a document finder function that can search the document_map
        
        Args:
            finder_function: A callable that takes a filename and returns a document or None
        """
        self.document_finder = finder_function
    
    async def process_assignment(self, assignment: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an assignment document, extracting content from any embedded files.
        
        Pipeline:
        1. Extract file references from assignment description
        2. Find those files in the vectordb document map
        3. Extract content from those files
        4. Add the extracted content to the assignment document
        
        Args:
            assignment: Assignment document to process
            
        Returns:
            Updated assignment document with extracted content
        """
        if not assignment.get('description'):
            return assignment
        
        # Create a copy of the assignment to avoid modifying the original
        processed_assignment = assignment.copy()
        
        # Step 1: Extract file references from description
        file_references = self._extract_file_references(processed_assignment['description'])
        
        if not file_references:
            logger.info(f"No file references found in assignment: {processed_assignment.get('name', '')}")
            return processed_assignment
        
        # Step 2 & 3: Find files and extract content
        extracted_content = []
        
        for file_ref in file_references:
            # Skip if finder function is not set
            if not self.document_finder:
                logger.warning("Document finder function not set, cannot look up files in vectordb")
                break
                
            # Try to find the file document in vectordb
            file_doc = self.document_finder(file_ref['name'])
            
            if file_doc:
                logger.info(f"Found file in vectordb: {file_doc.get('display_name', '')}")
                
                # Extract content based on file type
                file_content = await self._extract_content_by_type(file_doc)
                
                if file_content:
                    extracted_content.append(f"Content from {file_ref['name']}:\n{file_content}")
                    logger.info(f"Extracted content from file: {file_ref['name']}")
                else:
                    logger.warning(f"Failed to extract content from file: {file_ref['name']}")
            else:
                # If file not found in vectordb, try using the URL from the description
                if file_ref.get('url'):
                    logger.info(f"File not found in vectordb, trying URL from description: {file_ref['url']}")
                    file_content = await self.extract_text_from_url(file_ref['url'])
                    
                    if file_content:
                        extracted_content.append(f"Content from {file_ref['name']}:\n{file_content}")
                        logger.info(f"Extracted content from URL: {file_ref['url']}")
                    else:
                        logger.warning(f"Failed to extract content from URL: {file_ref['url']}")
                else:
                    logger.warning(f"File not found in vectordb and no URL available: {file_ref['name']}")
        
        # Step 4: Add extracted content to assignment
        if extracted_content:
            # Append to existing description
            original_description = self._parse_html_content(processed_assignment['description'])
            processed_assignment['description'] = f"{original_description}\n\n{''.join(extracted_content)}"
            
            # Also add to content field if it exists
            if 'content' not in processed_assignment:
                processed_assignment['content'] = []
                
            for content in extracted_content:
                processed_assignment['content'].append(content)
                
            logger.info(f"Added extracted content to assignment: {processed_assignment.get('name', '')}")
        
        return processed_assignment
    
    def _extract_file_references(self, html_content: str) -> List[Dict[str, str]]:
        """
        Extract file references from HTML content.
        
        Args:
            html_content: HTML content to parse
            
        Returns:
            List of dictionaries containing file name and URL
        """
        file_references = []
        
        # Look for Canvas file links in different formats
        
        # Pattern 1: Standard Canvas file links with title attribute
        pattern1 = r'<a[^>]*?class="[^"]*?instructure_file_link[^"]*?"[^>]*?title="([^"]+)"[^>]*?href="([^"]+)"[^>]*?>'
        matches1 = re.findall(pattern1, html_content)
        
        for title, href in matches1:
            file_references.append({
                'name': title,
                'url': href
            })
        
        # Pattern 2: Canvas file links with display_name attribute
        pattern2 = r'<a[^>]*?class="[^"]*?instructure_file_link[^"]*?"[^>]*?display_name="([^"]+)"[^>]*?href="([^"]+)"[^>]*?>'
        matches2 = re.findall(pattern2, html_content)
        
        for display_name, href in matches2:
            file_references.append({
                'name': display_name,
                'url': href
            })
        
        # Pattern 3: Links to Canvas files with data-api-endpoint attribute
        pattern3 = r'<a[^>]*?data-api-endpoint="([^"]*?/files/\d+)"[^>]*?href="([^"]+)"[^>]*?>(.*?)</a>'
        matches3 = re.findall(pattern3, html_content)
        
        for api_endpoint, href, link_text in matches3:
            # Extract filename from link text or from URL
            if link_text.strip():
                # Clean HTML tags from link text
                text = re.sub(r'<[^>]*>', '', link_text).strip()
                name = text
            else:
                name = href.split('/')[-1].split('?')[0]
                
            file_references.append({
                'name': name,
                'url': href,
                'api_endpoint': api_endpoint
            })
        
        # Extract file names from the description by looking for title and file extension
        extensions = ['.pdf', '.pptx', '.docx', '.doc', '.xlsx', '.xls', '.txt']
        for ext in extensions:
            # Look for titles with this extension
            title_pattern = rf'title="([^"]+{ext})"'
            title_matches = re.findall(title_pattern, html_content, re.IGNORECASE)
            
            for title in title_matches:
                # Check if this filename is already in our list
                if not any(ref['name'] == title for ref in file_references):
                    file_references.append({
                        'name': title,
                        'url': None  # Will need to find URL by searching vectordb
                    })
        
        # Log what we found
        if file_references:
            logger.info(f"Found {len(file_references)} file references: {[ref['name'] for ref in file_references]}")
        else:
            logger.warning("No file references found in HTML content")
        
        return file_references
    
    async def _extract_content_by_type(self, file_doc: Dict[str, Any]) -> Optional[str]:
        """
        Extract content from a file document based on its type.
        
        Args:
            file_doc: File document from vectordb
            
        Returns:
            Extracted text content or None if extraction failed
        """
        file_url = file_doc.get('url')
        if not file_url:
            logger.warning(f"No URL found for file: {file_doc.get('display_name', '')}")
            return None
        
        file_name = file_doc.get('display_name', '').lower()
        
        # Extract content based on file extension
        if file_name.endswith('.pdf'):
            return await self.extract_text_from_pdf_url(file_url)
        elif file_name.endswith(('.pptx', '.ppt')):
            return await self.extract_text_from_pptx_url(file_url)
        elif file_name.endswith(('.docx', '.doc')):
            return await self.extract_text_from_docx_url(file_url)
        elif file_name.endswith(('.xlsx', '.xls')):
            return await self.extract_text_from_xlsx_url(file_url)
        elif file_name.endswith('.txt'):
            return await self.extract_text_from_txt_url(file_url)
        else:
            logger.warning(f"Unsupported file type: {file_name}")
            return None
    
    async def extract_text_from_url(self, url: str) -> Optional[str]:
        """
        Extract text from a URL based on file extension.
        
        Args:
            url: URL to the file
            
        Returns:
            Extracted text from the file or None if extraction failed
        """
        if not url:
            return None
            
        url_lower = url.lower()
        
        if '.pdf' in url_lower:
            return await self.extract_text_from_pdf_url(url)
        elif '.pptx' in url_lower or '.ppt' in url_lower:
            return await self.extract_text_from_pptx_url(url)
        elif '.docx' in url_lower or '.doc' in url_lower:
            return await self.extract_text_from_docx_url(url)
        elif '.xlsx' in url_lower or '.xls' in url_lower:
            return await self.extract_text_from_xlsx_url(url)
        elif '.txt' in url_lower:
            return await self.extract_text_from_txt_url(url)
        else:
            # Try PDF as default for unknown types
            logger.info(f"Unknown file type, trying as PDF: {url}")
            return await self.extract_text_from_pdf_url(url)
    
    async def extract_text_from_pdf_url(self, pdf_url: str) -> Optional[str]:
        """
        Download a PDF from a URL and extract its text content.
        
        Args:
            pdf_url: URL to the PDF file
            
        Returns:
            Extracted text from the PDF or None if extraction failed
        """
        try:
            # Create a temporary file path
            temp_file_path = Path(self.temp_dir.name) / f"temp_{os.urandom(8).hex()}.pdf"
            
            # Set up headers for authenticated requests if token is available
            headers = {}
            if self.canvas_api_token:
                headers['Authorization'] = f'Bearer {self.canvas_api_token}'
            
            # Add user agent to mimic a browser request
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            
            logger.info(f"Downloading PDF from: {pdf_url}")
            
            # Download the PDF file
            with requests.Session() as session:
                response = session.get(pdf_url, headers=headers, stream=True, allow_redirects=True)
                response.raise_for_status()
                
                # Save the PDF to a temporary file
                with open(temp_file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Extract text from the PDF
                text = self._extract_text_from_pdf(temp_file_path)
                return text
                
        except requests.RequestException as e:
            logger.error(f"Failed to download PDF: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return None
        finally:
            # Ensure temporary file is deleted
            if 'temp_file_path' in locals() and temp_file_path.exists():
                try:
                    temp_file_path.unlink()
                except:
                    pass
    
    def _extract_text_from_pdf(self, pdf_path: Union[str, Path]) -> str:
        """
        Extract text from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text content
        """
        text_content = []
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)
                
                logger.info(f"Extracting text from {num_pages} pages")
                
                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(page_text)
            
            return "\n\n".join(text_content)
        except Exception as e:
            logger.error(f"Error in PDF text extraction: {e}")
            return ""
    
    # Placeholder methods for other file types - implement these based on your needs
    
    async def extract_text_from_pptx_url(self, url: str) -> Optional[str]:
        logger.info("PPTX extraction not yet implemented")
        return "PPTX content extraction not supported yet"
    
    async def extract_text_from_docx_url(self, url: str) -> Optional[str]:
        logger.info("DOCX extraction not yet implemented")
        return "DOCX content extraction not supported yet"
    
    async def extract_text_from_xlsx_url(self, url: str) -> Optional[str]:
        logger.info("XLSX extraction not yet implemented")
        return "XLSX content extraction not supported yet"
    
    async def extract_text_from_txt_url(self, url: str) -> Optional[str]:
        try:
            headers = {}
            if self.canvas_api_token:
                headers['Authorization'] = f'Bearer {self.canvas_api_token}'
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error downloading text file: {e}")
            return None
    
    def _parse_html_content(self, html_content: str) -> str:
        """
        Parse HTML content to extract plain text.
        
        Args:
            html_content: HTML content string to parse
            
        Returns:
            Plain text extracted from HTML content
        """
        if not html_content:
            return ""
        
        try:
            from html.parser import HTMLParser
            
            class HTMLTextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                    self.in_script = False
                    self.in_style = False
                    
                def handle_starttag(self, tag, attrs):
                    if tag.lower() == "script":
                        self.in_script = True
                    elif tag.lower() == "style":
                        self.in_style = True
                    elif tag.lower() == "br" or tag.lower() == "p":
                        self.text_parts.append("\n")
                    elif tag.lower() == "li":
                        self.text_parts.append("\n• ")
                
                def handle_endtag(self, tag):
                    if tag.lower() == "script":
                        self.in_script = False
                    elif tag.lower() == "style":
                        self.in_style = False
                    elif tag.lower() in ["div", "h1", "h2", "h3", "h4", "h5", "h6", "tr"]:
                        self.text_parts.append("\n")
                
                def handle_data(self, data):
                    if not self.in_script and not self.in_style:
                        # Only append non-empty strings after stripping whitespace
                        text = data.strip()
                        if text:
                            self.text_parts.append(text)
            
                def get_text(self):
                    # Join all text parts and normalize whitespace
                    text = " ".join(self.text_parts)
                    # Replace multiple whitespace with a single space
                    text = re.sub(r'\s+', ' ', text)
                    # Replace multiple newlines with a single newline
                    text = re.sub(r'\n+', '\n', text)
                    return text.strip()
            
            extractor = HTMLTextExtractor()
            extractor.feed(html_content)
            return extractor.get_text()
            
        except Exception as e:
            logger.error(f"Error parsing HTML content: {e}")
            # Fallback to a simple tag stripping approach if the parser fails
            text = re.sub(r'<[^>]*>', ' ', html_content)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
