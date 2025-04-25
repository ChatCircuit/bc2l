'''
create the input feed to the LLM as a string by combining user prompt, netlist, 
simulation results, and any other relevant information. 
This string will be passed to the LLM for processing.
'''

from llm.prompts.llm_general_instr import get_llm_general_instr_prompt

from logger import get_logger
logger = get_logger(__name__)


class Prompt_manager:
    def __init__(self, netlist:str, max_history_length:int=30):
        self.netlist = netlist
        self.max_history_length = max_history_length
        self.system_content = get_llm_general_instr_prompt(netlist)
        
        # initialize the prompt with system content
        self.prompt = []
        self.prompt.append({"role": "system", "content": self.system_content})

        # keep up a unique task id for each user prompt
        self.task_id = 0

    def append(self, role:str, content:str):
        """
        role: "user" | "assistant" | "system" for openai API
        """
        
        if (role == "user"):
            # append a unique task id to the user prompt
            content = f"{content} [task_id: {self.task_id}]"

        self.prompt.append({"role": role, "content": content})
        self.task_id += 1

        self.check_length()

    def check_length(self):
        """
        check the length of the prompt and trim it if it exceeds the max length
        """
        # TODO
        pass

    def get_user_prompt(self):
        """
        get the user prompt from the prompt history
        """
        user_prompt = []
        for p in self.prompt:
            if p["role"] == "user":
                user_prompt.append(p["content"])
        return user_prompt
    
    def get_prompt(self): 
        return self.prompt



###########################################################ty#########
if __name__ == "__main__":
    # while running as a script, set import line: from llm.prompts.llm_general_instr import get_llm_general_instr_prompt
    # to from prompts.llm_general_instr import get_llm_general_instr_prompt

    netlist = """* Simple RC circuit with 2 resistors and 1 capacitor
        V1 1 0 10V
        R1 1 2 1k
        R2 2 0 1k
        R3 2 0 2k
        .end"""

    prompt_manager = Prompt_manager(netlist=netlist, max_history_length=30)

    print(prompt_manager.get_prompt())