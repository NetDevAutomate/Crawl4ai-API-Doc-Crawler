import os
import sys
import json
import time
import random
import asyncio
import hashlib
import aiohttp
import argparse
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Comment
from html2text import HTML2Text
from packaging import version
from base import BaseDocCrawler, SDKConfig, RegistryConfig
from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from playwright.async_api import async_playwright
import re

class APIDocCrawler(BaseDocCrawler):
    def __init__(self):
        super().__init__("output")
        self.base_output_dir = "output"
        
        # Initialize rate limiting attributes
        self._request_times = []
        self._requests_per_minute = 60  # Default rate limit
        self._max_retries = 3
        self._retry_delay = 1.0
        self._rate_limit = asyncio.Lock()
        
        # Define sources first
        self.sources = {
            "crawl4ai": {
                "url": "https://crawl4ai.com/mkdocs/",
                "output_dir": "crawl4ai",
                "selector": "main",  # Main content container
                "link_selector": "nav a",  # Navigation links in sidebar
                "base_sections": [
                    "setup-installation",
                    "quick-start",
                    "blog-changelog",
                    "core",
                    "advanced",
                    "extraction",
                    "api-reference"
                ]
            },
            "pulumi_aws": {
                "url": "https://www.pulumi.com/registry/packages/aws/api-docs/",
                "output_dir": "pulumi",
                "selector": 'main',
                "link_selector": "ul.api a",
                "base_modules": [
                    "accessanalyzer", "account", "acm", "acmpca", "alb", "amp", "amplify", "apigateway",
                    "apigatewayv2", "appautoscaling", "appconfig", "appfabric", "appflow", "appintegrations",
                    "applicationinsights", "appmesh", "apprunner", "appstream", "appsync", "athena",
                    "auditmanager", "autoscaling", "autoscalingplans", "backup", "batch", "bcmdata",
                    "bedrock", "bedrockfoundation", "bedrockmodel", "budgets", "cfg", "chatbot", "chime",
                    "chimesdkmediapipelines", "cleanrooms", "cloud9", "cloudcontrol", "cloudformation",
                    "cloudfront", "cloudhsmv2", "cloudsearch", "cloudtrail", "cloudwatch", "codeartifact",
                    "codebuild", "codecatalyst", "codecommit", "codeconnections", "codedeploy", "codeguruprofiler",
                    "codegurureviewer", "codepipeline", "codestarconnections", "codestarnotifications",
                    "cognito", "comprehend", "computeoptimizer", "connect", "controltower", "costexplorer",
                    "costoptimizationhub", "cur", "customerprofiles", "dataexchange", "datapipeline",
                    "datasync", "datazone", "dax", "detective", "devicefarm", "devopsguru", "directconnect",
                    "directoryservice", "dlm", "dms", "docdb", "drs", "dynamodb", "ebs", "ec2", "ec2clientvpn",
                    "ec2transitgateway", "ecr", "ecrpublic", "ecs", "efs", "eks", "elasticache",
                    "elasticbeanstalk", "elasticsearch", "elastictranscoder", "elb", "emr", "emrcontainers",
                    "emrserverless", "evidently", "finspace", "fis", "fms", "fsx", "gamelift", "glacier",
                    "globalaccelerator", "glue", "grafana", "guardduty", "iam", "identitystore", "imagebuilder",
                    "inspector", "inspector2", "iot", "ivs", "ivschat", "kendra", "keyspaces", "kinesis",
                    "kinesisanalyticsv2", "kms", "lakeformation", "lambda", "lb", "lex", "licensemanager",
                    "lightsail", "location", "m2", "macie", "macie2", "mediaconvert", "medialive",
                    "mediapackage", "mediastore", "memorydb", "mq", "msk", "mskconnect", "mwaa", "neptune",
                    "networkfirewall", "networkmanager", "networkmonitor", "oam", "opensearch",
                    "opensearchingest", "opsworks", "organizations", "outposts", "paymentcryptography",
                    "pinpoint", "pipes", "polly", "pricing", "qldb", "quicksight", "ram", "rbin", "rds",
                    "redshift", "redshiftdata", "redshiftserverless", "rekognition", "resiliencehub",
                    "resourceexplorer", "resourcegroups", "resourcegroupstaggingapi", "rolesanywhere",
                    "route53", "route53domains", "route53recoverycontrol", "route53recoveryreadiness",
                    "rum", "s3", "s3control", "s3outposts", "s3tables", "sagemaker", "scheduler", "schemas",
                    "secretsmanager", "securityhub", "securitylake", "serverlessrepository", "servicecatalog",
                    "servicediscovery", "servicequotas", "ses", "sesv2", "sfn", "shield", "signer",
                    "simpledb", "sns", "sqs", "ssm", "ssmcontacts", "ssmincidents", "ssoadmin",
                    "storagegateway", "swf", "synthetics", "timestreaminfluxdb", "timestreamwrite",
                    "transcribe", "transfer", "verifiedaccess", "verifiedpermissions", "vpc", "vpclattice",
                    "waf", "wafregional", "wafv2", "worklink", "workspaces", "xray"
                ]
            },
            "boto3": {
                "url": "https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/index.html",
                "output_dir": "boto3",
                "selector": 'div.section',
                "link_selector": "li.toctree-l1 a.reference.internal"
            },
            "terraform_aws": {
                "url": "https://registry.terraform.io/providers/hashicorp/aws/latest/docs",
                "output_dir": "terraform",
                "api_based": True,
                "selector": "div[role='main']",  # Main content container
                "link_selector": "a[href*='/docs/']"  # Navigation links in sidebar
            },
            "go_sdk": {
                "url": "https://pkg.go.dev/github.com/aws/aws-sdk-go-v2",
                "output_dir": "go_sdk",
                "selector": 'main',
                "link_selector": "a[href*='/service/']"
            },
            "pydantic_ai": {
                "url": "https://ai.pydantic.dev/",
                "output_dir": "pydantic_ai",
                "selector": "main",  # Main content container
                "link_selector": "nav a",  # Navigation links in sidebar
                "base_sections": [
                    "install",
                    "models",
                    "dependencies",
                    "agents",
                    "help",
                    "contributing",
                    "troubleshooting"
                ]
            },
            "langtrace": {
                "url": "https://docs.langtrace.ai/",
                "output_dir": "langtrace",
                "selector": "main",  # Main content container
                "link_selector": ".sidebar-content a",  # Navigation links in sidebar
                "base_sections": [
                    "hosting/overview",
                    "getting-started",
                    "tracing",
                    "prompting",
                    "evaluations-testing",
                    "supported-integrations",
                    "api-reference",
                    "hosting",
                    "contact-us"
                ]
            },
        }
        
        # Initialize html2text with configuration
        self.h2t = HTML2Text()
        self.h2t.ignore_links = False
        self.h2t.ignore_images = False
        self.h2t.ignore_tables = False
        self.h2t.body_width = 0  # Don't wrap lines
        self.h2t.ignore_emphasis = False
        self.h2t.ul_item_mark = '-'  # Use - for unordered lists
        self.h2t.protect_links = True  # Don't wrap links
        self.h2t.unicode_snob = True  # Use Unicode characters
        self.h2t.images_to_alt = True  # Use alt text for images
        self.h2t.single_line_break = True  # Use single line breaks
        
        # Anti-bot settings
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
        ]
        
        self.accept_languages = [
            'en-US,en;q=0.9',
            'en-GB,en;q=0.9',
            'en;q=0.9',
        ]
        
        self.rate_limits = {
            "crawl4ai.com": 2,  # 2 requests per second
            "pkg.go.dev": 0.1,  # 1 request per 10 seconds
            "www.pulumi.com": 2,
            "boto3.amazonaws.com": 2,
            "registry.terraform.io": 2,
            "api.github.com": 10,  # 10 requests per second
            "ai.pydantic.dev": 2,  # 2 requests per second
            "docs.langtrace.ai": 2,  # 2 requests per second
        }
        
        self.last_request_time = {}
        self.backoff_times = {}  # Track backoff times per domain
        
        # Create output directories
        for source in self.sources.values():
            os.makedirs(os.path.join(self.base_output_dir, source["output_dir"]), exist_ok=True)
        
        # Separate directories for markdown and json
        self.markdown_output_dir = self.base_output_dir  # Keep original location for markdown
        self.json_output_dir = os.path.join(self.base_output_dir, "json_reference")
        
        # Create json_reference directory
        os.makedirs(self.json_output_dir, exist_ok=True)
        
    async def crawl_all(self):
        """Crawl all specified sources."""
        async with aiohttp.ClientSession() as session:
            for source_key, source in self.sources.items():
                if source_key == "terraform_aws":
                    await self.crawl_terraform_docs(session)
                elif source_key == "go_sdk":
                    await self.crawl_go_sdk_docs(session)
                else:
                    await self.process_page(session, source["url"], source_key)

    async def fetch_page(self, session: aiohttp.ClientSession, url: str) -> str:
        """Fetch a page with rate limiting and retries."""
        if not self.should_fetch_url(url):
            print(f"Skipping {url} - Not modified since last fetch")
            return None
            
        domain = urlparse(url).netloc
        await self.rate_limit(domain)
        
        headers = {
            'User-Agent': random.choice(self.user_agents),
            'Accept-Language': random.choice(self.accept_languages),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    content = await response.text()
                    print(f"Fetched {url} - Content length: {len(content)}")
                    self.update_cache(url, content)
                    return content
                else:
                    print(f"Failed to fetch {url} - Status: {response.status}")
                    return None
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            return None

    def clean_html_content(self, content: str) -> str:
        """Clean HTML content before processing."""
        if not content:
            return ""
        try:
            # Parse HTML
            soup = BeautifulSoup(content, 'html.parser')
            
            # Remove script and style elements
            for element in soup(['script', 'style']):
                element.decompose()
            
            # Remove comments
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            # Get the cleaned HTML
            cleaned_html = str(soup)
            return cleaned_html
        except Exception as e:
            print(f"Error cleaning HTML content: {str(e)}")
            return ""

    async def process_page(self, session: aiohttp.ClientSession, url: str, source_key: str):
        """Process a single page."""
        try:
            html_content = await self.fetch_page(session, url)
            if not html_content:
                print(f"No content received for {url}")
                return
            
            cleaned_content = self.clean_html_content(html_content)
            if not cleaned_content:
                print(f"Failed to clean content for {url}")
                return
            
            # Extract service name from URL
            service_name = url.rstrip('/').split('/')[-1]
            
            # Create document structure
            doc_structure = {
                "url": url,
                "service": service_name,
                "overview": self.extract_overview(cleaned_content),
                "api_reference": self.extract_api_reference(cleaned_content),
                "examples": self.extract_examples(cleaned_content)
            }
            
            # Save as markdown
            markdown_content = self.format_for_markdown(doc_structure)
            self.save_markdown(source_key, service_name, markdown_content)
            
            # Save as JSON
            self.save_json(source_key, service_name, doc_structure)
            
        except Exception as e:
            print(f"Error processing page {url}: {str(e)}")

    def extract_overview(self, content: str) -> str:
        """Extract overview section from the content."""
        if not content:
            return ""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            # Try to find overview section
            overview_section = soup.select_one('main')
            if overview_section:
                return self.html_to_markdown(str(overview_section))
            return ""
        except Exception as e:
            print(f"Error extracting overview: {str(e)}")
            return ""

    def extract_api_reference(self, content: str) -> List[Dict[str, str]]:
        """Extract API reference documentation."""
        soup = BeautifulSoup(content, 'html.parser')
        api_refs = []
        
        # Look for method definitions
        for method in soup.find_all(['h2', 'h3']):
            if 'method' in method.text.lower() or 'function' in method.text.lower():
                method_doc = {
                    "name": method.text.strip(),
                    "description": "",
                    "syntax": "",
                    "parameters": [],
                    "returns": ""
                }
                
                # Get description
                next_elem = method.find_next(['p', 'pre', 'h2', 'h3'])
                while next_elem and next_elem.name == 'p':
                    method_doc["description"] += next_elem.text.strip() + "\n"
                    next_elem = next_elem.find_next(['p', 'pre', 'h2', 'h3'])
                
                api_refs.append(method_doc)
        
        return api_refs

    def extract_examples(self, content: str) -> List[Dict[str, str]]:
        """Extract code examples."""
        soup = BeautifulSoup(content, 'html.parser')
        examples = []
        
        for example in soup.find_all(['pre', 'code']):
            if example.text.strip():
                examples.append({
                    "code": example.text.strip(),
                    "language": example.get('class', [''])[0] if example.get('class') else ""
                })
        
        return examples

    def format_for_markdown(self, doc_structure: Dict[str, Any]) -> str:
        """Format the document structure into markdown."""
        markdown = ""
        markdown += f"# {doc_structure['service']}\n\n"
        markdown += f"URL: {doc_structure['url']}\n\n"
        markdown += f"Overview:\n\n{doc_structure['overview']}\n\n"
        markdown += f"API Reference:\n\n"
        for api_ref in doc_structure['api_reference']:
            markdown += f"### {api_ref['name']}\n\n"
            markdown += f"{api_ref['description']}\n\n"
        markdown += f"Examples:\n\n"
        for example in doc_structure['examples']:
            markdown += f"### {example['language']}\n\n"
            markdown += f"```\n{example['code']}\n```\n\n"
        return markdown

    def save_markdown(self, source: str, filename: str, content: str):
        """Save content as markdown file."""
        if not filename.endswith('.md'):
            filename = f"{filename}.md"
            
        output_path = os.path.join(self.markdown_output_dir, source, filename)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def save_json(self, source: str, service_name: str, content: Dict[str, Any]):
        """Save documentation in a structured JSON format optimized for LLM consumption."""
        if not service_name.endswith('.json'):
            service_name = f"{service_name}.json"
            
        output_path = os.path.join(self.json_output_dir, source, service_name)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Add metadata to help LLMs understand the context
        doc_structure = {
            "metadata": {
                "source": source,  # e.g., "pulumi_aws", "boto3", "terraform_aws"
                "service": service_name.replace('.json', ''),  # e.g., "s3", "lambda", etc.
                "timestamp": datetime.now().isoformat(),  # Use timezone-aware datetime
                "format_version": "1.0"
            },
            "content": content
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(doc_structure, f, indent=2, ensure_ascii=False)

    async def fetch_terraform_docs(self, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """Fetch documentation for the Terraform AWS provider from GitHub."""
        # Base URL for raw content
        base_raw_url = "https://raw.githubusercontent.com/hashicorp/terraform-provider-aws/main/website/docs"
        print(f"Fetching Terraform docs from GitHub")
        
        try:
            docs = []
            # Get the list of all directories in docs/
            async with session.get("https://api.github.com/repos/hashicorp/terraform-provider-aws/contents/website/docs", 
                                 headers={"Accept": "application/vnd.github.v3+json"}) as response:
                if response.status != 200:
                    print(f"Failed to fetch root directory listing: {response.status}")
                    return []
                
                directories = [item for item in await response.json() if item['type'] == 'dir']
                print(f"Found directories: {[d['name'] for d in directories]}")
                
                # Process each directory
                for directory in directories:
                    dir_name = directory['name']
                    print(f"Processing directory: {dir_name}")
                    
                    # Get files in the directory
                    async with session.get(directory['url'], 
                                         headers={"Accept": "application/vnd.github.v3+json"}) as dir_response:
                        if dir_response.status != 200:
                            print(f"Failed to fetch directory {dir_name} listing: {dir_response.status}")
                            continue
                        
                        files = await dir_response.json()
                        
                        for file in files:
                            # Check for both .md and .html.markdown extensions
                            if not (file['name'].endswith('.md') or file['name'].endswith('.html.markdown')):
                                continue
                                
                            # Get the raw content
                            raw_url = file['download_url']
                            print(f"Fetching {dir_name}/{file['name']}")
                            
                            try:
                                async with session.get(raw_url) as response:
                                    if response.status != 200:
                                        print(f"Failed to fetch {file['name']}: {response.status}")
                                        continue
                                    
                                    content = await response.text()
                                    
                                    # Extract title from the markdown content
                                    title = ''
                                    for line in content.split('\n'):
                                        if line.startswith('# '):
                                            title = line[2:].strip()
                                            break
                                    
                                    if not title:
                                        # Remove both .html.markdown and .md extensions
                                        base_name = file['name'].replace('.html.markdown', '').replace('.md', '')
                                        title = base_name.replace('-', ' ').title()
                                    
                                    # Map directory names to doc types
                                    doc_type = {
                                        'r': 'resources',
                                        'd': 'data-sources',
                                        'guides': 'guides',
                                        'index': 'index'
                                    }.get(dir_name, dir_name)
                                    
                                    path = file['name'].replace('.html.markdown', '').replace('.md', '')
                                    
                                    docs.append({
                                        "title": title,
                                        "path": f"{doc_type}/{path}",
                                        "type": doc_type,
                                        "description": content,
                                        "url": f"https://registry.terraform.io/providers/hashicorp/aws/latest/docs/{doc_type}/{path}"
                                    })
                                    print(f"Processed {title} ({doc_type})")
                                    
                                    # Add a small delay between requests
                                    await asyncio.sleep(0.1)
                                    
                            except Exception as e:
                                print(f"Error processing {file['name']}: {str(e)}")
                                continue
                    
            print(f"Found {len(docs)} Terraform docs")
            return docs
                
        except Exception as e:
            print(f"Error fetching Terraform docs: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    async def process_terraform_docs(self, docs: List[Dict[str, Any]], output_dir: str):
        """Process and save Terraform documentation."""
        for doc in docs:
            title = doc.get("title", "").replace("/", "-")
            if not title:
                continue
                
            content = doc.get("description", "")
            if not content:
                continue
                
            # Determine doc type (resource or data source)
            doc_type = doc.get("type", "resources")
            
            # Create subdirectories if they don't exist
            os.makedirs(os.path.join(self.markdown_output_dir, "terraform", doc_type), exist_ok=True)
            os.makedirs(os.path.join(self.json_output_dir, "terraform", doc_type), exist_ok=True)
            
            # Convert HTML to markdown
            markdown_content = f"# {title}\n\n"
            markdown_content += f"Type: {doc_type}\n\n"
            markdown_content += self.h2t.handle(content)  # Use html2text to convert HTML to markdown
            
            # Save as markdown
            filename = f"{doc_type}/{title.lower()}.md"
            self.save_markdown("terraform", filename, markdown_content)
            
            # Save as JSON
            doc_structure = {
                "title": title,
                "path": doc.get("path", ""),
                "type": doc_type,
                "html_content": content,
                "markdown_content": markdown_content,
                "url": doc.get("url", "")
            }
            self.save_json("terraform", f"{doc_type}/{title.lower()}", doc_structure)
            
        print(f"Processed {len(docs)} Terraform docs")

    async def crawl_terraform_docs(self, session: aiohttp.ClientSession):
        """Crawl Terraform documentation using GitHub API."""
        source = self.sources["terraform_aws"]
        try:
            # Fetch documentation
            docs = await self.fetch_terraform_docs(session)
            if docs:
                # Process and save documentation
                await self.process_terraform_docs(docs, source["output_dir"])
            else:
                print("No Terraform docs to process")
            
        except Exception as e:
            print(f"Error crawling Terraform docs: {str(e)}")
            import traceback
            traceback.print_exc()

    async def fetch_go_sdk_docs(self, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """Fetch documentation for the AWS Go SDK v2."""
        base_url = "https://pkg.go.dev/github.com/aws/aws-sdk-go-v2"
        print(f"Fetching Go SDK docs from: {base_url}")
        
        # First get the list of service packages using rate limited request with caching
        text = await self._rate_limited_request(session, base_url)
        if not text:
            print(f"Failed to fetch Go SDK index")
            return []
            
        soup = BeautifulSoup(text, 'html.parser')
        
        # Find all service package links
        service_links = []
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if '/service/' in href:
                service_name = href.split('/')[-1]
                service_links.append({
                    'name': service_name,
                    'url': urljoin(base_url, href)
                })
        
        print(f"Found {len(service_links)} Go SDK service packages")
        
        # Fetch each service's documentation
        docs = []
        for service in service_links:
            print(f"Fetching Go SDK docs for {service['name']}")
            try:
                # Use rate limited request with caching for service docs
                service_text = await self._rate_limited_request(session, service['url'])
                if not service_text:
                    print(f"Failed to fetch {service['name']} docs")
                    continue
                    
                service_soup = BeautifulSoup(service_text, 'html.parser')
                
                # Get package documentation
                doc_content = service_soup.find('div', {'class': 'Documentation-content'})
                if not doc_content:
                    print(f"No documentation found for {service['name']}")
                    continue
                    
                # Get package overview
                overview = doc_content.find('section', {'class': 'Documentation-overview'})
                overview_text = overview.get_text() if overview else ""
                
                # Get types and functions
                types_section = doc_content.find('section', {'id': 'pkg-types'})
                types_text = types_section.get_text() if types_section else ""
                
                functions_section = doc_content.find('section', {'id': 'pkg-functions'})
                functions_text = functions_section.get_text() if functions_section else ""
                
                docs.append({
                    'service': service['name'],
                    'url': service['url'],
                    'overview': overview_text,
                    'types': types_text,
                    'functions': functions_text
                })
                
                # Add a small delay between requests
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"Error fetching {service['name']} docs: {str(e)}")
                continue
                
        return docs

    async def process_go_sdk_docs(self, docs: List[Dict[str, Any]], output_dir: str):
        """Process and save Go SDK documentation."""
        for doc in docs:
            service = doc['service']
            
            # Create service directory
            os.makedirs(os.path.join(self.markdown_output_dir, "go_sdk", service), exist_ok=True)
            os.makedirs(os.path.join(self.json_output_dir, "go_sdk", service), exist_ok=True)
            
            # Save as markdown
            markdown_content = f"# AWS SDK for Go v2 - {service}\n\n"
            markdown_content += f"Package URL: {doc['url']}\n\n"
            
            if doc['overview']:
                markdown_content += "## Overview\n\n"
                markdown_content += doc['overview'] + "\n\n"
                
            if doc['types']:
                markdown_content += "## Types\n\n"
                markdown_content += doc['types'] + "\n\n"
                
            if doc['functions']:
                markdown_content += "## Functions\n\n"
                markdown_content += doc['functions'] + "\n\n"
                
            self.save_markdown("go_sdk", f"{service}/index", markdown_content)
            
            # Save as JSON
            doc_structure = {
                'service': service,
                'url': doc['url'],
                'overview': doc['overview'],
                'types': doc['types'],
                'functions': doc['functions']
            }
            self.save_json("go_sdk", f"{service}/index", doc_structure)
            
        print(f"Processed {len(docs)} Go SDK docs")

    async def crawl_go_sdk_docs(self, session: aiohttp.ClientSession):
        """Crawl Go SDK documentation."""
        source = self.sources["go_sdk"]
        try:
            # Fetch documentation
            docs = await self.fetch_go_sdk_docs(session)
            if docs:
                # Process and save documentation
                await self.process_go_sdk_docs(docs, source["output_dir"])
            else:
                print("No Go SDK docs to process")
            
        except Exception as e:
            print(f"Error crawling Go SDK docs: {str(e)}")
            import traceback
            traceback.print_exc()

    async def fetch_and_process_page(self, session: aiohttp.ClientSession, url: str, source_key: str):
        """Fetch and process a single page."""
        html = await self.fetch_page(session, url)
        if html:
            await self.process_page(session, url, source_key)

    async def process_batch(self, session: aiohttp.ClientSession, urls: List[str], source_key: str):
        """Process a batch of URLs."""
        tasks = []
        for url in urls:
            if self.is_valid_url(url, urlparse(self.sources[source_key]["url"]).netloc):
                tasks.append(self.fetch_and_process_page(session, url, source_key))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for url, result in zip(urls, results):
                if isinstance(result, Exception):
                    print(f"Failed to process {url}: {str(result)}")

    async def rate_limit(self, domain: str) -> None:
        """Apply rate limiting for a specific domain."""
        if domain in self.rate_limits:
            current_time = time.time()
            if domain in self.last_request_time:
                time_since_last = current_time - self.last_request_time[domain]
                if time_since_last < 1.0 / self.rate_limits[domain]:
                    delay = (1.0 / self.rate_limits[domain]) - time_since_last
                    delay += random.uniform(0.1, 0.5)  # Add jitter
                    print(f"Rate limiting {domain}, waiting {delay:.2f}s")
                    await asyncio.sleep(delay)
            self.last_request_time[domain] = current_time

    async def fetch_pulumi_docs(self, session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
        """Fetch documentation for the Pulumi AWS provider."""
        base_url = "https://www.pulumi.com/registry/packages/aws/api-docs"
        print(f"Fetching Pulumi AWS provider index")
        
        try:
            # First get the index page to discover all resources
            async with session.get(base_url, headers={"Accept": "text/html"}) as response:
                if response.status != 200:
                    print(f"Failed to fetch index: {response.status}")
                    return []
                
                content = await response.text()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Find all resource links in the navigation
                docs = []
                resource_links = soup.select('a[href*="/api-docs/aws/"]')
                
                for link in resource_links:
                    href = link['href']
                    if not href.startswith('http'):
                        href = urljoin(base_url, href)
                    
                    # Skip non-resource pages
                    if not any(x in href for x in ['/resources/', '/functions/', '/types/']):
                        continue
                        
                    print(f"Found resource: {href}")
                    
                    try:
                        async with session.get(href, headers={"Accept": "text/html"}) as doc_response:
                            if doc_response.status != 200:
                                print(f"Failed to fetch {href}: {doc_response.status}")
                                continue
                                
                            doc_content = await doc_response.text()
                            doc_soup = BeautifulSoup(doc_content, 'html.parser')
                            
                            # Extract main content
                            main_content = doc_soup.select_one('main')
                            if not main_content:
                                continue
                                
                            # Extract title
                            title = doc_soup.select_one('h1')
                            title_text = title.get_text(strip=True) if title else href.split('/')[-1]
                            
                            # Determine doc type from URL
                            if '/resources/' in href:
                                doc_type = 'resources'
                            elif '/functions/' in href:
                                doc_type = 'functions'
                            elif '/types/' in href:
                                doc_type = 'types'
                            else:
                                doc_type = 'other'
                            
                            docs.append({
                                "title": title_text,
                                "path": href.split('/api-docs/aws/')[-1],
                                "type": doc_type,
                                "description": str(main_content),
                                "url": href
                            })
                            print(f"Processed {title_text} ({doc_type})")
                            
                            # Add a small delay between requests
                            await asyncio.sleep(0.1)
                            
                    except Exception as e:
                        print(f"Error processing {href}: {str(e)}")
                        continue
                
                print(f"Found {len(docs)} Pulumi docs")
                return docs
                
        except Exception as e:
            print(f"Error fetching Pulumi docs: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def should_fetch_url(self, url: str) -> bool:
        """Check if a URL should be fetched based on the source configuration.
        
        Args:
            url: The URL to check
            
        Returns:
            bool: True if the URL should be fetched, False otherwise
        """
        # Basic URL validation
        if not url or not isinstance(url, str):
            return False
            
        # Check if URL matches any of our source domains
        for source_key, source_config in self.sources.items():
            if source_config['url'] in url:
                return True
                
        return False

    def update_cache(self, url: str, content: str) -> None:
        """Update the cache with fetched content.
        
        Args:
            url: The URL that was fetched
            content: The content that was fetched
        """
        cache_dir = os.path.join(self.base_output_dir, ".cache")
        os.makedirs(cache_dir, exist_ok=True)
        
        # Create a hash of the URL to use as filename
        url_hash = hashlib.md5(url.encode()).hexdigest()
        cache_file = os.path.join(cache_dir, f"{url_hash}.html")
        
        # Save content to cache
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(content)

    def html_to_markdown(self, html_content: str) -> str:
        """Convert HTML content to markdown format.
        
        Args:
            html_content: HTML content to convert
            
        Returns:
            str: Converted markdown content
        """
        if not html_content:
            return ""
            
        # Use the configured html2text instance
        return self.h2t.handle(html_content).strip()

def main():
    """Main entry point for the crawler."""
    parser = argparse.ArgumentParser(description='Crawl AWS documentation from various sources.')
    parser.add_argument('sources', nargs='*', help='Specific sources to crawl (e.g., pulumi_aws, boto3, terraform_aws, all). If none specified, crawls all sources.')
    parser.add_argument('--output-dir', '-o', help='Custom output directory for documentation')
    parser.add_argument('--central-repo', '-c', action='store_true', help='Structure output for a central documentation repository')
    args = parser.parse_args()

    crawler = APIDocCrawler()
    
    # Set custom output directory if provided
    if args.output_dir:
        if args.central_repo:
            # Structure for central repo
            crawler.base_output_dir = os.path.join(args.output_dir, "docs")
            crawler.markdown_output_dir = crawler.base_output_dir
            crawler.json_output_dir = os.path.join(args.output_dir, "json_reference")
        else:
            # Structure for project-specific docs
            crawler.base_output_dir = args.output_dir
            crawler.markdown_output_dir = args.output_dir
            crawler.json_output_dir = os.path.join(args.output_dir, "json_reference")
        
        # Create output directories
        os.makedirs(crawler.base_output_dir, exist_ok=True)
        os.makedirs(crawler.json_output_dir, exist_ok=True)
    
    # If specific sources are provided, validate and filter them
    if args.sources:
        # Handle 'all' option
        if 'all' in args.sources:
            if len(args.sources) > 1:
                print("Warning: 'all' specified with other sources - will crawl all sources")
            print(f"Crawling all available sources: {', '.join(crawler.sources.keys())}")
        else:
            invalid_sources = [s for s in args.sources if s not in crawler.sources]
            if invalid_sources:
                print(f"Error: Invalid source(s): {', '.join(invalid_sources)}")
                print(f"Available sources: {', '.join(crawler.sources.keys())}, all")
                sys.exit(1)
                
            # Filter sources to only those requested
            crawler.sources = {k: v for k, v in crawler.sources.items() if k in args.sources}
        
    print(f"Starting crawler for sources: {', '.join(crawler.sources.keys())}")
    asyncio.run(crawler.crawl_all())

if __name__ == "__main__":
    main()
