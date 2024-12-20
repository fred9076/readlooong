import asyncio
from typing import Optional
import aiohttp
from trafilatura import fetch_url, extract
import re
from urllib.parse import urlparse, parse_qs
from .video import VideoProcessor

class LinkProcessor:
    def __init__(self):
        """Initialize the LinkProcessor."""
        self.session = None
        self.video_processor = VideoProcessor()

    def is_youtube_url(self, url: str) -> bool:
        """Check if the URL is a YouTube URL."""
        parsed_url = urlparse(url)
        return any(domain in parsed_url.netloc 
                  for domain in ['youtube.com', 'youtu.be', 'www.youtube.com'])

    async def process_link(self, url: str) -> Optional[str]:
        """Process a URL and extract text content."""
        try:
            if not self.is_valid_url(url):
                print(f"Invalid URL format: {url}")
                return None

            print(f"Fetching content from: {url}")
            
            # Check if it's a video URL
            if self.video_processor.is_supported_url(url):
                print("Video URL detected - extracting metadata")
                metadata = await self.video_processor.process_video(url)
                if metadata:
                    # Return formatted video metadata as text
                    return (
                        f"Video: {metadata['title']}\n\n"
                        f"By: {metadata['uploader']}\n"
                        f"Duration: {metadata['duration']} seconds\n\n"
                        f"Description:\n{metadata['description']}"
                    )
                return None

            # Check if it's a YouTube URL
            if self.is_youtube_url(url):
                print("YouTube URL detected - please use YouTubeProcessor instead")
                return None
            
            # Use trafilatura to fetch and extract content for non-YouTube URLs
            downloaded = fetch_url(url)
            if not downloaded:
                print(f"Failed to fetch content from {url}")
                return None
            
            # Extract main content with metadata
            extracted_text = extract(downloaded, 
                                  include_links=False,
                                  include_images=False,
                                  include_tables=True,
                                  include_comments=False,
                                  output_format='txt',
                                  with_metadata=False)
            
            if not extracted_text:
                print(f"No text content extracted from {url}")
                return None

            print("\n=== Original Text ===")
            print(extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text)
            
            # Clean the extracted text
            cleaned_text = self._clean_text(extracted_text)
            
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
        """
        Clean the extracted text.
        1. Remove citations patterns like [1] [ 2] [3  ]
        2. Remove citation objects like ^ "Order of..."
        3. Remove tables (including markdown tables and their headers)
        4. Remove [edit] tags and reference lines
        5. Remove numbered references like ^ 1.0 1.1 1.2 and their content
        """
        # Remove citation patterns with brackets
        cleaned_text = re.sub(r'\[\s*\d+\s*\]', '', text)
        cleaned_text = re.sub(r'\[edit\]', '', cleaned_text)
        
        # Split into lines and filter
        lines = cleaned_text.split('\n')
        
        # Keep lines that don't match any of these patterns
        lines = [line for line in lines 
                if not (
                    # Remove citation objects (lines starting with ^)
                    line.strip().startswith('^') or
                    # Remove numbered references with their content
                    re.match(r'^\s*\^?\s*\d+(\.\d+)*\s+.*$', line.strip()) or
                    # Remove lines with pipe symbols (markdown tables)
                    '|' in line or
                    # Remove horizontal separators
                    re.match(r'^\s*[-=+]+\s*$', line) or
                    # Remove lines that are part of table formatting
                    re.search(r'[-+|]\s*[-+|]', line) or
                    # Remove reference lines starting with -
                    line.strip().startswith('- ^') or
                    # Remove lines that are just "Notes:" or "See also" or "References"
                    re.match(r'^\s*(Notes:|See also|References)\s*$', line) or
                    # Remove citation help text
                    '{{cite' in line or 'ignored' in line
                )]
        
        cleaned_text = '\n'.join(lines)
        
        # Remove extra whitespace and normalize spacing
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        # Remove multiple newlines
        cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text)
        
        return cleaned_text

    def is_valid_url(self, url: str) -> bool:
        """Validate and potentially fix URLs."""
        # Strip whitespace
        url = url.strip()
        
        # Fix common URL issues
        if url.startswith('www.'):
            url = 'http://' + url
        elif not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Basic URL pattern validation
        url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
        return bool(re.match(url_pattern, url))
