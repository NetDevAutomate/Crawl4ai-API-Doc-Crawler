import os
import asyncio
import json
from pydantic import BaseModel, Field
from typing import List
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import LLMExtractionStrategy

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

URL = "https://aws.amazon.com/blogs/machine-learning/a-secure-approach-to-generative-ai-with-aws"


class Product(BaseModel):
    name: str
    price: str


async def main():
    # 1. Define the LLM extraction strategy
    llm_strategy = LLMExtractionStrategy(
        provider="openai/gpt-4o-mini",  # e.g. "ollama/llama2"
        api_token=os.getenv("OPENAI_API_KEY"),
        schema=Product.schema_json(),  # Or use model_json_schema()
        extraction_type="schema",
        instruction="Extract the blog post title, author, date, main content, key topics discussed, and AWS services mentioned. For services, include a brief description if available. Exclude any cookie notices, navigation menus, and other UI elements.",
        chunk_token_threshold=1000,
        overlap_rate=0.0,
        apply_chunking=True,
        input_format="markdown",  # or "html", "fit_markdown"
        extra_args={"temperature": 0.0, "max_tokens": 800},
    )

    # 2. Build the crawler config
    crawl_config = CrawlerRunConfig(
        extraction_strategy=llm_strategy, cache_mode=CacheMode.BYPASS
    )

    # 3. Create a browser config if needed
    browser_cfg = BrowserConfig(headless=True)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        # 4. Let's say we want to crawl a single page
        result = await crawler.arun(url=URL, config=crawl_config)

        if result.success:
            # 5. The extracted content is presumably JSON
            data = json.loads(result.extracted_content)
            print("Extracted items:", data)

            # 6. Show usage stats
            llm_strategy.show_usage()  # prints token usage
        else:
            print("Error:", result.error_message)


if __name__ == "__main__":
    asyncio.run(main())
