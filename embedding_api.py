from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING
from pydantic import BaseModel
import uvicorn
import logging
from pathlib import Path


logger = logging.getLogger(__name__)

# load the model once the service start.
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Load the model and attach it securely to the app state
        app.state.model = SentenceTransformer(
            EMBEDDING["MODEL_NAME"], 
            backend=EMBEDDING["BACKEND"]
        )
        logger.info("The embedding model has been loaded successfully into app state.")
    except Exception as e:
        logger.error(f"{Path(__file__).stem}: {e}")
        # Setting to None allows the server to start, but requests will fail safely
        app.state.model = None
        
    yield  # The application runs while paused here
    
    logger.info("Shutting down embedding model service")

#Pass the lifespan context manager to the FastAPI instance
app = FastAPI(lifespan=lifespan)

@app.get("/stats")
def get_stats():
    return {"embedding_model":EMBEDDING["MODEL_NAME"],
        "embedding_dim":EMBEDDING["EMBEDDING_DIM"],
            "normalize_embedding":EMBEDDING["NORMALIZE"],
           "backend":EMBEDDING["BACKEND"]}
    
    
@app.get("/health")
def health_check():
    if app.state.model != None:
        
        return {"status":"healthy",
               "status_code":200}
    # when the model has not been loaded.
    return {"status":"unhealthy",
            "status_code":503}



class EmbeddingRequest(BaseModel):
    # Hinting list[str] ensures validation checks that elements are actual strings
    payload: list[str]
    
@app.post("/v1")
def embedding(embedding_request: EmbeddingRequest):
    # Access the model safely from the application instance state
    model = app.state.model
    
    try:
        # Generate the embeddings matrix
        embeddings = model.encode(embedding_request.payload,normalize_embeddings=EMBEDDING["NORMALIZE"],
                                  truncate_dim=EMBEDDING["EMBEDDING_DIM"])
        
        # .tolist() converts the NumPy array into a JSON-serializable standard Python list
        return {
            "status_code":200,
            "embeddings": embeddings.tolist(),
            "embeddings_shape": list(embeddings.shape)
        }
    except Exception as e:
        return {
            "status_code": 500,
            "message": str(e)  
        }

if __name__ == "__main__":
    uvicorn.run("embedding_api:app",
                host=EMBEDDING["HOST"],
                port=EMBEDDING["PORT"],
                reload=True)