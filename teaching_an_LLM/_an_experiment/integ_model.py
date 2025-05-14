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

    ############################
    #### prompt management
    ############################

    def append_prompt(self, role:str, content:str):
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
        return self.prompt

    #############################
    #### llm response management
    #############################

    def ask_query(self, query:str):
        # ask query to the model
        self.append_prompt(role="user", content=query)
        response, token_count = self.llm_model.generate_response(self.get_prompt) # call the LLM model to get the response

        self.process_response(response)

    def process_response(self, response:str):
        """
        args:
            response - raw llm response to be processed according to the format of the response
        """
        # processing response
        response_dict = json.loads(response) # data is a dictionary object
        draft_ans = response_dict["draft_answer"]
        chunks = response_dict["chunks"]

        


    

    