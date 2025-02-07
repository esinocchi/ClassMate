from typing import List, Dict, Any
import openai
import backoff
from db import VectorDBHandler, S3Manager

class CanvasRAG:
    def __init__(self, vector_db: VectorDBHandler, s3_manager: S3Manager):
        self.vector_db = vector_db
        self.s3_manager = s3_manager
        self.llm_model = "gpt-4-turbo-preview"
        self.embedding_model = "text-embedding-3-small"
        self.max_context_length = 4000  # tokens

    def process_upload(self, user_id: str, course_id: str, file_data: bytes, filename: str):
        # Store in S3
        s3_uri = self.s3_manager.upload_file(user_id, course_id, file_data, filename)
        
        # Extract text
        text = self._extract_text(file_data, filename)
        
        # Store in vector DB
        doc_id = f"{user_id}_{course_id}_{filename}"
        metadata = {
            "user_id": user_id,
            "course_id": course_id,
            "s3_uri": s3_uri,
            "filename": filename
        }
        self.vector_db.insert_document(doc_id, text, metadata)
        return doc_id

    def query(self, user_id: str, question: str, k: int = 5) -> str:
        # Vector search
        results = self.vector_db.search(question, k=k)
        
        # Build context
        context = self._build_context(results)
        
        # Generate answer
        return self._generate_answer(question, context)

    @backoff.on_exception(backoff.expo, openai.APIError, max_tries=3)
    def _generate_answer(self, question: str, context: str) -> str:
        messages = [
            {
                "role": "system",
                "content": f"""Answer questions about course materials using only the provided context.
                Context: {context}"""
            },
            {"role": "user", "content": question}
        ]
        
        response = openai.ChatCompletion.create(
            model=self.llm_model,
            messages=messages,
            temperature=0.3,
            max_tokens=500
        )
        return response.choices[0].message.content

    def _extract_text(self, file_data: bytes, filename: str) -> str:
        if filename.endswith('.pdf'):
            from pypdf import PdfReader
            pdf = PdfReader(io.BytesIO(file_data))
            return "\n".join([page.extract_text() for page in pdf.pages])
        
        elif filename.endswith('.docx'):
            from docx import Document
            doc = Document(io.BytesIO(file_data))
            return "\n".join([para.text for para in doc.paragraphs])
        
        raise ValueError("Unsupported file format")

    def _build_context(self, results: List[Dict]) -> str:
        context = []
        current_length = 0
        
        for doc in results:
            doc_text = f"From {doc['metadata']['filename']}:\n{doc['text']}"
            if current_length + len(doc_text) > self.max_context_length:
                break
            context.append(doc_text)
            current_length += len(doc_text)
        
        return "\n\n".join(context)

    # Enable batch embedding for cost savings
    def batch_embed_documents(self, texts: List[str]) -> List[List[float]]:
        response = openai.Embedding.create(
            input=texts,
            model=self.embedding_model
        )
        return [item["embedding"] for item in response["data"]]