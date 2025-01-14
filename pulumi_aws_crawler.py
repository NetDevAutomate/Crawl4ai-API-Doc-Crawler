"""Pulumi documentation crawler using native Crawl4AI methods."""

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from urllib.parse import urljoin, urlparse
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from base import BaseDocCrawler, SDKConfig
from bs4 import BeautifulSoup

class PulumiNativeCrawler(BaseDocCrawler):
    """Crawler for Pulumi AWS Provider documentation using native Crawl4AI methods."""
    
    def __init__(self, output_dir: str, config: Optional[SDKConfig] = None):
        if config is None:
            config = SDKConfig(
                base_url="https://www.pulumi.com/registry/packages/aws/api-docs",
                provider="aws",
                sdk_version="latest"
            )
        super().__init__(output_dir, config)
        self._visited_urls = set()
        
        # Define sources with extraction strategies
        self.sources = {
            "pulumi_aws": {  
                "url": "https://www.pulumi.com/registry/packages/aws/api-docs",
                "output_dir": "pulumi_aws",  
                "index_config": CrawlerRunConfig(
                    wait_for="css:main",  
                    wait_until="networkidle",
                    process_iframes=True,
                    only_text=False,
                    css_selector="main"  
                ),
                "page_config": CrawlerRunConfig(
                    wait_for="css:article",  
                    wait_until="networkidle",
                    process_iframes=True,
                    only_text=False,
                    css_selector="article"  
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
        
        # Check if this is a Pulumi AWS API docs URL
        if not any(
            pattern in href 
            for pattern in [
                '/registry/packages/aws/api-docs',
                '/docs/reference/pkg/aws'
            ]
        ):
            return None
            
        return href
    
    def _get_resource_name(self, url: str) -> str:
        """Extract resource name from URL."""
        parts = url.rstrip('/').split('/')
        
        # Handle different URL patterns
        if 'api-docs' in parts:
            idx = parts.index('api-docs')
            # Get all parts after api-docs
            resource_parts = parts[idx + 1:]
            if not resource_parts:
                return 'index'
            # Join all parts with underscores
            return '_'.join(resource_parts).replace('.html', '')
        elif 'pkg' in parts and 'aws' in parts:
            idx = parts.index('aws')
            # Get all parts after aws
            resource_parts = parts[idx + 1:]
            if not resource_parts:
                return 'index'
            # Join all parts with underscores
            return '_'.join(resource_parts).replace('.html', '')
        
        return 'index'
    
    async def process_page(self, source_key: str, crawler, url: str = None):
        """Process a single page using Crawl4ai's native extraction."""
        source = self.sources[source_key]
        if url is None:
            url = source["url"]
        
        # Skip if already visited
        if url in self._visited_urls:
            print(f"Already visited {url}, skipping")
            return
        
        # Mark as visited
        self._visited_urls.add(url)
        
        retries = 3  # Number of retries per page
        for attempt in range(retries):
            try:
                # Determine page type and config
                if url.endswith('/api-docs') or url.endswith('/api-docs/'):
                    config = source.get("index_config")
                    is_index = True
                else:
                    config = source.get("page_config")
                    is_index = False
                
                print(f"Crawling {url} {'(index page)' if is_index else '(content page)'} - Attempt {attempt + 1}/{retries}")
                
                if config:
                    try:
                        # First ensure page is loaded
                        pre_config = CrawlerRunConfig(
                            wait_for="css:body",
                            wait_until="domcontentloaded",
                            process_iframes=True,
                            only_text=False,
                            css_selector="body"
                        )
                        
                        # Load the page initially
                        pre_result = await asyncio.wait_for(
                            crawler.arun(url=url, config=pre_config),
                            timeout=30
                        )
                        
                        if not pre_result or not pre_result.success:
                            print(f"Failed initial page load for {url}")
                            raise Exception("Initial page load failed")
                        
                        # Wait a bit for dynamic content
                        await asyncio.sleep(2)
                        
                        # Now load with specific config
                        result = await asyncio.wait_for(
                            crawler.arun(url=url, config=config),
                            timeout=30
                        )
                        
                        if not result or not result.success:
                            print(f"Failed to load page {url}")
                            raise Exception("Page load failed")
                        
                        print(f"Result success: {result.success}")
                        print(f"Result status code: {result.status_code}")
                        print(f"Result error message: {result.error_message}")
                        print(f"Result HTML length: {len(result.html) if result.html else 0}")
                        
                        # Parse the HTML
                        soup = BeautifulSoup(result.html, 'html.parser')
                        
                        # Extract links based on page type
                        links = []
                        if is_index:
                            # For index pages, look for module links
                            for link in soup.find_all('a'):
                                href = link.get('href', '')
                                text = link.get_text().strip()
                                
                                # Normalize URL
                                normalized_href = self._normalize_url(url, href)
                                if normalized_href:
                                    links.append({
                                        'href': normalized_href,
                                        'text': text
                                    })
                        else:
                            # For content pages, look for resource and function links
                            for link in soup.find_all('a'):
                                href = link.get('href', '')
                                text = link.get_text().strip()
                                
                                # Normalize URL
                                normalized_href = self._normalize_url(url, href)
                                if normalized_href:
                                    links.append({
                                        'href': normalized_href,
                                        'text': text
                                    })
                        
                        print(f"Found {len(links)} {'module' if is_index else 'resource'} links")
                        
                        # Get article content
                        article = soup.find('article') or soup.find('main')
                        if article:
                            # Clean up content
                            for el in article.select('.headerlink, .highlight-default'):
                                el.decompose()
                            
                            # Extract content
                            content = article.get_text(strip=True)
                            
                            # Create data structure
                            data = {
                                'content': content,
                                'links': links
                            }
                            
                            # Get resource name
                            resource_name = self._get_resource_name(url)
                            print(f"Saving content for {resource_name}")
                            
                            # Save the content as markdown
                            if data.get('content'):
                                markdown_content = f"# {resource_name}\n\n"
                                markdown_content += f"URL: {url}\n\n"
                                markdown_content += data['content']
                                
                                # Save markdown file
                                self.save_markdown(source_key, resource_name, markdown_content)
                                
                                # Save JSON for LLM consumption
                                doc_structure = {
                                    "url": url,
                                    "resource": resource_name,
                                    "content": data['content'],
                                    "navigation": data.get('links', []),
                                    "timestamp": datetime.now().isoformat()
                                }
                                self.save_json(source_key, resource_name, doc_structure)
                                print(f"Saved content for {resource_name}")
                        
                        # Process navigation links for recursive crawling
                        for link in links:
                            href = link['href']
                            if href and not href.startswith('#'):
                                await self.process_page(source_key, crawler, href)
                    
                    except asyncio.TimeoutError:
                        print(f"Timeout gathering URLs from {url}")
                        if attempt == retries - 1:  # Last attempt
                            raise
                    except Exception as e:
                        print(f"Error processing page {url}: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        if attempt == retries - 1:  # Last attempt
                            raise
            
            except Exception as e:
                print(f"Error in process_page for {url}: {str(e)}")
                import traceback
                traceback.print_exc()
                if attempt == retries - 1:  # Last attempt
                    print("All retry attempts failed")
                    raise
                await asyncio.sleep(5)  # Wait before retrying
    
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
    
    async def crawl(self, source_key: str = "pulumi_aws"):  
        """Crawl the documentation."""
        browser_config = BrowserConfig(
            headless=True,
            ignore_https_errors=True
        )
        
        retries = 3  # Number of retries for browser initialization
        for attempt in range(retries):
            try:
                async with AsyncWebCrawler(
                    browser_config=browser_config,
                    max_concurrent_pages=1  # Limit concurrent pages to avoid overload
                ) as crawler:
                    # Configure longer timeout in the run config instead
                    config = self.sources[source_key]["index_config"]
                    config.timeout = 60000  # 60 seconds timeout
                    await self.process_page(source_key, crawler)
                break  # If successful, break the retry loop
            except Exception as e:
                print(f"Attempt {attempt + 1}/{retries} failed: {str(e)}")
                if attempt == retries - 1:  # Last attempt
                    print("All retry attempts failed")
                    raise
                await asyncio.sleep(5)  # Wait before retrying

if __name__ == "__main__":
    crawler = PulumiNativeCrawler("output")
    asyncio.run(crawler.crawl())