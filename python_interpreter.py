import json
import numpy as np
    
from logger import get_logger
logger = get_logger(__name__)

class Python_Interpreter():
    def __init__(self):
        self.data = [] # variable to store the data from all the simulations

    def append_data(self, sim_data: dict):
        """
        This function takes a dictionary and appends it to the data list.
        data = {"data_points_df":...}
        """
        self.data.append(sim_data)

    def run_code(self, code: str) -> dict:
        """
        This function takes python code as a string and execute it with the data from the simulator.

        args:
            data - dict of format: {"var_name":var_value, ...}
        """
        
        # run the python code with the data
        all_simulation_results = self.data #[{"data_points_df":...}, {"data_points_df":...}...]

        try:
            exec(code)  # execute the python code
            # print(locals())  # print the local variables
            try:
                res = locals()["result"] #llm is instructed to put the output in a variable named "result"
            except:
                logger.error("No result variable found in the python code output")
                res = None

            error = None        
        except Exception as e:
            logger.error(f"Error in executing python code: {e}")
            res = None
            error = f"Error in executing python code: {e}"

        return {"result": res, "error": error}  # return the result as a dictionary


################################
##### PREVIOUS IMPLEMENTATION 
################################
# def python_interpreter(python_code: str, data: dict) -> dict:
#     """
#     This function takes python code as a string and execute it with the data from the simulator.

#     args:
#         data - dict of format: {"vars":[], "data_points":[[]]}
#     """
    
#     # run the python code with the data
#     data_points_df = data["data_points_df"]


#     try:
#         exec(python_code)  # execute the python code
#         # print(locals())  # print the local variables
#         try:
#             res = locals()["result"] #llm is instructed to put the output in a variable named "result"
#         except:
#             logger.error("No result variable found in the python code output")
#             res = None

#         error = None        
#     except Exception as e:
#         logger.error(f"Error in executing python code: {e}")
#         res = None
#         error = f"Error in executing python code: {e}"

#     return {"result": res, "error": error}  # return the result as a dictionary
    
