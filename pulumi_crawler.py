"""Pulumi AWS provider documentation crawler."""

import os
import json
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from base import BaseDocCrawler, RegistryConfig

class PulumiCrawler(BaseDocCrawler):
    """Crawler for Pulumi AWS provider documentation."""
    
    def __init__(self, output_dir: str, config: Optional[RegistryConfig] = None):
        if config is None:
            config = RegistryConfig(
                base_url="https://www.pulumi.com/registry/packages/aws/api-docs",
                provider="aws",
                namespace="pulumi"
            )
        super().__init__(output_dir, config)
    
    async def get_service_list(self, session) -> List[str]:
        """Get list of AWS services."""
        try:
            # Get GitHub token using gh CLI
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'Authorization': 'Bearer ' + os.popen('gh auth token').read().strip()
            }
            
            # Use GitHub API to list contents
            api_url = "https://api.github.com/repos/pulumi/pulumi-aws/contents/sdk/python/pulumi_aws"
            async with session.get(api_url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    services = []
                    for item in data:
                        if item['type'] == 'dir':
                            service = item['name']
                            if service and not service.startswith('.') and not service.startswith('_'):
                                services.append(service)
                    
                    print(f"Found {len(services)} Pulumi services", flush=True)
                    return sorted(services)
                elif response.status == 403:
                    print("Rate limited by GitHub. Please authenticate using 'gh auth login'", flush=True)
                    return []
                else:
                    print(f"Failed to fetch Pulumi service list: {response.status}", flush=True)
                    return []
        except Exception as e:
            print(f"Error getting Pulumi service list: {str(e)}", flush=True)
            return []
    
    async def process_service(self, session, service: str, total_services: int, current: int) -> Optional[Dict[str, Any]]:
        """Process a single service."""
        print(f"Processing service {current}/{total_services}: {service}", end="\r", flush=True)
        
        try:
            # Fetch service documentation
            url = f"{self.config.base_url}/{service}/index.html"
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"\nFailed to fetch documentation for {service}: {response.status}")
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract resources
                resources = []
                for resource in soup.find_all('div', class_='resource'):
                    name = resource.find('h3')
                    if name:
                        resources.append(name.text.strip())
                
                # Extract functions
                functions = []
                for function in soup.find_all('div', class_='function'):
                    name = function.find('h3')
                    if name:
                        functions.append(name.text.strip())
                
                return {
                    'service': service,
                    'resources': resources,
                    'functions': functions
                }
                
        except Exception as e:
            print(f"\nError processing {service}: {e}")
            return None

    async def save_service_doc(self, doc: Dict[str, Any]):
        """Save a single service's documentation."""
        if not doc:
            return
            
        service = doc['service']
        output_prefix = os.path.join('pulumi_aws', service)
        
        # Convert to markdown format
        content = f"# {service.upper()}\n\n"
        content += "\n\n"
        
        if doc['resources']:
            content += "## Resources\n\n"
            for resource in doc['resources']:
                content += f"### {resource}\n"
                content += "\n\n"
        
        if doc['functions']:
            content += "## Functions\n\n"
            for function in doc['functions']:
                content += f"### {function}\n"
                content += "\n\n"
        
        # Save as markdown
        self.formatter.save_markdown(output_prefix, service, content)

    async def crawl(self, service: str = None):
        """Crawl Pulumi AWS provider documentation."""
        async with aiohttp.ClientSession() as session:
            # Get list of services
            all_services = await self.get_service_list(session)
            if not all_services:
                print("No services found")
                return
            
            # Filter services if specified
            if service:
                all_services = [s for s in all_services if s == service]
                if not all_services:
                    print(f"Service {service} not found")
                    return
            
            print(f"Found {len(all_services)} service packages")
            
            # Process services concurrently in batches
            batch_size = 5
            for i in range(0, len(all_services), batch_size):
                batch = all_services[i:i + batch_size]
                tasks = []
                for j, service in enumerate(batch, 1):
                    current = i + j
                    task = asyncio.create_task(
                        self.process_service(session, service, len(all_services), current)
                    )
                    tasks.append(task)
                
                # Wait for batch to complete
                batch_results = await asyncio.gather(*tasks)
                for doc in batch_results:
                    if doc:
                        await self.save_service_doc(doc)
            
            # Clear the progress line and print completion message
            print(" " * 100, end="\r")
            print(f"Finished processing all {len(all_services)} services")
