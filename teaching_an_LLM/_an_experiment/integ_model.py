import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))) #appending parent folder to sys path so that modules can be imported from there

from database import memory_manager
from prompt_manager2 import Prompt_manager
import json

from logger import get_logger
logger = get_logger(__name__)

class IntegratedModel():
    """
    this class implements an integrated LLM model object that integrates both persistent situation aware memory and raw LLM.
    """
    def __init__(self, index_path:str, meta_path:str, max_history_length:int):
        """
        args:
            index_path - path to store memory vector index
            meta_path - metadata path to store memory with metadata
            max_history_len - max conversation history to keep up
        """
        # initialize LLM model
        import llm.llm_model as llm_model
        self.llm_model = llm_model
        self.llm_model.Prepare_llm()

        # initialize memory
        from database.memory_manager import MemoryManager
        self.index_path = index_path
        self.meta_path = meta_path
        self.mem_manager = MemoryManager(index_path=self.index_path, meta_path=self.meta_path)

        # initialize prompt manager
        from prompt.general_instr import get_general_instruction

        self.max_history_length = max_history_length

        self.prompt = []

        self.system_content = get_general_instruction()
        self.prompt.append({"role": "system", "content": self.system_content})

        logger.info("initialization of integrated model successful")

    ############################
    #### prompt management
    ############################

    def append_prompt(self, role:str, content):
        """
        args:
            content - not a string
        """
        content = json.dumps(content)
        self.prompt.append({"role": role, "content": content})
        self.check_length()
    
    def check_length(self):
        """
        check the length of the prompt and trim it if it exceeds the max length
        """
        if (len(self.prompt) > self.max_history_length):
            # remove the oldest entry from the prompt
            self.prompt.pop(1) # not zero as removing the first entry is the system content
            logger.info(f"prompt history length exceeded {self.max_history_length}, removed the oldest entry")
        else:
            logger.debug(f"prompt history length: {len(self.prompt)}")
        pass        

    def get_prompt(self):
        """
        returns the full prompt to be passed to the LLM.
        """ 
        # print(f">>>>>>>>>>>>>>>>> total prompt: {self.prompt}")
        return self.prompt

    #############################
    #### llm response management
    #############################

    def ask_query(self, query:str):
        # ask query to the model
        self.append_prompt(role="user", content=query)

        response, token_count = self.llm_model.generate_response(self.get_prompt()) # call the LLM model to get the response
        response_dict = json.loads(response) # data is a dictionary object
        self.append_prompt(role="assistant", content=response_dict)

        final_answer = response_dict["final_answer"]

        # process response to get query answers from memory if final answer is not ready
        if (final_answer) is None:
            logger.info(f"""draft answer: {response_dict["draft_answer"]}""")
        
            mod_response_dict = self.process_response(response_dict)  

            # re ask llm      
            self.append_prompt(role="user", content=mod_response_dict)
            response2, token_count2 = self.llm_model.generate_response(self.get_prompt())
            response_dict2 = json.loads(response2) # data is a dictionary object
            self.append_prompt(role="assistant", content=response_dict2)

            # get final answer
            final_answer = response_dict2["final_answer"]
        
        return final_answer

    def process_response(self, response_dict:dict):
        """
        args:
            response - raw llm response to be processed according to the format of the response, pass after json.loads
        """
        # processing response
        draft_ans = response_dict["draft_answer"]
        chunks = response_dict["chunks"]
       

        if chunks is None:
            # there is no chunkifying, so assuming final answer is ready and no processing is necessary
            return response_dict 
        else:
            mod_chunks = [] # list to hold the modified chunks with RAG query answer
            total_memory_size = 0  

            for i, chunk_data in enumerate(chunks):
                chunk = chunk_data.get("chunk", "No chunk provided")
                RAG_query = chunk_data.get("RAG_query", "No RAG_query provided")

                logger.info(f"Processing chunk {i + 1}: {chunk}")
                logger.info(f"Associated RAG query: {RAG_query}")

                memories, distances = self.mem_manager.get_memory(RAG_query, top_n=1) #memories is a list of dict of format: [{"id":"<>", "content":"<>"},{...},...]

                merged_memory = "\n".join(
                f"[{mem.get('id', 'No ID')}]: {mem.get('content', '')}" for mem in memories
            )
                
                # print(merged_memory)

                # logging memory size (token count)
                mem_size = self.llm_model.count_tokens(merged_memory)
                total_memory_size = total_memory_size + mem_size
                logger.info(f"extracted memory for chunk {i}. memory size: {mem_size} tokens.")

                chunk_data["answer_to_RAG_query"] = merged_memory
                mod_chunks.append(chunk_data)

        # print(f"modified chunk: {mod_chunks}")

        logger.info(f"total extracted memory size: {total_memory_size} tokens")

        response_dict["chunks"] = mod_chunks # this is the modified response_dict with all the rag answers added

        return response_dict



if __name__ == "__main__":
    # index and meta path for the ngspice manual rag db
    index_path1 = r"H:\NOTHING\#Projects\bring_ckt_to_life_project\code\teaching_an_LLM\_an_experiment\memory\ngspice_index.faiss" 
    meta_path1 = r"H:\NOTHING\#Projects\bring_ckt_to_life_project\code\teaching_an_LLM\_an_experiment\memory\ngspice_meta.npy"

    # index and meta path for my curated memory
    index_path2 = r"H:\NOTHING\#Projects\bring_ckt_to_life_project\code\teaching_an_LLM\_an_experiment\memory\curated_memory.faiss" 
    meta_path2 = r"H:\NOTHING\#Projects\bring_ckt_to_life_project\code\teaching_an_LLM\_an_experiment\memory\curated_memory_meta.npy"


    integ_model = IntegratedModel(index_path=index_path2 , meta_path=meta_path2, max_history_length=30)

    ans = integ_model.ask_query("give me an example ngspice netlist code for measuring the current accross a resistor in an RC circuit with 2 resistors in parallel.")
    print(ans)

    

    