#!/usr/bin/env python3
"""
Stacks
A simple, fast downloader for Anna's Archive. Supports fast download via membership API.
"""

import argparse
import re
import sys
import time
import logging
import requests
from pathlib import Path
from urllib.parse import urlparse, urljoin, unquote
from bs4 import BeautifulSoup


def extract_md5(input_string):
    """Extract MD5 hash from URL or return the MD5 if it's already one."""
    # Check if it's already an MD5 (32 hex characters)
    if re.match(r'^[a-f0-9]{32}$', input_string.lower()):
        return input_string.lower()
    
    # Extract MD5 from Anna's Archive URL
    match = re.search(r'/md5/([a-f0-9]{32})', input_string)
    if match:
        return match.group(1)
    
    return None


class AnnaDownloader:
    def __init__(self, output_dir="./downloads", incomplete_dir=None, progress_callback=None, 
                 fast_download_config=None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Incomplete directory for .part files
        if incomplete_dir:
            self.incomplete_dir = Path(incomplete_dir)
        else:
            self.incomplete_dir = self.output_dir / "incomplete"
        self.incomplete_dir.mkdir(parents=True, exist_ok=True)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.logger = logging.getLogger('stacks_downloader')
        self.progress_callback = progress_callback
        
        # Fast download configuration
        self.fast_download_config = fast_download_config or {}
        self.fast_download_enabled = self.fast_download_config.get('enabled', False)
        self.fast_download_key = self.fast_download_config.get('key')
        self.fast_download_api_url = self.fast_download_config.get(
            'api_url', 
            'https://annas-archive.org/dyn/api/fast_download.json'
        )
        
        # Fast download state
        self.fast_download_info = {
            'available': bool(self.fast_download_enabled and self.fast_download_key),
            'downloads_left': None,
            'downloads_per_day': None,
            'recently_downloaded_md5s': [],
            'last_refresh': 0  # Timestamp of last API refresh
        }
        
        # Cooldown period for refreshing fast download info (1 hour)
        self.fast_download_refresh_cooldown = 3600
        
    def extract_md5(self, input_string):
        """Extract MD5 hash from URL or return the MD5 if it's already one."""
        return extract_md5(input_string)
    
    def get_unique_filename(self, base_path):
        """
        Generate a unique filename by adding (1), (2), etc. if file exists.
        Returns the unique Path object.
        """
        if not base_path.exists():
            return base_path
        
        # Split into stem and suffix
        stem = base_path.stem
        suffix = base_path.suffix
        parent = base_path.parent
        
        counter = 1
        while True:
            new_name = f"{stem} ({counter}){suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                self.logger.info(f"File exists, using unique name: {new_name}")
                return new_path
            counter += 1
    
    def try_fast_download(self, md5):
        """
        Attempt to get a fast download URL via the membership API.
        Returns (success, download_url_or_error_message)
        """
        if not self.fast_download_enabled or not self.fast_download_key:
            return False, "Fast download not configured"
        
        # Check if we have downloads left
        if self.fast_download_info.get('downloads_left') is not None:
            if self.fast_download_info['downloads_left'] <= 0:
                self.logger.warning("No fast downloads remaining")
                return False, "No fast downloads remaining"
        
        self.logger.info("Attempting fast download...")
        
        try:
            # Build API request
            params = {
                'md5': md5,
                'key': self.fast_download_key,
                'path_index': self.fast_download_config.get('path_index', 0),
                'domain_index': self.fast_download_config.get('domain_index', 0)
            }
            
            response = self.session.get(
                self.fast_download_api_url, 
                params=params, 
                timeout=30
            )
            
            # Parse response
            try:
                data = response.json()
            except Exception as e:
                self.logger.error(f"Failed to parse fast download API response: {e}")
                return False, "Invalid API response"
            
            # Update fast download info if available
            if 'account_fast_download_info' in data:
                info = data['account_fast_download_info']
                self.fast_download_info.update({
                    'available': True,
                    'downloads_left': info.get('downloads_left'),
                    'downloads_per_day': info.get('downloads_per_day'),
                    'recently_downloaded_md5s': info.get('recently_downloaded_md5s', []),
                    'last_refresh': time.time()  # Update timestamp
                })
                self.logger.info(f"Fast downloads remaining: {info.get('downloads_left')}/{info.get('downloads_per_day')}")
            
            # Handle different response codes
            if response.status_code == 200:
                download_url = data.get('download_url')
                if download_url:
                    self.logger.info("✓ Fast download URL obtained")
                    return True, download_url
                else:
                    error = data.get('error', 'Unknown error')
                    self.logger.warning(f"Fast download failed: {error}")
                    return False, error
                    
            elif response.status_code == 204:
                # No content but successful - might indicate already downloaded
                error = data.get('error', 'File already downloaded recently')
                self.logger.info(f"Fast download: {error}")
                return False, error
                
            elif response.status_code == 400:
                # Invalid MD5
                error = data.get('error', 'Invalid MD5')
                self.logger.warning(f"Fast download: {error}")
                return False, error
                
            elif response.status_code == 401:
                # Invalid key
                error = data.get('error', 'Invalid secret key')
                self.logger.error(f"Fast download: {error}")
                self.fast_download_info['available'] = False
                return False, error
                
            elif response.status_code == 403:
                # Not a member
                error = data.get('error', 'Not a member')
                self.logger.error(f"Fast download: {error}")
                self.fast_download_info['available'] = False
                return False, error
                
            elif response.status_code == 429:
                # No downloads left
                error = data.get('error', 'No downloads left')
                self.logger.warning(f"Fast download: {error}")
                # Update counter to 0 to prevent further attempts
                self.fast_download_info['downloads_left'] = 0
                return False, error
                
            else:
                # Unknown status code
                error = data.get('error', f'HTTP {response.status_code}')
                self.logger.warning(f"Fast download unexpected status: {error}")
                return False, error
                
        except requests.RequestException as e:
            self.logger.error(f"Fast download API request failed: {e}")
            return False, f"API request failed: {e}"
        except Exception as e:
            self.logger.error(f"Fast download error: {e}")
            return False, f"Unexpected error: {e}"
    
    def download_direct(self, download_url, title=None, resume_attempts=3):
        """
        Download file directly from a URL with resume support.
        Used for both fast downloads and mirror downloads.
        """
        self.logger.debug(f"Downloading from: {download_url}")
        
        try:
            # Get file info with HEAD request
            head_response = self.session.head(download_url, timeout=30, allow_redirects=True)
            total_size = int(head_response.headers.get('content-length', 0))
            supports_resume = head_response.headers.get('accept-ranges') == 'bytes'
            
            # Detect file extension from content-type or URL
            file_ext = None
            content_type = head_response.headers.get('Content-Type', '').lower()
            
            # Check if we're getting an HTML page instead of a file
            if 'text/html' in content_type:
                self.logger.warning(f"URL returned HTML instead of a file: {download_url}")
                self.logger.warning("This might be an error page or requires additional navigation")
                return None
            
            # Try to detect extension from content type
            if 'pdf' in content_type:
                file_ext = '.pdf'
            elif 'epub' in content_type:
                file_ext = '.epub'
            elif 'mobi' in content_type:
                file_ext = '.mobi'
            elif 'cbr' in content_type or 'rar' in content_type:
                file_ext = '.cbr'
            elif 'cbz' in content_type or 'zip' in content_type:
                file_ext = '.cbz'
            
            # Try to get extension from URL if not found
            if not file_ext:
                url_path = unquote(urlparse(download_url).path)
                for ext in ['.pdf', '.epub', '.mobi', '.azw3', '.cbr', '.cbz', '.djvu']:
                    if ext in url_path.lower():
                        file_ext = ext
                        break
            
            # Try Content-Disposition for extension if still not found
            if not file_ext and 'Content-Disposition' in head_response.headers:
                cd = head_response.headers['Content-Disposition']
                filename_match = re.findall('filename="?(.+)"?', cd)
                if filename_match:
                    cd_filename = unquote(filename_match[0].strip('"'))
                    for ext in ['.pdf', '.epub', '.mobi', '.azw3', '.cbr', '.cbz', '.djvu']:
                        if cd_filename.lower().endswith(ext):
                            file_ext = ext
                            break
            
            # Default extension if none found
            if not file_ext:
                file_ext = '.bin'
            
            # Build filename from title if provided
            if title and title.lower() not in ['unknown', "anna's archive", 'annas archive']:
                # Clean the title for use as filename
                filename = re.sub(r'[<>:"/\\|?*]', '_', title)
                # Remove extra whitespace
                filename = ' '.join(filename.split())
                # Add extension if not already present
                if not filename.lower().endswith(file_ext.lower()):
                    filename = filename + file_ext
            else:
                # Fallback to URL-based filename
                url_path = unquote(urlparse(download_url).path)
                filename = url_path.split('/')[-1]
                
                if not filename or '.' not in filename:
                    filename = f"download{file_ext}"
                else:
                    # Fast download URLs often have pattern: "[real title] -- [md5] -- Anna's Archive.ext"
                    # Strip the "-- [md5] -- Anna's Archive" suffix if present
                    if ' -- ' in filename:
                        parts = filename.split(' -- ')
                        # Check if last part is "Anna's Archive.ext" or similar
                        if len(parts) >= 2 and ('anna' in parts[-1].lower() and 'archive' in parts[-1].lower()):
                            # Find the MD5 (32 hex chars) and take everything before it
                            for i, part in enumerate(parts):
                                if re.match(r'^[a-f0-9]{32}$', part.strip()):
                                    # Everything before the MD5 is the real title
                                    if i > 0:
                                        filename = ' -- '.join(parts[:i]).strip()
                                        # Add extension if not present
                                        if not filename.lower().endswith(file_ext.lower()):
                                            filename = filename + file_ext
                                        break
                
                # Sanitize
                filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
            
            # Determine final path with deduplication
            base_final_path = self.output_dir / filename
            final_path = self.get_unique_filename(base_final_path)
            
            # Update temp path to match the (possibly deduplicated) final filename
            temp_path = self.incomplete_dir / f"{final_path.name}.part"
            
            # Check if partial file exists
            downloaded = 0
            if temp_path.exists() and supports_resume:
                downloaded = temp_path.stat().st_size
                self.logger.info(f"Found partial file: {downloaded}/{total_size} bytes")
            
            # Attempt download with resume
            for attempt in range(resume_attempts):
                try:
                    headers = {}
                    if downloaded > 0 and supports_resume:
                        headers['Range'] = f'bytes={downloaded}-'
                        self.logger.info(f"Resuming from byte {downloaded}")
                    
                    response = self.session.get(download_url, headers=headers, stream=True, timeout=60)
                    
                    # Check if resume worked
                    if downloaded > 0 and response.status_code not in [200, 206]:
                        self.logger.warning("Resume not supported, starting from beginning")
                        downloaded = 0
                        temp_path.unlink(missing_ok=True)
                        response = self.session.get(download_url, stream=True, timeout=60)
                    
                    response.raise_for_status()
                    
                    # Update total size if we got it from response
                    if not total_size:
                        total_size = int(response.headers.get('content-length', 0))
                    
                    # Report initial progress
                    if self.progress_callback:
                        self.progress_callback({
                            'total_size': total_size,
                            'downloaded': downloaded,
                            'percent': (downloaded / total_size * 100) if total_size else 0
                        })
                    
                    # Download to temp file
                    mode = 'ab' if downloaded > 0 else 'wb'
                    with open(temp_path, mode) as f:
                        chunk_count = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                # Check first chunk for HTML content
                                if chunk_count == 0 and downloaded == 0:
                                    # Check if this looks like HTML
                                    chunk_start = chunk[:500].decode('utf-8', errors='ignore').lower()
                                    if '<!doctype html' in chunk_start or '<html' in chunk_start or '<head>' in chunk_start:
                                        self.logger.warning("Downloaded content appears to be HTML, aborting")
                                        temp_path.unlink(missing_ok=True)
                                        return None
                                
                                f.write(chunk)
                                downloaded += len(chunk)
                                chunk_count += 1
                                
                                # Report progress
                                if self.progress_callback and total_size:
                                    self.progress_callback({
                                        'total_size': total_size,
                                        'downloaded': downloaded,
                                        'percent': (downloaded / total_size * 100)
                                    })
                    
                    # Move to final location
                    temp_path.rename(final_path)
                    self.logger.info(f"Downloaded: {final_path}")
                    return final_path
                    
                except (requests.RequestException, IOError) as e:
                    self.logger.warning(f"Download attempt {attempt + 1} failed: {e}")
                    if attempt < resume_attempts - 1:
                        time.sleep(2)
                        if temp_path.exists():
                            downloaded = temp_path.stat().st_size
                    else:
                        raise
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error downloading: {e}")
            return None
    
    def get_download_links(self, md5):
        """Fetch the page and extract download links."""
        url = f"https://annas-archive.org/md5/{md5}"
        self.logger.debug(f"Fetching: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Error fetching page: {e}")
            return None, []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title - try multiple selectors for Anna's Archive
        title = "Unknown"
        
        # Try div with text-3xl class (main book title)
        title_elem = soup.find('div', class_=lambda x: x and 'text-3xl' in x)
        if title_elem:
            title = title_elem.get_text(strip=True)
        else:
            # Fallback to h1
            title_elem = soup.find('h1')
            if title_elem:
                title = title_elem.get_text(strip=True)
        
        # Find download links
        download_links = []
        
        # Look for links with common download patterns
        for link in soup.find_all('a', href=True):
            href = link['href']
            link_text = link.get_text(strip=True).lower()
            
            # Check for known mirror domains
            if any(domain in href for domain in [
                'libgen.li', 'libgen.is', 'libgen.st',
                'library.lol', 'download.library.lol',
                'zlibrary', 'z-lib',
                'sci-hub', 'nexusstc'
            ]):
                # Convert relative URLs to absolute URLs
                absolute_url = urljoin(url, href)
                download_links.append({
                    'url': absolute_url,
                    'text': link.get_text(strip=True),
                    'domain': urlparse(absolute_url).netloc
                })
        
        return title, download_links
    
    def download_from_libgen(self, mirror_url, title=None, resume_attempts=3, retry_on_500=3):
        """Download file from a Libgen mirror with resume support and 500 error retry."""
        self.logger.debug(f"Accessing mirror: {mirror_url}")
        
        for attempt in range(retry_on_500):
            try:
                # Get the mirror page
                response = self.session.get(mirror_url, timeout=30)
                
                # If we get a 500 error, retry with exponential backoff
                if response.status_code == 500:
                    if attempt < retry_on_500 - 1:
                        wait_time = 2 ** attempt  # 1s, 2s, 4s
                        self.logger.warning(f"Mirror returned 500 error, retrying in {wait_time}s (attempt {attempt + 1}/{retry_on_500})")
                        time.sleep(wait_time)
                        continue
                    else:
                        self.logger.error(f"Mirror returned 500 error after {retry_on_500} attempts")
                        return None
                
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find the actual download link
                download_link = None
                
                # Method 1: Look for get.php links (these are usually direct downloads)
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if 'get.php' in href or 'main.php' in href:
                        download_link = href
                        if not download_link.startswith('http'):
                            download_link = urljoin(mirror_url, download_link)
                        self.logger.debug(f"Found link (get.php): {download_link}")
                        break
                
                # Method 2: Look for direct download links with 'download' text
                if not download_link:
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        link_text = link.get_text().lower()
                        # Must have "download" in text AND not be a file.php link (those are intermediate)
                        if 'download' in link_text and 'file.php' not in href:
                            download_link = href
                            if not download_link.startswith('http'):
                                download_link = urljoin(mirror_url, download_link)
                            self.logger.debug(f"Found link (download text): {download_link}")
                            break
                
                # Method 3: Look for direct file links with extensions
                if not download_link:
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if any(ext in href.lower() for ext in ['.epub', '.pdf', '.mobi', '.azw3', '.cbr', '.cbz', '.djvu']):
                            download_link = href
                            if not download_link.startswith('http'):
                                download_link = urljoin(mirror_url, download_link)
                            self.logger.debug(f"Found link (file extension): {download_link}")
                            break
                
                if not download_link:
                    self.logger.warning("Could not find download link on mirror page")
                    page_title = soup.title.string if soup.title else 'No title'
                    self.logger.info(f"Page title: {page_title}")
                    # Log first 500 chars to help debug
                    preview = response.text[:500].replace('\n', ' ').replace('\r', '')
                    self.logger.info(f"Page preview: {preview}...")
                    return None
                
                self.logger.info(f"Downloading from: {download_link}")
                return self.download_direct(download_link, title=title, resume_attempts=resume_attempts)
                
            except requests.RequestException as e:
                if attempt < retry_on_500 - 1:
                    wait_time = 2 ** attempt
                    self.logger.warning(f"Request error: {e}, retrying in {wait_time}s (attempt {attempt + 1}/{retry_on_500})")
                    time.sleep(wait_time)
                    continue
                else:
                    self.logger.error(f"Error downloading after {retry_on_500} attempts: {e}")
                    return None
            except Exception as e:
                self.logger.error(f"Error downloading: {e}")
                return None
        
        return None
    
    def download(self, input_string, prefer_mirror=None, resume_attempts=3, title_override=None):
        """
        Main download function.
        Tries fast download first (if enabled), then falls back to mirrors.
        Returns: (success: bool, used_fast_download: bool)
        """
        # Extract MD5
        md5 = self.extract_md5(input_string)
        if not md5:
            self.logger.error("Could not extract MD5 from input")
            return False, False
        
        self.logger.debug(f"MD5: {md5}")
        
        # Get title - use override if provided, otherwise fetch from page
        if title_override:
            title = title_override
            self.logger.debug(f"Using provided title: {title}")
            # Still need to get links
            _, links = self.get_download_links(md5)
        else:
            title, links = self.get_download_links(md5)
            self.logger.debug(f"Fetched title: {title}")
        
        # Try fast download first
        if self.fast_download_enabled and self.fast_download_key:
            success, result = self.try_fast_download(md5)
            
            if success:
                # We got a fast download URL
                self.logger.info("Using fast download")
                filepath = self.download_direct(result, title=title, resume_attempts=resume_attempts)
                if filepath:
                    self.logger.info("✓ Fast download successful")
                    return True, True
                else:
                    self.logger.warning("Fast download URL obtained but download failed, falling back to mirrors")
            else:
                # Fast download not available or failed
                self.logger.info(f"Fast download not available: {result}")
                self.logger.info("Falling back to mirror download")
        
        # Fall back to mirror download
        self.logger.info("Using mirror download")
        
        if not links:
            self.logger.warning("No download links found")
            return False, False
        
        self.logger.debug(f"Found {len(links)} download link(s)")
        
        # Select mirror priority
        mirrors_to_try = []
        
        # If user has a preferred mirror, try it first
        if prefer_mirror:
            for link in links:
                if prefer_mirror.lower() in link['domain'].lower():
                    mirrors_to_try.append(link)
            # Add remaining mirrors
            for link in links:
                if link not in mirrors_to_try:
                    mirrors_to_try.append(link)
        else:
            # Use all mirrors in order
            mirrors_to_try = links
        
        # Try each mirror until one succeeds
        for i, mirror_link in enumerate(mirrors_to_try):
            self.logger.info(f"Trying mirror {i+1}/{len(mirrors_to_try)}: {mirror_link['domain']}")
            
            filepath = self.download_from_libgen(mirror_link['url'], title=title, resume_attempts=resume_attempts)
            
            if filepath:
                return True, False
            else:
                self.logger.warning(f"Mirror {mirror_link['domain']} failed")
                if i < len(mirrors_to_try) - 1:
                    self.logger.info("Trying next mirror...")
        
        # All mirrors failed
        self.logger.error("All mirrors failed")
        return False, False
    
    def get_fast_download_info(self):
        """Get current fast download status."""
        return self.fast_download_info.copy()
    
    def refresh_fast_download_info(self, force=False):
        """
        Refresh fast download info from API without attempting a download.
        Respects 1-hour cooldown unless force=True.
        """
        if not self.fast_download_enabled or not self.fast_download_key:
            return False
        
        # Check cooldown (unless forced)
        if not force:
            time_since_refresh = time.time() - self.fast_download_info.get('last_refresh', 0)
            if time_since_refresh < self.fast_download_refresh_cooldown:
                self.logger.debug(f"Fast download info refresh on cooldown ({int(time_since_refresh)}s since last refresh)")
                return True  # Return True because we have cached data
        
        try:
            # Use a known valid MD5 just to get account info
            test_md5 = 'd6e1dc51a50726f00ec438af21952a45'
            
            params = {
                'md5': test_md5,
                'key': self.fast_download_key,
                'path_index': self.fast_download_config.get('path_index', 0),
                'domain_index': self.fast_download_config.get('domain_index', 0)
            }
            
            response = self.session.get(
                self.fast_download_api_url, 
                params=params, 
                timeout=10
            )
            
            # Parse response
            try:
                data = response.json()
            except Exception:
                return False
            
            # Update fast download info if available
            if 'account_fast_download_info' in data:
                info = data['account_fast_download_info']
                self.fast_download_info.update({
                    'available': True,
                    'downloads_left': info.get('downloads_left'),
                    'downloads_per_day': info.get('downloads_per_day'),
                    'recently_downloaded_md5s': info.get('recently_downloaded_md5s', []),
                    'last_refresh': time.time()  # Update timestamp
                })
                self.logger.debug(f"Refreshed fast download info: {info.get('downloads_left')}/{info.get('downloads_per_day')}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to refresh fast download info: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Download files from Anna's Archive using MD5 or URL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download by MD5
  %(prog)s 1d6fd221af5b9c9bffbd398041013de8
  
  # Download by URL
  %(prog)s https://annas-archive.org/md5/1d6fd221af5b9c9bffbd398041013de8
  
  # With preferred mirror
  %(prog)s 1d6fd221af5b9c9bffbd398041013de8 --mirror libgen.li
  
  # With fast download key
  %(prog)s 1d6fd221af5b9c9bffbd398041013de8 --fast-key YOUR_SECRET_KEY
        """
    )
    
    parser.add_argument(
        'input',
        help='MD5 hash or Anna\'s Archive URL'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='./downloads',
        help='Output directory (default: ./downloads)'
    )
    
    parser.add_argument(
        '--mirror',
        help='Preferred mirror domain (e.g., libgen.li)'
    )
    
    parser.add_argument(
        '--fast-key',
        help='Anna\'s Archive membership secret key for fast downloads'
    )
    
    args = parser.parse_args()
    
    # Setup fast download config
    fast_config = None
    if args.fast_key:
        fast_config = {
            'enabled': True,
            'key': args.fast_key,
            'api_url': 'https://annas-archive.org/dyn/api/fast_download.json',
            'path_index': 0,
            'domain_index': 0
        }
    
    downloader = AnnaDownloader(output_dir=args.output, fast_download_config=fast_config)
    
    # Download
    success, _ = downloader.download(args.input, prefer_mirror=args.mirror)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()