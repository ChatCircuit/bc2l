def get_prompt():
    return """Just give me the whole thing but in graph data structure. 

Key instructions to follow while making the graph:
- Try not to change the content very much from the given text. Try to keep the lines same as the given text. Your main job is to just find the relationships between the lines and make a graph out of it.
- Try to keep the memory snippets as short as possible(maybe one line or two), but they should still be meaningful.
- In case there are multiple things of something, do not give edge label like: "what is one type of X", "what is another type of X", "what is the third type of X", etc. Instead, give in these cases give edge name like: "what is first type of X", "what is second type of X", "what is third type of X", etc. Use 1st, 2nd, 3rd or 1,2,3 instead of one type, another type, etc.

Your response should always be in JSON format with the following structure:

{
  "nodes": [
    {
      "id": "1",
      "memory": "The content of the memory snippet."
    }
  ],
  "edges": [
    {
      "source": "source_id",
      "target": "target_id",
      "label": "A question that relates the source node to the target node."
    }
  ]
}

"""