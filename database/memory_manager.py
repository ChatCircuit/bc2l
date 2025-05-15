"""
RAG based memory manager system
"""
import os, faiss
from openai import AzureOpenAI  
import numpy as np

# get logger
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) #appending parent folder to sys path so that modules can be imported from there
from logger import get_logger
logger = get_logger(__name__)

class MemoryManager:
    def __init__(self, index_path:str="emb_index.faiss", meta_path: str="emb_meta.npy"):
        """
        args:
            index_path - desiered path to index file, defaults to emb_index.faiss file
            meta_path - desired patth to store metta data

        internal properties:
            self.metadata - a list of dict of format [{"id":<>, "content":<>}, {..}, ....]

        methods:
            save_memory(data:str, save:bool=True) - for saving new memory or updating old memory
            get_memory(query:str, top_n:int) - to retreive top n number of memory using a query
        """

        self.index_path = index_path
        self.meta_path = meta_path

        # set up embedding model using api keys
        self.EMBED_MODEL = os.getenv("AZURE_E3L_DEPLOYMENT")
        API_KEY = os.getenv("AZURE_E3L_API_KEY")
        API_VER = os.getenv("AZURE_E3L_API_VERSION")
        ENDPNT = os.getenv("AZURE_E3L_ENDPOINT")

        self.ECLIENT = AzureOpenAI(
            api_version= API_VER,
            azure_endpoint= ENDPNT,
            api_key= API_KEY
        )

        logger.info(f"Configured LLM with embed_model={self.EMBED_MODEL} for RAG embedding generation")


        # setup faiss index
        if os.path.exists(self.index_path) and os.path.exists(self.meta_path):
            
            self.index = faiss.read_index(self.index_path)
            self.metadata = np.load(self.meta_path, allow_pickle=True).tolist()
            
            logger.info(f"Loaded index with {self.index.ntotal} vectors.")
        else:
            # faiss index and metadata doesn't exist, setting up an empty index from scratch
            logger.info("no index built up, setting up a new index")

            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)  # Ensure directory exists
            
            self.index = faiss.IndexFlatL2(int(os.getenv("E3L_DIM")))
            faiss.write_index(self.index, self.index_path) # empty index file
            
            self.metadata = []
            np.save(self.meta_path, self.metadata) # empty data file
            
            logger.info(f"Built new index with {self.index.ntotal} vectors at location: {os.path.abspath(self.index_path)}")
            logger.info(f"Metadata file created at location: {os.path.abspath(self.meta_path)}")


    def _embed_text(self ,text: str):
        """
        Generate an embedding vector for the given text using the configured embed_model.

        returns:
            a numpy embedding array
        """
        resp = self.ECLIENT.embeddings.create(
            input=[text],
            model=self.EMBED_MODEL
        )
        emb = np.array(resp.data[0].embedding).astype('float32') 
        emb = emb.reshape(1, -1) # faiss index expects a 2D numpy array

        return emb

    def save_memory(self, data:dict, save:bool=True):
        """
        args:
            doc - a dictionary of format {"id": <data_id>, "content": <data_text>}, if id already exists, then the content will be updated with the current data.
            save - whether to save the new embedding and data into the index and metadata file
        """
        # Check if the ID already exists in metadata
        for idx, item in enumerate(self.metadata):
            if item["id"] == data["id"]:
                logger.info(f"ID '{data['id']}' already exists in metadata. updating with new data.")
                
                # Remove metadata
                del self.metadata[idx]
                
                # Remove faiss index
                self.index.remove_ids(np.array([idx]))  # Remove the old embedding
                

        emb = self._embed_text(data["content"])
        
        # Save to faiss index
        self.index.add(emb)
        if save:
            faiss.write_index(self.index, self.index_path)

        # Save to npy metadata
        self.metadata.append(data)
        if save:
            np.save(self.meta_path, self.metadata)

        logger.info(f"Added new data to index and metadata. Saved to file: {save}")
        

    def get_memory(self, query:str, top_n:int=5):
        """
        returns:
            list of dictionary of retreived memory with id of format: [{"id":<>, "content":<>}, {..}, ...]
            and also the distances list
        """
        q_emb = np.array(self._embed_text(query)).astype('float32').reshape(1, -1)
        distances, indices = self.index.search(q_emb, top_n)
        
        # print([self.metadata[i] for i in indices[0]])

        return [self.metadata[i] for i in indices[0]], distances


if __name__ == "__main__":
    # index and meta path for the ngspice manual rag db
    index_path1 = r"H:\NOTHING\#Projects\bring_ckt_to_life_project\code\teaching_an_LLM\_an_experiment\memory\ngspice_index.faiss" 
    meta_path1 = r"H:\NOTHING\#Projects\bring_ckt_to_life_project\code\teaching_an_LLM\_an_experiment\memory\ngspice_meta.npy"

    # index and meta path for my curated memory
    index_path2 = r"H:\NOTHING\#Projects\bring_ckt_to_life_project\code\teaching_an_LLM\_an_experiment\memory\curated_memory.faiss" 
    meta_path2 = r"H:\NOTHING\#Projects\bring_ckt_to_life_project\code\teaching_an_LLM\_an_experiment\memory\curated_memory_meta.npy"

    mem_manager = MemoryManager(index_path=index_path2, meta_path=meta_path2)
    
    # data = {"id":"measuring current in ngspice", "content":"you should always use '.probe I(component_name)' in ngspice to find current through a component. do not use any other method for current measuring."}
    content = """The title line must be the first line of the netlist file or explicitly specified using a `.TITLE` statement.
Syntax: `.TITLE <any title>`"""
    data = {"id":"title line in ngspice", "content":content}

    mem_manager.save_memory(data)
    
    # mem, distances = mem_manager.get_memory("ngspice", top_n=2)

    # for i, (memory, distance) in enumerate(zip(mem, distances[0])):
    #     print(f"Memory {i + 1}: ID={memory['id']}, Content={memory['content']}, Distance={distance}")
