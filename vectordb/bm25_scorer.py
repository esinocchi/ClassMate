"""BM25 scoring for Canvas educational content."""

import math
import re
from collections import defaultdict
from typing import Dict, List

class CanvasBM25:
    """BM25 scorer optimized for Canvas documents.
    
    This class implements the BM25 ranking algorithm specifically tailored for
    Canvas educational content, with optimizations for academic document types
    and course-specific terminology.
    
    Attributes:
        documents: List of documents to index and search.
        k1: Term frequency saturation parameter (default 1.5).
        b: Document length normalization parameter (default 0.75).
        doc_freqs: Dictionary mapping terms to their document frequencies.
        avg_doc_length: Average document length across the collection.
    """
    
    def __init__(self, documents: List[Dict], k1: float = 1.5, b: float = 0.75):
        """Initialize the BM25 scorer with documents and parameters.
        
        Args:
            documents: List of document dictionaries to index.
            k1: Term frequency saturation parameter. Higher values give more
                weight to term frequency. Typical range: 1.2-2.0.
            b: Document length normalization parameter. 0 = no normalization,
                1 = full normalization. Typical range: 0.75.
        """
        self.documents = documents
        self.k1 = k1
        self.b = b
        self.doc_frequency = defaultdict(int)
        self.avg_doc_length = 0
        self._precompute()
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text while preserving academic course codes.
        
        Args:
            text: Input text string to tokenize from a document
            
        Returns:
            List of tokens, filtered to remove short words except for
            academic course codes (e.g., CS101, MATH203).
        """
        if not text:
            return []
        
        # Remove punctuation and convert to lowercase
        text = re.sub(r'[^\w\s\-]', ' ', text.lower())
        tokens = text.split()
        
        # Keep academic terms (CS101) and longer words
        return list(filter(lambda token: len(token) > 2 or re.match(r'^[a-z]+\d+$', token), tokens))
    
    def _get_text(self, doc: Dict) -> str:
        """Extract and weight text content from a document.
        
        Different document types have different field weights to emphasize
        important content (e.g., titles are weighted higher than descriptions).
        
        Args:
            doc: Document dictionary containing type and content fields.
            
        Returns:
            Concatenated text string with weighted field repetitions.
        """
        doc_type = doc.get('type', 'file')
        
        # Field weights by importance
        weights = {
            'assignment': {'name': 3, 'description': 1},
            'file': {'display_name': 3, 'filename': 2},
            'quiz': {'title': 3, 'description': 1},
            'announcement': {'title': 3, 'message': 1},
            'calendar_event': {'title': 3, 'description': 1}
        }.get(doc_type, {'title': 2, 'content': 1})
        
        parts = []
        for field, weight in weights.items():
            if field in doc and doc[field]:
                parts.extend([str(doc[field])] * weight)
        
        return ' '.join(parts)
    
    def _precompute(self):
        """Precompute document collection statistics for BM25 scoring.
        
        Calculates document frequencies for all terms and average document
        length, which are required for efficient BM25 score computation.
        This method is called automatically during initialization.
        """
        total_length = 0
        documents_with_term = defaultdict(set)
        
        for doc in self.documents:
            terms = self._tokenize(self._get_text(doc))
            total_length += len(terms)
            
            for term in set(terms):
                documents_with_term[term].add(str(doc.get('id')))
        
        self.avg_doc_length = total_length / len(self.documents) if self.documents else 0
        
        for term, docs in documents_with_term.items():
            self.doc_frequency[term] = len(docs)
    
    def score(self, doc: Dict, keywords: List[str]) -> float:
        """Calculate BM25 relevance score for a document given query terms.
        
        Args:
            doc: Document dictionary to score.
            keywords: List of keywords to match against.
            
        Returns:
            BM25 relevance score. Higher scores indicate better matches.
            Returns 0.0 for empty documents or no term matches.
        """
        doc_text = self._get_text(doc)
        doc_terms = self._tokenize(doc_text)
        doc_length = len(doc_terms)
        
        if doc_length == 0:
            return 0.0
        
        # Count term frequencies
        term_frequency = defaultdict(int)
        for term in doc_terms:
            term_frequency[term] += 1
        
        score = 0.0
        for term in keywords:
            term = term.lower()
            term_frequency_in_doc = term_frequency.get(term, 0)
            
            if term_frequency_in_doc > 0:
                documents_containing_term = self.doc_frequency.get(term, 0)
                if documents_containing_term > 0:
                    score += self._calculate_bm25_score(term_frequency_in_doc, documents_containing_term, doc_length)
        
        return score
    
    def _calculate_bm25_score(self, term_frequency_in_doc: int, documents_containing_term: int, doc_length: int) -> float:
        """
        Calculate BM25 score for a term in a document.
        BM25 information found here: https://en.wikipedia.org/wiki/Okapi_BM25
        
        Args:
            term_frequency_in_doc: Frequency of the term in the document.
            documents_containing_term: Number of documents containing the term.
            doc_length: Length of the document.
        
        Returns:
            BM25 score for the term in the document.
        """
        inverse_document_frequency = math.log((len(self.documents) - documents_containing_term + 0.5) / (documents_containing_term + 0.5))
        length_norm = (1 - self.b) + self.b * (doc_length / self.avg_doc_length)
        return max(inverse_document_frequency, 0) * (term_frequency_in_doc * (self.k1 + 1)) / (term_frequency_in_doc + self.k1 * length_norm)
    
    def search(self, query: str, docs: List[Dict] = None, limit: int = 10) -> List[Dict]:
        """Search documents using BM25 scoring and return ranked results.
        
        Args:
            query: Search query string.
            docs: Optional list of documents to search. If None, searches
                all documents in the collection.
            limit: Maximum number of results to return.
            
        Returns:
            List of result dictionaries sorted by relevance score, each containing:
                - 'document': The original document dictionary
                - 'similarity': BM25 relevance score
                - 'type': String identifier 'bm25'
        """
        docs = docs or self.documents
        terms = self._tokenize(query)
        
        if not terms:
            return []
        
        results = []
        for doc in docs:
            score = self.score(doc, terms)
            if score > 0:
                results.append({'document': doc, 'similarity': score, 'type': 'bm25'})
        
        return sorted(results, key=lambda x: x['similarity'], reverse=True)[:limit]


def fuse_results(semantic_results: List[Dict], bm25_results: List[Dict], 
                 alpha: float = 0.7) -> List[Dict]:
    """
    Combine semantic and BM25 search results using weighted score fusion.
    
    Normalizes scores from both result sets and combines them using a weighted
    average to produce hybrid search results that leverage both semantic
    understanding and keyword matching.
    
    Args:
        semantic_results: List of semantic search result dictionaries.
        bm25_results: List of BM25 search result dictionaries.
        alpha: Weight for semantic results (0.0-1.0). BM25 results get
            weight (1-alpha). Default 0.7 favors semantic results.
            
    Returns:
        List of fused result dictionaries sorted by combined relevance score,
        each containing:
            - 'document': The original document dictionary
            - 'similarity': Combined relevance score
            - 'type': String identifier 'hybrid'
    """
    # Normalize scores
    def normalize(results):
        if not results:
            return results
        max_score = max(r['similarity'] for r in results)
        if max_score > 0:
            for r in results:
                r['similarity'] /= max_score
        return results
    
    semantic_results = normalize(semantic_results.copy())
    bm25_results = normalize(bm25_results.copy())
    
    # Combine scores
    doc_scores = {}
    
    for result in semantic_results:
        doc_id = str(result['document']['id'])
        doc_scores[doc_id] = {
            'document': result['document'],
            'score': alpha * result['similarity']
        }
    
    for result in bm25_results:
        doc_id = str(result['document']['id'])
        if doc_id in doc_scores:
            doc_scores[doc_id]['score'] += (1 - alpha) * result['similarity']
        else:
            doc_scores[doc_id] = {
                'document': result['document'],
                'score': (1 - alpha) * result['similarity']
            }
    
    return sorted([
        {'document': data['document'], 'similarity': data['score'], 'type': 'hybrid'}
        for data in doc_scores.values()
    ], key=lambda x: x['similarity'], reverse=True)