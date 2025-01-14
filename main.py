#!/usr/bin/env python3

"""Main entry point for AWS documentation crawlers."""

import os
import sys
import json
import asyncio
import argparse
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

class DocCrawler:
    def __init__(self, output_dir: str = "output"):
        """Initialize the documentation crawler.
        
        Args:
            output_dir: Base directory for output files
        """
        self.base_output_dir = output_dir
        
        # Define available crawlers and their configurations
        self.sources = {
            "cloudformation": {
                "url": "https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-template-resource-type-ref.html",
                "output_dir": "cloudformation",
                "content_selectors": [
                    'div.awsdocs-content',
                    'div#main-content',
                    'div[role="main"]',
                    'div.awsui-context-content-header',
                    'main',
                    'article',
                    'div.table-contents'
                ],
                "link_pattern": "/AWS_"
            },
            "boto3": {
                "url": "https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/index.html",
                "output_dir": "boto3",
                "content_selectors": [
                    'div.section',
                    'div.body',
                    'div[role="main"]'
                ],
                "link_pattern": "services/"
            },
            "pulumi": {
                "url": "https://www.pulumi.com/registry/packages/aws/api-docs/",
                "output_dir": "pulumi",
                "content_selectors": [
                    'main',
                    'article',
                    'div.content'
                ],
                "link_pattern": "/api-docs/"
            },
            "terraform": {
                "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
                "output_dir": "terraform",
                "content_selectors": [
                    'div[role="main"]',
                    'article',
                    'div.content'
                ],
                "link_pattern": "/docs/providers/aws/"
            },
            "gosdk": {
                "url": "https://pkg.go.dev/github.com/aws/aws-sdk-go-v2",
                "output_dir": "gosdk",
                "content_selectors": [
                    'main',
                    'div.Documentation-content',
                    'article'
                ],
                "link_pattern": "/service/"
            },
            "cdkpython": {
                "url": "https://docs.aws.amazon.com/cdk/api/v2/python/modules.html",
                "output_dir": "cdkpython",
                "content_selectors": [
                    'div#main-content',
                    'main',
                    'article',
                    'div.content'
                ],
                "link_pattern": "aws_cdk."
            }
        }
        
        # Create output directories
        for source in self.sources.values():
            os.makedirs(os.path.join(self.base_output_dir, source["output_dir"]), exist_ok=True)

    def _normalize_url(self, base_url: str, href: str) -> Optional[str]:
        """Normalize URL and check if it should be crawled."""
        try:
            if href.startswith('/'):
                base_parts = urlparse(base_url)
                return f"{base_parts.scheme}://{base_parts.netloc}{href}"
            elif href.startswith('http'):
                return href
            else:
                return urljoin(base_url, href)
        except Exception as e:
            print(f"Error normalizing URL {href}: {str(e)}")
            return None

    def _clean_content(self, article: BeautifulSoup) -> BeautifulSoup:
        """Clean the content by removing unnecessary elements."""
        # Remove navigation elements
        for selector in ['nav', '.feedback-section', '.breadcrumbs']:
            for element in article.select(selector):
                element.decompose()
        return article

    async def process_page(self, source_name: str, crawler: AsyncWebCrawler, url: str) -> None:
        """Process a single documentation page."""
        try:
            print(f"\nProcessing page: {url}")
            
            # Get source configuration
            source = self.sources[source_name]
            output_dir = os.path.join(self.base_output_dir, source["output_dir"])
            
            # Run the crawler
            result = await crawler.arun(url)
            
            if not result.success:
                print(f"Failed to fetch {url}: {result.error_message}")
                return
                
            # Parse the HTML
            soup = BeautifulSoup(result.html, 'html.parser')
            
            # Try to find content with selectors
            article = None
            for selector in source["content_selectors"]:
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
                
                # Extract all service links
                links = []
                for link in article.find_all('a', href=True):
                    href = link.get('href', '')
                    text = link.get_text().strip()
                    
                    if source["link_pattern"] in href and text and not href.startswith('#'):
                        normalized_href = self._normalize_url(url, href)
                        if normalized_href:
                            links.append({
                                'href': normalized_href,
                                'text': text
                            })
                
                print(f"\nFound {len(links)} service links")
                
                # Generate filenames
                base_name = os.path.splitext(os.path.basename(url))[0] or "index"
                
                # Save as markdown
                markdown_file = os.path.join(output_dir, f"{base_name}.md")
                with open(markdown_file, "w") as f:
                    f.write(f"# {base_name}\n\n")
                    f.write(f"URL: {url}\n\n")
                    f.write(content)
                print(f"Saved markdown to {markdown_file}")
                
                # Save as JSON
                json_file = os.path.join(output_dir, f"{base_name}.json")
                with open(json_file, "w") as f:
                    json.dump({
                        "url": url,
                        "content": content,
                        "navigation": links,
                        "timestamp": datetime.now().isoformat()
                    }, f, indent=2)
                print(f"Saved JSON to {json_file}")
                
                # Return links for further crawling
                return links
            else:
                print("\nNo content found to save")
                return []
                
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")
            return []

    async def crawl(self, sources: List[str] = None, service: str = None):
        """Crawl the documentation."""
        try:
            print("\nStarting crawl")
            
            # Filter sources if specified
            if sources and 'all' not in sources:
                self.sources = {k: v for k, v in self.sources.items() if k in sources}
            
            print(f"Processing sources: {', '.join(self.sources.keys())}")
            
            for source_name, source in self.sources.items():
                print(f"\nProcessing source {source_name}")
                print(f"URL: {source['url']}")
                print(f"Output dir: {source['output_dir']}")
                
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
                    print("\nProcessing index page")
                    links = await self.process_page(source_name, crawler, source["url"])
                    
                    if links:
                        # Filter links by service if specified
                        if service:
                            links = [link for link in links if service.lower() in link['href'].lower() or service.lower() in link['text'].lower()]
                            print(f"\nFiltered to {len(links)} links for service: {service}")
                        
                        # Process each service page
                        for i, link in enumerate(links, 1):
                            print(f"\nProcessing service page {i}/{len(links)}: {link['href']}")
                            try:
                                await self.process_page(source_name, crawler, link['href'])
                            except Exception as e:
                                print(f"Error processing {link['href']}: {str(e)}")
                                continue
                    
                    print("\nFinished crawling all pages")
            
        except Exception as e:
            print(f"Error in crawl: {str(e)}")
            traceback.print_exc()

def main():
    """Main entry point for the crawler."""
    parser = argparse.ArgumentParser(description='Crawl AWS documentation from multiple sources.')
    
    # Sources group
    source_group = parser.add_argument_group('Documentation Sources')
    source_group.add_argument('--cloudformation', action='store_true', help='AWS CloudFormation')
    source_group.add_argument('--boto3', action='store_true', help='AWS SDK for Python (Boto3)')
    source_group.add_argument('--gosdk', action='store_true', help='AWS SDK for Go')
    source_group.add_argument('--terraform', action='store_true', help='Terraform AWS Provider')
    source_group.add_argument('--pulumi', action='store_true', help='Pulumi AWS Provider')
    source_group.add_argument('--cdkpython', action='store_true', help='AWS CDK for Python')
    source_group.add_argument('--all', action='store_true', help='All documentation sources')
    
    # Service selection
    parser.add_argument('--service', help='Single service to crawl (e.g., s3, ec2)')
    
    # Other options
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--output-dir', help='Custom output directory for documentation')
    
    args = parser.parse_args()
    
    # Initialize crawler with custom output directory if provided
    output_dir = args.output_dir if args.output_dir else "output"
    crawler = DocCrawler(output_dir)
    
    # Determine which sources to crawl
    sources = []
    if args.all:
        sources = ['all']
    else:
        if args.cloudformation:
            sources.append('cloudformation')
        if args.boto3:
            sources.append('boto3')
        if args.gosdk:
            sources.append('gosdk')
        if args.terraform:
            sources.append('terraform')
        if args.pulumi:
            sources.append('pulumi')
        if args.cdkpython:
            sources.append('cdkpython')
        
        if not sources:
            parser.error("Please specify at least one documentation source or use --all")
    
    print(f"Starting crawler for sources: {', '.join(sources)}")
    asyncio.run(crawler.crawl(sources, args.service))

if __name__ == "__main__":
    main()
