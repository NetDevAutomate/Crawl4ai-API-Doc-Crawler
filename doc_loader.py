import os
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

class APIDocLoader:
    def __init__(self, json_reference_dir: str = "output/json_reference"):
        """Initialize the API documentation loader.
        
        Args:
            json_reference_dir: Directory containing the JSON reference documentation.
                              Each subdirectory represents a different source (e.g., aws, azure, gcp).
        """
        self.json_reference_dir = json_reference_dir
        self.docs_cache: Dict[str, Dict[str, Any]] = {}
        self.embeddings_cache: Dict[str, np.ndarray] = {}
        # Initialize the sentence transformer model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Load all documents into memory
        self.load_all_documents()
    
    def load_all_documents(self):
        """Load all JSON documents from the reference directory."""
        for source_dir in os.listdir(self.json_reference_dir):
            source_path = os.path.join(self.json_reference_dir, source_dir)
            if os.path.isdir(source_path):
                for json_file in os.listdir(source_path):
                    if json_file.endswith('.json'):
                        file_path = os.path.join(source_path, json_file)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            doc = json.load(f)
                            doc_id = f"{source_dir}/{json_file}"
                            self.docs_cache[doc_id] = doc
                            # Create embeddings for the document
                            self.create_embeddings(doc_id, doc)
    
    def create_embeddings(self, doc_id: str, doc: Dict[str, Any]):
        """Create embeddings for document content."""
        # Combine relevant text fields for embedding
        text_content = f"{doc['content']['overview']} "
        for api_ref in doc['content']['api_reference']:
            text_content += f"{api_ref['name']} {api_ref['description']} "
        
        # Generate embedding
        self.embeddings_cache[doc_id] = self.model.encode(text_content)
    
    def semantic_search(self, query: str, top_k: int = 5, source_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search documents using semantic similarity.
        
        Args:
            query: The search query.
            top_k: Number of top results to return.
            source_filter: Optional filter to search only within a specific source (e.g., 'aws', 'azure').
        """
        # Generate query embedding
        query_embedding = self.model.encode(query)
        
        # Calculate similarities
        similarities = []
        for doc_id, doc_embedding in self.embeddings_cache.items():
            # Apply source filter if specified
            if source_filter and not doc_id.startswith(f"{source_filter}/"):
                continue
                
            similarity = cosine_similarity(
                query_embedding.reshape(1, -1),
                doc_embedding.reshape(1, -1)
            )[0][0]
            similarities.append((doc_id, similarity))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Return top k results
        results = []
        for doc_id, similarity in similarities[:top_k]:
            doc = self.docs_cache[doc_id]
            results.append({
                "doc_id": doc_id,
                "similarity": similarity,
                "metadata": doc["metadata"],
                "content": doc["content"]
            })
        
        return results
    
    def get_service_docs(self, service_name: str, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get documentation for a specific service.
        
        Args:
            service_name: Name of the service to get documentation for.
            source: Optional source filter (e.g., 'aws', 'azure').
        """
        results = []
        for doc_id, doc in self.docs_cache.items():
            if service_name.lower() in doc["metadata"]["service"].lower():
                if source is None or source.lower() in doc["metadata"]["source"].lower():
                    results.append({
                        "doc_id": doc_id,
                        "metadata": doc["metadata"],
                        "content": doc["content"]
                    })
        return results
    
    def get_api_examples(self, service_name: str, method_name: Optional[str] = None, source: Optional[str] = None) -> List[Dict[str, str]]:
        """Get code examples for a service/method.
        
        Args:
            service_name: Name of the service.
            method_name: Optional specific method name to filter examples.
            source: Optional source filter (e.g., 'aws', 'azure').
        """
        examples = []
        docs = self.get_service_docs(service_name, source=source)
        
        for doc in docs:
            for example in doc["content"]["examples"]:
                if method_name is None or method_name.lower() in example["code"].lower():
                    examples.append({
                        "service": doc["metadata"]["service"],
                        "source": doc["metadata"]["source"],
                        "code": example["code"],
                        "language": example["language"]
                    })
        
        return examples

def format_for_llm(results: List[Dict[str, Any]]) -> str:
    """Format search results in a way that's optimal for LLM consumption."""
    formatted = "API Documentation:\n\n"
    
    for result in results:
        formatted += f"Service: {result['metadata']['service']}\n"
        formatted += f"Source: {result['metadata']['source']}\n"
        formatted += f"Overview: {result['content']['overview']}\n\n"
        
        if result['content']['api_reference']:
            formatted += "API Reference:\n"
            for api in result['content']['api_reference']:
                formatted += f"- {api['name']}: {api['description']}\n"
            formatted += "\n"
        
        if result['content']['examples']:
            formatted += "Examples:\n"
            for example in result['content']['examples'][:2]:  # Limit to 2 examples
                formatted += f"```{example['language']}\n{example['code']}\n```\n"
            formatted += "\n"
        
        formatted += "---\n\n"
    
    return formatted
