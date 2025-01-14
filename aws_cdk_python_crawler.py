#!/usr/bin/env python3

from datetime import datetime
from urllib.parse import urljoin, urlparse
import asyncio
import os
import json
import random
from bs4 import BeautifulSoup

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

DEBUG = True

class CDKPythonDocCrawler:
    def __init__(self, max_concurrent=5):
        self.base_output_dir = "output"
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Track visited URLs to prevent infinite loops
        self._visited_urls = set()
        self._processing_urls = set()  # Track URLs being processed
        
        # Define sources with extraction strategies
        self.sources = {
            "cdk_python": {
                "url": "https://docs.aws.amazon.com/cdk/api/v2/python/modules.html",
                "output_dir": "cdk_python",
                "index_config": CrawlerRunConfig(
                    wait_for="css:.toctree-wrapper",  # Wait for Sphinx toctree
                    wait_until="networkidle",
                    process_iframes=True,
                    only_text=False,
                    css_selector=".toctree-wrapper",  # Get Sphinx toctree
                    page_timeout=120000  # 120 seconds timeout
                ),
                "page_config": CrawlerRunConfig(
                    wait_for="css:section",  # Wait for content section
                    wait_until="networkidle",
                    process_iframes=True,
                    only_text=False,
                    css_selector="section",  # Get content section
                    page_timeout=120000  # 120 seconds timeout
                )
            }
        }
    
    def save_markdown(self, source_key: str, module_name: str, content: str):
        """Save content as markdown file."""
        output_dir = os.path.join(self.base_output_dir, self.sources[source_key]["output_dir"])
        os.makedirs(output_dir, exist_ok=True)
        
        filename = os.path.join(output_dir, f"{module_name}.md")
        print(f"Saving markdown to {filename}")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Saved markdown to {filename}")
    
    def save_json(self, source_key: str, module_name: str, data: dict):
        """Save structured data as JSON."""
        output_dir = os.path.join(self.base_output_dir, self.sources[source_key]["output_dir"])
        os.makedirs(output_dir, exist_ok=True)
        
        filename = os.path.join(output_dir, f"{module_name}.json")
        print(f"Saving JSON to {filename}")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Saved JSON to {filename}")
    
    def _normalize_url(self, base_url: str, href: str) -> str:
        """Normalize URL to absolute form."""
        if href.startswith('http'):
            return href
        elif href.startswith('/'):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}://{parsed.netloc}{href}"
        else:
            return urljoin(base_url, href)
    
    def _is_valid_cdk_link(self, url: str) -> bool:
        """Check if URL is a valid CDK documentation link."""
        return (
            'docs.aws.amazon.com/cdk/api/v2/python' in url and
            not any(x in url.lower() for x in [
                'privacy', 'terms', 'conditions', 'contributing',
                'license', 'notice', 'readme', 'changelog'
            ]) and
            not url.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')) and
            '#' not in url
        )
    
    def _is_404_page(self, soup: BeautifulSoup) -> bool:
        """Check if the page is a 404 error page."""
        # Check for AWS 404 page indicators
        meta_page_type = soup.find('meta', {'name': 'page-type'})
        if meta_page_type and meta_page_type.get('content') == 'errorPage':
            return True
        
        # Check for common 404 indicators
        title = soup.find('title')
        if title and any(x in title.text.lower() for x in ['404', 'not found', 'error']):
            return True
        
        h1 = soup.find('h1')
        if h1 and any(x in h1.text.lower() for x in ['looking for something', '404', 'not found']):
            return True
        
        return False

    async def _retry_with_backoff(self, func, *args, max_retries=3, **kwargs):
        """Retry a function with exponential backoff."""
        last_error = None
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt == max_retries - 1:
                    break
                wait_time = (2 ** attempt) + (random.random() * 0.1)
                print(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {wait_time:.2f}s...")
                await asyncio.sleep(wait_time)
        
        print(f"All {max_retries} attempts failed. Last error: {str(last_error)}")
        raise last_error
    
    async def process_page(self, source_key: str, crawler: AsyncWebCrawler, url: str = None):
        """Process a single page with improved error handling."""
        source = self.sources[source_key]
        if url is None:
            url = source["url"]
        
        # Skip if already visited, being processed, or invalid
        if (url in self._visited_urls or 
            url in self._processing_urls or 
            not self._is_valid_cdk_link(url)):
            return []
        
        # Mark as being processed
        self._processing_urls.add(url)
        
        try:
            async with self.semaphore:  # Control concurrency
                # Determine page type and config
                is_index = 'modules.html' in url
                config = source["index_config"] if is_index else source["page_config"]
                
                print(f"\nProcessing {'index' if is_index else 'module'} page: {url}")
                
                # Use retry mechanism for page loading
                result = await self._retry_with_backoff(
                    crawler.arun,
                    url=url,
                    config=config,
                    max_retries=3
                )
                
                if not result.success:
                    print(f"Failed to load {url}: {result.error_message}")
                    return []
                
                # Parse HTML content
                soup = BeautifulSoup(result.html, 'html.parser')
                
                # Check for 404 page
                if self._is_404_page(soup):
                    print(f"Skipping 404 page: {url}")
                    return []
                
                discovered_links = []
                if is_index:
                    # For index page, look for toctree entries
                    content_div = soup.select_one('.toctree-wrapper')
                    if not content_div:
                        print(f"No toctree found in {url}")
                        if DEBUG:
                            print("\nAvailable classes:")
                            for elem in soup.find_all(class_=True):
                                classes = elem.get('class', [])
                                if isinstance(classes, list):
                                    print(f"Found element with classes: {' '.join(classes)}")
                                else:
                                    print(f"Found element with class: {classes}")
                        return []
                    
                    # Process toctree links
                    for link in content_div.select('a.reference.internal'):
                        href = link.get('href', '')
                        if href and not href.startswith(('#', 'javascript:')):
                            abs_url = self._normalize_url(url, href)
                            if (abs_url not in self._visited_urls and 
                                abs_url not in self._processing_urls and 
                                self._is_valid_cdk_link(abs_url)):
                                discovered_links.append(abs_url)
                                print(f"Found link: {abs_url}")
                    
                    # Save index content
                    content = "# AWS CDK Python Modules\n\n"
                    for link in content_div.select('li.toctree-l1'):
                        module_link = link.find('a')
                        if module_link:
                            content += f"- [{module_link.get_text()}]({module_link.get('href', '')})\n"
                    
                    self.save_markdown(source_key, "index", content)
                    self.save_json(source_key, "index", {
                        "url": url,
                        "module_name": "index",
                        "content": content,
                        "links": discovered_links,
                        "timestamp": datetime.now().isoformat(),
                        "type": "index"
                    })
                else:
                    # For content pages, look for section content
                    content_div = soup.select_one('section')
                    if not content_div:
                        print(f"No content found in {url}")
                        if DEBUG:
                            print("\nAvailable classes:")
                            for elem in soup.find_all(class_=True):
                                classes = elem.get('class', [])
                                if isinstance(classes, list):
                                    print(f"Found element with classes: {' '.join(classes)}")
                                else:
                                    print(f"Found element with class: {classes}")
                        return []
                    
                    # Process content links
                    for link in content_div.find_all('a'):
                        href = link.get('href', '')
                        if href and not href.startswith(('#', 'javascript:')):
                            abs_url = self._normalize_url(url, href)
                            if (abs_url not in self._visited_urls and 
                                abs_url not in self._processing_urls and 
                                self._is_valid_cdk_link(abs_url)):
                                discovered_links.append(abs_url)
                                print(f"Found link: {abs_url}")
                    
                    # Save content
                    module_name = os.path.splitext(os.path.basename(url))[0]
                    content = content_div.get_text(separator='\n\n', strip=True)
                    
                    # Save as markdown with better formatting
                    markdown_content = f"""# {module_name}

Source: {url}

{content}
"""
                    self.save_markdown(source_key, module_name, markdown_content)
                    
                    # Save as JSON with additional metadata
                    data = {
                        "url": url,
                        "module_name": module_name,
                        "content": content,
                        "links": discovered_links,
                        "timestamp": datetime.now().isoformat(),
                        "type": "module"
                    }
                    self.save_json(source_key, module_name, data)
                
                # Mark as visited after successful processing
                self._visited_urls.add(url)
                self._processing_urls.remove(url)
                
                return discovered_links
                
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            # Ensure URL is removed from processing set even if an error occurs
            self._processing_urls.discard(url)
    
    async def crawl(self):
        """Crawl AWS CDK Python documentation."""
        browser_config = BrowserConfig(
            headless=True,
            ignore_https_errors=True
        )
        
        async with AsyncWebCrawler(
            browser_config=browser_config,
            max_concurrent_pages=self.max_concurrent
        ) as crawler:
            try:
                # Start with the index page
                links_to_process = await self.process_page("cdk_python", crawler)
                
                # Process discovered links in parallel
                while links_to_process:
                    # Process links in parallel
                    tasks = []
                    for link in links_to_process:
                        if (link not in self._visited_urls and 
                            link not in self._processing_urls):
                            task = asyncio.create_task(
                                self.process_page("cdk_python", crawler, link)
                            )
                            tasks.append(task)
                    
                    if not tasks:
                        break
                    
                    # Wait for all tasks to complete and collect new links
                    results = await asyncio.gather(*tasks)
                    links_to_process = []
                    for new_links in results:
                        links_to_process.extend(new_links)
                    
                    # Add small delay between batches to prevent overwhelming
                    await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"Error during crawl: {str(e)}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    crawler = CDKPythonDocCrawler(max_concurrent=5)  # Process 5 pages concurrently
    asyncio.run(crawler.crawl())
