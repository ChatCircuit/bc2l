# command line interface for the bring circuit to life application software

import argparse
#from components import cook_llm_feed, img2nl
import static_database
import llm_model
import database_query

def print_json(obj, indent=1):
    if isinstance(obj, dict):
        for key, value in obj.items():
            prefix = '\t' * indent + str(key)
            if isinstance(value, (dict, list)):
                print(f"{prefix}:")
                print_json(value, indent + 1)
            else:
                print(f"{prefix}: {value}")
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            prefix = '\t' * indent + f'[{idx}]'
            if isinstance(item, (dict, list)):
                print(f"{prefix}:")
                print_json(item, indent + 1)
            else:
                print(f"{prefix}: {item}")


def main():
    parser = argparse.ArgumentParser(description="Bring Circuit to Life - Netlist Input CLI")
    parser.add_argument("-s", "--source", choices=["image", "schematic", "netlist"], required=True,
                        help="Specify the type of input: image (circuit schematic image), schematic (.sch file), or netlist (raw netlist file)")
    parser.add_argument("-f", "--file", type=str, required=True, help="Path to the input file")
    parser.add_argument("-m", "--mode", type=str, required=True, help="Demonstrating(demo) or Developing/Debugging(dbg)")
    
    args = parser.parse_args()

    # print(f"Processing {args.source} from file: {args.file}")
    
    # logic to handle each type of input accordingly
    if args.source == "image":
        print("TODO: Process circuit schematic image")
    elif args.source == "schematic":
        print("TODO: Parse .sch file")
    elif args.source == "netlist":
        # print("TODO: Read and process netlist file")

        with open(args.file, 'r') as file:
            netlist = file.read()
        #print("netlist: \n",netlist)
        static_database.main(New_Netlist=netlist, sample_test=False)
        print(f"=========> Successfully Built a database on {args.file}. <=========")

    if args.mode.lower() == 'dbg':
        dbg = True
        print("=========> WE ARE NOW DEBUGGING/DEVELOPING.......")
    else:
        dbg = False
        print("=========> WE ARE NOW DEMOSTRATING.......")


    # keep history of prompts with a maximum limit
    prompt_history = []
    max_history_length = 5  # set the maximum number of prompts to keep
    LLM = "gpt-o4-mini"

    #initialize and prepare the LLM model.
    llm_model.Prepare_llm(llm=LLM)

    # take prompt from user on a loop and process
    while True:
        prompt = input("\n\n\n#Enter your prompt (or 'exit' to quit): ")
        if prompt.lower() == 'exit':
            break
        prompt_history.append(prompt)
        if len(prompt_history) > max_history_length:
            prompt_history.pop(0)  # remove the oldest prompt to maintain the limit
        #print(f"You entered: {prompt}")
        #print(f"Prompt History: {prompt_history}")

        resp_json, resp_text = llm_model.Call_Agent(prompt)
        if dbg:
            print("original response:\n", resp_text, '\n')
            print("parsed JSON object:\n")
            print_json(resp_json)
        brief, count = database_query.Loop_over_commands(resp_json, dbg=dbg, llm=LLM)

        print(f"{count})\t Briefing: {brief}")

        # llm_feed = cook_llm_feed(netlist, prompt)
        # print("LLM Feed: \n", llm_feed)

        # import llm_model
        # llm_response = llm_model(llm_feed)
        # print("LLM Response: \n", llm_response)

        # if llm_response.type == "non_exec":
        #     print(llm_response.text)
        # elif llm_response.type == "exec":
        #     sim_result = simulator(llm_response.text) # simulate the code on the llm response

        #     updated_llm_feed = cook_llm_feed(sim_result, llm_feed)

        #     llm_response = llm_model(updated_llm_feed)
        #     print("LLM Response: \n", llm_response.text)
        # else:
        #     print("Invalid response type from LLM")
        #     # print("LLM Response: \n", llm_response.text)


if __name__ == "__main__":
    main()


