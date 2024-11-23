from typing import Dict, List, Any
from db import CanvasDatabase

class CanvasRAG:
    def __init__(self):
        self.db = CanvasDatabase()

    def query_llm(self, user_query: str) -> Dict[str, Any]:
        """Process user query using RAG approach"""
        try:
            # Get relevant content from database
            context = self.db.query_content(user_query)
            
            # Format context for LLM
            formatted_context = self._format_context_for_llm(context)
            
            # Create prompt
            prompt = self._create_llm_prompt(user_query, formatted_context)
            
            # Get LLM response
            response = self._get_llm_response(prompt)
            
            return {
                'answer': response,
                'sources': context
            }

        except Exception as e:
            print(f"Error in RAG query: {e}")
            return {
                'answer': "I encountered an error processing your query.",
                'sources': []
            }

    def _format_context_for_llm(self, context: List[Dict[str, Any]]) -> str:
        """Format context for LLM consumption"""
        formatted_parts = []
        
        for item in context:
            content_type = item['metadata']['type']
            
            if content_type == 'assignment':
                formatted_parts.append(
                    f"Assignment Information:\n"
                    f"Title: {item['details'].get('title', 'Untitled')}\n"
                    f"Due Date: {item['details'].get('due_date', 'Not specified')}\n"
                    f"Description: {item['details'].get('description', 'No description')}\n"
                    f"Points: {item['details'].get('points_possible', 'Not specified')}"
                )
            
            elif content_type == 'file':
                formatted_parts.append(
                    f"Content from {item['metadata'].get('filename', 'File')}:\n"
                    f"{item['content']}"
                )
            
            elif content_type == 'course':
                formatted_parts.append(
                    f"Course Information:\n"
                    f"{item['content']}"
                )
            
            # Add more content types as needed...
        
        return "\n\n".join(formatted_parts)

    def _create_llm_prompt(self, user_query: str, context: str) -> str:
        """Create prompt for LLM"""
        return f"""As a Canvas learning assistant, please help answer the following question based on the course content provided.

Relevant Course Content:
{context}

User Question: {user_query}

Please provide a clear and specific answer based on the above course content. Include any relevant dates, requirements, or important details mentioned in the content.

Answer:"""

    def _get_llm_response(self, prompt: str) -> str:
        """Get response from Llama (implement this)"""
        # Implement your Llama integration here
        # This is where you'll add your Llama code
        pass

    def close(self):
        """Close database connection"""
        self.db.close()

if __name__ == "__main__":
    rag = CanvasRAG()
    
    # Example: Query about an assignment
    response = rag.query_llm("When is the Python assignment due and what are the requirements?")
    
    print("Answer:", response['answer'])
    print("\nSources used:")
    for source in response['sources']:
        print(f"- {source['metadata']['type']}: {source['content'][:100]}...")
    
    rag.close()

if __name__ == "__main__":
    # Test the RAG system
    rag = CanvasRAG()
    
    # Example query
    test_query = "When is my Python assignment due?"
    result = rag.query_llm(test_query)
    
    print(f"\nQuery: {test_query}")
    print(f"Answer: {result['answer']}")
    print("\nSources used:")
    for source in result['sources']:
        print(f"- {source['metadata']['type']}: {source['content'][:100]}...")
    
    rag.close()