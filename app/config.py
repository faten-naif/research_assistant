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

# # Text Chunking Settings
# CHUNKING = {
#     "CHUNK_SIZE": 500,
#     "CHUNK_OVERLAP": 50
# }

# # Vector Database Settings
# VECTOR_DB = {
#     "PROVIDER": "chroma",
#     "COLLECTION_NAME": "pdf_embeddings",
#     "EMBEDDING_MODEL": "text-embedding-3-small",
#     # Automatically pulls from environment variables for security
#     "API_KEY": os.getenv("VECTOR_DB_API_KEY", "default_local_key")
# }