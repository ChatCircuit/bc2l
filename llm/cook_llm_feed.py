'''
create the input feed to the LLM as a string by combining user prompt, netlist, 
simulation results, and any other relevant information. 
This string will be passed to the LLM for processing.
'''
import json
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

        # list of interactions with the LLM, a interaction includes the user prompt, intermediated LLM responses and intermediate simulator and interpretor responses
        # every task id is 1 entry in the interaction list, and each entry is a dictionary with the following keys:
        """ format of each entry: {"task_id": task_id, 
                                     "interaction": [{"role": role, "subrole": subrole, "content": content},
                                                        {"role": role, "subrole": subrole, "content": content},
                                                        {"role": role, "subrole": subrole, "content": content},...]                                         
                                }
        """        
        # keep up a unique task id for each user prompt
        self.task_id = 0

    def append(self, role:str, content:dict, subrole: str=None):
        """
        role: "user" | "assistant" | "system" for openai API
        subrole: "simulator", "interpereter", this is used to identify the type of user prompt 
        """
                # processing various roles and subroles
        if (role == "assistant"):
            # if there is a modified netlist in the content, then update the system content with the new netlist
            try: 
                mod_netlist = content["netlist_for_simulator"]
            except:
                mod_netlist = None

            if mod_netlist is not None:
                # if the modified netlist is not None, then update the system content with the new netlist
                self.update_system_content(mod_netlist)
                logger.info(f"updated system content with new netlist: {mod_netlist}")

            content = json.dumps(content) # convert the content to json string for llm

        elif (role == "user"):
            if (subrole == None):
                # make a unique task id to the user prompt but don't change it for subrole simulator or interpreter
                self.task_id += 1
                logger.info(f"created a new task id: {self.task_id}")

                # interaction_entry = {"task_id": self.task_id, "interaction": [{"role": role, "subrole": subrole, "content": content}] }
            elif (subrole == "simulator"):
                content = f"simulator output: {content}"
                logger.debug(f"simulator output: {content}")

            elif (subrole == "interpreter"):
                content = f"interpreter output: {content}"
                logger.debug(f"interpreter output: {content}")
            else:
                logger.error(f"Invalid subrole: {subrole}")
                raise ValueError(f"Invalid subrole: {subrole}")
            
            content = json.dumps(content) # convert the content to json string for llm
            content = f"{content} [task_id: {self.task_id}]"
        
        else:
            logger.error(f"Invalid role: {role}")
            raise ValueError(f"Invalid role: {role}")
 
        self.prompt.append({"role": role, "content": content})
        self.check_length()

    def update_system_content(self, new_netlist:str):
        """
        update the system content with the new netlist
        """
        self.netlist = new_netlist 
        self.system_content = get_llm_general_instr_prompt(new_netlist)
        
        # update the system content in the prompt
        for p in self.prompt:
            if p["role"] == "system":
                p["content"] = self.system_content


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

    def clear_history(self, netlist:str=None):
        """
        clear the prompt history entirely and add a new system content with new netlist. this is used when the user wants to start a new task with a new netlist.
        """
        self.prompt = []
        self.system_content = get_llm_general_instr_prompt(netlist)
        self.prompt.append({"role": "system", "content": self.system_content})

    def get_current_netlist(self):
        return self.netlist


    def get_user_prompt(self):
        """
        get the user prompt from the prompt history. won't return the intermediate simulator or interpreter subrole prompts although they are passed as user to the llm
        """
        user_prompt = []
        # TODO: filter this from interaction list instead of prompt history and filter for subrole simulator and interpreter
        for p in self.prompt:
            if p["role"] == "user":
                user_prompt.append(p["content"])
        return user_prompt
    
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