import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))) #appending parent folder to sys path so that modules can be imported from there


import llm.llm_model as llm_model
from llm.cook_llm_feed import Prompt_manager
from general_instr import get_general_instruction
import json

llm_model.Prepare_llm()  # prepare the LLM model

system_instr = get_general_instruction()
# print(system_instr)

query = "user: how to measure current in ngspice"

prompt = [{"role":"system", "content":system_instr}, {"role":"user", "content":query}]

# print(prompt)

response, token_count = llm_model.generate_response(prompt) # call the LLM model to get the response

# print(response, token_count)

response_dict = json.loads(response) # data is a dictionary object

# print(response_dict)

draft_ans = response_dict["draft_answer"]
chunks = response_dict["chunks"]

for i in range(len(chunks)):
    chunk = chunks[i]["chunk"]
    RAG_query = chunks[i]["RAG_query"]

    print(chunk)
    print(RAG_query)
