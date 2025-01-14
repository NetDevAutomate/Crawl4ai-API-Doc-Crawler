from doc_loader import APIDocLoader

def main():
    # Initialize the document loader
    doc_loader = APIDocLoader()
    
    # Example 1: Semantic search for S3 bucket creation (AWS specific)
    print("Searching for S3 bucket creation in AWS docs...")
    results = doc_loader.semantic_search("how to create an S3 bucket", top_k=2, source_filter="aws")
    formatted_results = doc_loader.format_for_llm(results)
    print("\nFormatted results for LLM:")
    print(formatted_results)
    
    # Example 2: Get specific service documentation from a specific source
    print("\nGetting Lambda documentation from Pulumi AWS...")
    lambda_docs = doc_loader.get_service_docs("lambda", source="pulumi_aws")
    formatted_lambda = doc_loader.format_for_llm(lambda_docs)
    print(formatted_lambda)
    
    # Example 3: Get code examples from a specific source
    print("\nGetting S3 bucket examples from AWS sources...")
    examples = doc_loader.get_api_examples("s3", method_name="create_bucket", source="aws")
    for example in examples:
        print(f"\nSource: {example['source']}")
        print(f"Language: {example['language']}")
        print("Code:")
        print(example['code'])

if __name__ == "__main__":
    main()
