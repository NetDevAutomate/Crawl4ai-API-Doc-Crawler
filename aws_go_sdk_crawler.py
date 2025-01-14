"""AWS Go SDK v2 documentation crawler using native Crawl4AI methods."""

from datetime import datetime
from typing import Dict, Any, Optional, List, Set
from urllib.parse import urljoin
import asyncio
import os
import json
import time
import random
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from base import BaseDocCrawler, SDKConfig

class GoSDKCrawler(BaseDocCrawler):
    """Crawler for AWS Go SDK v2 documentation using native Crawl4AI methods."""
    
    def __init__(self, output_dir: str, config: Optional[SDKConfig] = None):
        if config is None:
            config = SDKConfig(
                base_url="https://pkg.go.dev/github.com/aws/aws-sdk-go-v2",
                provider="aws",
                sdk_version="latest"
            )
        super().__init__(output_dir, config)
        self._visited_urls = set()
        self._pending_urls = asyncio.Queue()
        self._active_workers = 0
        self._worker_lock = asyncio.Lock()
        
        # Define sources with extraction strategies
        self.sources = {
            "gosdk_aws": {
                "url": "https://pkg.go.dev/github.com/aws/aws-sdk-go-v2/service",
                "output_dir": "gosdk_aws",
                "service_list_config": CrawlerRunConfig(
                    wait_for="css:.Documentation-content",  # Wait for documentation content
                    wait_until="networkidle",
                    process_iframes=True,
                    only_text=False,
                    css_selector=".Documentation-content"  # Get documentation content
                ),
                "service_config": CrawlerRunConfig(
                    wait_for="css:.Documentation-content",
                    wait_until="networkidle",
                    process_iframes=True,
                    only_text=False,
                    css_selector=".Documentation-content"
                ),
                "operation_config": CrawlerRunConfig(
                    wait_for="css:.Documentation-content",
                    wait_until="networkidle",
                    process_iframes=True,
                    only_text=False,
                    css_selector=".Documentation-content"
                )
            }
        }
        
        # Add cache tracking
        self._operation_cache: Dict[str, Set[str]] = {}
        self._cache_file = os.path.join(output_dir, "gosdk_aws", "cache.json")
        self._load_cache()

    def _load_cache(self):
        """Load cache from file if it exists."""
        if os.path.exists(self._cache_file):
            try:
                with open(self._cache_file, 'r') as f:
                    cache_data = json.load(f)
                    self._operation_cache = {k: set(v) for k, v in cache_data.items()}
                print(f"Loaded cache from {self._cache_file}")
            except Exception as e:
                print(f"Error loading cache: {str(e)}")
                self._operation_cache = {}

    def _save_cache(self):
        """Save cache to file."""
        try:
            os.makedirs(os.path.dirname(self._cache_file), exist_ok=True)
            with open(self._cache_file, 'w') as f:
                cache_data = {k: list(v) for k, v in self._operation_cache.items()}
                json.dump(cache_data, f, indent=2)
            print(f"Saved cache to {self._cache_file}")
        except Exception as e:
            print(f"Error saving cache: {str(e)}")

    async def _retry_with_backoff(self, func, *args, max_retries=3, **kwargs):
        """Retry a function with exponential backoff."""
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                wait_time = (2 ** attempt) + (random.random() * 0.1)
                print(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)

    async def process_page(self, source_key: str, crawler: AsyncWebCrawler, url: str):
        """Process a single page with improved error handling."""
        if url in self._visited_urls:
            return
        
        self._visited_urls.add(url)
        source = self.sources[source_key]
        
        try:
            # Determine the type of page and its config
            if '/service' in url and url.count('/') == 7:
                config = source["service_list_config"]
                page_type = "service_list"
            elif '/service/' in url and url.count('/') == 8:
                config = source["service_config"]
                page_type = "service"
            else:
                config = source["operation_config"]
                page_type = "operation"
            
            print(f"\nProcessing {page_type} page: {url}")
            
            # Use retry mechanism for page loading
            result = await self._retry_with_backoff(
                crawler.arun,
                url=url,
                config=config,
                max_retries=3
            )
            
            if not result.success:
                print(f"Failed to load {url}: {result.error_message}")
                return
            
            soup = BeautifulSoup(result.html, 'html.parser')
            
            if page_type == "service_list":
                # Process service list page
                for link in soup.select('a[href*="/service/"]'):
                    service_url = urljoin(url, link['href'])
                    if service_url not in self._visited_urls:
                        await self._pending_urls.put(service_url)
                        
            elif page_type == "service":
                # Process service page
                service_name = url.split('/')[-1]
                content = soup.get_text()
                
                # Save documentation
                self.save_markdown(source_key, service_name, f"# {service_name}\n\n{content}")
                self.save_json(source_key, service_name, {
                    "url": url,
                    "service": service_name,
                    "content": content,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Find operation links
                for link in soup.select('a[href*="/service/"]'):
                    op_url = urljoin(url, link['href'])
                    if op_url not in self._visited_urls:
                        await self._pending_urls.put(op_url)
                        
            else:  # operation page
                operation_name = url.split('/')[-1]
                service_name = url.split('/')[-2]
                
                if service_name not in self._operation_cache:
                    self._operation_cache[service_name] = set()
                
                if operation_name not in self._operation_cache[service_name]:
                    self._operation_cache[service_name].add(operation_name)
                    print(f"Added operation {operation_name} to service {service_name}")
                    self._save_cache()
            
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    async def crawl(self):
        """Crawl all AWS Go SDK v2 documentation."""
        browser_config = BrowserConfig(
            headless=True,
            ignore_https_errors=True,
            timeout=60000  # Increase timeout to 60 seconds
        )
        
        async with AsyncWebCrawler(
            browser_config=browser_config,
            max_concurrent_pages=1  # Reduce concurrency to prevent timing issues
        ) as crawler:
            for source_key, source in self.sources.items():
                # Start with the service list
                await self._pending_urls.put(source["url"])
                
                while not self._pending_urls.empty():
                    url = await self._pending_urls.get()
                    try:
                        await self.process_page(source_key, crawler, url)
                        # Add small delay between requests
                        await asyncio.sleep(1)
                    except Exception as e:
                        print(f"Error crawling {url}: {str(e)}")
                    finally:
                        self._pending_urls.task_done()

    def save_json(self, source_key: str, name: str, data: Dict[str, Any]):
        """Save data as JSON file."""
        source = self.sources[source_key]
        output_dir = os.path.join(self.output_dir, source["output_dir"])
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{name}.json"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved JSON to {filepath}")

    def save_markdown(self, source_key: str, name: str, content: str):
        """Save content as markdown file."""
        source = self.sources[source_key]
        output_dir = os.path.join(self.output_dir, source["output_dir"])
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{name}.md"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Saved markdown to {filepath}")

if __name__ == "__main__":
    crawler = GoSDKCrawler("output")
    asyncio.run(crawler.crawl())