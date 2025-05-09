from flask import Flask, request, jsonify
from flask_cors import CORS
import trafilatura
import os
import hashlib  # Import hashlib
import json  # Import json
import re  # Import the re module
import requests  # Add this import for making HTTP requests to Ollama
import numpy as np  # Add this import at the top
import faiss
import asyncio
import agent  # Adjust if your import path is different
from pathlib import Path  # <-- Added for consistent path handling

app = Flask(__name__)
CORS(app)

# Constants
CHUNKS_FILE = "all_chunks.json"
EMBEDDINGS_FILE = "chunks_embeddings.json"
CHUNK_SIZE = 256
CHUNK_OVERLAP = 40
OLLAMA_ENDPOINT = "http://localhost:11434/api/embeddings"

# Set up faiss_index directory and file paths to match mcp_server.py
ROOT = Path(__file__).parent.resolve()
INDEX_CACHE = ROOT / "faiss_index"
INDEX_CACHE.mkdir(exist_ok=True)

FAISS_INDEX_FILE = str(INDEX_CACHE / "index.bin")
FAISS_MAPPING_FILE = str(INDEX_CACHE / "metadata.json")
CACHE_META_FILE = str(INDEX_CACHE / "doc_index_cache.json")

# Load existing index or create a new one (CACHE_META equivalent)
try:
    if Path(CACHE_META_FILE).exists():
        with open(CACHE_META_FILE, "r") as f:
            url_index = json.load(f)
    else:
        url_index = {}
except Exception:
    url_index = {}

# Define directories
markdown_dir = "markdown_files"
chunks_file = "all_chunks.json"  # Single file to store all chunks
cleaned_text_dir = "cleaned_text_files"

# Ensure directories exist
os.makedirs(markdown_dir, exist_ok=True)
os.makedirs(cleaned_text_dir, exist_ok=True)

# Add these as global variables after your other constants
FAISS_INDEX = None
CHUNK_ID_TO_INDEX = {}  # Maps chunk_ids to their position in the index

def generate_hash(url: str) -> str:
    """Generates an MD5 hash of the URL."""
    return hashlib.md5(url.encode('utf-8')).hexdigest()

def clean_markdown(markdown_text: str, remove_html: bool = True) -> str:
    """Cleans the markdown text by removing HTML tags and other unwanted elements."""
    text = markdown_text

    # Replace tabs with 4 spaces
    text = text.replace("\t", "    ")

    # Ensure space after heading hashes
    text = re.sub(r"^(#+)([^ ]|$)", r"\1 ", text, flags=re.MULTILINE)

    # Remove raw HTML tags if requested
    if remove_html:
        text = re.sub(r"<[^>]+>", "", text)

    # Remove Markdown links
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)

    # Remove standalone URLs
    text = re.sub(r"https?://\S+", "", text)

    # Remove angle bracketed URLs
    text = re.sub(r"<https?://\S+>", "", text)

    # Remove duplicate blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Ensure blank lines before and after headings
    text = re.sub(r"(?<!\n)(^#+ .*)", r"\n\1", text, flags=re.MULTILINE)
    text = re.sub(r"(^#+ .*)(?!\n)", r"\1\n", text, flags=re.MULTILINE)

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Remove tables
    text = re.sub(r"\|.*?\|", "", text) 

    return text

def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    Split text into overlapping chunks.
    Args:
        text (str): Text to be chunked
        size (int): Size of each chunk in words
        overlap (int): Number of overlapping words between chunks
    Returns:
        generator: Yields text chunks
    """
    words = text.split()
    for i in range(0, len(words), size - overlap):
        yield " ".join(words[i:i+size])

def load_existing_chunks():
    """Load existing chunks from the chunks file."""
    try:
        if not os.path.exists(CHUNKS_FILE):
            print(f"Warning: {CHUNKS_FILE} does not exist yet")
            return []
            
        with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
            chunks = json.load(f)
            print(f"Successfully loaded {len(chunks)} chunks from {CHUNKS_FILE}")
            return chunks
    except Exception as e:
        print(f"Error loading {CHUNKS_FILE}: {str(e)}")
        return []

def save_chunks(chunks):
    """Save chunks to the chunks file."""
    with open(CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=4)

def get_embedding(text: str) -> list[float]:
    """
    Get embeddings for a text using Ollama's Nomic embedding model.
    
    Args:
        text (str): The text to generate embeddings for
        
    Returns:
        list[float]: The embedding vector
        
    Raises:
        HTTPException: If the embedding request fails
    """
    try:
        response = requests.post(
            OLLAMA_ENDPOINT,
            json={
                "model": "nomic-embed-text",
                "prompt": text
            }
        )
        
        if response.status_code == 200:
            return response.json()["embedding"]
        else:
            raise Exception(
                f"Embedding request failed with status {response.status_code}"
            )
    except Exception as e:
        raise Exception(
            f"Failed to generate embedding: {str(e)}"
        )

def process_chunk_with_embedding(chunk_text: str, chunk_id: str, url: str) -> dict:
    """
    Process a single chunk of text by adding embedding and metadata.
    
    Args:
        chunk_text (str): The text content of the chunk
        chunk_id (str): The unique identifier for the chunk
        url (str): The source URL
        
    Returns:
        dict: Chunk data including text, embedding, and metadata
    """
    embedding = get_embedding(chunk_text)
    
    return {
        "chunk_id": chunk_id,
        "url": url,
        "chunk_text": chunk_text,
        "embedding": embedding
    }

@app.route("/", methods=["GET"])
def root():
    url = request.args.get("url")
    if url:
        try:
            # 1. Download and process the URL
            downloaded = trafilatura.fetch_url(url)
            text = trafilatura.extract(downloaded, output_format='markdown')
            # print("inside try" + text)
            # 2. Save the downloaded markdown
            downloaded_dir = markdown_dir
            os.makedirs(downloaded_dir, exist_ok=True)
            downloaded_filename = f"{generate_hash(url)}_downloaded.md"
            downloaded_filepath = os.path.join(downloaded_dir, downloaded_filename)
            with open(downloaded_filepath, "w", encoding="utf-8") as f:
                f.write(text)

            # 3. Clean and chunk the text
            cleaned_text = clean_markdown(text)
            url_hash = generate_hash(url)
            
            # 4. Process chunks
            existing_chunks = load_existing_chunks()
            existing_chunks = [chunk for chunk in existing_chunks if chunk['url'] != url]
            
            new_chunks = []
            for i, chunk in enumerate(chunk_text(cleaned_text)):
                chunk_id = f"{url_hash}_chunk_{i}"
                chunk_data = {
                    "chunk_id": chunk_id,
                    "url": url,
                    "chunk_text": chunk
                }
                new_chunks.append(chunk_data)
            
            all_chunks = existing_chunks + new_chunks
            save_chunks(all_chunks)

            # 5. Generate embeddings
            embeddings_data = load_existing_embeddings()
            newly_processed = 0
            failed_chunks = []
            print("new chunks" + str(new_chunks))
            for chunk in new_chunks:  # Only process new chunks
                chunk_id = chunk["chunk_id"]
                try:
                    embedding = get_embedding(chunk["chunk_text"])
                    embeddings_data[chunk_id] = {
                        "embedding": embedding,
                        "url": chunk["url"]
                    }
                    newly_processed += 1
                except Exception as e:
                    failed_chunks.append({
                        "chunk_id": chunk_id,
                        "error": str(e)
                    })
            
            save_embeddings(embeddings_data)

            # 6. Initialize/Update FAISS index
            if initialize_faiss_index():
                save_faiss_index()

            # 7. Update URL index
            url_index[url] = url_hash        
            with open(CACHE_META_FILE, "w") as f:
                json.dump(url_index, f)

            # 8. Return comprehensive results
            return jsonify({
                "message": f"Processed {url}",
                "details": {
                    "markdown_file": downloaded_filename,
                    "chunks_created": len(new_chunks),
                    "total_chunks": len(all_chunks),
                    "embeddings_generated": newly_processed,
                    "failed_embeddings": len(failed_chunks),
                    "failed_chunk_ids": [f["chunk_id"] for f in failed_chunks],
                    "faiss_index_updated": True
                }
            })

        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"message": "Hello World"})

def load_existing_embeddings():
    """Load existing embeddings if they exist."""
    try:
        if not os.path.exists(EMBEDDINGS_FILE):
            return {}
        with open(EMBEDDINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_embeddings(embeddings_data):
    """Save embeddings to the embeddings file."""
    with open(EMBEDDINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(embeddings_data, f, ensure_ascii=False, indent=4)

@app.route("/generate-embeddings", methods=["GET"])
def generate_embeddings_for_chunks():
    """
    Generate embeddings for chunks and store them in a separate file.
    """
    try:
        # Load existing chunks
        existing_chunks = load_existing_chunks()
        
        if not existing_chunks:
            return jsonify({
                "message": f"No chunks found in {CHUNKS_FILE}",
                "chunks_processed": 0
            })
        
        # Load existing embeddings
        embeddings_data = load_existing_embeddings()
        
        # Process each chunk
        newly_processed = 0
        failed_chunks = []
        
        for chunk in existing_chunks:
            chunk_id = chunk["chunk_id"]
            
            # Skip if embedding already exists
            if chunk_id in embeddings_data:
                print(f"Embedding already exists for chunk {chunk_id}")
                continue
                
            try:
                # Generate embedding for the chunk
                embedding = get_embedding(chunk["chunk_text"])
                
                # Store embedding with minimal metadata
                embeddings_data[chunk_id] = {
                    "embedding": embedding,
                    "url": chunk["url"]
                }
                
                newly_processed += 1
                print(f"Successfully generated embedding for chunk {chunk_id}")
                
            except Exception as e:
                print(f"Failed to process chunk {chunk_id}: {str(e)}")
                failed_chunks.append({
                    "chunk_id": chunk_id,
                    "error": str(e)
                })
        
        # Save updated embeddings
        save_embeddings(embeddings_data)
        
        return jsonify({
            "message": "Embeddings generation complete",
            "details": {
                "total_chunks": len(existing_chunks),
                "total_embeddings": len(embeddings_data),
                "newly_processed": newly_processed,
                "failed_chunks": len(failed_chunks),
                "failed_chunk_ids": [f["chunk_id"] for f in failed_chunks]
            }
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Failed to process chunks: {str(e)}"
        }), 500

@app.route("/embeddings-status", methods=["GET"])
def check_embeddings_status():
    """
    Check the status of embeddings generation
    """
    try:
        chunks = load_existing_chunks()
        embeddings = load_existing_embeddings()
        
        chunks_without_embeddings = [
            chunk["chunk_id"] 
            for chunk in chunks 
            if chunk["chunk_id"] not in embeddings
        ]
        
        return jsonify({
            "total_chunks": len(chunks),
            "total_embeddings": len(embeddings),
            "chunks_without_embeddings": len(chunks_without_embeddings),
            "pending_chunk_ids": chunks_without_embeddings
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Failed to check status: {str(e)}"
        }), 500

@app.route("/get-chunk-embedding/<chunk_id>", methods=["GET"])
def get_chunk_embedding(chunk_id: str):
    """
    Retrieve embedding for a specific chunk
    """
    try:
        embeddings = load_existing_embeddings()
        
        if chunk_id not in embeddings:
            return jsonify({
                "error": f"No embedding found for chunk {chunk_id}"
            }), 404
            
        return jsonify(embeddings[chunk_id])
        
    except Exception as e:
        return jsonify({
            "error": f"Error retrieving embedding: {str(e)}"
        }), 500

# Add a new endpoint to verify the contents of all_chunks.json
@app.route("/verify-chunks", methods=["GET"])
def verify_chunks():
    """
    Verify the contents of all_chunks.json file
    """
    try:
        if not os.path.exists(CHUNKS_FILE):
            return jsonify({
                "status": "error",
                "message": f"File {CHUNKS_FILE} does not exist",
                "file_path": os.path.abspath(CHUNKS_FILE)
            })
            
        with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
            chunks = json.load(f)
            
        return jsonify({
            "status": "success",
            "file_path": os.path.abspath(CHUNKS_FILE),
            "total_chunks": len(chunks),
            "sample_chunk": chunks[0] if chunks else None,
            "file_size": os.path.getsize(CHUNKS_FILE)
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "file_path": os.path.abspath(CHUNKS_FILE)
        })

@app.route("/get-faiss-data", methods=["GET"])
def get_faiss_data():
    """
    Get embeddings and chunk IDs in a format suitable for FAISS.
    Returns:
        - embeddings: list of embeddings as numpy array
        - chunk_ids: list of chunk IDs in the same order as embeddings
    """
    try:
        # Load embeddings
        embeddings_data = load_existing_embeddings()
        
        if not embeddings_data:
            return jsonify({
                "message": "No embeddings found",
                "embeddings": [],
                "chunk_ids": []
            })
        
        # Create ordered lists of embeddings and chunk IDs
        chunk_ids = []
        embeddings_list = []
        
        for chunk_id, data in embeddings_data.items():
            chunk_ids.append(chunk_id)
            embeddings_list.append(data["embedding"])
            
        # Convert to numpy array for FAISS
        embeddings_array = np.array(embeddings_list, dtype=np.float32)
        
        return jsonify({
            "embeddings": embeddings_array.tolist(),  # Convert numpy array to list for JSON serialization
            "chunk_ids": chunk_ids
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Failed to prepare FAISS data: {str(e)}"
        }), 500

@app.route("/get-chunks-by-ids", methods=["GET"])
def get_chunks_by_ids(chunk_ids: list[str]):
    """
    Get original chunk texts for given chunk IDs.
    """
    try:
        chunks = load_existing_chunks()
        chunk_dict = {chunk["chunk_id"]: chunk["chunk_text"] for chunk in chunks}
        
        results = {}
        for chunk_id in chunk_ids:
            if chunk_id in chunk_dict:
                results[chunk_id] = chunk_dict[chunk_id]
                
        return jsonify(results)
        
    except Exception as e:
        return jsonify({
            "error": f"Failed to retrieve chunks: {str(e)}"
        }), 500

@app.route("/get-embedding", methods=["POST"])
def get_query_embedding():
    """
    Get embedding for query text
    """
    try:
        data = request.get_json()
        text = data.get("text")
        if not text:
            return jsonify({"error": "No text provided"}), 400
        embedding = get_embedding(text)
        return jsonify({
            "embedding": embedding
        })
    except Exception as e:
        return jsonify({
            "error": f"Failed to generate embedding: {str(e)}"
        }), 500

def save_faiss_index(metadata_list=None):
    """
    Save FAISS index and metadata to files
    """
    global FAISS_INDEX, CHUNK_ID_TO_INDEX
    
    try:
        if FAISS_INDEX is None:
            print("No FAISS index to save")
            return False
            
        # Save FAISS index
        faiss.write_index(FAISS_INDEX, FAISS_INDEX_FILE)
        
        # Save metadata (doc, chunk, chunk_id)
        metadata = {
            "chunk_mapping": CHUNK_ID_TO_INDEX,
            "metadata": metadata_list if metadata_list else []
        }
        
        with open(FAISS_MAPPING_FILE, "w") as f:
            json.dump(metadata, f, indent=4)
            
        print(f"Successfully saved FAISS index to {FAISS_INDEX_FILE}")
        return True
        
    except Exception as e:
        print(f"Error saving FAISS index: {str(e)}")
        return False

def load_faiss_index():
    """
    Load FAISS index and metadata from files
    """
    global FAISS_INDEX

    try:
        if not os.path.exists(FAISS_INDEX_FILE) or not os.path.exists(FAISS_MAPPING_FILE):
            print("FAISS index files not found")
            return False

        # Load FAISS index
        FAISS_INDEX = faiss.read_index(FAISS_INDEX_FILE)

        # Load metadata (as a list of dicts)
        with open(FAISS_MAPPING_FILE, "r") as f:
            metadata_list = json.load(f)

        print(f"Successfully loaded FAISS index with {FAISS_INDEX.ntotal} vectors")
        return metadata_list

    except Exception as e:
        print(f"Error loading FAISS index: {str(e)}")
        return None

def initialize_faiss_index():
    """
    Initialize FAISS index from existing embeddings file and save it with doc and chunk information
    """
    global FAISS_INDEX, CHUNK_ID_TO_INDEX
    
    try:
        # Load embeddings
        embeddings_data = load_existing_embeddings()
        if not embeddings_data:
            print("No embeddings found to create FAISS index")
            return False
            
        # Load all chunks to get chunk text
        all_chunks = load_existing_chunks()
        chunk_text_lookup = {chunk["chunk_id"]: chunk["chunk_text"] for chunk in all_chunks}
        
        # Create lists for embeddings and metadata
        embeddings_list = []
        metadata_list = []  # Store doc, chunk, chunk_id
        
        # Convert dictionary to ordered lists
        for chunk_id, data in embeddings_data.items():
            embeddings_list.append(data["embedding"])
            metadata_list.append({
                "doc": data["url"],  # Rename url to doc
                "chunk": chunk_text_lookup.get(chunk_id, ""),  # Add chunk text
                "chunk_id": chunk_id
            })
            CHUNK_ID_TO_INDEX[chunk_id] = len(metadata_list) - 1
        
        # Convert to numpy array
        embeddings_array = np.array(embeddings_list, dtype=np.float32)
        
        # Create and populate FAISS index
        dimension = len(embeddings_array[0])
        FAISS_INDEX = faiss.IndexFlatL2(dimension)
        FAISS_INDEX.add(embeddings_array)
        
        # Save the index and metadata
        save_faiss_index(metadata_list)
        
        print(f"Successfully created FAISS index with {len(metadata_list)} embeddings")
        return True
        
    except Exception as e:
        print(f"Error creating FAISS index: {str(e)}")
        return False

@app.route("/search", methods=["GET"])
def search():
    """Search endpoint with doc and chunk information"""
    try:
        # Load FAISS index if not loaded
        global FAISS_INDEX
        if FAISS_INDEX is None:
            metadata_list = load_faiss_index()
            if not metadata_list:
                if not initialize_faiss_index():
                    return jsonify({
                        "error": "Failed to initialize FAISS index"
                    }), 500
                metadata_list = load_faiss_index()
        else:
            metadata_list = load_faiss_index()
        
        # Get query embedding and search
        query = request.args.get("query")
        k = int(request.args.get("k", 5))
        query_embedding = get_embedding(query)
        query_array = np.array([query_embedding], dtype=np.float32)
        distances, indices = FAISS_INDEX.search(query_array, k)
        
        # Get results with doc and chunk
        results = []
        for i, idx in enumerate(indices[0]):
            if not isinstance(idx, (int, np.integer)) or idx < 0 or idx >= len(metadata_list):
                continue
            metadata = metadata_list[idx]
            chunk_id = metadata["chunk_id"]
            doc = metadata["doc"]
            chunk_text = metadata["chunk"]
            
            results.append({
                "chunk_id": chunk_id,
                "text": chunk_text,
                "doc": doc,
                "distance": float(distances[0][i])
            })
        
        return jsonify({
            "query": query,
            "results": results
        })
        
    except Exception as e:
        return jsonify({
            "error": f"Search failed: {str(e)}"
        }), 500

# Add endpoint to refresh FAISS index
@app.route("/refresh-index", methods=["POST"])
def refresh_faiss_index():
    """
    Rebuild the FAISS index from current embeddings
    """
    try:
        if initialize_faiss_index():
            return jsonify({"message": "FAISS index successfully refreshed"})
        else:
            return jsonify({
                "error": "Failed to refresh FAISS index"
            }), 500
    except Exception as e:
        return jsonify({
            "error": f"Error refreshing index: {str(e)}"
        }), 500

# Add endpoints to manage FAISS index persistence
@app.route("/save-index", methods=["POST"])
def save_index():
    """
    Save current FAISS index to file
    """
    try:
        if save_faiss_index():
            return jsonify({"message": "FAISS index successfully saved"})
        else:
            return jsonify({
                "error": "Failed to save FAISS index"
            }), 500
    except Exception as e:
        return jsonify({
            "error": f"Error saving index: {str(e)}"
        }), 500

@app.route("/load-index", methods=["POST"])
def load_index():
    """
    Load FAISS index from file
    """
    try:
        if load_faiss_index():
            return jsonify({"message": "FAISS index successfully loaded"})
        else:
            return jsonify({
                "error": "Failed to load FAISS index"
            }), 500
    except Exception as e:
        return jsonify({
            "error": f"Error loading index: {str(e)}"
        }), 500

@app.route("/agent-search", methods=["POST"])
def agent_search():
    data = request.get_json()
    query = data.get("query")
    if not query:
        return jsonify({"error": "No query provided"}), 400
    try:
        result = asyncio.run(agent.main(query))
        if not isinstance(result, str):
            result = str(result)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=8000, debug=True)
