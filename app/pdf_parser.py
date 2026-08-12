import pymupdf  # PyMuPDF
import utils
import time
import config
import logging
from pathlib import Path
# responsible for the extraction of the papers and storing as json file. 
# best to start the experiment with RAG with one paper.

logger = logging.getLogger(__name__)


def table_extraction(page):
    tables = page.find_tables()
    table_rects = []
    table_blocks = []
    for i, table in enumerate(tables):
        # Remember where the table is, to prevent drawing overlaps
        table_rects.append(pymupdf.Rect(table.bbox))
        table_blocks.append({"type": 3, "bbox": table.bbox, "markdown": table.to_markdown()})
        
    return table_blocks, table_rects

def drawing_extraction(page):
    drawing_blocks = []
    drawings_rects = []
    drawing_clusters = page.cluster_drawings(x_tolerance=10, y_tolerance=10)
    for cluster_bbox in drawing_clusters:
        # Filter out negligible marks (e.g. tiny bullet points, single underscores)
        if cluster_bbox.is_empty or (cluster_bbox.x1 - cluster_bbox.x0 < 15 or cluster_bbox.y1 - cluster_bbox.y0 < 15):
            continue
        cluster_text = page.get_text("text", clip=cluster_bbox).strip()
        if len(cluster_text) < 60:
            continue
        bbox = (
                cluster_bbox.x0,
                cluster_bbox.y0,
                cluster_bbox.x1,
                cluster_bbox.y1,
            )
        drawings_rects.append(pymupdf.Rect(bbox))
        drawing_blocks.append({
            "type": 2,
            "bbox":bbox ,

        })
    return drawing_blocks, drawings_rects

def pdf_extraction(title):
    # open the pdf file.
    doc = pymupdf.open(title)
    # store the extracted pages
    extracted_pages = []
    # store metadata about the paper.
    total_images = 0
    total_tables = 0
    # iterate through the pages.
    for page_num, page in enumerate(doc):
        drawing_counter = 0
        image_counter = 0
        
        page_content= page.get_text("dict")
        all_blocks = list(page_content["blocks"])
        table_blocks, table_rects = table_extraction(page)
        # concate tables to the text blocks.
        all_blocks+= table_blocks 
        
        # add the drawings blocks to the list of contents.
        drawing_blocks, drawings_rect = drawing_extraction(page)
        # concate drawings blocks.
        all_blocks+= drawing_blocks
        # sort blocks, to maintain the original document flow.
        sorted_blocks = sorted(
            all_blocks, key=lambda b: (b["bbox"][1], b["bbox"][0])
        )
        
        print(f"Page_num: {page_num}")
        # find the width of the page, 
        mid_x = page.rect.width / 2
        # first: detect if the block is double or single column. if it passes the middle point then single if not then double.
        
        left_blocks = []
        right_blocks = []
        for block in sorted_blocks:
            
            block_text = ""
            block_type = block["type"]
            x0,_,x1,_ = block["bbox"]
            block_rect = pymupdf.Rect(block["bbox"])
            # check the layout of the page.
            is_double = False
            if x0 > mid_x or x1 < mid_x:
                is_double = True
            # ----------------------------------------------------------
            # Table block (already extracted as markdown)
            # ----------------------------------------------------------
            if block_type == 3:
                block_text += block["markdown"]
            else:
                # Skip text/images contained inside detected tables
                if any(block_rect.intersects(table_rect) for table_rect in table_rects):
                    continue
                # ---------------- Text ----------------
                if block_type == 0:
                    # the table might be extracted as text even though it was added as table.
                    # so, if there is overlap between the text and table boxes, skip.
                    for line in block["lines"]:
                        for spans in line["spans"]:
                            block_text+=spans["text"]
                        block_text+="\n"
                        
                # ---------------- Image ----------------
                elif block_type == 1:
                    #print(block)
                    img_name = f"image_{image_counter}_page{page_num}.{block['ext']}"
                    block_text+=f"\n[IMAGE] {img_name}\n"
                    with open(Path(config.DIRECTORY["IMAGES"],img_name).joinpath(), "wb") as f:
                        f.write(block["image"])
                    image_counter+=1
                    
                # ---------------- Drawings ----------------
                elif block_type == 2:
                    graph_name = f"vector_graph_{drawing_counter}_page{page_num}.png"
                    block_text += f"\n[GRAPH/DRAWING] {graph_name}\n"
        
                    clip_rect = pymupdf.Rect(block["bbox"])
                    pix = page.get_pixmap(clip=clip_rect, dpi=150)
                    pix.save(Path(config.DIRECTORY["IMAGES"],graph_name).joinpath())
                    drawing_counter += 1
                    
            # ---------------- Layout ----------------
            # research papers could be single or double columns, if single add to the left (English text)
            if is_double:
            
                if x1 < mid_x:
                    left_blocks.append(block_text)
                elif x0 > mid_x:
                    right_blocks.append(block_text)
            else:
                left_blocks.append(block_text)

        # prepare the output.
        page_text = "".join(left_blocks)
        if len(right_blocks) > 0:
            page_text+= "".join(right_blocks)
        # add the extracted page with its metadata to the list.
        page_data = {"page_no": page_num, "content": page_text,"images_no":image_counter+drawing_counter,"tables_no":len(table_rects)}
        extracted_pages.append(page_data)
        total_images+=page_data["images_no"]
        total_tables+=page_data["tables_no"]
    
    return extracted_pages,total_images,total_tables
    

def parsing_papers(metadata_file,papers_dir):
    """
    Parse PDFs to JSON for vector database ingestion.
    Args:
        metadata_file: (str) path of json metadata file retrived from arxiv.
        papers_dir: (str) location of stored PDFs.
    """
    papers_content = []
    try:
        papers = utils.read_file(metadata_file)
        for paper in papers:
            paper_path = Path(papers_dir,paper['title']+".pdf").joinpath()
            print(paper_path)
            paper_content,total_images, total_tables = pdf_extraction(paper_path)
            papers_content.append({"title":paper['title'], "content": paper_content, "pages_no": len(paper_content), "images_no":total_images, "tables_no":total_tables})
        logger.info("successfully parsed all PDFs")
    except pymupdf.FileNotFoundError as e:
        logger.error(f"{Path(__file__).stem}: {e}")
    finally: 
        ms_timestamp = int(time.time() * 1000)
        file_name = Path(config.DIRECTORY['DATA'],f"rag_{ms_timestamp}.json").joinpath()
        utils.write_file(file_name, papers_content)



if __name__ == "__main__":
    # take certain arguments, like the titles.
    metadata_file = Path(config.DIRECTORY["DATA"],"arxiv_data.json").joinpath()
    papers_dir = config.DIRECTORY["PAPERS_DIR"]
    parsing_papers(metadata_file,papers_dir)