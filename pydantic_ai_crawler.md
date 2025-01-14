# Pydantic AI Documentation Crawler

## Overview
This crawler is designed to extract documentation from the Pydantic AI documentation site (https://ai.pydantic.dev/). It uses crawl4ai to navigate and extract content while respecting the site's structure and rate limits.

## Methodology

### 1. Site Structure
The Pydantic AI documentation follows a Material for MkDocs structure with:
- Main content in `<main>` elements
- Navigation in sidebar
- Single-page documentation style with anchor links
- Clean URLs without file extensions

### 2. Crawling Strategy
- Starts from the main index page (https://ai.pydantic.dev/)
- Uses two configurations:
  - Index page configuration for the main landing page
  - Page configuration for content pages
- Handles anchor links by normalizing URLs to prevent duplicate crawling
- Processes pages concurrently (2 at a time) to avoid overloading the server

### 3. Content Extraction
The crawler extracts:
- Main content using CSS selector "main"
- Internal navigation links
- Page metadata (URL, title, timestamp)

### 4. Output Schema

#### Markdown Files 