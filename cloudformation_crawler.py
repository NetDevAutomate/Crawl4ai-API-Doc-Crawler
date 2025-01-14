"""CloudFormation documentation crawler using native Crawl4AI methods."""

import os
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from urllib.parse import urljoin, urlparse
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from base import BaseDocCrawler, SDKConfig
from bs4 import BeautifulSoup
import traceback

class CloudFormationNativeCrawler(BaseDocCrawler):
    """Crawler for AWS CloudFormation documentation using native Crawl4AI methods."""
    
    def __init__(self, output_dir: str, config: Optional[SDKConfig] = None):
        if config is None:
            config = SDKConfig(
                base_url="https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-template-resource-type-ref.html",
                provider="aws",
                sdk_version="latest"
            )
        super().__init__(output_dir, config)
        self._visited_urls = set()
        
        # Define sources with extraction strategies
        self.sources = {
            "cloudformation": {
                "url": "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-template-resource-type-ref.html",
                "output_dir": "cloudformation",
                "index_config": CrawlerRunConfig(
                    wait_for="css:div.awsdocs-content",  # Wait for AWS docs content
                    wait_until="networkidle",
                    process_iframes=True,
                    only_text=False,
                    css_selector="div.awsdocs-content"  # Get AWS docs content
                ),
                "page_config": CrawlerRunConfig(
                    wait_for="css:div.awsdocs-content",  # Wait for AWS docs content
                    wait_until="networkidle",
                    process_iframes=True,
                    only_text=False,
                    css_selector="div.awsdocs-content"  # Get AWS docs content
                )
            }
        }
    
    def _normalize_url(self, base_url: str, href: str) -> Optional[str]:
        """Normalize URL and check if it should be crawled."""
        try:
            # Handle AWS documentation URLs
            if href.startswith('/'):
                # Convert relative URL to absolute
                base_parts = urlparse(base_url)
                return f"{base_parts.scheme}://{base_parts.netloc}{href}"
            elif href.startswith('http'):
                # Already absolute URL
                return href
            else:
                # Relative URL
                return urljoin(base_url, href)
        except Exception as e:
            print(f"Error normalizing URL {href}: {str(e)}")
            return None
    
    def _get_resource_name(self, url: str) -> str:
        """Extract resource name from URL."""
        parts = url.rstrip('/').split('/')
        
        # Get the last part of the URL and remove .html
        resource_name = parts[-1].replace('.html', '')
        
        # Handle different URL patterns
        if 'aws-resource' in parts:
            # For resource types like AWS::S3::Bucket
            return resource_name.replace('-', '_')
        elif 'aws-properties' in parts:
            # For property types
            return f"properties_{resource_name.replace('-', '_')}"
        
        return 'index'
    
    def _clean_content(self, article):
        """Clean up the HTML content."""
        # Remove navigation elements
        for selector in ['.awsdocs-navigation', '.awsdocs-breadcrumbs', '.awsdocs-page-header']:
            for el in article.select(selector):
                el.decompose()
        
        # Clean up code blocks
        for code in article.select('pre code'):
            code.string = f"\n{code.get_text()}\n"
        
        # Remove internal links and buttons
        for el in article.select('.awsdocs-thumbs-feedback'):
            el.decompose()
        
        return article
    
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
                if url.endswith('aws-template-resource-type-ref.html'):
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
                        
                        # Debug: Print HTML structure
                        print("\nDEBUG: HTML Structure")
                        print("=" * 80)
                        
                        # Print all div classes
                        print("\nAll div classes found:")
                        for div in soup.find_all('div', class_=True):
                            print(f"Found div with class: {' '.join(div['class'])}")
                        
                        # Print all links
                        print("\nAll links found:")
                        for link in soup.find_all('a', href=True):
                            href = link.get('href', '')
                            text = link.get_text().strip()
                            if '/AWS_' in href and text:
                                print(f"Link: {href} -> {text}")
                        
                        # Try to find content with broader selectors
                        content_selectors = [
                            'div.awsdocs-content',
                            'div#main-content',
                            'div[role="main"]',
                            'div.awsui-context-content-header',
                            'main',
                            'article',
                            'div.table-contents'
                        ]
                        
                        article = None
                        for selector in content_selectors:
                            print(f"\nTrying selector: {selector}")
                            article = soup.select_one(selector)
                            if article:
                                print(f"Found content with selector: {selector}")
                                print(f"Content length: {len(article.get_text())}")
                                break
                        
                        if not article:
                            print("\nWARNING: No content found with standard selectors")
                            # Try finding any div with substantial content
                            for div in soup.find_all('div'):
                                text = div.get_text().strip()
                                if len(text) > 1000:  # Look for divs with significant content
                                    print(f"Found large div with classes: {div.get('class', [])}")
                                    article = div
                                    break
                        
                        if article:
                            # Clean up content
                            article = self._clean_content(article)
                            
                            # Extract content
                            content = article.get_text(strip=True)
                            
                            # Extract all AWS service links
                            links = []
                            for link in article.find_all('a', href=True):
                                href = link.get('href', '')
                                text = link.get_text().strip()
                                
                                if '/AWS_' in href and text and not href.startswith('#'):
                                    normalized_href = self._normalize_url(url, href)
                                    if normalized_href:
                                        links.append({
                                            'href': normalized_href,
                                            'text': text
                                        })
                            
                            print(f"\nFound {len(links)} AWS service links")
                            
                            # Create data structure
                            data = {
                                'content': content,
                                'links': links
                            }
                            
                            # Get resource name from URL
                            if '/AWS_' in url:
                                resource_name = url.split('/AWS_')[-1].split('.')[0]
                            else:
                                resource_name = 'index'
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
                        if attempt == retries - 1:  # Last attempt
                            raise
            
            except Exception as e:
                print(f"Error in process_page for {url}: {str(e)}")
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
    
    async def crawl(self):
        """Crawl the documentation."""
        try:
            print("\nDEBUG: Starting crawl")
            print(f"Sources: {self.sources}")
            
            for source_name, source in self.sources.items():
                print(f"\nDEBUG: Processing source {source_name}")
                print(f"URL: {source['url']}")
                print(f"Output dir: {source['output_dir']}")
                
                # Create output directory
                output_dir = os.path.join(self.output_dir, source["output_dir"])
                os.makedirs(output_dir, exist_ok=True)
                print(f"Created output directory: {output_dir}")
                
                # Create the crawler
                browser_config = BrowserConfig(
                    headless=True,
                    ignore_https_errors=True
                )
                
                async with AsyncWebCrawler(
                    browser_config=browser_config,
                    max_concurrent_pages=1  # Limit concurrent pages to avoid overload
                ) as crawler:
                    # Process the index page first
                    print("\nDEBUG: Processing index page")
                    await self.process_page(source_name, crawler, source["url"])
                    
                    # Get the list of service pages to crawl
                    service_pages = []
                    index_file = os.path.join(output_dir, "index.json")
                    if os.path.exists(index_file):
                        with open(index_file, 'r') as f:
                            index_data = json.load(f)
                            for link in index_data.get('navigation', []):
                                if '/AWS_' in link['href']:
                                    service_pages.append(link['href'])
                    
                    print(f"\nFound {len(service_pages)} service pages to crawl")
                    
                    # Process each service page
                    for i, page_url in enumerate(service_pages, 1):
                        print(f"\nProcessing service page {i}/{len(service_pages)}: {page_url}")
                        try:
                            await self.process_page(source_name, crawler, page_url)
                        except Exception as e:
                            print(f"Error processing {page_url}: {str(e)}")
                            continue
                    
                    print("\nFinished crawling all pages")
            
        except Exception as e:
            print(f"Error in crawl: {str(e)}")
            traceback.print_exc()
    
if __name__ == "__main__":
    crawler = CloudFormationNativeCrawler("output")
    asyncio.run(crawler.crawl())
