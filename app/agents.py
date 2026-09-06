# implement agents
# setup the llm call with different prompts and pydantic classes. 
# but first I need to survey similar tools to langchain to see if there is an alternative that could offer me visualization. 

# 1- serve the llm (done)
# 2- test different tools using jupyter notebook (done)
# 3- test observability tools. (done)
# 4- create the script.
# 5- create an interface
# 6- can we serve the embedding on cpu with optimal speed? I do not have enough VRAM for both llm and embeddings. (done)
# 7- dockerfile
import mlflow
import asyncio
from llama_index.core.prompts import RichPromptTemplate

from llama_index.llms.openai_like import OpenAILike
from workflows import Workflow,step
from workflows.events import Event, StartEvent,StopEvent
from config import LLM_SETTINGS,MLFLOW,AGENT_PROMPTS,SIMILARITY_THRESHOLD
import os 
from pydantic import BaseModel, Field, model_validator, ConfigDict
from crewai.flow.flow import Flow,router,listen,start
from typing import Literal,Annotated,Optional,Any, List
import sys
from milvus_db import setup_milvus
from enum import StrEnum, auto
import datetime
# TODO: REMOVE THIS
os.environ["OPENAI_API_KEY"] = "no_key"

class RoutingDecisions(StrEnum):
    ANSWER="answer"
    REFERENCE_SEARCH="reference_search"
    ARXIV_SEARCH="arxiv_search"
# move some declaration in the __init__
# event for answer or we just specify it in the same prompt to reduce the calls.
class RouterOutput(Event):
    model_config = ConfigDict(use_enum_values=True)
    routing_decision: RoutingDecisions
    response: Optional[str] = None
    # when the query is classified as answer, the query answer should be given.
    @model_validator(mode='after')
    def answer_given_validation(self) -> "RouterOutput":
        if self.routing_decision == RoutingDecisions.ANSWER.value and not self.response:
            raise ValueError("The 'response' field is required when 'routing_decision' is set to 'answer'.")
        return self
        
#TODO: it should be a list, with strings 
class QueryVariations(BaseModel):
    queries : List[str]
class SearchArxiv(Event):
    payload: str
class SearchReference(Event):
    payload: str
# create the flow.
class ResearchAssistant(Workflow):
    
 
    
    def __init__(self,*args: Any,**kwargs: Any ):
        super().__init__(*args, **kwargs)
        # prepare mlflow for experiment tracking.
        # mlflow.openai.autolog()
        # mlflow.set_tracking_uri(MLFLOW["URL"])
        # mlflow.set_experiment(MLFLOW["EXPERIMENT"])
       
        self.llm = OpenAILike(model=LLM_SETTINGS["MODEL_NAME"], temperature=LLM_SETTINGS["TEMPERATURE"], api_base=LLM_SETTINGS["URL"],is_chat_model=True)
        self.client = setup_milvus()
        self.date = str(datetime.date.today())
    @step
    async def router_agent(self, ev: StartEvent) -> SearchArxiv | SearchReference | StopEvent:
        try:
            query = ev.query
            prompt_template = RichPromptTemplate(f"""
            Carefully read the user query and classify it into exactly one of the following routing decisions:

{RoutingDecisions.REFERENCE_SEARCH.value} — Use when the user wants to search, retrieve, inspect, or identify information from the reference list/bibliography of a specific scientific paper.
{RoutingDecisions.ARXIV_SEARCH.value} — Use when the user wants to search for scientific research, papers, or literature on a specific topic, including requests to find relevant papers on arXiv.
{RoutingDecisions.ANSWER.value} — Use when the query is not primarily a scientific-literature search request, such as general knowledge questions, explanations, summaries, reasoning, or other requests that can be answered directly without searching paper references or arXiv.
Classification rules
Choose exactly one routing decision.
Prioritize the user's primary intent, not individual keywords.
If the user explicitly asks to search the references/bibliography of a paper, choose REFERENCE_SEARCH.
If the user asks to find scientific papers or research about a topic, choose ARXIV_SEARCH.
Otherwise, choose ANSWER.
Query

{{query}}

Output

Return only the selected routing decision. Do not provide an explanation or any additional text.""")
            llm_answer = self.llm.structured_predict(
                RouterOutput, prompt_template, query=query
            )
            print(llm_answer.routing_decision)
            if llm_answer.routing_decision == RoutingDecisions.ARXIV_SEARCH.value:
                print("search Arxiv")
                return SearchArxiv(payload=query)
            elif llm_answer.routing_decision == RoutingDecisions.REFERENCE_SEARCH.value:
                print("search reference")
                return SearchReference(payload=query)
            
            return StopEvent(result=llm_answer.response)
        except Exception as e:
            print(e)
            sys.exit(1)
            

    @step
    async def search_reference(self,ev: SearchReference) -> StopEvent:
        query = ev.payload
        return StopEvent(result=f"Search_Reference, this is your query: {query}")
        #input("please provide the name of the paper that contain the reference")
        # TODO: this need different handling, this is controled by the rag storage.
        # this could be multiple steps.
        # 1- limit the search to the chunks related to the selected paper that contain the referece.
        # 2- identify the refernce number based on the user question. 
        # 3- get the link from the reference pages based on the reference number retrived in step 2.
        # 4- download, add to rag and answer the user origianl question.
        
    @step
    async def RAG_search(self,ev: SearchArxiv) -> StopEvent:
        print("start searching the database")
        # search milvus for the query, if not found or with low similarity download more papers.
        query = ev.payload
        highest_similarity = 0
        # Get stats
        stats = self.client.get_stats()
        print(f"Collection stats: {stats}")
    
        
        # Query
        rag_results = self.client.search(query=query)
        # order by similarity to the query
        rag_results = sorted(rag_results,key=lambda d: d['distance'],reverse=True)
        #print(f"Query results: {results}")
        if rag_results != []:
            highest_similarity = rag_results[0].get("distance",0)
        if highest_similarity < SIMILARITY_THRESHOLD:
            print("download new information")
            rag_results = "start downloading"
            # query expansion
            # download and build the rag.
        return StopEvent(result=rag_results)
        # TODO
        # 1- order by similarity (done)
        # 2- check if above threshold then generate the answer (done)
        # 3- if below a threshold then download papers and create rag
        # 4- then search and generate answers.
        # query expansion, I belive this should be used at all times to improve retrival.
        # TODO: FUTURE
        # how to prevent downloading the same papers or stuck searching with the same keywords and retriving the same results.
        # what about the abstract, when quering the arxiv for papers.???
    def query_expansion(self,query,limit,task):
        """Create variations of the user query to improve the retrival
        query (str): user query.
        limit (int): number of enhanced versions of the query.
        """
        prompt_template = RichPromptTemplate("""
    {% chat role="system" %}
Today date: {{date}}
        Optimize the following user query by generating up to {{limit}} alternative versions for {{task}} search.

Requirements:

Preserve the original intent and meaning.
Increase coverage by adding relevant context, synonyms, related concepts, and useful search terms.
Improve coherence, clarity, and specificity.
Each version should explore a meaningfully different angle while remaining faithful to the original query.
Avoid unnecessary verbosity, repetition, or invented assumptions.
Return only the optimized queries as a list.
Do not include explanations, labels, numbering, or commentary.
{% endchat %}
{% chat role="user" %}
Input query:
{{query}}
{% endchat %}
        """)
        prompt = prompt_template.format_messages(query=query, limit=limit, task=task, date=self.date)
        print(prompt)
        llm_answer = self.llm.structured_predict(
            QueryVariations, prompt_template, query=query,limit=limit,task=task,date=self.date
        )
        #TODO: let the query expansion set filter for arxiv search. it could chat with the user to confirm the search filters before starting.
        print(type(llm_answer))
        print(llm_answer)
async def main():
    flow = ResearchAssistant(verbose=True)
    while(True):
        query=input()
        result = await flow.run(query=query)
        print(result)
        print("*"*50)
if __name__ == "__main__":
    # query = input("what is your question: ")
    # print(call_llm(query))
    #asyncio.run(main())
    flow = ResearchAssistant(verbose=True)
    query = "what is the current trends in AI"
    limit = 3
    task="arxiv website"
    flow.query_expansion(query, limit,task)

# future work
# different managemnt of references
# decide what new papers to download that is not present in the database. it could get stuck downloading the same set of papers.
    
    