#!/usr/bin/env python3

"""Query interface for crawled AWS API documentation using LLM."""

import os
import json
import glob
import argparse
from typing import List, Dict, Any
import openai
from rich.console import Console
from rich.markdown import Markdown

console = Console()

class DocQuery:
    def __init__(self, api_key: str, output_dir: str = "output"):
        """Initialize the documentation query interface.
        
        Args:
            api_key: OpenAI API key
            output_dir: Directory containing crawled documentation
        """
        self.output_dir = output_dir
        openai.api_key = api_key
        self.docs_cache: Dict[str, List[Dict[str, Any]]] = {}
        
    def load_documentation(self, source: str) -> List[Dict[str, Any]]:
        """Load documentation for a specific source.
        
        Args:
            source: Source name (e.g., 'boto3', 'cloudformation')
            
        Returns:
            List of documentation entries
        """
        if source in self.docs_cache:
            return self.docs_cache[source]
            
        docs = []
        source_dir = os.path.join(self.output_dir, source)
        
        if not os.path.exists(source_dir):
            console.print(f"[yellow]Warning: No documentation found for {source}[/yellow]")
            return []
            
        # Load all JSON files in the source directory
        for json_file in glob.glob(os.path.join(source_dir, "*.json")):
            try:
                with open(json_file, 'r') as f:
                    doc = json.load(f)
                    docs.append(doc)
            except Exception as e:
                console.print(f"[red]Error loading {json_file}: {str(e)}[/red]")
                
        self.docs_cache[source] = docs
        return docs
        
    def create_context(self, query: str, source: str) -> str:
        """Create context for the query from loaded documentation.
        
        Args:
            query: User's query
            source: Documentation source to search in
            
        Returns:
            Relevant context as a string
        """
        docs = self.load_documentation(source)
        
        # Simple keyword matching for now
        # Could be enhanced with embeddings and vector search
        query_terms = query.lower().split()
        relevant_docs = []
        
        for doc in docs:
            content = doc.get('content', '').lower()
            if any(term in content for term in query_terms):
                relevant_docs.append(doc)
                
        # Combine relevant documentation into context
        context = "\n\n".join(
            f"From {doc.get('url', 'unknown')}:\n{doc.get('content', '')}"
            for doc in relevant_docs[:3]  # Limit to top 3 most relevant docs
        )
        
        return context if context else "No relevant documentation found."
        
    async def query(self, query: str, source: str = "all") -> str:
        """Query the documentation using LLM.
        
        Args:
            query: User's question
            source: Documentation source to search in
            
        Returns:
            LLM response
        """
        # If source is 'all', search in all available sources
        if source == "all":
            sources = [d for d in os.listdir(self.output_dir) 
                      if os.path.isdir(os.path.join(self.output_dir, d))]
        else:
            sources = [source]
            
        # Gather context from all relevant sources
        all_context = []
        for src in sources:
            context = self.create_context(query, src)
            if context != "No relevant documentation found.":
                all_context.append(f"=== {src.upper()} Documentation ===\n{context}")
                
        if not all_context:
            return "No relevant documentation found for your query."
            
        # Combine context and create prompt
        combined_context = "\n\n".join(all_context)
        prompt = f"""Based on the following AWS documentation, please answer the question.
        If the answer cannot be found in the documentation, say so.
        
        Documentation:
        {combined_context}
        
        Question: {query}
        
        Answer:"""
        
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful AWS documentation assistant. Provide clear, accurate answers based on the documentation provided."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Lower temperature for more focused responses
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error querying LLM: {str(e)}"

def main():
    """Main entry point for the documentation query interface."""
    parser = argparse.ArgumentParser(
        description='Query AWS API documentation using LLM'
    )
    
    parser.add_argument(
        'query',
        help='Your question about AWS services'
    )
    
    parser.add_argument(
        '--source',
        default='all',
        help='Documentation source to search (boto3, cloudformation, etc.)'
    )
    
    parser.add_argument(
        '--output-dir',
        default='output',
        help='Directory containing crawled documentation'
    )
    
    args = parser.parse_args()
    
    # Get API key from environment
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        console.print("[red]Error: OPENAI_API_KEY environment variable not set[/red]")
        return
        
    # Initialize query interface
    querier = DocQuery(api_key, args.output_dir)
    
    # Run query
    import asyncio
    response = asyncio.run(querier.query(args.query, args.source))
    
    # Print response
    console.print("\n[bold blue]Answer:[/bold blue]")
    console.print(Markdown(response))

if __name__ == "__main__":
    main()
