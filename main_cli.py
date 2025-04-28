# command line interface for the bring circuit to life application software

import argparse, logging, json, os, sys
from dotenv import load_dotenv


import database.static_database as static_database
import llm.llm_model as llm_model
import database.database_query as database_query
from python_interpreter import python_interpreter

from logger import get_logger
logger = get_logger(__name__)

load_dotenv()


# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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
    # parser.add_argument("-m", "--mode", type=str, required=True, help="Demonstrating(demo) or Developing/Debugging(dbg)")
    ### use logging module to log the information instead of dbg variable
    args = parser.parse_args()

    logger.info(f"Processing {args.source} from file: {args.file}")
    
    ###############################################
    ########## handle args
    ###############################################

    # logic to handle each type of input accordingly
    if args.source == "image":
        # TODO
        print("TODO: Process circuit schematic image")
    elif args.source == "schematic":
        # TODO
        print("TODO: Parse .sch file")
    elif args.source == "netlist":

        with open(args.file, 'r') as file:
            netlist = file.read()
        #print("netlist: \n",netlist)
        # static_database.main(New_Netlist=netlist, sample_test=False)
        # logging.info("=========> Successfully Built a database on {args.file}. <=========")

    # use logging module to log the information instead of dbg variable



    ############################
    ##### initialize llm and prompts and simulator
    ############################
    llm_model.Prepare_llm(llm=os.getenv("LLM_MODEL"))  # prepare the LLM model

    from llm.cook_llm_feed import Prompt_manager
    prompt_manager = Prompt_manager(netlist=netlist, max_history_length=int((os.getenv("MAX_HISTORY_LENGTH"))))  # initialize the prompt manager with the netlist and max history length
    
    from run_simulation_from_nl import SpiceServer
    spice_exe_path = os.getenv("NGSPICE_PATH")
    spice_server = SpiceServer(spice_command = f"{spice_exe_path}")  # the ngspice_con.exe file should be in the same directory as this script

    ##########################################
    ########Loop without maintaining database
    ##########################################
    data = {"data_points_df":None} # initialize the data object to pass to the python interpreter


    # take prompt from user on a loop and process
    while True:
        prompt = input("\n\n\n\n#Enter your prompt (or 'quit' to quit): ")

        # special commands to handle
        if prompt.lower() == 'quit':
            break
        elif prompt.lower() == 'show-netlist':
            # show the current netlist
            print("Current netlist: \n", prompt_manager.get_current_netlist())
            continue
        elif prompt.lower() == 'load-new':
            # load a new netlist from file
            new_netlist_file = input("Enter the path to the new netlist file: ").strip('"')
            with open(new_netlist_file, 'r') as file:
                netlist = file.read()
            print("loaded new netlist: \n", netlist)
            prompt_manager.clear_history(netlist)  # update the netlist in the prompt manager and clear the history
            continue
        elif prompt.lower() == 'stop-debug':
            # TODO: gotta update the looger file, otherwise not working
            # stop the debug mode and start the normal mode
            os.environ["LOGGING_LEVEL"] = "CRITICAL" # set the logging level to CRITICAL to stop the debug mode
            print("Debug mode stopped")
            continue
        elif prompt.lower() == 'start-debug':
            # start the debug mode
            #TODO: gotta update the looger file
            os.environ["LOGGING_LEVEL"] = "DEBUG" # set the logging level to DEBUG to start the debug mode
            print("Debug mode started")
            continue

        prompt_manager.append(role="user", content= prompt)      

        ####### processing the prompt with LLM
        while True:
            sim_error_retry_count = 0
            ipreter_error_retry_count = 0

            if os.getenv("SHOW_FULL_PROMPT") == "True": 
                print("full prompt being passed to llm: \n", prompt_manager.get_pretty_prompt())
            
            response, token_count = llm_model.generate_response(message_history=prompt_manager.get_prompt()) # call the LLM model to get the response

            logger.debug(f"llm raw response: {response}")
            logger.debug(f"llm response token count: {token_count}")

            ######## decoding json into dictionary object
            try:
                response_dict = json.loads(response) # data is a dictionary object
                prompt_manager.append(role="assistant", content=response_dict)  # append the response to the prompt history

            except json.JSONDecodeError:
                response_dict = None
                logger.error("Failed to parse JSON response from LLM, re-entering the loop with the same prompt and retrying.")
                continue    
            
            ####### handle output from llm
            target = response_dict.get("target")

            if target == "user":
                # if the target is user, then we can print the final answer
                if response_dict["user_query_answer"] is not None:
                    print(f">>>> {response_dict['user_query_answer']}")
                else:
                    logger.error("Invalid response from LLM: target is user but current status is not final answer ready")

                break # if the target is user, only then we can break the loop and wait for the next prompt

            elif target == "simulator":
                # if the target is simulator, then we can run the simulator and get the output
                logger.info("Running simulator with modified netlist")
                mod_netlist = response_dict["netlist_for_simulator"]
                
                if mod_netlist is not None:
                    print("(simulating circuit....)", end="")
                    result = spice_server(mod_netlist)  # run the simulator with the modified netlist
                    print("(simulation completed)")

                    data = result["data"] # a dictionary object {"vars": [], "data_points": []}
                    sim_out_desc = result["description"] # a dictionary object
                    error = result["description"]["error"] # a string object

                    if error is not None:
                        sim_error_retry_count += 1
                        if sim_error_retry_count > int(os.getenv("SIM_ERROR_RETRY_LIMIT")):
                            logger.error(f"Error in simulation. LLM could not fix the error within the given try limit.")
                            print("Failed to execute. Please try again, thank you.")
                            break
                        else:
                            # retry the simulation with the same netlist
                            logger.info(f"Error in simulation. Retrying({sim_error_retry_count})... Error Message: {error}")
                    
                    prompt_manager.append(role="user", content = sim_out_desc, subrole="simulator")
                else:
                    logger.error("Trying to simulate but modified netlist is None")
                    print("Failed to execute :( Please try again, thank you.")
                    break

            elif target == "python interpreter":
                # if the target is python interpreter, then we can run the python code and get the output
                logger.info("Running python interpreter with python code")
                python_code = response_dict["python_code_for_interpreter"] 

                if python_code is not None:
                    # run the python code with the data from simulator
                    print("(analyzing data...)", end="") 
                    ipreter_out = python_interpreter(python_code, data=data) # run the python code with the data from simulator
                    print("(data analysis completed)")


                    ipreter_error = ipreter_out["error"] # a string object

                    if ipreter_error is not None:
                        ipreter_error_retry_count += 1
                        if ipreter_error_retry_count > int(os.getenv("IPRETER_ERROR_RETRY_LIMIT")):
                            logger.error(f"Error in interpreter execution. LLM could not fix the error within the given try limit.")
                            print("Failed to execute. Please try again, thank you.")
                            break
                        else:
                            # retry the simulation with the same netlist
                            logger.info(f"Error in python interpreter. Retrying({ipreter_error_retry_count})... Error Message: {ipreter_error}")
                    
                    prompt_manager.append(role="user", content = ipreter_out, subrole="interpreter")
            else:
                logger.error("Invalid response from LLM: target is not user or simulator or python interpreter")
                print("Failed to execute :( Please try again, thank you.")
                break


    #######################################
    ##########Loop with maintaining database
    #######################################
    # # take prompt from user on a loop and process
    # while True:
    #     prompt = input("\n\n\n#Enter your prompt (or 'exit' to quit): ")
    #     if prompt.lower() == 'exit':
    #         break
    #     prompt_history.append(prompt)
    #     if len(prompt_history) > max_history_length:
    #         prompt_history.pop(0)  # remove the oldest prompt to maintain the limit
    #     #print(f"You entered: {prompt}")
    #     #print(f"Prompt History: {prompt_history}")

    #     resp_json, resp_text = llm_model.Call_Agent(prompt)
    #     if dbg:
    #         print("original response:\n", resp_text, '\n')
    #         print("parsed JSON object:\n")
    #         print_json(resp_json)
    #     brief, count = database_query.Loop_over_commands(resp_json, dbg=dbg, llm=LLM)

    #     print(f"{count})\t Briefing: {brief}")

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


