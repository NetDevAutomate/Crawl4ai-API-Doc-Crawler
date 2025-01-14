# Native Documentation Crawler

## Overview
The Native Documentation Crawler is a flexible and extensible tool designed to crawl AWS service documentation using Crawl4AI's native methods. It supports multiple documentation sources and can be easily extended to support new services.

## Architecture

### Main Components
1. **NativeDocCrawler**: Core crawler class that manages the crawling process
2. **AsyncWebCrawler**: Crawl4AI's native crawler for efficient web page processing
3. **BeautifulSoup**: HTML parsing and content extraction
4. **Output Formats**: Both markdown and JSON output support

### Configuration
- **Browser Config**: Headless mode with HTTPS error handling
- **Crawler Config**: Service-specific selectors and patterns
- **Rate Limiting**: Single concurrent page to avoid server overload

## Implementation Details

### Service Configuration
Each service is configured with:
1. **Base URL**: Starting point for crawling
2. **Output Directory**: Where to save crawled content
3. **Content Selectors**: List of CSS selectors to find main content
4. **Link Pattern**: Pattern to identify service-specific links

Example configuration:
```python
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
}
```

### Content Extraction
1. **Multiple Selectors**: Tries multiple CSS selectors to find content
2. **Fallback Strategy**: Falls back to finding large content divs
3. **Content Cleaning**: Removes navigation and feedback elements

### Link Processing
1. **Pattern Matching**: Uses service-specific patterns
2. **URL Normalization**: Handles relative and absolute URLs
3. **Link Extraction**: Gets both URL and text content

## Usage

### Command Line Interface
```bash
# Crawl all available sources
python crawler_native.py all

# Crawl specific source(s)
python crawler_native.py cloudformation

# Specify custom output directory
python crawler_native.py cloudformation --output-dir ./my-docs
```

### Output Structure
```
output/
  cloudformation/
    index.md                 # Main resource type listing
    index.json              # Machine-readable index
    [resource_name].md      # Per-resource documentation
    [resource_name].json    # Per-resource structured data
```

### Output Formats

#### Markdown Files
```markdown
# [Resource Name]

URL: [Resource URL]

[Content]
```

#### JSON Files
```json
{
  "url": "resource_url",
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
- Graceful handling of missing content
- Detailed error logging
- Continues processing on individual page failures

## Best Practices
1. **Rate Limiting**:
   - Single concurrent page
   - Waits between requests

2. **Content Verification**:
   - Multiple selector attempts
   - Content length validation
   - Link validation

3. **Resource Management**:
   - Proper browser cleanup
   - Efficient memory usage
   - Organized file structure

## Adding New Services
To add a new service:
1. Add configuration to `sources` dictionary
2. Define content selectors
3. Specify link pattern
4. Create output directory

Example:
```python
"new_service": {
    "url": "https://docs.example.com/api-reference",
    "output_dir": "new_service",
    "content_selectors": [
        'div.main-content',
        'article.documentation'
    ],
    "link_pattern": "/api/"
}
```

## Debugging
The crawler provides detailed debugging output:
- HTML structure analysis
- Content selector matching
- Link extraction results
- Processing progress

## Future Improvements
1. **Enhanced Content Processing**:
   - Better handling of complex HTML structures
   - Improved code block formatting
   - Enhanced table extraction

2. **Performance Optimization**:
   - Smart rate limiting
   - Caching support
   - Parallel processing options

3. **Content Validation**:
   - Schema validation
   - Link consistency checking
   - Content quality metrics
