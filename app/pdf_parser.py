import utils as utils
import time
import config as config
import logging
from pathlib import Path
import re
from tqdm import tqdm
import math
from grobid_client.grobid_client import GrobidClient
from lxml import etree as ET 
# responsible for the extraction of the papers and storing them as json file. 

logger = logging.getLogger(__name__)

#################################### Metadata ####################################
def get_authors(authors_elem, ns):
    """
    Retrive the paper authors' names
    input: 
        authors_elem: (list) of lxml elements.
        ns: (dict) of namespaces.
    returns: 
        list of authors full name or empty.
    """
    authors_list = []
    for elem in authors_elem:
        # Find nested components using your namespace
        forename = elem.findtext('./tei:forename', default='', namespaces=ns).strip()
        surname = elem.findtext('./tei:surname', default='', namespaces=ns).strip()
        authors_list.append({"forename":forename,"surname":surname})
    return authors_list
    
def get_keywords(keywords_elem, ns):
    """
    return the search keywords found in the paper.
    input:
        keywords_elem: (lists) of lxml elements.
        ns: (dict) of namespaces.
    returns: 
        list of keywords or empty.
    """
    keywords = []
    for elem in keywords_elem:
        if elem != None:
            term = elem.text
            keywords.append(term)
    return keywords


def get_paper_metadata(header, root,ns):
    """
    Function that combines all metadata found in the paper: title, publication date, authors and keywords.
    input:
        header: xlmx element of the header section.
        root: xlmx element of the whole paper.
        ns: (dict) of namespaces
    return:
        dictionary of metadata.
    """
    meta_data = {}
    # get the header section.
    header = root.find('tei:teiHeader', ns)
    # get paper title.
    title = header.findtext("tei:fileDesc/tei:titleStmt/tei:title",default="",namespaces=ns)
    # get publication date.
    publication_date = header.findtext("tei:fileDesc/tei:publicationStmt/tei:date",default="",namespaces=ns)
    # list of authors
    authors_xml = header.findall("tei:fileDesc/tei:sourceDesc/tei:biblStruct/tei:analytic/tei:author/tei:persName",ns)
    authors = get_authors(authors_xml, ns)
    # paper search keywords
    keywords_xml = header.findall("tei:profileDesc/tei:textClass/tei:keywords/tei:term",ns)
    keywords = get_keywords(keywords_xml,ns)
    return {"title":title,
           "date":publication_date,
           "authors":authors,
           "keywords":keywords}

#################################### Reference section parsing ####################################


    
def process_coords(coords):
    page = None
    x = None
    y = None
    width = None
    height = None
    if coords:
        first_box = coords.split(';')[0]
        data_types = (int, float, float, float, float)
        page, x, y, width, height = [d_type(val) for d_type, val in zip(data_types, first_box.split(","))]
    return page, x, y, width, height

def get_idno(bibl,ns):
    """
    get the identification number for each reference, if exsit.
    Input:
        bibl: xlmx element of a reference.
        ns: (dict) of namespaces.
    return: (dic) of doi and doi type.
    """
    identifier = {}
        
    arxiv_idno_elem = bibl.find(f".//tei:idno", namespaces=ns)
    if arxiv_idno_elem is not None:
        arxiv_idno = arxiv_idno_elem.text
        identifier = {"doi":arxiv_idno,
                     "type":"arxiv_id"}

    doi_elem = bibl.find(f".//tei:analytic", namespaces=ns)
    if doi_elem is not None:
        doi = doi_elem.text
        identifier = {"doi":doi,
                     "type":doi_elem.get("type")}
    return identifier
    
def extract_references(bibl_entries,short_citaions, ns):
    """
    Extract and parse the reference section of the paper.
    Input:
        bibl_entries: (list) of xlmx elements of bibliography tags.
        short_citations: (set) in text citations.
        ns: (dict) of namespaces.
    Return:
        list of dictionaries of all reference data.
    """
    
    parsed_references = []

    for bibl in bibl_entries:
        tag_name = bibl.xpath('local-name()')
        # Extract unique reference ID attribute (e.g., "b0", "b1")
        ref_id = bibl.xpath('@xml:id', namespaces=ns)[0] if bibl.xpath('@xml:id', namespaces=ns) else bibl.get('id')
        
        # --- COORDINATE EXTRACTION ---
        coords_str = bibl.get('coords')  
        # Grobid can output multiple bounding boxes separated by semicolons
        # We take the first bounding box to determine where the element begins
        first_box = coords_str.split(';')[0]
        page, x, y, width, height = process_coords(coords_str)
       
        # --- TITLE EXTRACTION ---
        # Grobid splits titles: analytic title (paper name) vs monogr title (journal/book name)
        title_analytic = bibl.findtext(f".//tei:analytic/tei:title", default="", namespaces=ns).strip()
        title_monogr = bibl.findtext(f".//tei:monogr/tei:title", default="", namespaces=ns).strip()
        
        # If it's a journal paper, analytic title is the paper name. If it's a book, monogr is the main title.
        main_title = title_analytic if title_analytic else title_monogr
        venue = title_monogr if title_analytic else ""

        # --- AUTHOR EXTRACTION ---
        authors = []
        # Find all author blocks inside this reference
        for author_elem in bibl.findall(f".//tei:author", namespaces=ns):
            # extract the full author name.
            full_name = " ".join(author_elem.itertext()).strip()
                
            if full_name:
                authors.append(full_name)

        # --- METADATA EXTRACTION (Date, Volume, Issue, Pages) ---
        # Date
        date_elem = bibl.find(f".//tei:date", namespaces=ns)
        year = ""
        if date_elem is not None:
            # Grobid often sets a 'when' attribute (e.g., when="2020")
            year = date_elem.get('when') or "".join(date_elem.itertext()).strip()

        # Volume, Issue, and Pages live under <biblScope> tags distinguished by a 'unit' attribute
        volume = ""
        issue = ""
        pages = ""
        for scope in bibl.findall(f".//tei:biblScope", namespaces=ns):
            unit = scope.get('unit')
            if unit == 'volume':
                volume = "".join(scope.itertext()).strip()
            elif unit == 'issue':
                issue = "".join(scope.itertext()).strip()
            elif unit == 'page':
                # Can capture page ranges (e.g., "121-135")
                from_p = scope.get('from', '')
                to_p = scope.get('to', '')
                pages = f"{from_p}-{to_p}" if from_p and to_p else "".join(scope.itertext()).strip()

        # --- DIGITAL IDENTIFIERS (DOI, ArXiv ID) ---
        
        doi = get_idno(bibl, ns)
        # use authors and the detected in text citations as anchors to remove false references like text in appendix.
        if authors or (ref_id in short_citaions):
            # if it passes the reference check then append it to the list.
            parsed_references.append({
                "tag_name": tag_name,
                "text": {
                    "title": main_title,
                    "authors": authors,
                    "venue": venue,
                    "year": year,
                    "volume": volume,
                    "issue": issue,
                    "pages": pages,
                    "doi": doi
                },
                "target": ref_id, # reference id
                "page": page,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "raw_coords": coords_str
                
            })
    
    return parsed_references

    
#################################### Main body ####################################
def extract_text(all_divs, ns,section_type=None):
    """
    Extract the main text from div sections.
    input:
        all_divs: (list) of div tags.
        ns: (dict) of namespaces.
        section_type: (str) set the tag name could be: abstract or none.
    return:
        output: (list) of dicts of the extracted text and inline references.
        short_citations: (set) of the inline paper references to be used as filter of false full citations parsing.
    """
    outputs = []
    short_citations = []

    for div in all_divs:
        
        # Loop through direct children (usually <p> or <head>)
        for child in div:
            tag_name = child.xpath('local-name()')
            text = "".join(child.itertext())
            coords = child.get("coords")
            try:
                page, x, y, width, height = process_coords(coords)
            except:
                logger.error(f"{Path(__file__).stem}: the coords was not processed correctly: page {page}, x: {x}, y: {y}, width: {width}, height: {height}")
            # if section_type is none use the tag name from xlm.
            
            outputs.append({
                    "tag_name":tag_name if section_type == None else section_type,
                    "text":text,
                    "target": None,
                    "page":page,
                    "x":x,
                    "y":y,
                    "width":width,
                    "height":height,
                    "raw_coords": coords
                    
                })
            
            refs = child.xpath('.//tei:ref', namespaces=ns)
            
            # Process the references found inside this paragraph/header
            for ref in refs:
                tag_name = ref.xpath('local-name()')
                ref_text = ref.text
                ref_target = ref.get("target")
                ref_coords = ref.get("coords")
                # get the citation in text.
                if (ref_target) and (re.match(r"#b\d",ref_target)):
                    short_citations.append(ref_target.replace("#",""))
                try:
                    page, x, y, width, height = process_coords(ref_coords)
                except:
                    logger.error(f"{Path(__file__).stem}: the coords was not processed correctly: page {page}, x: {x}, y: {y}, width: {width}, height: {height}")
                    
                outputs.append({
                    "tag_name":tag_name,
                    "text":ref_text,
                    "target": ref_target,
                    "page":page,
                    "x":x,
                    "y":y,
                    "width":width,
                    "height":height,
                    "raw_coords":ref_coords
                    
                })
    return outputs, set(short_citations)

def paper_content(root,ns):
    """
    extract all information from the paper and combine them in a list.
    input:
        root: xlmx of the whole document.
        ns: (dict) of namespaces.
    return:
        dict of all parsed content.
    """
    # extract the abstract
    all_divs = root.xpath("//tei:teiHeader//tei:profileDesc//tei:abstract//tei:div",namespaces=ns)
    abstract,_ = extract_text(all_divs, ns,section_type="abstract")
    abstract = abstract[0]
    # main body
    all_divs = root.xpath('//tei:body/tei:div', namespaces=ns)
    body_text, short_citaions = extract_text(all_divs, ns)
    # back, retrive every element in back section except the bibliography list.
    all_divs = root.xpath('//tei:back//*[not(ancestor-or-self::tei:listBibl)]', namespaces=ns)
    back_text = extract_text(all_divs, ns)
    # references section
    bibl = root.xpath("//tei:back//tei:biblStruct",namespaces=ns)
    bibliography = extract_references(bibl,short_citaions, ns)
   
    
    return {"abstract":abstract, 
           "body_text":body_text,
           "back_text":back_text,
            "bibliography":bibliography} 
    

def main(papers_dir,output_dir,n):
    g_client = GrobidClient()
    ns = {
        'tei': "",
        'xml': 'http://www.w3.org/XML/1998/namespace' 
    }
    papers_content = []
    # get the downloaded pdf papers.
    papers_path = [str(file_name) for file_name in Path(papers_dir).glob("*.pdf")]
    try:
        # return a set of three values: title, status, and xml content.
        xml_batch = g_client.process_documents("processFulltextDocument",papers_path,n=n,tei_coordinates=True,consolidate_citations=False)
        
        for xml_doc in xml_batch:
            if xml_doc[1] == 200:
                # start the processing 
              
                raw_xml_bytes = xml_doc[2].encode('utf-8')
                root = ET.fromstring(raw_xml_bytes)
                ns["tei"] = root.tag.split('}')[0].strip('{') if '}' in root.tag else "http://www.tei-c.org/ns/1.0"
                output = paper_content(root,ns)
                papers_content.append({"title":xml_doc[0],"xml_content":output})
        
        logger.info("successfully parsed all PDFs")

    except Exception as e:
        logger.error(f"{Path(__file__).stem}: {e}")
    finally: 
        # store the parsed files.
        ms_timestamp = int(time.time() * 1000)
        file_name = Path(output_dir,f"rag_{ms_timestamp}.json").joinpath()
        utils.write_file(file_name, papers_content)

if __name__ == "__main__":
    output_dir = config.DIRECTORY['DATA']
    papers_dir = config.DIRECTORY["PAPERS_DIR"]
    # number of documents processed in parallel.
    n = config.GROBID["n_parallel"]
    main(papers_dir,output_dir,n)