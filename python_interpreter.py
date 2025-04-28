import json
import numpy as np
    
from logger import get_logger
logger = get_logger(__name__)

def python_interpreter(python_code: str, data: dict) -> dict:
    """
    This function takes python code as a string and execute it with the data from the simulator.

    args:
        data - dict of format: {"vars":[], "data_points":[[]]}
    """
    
    # run the python code with the data
    data_points_df = data["data_points_df"]


    try:
        exec(python_code)  # execute the python code
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
    


if __name__ == "__main__":
    # code = """result = vars + data_points"""

    code = """import numpy as np
import matplotlib.pyplot as plt

# Process the variable mapping
lines = vars.strip().splitlines()
column_map = {}

for line in lines:
    parts = line.split(',')
    # Extract variable index and name
    parts0 = parts[0].strip().strip('()').split()
    idx = int(parts0[0])
    varname = parts[1].strip().strip("'")
    column_map[varname] = idx

# Extract indices for time and voltages
time_idx = column_map['time']
v1_idx = column_map['v(1)']
v2_idx = column_map['v(2)']

# Calculate voltage across C1
voltage_across_C1 = data_points[:, v1_idx] - data_points[:, v2_idx]

# Plot
plt.figure()
plt.plot(data_points[:, time_idx], voltage_across_C1)
plt.xlabel('Time (s)')
plt.ylabel('Voltage across C1 (V)')
plt.title('Transient Analysis: Voltage across C1')
plt.grid(True)
plt.savefig('voltage_across_C1.png')

result = 'Plot saved as voltage_across_C1.png'
"""


    out = python_interpreter(code, data={"vars": 5, "data_points": 10})
    print(out["result"], out["error"])