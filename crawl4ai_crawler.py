import asyncio
from typing import List, Set
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path

class Crawl4AICrawler:
    """Crawler for Crawl4AI documentation."""
    
    def __init__(self, output_dir: str):
        self.base_url = "https://crawl4ai.com/mkdocs/"
        self.output_dir = Path(output_dir)
        self.visited_urls: Set[str] = set()
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and belongs to Crawl4AI docs."""
        parsed = urlparse(url)
        return (
            parsed.netloc == "crawl4ai.com" and
            parsed.path.startswith("/mkdocs/") and
            not any(ext in parsed.path for ext in ['.png', '.jpg', '.css', '.js'])
        )
    
    async def extract_links(self, html: str, base_url: str) -> List[str]:
        """Extract all valid documentation links from a page."""
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        # Find all links in the navigation and main content
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            full_url = urljoin(base_url, href)
            
            if self.is_valid_url(full_url) and full_url not in self.visited_urls:
                links.append(full_url)
                
        return links
    
    async def process_page(self, url: str) -> None:
        """Process a single documentation page."""
        if url in self.visited_urls:
            return
            
        self.visited_urls.add(url)
        
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return
                    
                html = await response.text()
                
                # Extract content
                soup = BeautifulSoup(html, 'html.parser')
                main_content = soup.find('main') or soup.find('article')
                
                if main_content:
                    # Create output file path
                    parsed = urlparse(url)
                    rel_path = parsed.path.replace('/mkdocs/', '')
                    if not rel_path or rel_path.endswith('/'):
                        rel_path += 'index'
                    
                    output_file = self.output_dir / f"{rel_path}.md"
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Save content
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(main_content.get_text())
                
                # Extract and process links
                links = await self.extract_links(html, url)
                tasks = [self.process_page(link) for link in links]
                await asyncio.gather(*tasks)
                
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")
    
    async def crawl(self) -> None:
        """Main crawl method to process all documentation pages."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        await self.process_page(self.base_url)

# Example usage:
async def main():
    async with Crawl4AICrawler("output/crawl4ai") as crawler:
        await crawler.crawl()

if __name__ == "__main__":
    asyncio.run(main()) 