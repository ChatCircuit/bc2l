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
                supported models: 'gpt-o3-mini', 'gpt-o4-mini', 
                                    'deepseek-r1', 
                                    'gemini-2.0-flash', 'gemini-2.5-flash-preview-04-17', and other gemini models: https://ai.google.dev/gemini-api/docs/models, rate limit: https://ai.google.dev/gemini-api/docs/rate-limits#free-tier
    """

    def __init__(self, llm='gpt-o3-mini'):
        self.LLM = llm
        self.api_key = None
        self.api_endpoint = None
        self.deployment_name = None
        self.api_version = None
        self.client = None
        self.tokenizer = None
        self.prepare_llm()

    def prepare_llm(self):
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
            self.api_key = os.getenv("GEMINI_API_KEY")
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
            self.client = genai.Client(api_key="AIzaSyBBMeE2Qluk-v2de60x35i3RpZjTVZtiJ4")

        logger.info(f"finished preparing llm. llm name: {self.LLM}")

    def count_tokens(self, text):
        if 'gpt' in self.LLM.lower():
            tokenizer = tiktoken.get_encoding("cl100k_base")
            return len(tokenizer.encode(text))
        elif 'gemini' in self.LLM.lower():
            total_tokens = self.client.models.count_tokens(model=self.LLM, contents=text)
            return total_tokens


    def generate_response_basic(self, System_Prompt, User_Prompt):
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
        # TODO: add gemini support in this function
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
                else:
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

    def generate_response_stream(self, System_Prompt, User_Prompt):
        if 'gpt' in self.LLM.lower():
            stream = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": System_Prompt},
                    {"role": "user",   "content": User_Prompt}
                ],
                stream=True
            )

            full_response = ""
            for chunk in stream:
                try:
                    content_piece = chunk.choices[0].delta.content
                    if content_piece:
                        print(content_piece, end="", flush=True)
                        full_response += content_piece
                        time.sleep(0.1)
                except Exception:
                    pass

            print()
            return full_response

        elif 'gemini' in self.LLM.lower():
            full_response = ""
            
            response = self.client.models.generate_content_stream(
                model=self.LLM,
                config=types.GenerateContentConfig(system_instruction=System_Prompt),
                contents=User_Prompt
            )

            for chunk in response:
                print(chunk.text, end="", flush=True)
                full_response += chunk.text

            print()
            return full_response

if __name__ == "__main__":
    # model = "gpt-o3-mini"
    # model = "gemini-2.0-flash"
    model = "deepseek-r1"

    llm = LLMmodel(llm=model)
    sys_prompt = "you are a helpful AI assistant."
    user_prompt = "tell me the capital of 100 random countries in the worldd."
    # llm.generate_response_stream(System_Prompt=sys_prompt, User_Prompt=user_prompt)
    res, tc = llm.generate_response_basic(sys_prompt, user_prompt)
    print(res, tc)