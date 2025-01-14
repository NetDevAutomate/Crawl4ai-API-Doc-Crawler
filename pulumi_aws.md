# Pulumi AWS Native Crawler Documentation

## Overview
The Pulumi AWS Native Crawler is designed to efficiently extract documentation from the Pulumi AWS Provider's documentation website. It uses Crawl4AI's native methods for web crawling and content extraction, providing a robust and maintainable solution for documentation gathering.

## Code Structure

### Main Components

1. **PulumiNativeCrawler Class**
   - Inherits from `BaseDocCrawler`
   - Manages the crawling process and content extraction
   - Handles URL normalization and resource naming
   - Implements file saving in both Markdown and JSON formats

2. **Configuration System**
   ```python
   self.sources = {
       "pulumi_aws": {
           "url": "https://www.pulumi.com/registry/packages/aws/api-docs",
           "output_dir": "pulumi_aws",
           "index_config": CrawlerRunConfig(...),
           "page_config": CrawlerRunConfig(...)
       }
   }
   ```
   - Separate configurations for index and content pages
   - Customized waiting conditions and selectors for different page types
   - Flexible output directory structure

### Key Features

1. **URL Handling**
   - Robust URL normalization with `_normalize_url` method
   - Handles both relative and absolute URLs
   - Filters out non-documentation URLs
   - Supports multiple documentation URL patterns

2. **Resource Naming**
   - Smart resource name extraction with `_get_resource_name`
   - Handles different URL patterns (api-docs and pkg/aws)
   - Creates clean, hierarchical file names

3. **Content Extraction**
   - Two-phase page loading for better reliability
   - Separate strategies for index and content pages
   - Clean content processing with BeautifulSoup
   - Preservation of document structure and links

4. **Error Handling**
   - Multiple retry attempts at different levels
   - Timeout handling for page loads
   - Detailed error logging
   - Graceful failure recovery

## Methodology

### 1. Initialization
```python
crawler = PulumiNativeCrawler("output")
```
- Sets up output directory
- Initializes configuration
- Prepares browser settings

### 2. Crawling Process
1. **Browser Setup**
   - Headless browser configuration
   - Error handling for HTTPS
   - Concurrent page limit for stability

2. **Page Processing**
   ```python
   async def process_page(self, source_key: str, crawler, url: str = None):
   ```
   - Detects page type (index or content)
   - Loads page content in two phases
   - Extracts links and content
   - Saves processed content

3. **Content Extraction**
   - Uses CSS selectors for reliable content targeting
   - Cleans up unwanted elements
   - Extracts both text content and navigation links

4. **File Storage**
   - Markdown files for human readability
   - JSON files for LLM consumption
   - Hierarchical organization based on URL structure

### 3. Link Processing
1. **Link Discovery**
   - Finds all relevant links in the page
   - Normalizes URLs
   - Filters out non-documentation links

2. **Recursive Crawling**
   - Follows normalized links
   - Maintains visited URL set
   - Prevents duplicate processing

## Best Practices Implemented

1. **Reliability**
   - Retry mechanisms at multiple levels
   - Proper error handling and logging
   - URL deduplication

2. **Performance**
   - Limited concurrent pages
   - Efficient URL normalization
   - Smart content caching

3. **Maintainability**
   - Clear code structure
   - Comprehensive documentation
   - Modular design

4. **Extensibility**
   - Easy configuration updates
   - Flexible URL pattern matching
   - Customizable content processing

## Output Format

### Markdown Files
```markdown
# resource_name

URL: https://www.pulumi.com/...

[Content from the documentation page]
```

### JSON Files
```json
{
    "url": "https://www.pulumi.com/...",
    "resource": "resource_name",
    "content": "...",
    "navigation": [...],
    "timestamp": "..."
}
```

## Usage

1. **Basic Usage**
   ```python
   crawler = PulumiNativeCrawler("output")
   asyncio.run(crawler.crawl())
   ```

2. **Custom Configuration**
   ```python
   config = SDKConfig(
       base_url="https://www.pulumi.com/registry/packages/aws/api-docs",
       provider="aws",
       sdk_version="latest"
   )
   crawler = PulumiNativeCrawler("output", config)
   ```

## Adapting for Other API Documentation

### Step-by-Step Guide

1. **Analyze the Target Documentation**
   ```python
   # Key aspects to identify:
   - Base URL pattern (e.g., "https://docs.example.com/api")
   - URL structure for different content types
   - Navigation patterns (index pages vs. content pages)
   - HTML structure and CSS selectors for content
   ```

2. **Configure Source Settings**
   ```python
   self.sources = {
       "your_api": {
           "url": "https://docs.example.com/api",
           "output_dir": "your_api_docs",
           "index_config": CrawlerRunConfig(
               # Customize these based on the documentation structure:
               wait_for="css:main",  # CSS selector for main content
               wait_until="networkidle",  # Page load condition
               css_selector="main"  # Content selector
           ),
           "page_config": CrawlerRunConfig(
               # Different settings for content pages if needed
               wait_for="css:article",
               wait_until="networkidle",
               css_selector="article"
           )
       }
   }
   ```

3. **Customize URL Handling**
   ```python
   def _normalize_url(self, base_url: str, href: str) -> Optional[str]:
       """
       Adapt these patterns for your API docs:
       1. Valid URL patterns to include
       2. URL normalization rules
       3. Fragment and query parameter handling
       """
       if not href or href.startswith(('#', 'javascript:', 'mailto:')):
           return None
           
       # Convert relative URL to absolute
       if not href.startswith('http'):
           href = urljoin(base_url, href)
       
       # Add your URL validation patterns
       if not any(pattern in href for pattern in [
           '/your/docs/pattern',
           '/alternate/pattern'
       ]):
           return None
           
       return href
   ```

4. **Adjust Resource Naming**
   ```python
   def _get_resource_name(self, url: str) -> str:
       """
       Customize based on your URL structure:
       1. Identify key URL segments
       2. Handle special cases
       3. Create consistent naming scheme
       """
       parts = url.rstrip('/').split('/')
       
       # Example pattern matching
       if 'api-docs' in parts:
           idx = parts.index('api-docs')
           resource_parts = parts[idx + 1:]
           if not resource_parts:
               return 'index'
           return '_'.join(resource_parts)
       
       return 'index'
   ```

5. **Modify Content Extraction**
   ```python
   # In process_page method:
   
   # Identify page type
   if url.endswith('/api') or url.endswith('/docs/'):
       is_index = True
   else:
       is_index = False
   
   # Extract links based on documentation structure
   links = []
   if is_index:
       # Find navigation elements specific to your docs
       for link in soup.select('your-navigation-selector'):
           href = link.get('href', '')
           text = link.get_text().strip()
           # Process links
   else:
       # Handle content page links differently if needed
       for link in soup.select('your-content-links-selector'):
           # Process content links
   ```

### Common Documentation Patterns

1. **Single Page Applications (SPAs)**
   ```python
   # Handle dynamic content loading
   pre_config = CrawlerRunConfig(
       wait_for="css:body",
       wait_until="domcontentloaded",
       process_iframes=True
   )
   
   # Wait for dynamic content
   await asyncio.sleep(2)
   ```

2. **Traditional Multi-page Docs**
   ```python
   # Simpler configuration might work
   config = CrawlerRunConfig(
       wait_until="networkidle",
       css_selector="main"
   )
   ```

3. **API Reference Docs**
   ```python
   # Common selectors to look for
   selectors = {
       'method': '.api-method',
       'endpoint': '.endpoint-url',
       'parameters': '.params-table',
       'response': '.response-section'
   }
   ```

### Content Processing Strategies

1. **Clean HTML Content**
   ```python
   def clean_content(self, article):
       # Remove common unwanted elements
       for selector in ['.headerlink', '.highlight-default', '.edit-page']:
           for el in article.select(selector):
               el.decompose()
       
       # Handle code blocks
       for code in article.select('pre code'):
           # Preserve formatting
           code.string = f"\n{code.get_text()}\n"
       
       return article
   ```

2. **Structure Extraction**
   ```python
   def extract_structure(self, soup):
       data = {
           'title': soup.find('h1').get_text(),
           'description': soup.find('p').get_text(),
           'sections': []
       }
       
       for section in soup.find_all('section'):
           data['sections'].append({
               'heading': section.find('h2').get_text(),
               'content': section.get_text()
           })
       
       return data
   ```

### Common Challenges and Solutions

1. **Dynamic Content**
   ```python
   # Solution: Multi-phase loading
   async def load_dynamic_content(self, crawler, url):
       # Phase 1: Initial page load
       pre_result = await crawler.arun(url=url, config=pre_config)
       
       # Phase 2: Wait for dynamic content
       await asyncio.sleep(2)
       
       # Phase 3: Extract content
       result = await crawler.arun(url=url, config=main_config)
   ```

2. **Rate Limiting**
   ```python
   # Add delay between requests
   async def process_page(self, source_key: str, crawler, url: str = None):
       await asyncio.sleep(1)  # Respect rate limits
       # Process page
   ```

3. **Error Recovery**
   ```python
   # Implement checkpointing
   def save_checkpoint(self, url):
       with open('crawler_checkpoint.json', 'w') as f:
           json.dump({
               'last_url': url,
               'visited': list(self._visited_urls)
           }, f)
   ```

### Testing Your Adaptation

1. **Start Small**
   ```python
   # Test with a subset of pages
   async def test_crawl(self):
       urls = [
           'docs/index',
           'docs/getting-started',
           'docs/api/endpoint'
       ]
       for url in urls:
           await self.process_page(self.source_key, self.crawler, url)
   ```

2. **Validate Output**
   ```python
   def validate_content(self, content):
       required_fields = ['title', 'content', 'navigation']
       for field in required_fields:
           if not content.get(field):
               print(f"Missing required field: {field}")
               return False
       return True
   ```

3. **Monitor Performance**
   ```python
   async def process_page(self, source_key: str, crawler, url: str = None):
       start_time = time.time()
       # Process page
       end_time = time.time()
       print(f"Processed {url} in {end_time - start_time:.2f} seconds")
   ```

Remember to:
- Start with a small subset of pages for testing
- Monitor memory usage and performance
- Implement proper error handling
- Respect the target site's robots.txt and rate limits
- Document your customizations for future maintenance

These patterns and examples should help you adapt the crawler for various API documentation sites while maintaining code quality and reliability.

## Future Improvements

1. **Performance Optimization**
   - Implement rate limiting
   - Add caching mechanisms
   - Optimize concurrent processing

2. **Content Processing**
   - Enhanced content cleaning
   - Better handling of code blocks
   - Improved metadata extraction

3. **Error Recovery**
   - Checkpoint system
   - Resume capability
   - Better error reporting

4. **Documentation Quality**
   - Content validation
   - Link verification
   - Schema validation
