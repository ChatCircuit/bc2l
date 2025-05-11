import os
import glob
import numpy as np
import faiss
from openai import AzureOpenAI  
from azure.core.credentials import AzureKeyCredential
import dotenv
from typing import List, Dict


# Globals to be configured
DATA_DIR: str
INDEX_PATH: str
META_PATH: str
EMBED_MODEL: str
API_KEY: str
API_VER: str
ENDPNT: str
ECLIENT = None
docs = None
index = None
meta = None


def Prepare_RAG_DB(
    data_dir: str,
    index_path: str,
    meta_path: str,
):
    """
    Set up global file paths, API key, and model identifiers for embeddings and chat completions.
    """
    dotenv.load_dotenv()
    global DATA_DIR, INDEX_PATH, META_PATH, EMBED_MODEL, API_KEY, API_VER, ENDPNT, ECLIENT, docs, index, meta
    DATA_DIR = data_dir
    INDEX_PATH = index_path
    META_PATH = meta_path
    EMBED_MODEL = os.getenv("AZURE_E3L_DEPLOYMENT")
    API_KEY = os.getenv("AZURE_E3L_API_KEY")
    API_VER = os.getenv("AZURE_E3L_API_VERSION")
    ENDPNT = os.getenv("AZURE_E3L_ENDPOINT")
    ECLIENT = AzureOpenAI(
            api_version= API_VER,
            azure_endpoint= ENDPNT,
            api_key= API_KEY
        )
    #print(f"Configured LLM with embed_model={EMBED_MODEL}")

    print("data path = ", DATA_DIR)
    print("index path = ", INDEX_PATH)
    print("meta path = ", META_PATH)

    docs = load_documents(DATA_DIR)
    index, meta = build_or_load_index(docs)


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


def embed_text(text: str) -> List[float]:
    """
    Generate an embedding vector for the given text using the configured embed_model.
    """
    resp = ECLIENT.embeddings.create(
        input=[text],
        model=EMBED_MODEL
    )
    return resp.data[0].embedding


def build_or_load_index(documents=None):
    """
    Build a FAISS index from scratch, or load existing index + metadata.
    """
    dim = 3072  # embedding dimension for text-embedding-3-large
    if os.path.exists(INDEX_PATH) and os.path.exists(META_PATH):
        index = faiss.read_index(INDEX_PATH)
        metadata = np.load(META_PATH, allow_pickle=True).tolist()
        print(f"Loaded index with {index.ntotal} vectors.")
    else:
        global docs
        if documents == None:
            documents = docs
        #embs = [embed_text(doc['content']) for doc in docs]
        embs = []
        total = len(docs)
        for idx, doc in enumerate(docs, start=1):
            embs.append(embed_text(doc['content']))
            percent_complete = int((idx / total) * 100)
            print(f"\rBuilding the Embedding DB: {percent_complete}%", end="", flush=True)
        print('\n')
        embs = np.array(embs).astype('float32')
        index = faiss.IndexFlatL2(dim)
        index.add(embs)
        faiss.write_index(index, INDEX_PATH)
        np.save(META_PATH, documents)
        metadata = documents
        print(f"Built new index with {index.ntotal} vectors.")
    return index, metadata

if __name__ == "__main__":
    text = "hello world, my name is touhid"
    emb = embed_text(text)

    print(emb)