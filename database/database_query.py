import os
import static_database as sd
import json
import llm_model

SQLITE_DB_PATH = "DB/netlist.db"
GRAPH_DB_PATH = "DB/netlist_graph.gpickle"
DBG = False
LLM = 'gpt'

def Retrieve_line(component_name):
    report = sd.query_component(component_name, SQLITE_DB_PATH)[0]
    return report
    
def Update_DB(component_name, new_line):
    flag = 1
    try:
        sd.update_component_line(component_name, new_line, SQLITE_DB_PATH, GRAPH_DB_PATH)
        printable = f"Successfully updated content of {component_name}."
    except:
        printable = f"The component {component_name} being tried to update, has failed."
        flag = 0
    return printable, flag
    
def Create_New_DB_from_scratch(New_Netlist):
    flag = 1
    try:
        sd.main(New_Netlist, SQLITE_DB_PATH, GRAPH_DB_PATH, sample_test=False)
        printable = "New Netlist DB has successfully initiated."
    except:
        printable = "New Netlist initiation unsuccessful."
        flag = 0
    return


def Retrieve_Graph(component_name, depth):
    results = sd.query_component(component_name, SQLITE_DB_PATH)
    if DBG:
        print("\n--- Query Results for component 'R1' ---")
        for row in results:
            print(row)
    printable = ""
    flag = 1
    # Example 2: From the first found result, perform a BFS (e.g., depth=2) to retrieve its connectivity.
    if results:
        line_no, comp_id, nets_str, rest, raw_line = results[0]
        comp_node = f"COMP_{comp_id}_{line_no}"
        printable += f"\n--- BFS Network from node {comp_node} (depth=2) ---\n"
        subgraph = sd.bfs_network(comp_node, depth, GRAPH_DB_PATH)
        printable += "Nodes in subgraph:"

        for n, data in subgraph.nodes(data=True):
            printable = printable + f"  {n}: {data}\n"
        printable = printable + "Edges in subgraph:\n"
        for u, v in subgraph.edges():
            printable = printable + f"  {u} -- {v}\n"
    else:
        printable = f"Couldn't successfully retrive subgraph for {component_name}\n"
        flag = 0
    return printable, flag       

def Update_line_by_llm(update_prompt):
    llm_model.Prepare_llm(DQuery=False, dbg = DBG, llm=LLM)
    res_json, res_text = llm_model.Call_Agent(user_message=update_prompt, mode = 'Simple')
    if DBG:
        print(f"====> response to update by llm:\n{res_text}")
    return res_json["updated"]

def Explained_by_llm(instruction_prompt):
    llm_model.Prepare_llm(DQuery=False, dbg = DBG, llm=LLM)
    res_json, res_text = llm_model.Call_Agent(user_message=instruction_prompt, mode = 'Explain')
    if DBG:
        print(f"====> response to explain command:\n{res_text}")
    return res_text

def Extract_Subcircuit(list_of_nodes):
    _, _, snippet = sd.extract_subckt_by_nodes(desired_nets=list_of_nodes, graph_db_path=GRAPH_DB_PATH)
    return snippet

def miscellenous(instruction):
    printable = f"**There is nothing to execute.**\n{instruction}."
    return printable, 0

def Loop_over_commands(comms, dbg=False, llm='gpt'):
    global DBG, LLM
    DBG = dbg
    LLM = llm
    count = 1
    commands = comms["calls"]
    new_line = None
    old_line = None
    old_comp = None
    global_print = ""
    brief = None
    for cmd in commands:
        func = cmd["FunctionName"].lower()
        params = cmd["Parameters"]
        if  'update_db' in func:
            Update_DB(params["component_name"], new_line)

        if  'retrieve_line' in func:
            old_comp = params["component_name"]
            old_line = Retrieve_line(params["component_name"])[-1]

        if  'update_line_by_llm' in func:
            update_prompt = params["update_prompt"]["instruction"].format(old_line)
            if DBG:
                print(f"===> Update Prompt:\n{update_prompt}")
            new_line = Update_line_by_llm(update_prompt)

        if  'retrieve_graph' in func:
            printable, flag = Retrieve_Graph(params["component_name"], int(params["depth"]))
            if flag == 0:
                print(printable)
            else:
                global_print = printable

        if  'explained_by_llm' in func:
            instruction_prompt = params["instruction_prompt"].format(old_comp, old_line)
            if DBG:
                print(f"====> Explain instruction: {instruction_prompt}")
            explannation = Explained_by_llm(instruction_prompt)
            print(f"{count})\t {explannation}")
            count += 1
        if  'extract_subcircuit' in func:
            list_of_nodes = params["list_of_nodes"]
            snippet = Extract_Subcircuit(list_of_nodes)
            print(f"{count})\tHere is the extracted netlist code on subcircuit for: {list_of_nodes}")
            print(snippet)
            count+=1

        if  'miscellenous' in func:
            printable, _ = miscellenous(params["comments"])
            print(f"{count})\t printable")
            count += 1

        if  'create_new_db_from_scratch' in func:
            printable, flag = Create_New_DB_from_scratch(params["New_Netlist"])
            if flag == 0:
                print(printable)
            else:
                global_print += printable

    brief = comms["briefing"]
        
    if global_print != "":
        print(f"{count})\t {global_print}")
        count += 1
    
    return brief, count

