import utils
import arxiv
from download_arxiv import donwload_papers
from pdf_parser import parsing_papers
import config
import logging
from pathlib import Path
logger = logging.getLogger(__name__)

def call_arxiv(page_size, topics, date_limit, max_results=100):
    """
    Function that retrive metadata about relevent papers to the topic.
    Args:
        page_size: (int) number of pages.
        topics: (list) search topics.
        date_limit: (str) search date interval.
        max_results: (int) number of papers retrived.
    """
    client = arxiv.Client(page_size=page_size)
    search = arxiv.Search(query= topics, max_results=max_results)
    results = [
        { 
    'title': r.title,
    'categories': r.categories,
    'authors': [a.name for a in r.authors],
    'published': r.published.isoformat(),
    'summary': r.summary,
    'pdf_url': r.pdf_url,
        } for r in client.results(search)]
    # store the retrived metadata in json, to start the download.
    file_name = Path(config.DIRECTORY["DATA"],"arxiv_data.json").joinpath()
    utils.write_file(file_name, results)
    return file_name
    


def process_query(page_size, topics, date_limit, max_results):
    """
    Process download and parsing requests.
    Args:
        page_size: (int) number of pages searched.
        topics: (str) search query.
        date_limit: (str) date and time filter of query results.
        max_results: (int) number of retrived relevent papers.
    """
    # retrive metadata of relevent paper to user query.
    metadata_file = call_arxiv(page_size, topics, date_limit, max_results)
    
    papers_dir = config.DIRECTORY["PAPERS_DIR"]
    
    # donwload the PDFs using paper's url
    donwload_papers(metadata_file, papers_dir)
    # PDFs parsing.
    parsing_papers(metadata_file,papers_dir)


def setup():
    """
    App initialization and configuration
    """
    print("DATA exist") if Path(config.DIRECTORY["DATA"]).exists() else Path(config.DIRECTORY["DATA"]).mkdir()
    print("IMAGES exist") if Path(config.DIRECTORY["IMAGES"]).exists() else Path(config.DIRECTORY["IMAGES"]).mkdir()
    print("PAPERS_DIR exist") if Path(config.DIRECTORY["PAPERS_DIR"]).exists() else Path(config.DIRECTORY["PAPERS_DIR"]).mkdir()
    utils.logs()
    
if __name__ == "__main__":
    setup()
    page_size = 10
    topics = "AI"
    date_limit = "202401010600 TO 202606010600"
    max_results = 10
    process_query(page_size, topics, date_limit, max_results)



    