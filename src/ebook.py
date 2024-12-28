import os
import fitz  # PyMuPDF for PDF processing
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import tempfile
from typing import Tuple, Optional
from .config import MAX_BUFFER_SIZE

class EbookProcessor:
    def __init__(self):
        """Initialize the EbookProcessor."""
        self.supported_formats = {
            'application/pdf': self._process_pdf,
            'application/epub+zip': self._process_epub,
            'application/x-mobipocket-ebook': self._process_mobi
        }

    def _is_pdf(self, file_bytes: bytes) -> bool:
        """Check if file is a PDF by looking at its signature."""
        return file_bytes.startswith(b'%PDF')

    async def process_ebook(self, file_bytes: bytes) -> Tuple[bool, list]:
        """
        Process an ebook file and extract its text content.
        Returns (success, content/error_message)
        """
        try:
            # Check if it's a PDF by looking at file signature
            if self._is_pdf(file_bytes):
                # Create temporary PDF file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    temp_file.write(file_bytes)
                    pdf_path = temp_file.name
                    
                    try:
                        doc = fitz.open(pdf_path)
                        success, content = self._process_pdf(pdf_path)
                        doc.close()
                        return success, content
                    except Exception as pdf_error:
                        print(f"PDF processing error: {str(pdf_error)}")
                        return False, f"Error processing PDF: {str(pdf_error)}"
                    finally:
                        if os.path.exists(pdf_path):
                            os.remove(pdf_path)
            
            # Try MOBI first (since we'll convert it to EPUB anyway)
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mobi') as temp_file:
                    temp_file.write(file_bytes)
                    mobi_path = temp_file.name
                    
                    try:
                        success, content = self._process_mobi(mobi_path)
                        if success:
                            return success, content
                    except Exception as mobi_error:
                        print(f"MOBI processing error: {str(mobi_error)}")
                    finally:
                        if os.path.exists(mobi_path):
                            os.remove(mobi_path)
            except Exception as mobi_error:
                print(f"Error trying MOBI format: {str(mobi_error)}")
            
            # Try as EPUB if not PDF or MOBI
            with tempfile.NamedTemporaryFile(delete=False, suffix='.epub') as temp_file:
                temp_file.write(file_bytes)
                epub_path = temp_file.name
                
                try:
                    success, content = self._process_epub(epub_path)
                    return success, content
                except Exception as epub_error:
                    print(f"EPUB processing error: {str(epub_error)}")
                    return False, "Unsupported or corrupted file format"
                finally:
                    if os.path.exists(epub_path):
                        os.remove(epub_path)

        except Exception as e:
            print(f"Error processing ebook: {str(e)}")
            return False, f"Error processing ebook: {str(e)}"

    def _process_pdf(self, file_path: str) -> Tuple[bool, list]:
        """
        Process PDF files and extract text by sections.
        Returns (success, list of sections) where each section is a tuple (title, content)
        """
        doc = None
        try:
            doc = fitz.open(file_path)
            
            # Check if PDF is scanned
            if self._is_scanned_pdf(doc):
                return False, "This appears to be a scanned PDF. Please use OCR processing instead."

            sections = []
            current_section = []
            current_title = "Section 1"
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                
                # Try to find section/chapter headings
                lines = text.split('\n')
                found_heading = False
                
                for line in lines:
                    line = line.strip()
                    # Check for common heading patterns
                    if (line and (
                        line.lower().startswith(('chapter', 'section', '第', '章', '节')) or
                        (len(line) < 50 and line.replace(' ', '').isalnum() and 
                         any(c.isupper() for c in line))
                    )):
                        # If we have accumulated text, save it as a section
                        if current_section:
                            section_text = '\n'.join(current_section).strip()
                            if len(section_text) > 100:  # Only add if section has substantial content
                                sections.append((current_title, section_text))
                        
                        # Start new section
                        current_section = []
                        current_title = line
                        found_heading = True
                        continue
                    
                    if line.strip():
                        current_section.append(line)
                
                # If no heading found, just add page text to current section
                if not found_heading and text.strip():
                    current_section.append(text)
                    
                # If current section is getting too large, split it
                section_text = '\n'.join(current_section)
                if len(section_text) > MAX_BUFFER_SIZE:
                    sections.append((current_title, section_text))
                    current_section = []
                    current_title = f"Section {len(sections) + 1}"

            # Add the last section if it has content
            if current_section:
                section_text = '\n'.join(current_section).strip()
                if len(section_text) > 100:
                    sections.append((current_title, section_text))

            if not sections:
                return False, "No readable content found in PDF"
            
            return True, sections

        except Exception as e:
            return False, f"Error processing PDF: {str(e)}"
        finally:
            if doc:
                doc.close()

    def _is_scanned_pdf(self, doc) -> bool:
        """
        Check if a PDF is likely scanned by analyzing its content.
        Returns True if the PDF appears to be scanned.
        """
        try:
            # Check first few pages
            pages_to_check = min(3, len(doc))
            text_length = 0
            
            for page_num in range(pages_to_check):
                page = doc[page_num]
                text = page.get_text()
                text_length += len(text.strip())
                
                # Check for images
                image_list = page.get_images()
                
                # If page has images but very little text, likely scanned
                if len(image_list) > 0 and len(text.strip()) < 100:
                    return True
            
            # If average text length per page is very low, likely scanned
            avg_text_length = text_length / pages_to_check
            return avg_text_length < 50

        except Exception:
            return False

    def _process_epub(self, file_path: str) -> Tuple[bool, list]:
        """
        Process EPUB files and extract text by chapters.
        Returns (success, list of chapters) where each chapter is a tuple (title, content)
        """
        try:
            book = epub.read_epub(file_path)
            chapters = []
            
            # First try to process using spine
            for item in book.spine:
                if isinstance(item, epub.EpubHtml):
                    # Parse HTML content
                    soup = BeautifulSoup(item.content, 'html.parser')
                    
                    # Get chapter title from item or try to find in content
                    title = item.title
                    if not title:
                        title_tag = soup.find(['h1', 'h2', 'h3'])
                        title = title_tag.get_text().strip() if title_tag else None
                    if not title:
                        title = f"Chapter {len(chapters) + 1}"
                    
                    # Extract text, removing scripts and styles
                    for tag in soup(["script", "style", "nav", "header", "footer"]):
                        tag.decompose()
                    
                    # Get chapter content
                    text = soup.get_text()
                    # Clean up whitespace
                    text = " ".join(text.split())
                    
                    if len(text.strip()) > 100:  # Only add if chapter has substantial content
                        chapters.append((title, text))

            # If no chapters found, try processing all HTML items
            if not chapters:
                print("No chapters found in spine, trying all HTML items...")
                for item in book.get_items():
                    if item.get_type() == ebooklib.ITEM_DOCUMENT:
                        try:
                            # Parse HTML content
                            soup = BeautifulSoup(item.get_content(), 'html.parser')
                            
                            # Get chapter title
                            title_tag = soup.find(['h1', 'h2', 'h3'])
                            title = title_tag.get_text().strip() if title_tag else f"Chapter {len(chapters) + 1}"
                            
                            # Extract text, removing scripts and styles
                            for tag in soup(["script", "style", "nav", "header", "footer"]):
                                tag.decompose()
                            
                            # Get chapter content
                            text = soup.get_text()
                            # Clean up whitespace
                            text = " ".join(text.split())
                            
                            if len(text.strip()) > 100:  # Only add if chapter has substantial content
                                chapters.append((title, text))
                        except Exception as e:
                            print(f"Error processing HTML item: {str(e)}")
                            continue

            if not chapters:
                return False, "No readable chapters found in EPUB"
            
            # Sort chapters if they got mixed up
            if all(title.startswith("Chapter ") for title, _ in chapters):
                try:
                    chapters.sort(key=lambda x: int(x[0].split()[1]))
                except:
                    pass  # If sorting fails, keep original order
            
            return True, chapters

        except Exception as e:
            print(f"Error processing EPUB: {str(e)}")
            return False, f"Error processing EPUB: {str(e)}"

    def _convert_mobi_to_epub(self, mobi_path: str) -> Tuple[bool, str]:
        """Convert MOBI to EPUB using Calibre's ebook-convert."""
        try:
            # Create temporary file for EPUB output
            with tempfile.NamedTemporaryFile(delete=False, suffix='.epub') as temp_file:
                epub_path = temp_file.name

            # Use Calibre's ebook-convert command
            import subprocess
            process = subprocess.Popen(
                ['ebook-convert', mobi_path, epub_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                print(f"Conversion error: {stderr.decode()}")
                return False, epub_path

            return True, epub_path

        except FileNotFoundError:
            return False, "Calibre's ebook-convert not found. Please install Calibre."
        except Exception as e:
            return False, f"Error converting MOBI to EPUB: {str(e)}"

    def _process_mobi(self, file_path: str) -> Tuple[bool, list]:
        """Process MOBI files by converting to EPUB first."""
        epub_path = None
        try:
            # Convert MOBI to EPUB
            success, result = self._convert_mobi_to_epub(file_path)
            if not success:
                return False, result
            
            epub_path = result
            # Process the converted EPUB
            return self._process_epub(epub_path)

        except Exception as e:
            return False, f"Error processing MOBI: {str(e)}"
        finally:
            # Clean up temporary EPUB file
            if epub_path and os.path.exists(epub_path):
                os.remove(epub_path)
