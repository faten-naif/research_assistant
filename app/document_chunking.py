import config as config
import utils as utils
import time
import logging
from pathlib import Path
import sys
from transformers import AutoTokenizer
from collections import ChainMap
from tqdm import tqdm
class Chunking():
    def __init__(self, user_dir, file_name):
        #self.data_file = file_name
        self.user_dir = user_dir
        self.data_file = Path(file_name)
        self.chunk_size = config.CHUNKING["CHUNK_SIZE"]
        self.chunk_overlap = config.CHUNKING["CHUNK_OVERLAP"]
        self.logger = logging.getLogger(__name__)
        self.papers = self._open_file()
        self.tokenizer = AutoTokenizer.from_pretrained(config.EMBEDDING["MODEL_NAME"], trust_remote_code=True)
    def _open_file(self):
        if not self.data_file:
            # TODO: check to see how it behaves.
            self.logger.error("no rag_*.json found, run pdf_parser first")
            return []
            
        papers = utils.read_file(self.data_file)
        return papers
        
    def start(self) -> tuple[list, str]:
        try:
            documents = self._chunk_papers()
            output_file = Path(self.user_dir, config.DIRECTORY["DATA"], f"chunks_{int(time.time() * 1000)}.json").joinpath()
            utils.write_file(output_file, documents)
            return {"status":"success",
                    "data":
                    {"documents": documents,
                     "output_file":output_file}
                   }
        except Exception as e:
            self.logger.error(f"{Path(__file__).stem}: {e}")
        return {"status":"fail",
           "data":{}
           }
        
        
    def _chunk_papers(self) -> list:
        documents = []
        for paper in tqdm(self.papers):
            chunks = []
            title = Path(paper.get("title","")).stem
            content = paper.get("xml_content",{})
            # retrive the main contents of the paper.
            abstract = content.get("abstract",{})
            body_content = content.get("body_text",[])
            back_content = content.get("back_text",[])
            # start chunking to store in Vector DB.
            abstract_chunks = self._get_abstract(title, abstract)
            #all_chunks.extend(abstract_chunks)
            body_chunks = self._split_into_chunks(title, body_content)
            #all_chunks.extend(body_chunks)
            back_chunks = self._split_into_chunks(title, back_content)
            #documents.extend(back_chunks)
            chunks = abstract_chunks+body_chunks+back_chunks
            documents.append({"title":title,
                             "no_chunks":len(chunks),
                             "chunks":chunks})
            
            self.logger.info(f"{Path(__file__).stem}: {paper['title']} split into {len(chunks)} chunks")
        self.logger.info(f"{Path(__file__).stem}: total {len(documents)} documents")
        return documents
        
    def _chunk(self,tokens:list) -> list:
        # TODO: docstr.
        chunks = []
        start = 0
        end = self.chunk_size
        done = False
        while not done:
            if end > len(tokens):
                done = True
                chunk = tokens[start:]
            else:
                chunk = tokens[start:end]
            text = self.tokenizer.decode(chunk, skip_special_tokens=True)
            chunks.append(text.strip())
            start = end - self.chunk_overlap
            end = start + self.chunk_size
        return chunks
        
    def _get_abstract(self,title:str, abstract:dict) -> list:
        # TODO: docstr.
        chunks = []
        
        # check the number of tokens in abstract
        tokens = self.tokenizer.encode(abstract.get("text",""),add_special_tokens=False)
        # text is empty, return .
        if len(tokens) == 0:
            return []
            
        if len(tokens) <= self.chunk_size:
            # no chunking is needed.
            return [{
                   "title": title,
                    "heading":abstract.get("tag_name",""),
                    "page_no": abstract.get("page",-1),
                    "chunk_no": 0,
                    "content": abstract.get("text",""),
                    "references": {}
            }]
        
        chunks = self._chunk(tokens)
        segments = []
        for index in range(len(chunks)):
            segments.append({
                   "title": title,
                    "heading":abstract.get("tag_name",""),
                    "page_no": abstract.get("page",-1),
                    "chunk_no": index+1,
                    "content": chunks[index],
                    "references":{}
            })
            
        return segments
    
    def _split_into_chunks(self,title: str,paper_content:list) -> list:
        """
        Group text segments into chunks based on the configured token limit.
        Headings define section boundaries, and oversized segments are split
        into smaller chunks.
    
        Args:
            paper_content: Parsed XML content of the PDF paper, represented
                as a list of text segments.
    
        Returns:
            A list of prepared chunks containing grouped or split segments.
        """
        # Initialize chunking state.
        section_head = ""
        chunks = []
        current_token_count = 0
        block = []
        # add the split/combined block into the chunks list, and reset the variables 
        def flush_block(chunked=False):
            """Process the current block and reset the chunking state."""
            nonlocal block, current_token_count
        
            if block:
                chunks.extend(self._prepare_data(block, section_head, title,chunked=chunked))
                block = []
                current_token_count = 0
        # Process each extracted segment in document order.
        for segment in paper_content:
            tag = segment["tag_name"]
            # we are only intreseted in these tags. other tags do not include related data.
            if not tag in ["head","p","div"]:
                continue
            # Start a new section when a heading is encountered.
            if tag == "head":
                if len(block) > 0:
                    flush_block()
                # update the section head.
                section_head = segment.get("text","")
                continue
            # Only paragraphs and divs are included in text chunks.
            elif tag in ["p","div"]:
                # Tokenize the segment to check whether it exceeds the limit.
                current_tokens = self.tokenizer.encode(segment.get("text",""),add_special_tokens=False)
                current_token_count = len(current_tokens)
                 # Split oversized segments into a smaller size and store them as separate chunks.
                if current_token_count > self.chunk_size:
                    if len(block) > 0:
                        flush_block()
                    block = self._chunk(current_tokens)
                    # original_seg contain metadata related to the text.
                    block = {"chunked":block,
                            "original_seg": segment}
                    flush_block(chunked=True)
                    continue
                # keep adding segements into the current block until exceeds the token_limt
                block.append(segment)
                current_tokens = self.tokenizer.encode(" ".join([el.get("text","") for el in block]),add_special_tokens=False)
                current_token_count = len(current_tokens)
                if current_token_count > self.chunk_size:
                    # Save the existing block and start a new one with the current segment.
                    block.pop()
                    flush_block()
                    block = [segment]
        # Process any remaining segments after iteration.
        flush_block()
        return chunks
    # Formatting.
    def _prepare_data(self,elements:list,section_head:str,title:str,chunked=False) -> list:
        """
        Convert grouped or split text segments into standardized chunk records.
    
        Args:
            elements: A list of grouped segments, or a dictionary containing
                split chunks and their original segment when chunked=True.
            section_head: Heading associated with the current section.
            title: Title of the document.
            chunked: Whether elements contains a pre-split oversized segment.
    
        Returns:
            A list of formatted chunk dictionaries.
        """
        chunks = []
        try:
            
            if chunked:
                # Preserve the original segment's metadata for each split chunk.
                split_section = elements["chunked"]
                original_section = elements["original_seg"]
                for index in range(len(split_section)):
                    chunks.append({
                            "title":title,
                            "heading":section_head,
                            "page":{original_section["page"]},
                            "chunk_no":index+1,
                            "content":split_section[index],
                            "references": original_section["references"]})
            elif elements:
                # Aggregate text, unique page numbers, and merged references.
                pages, texts,references_dicts = map(list, zip(
                    *[(item["page"], item["text"],item["references"])
                    for item in elements]))
                # combine the list into one with unique references.
                references = dict(ChainMap(*references_dicts))
                
                chunks.append({"title":title,
                           "heading":section_head,
                           "page":set(pages),
                           "chunk_no":0,
                           "content":" ".join(texts),
                            "references": references})
        except Exception as e:
            self.logger.error(f"{Path(__file__).stem}: Error preparing chunk data -> {e}")
        return chunks
if __name__ == "__main__":
    file_name = "../temp/user_ok1bl3od/data/rag_1792610683534.json"
    user_name = "../temp/user_ok1bl3od"
    start_chunking = Chunking(user_name, file_name)
    output = start_chunking.start()
    print(output["data"].keys())
