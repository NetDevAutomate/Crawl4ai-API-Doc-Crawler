from datetime import datetime
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

DEBUG = False

class Boto3DocCrawler:
    def __init__(self):
        self.base_output_dir = "output"
        
        # Track visited URLs to prevent infinite loops
        self._visited_urls = set()
        
        # Define sources with extraction strategies
        self.sources = {
            "boto3": {
                "url": "https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/index.html",
                "output_dir": "boto3",
                "index_config": CrawlerRunConfig(
                    wait_for="css:.toctree-wrapper",  # Wait for toctree to load
                    wait_until="networkidle",  # Wait for network requests to finish
                    process_iframes=True,  # Handle any iframe content
                    only_text=False,  # Keep HTML structure for markdown conversion
                    css_selector=".toctree-wrapper",  # Get toctree content
                ),
                "page_config": CrawlerRunConfig(
                    wait_for="css:article",  # Wait for article content to load
                    wait_until="networkidle",  # Wait for network requests to finish
                    process_iframes=True,  # Handle any iframe content
                    only_text=False,  # Keep HTML structure for markdown conversion
                    css_selector="article",  # Get article content
                )
            }
        }
    
    def save_markdown(self, source_key: str, service_name: str, content: str):
        """Save content as markdown file."""
        import os
        output_dir = os.path.join(self.base_output_dir, self.sources[source_key]["output_dir"])
        os.makedirs(output_dir, exist_ok=True)
        
        filename = os.path.join(output_dir, f"{service_name}.md")
        print(f"Saving markdown to {filename}")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Saved markdown to {filename}")
    
    def save_json(self, source_key: str, service_name: str, data: dict):
        """Save structured data as JSON."""
        import os
        import json
        output_dir = os.path.join(self.base_output_dir, self.sources[source_key]["output_dir"])
        os.makedirs(output_dir, exist_ok=True)
        
        filename = os.path.join(output_dir, f"{service_name}.json")
        print(f"Saving JSON to {filename}")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Saved JSON to {filename}")
    
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
        
        try:
            # Determine page type and config
            if '/services/index.html' in url:
                config = source.get("index_config")
                is_index = True
            else:
                config = source.get("page_config")
                is_index = False
            
            print(f"Crawling {url} {'(index page)' if is_index else '(content page)'}")
            
            if config:
                try:
                    # First, load the page and wait for content
                    result = await asyncio.wait_for(
                        crawler.arun(url=url, config=config),
                        timeout=30  # 30 seconds timeout for dynamic content
                    )
                    
                    if not result or not result.success:
                        print(f"Failed to load page {url}")
                        return
                    
                    print(f"Result success: {result.success}")
                    print(f"Result status code: {result.status_code}")
                    print(f"Result error message: {result.error_message}")
                    print(f"Result HTML length: {len(result.html) if result.html else 0}")
                    print(f"Result cleaned HTML length: {len(result.cleaned_html) if result.cleaned_html else 0}")
                    
                    # Parse the HTML
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(result.html, 'html.parser')
                    
                    # Extract links based on page type
                    links = []
                    if is_index:
                        # For index pages, look for service links
                        for link in soup.find_all('a', class_='reference internal'):
                            href = link.get('href', '')
                            text = link.get_text().strip()
                            
                            # Skip navigation and index links
                            if (href and not href.startswith(('http', '#', '../../guide/', 'index.html')) and 
                                text and not text.lower() in ['index', 'search', 'next', 'previous']):
                                
                                # Convert relative URL to absolute
                                if not href.startswith('http'):
                                    href = urljoin(url, href)
                                
                                links.append({
                                    'href': href,
                                    'text': text
                                })
                    else:
                        # For content pages, look for method links
                        for link in soup.select('a.reference.internal'):
                            href = link.get('href', '')
                            text = link.get_text().strip()
                            
                            if href and not href.startswith('#'):
                                # Convert relative URL to absolute
                                if not href.startswith('http'):
                                    href = urljoin(url, href)
                                
                                if '/documentation/api/' in href:
                                    links.append({
                                        'href': href,
                                        'text': text
                                    })
                    
                    print(f"Found {len(links)} {'service' if is_index else 'method'} links")
                    
                    # Get article content
                    article = soup.find('article')
                    if article:
                        # Clean up content
                        for el in article.select('.headerlink, .sphinx-tabs-tab, .sphinx-tabs-panel'):
                            el.decompose()
                        
                        # Extract content
                        content = article.get_text(strip=True)
                        
                        # Create data structure
                        data = {
                            'content': content,
                            'links': links
                        }
                        
                        # Extract service name from URL
                        parts = url.rstrip('/').split('/')
                        if 'client' in parts:
                            # This is a method page
                            service_name = parts[parts.index('services') + 1]
                            method_name = parts[-1].replace('.html', '')
                            file_name = f"{service_name}_{method_name}"
                        else:
                            # This is a service page
                            service_name = parts[-1].replace('.html', '')
                            if not service_name or service_name == 'index':
                                service_name = parts[-2]
                            file_name = service_name
                        
                        print(f"Saving content for {file_name}")
                        
                        # Save the content as markdown
                        if data.get('content'):
                            markdown_content = f"# {file_name}\n\n"
                            markdown_content += f"URL: {url}\n\n"
                            markdown_content += data['content']
                            
                            # Save markdown file
                            self.save_markdown(source_key, file_name, markdown_content)
                            
                            # Save JSON for LLM consumption
                            doc_structure = {
                                "url": url,
                                "service": service_name,
                                "content": data['content'],
                                "navigation": data.get('links', []),
                                "timestamp": datetime.now().isoformat()
                            }
                            self.save_json(source_key, file_name, doc_structure)
                            print(f"Saved content for {file_name}")
                    
                    # Process navigation links for recursive crawling
                    for link in links:
                        href = link['href']
                        if href and not href.startswith('#'):
                            # Remove any anchor fragments
                            href = href.split('#')[0]
                            
                            # Only crawl URLs from the same domain and path
                            parsed_url = urlparse(href)
                            parsed_base = urlparse(url)
                            if (parsed_url.netloc == parsed_base.netloc and
                                '/documentation/api/' in parsed_url.path):
                                print(f"Found valid link to gather: {href}")
                                await self.process_page(source_key, crawler, href)
                
                except asyncio.TimeoutError:
                    print(f"Timeout gathering URLs from {url}")
                except Exception as e:
                    print(f"Error processing page {url}: {str(e)}")
                    import traceback
                    traceback.print_exc()
            
        except Exception as e:
            print(f"Error in process_page for {url}: {str(e)}")
            import traceback
            traceback.print_exc()

    async def _gather_urls(self, source_key: str, crawler, urls_to_crawl: set, url: str = None):
        """Recursively gather all URLs to crawl."""
        source = self.sources[source_key]
        if url is None:
            url = source["url"]
        
        # Skip if already gathered
        if url in urls_to_crawl:
            print(f"Already gathered {url}, skipping")
            return
        
        # Add URL to set
        urls_to_crawl.add(url)
        print(f"Added {url} to URLs to crawl")
        
        try:
            config = source.get("config")
            print(f"Gathering links from {url}")
            
            if config:
                # Add timeout to arun
                result = await asyncio.wait_for(
                    crawler.arun(url=url, config=config),
                    timeout=30  # 30 seconds timeout
                )
                
                if not result:
                    print(f"No result from {url}")
                    return
                
                print(f"Result success: {result.success}")
                print(f"Result status code: {result.status_code}")
                print(f"Result error message: {result.error_message}")
                
                # Process all internal links
                if result.links and 'internal' in result.links:
                    print(f"Found {len(result.links['internal'])} internal links")
                    for link in result.links['internal']:
                        href = link['href']
                        if href and not href.startswith('#'):
                            # Remove any anchor fragments
                            href = href.split('#')[0]
                            
                            # Only gather URLs from the same domain and path
                            parsed_url = urlparse(href)
                            parsed_base = urlparse(url)
                            if (parsed_url.netloc == parsed_base.netloc and
                                '/documentation/api/' in parsed_url.path):
                                print(f"Found valid link to gather: {href}")
                                # Recursively gather URLs
                                await self._gather_urls(source_key, crawler, urls_to_crawl, href)
                else:
                    print(f"No internal links found in {url}")
        
        except asyncio.TimeoutError:
            print(f"Timeout gathering URLs from {url}")
        except Exception as e:
            print(f"Error gathering URLs from {url}: {str(e)}")
            import traceback
            traceback.print_exc()

    async def crawl(self, source_key: str):
        """Crawl documentation for a specific source."""
        if source_key not in self.sources:
            print(f"Source {source_key} not found")
            return
        
        print(f"Starting crawler for sources: {source_key}")
        
        # Create a browser config
        browser_config = BrowserConfig(
            headless=True,  # Run in headless mode
            ignore_https_errors=True  # Ignore HTTPS errors
        )
        
        # Create the crawler instance with concurrency settings
        async with AsyncWebCrawler(
            browser_config=browser_config,
            max_concurrent_pages=5  # Process up to 5 pages concurrently
        ) as crawler:
            try:
                # First gather all URLs to crawl
                urls_to_crawl = set()
                await self._gather_urls(source_key, crawler, urls_to_crawl)
                
                print(f"Found {len(urls_to_crawl)} unique URLs to crawl")
                for url in urls_to_crawl:
                    print(f"  - {url}")
                
                # Process URLs concurrently
                tasks = []
                for url in urls_to_crawl:
                    task = self.process_page(source_key, crawler, url)
                    tasks.append(task)
                
                # Use asyncio.gather to process pages concurrently
                await asyncio.gather(*tasks)
                
            except Exception as e:
                print(f"Error during crawl: {str(e)}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    import sys
    
    async def main():
        crawler = Boto3DocCrawler()
        await crawler.crawl("boto3")
    
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
