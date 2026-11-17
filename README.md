## AI Research Assistant
## Objective

The objective of this project is to develop an agentic AI research assistant that enables users to explore scientific literature through natural language conversations. The system automatically discovers relevant research papers based on a user's topic of interest, downloads and processes the papers, and constructs a Retrieval-Augmented Generation (RAG) for intelligent question answering.

Unlike traditional paper search tools, the system employs multiple specialized agents to autonomously determine the most appropriate action for each user query, including searching for newly published papers, retrieving information from the existing knowledge base, or traversing paper citations to acquire additional context. 

The long-term objective of this project is to give the assistant the abilities to provide concise research summaries, compares related works, identifies research trends and gaps, and supports interactive exploration of scientific literature, helping researchers efficiently understand and stay up to date with rapidly evolving research domains.


### Built with
* [GROBID](https://grobid.readthedocs.io)
* [Milvus](https://milvus.io/)
* [Llamaindex](https://www.llamaindex.ai)


## Getting Started




## Roadmap

> **Development Status:** This project is under active development.
> Some of the described objectives and features are not yet implemented.
> Features may change as development progresses.

This roadmap reflect the current plan for the project. it may change overtime as development progresses and new ideas or requirements emerge.
#### Sprint 1
[x] ntegrate the arXiv API to discover and retrieve relevant scientific papers. <br>
[x] Download research papers using metadata obtained from arXiv.<br>
[x] Process and parse scientific papers using GROBID for structured information extraction.<br>
[x] Chunk parsed documents based on XML structure to preserve semantic context while maintaining compact text segments.<br>
[x] Store document chunks in Milvus to enable vector-based semantic search.<br>
#### Sprint 2
[] Implement a routing agent to intelligently coordinate and delegate tasks to specialized agents.<br>
[] Develop arXiv query expansion to improve research discovery and retrieve more relevant papers. <br>
[] mplement reference paper retrieval, downloading, and parsing to support deeper research analysis. <br>
[] Develop a user interface to enable users to interact with the application. <br>


## Contributing


This is a personal project, but suggestions, feedback, and contributions are welcome!


- Fork the repository.
- Create a new branch.
- Make your changes.
- Submit a pull request.

## License


This project is licensed under the MIT License.


Built with curiosity, creativity, and a passion for learning.
