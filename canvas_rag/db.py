import boto3
import os
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from typing import List, Dict, Any
import openai
import backoff

class VectorDBHandler:
    def __init__(self):
        self.opensearch_host = os.getenv('OPENSEARCH_HOST')
        self.aws_region = os.getenv('AWS_REGION', 'us-west-2')
        self.service = 'es'
        self.credentials = boto3.Session().get_credentials()
        self.awsauth = AWS4Auth(
            self.credentials.access_key,
            self.credentials.secret_key,
            self.aws_region,
            self.service,
            session_token=self.credentials.token
        )
        
        self.client = OpenSearch(
            hosts=[{'host': self.opensearch_host, 'port': 443}],
            http_auth=self.awsauth,
            use_ssl=True,
            connection_class=RequestsHttpConnection,
            timeout=30
        )
        
        self.index_name = "canvasai-vectors"
        self._create_index_if_not_exists()
    
    def _create_index_if_not_exists(self):
        if not self.client.indices.exists(index=self.index_name):
            body = {
                "settings": {
                    "index.knn": True,
                    "number_of_shards": 3,
                    "number_of_replicas": 1
                },
                "mappings": {
                    "properties": {
                        "vector": {
                            "type": "knn_vector",
                            "dimension": 1536,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib"
                            }
                        },
                        "metadata": {
                            "type": "object",
                            "enabled": True
                        }
                    }
                }
            }
            self.client.indices.create(index=self.index_name, body=body)

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def insert_document(self, doc_id: str, text: str, metadata: Dict[str, Any]):
        embedding = self._get_embedding(text)
        document = {
            "vector": embedding,
            "metadata": metadata,
            "text": text
        }
        self.client.index(
            index=self.index_name,
            id=doc_id,
            body=document,
            refresh=True
        )
    
    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    def search(self, query: str, k: int = 5) -> List[Dict]:
        query_embedding = self._get_embedding(query)
        body = {
            "size": k,
            "query": {
                "knn": {
                    "vector": {
                        "vector": query_embedding,
                        "k": k
                    }
                }
            }
        }
        response = self.client.search(
            index=self.index_name,
            body=body
        )
        return [hit["_source"] for hit in response["hits"]["hits"]]
    
    def _get_embedding(self, text: str) -> List[float]:
        response = openai.Embedding.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response["data"][0]["embedding"]

class S3Manager:
    def __init__(self):
        self.s3 = boto3.client('s3')
        self.bucket_name = 'canvasai-users'
    
    def upload_file(self, user_id: str, course_id: str, file_data: bytes, filename: str) -> str:
        s3_key = f"{user_id}/courses/{course_id}/{filename}"
        self.s3.put_object(
            Bucket=self.bucket_name,
            Key=s3_key,
            Body=file_data
        )
        return f"s3://{self.bucket_name}/{s3_key}"