The project involves developing a Chrome extension(RAG) that logs websites visited, converts the content into Nomic embeddings, and stores them in a FAISS index. The extension also supports search functionality, allowing users to query and retrieve relevant information directly from the FAISS-stored data and also giving the website link from where the information was retrieved.

# RAG-BACKEND: Model Context Protocol (MCP) Based RAG System

This project implements a Retrieval-Augmented Generation (RAG) system using the Model Context Protocol (MCP) to create, store, and search through document embeddings for intelligent query responses.


## Folder Structure
RAG-BACKEND/
├── agent.py # Main agent implementation
├── action.py # Tool execution and function call parsing
├── models.py # Pydantic models for data validation
├── decision.py # Decision making and planning logic
├── perception.py # Intent and entity extraction
├── memory.py # Memory management and retrieval
├── mcp_server.py # MCP server implementation
├── rag_backend.py # Main RAG backend implementation
├── faiss_index/ # Vector storage directory
│ ├── index.bin # FAISS index file
│ ├── metadata.json # Document metadata
│ └── doc_index_cache.json # Document processing cache
├── pyproject.toml # Project dependencies
└── README.md # This file

Chrome extension:



## Dependencies

- FAISS: Vector similarity search
- Pydantic: Data validation
- MCP: Model Context Protocol implementation
- Other dependencies listed in `pyproject.toml`

## Setup

1. To install dependencies as per the `pyproject.toml` file:   

   >pip install build
   To build a Python project (using the pyproject.toml), you should navigate to the project root (where pyproject.toml is located), and then run:
   >python -m build

2. Place documents in the documents directory(faiss_index).

3. Run the backend:
   ```bash
   python rag_backend.py
   ```
