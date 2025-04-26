import os
import glob
import numpy as np
import faiss
from openai import AzureOpenAI  
from azure.core.credentials import AzureKeyCredential
import dotenv
from typing import List, Dict
import RAG_db_creation as crag

# Globals to be configured
DATA_DIR = "subchapter_summaries"
INDEX_PATH = None
META_PATH = None
EMBED_MODEL = None
API_KEY = None
ECLIENT = None
REQ = True
docs = None
index = None
meta = None


def Prepare_RAG_DBQ(
    data_dir = None,
    index_path = None,
    meta_path = None,
    requery = False
):
    """
    Set up global file paths, API key, and model identifiers for embeddings and chat completions.
    """
    dotenv.load_dotenv()

    global DATA_DIR, INDEX_PATH, META_PATH, EMBED_MODEL, API_KEY, REQ, docs, index, meta
    if data_dir != None:
        DATA_DIR = data_dir
    if index_path != None:
        INDEX_PATH = index_path
    if meta_path != None:
        META_PATH = meta_path
    REQ = requery

    EMBED_MODEL = os.getenv("AZURE_E3L_DEPLOYMENT")
    API_KEY = os.getenv("AZURE_E3L_API_KEY")

    print(f"Configured LLM with embed_model={EMBED_MODEL}")

    docs = load_documents(DATA_DIR)
    crag.Prepare_RAG_DB(DATA_DIR, INDEX_PATH, META_PATH)
    index, meta = crag.build_or_load_index()


def load_documents(data_dir: str) -> List[Dict]:
    """
    Load each .txt file in the data directory as a document.
    Returns a list of dicts with keys: 'id' and 'content'.
    """
    docs = []
    for filepath in glob.glob(os.path.join(data_dir, "*.txt")):
        with open(filepath, 'r', encoding="utf-8") as f:
            content = f.read().strip()
        docs.append({
            "id": os.path.basename(filepath),
            "content": content
        })
    return docs



def rewrite_query(query: str) -> str:
    """
    Rewrite the user query into a concise, keyword-rich
    search prompt using Azure's 'o3-mini' chat model.
    """
    prompt = (
        "You are a helpful assistant specialized in SPICE queries. "
        "Rewrite the following user query into a concise, keyword-rich "
        "search query for document retrieval."
        f"\n\nUser Query: {query}"
    )

    azure_client = AzureOpenAI(
        api_version= os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint= os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_API_KEY")
    )

    resp = azure_client.chat.completions.create(
        model= os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": "Query rewriter for NGSpice documentation."},
            {"role": "user",   "content": prompt}
        ],
        temperature=0.0
    )

    # AzureOpenAI mirrors the OpenAI shape:
    return resp.choices[0].message.content.strip()



def retrieve_docs(query, top_n = 1):
    """
    Given a raw user query, rewrite it, embed it, and return the top_n matching documents.
    """
    global meta, index

    if REQ:
        query = rewrite_query(query)
    
    q_emb = np.array(crag.embed_text(query)).astype('float32').reshape(1, -1)
    distances, indices = index.search(q_emb, top_n)
    return [meta[i] for i in indices[0]]


if __name__ == "__main__":
    # Example initialization
    Prepare_RAG_DBQ(
        index_path="./DB/ngspice_index.faiss",
        meta_path="./DB/ngspice_meta.npy"
    )
    user_query = "How can I add a current source to an existing netlist component?"
    top_docs = retrieve_docs(user_query, top_n=2)
    print("Top relevant documents:")
    for d in top_docs:
        print(f"- {d['id']}")
