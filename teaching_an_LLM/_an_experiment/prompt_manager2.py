import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))) #appending parent folder to sys path so that modules can be imported from there

from prompt.general_instr import get_general_instruction

from logger import get_logger
logger = get_logger(__name__)


class Prompt_manager:
    def __init__(self, netlist:str, max_history_length:int=30):
        self.max_history_length = max_history_length
        self.system_content = get_general_instruction()
        
        # initialize the prompt with system content
        self.prompt = []
        self.prompt.append({"role": "system", "content": self.system_content})

        # keep up a unique task id for each user prompt
        self.task_id = 0

    def get_pretty_prompt(self):
        """
        get the prompt in a pretty format for debugging
        """
        pretty_prompt = ""
        for p in self.prompt:
            pretty_prompt += f"{p['role']}: {p['content']}\n"
        return pretty_prompt

    def get_prompt(self):
        """
        returns the full prompt to be passed to the LLM.
        """ 
        return self.prompt