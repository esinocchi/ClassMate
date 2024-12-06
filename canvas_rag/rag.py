# rag.py
from typing import Dict, List, Any
from db import CanvasDatabase
from config import API_KEY
import openai
from tenacity import retry, stop_after_attempt, wait_exponential

class CanvasRAG:
    def __init__(self, api_key, model, temperature, max_tokens):
        # Initialize the CanvasDatabase instance
        self.db = CanvasDatabase()
        openai.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def query_llm(self, user_query: str) -> Dict[str, Any]:
        """Process user query using RAG approach"""
        try:
            # Get relevant content from the database based on the user query
            context = self.db.query_content(user_query)
            
            # Format the retrieved context for LLM consumption
            formatted_context = self._format_context_for_llm(context)
            
            # Create a prompt for the LLM using the user query and formatted context
            prompt = self._create_llm_prompt(user_query, formatted_context)
            
            # Get the response from the LLM based on the prompt
            response = self._get_llm_response(prompt)
            
            # Return the LLM's answer along with the sources used
            return {
                'answer': response,
                'sources': context
            }

        except Exception as e:
            # Handle any errors that occur during the query process
            print(f"Error in RAG query: {e}")
            return {
                'answer': "I encountered an error processing your query.",
                'sources': []
            }

    def _format_context_for_llm(self, context: List[Dict[str, Any]]) -> str:
        """Format context for LLM consumption"""
        formatted_parts = []
        
        # Iterate through each item in the context to format it
        for item in context:
            content_type = item['metadata']['type']
            
            # Format assignment information
            if content_type == 'assignment':
                formatted_parts.append(
                    f"Assignment Information:\n"
                    f"Title: {item['details'].get('title', 'Untitled')}\n"
                    f"Due Date: {item['details'].get('due_date', 'Not specified')}\n"
                    f"Description: {item['details'].get('description', 'No description')}\n"
                    f"Points: {item['details'].get('points_possible', 'Not specified')}"
                )
            
            # Format file content
            elif content_type == 'file':
                formatted_parts.append(
                    f"Content from {item['metadata'].get('filename', 'File')}:\n"
                    f"{item['content']}"
                )
            
            # Format course information
            elif content_type == 'course':
                formatted_parts.append(
                    f"Course Information:\n"
                    f"{item['content']}"
                )
            
            # Format announcement details
            elif content_type == 'announcement':
                formatted_parts.append(
                    f"Announcement:\n"
                    f"Title: {item['details'].get('title', 'Untitled')}\n"
                    f"Message: {item['details'].get('message', 'No message')}"
                )
            
            # Format page content
            elif content_type == 'page':
                formatted_parts.append(
                    f"Page Content:\n"
                    f"Title: {item['details'].get('title', 'Untitled')}\n"
                    f"Content: {item['details'].get('body', 'No content')}"
                )
            
            # Format module information
            elif content_type == 'module':
                formatted_parts.append(
                    f"Module Information:\n"
                    f"Name: {item['details'].get('name', 'Untitled')}\n"
                    f"Position: {item['details'].get('position', 'Not specified')}"
                )
        
        # Join all formatted parts into a single string
        return "\n\n".join(formatted_parts)

    def _create_llm_prompt(self, user_query: str, context: str) -> str:
        """Create prompt for LLM"""
        # Construct the prompt for the LLM using the user query and context
        return f"""As a Canvas learning assistant, please help answer the following question based on the course content provided.

Relevant Course Content:
{context}

User Question: {user_query}

Please provide a clear and specific answer based on the above course content. Include any relevant dates, requirements, or important details mentioned in the content.

Answer:"""
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _get_llm_response(self, prompt: str) -> str:
        """Get response from LLM"""
        # Implement your LLM integration here
        try:
            response = openai.ChatCompletion.create(
                model= self.model,  # You can also use "gpt-4-turbo-preview" for the latest version
                messages=[
                    {"role": "system", "content": """You are a knowledgeable Canvas learning assistant. 
                    Your role is to help students by providing accurate information based on 
                    the course content provided. Always base your responses on the given context and 
                    acknowledge if certain information isn't available in the provided content."""},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,  # Lower temperature for more focused responses
                max_tokens=self.max_tokens,  # Adjust based on your needs
                presence_penalty=0.0,
                frequency_penalty=0.0
            )
            
            # Extract the response text
            answer = response.choices[0].message.content.strip()
            
            return answer
            
        except openai.error.RateLimitError:
            raise Exception("Rate limit exceeded. Please try again later")
        except openai.error.AuthenticationError:
            raise Exception("Authentication failed")
        except openai.error.APIError as e:
            raise Exception(f"API error occurred: {str(e)}")
        except Exception as e:
            raise Exception(f"An error occurred while getting LLM response: {str(e)}")

    def close(self):
        """Close database connection"""
        # Close the connection to the database
        self.db.close()

if __name__ == "__main__":
    rag = CanvasRAG(API_KEY, 'gpt-4o-2024-11-20', 0.3, 500)
    
    # Example query
    test_query = "What assignments are due this week?"
    result = rag.query_llm(test_query)
    
    # Print the query and the answer received from the LLM
    print(f"\nQuery: {test_query}")
    print(f"Answer: {result['answer']}")
    print("\nSources used:")
    for source in result['sources']:
        print(f"- {source['metadata']['type']}: {source['content'][:100]}...")
    
    # Close the database connection
    rag.close()