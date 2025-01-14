"""Single page crawler using Crawl4AI."""

import os
import json
import asyncio
import warnings
from typing import Optional, List, Any
from pathlib import Path
from slugify import slugify
from pydantic import BaseModel, ConfigDict
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig, CacheMode, JsonCssExtractionStrategy
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter

# Suppress Pydantic warning about fields
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

class Service(BaseModel):
    model_config = ConfigDict(extra='allow')
    name: str
    description: Optional[str] = None

class BlogPost(BaseModel):
    model_config = ConfigDict(extra='allow')
    title: str
    content: str
    author: Optional[str] = None
    date: Optional[str] = None
    topics: Optional[List[str]] = None
    services: Optional[List[Service]] = None

class CustomExtractionStrategy(JsonCssExtractionStrategy):
    def preprocess_html(self, html_content):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # First, try to find the main blog content container
        main_content = soup.find('div', {'id': 'aws-page-content'})
        if not main_content:
            main_content = soup.find('div', {'class': 'blog-post'})
        if not main_content:
            main_content = soup.find('article')
        
        if main_content:
            # Create a new soup with just the main content
            new_soup = BeautifulSoup('<html><body></body></html>', 'html.parser')
            new_soup.body.append(main_content)
            
            # Remove unwanted elements
            for element in new_soup.find_all(['script', 'style', 'noscript', 'iframe', 'nav', 'header', 'footer']):
                element.decompose()
            
            # Remove elements by class or id
            for element in new_soup.find_all(class_=lambda x: x and any(term in str(x).lower() for term in [
                'cookie', 'navigation', 'header', 'footer', 'sidebar', 'menu', 'banner',
                'popup', 'modal', 'overlay', 'social', 'share', 'comment'
            ])):
                element.decompose()
            
            # Remove empty elements
            for element in new_soup.find_all():
                if len(element.get_text(strip=True)) == 0:
                    element.decompose()
            
            return str(new_soup)
        return html_content

    async def extract(self, html_content, url=None):
        html_content = self.preprocess_html(html_content)
        return await super().extract(html_content, url)

async def crawl_page(url: str, output_dir: str = "crawled_content") -> None:
    """Crawl a single page and save its content."""
    
    md_generator = DefaultMarkdownGenerator(
        content_filter=lambda e: (
            # Keep main content elements
            e.tag not in ['nav', 'header', 'footer', 'script', 'style', 'iframe'] and
            not any(c in (e.get('class', '') or '') for c in [
                'navigation', 'menu', 'sidebar', 'cookie', 'share', 'social',
                'comments', 'table-of-contents'
            ])
        )
    )

    # Configure the crawler
    crawl_config = CrawlerRunConfig(
        extraction_strategy=JsonCssExtractionStrategy(
            schema={
                "fields": [
                    {
                        "name": "title",
                        "selector": "h1",
                        "type": "text"
                    },
                    {
                        "name": "content",
                        "selector": "article, div.blog-post, div.blog-content, div.post-content",
                        "type": "markdown"
                    }
                ]
            }
        ),
        markdown_generator=md_generator,
        wait_until="networkidle",
        cache_mode=CacheMode.BYPASS
    )

    try:
        # Create the crawler instance with basic browser config
        browser_config = BrowserConfig(
            headless=True
        )
        
        # Configure the crawler with content extraction
        crawl_config = CrawlerRunConfig(
            extraction_strategy=CustomExtractionStrategy(
                schema={
                    "fields": [
                        {
                            "name": "title",
                            "selector": "h1",
                            "type": "text"
                        },
                        {
                            "name": "content",
                            "selector": "article, div.blog-post, div.blog-content, div.post-content",
                            "type": "markdown"
                        }
                    ]
                }
            ),
            markdown_generator=md_generator,
            wait_until="networkidle",
            cache_mode=CacheMode.BYPASS,
            wait_for="article, div.blog-post, div.blog-content, div.post-content"
        )
        
        crawler = AsyncWebCrawler(config=browser_config)
        
        # Crawl the page with the crawl config
        result = await crawler.arun(url=url, config=crawl_config)
        print(f"\nCrawl Result:")
        print(f"Success: {result.success}")
        if hasattr(result, 'html'):
            print(f"HTML Length: {len(result.html)}")
        if hasattr(result, 'cleaned_html'):
            print(f"Cleaned HTML Length: {len(result.cleaned_html)}")
        
        # Save the markdown content
        if result.success and hasattr(result, 'markdown') and result.markdown:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Get filename from URL
            filename = url.rstrip('/').split('/')[-1]
            output_file = os.path.join(output_dir, f"{filename}.md")
            
            # Save markdown content
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result.markdown)
            print(f"Saved markdown to {output_file}")
        
        return result
    except Exception as e:
        print(f"Error crawling page: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Crawl a single page and save its content.')
    parser.add_argument('-u', '--url', required=True, help='URL to crawl')
    parser.add_argument('-o', '--output', default='crawled_content', help='Output directory')
    args = parser.parse_args()
    
    asyncio.run(crawl_page(args.url, args.output))

if __name__ == "__main__":
    import argparse
    main()
