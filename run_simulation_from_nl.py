"""This module provides an interface to run ngspice in server mode and get back the simulation
output.

When ngspice runs in server mode, it writes on the standard output an header and then the simulation
output in binary format.  At the end of the simulation, it writes on the standard error a line of
the form:

    .. code::

        @@@ \d+ \d+

where the second number is the number of points of the simulation.  Due to the iterative and
adaptive nature of a transient simulation, the number of points is only known at the end.

Any line starting with "Error" in the standard output indicates an error in the simulation process.
The line "run simulation(s) aborted" in the standard error indicates the simulation aborted.

Any line starting with *Warning* in the standard error indicates non critical error in the
simulation process.

"""

####################################################################################################

import os
import re
import subprocess
import re
import numpy as np

from logger import get_logger
logger = get_logger(__name__)

class SpiceServer:

    """This class wraps the execution of ngspice in server mode and convert the output to a Python data
    structure.

    Example of usage::

      spice_server = SpiceServer(spice_command='/path/to/ngspice')
      variables, data_points = spice_server(spice_netlist)

    It returns the list of variables and the data points as a 2D numpy array.

    """

    SPICE_COMMAND = 'ngspice_con.exe' # the ngspice_con.exe file should be in the same directory as this script 

    ##############################################

    def __init__(self, **kwargs):

        self._spice_command = kwargs.get('spice_command') or self.SPICE_COMMAND
        self.error = ""

    ##############################################

    def _decode_number_of_points(self, line):

        """Decode the number of points in the given line."""

        match = re.match(r'@@@ (\d+) (\d+)', line)
        if match is not None:
            return int(match.group(2))
        else:
            raise NameError("Cannot decode the number of points")

    ##############################################
    
    def _extract_spice_variables(self, spice_output_string_lines: list) -> list[tuple[int, str, str]]:
        """
        Extracts variable definitions from a SPICE simulation output string.

        Args:
            spice_output_string: The string containing the SPICE output converted to list of lines.

        Returns:
            A list of tuples, where each tuple represents a variable
            in the format (index, name, data)type).
            Returns an empty list if the variable section or 'Values:' marker
            is not found, or if parsing fails.
        """
        variables = []
        lines = spice_output_string_lines

        try:
            # Find the index of the line containing "Values:"
            values_index = -1
            for i, line in enumerate(lines):
                # Use strip() to handle potential leading/trailing whitespace
                if line.strip() == "Values:":
                    values_index = i
                    break

            if values_index == -1:
                print("Warning: 'Values:' marker not found.")
                return []

            # Regex to match the variable definition lines (index, name, type)
            # Allows for variable whitespace between elements
            # Assumes index is numeric, name and type are non-whitespace sequences
            var_pattern = re.compile(r"^\s*(\d+)\s+(\S+)\s+(\S+)\s*$")

            # Iterate through the lines *before* the "Values:" line
            # Check lines that potentially define variables
            for i in range(values_index):
                line = lines[i]
                match = var_pattern.match(line)
                if match:
                    # Extract the matched groups
                    index_str, name, var_type = match.groups()
                    try:
                        index = int(index_str)
                        variables.append((index, name, var_type))
                    except ValueError:
                        # This should not happen due to \d+ in regex, but safety first
                        print(f"Warning: Could not convert index '{index_str}' to int on line: {line}")
                        continue

        except Exception as e:
            print(f"An error occurred during parsing: {e}")
            return [] # Return empty list on error

        # Optional: Validate against "No. Variables" line if needed
        # num_vars = 0
        # for line in lines:
        #     if "No. Variables:" in line:
        #         try:
        #             num_vars = int(line.split(':')[1].strip())
        #             break
        #         except (IndexError, ValueError):
        #             pass # Ignore if parsing fails
        # if num_vars > 0 and len(variables) != num_vars:
        #     print(f"Warning: Expected {num_vars} variables based on header, but found {len(variables)}.")

        return variables
    
    def _extract_spice_data_numpy(self, spice_output_string_lines: list) -> np.ndarray | None:
        """
        Extracts numerical data points following the 'Values:' line from SPICE
        output string and stores them in a 2D NumPy array. Handles both
        'real' and 'complex' data types based on the 'Flags:' line.

        Args:
            spice_output_string: The string containing the SPICE output converted to list of lines.

        Returns:
            A 2D NumPy array containing the data points (dtype=float or complex),
            or None if parsing fails (e.g., 'Values:' or 'No. Variables:'
            not found, data inconsistent).
            Returns an empty array (with correct columns/dtype) if no data points exist.
        """
        lines = spice_output_string_lines
        values_index = -1
        num_variables = -1
        data_is_complex = False # Default to real data
        flags_line_found = False

        # --- 1. Parse Header Information ---
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            if stripped_line.startswith("No. Variables:"):
                try:
                    num_variables = int(line.split(':')[1].strip())
                except (IndexError, ValueError):
                    print("Warning: Could not parse 'No. Variables'.")
            elif stripped_line.startswith("Flags:"):
                flags_line_found = True
                try:
                    flag_value = line.split(':')[1].strip().lower()
                    if flag_value == 'complex':
                        data_is_complex = True
                    # Add handling for other flags if needed, otherwise assume real
                except IndexError:
                     print("Warning: Could not parse 'Flags:' line content.")
            elif stripped_line == "Values:":
                values_index = i
                # Optimization break can be added here if desired

        # --- 2. Validate Header Information ---
        if values_index == -1:
            print("Error: 'Values:' marker not found in the output.")
            return None
        if num_variables <= 0:
            # Try to infer num_variables from 'No. of Data Columns' if necessary?
            # For now, require 'No. Variables'.
            print("Error: 'No. Variables:' not found or has an invalid value.")
            return None
        if not flags_line_found:
            print("Warning: 'Flags:' line not found. Assuming data type is 'real'.")


        # --- 3. Extract Data Points ---
        data_points_flat = []
        target_dtype = np.complex128 if data_is_complex else np.float64

        # Start reading from the line immediately after "Values:"
        for line_num in range(values_index + 1, len(lines)):
            line = lines[line_num].strip()
            if not line:
                continue # Skip empty lines

            parts = line.split()
            if not parts:
                continue # Skip lines that only contained whitespace

            value_str = parts[-1] # The numerical value (or complex pair) is expected last

            try:
                if data_is_complex:
                    # Expect format "real_part,imaginary_part"
                    real_str, imag_str = value_str.split(',')
                    value = complex(float(real_str), float(imag_str))
                else:
                    # Expect a single float
                    value = float(value_str)

                data_points_flat.append(value)

            except (ValueError, IndexError) as parse_error:
                # Handles errors from split(',') if not complex format,
                # or float() conversion errors for both types.
                # print(f"Warning: Skipping line {line_num+1}, parse error: {parse_error} "
                #       f"on value string: '{value_str}'") # Optional Debug
                pass # Skip lines that don't match the expected format


        # --- 4. Validate and Reshape Data ---
        if not data_points_flat:
            print("Warning: No numerical data found after 'Values:'. Returning empty array.")
            # Return an empty array with the correct number of columns and dtype
            return np.empty((0, num_variables), dtype=target_dtype)

        if len(data_points_flat) % num_variables != 0:
            print(f"Error: The total number of data points found ({len(data_points_flat)}) "
                  f"is not a multiple of the number of variables ({num_variables}). "
                  "Data might be incomplete or corrupted.")
            return None

        num_rows = len(data_points_flat) // num_variables

        try:
            # Convert the flat list into a NumPy array and reshape it
            # Explicitly set the dtype based on the detected flag
            data_array = np.array(data_points_flat, dtype=target_dtype).reshape(num_rows, num_variables)
            return data_array
        except Exception as e:
            print(f"Error creating or reshaping NumPy array: {e}")
            return None


    def _parse_stdout(self, stdout):

        """Parse stdout for errors and return the data points and variables and metadata"""

        # first checking out for errors
        error_found = False
        # UnicodeDecodeError: 'utf-8' codec can't decode byte 0xc0 in position 870: invalid start byte
        # lines = stdout.decode('utf-8').splitlines()
        lines = stdout.splitlines()
        for line_index, line in enumerate(lines):
            if line.startswith('Error '):
                error_found = True
                # self._logger.error(os.linesep + line.decode('utf-8') + os.linesep + lines[line_index+1].decode('utf-8'))
                print(f"Error found in stdout: {os.linesep + line + os.linesep + lines[line_index+1]}")
        if error_found:
            raise NameError("Errors was found by Spice")

        # now parsing for variables and data points
        self.variables = self._extract_spice_variables(lines)
        self.data_points = self._extract_spice_data_numpy(lines)
       


    ##############################################

    def _parse_stderr(self, stderr):

        """Parse stderr for warnings and return the number of points."""

        # self._logger.debug(os.linesep + stderr)

        stderr_lines = stderr.splitlines()
        number_of_points = None
        for line in stderr_lines:
            if line.startswith('Warning:'):
                # self._logger.warning(line[len('Warning :'):])
                print(f"Warning found in stderr: {line[len('Warning :'):]}")
            elif line == 'run simulation(s) aborted':
                raise NameError('Simulation aborted' + os.linesep + stderr)
            elif line.startswith('@@@'):
                number_of_points = self._decode_number_of_points(line)

        return number_of_points

    ##############################################

    def __call__(self, spice_input):

        """Run SPICE in server mode as a subprocess for the given input and return a
        :obj:`PySpice.RawFile.RawFile` instance.

        """

        logger.info("Start the spice subprocess")
        
        # spice_exe_path = os.path.join(os.getcwd(), 'ngspice_con.exe')

        process = subprocess.Popen((self._spice_command, '-s'),
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        input_ = str(spice_input).encode('utf-8')
        stdout, stderr = process.communicate(input_)

        stdout = stdout.decode('utf-8')
        stderr = stderr.decode('utf-8')

        # print(f"stderr:{stderr}")
        # print(f"stdout:{stdout}")


        self._parse_stdout(stdout)
        number_of_points = self._parse_stderr(stderr)
        
        if number_of_points is None:
            raise NameError('The number of points was not found in the standard error buffer,'
                            ' ngspice returned:' + os.linesep +
                            stderr)
        if len(self.data_points) != number_of_points:
            logger.error('The number of points returned by ngspice does not match the number of points '
                         'in the data array, ngspice returned:' + os.linesep +
                         stderr)
            # raise NameError('The number of points returned by ngspice does not match the number of points '
            #                 'in the data array, ngspice returned:' + os.linesep +
            #                 stderr)
            self.error = 'The number of points returned by ngspice does not match the number of points ' \
                         'in the data array, ngspice returned:' + os.linesep + stderr

        # TODO: handle error by simulator properly and create error mitigation by LLM strategy 
        
        # return result as a dictionary format 
        formatted_variables = "\n".join([f"({item[0]}, '{item[1]}', '{item[2]}')" for item in self.variables])

        result = {
            "data":{"vars": self.variables, "data_points": self.data_points},
            
            "description":{
                "number of variables": len(self.variables),
                "number of points": number_of_points,
                "vars": formatted_variables,
                "data_points": f"a 2D numpy array of shape {self.data_points.shape}",
                "error": self.error
            },
            "error": self.error
        }

        # the description is for the LLM to understand the output

        return result



if __name__ == '__main__':
    # spice_netlist = """A Berkeley SPICE3 compatible circuit
    # *
    # * This circuit contains only Berkeley SPICE3 components.
    # *
    # * The circuit is an AC coupled transistor amplifier with
    # * a sinewave input at node "1", a gain of approximately -3.9,
    # * and output on node "coll".
    # *
    # * .tran 1e-5 2e-3
    # .ac dec 10 0.01 100
    # * .dc vcc 0 15 0.1
    # * .op
    # *
    # vcc vcc 0 12.0
    # vin 1 0 0.0 ac 1.0 sin(0 1 1k)
    # ccouple 1 base 10uF
    # rbias1 vcc base 100k
    # rbias2 base 0 24k
    # q1 coll base emit generic
    # rcollector vcc coll 3.9k
    # remitter emit 0 1k
    # *
    # .model generic npn
    # *
    # .end
    # """

    # with open(r"C:\\Users\\Touhid2\\Desktop\\test.cir", 'r') as file:
    #     spice_netlist = file.read()

#     spice_netlist = """"* simple RC circuit with 2 R and 1 C

# V1 1 0 10V
# R1 1 2 300
# R2 2 0 700
# C1 2 0 1uF ic=0

# .tran 0.1ms 10ms uic
# .end

# """

    spice_netlist = """* simple ckt
V1 1 0 DC 10
R1 1 2 1k
R2 2 0 1k
R3 2 0 2k
.op
.end
    """
    import os
    from dotenv import load_dotenv
    load_dotenv()

    spice_exe_path = os.getenv("NGSPICE_PATH")

    spice_server = SpiceServer(spice_command = f"{spice_exe_path}")  # the ngspice_con.exe file should be in the same directory as this script
    
    sim_out = spice_server(spice_netlist)
    
    import json
    print(json.dumps(sim_out["description"], indent=0))

    # print("Number of points:", len(data_points))
    # print("Number of variables:", len(vars))
    # print("Variables:")
    # for i in range(len(vars)):
    #     print(vars[i])

    # print("data_Points[0:4]:")
    # for i in range(5):
    #     print(data_points[i])


    # time_data = data_points[:, 0]
    # print(time_data)

    #############################################################################################
