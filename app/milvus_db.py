from pymilvus import MilvusClient, DataType
from sentence_transformers import SentenceTransformer
from transformers import AutoConfig
import config as config
import logging
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import requests
logger = logging.getLogger(__name__)


class Milvus:
    """
    Milvus vector database client with integrated embedding model.
    All methods access client and model via instance properties.
    """
    
    def __init__(self):
        self.host = config.VECTOR_DB["HOST"]
        self.token = config.VECTOR_DB["TOKEN"]
        self.client = MilvusClient(self.host, token=self.token)
        self.model: Optional[SentenceTransformer] = None
        #self.token_limit: Optional[int] = None
        self.db_name: str = config.VECTOR_DB["DB_NAME"]
        self.collection_name: str = config.VECTOR_DB["COLLECTION_NAME"]
        self.env: str = config.ENV
        self.embedding_dim: int = config.EMBEDDING["EMBEDDING_DIM"]
        self.embedding_api = f"http://{config.EMBEDDING['HOST']}:{config.EMBEDDING['PORT']}/v1"
        logger.info(f"MilvusClient initialized: host={self.host}, db={self.db_name}, collection={self.collection_name}")
    
    @property
    def is_connected(self) -> bool:
        """Check if Milvus connection is active"""
        return hasattr(self.client, 'is_connected') and self.client.is_connected()
    
    def setup_connection(self) -> 'MilvusClient':
        """
        Set up Milvus database connection.
        Creates database if it doesn't exist.
        Returns self for method chaining.
        """
        if not self.is_connected:
            try:
                if not self.db_name in self.client.list_databases():
                    self.client.create_database(db_name=self.db_name)
                    logger.info(f"New vector DB created: {self.db_name}")
                self.client.use_database(db_name=self.db_name)
            except Exception as e:
                logger.error(f"Failed to setup Milvus connection: {e}")
                raise
        
        return self
    
    
    def setup_collection(self) -> 'MilvusClient':
        """
        Create or initialize Milvus collection with schema and indexes.
        Drops collection in dev environment.
        Returns self for method chaining.
        """
        schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=True)
        schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=500, default_value="")
        schema.add_field(field_name="title_embedding", datatype=DataType.FLOAT_VECTOR, dim=self.embedding_dim)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=2000, default_value="")
        schema.add_field(field_name="content_embedding", datatype=DataType.FLOAT_VECTOR, dim=self.embedding_dim)
        schema.add_field(field_name="inserted_at", datatype=DataType.TIMESTAMPTZ,nullable=True)
        
        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="content_embedding",
            metric_type="COSINE",
            index_type="IVF_FLAT",
            params={"nlist": 128}
        )
        index_params.add_index(
            field_name="title_embedding",
            metric_type="COSINE",
            index_type="IVF_FLAT",
            params={"nlist": 128}
        )
        
        # Recreate collection in dev environment
        if self.env == "dev":
            try:
                self.client.drop_collection(collection_name=self.collection_name)
                logger.info(f"Collection dropped in dev mode: {self.collection_name}")
            except Exception as e:
                logger.warning(f"Failed to drop collection (may not exist): {e}")
        
        if not self.client.has_collection(collection_name=self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                dimension=self.embedding_dim,
                schema=schema,
                index_params=index_params
            )
            logger.info(f"Collection created: {self.collection_name}")
        
        return self
    
    def get_schema(self) -> Dict[str, Any]:
        """Return the current collection schema"""
        if self.client.has_collection(collection_name=self.collection_name):
            return self.client.describe_collection(collection_name=self.collection_name)
        return None
    def embedding_request(self, data:List) -> List:
        """Post request to convert list of text to embeddings"""
        try:
            response = requests.post(self.embedding_api,json={"payload":data})
            if response:
                return response.json()
        except requests.exceptions.HTTPError as e:
            return {
                "status_code": 500,
                "message": str(e)  
            }
        
    def insert(self, data: List[Dict[str, Any]], enable_dynamic: bool = True) -> int:
        """
        Insert records into the collection.
        
        Args:
            data: List of dictionaries with keys: title, content, title_embedding, content_embedding
            enable_dynamic: Allow dynamic fields
        
        Returns:
            Number of inserted records
        """
        if not self.client.has_collection(collection_name=self.collection_name):
            logger.error(f"Collection not found: {self.collection_name}")
            return 0
        
        # Extract embeddings from data
        records = []
        for record in data:
            title = record.get("title", "")
            content = record.get("content", "")
            # convert chunk and paper title to embeddings.
            response = self.embedding_request([title,content])
            
            if response["status_code"] == 200:
                title_embedding,content_embedding = response["embeddings"]
                records.append({
                    "title": title, 
                    "content": content,
                    "title_embedding": title_embedding, 
                    "content_embedding": content_embedding,
                    "inserted_at":str(datetime.datetime.today())
                })
            
            # Insert using MilvusClient insert method
            result = self.client.insert(
                collection_name=self.collection_name,
                data=records,
                enable_dynamic_field=enable_dynamic
            )
            self.client.flush(collection_name=self.collection_name)
    
            logger.info(f"Inserted {len(records)} records into {self.collection_name}")
            return len(records)
            
        logger.error(f"{Path(__file__).stem}: embedding request failed {response['message']}")
        return 0
# it uses filttering to get the results not embedding
    def query(
        self,
        limit: int = 10,
        offset: int = 0,
        output_fields: Optional[List[str]] = None,
        filter_: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query records from the collection.
        
        Args:
            limit: Maximum number of results
            offset: Number of records to skip
            output_fields: Fields to return (if None, returns all)
            filter_: Filter expression (e.g., "title == 'test'")
        
        Returns:
            List of matching records
        """
        output_fields = output_fields or ["id", "title", "content"]
        
        search_results = self.client.query(
            collection_name=self.collection_name,
            output_fields=output_fields,
            limit=limit,
            offset=offset,
            filter=filter_
        )
        
        return search_results
# it retrive similar embedding that are closer to the query embedding.
    def search(
        self,
        query: str,
        limit: int = 10,
        output_fields: Optional[List[str]] = None,
        filter_: Optional[str] = None,
        search_field: str = "content_embedding"
    ) -> List[Dict[str, Any]]:
        """
        Search using vector similarity.
        
        Args:
            query: User Query
            limit: Maximum number of results
            output_fields: Fields to return
            filter_: Filter expression
            search_field: Field to search against
        
        Returns:
            List of results with distance scores
        """
        response = self.embedding_request([query])
        output_fields = output_fields or ["title", "content","distance"]
        
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 128},
        }
        results = []
        if response["status_code"] == 200:
            query_vector = response["embeddings"]
            search_results = self.client.search(
                collection_name=self.collection_name,
                data=query_vector,
                anns_field=search_field,
                limit=limit,
                output_fields=output_fields,
                filter=filter_,
                search_params=search_params
            )
            
            # Format results with distances
            
            for i, result in enumerate(search_results[0] if search_results else []):
                # dynamic output to adapt to output_fields.
                results.append({k:result.get(k) for k in output_fields})
        else:
            logger.error(f"{Path(__file__).stem}: embedding request failed {response['message']}")
        return results
            
    
    def delete(self, ids: Optional[List[int]] = None, filter_: Optional[str] = None) -> int:
        """
        Delete records from the collection.
        
        Args:
            ids: List of record IDs to delete
            filter_: Filter expression
        
        Returns:
            Number of deleted records
        """
        if ids:
            deleted = self.client.delete(
                collection_name=self.collection_name,
                ids=ids
            )
        elif filter_:
            deleted = self.client.delete(
                collection_name=self.collection_name,
                filter=filter_
            )
        else:
            return 0
        
        logger.info(f"Deleted {deleted} records from {self.collection_name}")
        return deleted
    
    def update(
        self,
        ids: List[int],
        updates: Dict[str, Any],
        filter_: Optional[str] = None
    ) -> int:
        """
        Update records in the collection.
        
        Args:
            ids: List of record IDs to update
            updates: Dictionary of fields and values to update
            filter_: Filter expression
        
        Returns:
            Number of updated records
        """
        if ids:
            pass
        elif filter_:
            pass
        # Note: Milvus doesn't support direct updates, need to delete and re-insert using upsert
        # For now, return 0 - implement when needed in future.
        return 0
    
    def drop_collection(self) -> None:
        """Drop the collection"""
        try:
            self.client.drop_collection(collection_name=self.collection_name)
            logger.info(f"Collection dropped: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to drop collection: {e}")
    
    def drop_database(self) -> None:
        """Drop the database"""
        try:
            self.client.drop_database(db_name=self.db_name)
            logger.info(f"Database dropped: {self.db_name}")
        except Exception as e:
            logger.error(f"Failed to drop database: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        if not self.client.has_collection(collection_name=self.collection_name):
            return {"exists": False, "count": 0}
            
        stats = self.client.describe_collection(collection_name=self.collection_name)
        row_count = self.client.get_collection_stats(collection_name=self.collection_name)
        
        return {
            "exists": True,
            "count": row_count.get("row_count", 0),
            "dimension": self.embedding_dim,
            "num_partitions": stats.get("num_partitions", 0),
        }
    
    def __repr__(self) -> str:
        return (
            f"MilvusClient(db='{self.db_name}', "
            f"collection='{self.collection_name}', "
            f"connected={self.is_connected}, "
            f"model={self.model is not None})"
        )


def setup_milvus() -> MilvusClient:
    """
    Initialize and setup the Milvus client.
    Returns fully configured MilvusClient instance.
    """
    client = Milvus()
    client.setup_connection()
    client.setup_collection()
    return client


if __name__ == "__main__":
    # Demo / test
    client = setup_milvus()
    print(client)
    
    # Get stats
    stats = client.get_stats()
    print(f"Collection stats: {stats}")

    response = requests.get("http://127.0.0.1:8004/health")
    print(response.json())
    # Query
    results = client.search(query="RAG")
    print(f"Query results: {results}")

