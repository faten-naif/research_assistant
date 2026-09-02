from pathlib import Path


# Storage Settings
DIRECTORY = {
    "DATA":Path("..","data").joinpath(),
    "PAPERS_DIR":Path("..","data","documents").joinpath(),
    "IMAGES":Path("..","data","images").joinpath(),
    "LOGS":Path("..","logs").joinpath(),
}


LOGS = {
    "FILES_LIMIT":3

}

# Text Chunking Settings
CHUNKING = {
    "CHUNK_SIZE": 500,
    "CHUNK_OVERLAP": 50
}

# # Vector Database Settings
VECTOR_DB = {
    "HOST":"http://localhost:19530",
    "TOKEN":"root:Milvus",
    "DB_NAME":"arxiv_db",
    "COLLECTION_NAME":"papers_text",
    "EMBEDDING_MODEL":"Qwen/Qwen3-Embedding-0.6B",
    
}

ENV = "PROD"
EMBEDDING = {
    "MODEL_NAME":"Qwen/Qwen3-Embedding-0.6B",
    "HOST":"127.0.0.1",
    "PORT":8004,
    "BACKEND":"openvino",
    "NORMALIZE":True,
    "EMBEDDING_DIM":1024,
    
}
# LLM serving
# Embedding serving.
# VECTOR_DB = {
#     "PROVIDER": "chroma",
#     "COLLECTION_NAME": "pdf_embeddings",
#     "EMBEDDING_MODEL": "text-embedding-3-small",
#     # Automatically pulls from environment variables for security
#     "API_KEY": os.getenv("VECTOR_DB_API_KEY", "default_local_key")
# }