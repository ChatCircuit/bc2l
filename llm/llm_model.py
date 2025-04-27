import os
import openai
from openai import AzureOpenAI  
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.inference.models import SystemMessage, UserMessage
import tiktoken  # Tokenizer library for OpenAI models  
import dotenv
import json
import time
import sys
import threading
import re

from logger import get_logger
logger = get_logger(__name__)

dotenv.load_dotenv()

DBG = False
LLM = 'gpt-o3-mini'
api_key = None
api_endpoint = None
deployment_name = None
api_version = None
client = None
System_Prompt_Complex = None
System_Prompt_Simple = """You are an expert in SPICE netlist editing.
                        You will be given an instruction and the original netlist line.
                        Your job is to modify the line according to the instruction and
                        return the updated line in the valid netlist format.
                        Also, the response should strictly be JSON Object {"updated": ....}"""
System_Prompt_Exp = """You are an expert in SPICE netlist.
                        You will be given a component_name, netlist line and an instruction;
                        according to which you need to answer very shortly and precisely"""
tokenizer = None
# Function to calculate token count  
def count_tokens(text):  
    return len(tokenizer.encode(text))  
  
# Function to generate responses  
def generate_response_basic(System_Prompt, User_Prompt):  
    try:  

        if 'gpt' in LLM.lower():
            response = client.chat.completions.create(  
                model=deployment_name,  # In Azure, 'model' should be the deployment name  
                messages=[  
                    {"role": "system", "content": System_Prompt},  
                    {"role": "user", "content": User_Prompt}  
                ],  
                max_completion_tokens=4048
            )  
        else:
            response = client.complete(
                messages=[
                    SystemMessage(content=System_Prompt),
                    UserMessage(content=User_Prompt)
                ],
                max_completion_tokens=4048,
                model=deployment_name
            )
          
        # Extract response content  
        response_content = response.choices[0].message.content  
          
        # Count tokens in the response  
        #token_count = count_tokens(response_content)  
        token_count = response.usage.total_tokens
          
        return response_content, token_count  
    except Exception as e:  
        return f"Error: {e}", 0

def generate_response(message_history:list):
    """
    stage: at which stage is the LLM in - thinking, simulating, analyzing data
    """
    stop_event = threading.Event()
    result = {"response": None, "token_count": 0, "error": None}

    def api_call():
        try:
            if 'gpt' in LLM.lower():
                response = client.chat.completions.create(  
                    model=deployment_name,  # In Azure, 'model' should be the deployment name  
                    messages=message_history,  
                    max_completion_tokens=4048
                )  
            else:
                response = client.complete(
                    messages=[
                        UserMessage(content=message_history)
                    ],
                    max_tokens=4048,
                    model=deployment_name
                )
            content = response.choices[0].message.content
            token_count = response.usage.total_tokens
            #tokens  = count_tokens(content)
            if  'deepseek' in LLM:
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            result["response"]    = content
            result["token_count"] = token_count
        except Exception as e:
            result["error"] = e
        finally:
            stop_event.set()

    # Kick off the API call in the background
    thread = threading.Thread(target=api_call, daemon=True)
    thread.start()

    # Meanwhile: show elapsed seconds
    start_time = time.time()
    while not stop_event.is_set():
        elapsed = int(time.time() - start_time)
        # \r = return to start of line; \033[K = clear from cursor to end of line
        sys.stdout.write(f"\r\t\t\t\t processing prompt (thinking...): {elapsed} seconds elapsed....\033[K")
        sys.stdout.flush()
        time.sleep(1)

    # Once done, clear that line entirely
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()

    # Return the API result or the error
    if result["error"] is not None:
        logger.error(f"Error in API call: {result['error']}")
        return f"Error in API call: {result['error']}", 0
    
    return result["response"], result["token_count"]

    

def Call_Agent(user_message, mode = 'Complex', count_token = False):
    if mode == 'Complex':
        System_Prompt = System_Prompt_Complex
    elif mode == 'Simple':
        System_Prompt = System_Prompt_Simple
    elif mode == 'Explain':
        System_Prompt = System_Prompt_Exp

    Response, num_token = generate_response(System_Prompt=System_Prompt, User_Prompt=user_message)
    if count_token == True or DBG == True:
        print(f"====> Token used: {num_token}")
    try:
        parsed_json = json.loads(Response)
    except json.JSONDecodeError:
        parsed_json = None
        if mode != 'Explain':
            print("Please try again with alternate queries, thank you.")
        print(Response)
    return parsed_json, Response


def Prepare_llm(DQuery = False, llm='gpt'):
    global api_version, api_key, LLM, api_endpoint, deployment_name, client, System_Prompt_Complex, tokenizer, DBG
    # Retrieve environment variables  
    LLM = llm
    if LLM.lower() == 'gpt-o3-mini':
        api_key = os.getenv("AZURE_OPENAI_API_KEY")  
        api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")  
        deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")  
        api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    elif LLM.lower() == 'gpt-o4-mini':
        api_key = os.getenv("AZURE_O4_API_KEY")
        api_endpoint = os.getenv("AZURE_O4_ENDPOINT")  
        deployment_name = os.getenv("AZURE_O4_DEPLOYMENT")  
        api_version = os.getenv("AZURE_O4_API_VERSION")
    elif 'deepseek' in LLM.lower():
        api_key = os.getenv("AZURE_R1_API_KEY")  
        api_endpoint = os.getenv("AZURE_R1_ENDPOINT")  
        deployment_name = os.getenv("AZURE_R1_DEPLOYMENT")  
        api_version = os.getenv("AZURE_R1_API_VERSION")
    else:
        print("=======> Sorry not an available model. Try selecting among gpt-o4-mini/gpt-o3-mini/deepseek-r1")
    
    # Create an Azure client  
    if 'gpt' in LLM.lower():
        client = AzureOpenAI(  
            api_key=api_key,  
            api_version=api_version,  # Use the latest supported Azure API version  
            azure_endpoint=api_endpoint,  
        )
    elif 'gpt' in LLM.lower():
        client = ChatCompletionsClient(
            credential=AzureKeyCredential(api_key),
            endpoint=api_endpoint
        )

    # DBG = dbg
    tokenizer = tiktoken.get_encoding("cl100k_base")
    # with open('prompts/prompt3.txt', 'r', encoding='utf-8') as file:
    #     System_Prompt_Complex = file.read()

    # while DQuery:
    #     message = input("Enter your query: ")
    #     if message.lower() == 'exit':
    #         break
    #     _, text = Call_Agent(message)
    #     print(text)

#Prepare_llm(DQuery=True, dbg=True, llm='gpt-o3-mini')

if __name__ == "__main__":
    Prepare_llm(DQuery=True, dbg=True, llm='gpt-o3-mini')