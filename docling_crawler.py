import os
import asyncio
from typing import Dict, Any
from datetime import datetime
from urllib.parse import urljoin

from crawl4ai import (
    AsyncWebCrawler, 
    BrowserConfig, 
    CrawlerRunConfig, 
    CacheMode,
    JsonCssExtractionStrategy
)

class DoclingCrawler:
    """Crawler for Docling documentation"""
    
    def __init__(self):
        self.base_output_dir = "output"
        self.sources = {
            "docling": {
                "url": "https://ds4sd.github.io/docling/",
                "output_dir": "docling",
                "selector": "article.md-content__inner",
                # Main navigation sections from the site
                "base_sections": [
                    "getting-started",
                    "concepts",
                    "reference",
                    "examples",
                    "integrations"
                ],
                "extraction_schema": {
                    "name": "DoclingPage",
                    "baseSelector": "article.md-content__inner",
                    "fields": [
                        {"name": "title", "selector": "h1", "type": "text"},
                        {"name": "content", "selector": "article.md-content__inner", "type": "html"},
                        {"name": "code_examples", "selector": "pre code", "type": "array"},
                        {"name": "api_sections", "selector": "h2, h3", "type": "array"}
                    ]
                }
            }
        }

    async def crawl(self, source: str):
        """Crawl documentation for a specific source"""
        if source not in self.sources:
            raise ValueError(f"Unknown source: {source}")

        source_config = self.sources[source]
        base_url = source_config["url"]
        
        # Configure browser
        browser_config = BrowserConfig(
            headless=True,
            viewport_height=1200,
            viewport_width=1600
        )

        # Configure crawler with improved navigation handling
        crawler_config = CrawlerRunConfig(
            css_selector=source_config["selector"],
            wait_for="css:nav.md-nav--primary",  # Wait for main navigation
            extraction_strategy=JsonCssExtractionStrategy(source_config["extraction_schema"]),
            cache_mode=CacheMode.BYPASS,
            word_count_threshold=10,
            excluded_tags=["footer", "header"],
            exclude_external_links=True,
            js_code="""
                // Expand all navigation sections
                document.querySelectorAll('.md-nav__toggle').forEach(toggle => toggle.click());
                
                // Wait for navigation to expand
                await new Promise(r => setTimeout(r, 1000));
                
                // Get all navigation links
                const links = document.querySelectorAll('.md-nav__link');
                const linkList = document.createElement('ul');
                linkList.className = 'crawl4ai-links';
                document.body.appendChild(linkList);
                
                links.forEach(link => {
                    const href = link.getAttribute('href');
                    if (href && !href.startsWith('http') && !href.includes('#')) {
                        const li = document.createElement('li');
                        const a = document.createElement('a');
                        a.href = new URL(href, window.location.href).href;
                        a.textContent = link.textContent.trim();
                        li.appendChild(a);
                        linkList.appendChild(li);
                    }
                });
            """,
            delay_before_return_html=1.5
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            # Start with base URL to discover structure
            visited = set()
            to_visit = set([base_url])

            while to_visit:
                url = to_visit.pop()
                if url in visited:
                    continue

                print(f"\nCrawling: {url}")
                result = await crawler.arun(url=url, config=crawler_config)
                visited.add(url)

                if not result.success:
                    print(f"Failed to crawl {url}: {result.error_message}")
                    continue

                print(f"Found links: {len(result.links.get('internal', []))}")

                # Extract page content
                page_content = result.markdown_v2.raw_markdown if result.markdown_v2 else result.markdown
                
                # Save markdown
                relative_path = url.replace(base_url, "").strip("/")
                if not relative_path:
                    relative_path = "index"
                
                output_path = os.path.join(
                    self.base_output_dir,
                    source_config["output_dir"],
                    f"{relative_path}.md"
                )
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(f"# {relative_path}\n\n")
                    f.write(f"URL: {url}\n\n")
                    f.write(page_content)

                # Save JSON
                json_path = os.path.join(
                    self.base_output_dir,
                    source_config["output_dir"],
                    "json",
                    f"{relative_path}.json"
                )
                os.makedirs(os.path.dirname(json_path), exist_ok=True)

                json_content = {
                    "metadata": {
                        "source": source,
                        "url": url,
                        "timestamp": datetime.now().isoformat(),
                        "format_version": "1.0"
                    },
                    "content": {
                        "markdown": page_content,
                        "extracted": result.extracted_content
                    }
                }
                
                with open(json_path, "w", encoding="utf-8") as f:
                    import json
                    json.dump(json_content, f, indent=2)

                # Add new links to visit
                if result.links:
                    for link in result.links.get("internal", []):
                        href = link.get('href', '')
                        # Skip empty links
                        if not href:
                            continue
                            
                        # Remove anchor fragments from URLs
                        base_href = href.split('#')[0]
                        
                        # Only follow links that:
                        # 1. Start with base URL
                        # 2. Haven't been visited
                        # 3. Aren't already in queue
                        # 4. Aren't just anchor links
                        if (base_href and 
                            base_href.startswith(base_url) and 
                            base_href not in visited and 
                            base_href not in to_visit and
                            base_href != href):
                            
                            to_visit.add(base_href)
                            print(f"Added to queue: {base_href}")

async def main():
    crawler = DoclingCrawler()
    await crawler.crawl("docling")

if __name__ == "__main__":
    asyncio.run(main()) 