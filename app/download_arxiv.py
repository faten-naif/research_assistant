# responsible for handling the download operations handling any exceptions that could rise. 
import app.utils as utils
import requests
import app.config as config
import logging
from pathlib import Path 
from tqdm import tqdm
logger = logging.getLogger(__name__)

def download_pdf_files(paper,directory):
    """
    Handle the download request of the paper using its url.
    args:
        paper: (dict) metadata about the paper.
        directory: (str) storage location.
    returns:
        download_status: sucess/fail
    """
    response = requests.get(paper["pdf_url"])
    title = paper["title"]
    # check the request status before writing.
    if response.status_code == 200:
        title +=".pdf"
        # put this function in utils.
        file_name = Path(directory,title).joinpath()
        utils.write_file(file_name, response.content)
        logger.info(f"{title} was downloaded successfully")
        return "success"
    else:
        logger.warning(f"status_code: {response.status_code}, Could not download: {title}")
        return "fail"
    #return title

def donwload_papers(file_name, directory):
    """
    Download the pdf files using the papers' links stored in the metadata file.
    Args:
        file_name: (str) json file contain the metadata of retrived results relevent to the search keywords.
        directory: (str) folder dir to store the donwloaded pdf files.
    """
    try:
        metadata = utils.read_file(file_name)
        for paper in tqdm(metadata):
            # if the paper was downloaded then skip.
            if Path(directory,paper["title"]+".pdf").exists():
                logger.info(f"{paper['title']} already exists.")
                continue
            download_status = download_pdf_files(paper, directory)
            paper["download_status"] = download_status
    except requests.exceptions.ChunkedEncodingError as e:
        logger.error(f"{Path(__file__).stem}: {e}")
    finally:
        utils.write_file(file_name, metadata)



    
if __name__ == "__main__":
    file_name = Path(config.DIRECTORY["DATA"],"arxiv_data.json").joinpath()
    directory = config.DIRECTORY["PAPERS_DIR"]
    donwload_papers(file_name,directory)