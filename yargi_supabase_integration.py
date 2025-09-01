"""
Yargi MCP Supabase Integration
Save search results and queries to Supabase database
"""
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from supabase_client import supabase_client
import json

class YargiSupabaseIntegration:
    def __init__(self):
        self.client = supabase_client
    
    async def save_search_query(self, 
                               query_text: str,
                               search_type: str,  # 'yargitay', 'danistay', 'bedesten', etc.
                               user_id: Optional[str] = None,
                               metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Save search query to database"""
        try:
            data = {
                'query_text': query_text,
                'search_type': search_type,
                'user_id': user_id,
                'metadata': json.dumps(metadata) if metadata else None,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'status': 'completed'
            }
            
            result = await self.client.insert_data('search_queries', data)
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to save search query"
            }
    
    async def save_search_results(self,
                                 query_id: str,
                                 results: List[Dict[str, Any]],
                                 total_count: int = 0) -> Dict[str, Any]:
        """Save search results to database"""
        try:
            data = {
                'query_id': query_id,
                'results': json.dumps(results),
                'total_count': total_count,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            result = await self.client.insert_data('search_results', data)
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to save search results"
            }
    
    async def save_document_access(self,
                                  document_id: str,
                                  document_type: str,  # 'yargitay', 'danistay', etc.
                                  user_id: Optional[str] = None) -> Dict[str, Any]:
        """Save document access log"""
        try:
            data = {
                'document_id': document_id,
                'document_type': document_type,
                'user_id': user_id,
                'accessed_at': datetime.now(timezone.utc).isoformat()
            }
            
            result = await self.client.insert_data('document_access', data)
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to save document access"
            }
    
    async def get_user_search_history(self, user_id: str, limit: int = 50) -> Dict[str, Any]:
        """Get user's search history"""
        try:
            filters = {'user_id': user_id}
            result = await self.client.query_data('search_queries', filters)
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to get search history"
            }
    
    async def get_popular_searches(self, search_type: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """Get popular search queries"""
        try:
            filters = {}
            if search_type:
                filters['search_type'] = search_type
                
            result = await self.client.query_data('search_queries', filters)
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to get popular searches"
            }
    
    async def create_schema_tables(self) -> Dict[str, Any]:
        """Create necessary tables for Yargi MCP"""
        tables_created = []
        errors = []
        
        # Search queries table
        search_queries_schema = {
            "id": "UUID PRIMARY KEY DEFAULT gen_random_uuid()",
            "query_text": "TEXT NOT NULL",
            "search_type": "TEXT NOT NULL",
            "user_id": "TEXT",
            "metadata": "JSONB",
            "created_at": "TIMESTAMPTZ DEFAULT NOW()",
            "status": "TEXT DEFAULT 'pending'"
        }
        
        result = await self.client.create_table_if_not_exists('search_queries', search_queries_schema)
        if result['success']:
            tables_created.append('search_queries')
        else:
            errors.append(f"search_queries: {result['error']}")
        
        # Search results table
        search_results_schema = {
            "id": "UUID PRIMARY KEY DEFAULT gen_random_uuid()",
            "query_id": "TEXT NOT NULL",
            "results": "JSONB NOT NULL",
            "total_count": "INTEGER DEFAULT 0",
            "created_at": "TIMESTAMPTZ DEFAULT NOW()"
        }
        
        result = await self.client.create_table_if_not_exists('search_results', search_results_schema)
        if result['success']:
            tables_created.append('search_results')
        else:
            errors.append(f"search_results: {result['error']}")
        
        # Document access table
        document_access_schema = {
            "id": "UUID PRIMARY KEY DEFAULT gen_random_uuid()",
            "document_id": "TEXT NOT NULL",
            "document_type": "TEXT NOT NULL",
            "user_id": "TEXT",
            "accessed_at": "TIMESTAMPTZ DEFAULT NOW()"
        }
        
        result = await self.client.create_table_if_not_exists('document_access', document_access_schema)
        if result['success']:
            tables_created.append('document_access')
        else:
            errors.append(f"document_access: {result['error']}")
        
        return {
            "success": len(errors) == 0,
            "tables_created": tables_created,
            "errors": errors,
            "message": f"Created {len(tables_created)} tables, {len(errors)} errors"
        }

# Global instance
yargi_db = YargiSupabaseIntegration()

# Test function
async def test_yargi_integration():
    """Test Yargi Supabase integration"""
    print("Testing Yargi Supabase integration...")
    
    # Test saving a search query
    print("Testing search query save...")
    result = await yargi_db.save_search_query(
        query_text="İş kanunu",
        search_type="yargitay",
        user_id="test_user_123",
        metadata={"source": "api", "version": "2.0"}
    )
    
    if result['success']:
        print(f"Search query saved successfully!")
        print(f"Data: {result.get('data', {})}")
    else:
        print(f"Failed to save search query: {result['error']}")
    
    # Test getting search history
    print("Testing search history retrieval...")
    history_result = await yargi_db.get_user_search_history("test_user_123")
    
    if history_result['success']:
        print(f"Search history retrieved: {len(history_result.get('data', []))} records")
    else:
        print(f"Failed to get search history: {history_result['error']}")

if __name__ == "__main__":
    # Test integration when run directly
    asyncio.run(test_yargi_integration())