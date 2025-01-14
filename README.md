# AWS Documentation Reference

This repository contains crawled API documentation from multiple sources:
- Terraform AWS Provider
- Pulumi AWS Provider
- Boto3 SDK
- Crawl4AI Documentation

## Directory Structure

```
output/
  terraform/           # Terraform AWS Provider docs
    resources/
    data-sources/
    guides/
  pulumi/             # Pulumi AWS Provider docs
    resources/
    api/
    guides/
  boto3/              # AWS SDK for Python docs
    services/
    guides/
  crawl4ai/           # Crawl4AI documentation
    core/
    api/
    guides/
```

Each documentation source follows a consistent format:
- Markdown files for human reading
- JSON files for machine consumption
- Original HTML (optional, for debugging)

## Workflow

1. **Crawl Documentation**
   ```bash
   # Crawl a specific source
   python crawler.py terraform_aws
   
   # Or crawl multiple sources
   python crawler.py pulumi_aws boto3 terraform_aws
   ```
   This creates:
   - Human-readable markdown in `output/<source>/`
   - Machine-readable JSON in `output/json_reference/<source>/`

2. **Use Documentation Programmatically**
   ```python
   from doc_loader import APIDocLoader
   
   # Initialize with crawled docs
   loader = APIDocLoader("output/json_reference")
   
   # Search across all documentation
   results = loader.semantic_search(
       "How to create an S3 bucket with versioning?"
   )
   
   # Get examples for a specific service
   examples = loader.get_api_examples(
       service_name="s3",
       source="pulumi_aws"
   )
   ```

## Structure
- docs/
  - terraform/  # Terraform AWS Provider docs
  - pulumi/     # Pulumi AWS Provider docs
  - boto3/      # Boto3 SDK docs
  - crawl4ai/   # Crawl4AI documentation
- output/json_reference/  # Structured JSON for programmatic use

## Using the Documentation Loader

The `doc_loader.py` provides programmatic access to the crawled documentation:

```python
from doc_loader import APIDocLoader, format_for_llm

# Initialize the loader
loader = APIDocLoader("output/json_reference")

# 1. Semantic Search
# Find relevant documentation based on natural language queries
results = loader.semantic_search(
    query="How to create an S3 bucket with versioning?",
    top_k=3,  # Return top 3 results
    source_filter="pulumi_aws"  # Optional: filter by source
)

# 2. Service-Specific Documentation
# Get all documentation for a service
s3_docs = loader.get_service_docs(
    service_name="s3",
    source="boto3"  # Optional: specify source
)

# 3. Code Examples
# Extract code examples for a service/method
examples = loader.get_api_examples(
    service_name="s3",
    method_name="create_bucket",  # Optional: filter by method
    source="terraform_aws"  # Optional: specify source
)

# 4. Format for LLM Consumption
# Format results in a way that's optimal for LLMs
formatted_docs = format_for_llm(results)
```

### Features

1. **Semantic Search**
   - Uses sentence embeddings for meaning-based search
   - Supports filtering by documentation source
   - Returns ranked results by relevance

2. **Service Documentation**
   - Retrieve all documentation for specific services
   - Filter by source (e.g., Terraform, Pulumi, Boto3)
   - Access structured content including overview, API reference, and examples

3. **Code Examples**
   - Extract relevant code examples
   - Filter by service, method, or source
   - Includes language information and context

4. **LLM Integration**
   - Format documentation for optimal LLM consumption
   - Includes metadata, overview, API reference, and examples
   - Structured for easy parsing and context understanding

## Guide: Analyzing API Documentation Sites for crawl4ai

### 1. Initial Analysis Tools
```bash
# Chrome DevTools shortcuts
F12 or Cmd+Opt+I (Mac)  # Open DevTools
Cmd+Shift+C (Mac)       # Enable element selector
```

### 2. Key Elements to Identify

1. **Main Content Container**:
   ```python
   # Common patterns to look for
   selectors = [
       "main",                    # Modern sites often use semantic HTML
       "article",                 # Documentation articles
       ".content",               # Content class
       ".documentation",         # Documentation class
       "[role='main']",         # ARIA role
       ".markdown-body"         # Documentation body (e.g., GitHub)
   ]
   
   # Example crawl4ai config
   config = CrawlerRunConfig(
       wait_for="css:main",        # Wait for main content
       css_selector="main",        # Extract main content
       wait_until="load"           # Wait for page load
   )
   ```

2. **Navigation Elements**:
   ```python
   # Common navigation patterns
   nav_selectors = [
       "nav",                     # Semantic nav element
       ".sidebar",               # Sidebar navigation
       ".toc",                  # Table of contents
       ".menu",                 # Menu container
       "[role='navigation']"    # ARIA navigation
   ]
   
   # Example link extraction
   links = result.links['internal']  # crawl4ai's native link extraction
   ```

3. **Code Blocks**:
   ```python
   # Common code block patterns
   code_selectors = [
       "pre",                    # Preformatted code
       "code",                   # Inline code
       ".highlight",            # Syntax highlighting
       ".code-block"           # Code block container
   ]
   ```

### 3. Analysis Process

1. **URL Structure Analysis**:
   ```python
   # Example URL patterns to look for
   patterns = {
       "section_urls": "/docs/section/",
       "api_urls": "/api-reference/",
       "anchors": "#section-name",
       "versioned": "/v2/docs/"
   }
   
   # crawl4ai configuration
   config = CrawlerRunConfig(
       # Skip certain patterns
       url_filter=lambda url: not url.endswith('.png')
   )
   ```

2. **Content Loading**:
   ```python
   # Check if content is:
   # 1. Static HTML
   config = CrawlerRunConfig(
       wait_until="domcontentloaded"  # Faster for static content
   )
   
   # 2. Dynamic JavaScript
   config = CrawlerRunConfig(
       wait_until="networkidle",     # Wait for dynamic content
       wait_for="css:.content"      # Wait for specific element
   )
   ```

3. **Site Structure Mapping**:
   ```python
   # Common documentation structures
   structures = {
       "nested": {
           "url": "base_url/section/subsection",
           "config": CrawlerRunConfig(
               wait_for="css:main",
               css_selector="main"
           )
       },
       "flat": {
           "url": "base_url/page-name",
           "config": CrawlerRunConfig(
               wait_for="css:article",
               css_selector="article"
           )
       },
       "anchored": {
           "url": "base_url/page#section",
           "config": CrawlerRunConfig(
               wait_for="css:.section",
               css_selector=".section"
           )
       }
   }
   ```

### 4. crawl4ai Configuration Examples

1. **Basic Static Site**:
   ```python
   config = CrawlerRunConfig(
       wait_for="css:main",
       wait_until="domcontentloaded",
       process_iframes=False,
       only_text=False,
       css_selector="main"
   )
   ```

2. **Dynamic Documentation**:
   ```python
   config = CrawlerRunConfig(
       wait_for="css:.content",
       wait_until="networkidle",
       process_iframes=True,
       only_text=False,
       css_selector=".content"
   )
   ```

3. **API Reference**:
   ```python
   config = CrawlerRunConfig(
       wait_for="css:.api-content",
       wait_until="networkidle",
       process_iframes=False,
       only_text=False,
       css_selector=".api-content",
       url_filter=lambda url: "/api/" in url
   )
   ```

### 5. Common Challenges and Solutions

1. **Dynamic Content**:
   ```python
   # Wait for dynamic content to load
   config = CrawlerRunConfig(
       wait_until="networkidle",
       timeout=30000  # 30 seconds
   )
   ```

2. **Infinite Scrolling**:
   ```python
   # Handle pagination or infinite scroll
   config = CrawlerRunConfig(
       wait_for="css:.content",
       scroll_to_bottom=True,
       scroll_timeout=5000
   )
   ```

3. **Authentication**:
   ```python
   # Handle authenticated content
   browser_config = BrowserConfig(
       headless=True,
       storage_state="auth.json"  # Save authenticated state
   )
   ```

4. **Rate Limiting**:
   ```python
   # Implement rate limiting
   rate_limits = {
       "docs.example.com": 2,  # 2 requests per second
   }
   ```

### 6. Testing Your Selectors

1. **Chrome DevTools Console**:
   ```javascript
   // Test CSS selectors
   document.querySelector('main')
   document.querySelectorAll('nav a')
   
   // Test content extraction
   document.querySelector('main').textContent
   ```

2. **Python Interactive Testing**:
   ```python
   # Quick selector testing
   async def test_selectors(url, selector):
       config = CrawlerRunConfig(
           wait_for=f"css:{selector}",
           css_selector=selector
       )
       result = await crawler.arun(url=url, config=config)
       print(f"Found content: {bool(result.html)}")
       return result
   ```

### 7. Best Practices

1. **Start Simple**:
   ```python
   # Begin with basic selectors
   config = CrawlerRunConfig(
       wait_for="css:main",
       css_selector="main"
   )
   ```

2. **Iterate and Refine**:
   ```python
   # Add more specific selectors
   config = CrawlerRunConfig(
       wait_for="css:main",
       css_selector="main article",
       url_filter=lambda url: "/docs/" in url
   )
   ```

3. **Document Your Analysis**:
   ```python
   # Comment your findings
   sources = {
       "example_docs": {
           "url": "https://docs.example.com",
           "selector": "main",  # Main content wrapper
           "link_selector": "nav a",  # Navigation links
           "code_selector": "pre code"  # Code blocks
       }
   }
   ```

## Usage
This repository is designed to be used as a git submodule in your projects:
```bash
git submodule add https://github.com/your-org/aws-docs-reference .docs/aws
```
