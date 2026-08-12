import json
from pathlib import Path
import config
import logging
import time


logger = logging.getLogger(__name__)

def write_file(file_name, data):
    """
    Write JSON and PDFs into files.
    Args:
        file_name: (str) file path.
        data: the data to write into the file.
    
    """
    file_type = Path(file_name).suffix.lstrip(".")
    
    if file_type == 'json':
        with open(file_name,"w",encoding="utf-8") as file:
            json.dump(data, file, indent=4)
            logger.info("json saved successfully")
            
    elif file_type == "pdf":
        with open(file_name, "wb") as file:
            file.write(data)
            logger.info("pdf saved successfully")
        

def read_file(file_name):
    """
    Open and read JSON files.
    Args:
        file_name: (str) file path.
    """
    try:
        file_type = Path(file_name).suffix.lstrip(".")
        with open(file_name, "r", encoding="utf-8") as file:
            if file_type == "json":
                data = json.load(file)
                logger.info(f"{Path(__file__).stem}: {file_name} loaded successfully")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"{Path(__file__).stem}: {e}")
    except FileNotFoundError as e:
        logger.error(f"{Path(__file__).stem}: {e}")
 
def _log_manager():
    """
    Create the logs folder if nonexistent, and rotate the log files by deleting the older logs if number of files exceed limit.
    """
    if Path(config.DIRECTORY["LOGS"]).is_dir():
        print("LOGS exist") 
        files = sorted(list(Path(config.DIRECTORY["LOGS"]).glob("*.log")))
        if len(files) > config.LOGS["FILES_LIMIT"]:
            # delete the oldest log file.
            Path.unlink(files[0])
    else:
        Path(config.DIRECTORY["LOGS"]).mkdir()

def logs():
    """
    Logging configurations.
    """
    _log_manager()
    ms_timestamp = int(time.time() * 1000)
    logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename=Path(config.DIRECTORY['LOGS'],f"logs_{ms_timestamp}.log").joinpath(),
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG
)
