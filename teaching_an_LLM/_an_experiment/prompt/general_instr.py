def get_general_instruction():
    return """you first produce a draft answer. if the answer and query is related to ngspice, you chunkify the answer by lines or blocks for debugging purpose. for every chunk you make some relevant questions for the purpose of validation/debugging of that portion of your answer. these questions will be passed onto a RAG system to retreive answer of these questions. 

always reply in the following JSON format:
{{
	"draft_answer":"<your draft answer>",
	"chunks":[
			{{"chunk": "<>",	"RAG_query":"<>"}},
			{{"chunk": "<>", "RAG_query":"<>"}},
			....
		]
}}

"""
