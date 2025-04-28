"""
python  file to run tests on queryset automatically
"""
# TODO: solve the EOF error in the subprocess call

import subprocess
import csv
import os
import time

# Path to the main_cli.py script
cli_script_path = r"H:\NOTHING\#Projects\bring_ckt_to_life_project\code\main_cli.py"
netlist_file = r"H:\NOTHING\#Projects\bring_ckt_to_life_project\code\llm_query_dataset\querysets\queryset0\test_queryset0_nl.cir"
queryset_file = r"H:\NOTHING\#Projects\bring_ckt_to_life_project\code\llm_query_dataset\querysets\queryset0\test_queryset0.csv"

def run_cli_with_input(query):
    # Prepare the command to invoke your CLI script
    command = f'python {cli_script_path} -s netlist -f "{netlist_file}"'
    
    # Start the process with subprocess
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Provide the input to the CLI
    stdout, stderr = process.communicate(input=query + '\n')  # Send query and simulate Enter
    
    if process.returncode != 0:
        # If there is an error, capture stderr
        return f"Error: {stderr}"

    # Return the standard output
    return stdout


def process_query(query, expected_output):
    # Call the CLI and get the output
    output = run_cli_with_input(query)

    # Print the output (optional, for debugging)
    print(f"Query: {query}")
    print(f"Output: {output}")
    
    # Ask user for the result
    # success = input(f"Is the output successful (expected: {expected_output})? (yes/no): ").strip().lower()
    
    # return success == 'yes'

def read_and_test_queries():
    # Open the CSV file with queries
    with open(queryset_file, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row in reader:
            query = row['QUERY']
            expected_output = row['EXPECTED OUTPUT']
            
            print(f"Running test for query: {query}")
            
            # Run the test for this query
            # success = process_query(query, expected_output)
            process_query(query, expected_output)
            # Save the result in the CSV file (optional)
            # row['SUCCESS'] = 'yes' if success else 'no'
            
            # Optionally, print or save the updated row
            # print(f"Test result for query: {row['SUCCESS']}")

            # Simulate saving results back to CSV (if needed)
            # Optionally, save updated CSV if you want to track success/failure
            # with open(queryset_file, 'a', newline='', encoding='utf-8') as outfile:
            #     writer = csv.DictWriter(outfile, fieldnames=row.keys())
            #     writer.writerow(row)

if __name__ == '__main__':
    read_and_test_queries()


