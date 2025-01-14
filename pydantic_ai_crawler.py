from datetime import datetime
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

DEBUG = False

class PydanticAIDocCrawler:
    def __init__(self):
        self.base_output_dir = "output"
        
        # Track visited URLs to prevent infinite loops
        self._visited_urls = set()
        
        # Define sources with extraction strategies
        self.sources = {
            "pydantic_ai": {
                "url": "https://ai.pydantic.dev/",
                "output_dir": "pydantic_ai",
                "index_config": CrawlerRunConfig(
                    wait_for="css:main",  # Wait for main content container
                    wait_until="load",    # Wait until load event fires
                    process_iframes=False, # No iframes needed
                    only_text=False,
                    css_selector="main",  # Get main content
                ),
                "page_config": CrawlerRunConfig(
                    wait_for="css:main",  # Wait for main content
                    wait_until="load",    # Wait until load event fires
                    process_iframes=False,
                    only_text=False,
                    css_selector="main",  # Get main content
                )
            }
        }
    
    def save_markdown(self, source_key: str, page_name: str, content: str):
        """Save content as markdown file."""
        import os
        output_dir = os.path.join(self.base_output_dir, self.sources[source_key]["output_dir"])
        os.makedirs(output_dir, exist_ok=True)
        
        # Clean filename
        page_name = page_name.replace('/', '_').replace('\\', '_')
        filename = os.path.join(output_dir, f"{page_name}.md")
        print(f"Saving markdown to {filename}")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Saved markdown to {filename}")
    
    def save_json(self, source_key: str, page_name: str, data: dict):
        """Save structured data as JSON."""
        import os
        import json
        output_dir = os.path.join(self.base_output_dir, self.sources[source_key]["output_dir"])
        os.makedirs(output_dir, exist_ok=True)
        
        # Clean filename
        page_name = page_name.replace('/', '_').replace('\\', '_')
        filename = os.path.join(output_dir, f"{page_name}.json")
        print(f"Saving JSON to {filename}")
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Saved JSON to {filename}")
    
    async def process_page(self, source_key: str, crawler, url: str = None):
        """Process a single page using Crawl4ai's native extraction."""
        source = self.sources[source_key]
        if url is None:
            url = source["url"]
        
        # Remove anchor from URL for visited check
        base_url = url.split('#')[0]
        
        # Skip if already visited
        if base_url in self._visited_urls:
            print(f"Already visited {base_url}, skipping")
            return
        
        # Mark as visited
        self._visited_urls.add(base_url)
        
        try:
            # Determine if this is the index page
            is_index = base_url.rstrip('/') == source["url"].rstrip('/')
            config = source["index_config"] if is_index else source["page_config"]
            
            print(f"Crawling {base_url} {'(index page)' if is_index else '(content page)'}")
            
            try:
                # Load the page and wait for content
                result = await asyncio.wait_for(
                    crawler.arun(url=base_url, config=config),  # Use base_url without anchor
                    timeout=60
                )
                
                if not result or not result.success:
                    print(f"Failed to load page {base_url}")
                    return
                
                print(f"Result success: {result.success}")
                print(f"Result status code: {result.status_code}")
                
                # Extract links using crawl4ai's native link extraction
                links = []
                if result.links and 'internal' in result.links:
                    for link in result.links['internal']:
                        href = link.get('href', '')
                        text = link.get('text', '').strip()
                        
                        # Skip anchor-only links and process only unique page paths
                        if (href and 'ai.pydantic.dev' in href and 
                            text and not text.lower() in ['next', 'previous']):
                            # Remove anchor and normalize URL
                            clean_href = href.split('#')[0].rstrip('/')
                            if clean_href and clean_href not in self._visited_urls:
                                links.append({
                                    'href': clean_href,
                                    'text': text
                                })
                
                print(f"Found {len(links)} new internal links")
                
                # Get content using crawl4ai's content extraction
                if result.html:
                    # Use BeautifulSoup to parse and clean the HTML
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(result.html, 'html.parser')
                    
                    # Remove unwanted elements
                    for element in soup.select('nav, footer, header, script, style'):
                        element.decompose()
                    
                    # Get the main content
                    main_content = soup.select_one(config.css_selector)
                    if main_content:
                        # Create data structure
                        data = {
                            'content': main_content.get_text(strip=True, separator='\n'),
                            'links': links
                        }
                        
                        # Extract page name from URL
                        parsed_url = urlparse(base_url)
                        page_name = parsed_url.path.strip('/')
                        if not page_name:
                            page_name = 'index'
                        
                        print(f"Saving content for {page_name}")
                        
                        # Save as markdown
                        if data.get('content'):
                            markdown_content = f"# {page_name}\n\n"
                            markdown_content += f"URL: {base_url}\n\n"
                            markdown_content += data['content']
                            
                            self.save_markdown(source_key, page_name, markdown_content)
                            
                            # Save JSON for LLM consumption
                            doc_structure = {
                                "url": base_url,
                                "page": page_name,
                                "content": data['content'],
                                "navigation": data.get('links', []),
                                "timestamp": datetime.now().isoformat()
                            }
                            self.save_json(source_key, page_name, doc_structure)
                            print(f"Saved content for {page_name}")
                
                # Process navigation links recursively
                for link in links:
                    href = link['href']
                    if href:
                        await self.process_page(source_key, crawler, href)
                    
            except asyncio.TimeoutError:
                print(f"Timeout processing {base_url}")
            except Exception as e:
                print(f"Error processing page {base_url}: {str(e)}")
                import traceback
                traceback.print_exc()
                
        except Exception as e:
            print(f"Error in process_page for {base_url}: {str(e)}")
            import traceback
            traceback.print_exc()

    async def crawl(self, source_key: str):
        """Crawl documentation for a specific source."""
        if source_key not in self.sources:
            print(f"Source {source_key} not found")
            return
        
        print(f"Starting crawler for source: {source_key}")
        
        # Create browser config with minimal settings
        browser_config = BrowserConfig(
            headless=True,
            ignore_https_errors=True
        )
        
        # Create crawler instance with reduced concurrency
        async with AsyncWebCrawler(
            browser_config=browser_config,
            max_concurrent_pages=2  # Reduce concurrent pages to avoid overload
        ) as crawler:
            try:
                # Start with the main URL
                await self.process_page(source_key, crawler)
                
            except Exception as e:
                print(f"Error during crawl: {str(e)}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    import asyncio
    import sys
    
    async def main():
        crawler = PydanticAIDocCrawler()
        await crawler.crawl("pydantic_ai")
    
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main()) 