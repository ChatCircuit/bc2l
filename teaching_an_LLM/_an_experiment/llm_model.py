import llm.llm_model as llm_model

llm_model.Prepare_llm()  # prepare the LLM model
response, token_count = llm_model.generate_response(message_history=prompt_manager.get_prompt()) # call the LLM model to get the response


