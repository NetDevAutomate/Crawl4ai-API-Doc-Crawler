"""Terraform documentation crawler using native Crawl4AI methods."""

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from urllib.parse import urljoin, urlparse
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from base import BaseDocCrawler, SDKConfig
from bs4 import BeautifulSoup

class TerraformNativeCrawler(BaseDocCrawler):
    """Crawler for HashiCorp Terraform AWS Provider documentation using native Crawl4AI methods."""
    
    def __init__(self, output_dir: str, config: Optional[SDKConfig] = None):
        if config is None:
            config = SDKConfig(
                base_url="https://github.com/hashicorp/terraform-provider-aws/tree/main/website/docs",
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
            "terraform_aws": {
                "url": "https://github.com/hashicorp/terraform-provider-aws/tree/main/website/docs",
                "output_dir": "terraform_aws",
                "index_config": CrawlerRunConfig(
                    wait_for="css:div.react-directory-filename-column",  # Wait for file listing
                    wait_until="networkidle",
                    process_iframes=True,
                    only_text=False,
                    css_selector="div.Box-sc-g0xbh4-0"  # Get GitHub content
                ),
                "page_config": CrawlerRunConfig(
                    wait_for="css:article.markdown-body",  # Wait for markdown content
                    wait_until="networkidle",
                    process_iframes=True,
                    only_text=False,
                    css_selector="article.markdown-body"  # Get markdown content
                )
            }
        }
    
    def _normalize_url(self, base_url: str, href: str) -> Optional[str]:
        """Normalize URL and check if it should be crawled."""
        if not href or href.startswith(('#', 'javascript:', 'mailto:')):
            return None
            
        # Convert relative URL to absolute
        if not href.startswith('http'):
            href = urljoin(base_url, href)
        
        # Remove any anchor fragments
        href = href.split('#')[0]
        
        # Check if this is a Terraform AWS provider GitHub docs URL
        if not any(
            pattern in href 
            for pattern in [
                '/hashicorp/terraform-provider-aws/tree/main/website/docs',
                '/hashicorp/terraform-provider-aws/blob/main/website/docs'
            ]
        ):
            return None
            
        return href
    
    def _is_index_page(self, url: str) -> bool:
        """Determine if URL is an index/directory page."""
        return '/tree/main/' in url
    
    def _get_resource_name(self, url: str) -> str:
        """Extract resource name from URL."""
        parts = url.rstrip('/').split('/')
        
        # Handle different URL patterns
        if 'docs' in parts:
            idx = parts.index('docs')
            # Get all parts after docs
            resource_parts = parts[idx + 1:]
            if not resource_parts:
                return 'index'
            # Join all parts with underscores and remove .html.markdown extension
            name = '_'.join(resource_parts)
            return name.replace('.html.markdown', '')
        
        return 'index'
    
    async def process_page(self, source_key: str, crawler: AsyncWebCrawler, url: str = None) -> List[str]:
        """Process a single page and return list of discovered URLs."""
        source = self.sources[source_key]
        if url is None:
            url = source["url"]
        
        # Skip if already visited
        if url in self._visited_urls:
            print(f"Already visited {url}, skipping")
            return []
        
        # Mark as visited
        self._visited_urls.add(url)
        
        # Determine page type based on URL
        is_index = self._is_index_page(url)
        config = source.get("index_config" if is_index else "page_config")
        
        print(f"Processing {url} {'(index page)' if is_index else '(content page)'}")
        
        discovered_urls = []
        if config:
            try:
                # Load the page with specific config
                result = await asyncio.wait_for(
                    crawler.arun(url=url, config=config),
                    timeout=30
                )
                
                if not result or not result.success:
                    print(f"Failed to load page {url}")
                    return []
                
                # Parse the HTML
                soup = BeautifulSoup(result.html, 'html.parser')
                
                # Extract links based on page type
                links = []
                seen_hrefs = set()
                
                if is_index:
                    # For index pages, look for directory and file links
                    for row in soup.select("div.react-directory-filename-column"):
                        link = row.find('a')
                        if link:
                            href = link.get('href', '')
                            text = link.get_text().strip()
                            
                            # Skip navigation and index links
                            if (href and not href.startswith(('http', '#')) and 
                                text and not text.lower() in ['index', 'search', 'next', 'previous']):
                                
                                # Convert relative URL to absolute
                                if not href.startswith('http'):
                                    href = urljoin(url, href)
                                
                                # Skip if we've seen this href before
                                if href in seen_hrefs:
                                    continue
                                seen_hrefs.add(href)
                                
                                print(f"Found link: {text} -> {href}")
                                links.append({
                                    'href': href,
                                    'text': text
                                })
                                discovered_urls.append(href)
                    
                    # Save directory listing
                    resource_name = self._get_resource_name(url)
                    doc_structure = {
                        "url": url,
                        "resource": resource_name,
                        "navigation": links,
                        "timestamp": datetime.now().isoformat()
                    }
                    self.save_json(source_key, resource_name, doc_structure)
                    print(f"Saved directory listing for {resource_name}")
                    
                else:
                    # For content pages, get the markdown content
                    content = soup.select_one("article.markdown-body")
                    if content:
                        # Clean up content
                        for el in content.select('.headerlink, .highlight-default'):
                            el.decompose()
                        
                        # Extract content
                        text_content = content.get_text(strip=True)
                        
                        # Get resource name
                        resource_name = self._get_resource_name(url)
                        print(f"Saving content for {resource_name}")
                        
                        # Save the content as markdown
                        if text_content:
                            markdown_content = f"# {resource_name}\n\n"
                            markdown_content += f"URL: {url}\n\n"
                            markdown_content += text_content
                            
                            # Save markdown file
                            self.save_markdown(source_key, resource_name, markdown_content)
                            
                            # Save JSON for LLM consumption
                            doc_structure = {
                                "url": url,
                                "resource": resource_name,
                                "content": text_content,
                                "navigation": [],
                                "timestamp": datetime.now().isoformat()
                            }
                            self.save_json(source_key, resource_name, doc_structure)
                            print(f"Saved content for {resource_name}")
            
            except asyncio.TimeoutError:
                print(f"Timeout processing {url}")
            except Exception as e:
                print(f"Error processing {url}: {str(e)}")
                import traceback
                traceback.print_exc()
        
        return discovered_urls
    
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
    
    async def worker(self, source_key: str, crawler: AsyncWebCrawler, worker_id: int):
        """Worker to process pages from the queue."""
        async with self._worker_lock:
            self._active_workers += 1
        
        try:
            while True:
                try:
                    url = await self._pending_urls.get()
                    if url is None:  # Poison pill
                        break
                    
                    discovered_urls = await self.process_page(source_key, crawler, url)
                    
                    # Add discovered URLs to queue
                    for href in discovered_urls:
                        if href not in self._visited_urls:
                            await self._pending_urls.put(href)
                    
                    self._pending_urls.task_done()
                except Exception as e:
                    print(f"Worker {worker_id} error: {str(e)}")
                    self._pending_urls.task_done()
        finally:
            async with self._worker_lock:
                self._active_workers -= 1
                if self._active_workers == 0:
                    # Signal that all workers are done
                    self._pending_urls.task_done()

    async def crawl(self, source_key: str = "terraform_aws", num_workers: int = 3):
        """Crawl the documentation using parallel workers."""
        browser_config = BrowserConfig(
            headless=True,
            ignore_https_errors=True
        )
        
        # Create a single crawler instance to be shared
        async with AsyncWebCrawler(
            browser_config=browser_config,
            max_concurrent_pages=num_workers  # Allow concurrent page processing
        ) as crawler:
            # Add initial URL to queue
            source = self.sources[source_key]
            await self._pending_urls.put(source["url"])
            
            # Create workers
            workers = []
            for i in range(num_workers):
                worker = asyncio.create_task(self.worker(source_key, crawler, i))
                workers.append(worker)
            
            try:
                # Wait for all URLs to be processed
                await self._pending_urls.join()
                
                # Send poison pills to workers
                for _ in range(num_workers):
                    await self._pending_urls.put(None)
                
                # Wait for workers to finish
                await asyncio.gather(*workers)
            except Exception as e:
                print(f"Error in crawl: {str(e)}")
                # Cancel any remaining workers
                for worker in workers:
                    if not worker.done():
                        worker.cancel()
                # Wait for workers to finish
                await asyncio.gather(*workers, return_exceptions=True)
                raise
            finally:
                # Ensure all workers are done
                for worker in workers:
                    if not worker.done():
                        worker.cancel()
                await asyncio.gather(*workers, return_exceptions=True)

if __name__ == "__main__":
    crawler = TerraformNativeCrawler("output")
    asyncio.run(crawler.crawl()) 