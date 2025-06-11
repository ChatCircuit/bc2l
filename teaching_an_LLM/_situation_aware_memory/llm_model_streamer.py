"""
initialize and use a llm model that streams its output and based on the current 'situation' retrieves memory
using SAM Retriever and update/set its course of action and output.
"""
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from openai import AzureOpenAI  
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.inference.models import SystemMessage, UserMessage
from google import genai
from google.genai import types
import tiktoken
import dotenv
import time
import threading
import re

from logger import get_logger
logger = get_logger(__name__)

dotenv.load_dotenv()

class LLMmodel:
    """
    prepare and use an llm model

    args:
        llm - deployment model name.
                supported models: 
                i) 'gpt-o3-mini', 'gpt-o4-mini', 
                ii) 'deepseek-r1', 
                iii) 'gemini-2.0-flash', 'gemini-2.5-flash-preview-04-17', 'gemini-2.5-flash-preview-05-20'
                    and other gemini models: https://ai.google.dev/gemini-api/docs/models, 
                    rate limit: https://ai.google.dev/gemini-api/docs/rate-limits#free-tier
    """

    def __init__(self, llm='gpt-o3-mini'):
        self.LLM = llm
        self.api_key = None
        self.api_endpoint = None
        self.deployment_name = None
        self.api_version = None
        self.client = None
        self.tokenizer = None
        self.Prepare_llm()

                
    def Prepare_llm(self):
        # getting keys
        if self.LLM.lower() == 'gpt-o3-mini':
            self.api_key = os.getenv("AZURE_OPENAI_API_KEY")  
            self.api_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")  
            self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT")  
            self.api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        elif self.LLM.lower() == 'gpt-o4-mini':
            self.api_key = os.getenv("AZURE_O4_API_KEY")
            self.api_endpoint = os.getenv("AZURE_O4_ENDPOINT")  
            self.deployment_name = os.getenv("AZURE_O4_DEPLOYMENT")  
            self.api_version = os.getenv("AZURE_O4_API_VERSION")
        elif 'deepseek' in self.LLM.lower():
            self.api_key = os.getenv("AZURE_R1_API_KEY")  
            self.api_endpoint = os.getenv("AZURE_R1_ENDPOINT")  
            self.deployment_name = os.getenv("AZURE_R1_DEPLOYMENT")  
            self.api_version = os.getenv("AZURE_R1_API_VERSION")
        elif 'gemini' in self.LLM.lower():
            # self.api_key = os.getenv("GEMINI_API_KEY_31416")
            self.api_key = os.getenv("GEMINI_API_KEY_2718")
        else:
            logger.error("Sorry not an available model. Try selecting among gpt-o4-mini/gpt-o3-mini/deepseek-r1")
            raise ValueError("Invalid LLM model name.")

        # setting up client
        if 'gpt' in self.LLM.lower():
            self.client = AzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.api_endpoint,
            )
        elif 'deepseek' in self.LLM.lower():
            self.client = ChatCompletionsClient(
                credential=AzureKeyCredential(self.api_key),
                endpoint=self.api_endpoint
            )
        elif 'gemini' in self.LLM.lower():
            self.client = genai.Client(api_key=self.get_working_gemini_api_key())

        logger.info(f"finished preparing llm. llm name: {self.LLM}")



    def generate_response_basic(self, System_Prompt, User_Prompt):
        """
        Generate a response from the LLM based on the provided system and user prompts.
        Does not use message history, just the system and user prompts.
        """

        start_time = time.time()
        try:
            if 'gpt' in self.LLM.lower():
                response = self.client.chat.completions.create(
                    model=self.deployment_name,
                    messages=[
                        {"role": "system", "content": System_Prompt},
                        {"role": "user", "content": User_Prompt}
                    ],
                    max_completion_tokens=4048
                )
                response_content = response.choices[0].message.content
                token_count = response.usage.total_tokens

            elif 'gemini' in self.LLM.lower():
                response = self.client.models.generate_content(
                            model=self.LLM,
                            config=types.GenerateContentConfig(system_instruction=System_Prompt),
                            contents=User_Prompt
                        )
                response_content = response.text
                token_count = response.usage_metadata.total_token_count

            elif 'deepseek' in self.LLM.lower():
                response = self.client.complete(
                    messages=[
                        SystemMessage(content=System_Prompt),
                        UserMessage(content=User_Prompt)
                    ],
                    model=self.deployment_name
                )
                response_content = response.choices[0].message.content
                token_count = response.usage.total_tokens

            elapsed = time.time() - start_time
            logger.info(f"Time taken to generate response with {self.LLM}: {elapsed:.2f} seconds")

            return response_content, token_count
        except Exception as e:
            return f"Error: {e}", 0

    def generate_response(self, message_history: list):
        """
        Generate a response from the LLM based on the conversation history.

            args:
                message_history - a list of messages in the conversation history, where each message is a dictionary with 'role' and 'content' keys.
                    Example: [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "What is the capital of France?"},
                        {"role": "assistant", "content": "The weather in Paris is currently sunny and 25°C."},
                        {"role": "user", "content": "What about the weather in London?"}
                    ]
                    
                    role = either "system", "user", or "assistant"
        """
        stop_event = threading.Event()
        result = {"response": None, "token_count": 0, "error": None}

        def api_call():
            try:
                if 'gpt' in self.LLM.lower():
                    response = self.client.chat.completions.create(
                        model=self.deployment_name,
                        messages=message_history,
                        max_completion_tokens=4048
                    )
                    
                    content = response.choices[0].message.content
                    token_count = response.usage.total_tokens
                elif 'gemini' in self.LLM.lower():
                    """
                    for gemini the message history should be in the format:

                    system_instruction = '<system instruction string>'
                    contents: [
                        'user: What is the capital of France?',
                        'assistant: The weather in Paris is currently sunny and 25°C.',
                        'user: What about the weather in London?'
                    ] 
                    contents should not contain the system message, it should be passed separately as system_instruction.
                    The contents should be a list of strings, where each string is a message in the format 'role: content'.
                    """
                    # Extract system content and remove system message
                    system_content, gemini_style_message_history = self.gpt2gemini_history(message_history)
                    
                    if system_content is None:  # If no system message, use a default one
                        system_content = "You are a helpful assistant."
                    
                    response = self.client.models.generate_content(
                            model=self.LLM,
                            config=types.GenerateContentConfig(system_instruction=system_content),
                            contents=gemini_style_message_history
                        )
                    content = response.text
                    token_count = response.usage_metadata.total_token_count
                else:
                    # deepseek
                    response = self.client.complete(
                        messages=[
                            UserMessage(content=message_history)
                        ],
                        max_tokens=4048,
                        model=self.deployment_name
                    )
                    content = response.choices[0].message.content
                    token_count = response.usage.total_tokens

                if 'deepseek' in self.LLM:
                    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                result["response"] = content
                result["token_count"] = token_count
            except Exception as e:
                result["error"] = e
            finally:
                stop_event.set()

        thread = threading.Thread(target=api_call, daemon=True)
        thread.start()

        start_time = time.time()
        while not stop_event.is_set():
            elapsed = int(time.time() - start_time)
            sys.stdout.write(f"\r\t\t\t\t processing prompt (thinking...): {elapsed} seconds elapsed....\033[K")
            sys.stdout.flush()
            time.sleep(1)

        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

        if result["error"] is not None:
            logger.error(f"Error in API call: {result['error']}")
            return f"Error in API call: {result['error']}", 0

        return result["response"], result["token_count"]

    def generate_response_stream(self, message_history: list, sleep_time: float = 0):
        """
        Generate a response from the LLM based on the conversation history, streaming the output as it is generated.
        
            args:
                message_history - a list of messages in the conversation history, where each message is a dictionary with 'role' and 'content' keys.
                    Example: [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "What is the capital of France?"},
                        {"role": "assistant", "content": "The weather in Paris is currently sunny and 25°C."},
                        {"role": "user", "content": "What about the weather in London?"}
                    ]
                    
                    role = either "system", "user", or "assistant"

                sleep_time - time to sleep between chunks of the response, default is 0 seconds.        
        """

        #TODO: add deepseek support for streaming
        #TODO: add token counting for streaming responses and returning it

        if 'gpt' in self.LLM.lower():
            stream = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=message_history,
                stream=True
            )

            full_response = ""
            for chunk in stream:
                try:
                    content_piece = chunk.choices[0].delta.content
                    if content_piece:
                        print(content_piece, end="", flush=True)
                        full_response += content_piece
                        time.sleep(sleep_time)  # Sleep between chunks if specified
                except Exception:
                    pass

            print()

            token_count = self.count_tokens(full_response)
            return full_response, token_count

        elif 'gemini' in self.LLM.lower():
            system_content, gemini_style_message_history = self.gpt2gemini_history(message_history)
            if system_content is None:  # If no system message, use a default one
                system_content = "You are a helpful assistant."

            full_response = ""
            
            response = self.client.models.generate_content_stream(
                model=self.LLM,
                config=types.GenerateContentConfig(system_instruction=system_content),
                contents=gemini_style_message_history
            )

            for chunk in response:
                print(chunk.text, end="", flush=True)
                full_response += chunk.text
                time.sleep(sleep_time)  # Sleep between chunks if specified

            print()

            token_count = self.count_tokens(full_response)

            return full_response, token_count


    ################ helper functions ################
    def gpt2gemini_history(self, message_history: list):
        """
        Convert GPT-style message history to Gemini-style message history.
        
            args:
                message_history - a list of messages in the conversation history, where each message is a dictionary with 'role' and 'content' keys.
                    Example: [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": "What is the capital of France?"},
                        {"role": "assistant", "content": "The weather in Paris is currently sunny and 25°C."},
                        {"role": "user", "content": "What about the weather in London?"}
                    ]
                    
                    role = either "system", "user", or "assistant"        
        """
        system_content = None
        messages = [msg for msg in message_history if not (msg['role'] == 'system' and (system_content := msg['content']))]

        # Convert remaining messages to string format
        gemini_style_message_history = [f"{msg['role']}: {msg['content']}" for msg in messages]

        return system_content, gemini_style_message_history
    
    def get_working_gemini_api_key(self):
        api_key1 = os.getenv("GEMINI_API_KEY_2718")
        api_key2 = os.getenv("GEMINI_API_KEY_31416")
        api_key3 = os.getenv("GEMINI_API_KEY_16021")

        # manual (just uncomment the next line) 
        # return api_key3 

        # auto 
        api_keys = [(api_key1, "GEMINI_API_KEY_2718"), 
                    (api_key2, "GEMINI_API_KEY_31416"), 
                    (api_key3, "GEMINI_API_KEY_16021")]

        for api_key, env_var_name in api_keys:
            client = genai.Client(api_key=api_key)
            try:
                start_time = time.time()
                response = client.models.generate_content(
                    model=self.LLM,
                    contents="just return 1"
                )
                elapsed = time.time() - start_time
                logger.info(f"using gemini api key: {env_var_name}, time taken to check: {elapsed:.2f} seconds, token count: {response.usage_metadata.total_token_count}")
                return api_key
            except Exception:
                continue
            
        raise RuntimeError("No working Gemini API keys found.")
    
    def count_tokens(self, text):
        if 'gpt' in self.LLM.lower():
            tokenizer = tiktoken.get_encoding("cl100k_base")
            return len(tokenizer.encode(text))
        elif 'gemini' in self.LLM.lower():
            total_tokens = self.client.models.count_tokens(model=self.LLM, contents=text)
            return total_tokens


if __name__ == "__main__":
    model = "gpt-o3-mini"
    # model = "gemini-2.5-flash-preview-04-17"
    # model = "gemini-2.0-flash"
    # model = "deepseek-r1"

    llm = LLMmodel(llm=model)

    # checking the generate_response_basic function
    # sys_prompt = "you are a helpful AI assistant."
    # user_prompt = "tell me the capital of 10 random countries in the worldd."
    # res, tc = llm.generate_response_basic(sys_prompt, user_prompt)
    # print(res, tc)

    # checking the generate_response function
    message_history = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"},
        {"role": "assistant", "content": "The capital of France is Paris."},
        {"role": "user", "content": "What about the currency of this country?"}
    ]

    res, tc = llm.generate_response(message_history)
    print(res, tc)

    # checking the generate_response_stream function
    # message_history = [
    #     {"role": "system", "content": "You are a helpful assistant."},
    #     {"role": "user", "content": "What is the capital of France?"},
    #     {"role": "assistant", "content": "The capital of France is Paris."},
    #     {"role": "user", "content": "What about the currency of this country?"}
    # ]

    # res, tc = llm.generate_response_stream(message_history, sleep_time=0.1)
    # print(res, tc)