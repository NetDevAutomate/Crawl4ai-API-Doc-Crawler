# CloudFormation Native Crawler Documentation

## Overview
The CloudFormation Native Crawler is designed to extract AWS CloudFormation resource type documentation using Crawl4AI's native methods. It crawls the AWS CloudFormation documentation, extracts resource type information, and saves it in both markdown and JSON formats.

## Architecture

### Main Components
1. **AsyncWebCrawler**: Uses Crawl4AI's native crawler for efficient web page processing
2. **BeautifulSoup**: Parses HTML content and extracts relevant information
3. **Output Formats**: Saves data in both markdown (human-readable) and JSON (machine-readable) formats

### Configuration
- **Browser Config**: Headless mode with HTTPS error handling
- **Crawler Config**: Configured for AWS documentation structure with specific selectors
- **Rate Limiting**: Single concurrent page to avoid overloading servers

## Implementation Details

### Content Extraction Strategy
1. **Multiple CSS Selectors**:
   ```python
   content_selectors = [
       'div.awsdocs-content',
       'div#main-content',
       'div[role="main"]',
       'div.awsui-context-content-header',
       'main',
       'article',
       'div.table-contents'
   ]
   ```

2. **Link Extraction**:
   - Looks for links containing `/AWS_` in their href
   - Extracts both link URL and text
   - Normalizes URLs to absolute paths

3. **Content Cleaning**:
   - Removes feedback sections
   - Preserves main documentation content
   - Handles both index and detail pages

### Crawling Process
1. **Index Page**:
   - Starts with the main resource type reference page
   - Extracts all service links
   - Saves index content in both formats

2. **Service Pages**:
   - Processes each service page sequentially
   - Extracts detailed documentation
   - Saves per-service content

3. **URL Handling**:
   - Handles relative and absolute URLs
   - Maintains AWS documentation domain
   - Preserves query parameters when needed

### Output Structure
1. **Markdown Files**:
   ```markdown
   # [Resource Name]
   
   URL: [Resource URL]
   
   [Content]
   ```

2. **JSON Files**:
   ```json
   {
     "url": "resource_url",
     "resource": "resource_name",
     "content": "extracted_content",
     "navigation": [
       {
         "href": "link_url",
         "text": "link_text"
       }
     ],
     "timestamp": "iso_timestamp"
   }
   ```

## Error Handling
- Retries on page load failures
- Graceful handling of missing content
- Detailed error logging
- Continues processing on individual page failures

## Best Practices
1. **Rate Limiting**:
   - Single concurrent page
   - Waits between requests
   - Respects server load

2. **Content Verification**:
   - Validates HTML structure
   - Checks content length
   - Verifies link validity

3. **Resource Management**:
   - Proper browser cleanup
   - Efficient memory usage
   - Organized file structure

## Usage
```python
crawler = CloudFormationNativeCrawler("output")
asyncio.run(crawler.crawl())
```

## Output Directory Structure
```
output/
  cloudformation/
    index.md                 # Main resource type listing
    index.json              # Machine-readable index
    [service_name].md       # Per-service documentation
    [service_name].json     # Per-service structured data
```

## Debugging
The crawler provides detailed debugging output:
- HTML structure analysis
- Content selector matching
- Link extraction results
- Processing progress
