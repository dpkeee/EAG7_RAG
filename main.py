import fastapi
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import httpx
import trafilatura  # Import Trafilatura
from trafilatura import extract
from trafilatura.settings import use_config
import re
import json  # Import the json module
from datetime import datetime  # Import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = FastAPI()

class TextRequest(BaseModel):
    text: str

OLLAMA_API_ENDPOINT = "http://localhost:11434/api/embeddings"  # Default Ollama API endpoint
OLLAMA_MODEL_NAME = "nomic-embed-text"  # Replace with your Nomic model name in Ollama
EMBEDDING_FILE = "embeddings.jsonl"  # File to save embeddings

# Configuration for trafilatura
newconfig = use_config(
    # extraction
    deduplicate=True,
    only_with_metadata=False,
    # filter
    include_comments=False,
    include_tables=False,
    include_images=False,
    # output
    output_format='txt',
    # logging
    loglevel=0,
)

async def generate_nomic_embedding(text: str):
    logging.info(f"Generating Nomic embedding for text: {text[:50]}...")  # Log first 50 chars
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                OLLAMA_API_ENDPOINT,
                headers={
                    "Content-Type": "application/json",
                },
                json={
                    "prompt": text,
                    "model": OLLAMA_MODEL_NAME,
                    "stream": False  # Set to False to get the full response at once
                },
                timeout=30.0
            )
            response.raise_for_status()
            logging.info(f"Ollama API response status: {response.status_code}")
            embedding = json.loads(response.text)['response']
            logging.info(f"Embedding generated successfully.")
            return embedding
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error from Ollama API: {e}")
            raise HTTPException(status_code=e.response.status_code, detail=str(e))
        except httpx.RequestError as e:
            logging.error(f"Failed to connect to Ollama API: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to connect to Ollama API: {str(e)}")
        except Exception as e:
            logging.exception(f"Unexpected error during embedding generation: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

def clean_text(text: str) -> str:
    logging.info(f"Cleaning text: {text[:50]}...")  # Log first 50 chars
    """Cleans the text by removing images, Markdown links, URLs, and extra whitespace."""

    # Remove images (Markdown syntax: ![alt text](image URL))
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)

    # Remove Markdown links ([link text](URL))
    text = re.sub(r'\[.*?\]\(.*?\)', '', text)

    # Remove bold text (Markdown syntax: **bold text**)
    text = re.sub(r'\*\*.*?\*\*', '', text)

    # Remove italic text (Markdown syntax: *italic text*)
    text = re.sub(r'\*.*?\*', '', text)

    # Remove inline code (Markdown syntax: `code`)
    text = re.sub(r'`.*?`', '', text)

    # Remove blockquotes (Markdown syntax: > quoted text)
    # This removes the leading ">" and any whitespace after it
    text = re.sub(r'^> *', '', text, flags=re.MULTILINE)

   # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    # Remove standalone URLs
    text = re.sub(r'\b(?:https?://|www\.)\S+\b', '', text)

    # Remove angle-bracketed URLs (<URL>)
    text = re.sub(r'<https?://\S+>', '', text)

    # Remove extra whitespace (multiple spaces, tabs, newlines)
    text = re.sub(r'\s+', ' ', text).strip()

    logging.info("Text cleaning complete.")
    return text

@app.post("/embeddings/")
async def create_embedding(text_request: TextRequest):
    url = text_request.text  # Extract URL for logging
    logging.info(f"Received request for URL: {url}")
    try:
        logging.info(f"Fetching URL with Trafilatura: {url}")
        downloaded = trafilatura.fetch_url(url)
        logging.info(f"Extracting text with Trafilatura from: {url}")
        cleaned_text = trafilatura.extract(downloaded, config=newconfig)

        if cleaned_text is None:
            logging.warning(f"Trafilatura could not extract text from: {url}")
            cleaned_text = ""

        logging.info(f"Cleaning extracted text from: {url}")
        cleaned_text = clean_text(cleaned_text)

        logging.info(f"Generating embedding for cleaned text from: {url}")
        embedding_data = await generate_nomic_embedding(cleaned_text)

        # Save the embedding to the file
        embedding_record = {
            "url": url,
            "timestamp": datetime.now(datetime.UTC).isoformat(),
            "embedding": embedding_data
        }
        logging.info(f"Saving embedding to file for: {url}")
        with open(EMBEDDING_FILE, "a") as f:
            f.write(json.dumps(embedding_record) + "\n")

        logging.info(f"Embedding saved to file for: {url}")
        return {"embedding": embedding_data}
    except HTTPException as e:
        logging.error(f"HTTPException: {e} for URL: {url}")
        raise e
    except Exception as e:
        logging.exception(f"Exception during processing for URL: {url}")
        raise HTTPException(status_code=500, detail=f"Error processing embedding: {str(e)}")
