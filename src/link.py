import asyncio
from typing import Optional
import aiohttp
import re
from bs4 import BeautifulSoup
from markdown import markdown

class LinkProcessor:
    def __init__(self):
        """Initialize the LinkProcessor."""
        self.session = None

    async def ensure_session(self):
        """Ensure aiohttp session exists."""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def process_link(self, url: str) -> Optional[str]:
        """Process a URL and extract text content using Jina Reader API."""
        try:
            await self.ensure_session()
            
            # Create the Jina Reader URL
            reader_url = f'https://r.jina.ai/{url}'
            print(f"Fetching content from: {reader_url}")
            
            # Get the content using Jina Reader
            async with self.session.get(reader_url) as response:
                if response.status != 200:
                    print(f"Error from Reader API: {response.status}")
                    return None
                
                # Get raw response text first
                print("\n=== Debug: Getting raw response ===")
                raw_text = await response.text()
                print(f"Response type: {type(raw_text)}")
                print(f"Response length: {len(raw_text)}")
                print(f"First 100 chars: {raw_text[:100]}")
                
                # Try to parse as JSON
                try:
                    print("\n=== Debug: Attempting JSON parse ===")
                    import json
                    data = json.loads(raw_text)
                    print(f"Parsed JSON type: {type(data)}")
                    if isinstance(data, dict):
                        print("Data is dictionary")
                        print(f"Available keys: {data.keys()}")
                        extracted_text = data.get('text', raw_text)
                    else:
                        print(f"Data is not dictionary, type: {type(data)}")
                        extracted_text = raw_text
                except json.JSONDecodeError as e:
                    print(f"JSON parse failed: {str(e)}")
                    extracted_text = raw_text
                except Exception as e:
                    print(f"Unexpected error during JSON handling: {str(e)}")
                    extracted_text = raw_text
                
                if not extracted_text:
                    print(f"No text content extracted from {url}")
                    return None

                print("\n=== Original Text ===")
                print(extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text)
                
                # Clean and format the extracted text
                try:
                    print("\n=== Debug: Starting text cleaning ===")
                    cleaned_text = self._clean_text(extracted_text)
                    print("Text cleaning completed")
                except Exception as e:
                    print(f"Error during text cleaning: {str(e)}")
                    return None
                
                print("\n=== Cleaned Text ===")
                print(cleaned_text[:500] + "..." if len(cleaned_text) > 500 else cleaned_text)
                print("===================\n")
                
                print(f"Successfully extracted text from {url}")
                return cleaned_text

        except Exception as e:
            print(f"Error processing link {url}: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _clean_text(self, text: str) -> str:
        """Clean and format the extracted text using BeautifulSoup."""
        if not text:
            return ""
        
        print("\n=== Debug: Text cleaning steps ===")
        
        # Remove metadata lines and specific content
        lines = text.split('\n')
        lines = [line for line in lines if not (
            line.startswith('URL Source:') or 
            line.startswith('Published Time:') or
            line.startswith('Markdown Content:') or
            line.strip().startswith('*   [') or  # Remove list items with links
            '频道' in line  # Remove lines containing '频道'
        )]
        text = '\n'.join(lines)
        print("Step 1: Removed metadata, list lines, and lines with '频道'")
        
        try:
            # Convert markdown to HTML
            html = markdown(text)
            
            # Remove code blocks
            html = re.sub(r'<pre>(.*?)</pre>', ' ', html)
            html = re.sub(r'<code>(.*?)</code >', ' ', html)
            
            # Parse HTML and extract text
            soup = BeautifulSoup(html, "html.parser")
            cleaned_text = ' '.join(soup.findAll(text=True))
            
            # Clean up whitespace
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
            
            # Split into paragraphs
            paragraphs = [p.strip() for p in cleaned_text.split('\n') if p.strip()]
            cleaned_text = '\n\n'.join(paragraphs)
            
            return cleaned_text

        except Exception as e:
            print(f"Error in text cleaning: {str(e)}")
            print(f"Current text: {text[:200]}...")
            import traceback
            traceback.print_exc()
            return text  # Return original text if cleaning fails

    def is_valid_url(self, url: str) -> bool:
        """Basic URL validation."""
        return url.startswith(('http://', 'https://'))

def process_message(message):
    # existing code...
    
    # Check if message contains OCR or links
    has_ocr_or_link = any(
        text.get('ocr') or text.get('link') 
        for text in accumulated_message
    )
    
    if not has_ocr_or_link:
        # Combine all text into a single string
        combined_text = ' '.join(
            text.get('text', '') 
            for text in accumulated_message
        )
        
        # Create single audio file for combined text
        if combined_text:
            audio_file = text_to_speech(combined_text)
            audio_files.append(audio_file)
    else:
        # Original logic for processing individual messages
        for text in accumulated_message:
            if text.get('text'):
                audio_file = text_to_speech(text['text'])
                audio_files.append(audio_file)
    
    # Rest of the existing code...
