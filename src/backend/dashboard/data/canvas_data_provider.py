import asyncio
from typing import List, Dict, Any
from src.database.vectordb.db import VectorDatabase


class CanvasDataProvider:
    """Abstracts vector database operations for dashboard use."""
    
    def __init__(self, vector_db: VectorDatabase):
        self.vector_db = vector_db
    
    async def get_assignments_due_today(self) -> List[Dict[str, Any]]:
        """Get assignments due today."""
        return await self.vector_db.filter_search({
            "item_types": ["assignment"],
            "time_range": "NEAR_FUTURE",
            "query": ""
        })
    
    async def get_upcoming_deadlines(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get upcoming deadlines."""
        return await self.vector_db.filter_search({
            "item_types": ["assignment", "quiz"],
            "time_range": "FUTURE", 
            "query": ""
        })
    
    async def get_course_materials(self, course_id: str) -> List[Dict[str, Any]]:
        """Get materials for a specific course."""
        return await self.vector_db.filter_search({
            "course_id": course_id,
            "item_types": ["file", "announcement"],
            "query": ""
        })