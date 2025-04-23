
def main():

    #with open("/sample_netlist.cir", "r") as file:
    #    content = file.read()
    #print(content)

    # Open the file in read mode
    with open('prompts/prompt3.txt', 'r', encoding='utf-8') as file:
        content = file.read()

    # Print the contents of the file
    print(content)

if __name__ == "__main__":
    main()
