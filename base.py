"""Base classes for documentation crawlers."""

import os
import time
import asyncio
import aiohttp
import traceback
import json
import random
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from bs4 import BeautifulSoup, Comment
from urllib.parse import urlparse
import html2text
from datetime import datetime, timedelta
from pathlib import Path

@dataclass
class CrawlerConfig:
    """Base configuration for crawlers."""
    base_url: str
    provider: str

@dataclass
class RegistryConfig(CrawlerConfig):
    """Configuration for a registry provider."""
    namespace: str
    docs_url: str = "https://api.github.com/repos/hashicorp/terraform-provider-aws/contents"
    
    @property
    def provider_url(self) -> str:
        """Get the provider URL."""
        return f"{self.base_url}/providers/{self.namespace}/{self.provider}"

class SDKConfig(CrawlerConfig):
    """Configuration for SDK documentation crawlers."""

    def __init__(self, base_url: str = "", provider: str = "aws", sdk_version: str = ""):
        """Initialize SDK configuration."""
        self.base_url = base_url
        self.provider = provider
        self.sdk_version = sdk_version

    @property
    def docs_url(self) -> str:
        """Get the documentation URL."""
        return f"{self.base_url}/{self.sdk_version}/docs"

class TerraformConfig(RegistryConfig):
    """Configuration for Terraform provider documentation."""
    def __init__(self):
        self.namespace = "hashicorp"
        self.provider = "aws"
        self.base_url = "https://registry.terraform.io/v1/providers"
        super().__init__(self.base_url, self.provider)

class CacheManager:
    """Cache manager for storing API responses."""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_key(self, url: str) -> str:
        """Generate a cache key from URL."""
        return hashlib.sha256(url.encode()).hexdigest()
    
    def _get_cache_path(self, key: str) -> Path:
        """Get cache file path for a key."""
        return self.cache_dir / f"{key}.json"
    
    def get(self, url: str) -> Optional[Any]:
        """Get cached response for URL."""
        key = self._get_cache_key(url)
        cache_path = self._get_cache_path(key)
        
        if cache_path.exists():
            try:
                with cache_path.open('r') as f:
                    cached = json.load(f)
                    # Check if cache is still valid (24 hours)
                    if time.time() - cached['timestamp'] < 24 * 60 * 60:
                        print(f"Cache hit for: {url}", flush=True)
                        return cached['data']
                    else:
                        print(f"Cache expired for: {url}", flush=True)
            except Exception as e:
                print(f"Cache read error for {url}: {e}", flush=True)
        return None

    def set(self, url: str, data: Any) -> None:
        """Cache response data for URL."""
        key = self._get_cache_key(url)
        cache_path = self._get_cache_path(key)
        
        try:
            with cache_path.open('w') as f:
                json.dump({
                    'timestamp': time.time(),
                    'data': data
                }, f)
            print(f"Cached response for: {url}", flush=True)
        except Exception as e:
            print(f"Cache write error for {url}: {e}", flush=True)

class RateLimiter:
    """Rate limiter for API requests."""
    
    def __init__(self, requests_per_second: int = 2):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0
    
    async def wait(self):
        """Wait if necessary to maintain rate limit."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.min_interval:
            delay = self.min_interval - elapsed
            await asyncio.sleep(delay)
        
        self.last_request_time = time.time()

class DocumentFormatter:
    """Format and save documentation."""
    
    def __init__(self, output_dir: str):
        """Initialize the formatter."""
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def save_markdown(self, prefix: str, name: str, content: str):
        """Save content as markdown file."""
        output_dir = os.path.join(self.output_dir, prefix)
        os.makedirs(output_dir, exist_ok=True)
        
        output_file = os.path.join(output_dir, f"{name}.md")
        with open(output_file, 'w') as f:
            f.write(content)

    def save_json(self, prefix: str, name: str, content: Dict[str, Any]):
        """Save content as JSON."""
        try:
            # Sanitize prefix and name
            safe_prefix = prefix.replace('..', '').replace('/', '_')
            safe_name = name.replace('..', '').replace('/', '_')
            
            # Create output directory if it doesn't exist
            dir_path = os.path.join(self.output_dir, safe_prefix, 'json')
            os.makedirs(dir_path, exist_ok=True)
            
            # Save JSON file
            file_path = os.path.join(dir_path, f"{safe_name}.json")
            with open(file_path, 'w') as f:
                json.dump(content, f, indent=2)
        except Exception as e:
            print(f"Error saving JSON file: {str(e)}")
            print(f"  prefix: {prefix}")
            print(f"  name: {name}")
            print(f"  safe_prefix: {safe_prefix}")
            print(f"  safe_name: {safe_name}")
            print(f"  dir_path: {dir_path}")
            print(f"  file_path: {file_path}")
            raise

class BaseDocCrawler(ABC):
    """Base class for documentation crawlers."""

    def __init__(self, output_dir: str, config: Optional[SDKConfig] = None):
        """Initialize the crawler."""
        self.output_dir = output_dir
        self.config = config or SDKConfig()
        self.debug = False
        self.cache = CacheManager()
        self.formatter = DocumentFormatter(output_dir)
        self._service_mappings = None

    def _load_service_mappings(self) -> Dict[str, str]:
        """Load service mappings from config file."""
        if self._service_mappings is None:
            try:
                # Create config directory if it doesn't exist
                config_dir = Path(__file__).parent / "config"
                config_dir.mkdir(exist_ok=True)
                
                config_path = config_dir / "service_mappings.json"
                if config_path.exists():
                    print(f"\nLoading service mappings from {config_path}", flush=True)
                    with config_path.open('r') as f:
                        mappings = json.load(f)
                        crawler_type = self.name.lower() if hasattr(self, 'name') else 'default'
                        self._service_mappings = mappings.get(crawler_type, {})
                        print(f"Loaded {len(self._service_mappings)} service mappings for {crawler_type}", flush=True)
                else:
                    print(f"\nNo service mappings found at {config_path}", flush=True)
                    self._service_mappings = {}
            except Exception as e:
                print(f"\nError loading service mappings: {e}", flush=True)
                self._service_mappings = {}
        return self._service_mappings

    def normalize_service_name(self, service: str) -> str:
        """Normalize service name."""
        mappings = self._load_service_mappings()
        return mappings.get(service, service)

    async def _rate_limited_request(self, session, url: str, headers: Optional[Dict] = None, 
                                  method: str = 'GET', use_cache: bool = True, **kwargs) -> Optional[Any]:
        """Make a rate-limited request with retries and caching."""
        if not headers:
            headers = {}

        # Check cache first if enabled
        if use_cache:
            cached_data = self.cache.get(url)
            if cached_data is not None:
                self.log(f"Cache hit for {url}", always=False)
                return cached_data

        # Add GitHub token if available and if it's a GitHub URL
        if 'api.github.com' in url:
            gh_token = os.getenv('GITHUB_TOKEN')  # First try environment variable
            if not gh_token:
                try:
                    gh_token = os.popen('gh auth token 2>/dev/null').read().strip()  # Then try GitHub CLI
                except Exception:
                    pass
                    
            if gh_token:
                headers['Authorization'] = f'Bearer {gh_token}'
                headers['Accept'] = 'application/vnd.github.v3+json'
            else:
                print("Warning: No GitHub token found. API rate limits will be restricted.", flush=True)
        
        # Implement token bucket rate limiting
        now = time.time()
        self._request_times = [t for t in self._request_times if now - t < 60]
        if len(self._request_times) >= self._requests_per_minute:
            wait_time = 60 - (now - self._request_times[0])
            if wait_time > 0:
                print(f"Rate limit reached, waiting {wait_time:.1f} seconds...", flush=True)
                await asyncio.sleep(wait_time)

        async with self._rate_limit:
            for attempt in range(self._max_retries + 1):
                try:
                    if attempt > 0:
                        delay = self._retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                        print(f"Retry {attempt}/{self._max_retries} for {url} after {delay:.1f}s", flush=True)
                        await asyncio.sleep(delay)

                    async with session.request(method, url, headers=headers, **kwargs) as response:
                        self._request_times.append(time.time())

                        if response.status == 200:
                            if 'application/json' in response.headers.get('Content-Type', ''):
                                data = await response.json()
                            else:
                                data = await response.text()
                            
                            # Cache successful responses if caching is enabled
                            if use_cache:
                                self.cache.set(url, data)
                            return data
                            
                        elif response.status == 429:  # Too Many Requests
                            if attempt < self._max_retries:
                                retry_after = int(response.headers.get('Retry-After', 5))
                                print(f"Rate limited, waiting {retry_after}s before retry...", flush=True)
                                await asyncio.sleep(retry_after)
                                continue
                        elif response.status == 404:
                            print(f"Resource not found: {url}", flush=True)
                            return None
                        else:
                            print(f"Request failed with status {response.status}: {url}", flush=True)
                            if attempt < self._max_retries:
                                continue
                            return None

                except Exception as e:
                    print(f"Request error: {str(e)}", flush=True)
                    if attempt < self._max_retries:
                        continue
                    return None

        return None

    def log(self, message: str, always: bool = False) -> None:
        """Log a message if debug is enabled or always is True."""
        if self.debug or always:
            print(message, flush=True)

    @property
    def debug(self) -> bool:
        """Get debug mode."""
        return self._debug

    @debug.setter
    def debug(self, value: bool) -> None:
        """Set debug mode."""
        self._debug = value

    async def crawl(self, service: str = None):
        """Base crawl method to be implemented by subclasses."""
        self.log(f"=== Starting {self.__class__.__name__} ===", always=True)
        try:
            await self._crawl(service)
        except Exception as e:
            self.log(f"Error in {self.__class__.__name__}: {e}", always=True)
            if self._debug:
                import traceback
                traceback.print_exc()
        finally:
            self.log(f"=== {self.__class__.__name__} Completed ===", always=True)

    async def _crawl(self, service: str = None):
        """Internal crawl method to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _crawl method")

    async def get_service_list(self, session) -> List[str]:
        """Get list of services. To be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement get_service_list method")

    async def process_service(self, session, service: str, total_services: int, current: int) -> Optional[Dict[str, Any]]:
        """Process a single service. To be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement process_service method")

    async def fetch_page(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        """Fetch a page with rate limiting and caching."""
        return await self._rate_limited_request(session, url)
