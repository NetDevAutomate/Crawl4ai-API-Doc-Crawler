"""AWS Go SDK v2 documentation crawler."""

import os
import json
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from base import BaseDocCrawler, SDKConfig

class GoSDKCrawler(BaseDocCrawler):
    """Crawler for AWS Go SDK v2 documentation."""

    def __init__(self, output_dir: str, config: Optional[SDKConfig] = None):
        """Initialize the crawler."""
        super().__init__(output_dir, config)
        self.name = "Go SDK"
        self.base_url = "https://github.com/aws/aws-sdk-go-v2"

    def normalize_service_name(self, service: str) -> str:
        """Normalize service name to match Go SDK naming."""
        # Map common service names to Go SDK package names
        service_map = {
            "api-gateway": "apigateway",
            "cloudwatch": "cloudwatch",
            "dynamodb": "dynamodb",
            "ec2": "ec2",
            "ecs": "ecs",
            "eks": "eks",
            "elastic-beanstalk": "elasticbeanstalk",
            "elb": "elasticloadbalancing",
            "iam": "iam",
            "lambda": "lambda",
            "rds": "rds",
            "route53": "route53",
            "s3": "s3",
            "sns": "sns",
            "sqs": "sqs"
        }
        
        service = service.lower()
        return service_map.get(service, service)

    async def _rate_limited_request(self, session, url, headers=None, **kwargs):
        async with session.get(url, headers=headers, **kwargs) as response:
            if response.status != 200:
                print(f"Failed to fetch {url}: {response.status}")
                return None
            return await response.json() if 'json' in response.headers.get('Content-Type', '') else await response.text()
    
    async def get_service_list(self, session) -> List[str]:
        """Get list of AWS services."""
        try:
            print("\nFetching Go SDK service list...", flush=True)
            
            # Use GitHub API to list contents of service directory
            api_url = "https://api.github.com/repos/aws/aws-sdk-go-v2/contents/service"
            data = await self._rate_limited_request(session, api_url)
            
            if not data:
                print("Failed to fetch Go SDK service list", flush=True)
                return []
                
            services = []
            for item in data:
                if item['type'] == 'dir':
                    service = item['name']
                    if service and not service.startswith('.'):
                        services.append(service)
            
            print(f"Found {len(services)} Go SDK service packages", flush=True)
            return sorted(services)
            
        except Exception as e:
            print(f"Error getting Go SDK service list: {str(e)}", flush=True)
            return []

    async def process_service(self, session, service: str, total_services: int, current: int) -> Optional[Dict[str, Any]]:
        """Process a single service's documentation."""
        print(f"\nProcessing Go SDK service {current}/{total_services}: {service}", flush=True)
        
        try:
            # List contents of service directory
            api_url = f"https://api.github.com/repos/aws/aws-sdk-go-v2/contents/service/{service}"
            content = await self._rate_limited_request(session, api_url)
            
            if not content:
                print(f"Failed to list files for service: {service}", flush=True)
                return None

            # Find API operation files
            api_files = [item for item in content 
                        if item['type'] == 'file' and 
                           item['name'].startswith('api_op_') and 
                           item['name'].endswith('.go')]
            
            if not api_files:
                print(f"No API operation files found for service: {service}", flush=True)
                return None

            operations = []
            for api_file in api_files:
                # Get file content
                content = await self._rate_limited_request(session, api_file['download_url'])
                if content:
                    # Parse operations
                    for line in content.split('\n'):
                        if "func (c *Client)" in line:
                            op = line.split("func (c *Client)")[1].split("(")[0].strip()
                            if op:
                                operations.append(op)

            result = {
                'service': service,
                'operations': operations
            }

            print(f"Found {len(operations)} operations for service: {service}", flush=True)
            return result

        except Exception as e:
            print(f"Error processing Go SDK service {service}: {str(e)}", flush=True)
            return None

    async def save_service_doc(self, doc: Dict[str, Any]):
        """Save a single service's documentation."""
        title = doc.get('service', '')
        if not title:
            return
        
        # Save as markdown
        markdown_content = f"# {title}\n\n"
        markdown_content += f"Source: {self.base_url}/{title}\n\n"
        markdown_content += "## Overview\n\n"
        markdown_content += "## Operations\n\n"
        for operation in doc.get('operations', []):
            markdown_content += f"### {operation}\n\n"
        
        output_prefix = f"gosdk_{self.config.provider}"
        self.formatter.save_markdown(output_prefix, title, markdown_content)
        
        # Save as JSON
        doc_structure = {
            'title': title,
            'url': self.config.base_url + '/' + title,
            'operations': doc.get('operations', [])
        }
        self.formatter.save_json(output_prefix, title, doc_structure)

    async def _crawl(self, service: str = None):
        """Crawl Go SDK documentation."""
        print("\n=== Starting Go SDK Crawler ===", flush=True)
        
        try:
            async with aiohttp.ClientSession() as session:
                # Get list of services
                services = await self.get_service_list(session)
                if not services:
                    print("No Go SDK services found", flush=True)
                    return

                # Filter services if specified
                if service:
                    services = [s for s in services if service.lower() in s.lower()]
                    if not services:
                        print(f"No matching Go SDK services found for: {service}", flush=True)
                        return

                # Process each service
                processed_services = []
                for i, svc in enumerate(services, 1):
                    result = await self.process_service(session, svc, len(services), i)
                    if result:
                        processed_services.append(result)

                print(f"\nProcessed {len(processed_services)} Go SDK services", flush=True)

        except Exception as e:
            print(f"Error in Go SDK crawler: {str(e)}", flush=True)
            if self.debug:
                import traceback
                traceback.print_exc()
