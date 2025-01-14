# Crawling GitHub Pages Documentation Sites

This guide explains the methodology used to crawl the Docling documentation site (https://ds4sd.github.io/docling/) and provides tips for crawling similar GitHub Pages documentation sites.

## Understanding the Structure

### Material for MkDocs Pattern
Many GitHub Pages use Material for MkDocs, which follows a consistent structure:
```html
<body>
  <nav class="md-nav md-nav--primary">  <!-- Main navigation -->
    <ul class="md-nav__list">
      <li class="md-nav__item">
        <label class="md-nav__toggle">   <!-- Expandable sections -->
        <a class="md-nav__link">         <!-- Navigation links -->
  <main>
    <article class="md-content__inner">  <!-- Main content -->
```

### Common Sections
Documentation typically includes:
1. Getting Started / Installation
2. Concepts / Overview
3. API Reference
4. Examples / Tutorials
5. Integration Guides

## Crawling Strategy

### 1. Navigation Handling
```javascript
// Expand all navigation sections first
document.querySelectorAll('.md-nav__toggle').forEach(toggle => toggle.click());

// Wait for expansion animations
await new Promise(r => setTimeout(r, 1000));

// Get all navigation links
const links = document.querySelectorAll('.md-nav__link');
```

### 2. Content Selection
```python
crawler_config = CrawlerRunConfig(
    css_selector="article.md-content__inner",  # Main content
    wait_for="css:nav.md-nav--primary",       # Wait for navigation
    excluded_tags=["footer", "header"],        # Remove noise
    word_count_threshold=10                    # Skip empty pages
)
```

### 3. Link Processing
```python
# Remove anchors and duplicates
base_href = href.split('#')[0]
if (base_href and 
    base_href.startswith(base_url) and 
    base_href not in visited):
    to_visit.add(base_href)
```

## Tips & Tricks

### 1. Navigation Expansion
- Material for MkDocs uses checkboxes for navigation toggles
- Click all toggles at start to reveal full structure
- Wait for animations (usually 1000ms is enough)

### 2. Link Selection
- Use `.md-nav__link` for navigation links
- Exclude container buttons with `:not(.md-nav__container-button)`
- Convert relative to absolute URLs with `new URL(href, window.location.href)`

### 3. Content Extraction
- Main content is always in `article.md-content__inner`
- Code blocks are in `pre code` elements
- API sections usually start with `h2` or `h3`

### 4. Common Pitfalls
1. **Anchor Links**: Filter out `#` fragments to avoid duplicates
2. **External Links**: Skip links starting with `http`
3. **Navigation Timing**: Allow time for expansion animations
4. **Empty Pages**: Use word count threshold to skip placeholders

## Adapting for Other Sites

### 1. Check Repository Structure
```bash
# Look at docs directory structure
docs/
  ├── index.md
  ├── getting-started/
  ├── reference/
  ├── examples/
  └── assets/
```

### 2. Identify Navigation Pattern
```python
# Common selectors for different doc frameworks
selectors = {
    "material-mkdocs": ".md-nav__link",
    "docusaurus": ".menu__link",
    "vuepress": ".sidebar-link",
    "gitbook": ".css-1wt0ykv"
}
```

### 3. Configure Content Extraction
```python
extraction_schema = {
    "title": {"selector": "h1", "type": "text"},
    "content": {"selector": "article", "type": "html"},
    "code_examples": {"selector": "pre code", "type": "array"}
}
```

## Best Practices

1. **Start Simple**
   - Begin with main navigation
   - Add content extraction
   - Then handle special cases

2. **Maintain Structure**
   ```
   output/
     project_name/
       ├── index.md
       ├── json/
       │   └── index.json
       └── sections/
   ```

3. **Handle Common Issues**
   - Navigation expansion
   - Relative URLs
   - Duplicate content
   - Empty pages

4. **Debug Effectively**
   - Log found links
   - Track navigation state
   - Monitor content extraction

## Conclusion

This approach works well for GitHub Pages using Material for MkDocs and similar frameworks. The key is understanding the navigation structure and content patterns, then adapting the selectors and extraction logic accordingly. 