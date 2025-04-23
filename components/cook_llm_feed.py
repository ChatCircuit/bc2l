'''
create the input feed to the LLM as a string by combining user prompt, netlist, 
simulation results, and any other relevant information. 
This string will be passed to the LLM for processing.
'''

def cook_llm_feed(netlist, prompt):
    # Combine the netlist and prompt into a single input string for the LLM
    input_feed = f"Netlist: {netlist}\nUser Prompt: {prompt}"
    
    return input_feed