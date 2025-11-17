from loguru import logger
from .config import settings
import chromadb
from chromadb.config import Settings as ChromaSettings
import numpy as np
from typing import List, Dict, Optional


class ChromaStore:
    def __init__(self, collection_name: str = None):
        collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        
        # Determine which mode we're using
        if settings.CHROMA_MODE == "cloud":
            self._init_cloud_mode(collection_name)
        elif settings.CHROMA_MODE == "server":
            self._init_server_mode(collection_name)
        else:
            self._init_local_mode(collection_name)
    
    def _init_cloud_mode(self, collection_name: str):
        """Initialize client for Chroma Cloud"""
        try:
            logger.info(f"Connecting to Chroma Cloud database: {settings.CHROMA_DATABASE}")
            
            # Connect to Chroma Cloud
            self.client = chromadb.CloudClient(
                api_key=settings.CHROMA_API_KEY,
                tenant=settings.CHROMA_TENANT,
                database=settings.CHROMA_DATABASE
            )
            
            # Verify connection
            version = self.client.get_version()
            logger.info(f"Connected to Chroma Cloud version: {version}")
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}  # Recommended for embeddings
            )
            logger.info(f"Using collection: {collection_name} (Cloud Mode)")
            
        except Exception as e:
            logger.error(f"Failed to connect to Chroma Cloud: {e}")
            raise ConnectionError(
                f"Cannot connect to Chroma Cloud. Check your credentials:\n"
                f"  API Key: {settings.CHROMA_API_KEY[:20]}...\n"
                f"  Tenant: {settings.CHROMA_TENANT}\n"
                f"  Database: {settings.CHROMA_DATABASE}"
            )
    
    def _init_server_mode(self, collection_name: str):
        """Initialize client for Chroma Server (via HTTP)"""
        try:
            logger.info(f"Connecting to Chroma Server at {settings.CHROMA_URL}")
            
            # Connect to Chroma server via HTTP
            self.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
                headers={"Authorization": f"Bearer {settings.CHROMA_API_KEY}"}
                if settings.CHROMA_API_KEY else {}
            )
            
            # Verify connection
            version = self.client.get_version()
            logger.info(f"Connected to Chroma Server version: {version}")
            
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}  # Recommended for embeddings
            )
            logger.info(f"Using collection: {collection_name} (Server Mode)")
            
        except Exception as e:
            logger.error(f"Failed to connect to Chroma Server: {e}")
            raise ConnectionError(
                f"Cannot connect to Chroma Server at {settings.CHROMA_URL}. "
                "Ensure the server is running: chroma run --host 0.0.0.0 --port 8001"
            )
    
    def _init_local_mode(self, collection_name: str):
        """Initialize client for local persistent storage (development)"""
        try:
            logger.info(f"Using local ChromaDB at {settings.CHROMA_DIR}")
            
            # Use PersistentClient for local development
            self.client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
            
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Using collection: {collection_name} (Local Mode)")
            
        except Exception as e:
            logger.error(f"Failed to initialize local ChromaDB: {e}")
            raise

    def rebuild(self, documents: List[str], embeddings: List[List[float]], 
                metadatas: List[dict], ids: List[str]):
        """Clear and repopulate the collection"""
        try:
            # Delete existing collection
            self.client.delete_collection(self.collection.name)
            logger.info(f"Deleted existing collection: {self.collection.name}")
        except Exception as e:
            logger.debug(f"Collection didn't exist or couldn't be deleted: {e}")
        
        # Recreate collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection.name,
            metadata={"hnsw:space": "cosine"}
        )
        
        # Add documents in batches (Chroma has batch limits)
        batch_size = 100
        logger.info(f"Upserting {len(documents)} documents to ChromaDB (batch size: {batch_size})")
        
        for i in range(0, len(documents), batch_size):
            batch_ids = ids[i:i + batch_size]
            batch_docs = documents[i:i + batch_size]
            batch_metadatas = metadatas[i:i + batch_size]
            batch_embeddings = embeddings[i:i + batch_size]
            
            self.collection.add(
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_metadatas,
                embeddings=batch_embeddings
            )
            logger.debug(f"Upserted batch {i//batch_size + 1}")
        
        # Persist if supported
        try:
            if hasattr(self.client, 'persist'):
                self.client.persist()
                logger.info("Data persisted successfully")
        except Exception as e:
            logger.debug(f"Persistence not available or failed: {e}")

    def query(self, query_embedding: List[float], top_k: int = 6, rerank: bool = False):
        """Query the collection"""
        try:
            resp = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=['metadatas', 'documents', 'distances']
            )
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise

        results = []
        
        # Handle different response formats from Chroma
        if resp.get('results'):
            entries = resp.get('results', [])[0]
        elif resp.get('documents'):
            entries = {
                'documents': resp.get('documents', [[]])[0],
                'metadatas': resp.get('metadatas', [[]])[0],
                'distances': resp.get('distances', [[]])[0],
                'ids': resp.get('ids', [[]])[0] if resp.get('ids') else []
            }
        else:
            entries = {}

        docs = entries.get('documents', [])
        metadatas = entries.get('metadatas', [])
        distances = entries.get('distances', [])
        ids = entries.get('ids', [])

        for d, m, dist, id_ in zip(docs, metadatas, distances, ids):
            results.append({'id': id_, 'document': d, 'metadata': m, 'distance': dist})

        if rerank:
            stored = self.collection.get(
                ids=[r['id'] for r in results],
                include=['embeddings']
            )
            emb_map = {eid: emb for eid, emb in zip(
                stored.get('ids', []), 
                stored.get('embeddings', [])
            )}
            q = np.array(query_embedding, dtype=float)
            
            for r in results:
                e = np.array(emb_map.get(r['id'], []), dtype=float)
                if e.size == 0:
                    r['score'] = 0.0
                    continue
                cos = float(np.dot(q, e) / (np.linalg.norm(q) * np.linalg.norm(e) + 1e-12))
                r['score'] = cos
            
            results.sort(key=lambda x: x.get('score', 0.0), reverse=True)

        return results