import config
import utils
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def split_into_chunks(text, chunk_size, chunk_overlap):
    """
    Split text into overlapping chunks aligned to word boundaries.
    Args:
        text: (str) text to split.
        chunk_size: (int) maximum chunk length in characters.
        chunk_overlap: (int) characters repeated from the end of the previous chunk.
    Returns:
        (list) chunk strings.
    """
    words = text.split()
    chunks = []
    current = []
    current_len = 0

    for word in words:
        extra = len(word) + (1 if current else 0)
        if current and current_len + extra > chunk_size:
            chunks.append(" ".join(current))
            tail = []
            tail_len = 0
            for w in reversed(current):
                cost = len(w) + (1 if tail else 0)
                if tail_len + cost > chunk_overlap:
                    break
                tail.insert(0, w)
                tail_len += cost
            current = tail
            current_len = tail_len
        current.append(word)
        current_len += len(word) + (1 if len(current) > 1 else 0)

    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_paper(paper, chunk_size, chunk_overlap):
    """
    Chunk the pages of a parsed paper, keeping page-level provenance.
    Args:
        paper: (dict) parsed paper record from rag_*.json.
        chunk_size: (int) maximum chunk length in characters.
        chunk_overlap: (int) characters repeated between consecutive chunks.
    Returns:
        (list) chunk records.
    """
    chunks = []
    for page in paper["content"]:
        page_chunks = split_into_chunks(page["content"], chunk_size, chunk_overlap)
        for i, chunk in enumerate(page_chunks):
            chunks.append(
                {
                    "title": paper["title"],
                    "page_no": page["page_no"],
                    "chunk_no": i,
                    "content": chunk,
                }
            )
    return chunks


def chunk_papers(metadata_file):
    """
    Chunk all papers contained in a parsed RAG metadata file.
    Args:
        metadata_file: (str) path of rag_*.json produced by pdf_parser.
    Returns:
        (list) chunk records ready for vector database ingestion.
    """
    papers = utils.read_file(metadata_file)
    chunk_size = config.CHUNKING["CHUNK_SIZE"]
    chunk_overlap = config.CHUNKING["CHUNK_OVERLAP"]

    all_chunks = []
    for paper in papers:
        chunks = chunk_paper(paper, chunk_size, chunk_overlap)
        all_chunks.extend(chunks)
        logger.info(f"{Path(__file__).stem}: {paper['title']} split into {len(chunks)} chunks")
    logger.info(f"{Path(__file__).stem}: total {len(all_chunks)} chunks")
    return all_chunks

def chunk():
    rag_files = sorted(Path(config.DIRECTORY["DATA"]).glob("rag_*.json"))
    if not rag_files:
        raise FileNotFoundError("no rag_*.json found, run pdf_parser first")
    chunks = chunk_papers(rag_files[-1])
    file_name = Path(config.DIRECTORY["DATA"], f"chunks_{int(time.time() * 1000)}.json").joinpath()
    utils.write_file(file_name, chunks)
    return chunks, file_name
if __name__ == "__main__":
    chunk()
