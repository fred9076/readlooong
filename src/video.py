from typing import Optional, Dict, Tuple
from urllib.parse import urlparse, parse_qs
import yt_dlp
import os
import tempfile

class VideoProcessor:
    def __init__(self):
        """Initialize the VideoProcessor with yt-dlp configuration."""
        self.ydl_opts = {
            'format': 'best',  # Get best quality
            'quiet': True,     # Reduce output
            'no_warnings': True,
            'extract_flat': True,  # Don't download, just get metadata
        }

    async def extract_audio(self, url: str) -> Tuple[bool, str]:
        """
        Extract audio from video URL.
        Returns (success, result) where result is either file path or error message.
        """
        temp_dir = None
        try:
            # Create a temporary file that won't be immediately deleted
            temp_dir = tempfile.mkdtemp()
            output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
            print(f"Created temp directory: {temp_dir}")
            
            # Configure yt-dlp for audio extraction
            audio_opts = {
                'format': 'bestaudio/best',
                'quiet': False,  # Enable output for debugging
                'no_warnings': False,  # Enable warnings for debugging
                'outtmpl': output_template,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'ffmpeg_location': None,  # Let yt-dlp find ffmpeg automatically
                'prefer_ffmpeg': True,
                'keepvideo': False,
                'writethumbnail': False,
                'verbose': True,
                # Bilibili-specific options without browser cookies
                'extractor_args': {
                    'bilibili': {
                        'language': 'en_US',
                    }
                }
            }

            # For Bilibili URLs, add necessary headers
            if any(domain in url for domain in ['bilibili.com', 'b23.tv']):
                audio_opts.update({
                    'http_headers': {
                        'Referer': 'https://www.bilibili.com',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                    }
                })

            try:
                print(f"Starting download for URL: {url}")
                with yt_dlp.YoutubeDL(audio_opts) as ydl:
                    # Extract info first to verify URL
                    try:
                        info = ydl.extract_info(url, download=False)
                        if not info:
                            return False, "Could not extract video information"
                        print(f"Found video: {info.get('title', 'Unknown title')}")
                        
                        # Download and extract audio
                        ydl.download([url])
                        
                        # Look for the created MP3 file
                        mp3_files = [f for f in os.listdir(temp_dir) if f.endswith('.mp3')]
                        if mp3_files:
                            output_file = os.path.join(temp_dir, mp3_files[0])
                            print(f"Successfully created audio file: {output_file}")
                            return True, output_file
                        else:
                            print(f"No MP3 files found in {temp_dir}")
                            print(f"Directory contents: {os.listdir(temp_dir)}")
                            return False, "No audio file was created"
                        
                    except Exception as e:
                        print(f"Error during download/extraction: {str(e)}")
                        return False, f"Error processing video: {str(e)}"

            except Exception as e:
                print(f"Error in yt-dlp operation: {str(e)}")
                if os.path.exists(temp_dir):
                    import shutil
                    shutil.rmtree(temp_dir)
                return False, f"Error during download: {str(e)}"

        except Exception as e:
            print(f"Error in extract_audio: {str(e)}")
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)
            return False, f"Error setting up audio extraction: {str(e)}"

    async def process_video(self, url: str) -> Optional[Dict]:
        """
        Process a video URL and return metadata.
        Returns a dictionary containing video information or None if failed.
        """
        try:
            # Extract video information using yt-dlp
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    print(f"Could not extract information from {url}")
                    return None

                # Create a clean metadata dictionary
                metadata = {
                    'title': info.get('title'),
                    'description': info.get('description'),
                    'duration': info.get('duration'),  # in seconds
                    'view_count': info.get('view_count'),
                    'uploader': info.get('uploader'),
                    'upload_date': info.get('upload_date'),
                    'url': url,
                    'thumbnail': info.get('thumbnail'),
                }
                
                print(f"Successfully extracted metadata for: {metadata['title']}")
                return metadata

        except Exception as e:
            print(f"Error processing video {url}: {str(e)}")
            return None

    def get_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from various video platform URLs."""
        try:
            parsed_url = urlparse(url)
            
            # Handle YouTube URLs
            if any(domain in parsed_url.netloc 
                  for domain in ['youtube.com', 'youtu.be', 'www.youtube.com']):
                
                # Handle youtu.be format
                if 'youtu.be' in parsed_url.netloc:
                    return parsed_url.path.lstrip('/')
                
                # Handle youtube.com format
                query_params = parse_qs(parsed_url.query)
                return query_params.get('v', [None])[0]
            
            # Handle Bilibili URLs
            if any(domain in parsed_url.netloc 
                  for domain in ['bilibili.com', 'www.bilibili.com', 'b23.tv']):
                
                # Handle b23.tv short URLs
                if 'b23.tv' in parsed_url.netloc:
                    return parsed_url.path.lstrip('/')
                
                # Handle standard bilibili.com URLs
                # Bilibili URLs format: bilibili.com/video/BV1xx411c7mD
                video_id = parsed_url.path.split('/')[-1]
                if video_id.startswith(('BV', 'av')):
                    return video_id
            
            return None

        except Exception as e:
            print(f"Error extracting video ID: {str(e)}")
            return None

    def is_supported_url(self, url: str) -> bool:
        """Check if the URL is from a supported video platform."""
        try:
            parsed_url = urlparse(url)
            supported_domains = [
                'youtube.com',
                'youtu.be',
                'www.youtube.com',
                'bilibili.com',
                'www.bilibili.com',
                'b23.tv',  # Bilibili's short URL service
            ]
            return any(domain in parsed_url.netloc for domain in supported_domains)
        except:
            return False
