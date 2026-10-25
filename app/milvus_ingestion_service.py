# ETL
import utils
import arxiv
from download_arxiv import donwload_papers
from pdf_parser import process_pdf
from document_chunking import Chunking
from milvus_db import setup_milvus
import config
import logging
from pathlib import Path
from typing import Dict, Any, TypedDict
from tempfile import mkdtemp
import shutil
class StageResult(TypedDict):
        status: str
        data: Dict[str, Any]
    
class MilvusDataPipeline():
    def __init__(self):
        
        """
        App initialization and configuration
        """
        self.logger = logging.getLogger(__name__)

        self.user_dir = self._init_user_dir()
        utils.logs()
        # setup the connection, collection and embedding model.
        self.milvus_client = setup_milvus()
    # intialize the folders.
    def _init_user_dir(self):
        # TODO: create the temp directory if not exist, this should be set by the docker container. 
        if not config.DIRECTORY["TEMP"].is_dir():
            config.DIRECTORY["TEMP"].mkdir()
            
        # create user directory
        user_dir = mkdtemp(prefix="user_",dir=config.DIRECTORY["TEMP"])
        print(user_dir)
        data_dir = Path(user_dir, config.DIRECTORY["DATA"])
        data_dir.mkdir()
        Path(user_dir, config.DIRECTORY["IMAGES"]).mkdir()
        Path(user_dir, config.DIRECTORY["PAPERS_DIR"]).mkdir()
        if config.ENV == "DEV":
            source = Path("../data/arxiv_data.json")
            destination = Path(data_dir,"arxiv_data.json" ).joinpath()
            shutil.copy(source, destination)
        return user_dir
    
    def _call_arxiv(self,page_size, topics, date_limit, max_results=100):
        """
        Function that retrive metadata about relevent papers to the topic.
        Args:
            page_size: (int) number of pages.
            topics: (list) search topics.
            date_limit: (str) search date interval.
            max_results: (int) number of papers retrived.
        """
        try:
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
            file_name = Path(self.directory,config.DIRECTORY["DATA"],"arxiv_data.json").joinpath()
            utils.write_file(file_name, results)
            return {"status":"success",
                   "data":{
                       "file_name":file_name
                       }
                   }
        except Exception as e:
            self.logger.error(f"{Path(__file__).stem}: {e}")
        {
        "status":"fail",
            "data":{
                "file_name":file_name
                }
        }
    
    
    
        
    def run_pipeline(self, initial_args):
        """
        Process download and parsing requests.
        Args:
            page_size: (int) number of pages searched.
            topics: (str) search query.
            date_limit: (str) date and time filter of query results.
            max_results: (int) number of retrived relevent papers.
            milvus_client: (MilvusClient) milvus object to manage the database.
        """
        
        
        # first step
        #"arxiv_call": lambda ctx: self._call_arxiv(user_dir, ctx["page_size"], ctx["topics"],ctx["date_limit"],ctx["max_results"]),
      
        try:
            pipeline_steps: Dict[str, Callable[[Dict[str, Any]], StageResult]] = {
            
            "download_pdfs": lambda ctx: donwload_papers(self.user_dir, ctx["file_name"]),
            "parse_pdfs":lambda ctx: process_pdf(self.user_dir),
            "chunk_xml": lambda ctx: Chunking(self.user_dir,ctx["file_name"]).start(),
            
            "vector_db": lambda ctx: self.milvus_client.insert(ctx["documents"]),
            "clean_up": lambda ctx: utils.cleanup_temp_dir(self.user_dir),
        }
            
            pipeline_context = initial_args["data"].copy()
            #papers_dir = config.DIRECTORY["PAPERS_DIR"]
         
            results = {}
            
            
            # use another one with option or create your own.
            for step_name, script_invoker in pipeline_steps.items():
                #print(pipeline_context)
                res = script_invoker(pipeline_context)
                results[step_name] = res
                
                if res.get("status","status key not found") != "success":
                    self.logger.error(f"❌ Pipeline failed at {step_name}: {res}")
                    utils.cleanup_temp_dir(self.user_dir)
                    return {"status": "failed", "step": step_name}
                    
                # Inject the step data into the context for future steps.
                pipeline_context.update(res.get("data","data key not found"))
                self.logger.info(f"{step_name} finished")
                
            return {"status": "success", "final_context": pipeline_context, "pipeline_results": results}
        except Exception as e:
            self.logger.error(e)
            print(e)
            utils.cleanup_temp_dir(self.user_dir)
        
    
    
    
    
if __name__ == "__main__":
    # this script will be called by agent when new data is needed.
    

    initial_args = {
                    "data": 
                        {"page_size":10, 
                         "topics":"AI", 
                         "date_limit":"202401010600 TO 202606010600", 
                         "max_results": 2
                         }
                   }
    initial_args = {"status":"success",
                   "data":{
                       "file_name": "../data/arxiv_data.json"
                   }
                   }
    database = MilvusDataPipeline()
    output = database.run_pipeline(initial_args)
    print(f"Status: {output}")
    # print(f"final_content: {output['final_context'].keys()}")
    # print(f"pipeline_results: {output['pipeline_results'].keys()}")

    