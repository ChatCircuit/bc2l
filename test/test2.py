import pexpect
import csv
import time

import pexpect.popen_spawn

def run_test():
    # Start the main_cli.py script
    cmd = 'python main_cli.py -s netlist -f "H:\\NOTHING\\#Projects\\bring_ckt_to_life_project\\code\\llm_query_dataset\\querysets\\queryset0\\test_queryset0_nl.cir"'
    child = pexpect.popen_spawn.PopenSpawn(cmd)

    # Wait for the first prompt
    child.expect("\n\n\n#Enter your prompt (or 'quit' to quit): ")

    # Open the CSV file with the queries
    with open('H:\\NOTHING\\#Projects\\bring_ckt_to_life_project\\code\\llm_query_dataset\\querysets\\queryset0\\test_queryset0_nl.csv', mode='r') as file:
        reader = csv.DictReader(file)
        
        for row in reader:
            query = row['QUERY']
            expected_output = row['EXPECTED OUTPUT']
            success = row['SUCCESS']

            # Send the query as input
            print(f"Sending query: {query}")
            child.sendline(query)

            # Wait for the output, which will appear after the prompt
            child.expect('>>>>')
            output = child.before.decode('utf-8').strip()  # Capture the output

            # # Check if the output matches the expected result
            # if output == expected_output:
            #     print(f"Test for query '{query}' succeeded.")
            #     success_input = 'success'
            # else:
            #     print(f"Test for query '{query}' failed. Expected: '{expected_output}', Got: '{output}'")
            #     success_input = 'fail'

            # Respond with success or failure
            # child.sendline(success_input)

            # Wait for the next prompt, unless it's the last query
            if row != list(reader)[-1]:
                child.expect("\n\n\n#Enter your prompt (or 'quit' to quit): ")
            else:
                # If it's the last query, break the loop after the response
                child.sendline('quit')
                child.expect(pexpect.EOF)
                break

    # Close the process
    child.close()

if __name__ == "__main__":
    run_test()
