import json
import numpy as np
    

def python_interpreter(python_code: str, data: dict) -> dict:
    """
    This function takes python code as a string and execute it with the data from the simulator.

    args:
        data - dict of format: {"vars":[], "data_points":[[]]}
    """
    
    # run the python code with the data
    vars = data["vars"]
    data_points = data["data_points"]

    error = ""

    try:
        exec(python_code)  # execute the python code
        # print(locals())  # print the local variables
        try:
            res = locals()["result"] #llm is instructed to put the output in a variable named "result"
        except:
            res = None
    except Exception as e:
        error = f"Error in executing python code: {e}"

    return {"result": res, "error": error}  # return the result as a dictionary
    


if __name__ == "__main__":
    code = """result = vars + data_points"""
    out = python_interpreter(code, data={"vars": 5, "data_points": 10})
    print(out["result"])