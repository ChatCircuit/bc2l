from pyvis.network import Network
import webbrowser
import json
import networkx as nx


import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from logger import get_logger
logger = get_logger(__name__)

class SAMmaker:
    def __init__(self, model="gemini-2.5-flash-preview-05-20"):
        from sam_maker_prompt import get_prompt
        from llm_model_streamer import LLMmodel

        self.model = model
        self.llm = LLMmodel(self.model) 
        self.system_content = get_prompt()

    def convert2structured_text(self, text: str):
        """
        Converts the given text to structured text.
        """
        # For now, we just return the text as is
        instruction = r"""Sort out the given text, concept and topic-wise. Try to include all examples provided in the text."""
        logger.info(f"Converting text to structured text using model: {self.model}")
        
        # TODO: using same model for text -> structured text and structured text -> graph may not be a good idea always.

        res, _= self.llm.generate_response(message_history=[
            {"role": "system", "content": instruction},
            {"role": "user", "content": text}
        ])
        logger.info(f"Structured text: {res}")

        return res


    def make(self, stimulus_type: str, stimulus: str):
        """
            args:
                stimulus_type - text | file/text
                stimulus - if stimulus_type is "text", then it is a string containing the text stimulus. 
                            If stimulus_type is "file/text", then it is a string containing the path to the file containing the text stimulus.
            returns:
                A NetworkX DiGraph object representing the memory graph.
        """

        # processing stimulus based on its type
        if stimulus_type == "text":
            pass
        elif stimulus_type == "file/text":
            stimulus = open(stimulus, "r").read() # reading the text from the file into stimulus

        # stimulus -> structured text
        structured_text = self.convert2structured_text(stimulus)

        # structured text -> graph
        res, _ = self.llm.generate_response(message_history=[
                                    {"role": "system", "content": self.system_content},
                                    {"role": "user", "content": structured_text}
                    ])
        # TODO: for gemini, use its api feature of directly returning json response.
        if "gemini" in self.model:
            # Gemini model returns a string with a prefix "json\n"
            # We need to strip the prefix and the backticks
            res = res.strip("`").removeprefix("json\n")


        # Parse the JSON response as a graph
        logger.info("converting stuctured text to graph")
        try:
            data = json.loads(res)
        except Exception as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.info(f"LLM response: {res}")
            return None

        # Create a directed graph
        G = nx.DiGraph()

        # Add nodes
        for node in data.get("nodes", []):
            G.add_node(node["id"], memory=node.get("memory", ""))

        # Add edges
        for edge in data.get("edges", []):
            G.add_edge(edge["source"], edge["target"], label=edge.get("label", ""))

        return G

    def vectorize_memory(self, graph):
        """
        Vectorizes the memory of each node in the graph using a simple hash function.
        This is a placeholder for actual vectorization logic.
        """
        for node_id, data in graph.nodes(data=True):
            memory = data['memory']
            # Simple hash as a placeholder for vectorization
            vector = hash(memory) % (10 ** 8)
            # Store the vector in the node data
            graph.nodes[node_id]['vector'] = vector
        return graph
    
    
    def plot_memory_graph(self, graph, short_label_length: int = 10):
        G = graph

        net = Network(notebook=True, directed=True, height="750px", width="100%", bgcolor="#FFFFFF", font_color="black")

        # Add nodes with short label and full text as tooltip/title
        for node_id, data in G.nodes(data=True):
            full_text = data['memory']
            short_label = full_text[:short_label_length] + "..." if len(full_text) > short_label_length else full_text
        
            net.add_node(
                node_id,
                label=short_label,
                title=self.insert_line_breaks(full_text),
                color='#ADD8E6',
                size=20
            )

        # Add edges
        for source, target in G.edges():
            edge_label = G.edges[source, target].get('label', '')
            net.add_edge(source, target, label=edge_label[:short_label_length] + "..." if len(edge_label) > short_label_length else edge_label, title=self.insert_line_breaks(edge_label))

        # net.from_nx(G)
    
        # Set visualization options
        net.set_options("""
        var options = {
        "nodes": {
            "font": { "size": 10 }
        },
        "edges": {
            "font": {
            "size": 10,
            "align": "middle"
            },
            "smooth": {
            "forceDirection": "none"
            }
        },
        "physics": {
            "repulsion": {
            "centralGravity": 0.1,
            "damping": 0.09,
            "nodeDistance": 150,
            "springConstant": 0.08,
            "springLength": 120
            },
            "minVelocity": 0.75,
            "solver": "repulsion"
        },
        "interaction": {
            "tooltipDelay": 0,
            "hover": true,
            "selectable": true,
            "multiselect": false
        }
        }
        """)


        # Generate and save the HTML file
        net.show("graph_vis.html")

        # Inject custom JS for double-click copy
        with open("graph_vis.html", "r+", encoding="utf-8") as f:
            html = f.read()
            f.seek(0)
            # Insert JS before the closing </script> tag
            custom_js = """
                    <script type="text/javascript">
            network.on("doubleClick", function (params) {
                if (params.nodes.length > 0) {
                    var nodeId = params.nodes[0];
                    var node = nodes.get(nodeId);
                    var fullText = node.title; // Use the full text from the title attribute
                    navigator.clipboard.writeText(fullText).then(function () {
                        // Create the popup
                        var popup = document.createElement("div");
                        popup.innerText = "Copied!";
                        popup.style.position = "fixed";
                        popup.style.bottom = "30px";
                        popup.style.left = "50%";
                        popup.style.transform = "translateX(-50%)";
                        popup.style.backgroundColor = "#333";
                        popup.style.color = "#fff";
                        popup.style.padding = "10px 20px";
                        popup.style.borderRadius = "8px";
                        popup.style.boxShadow = "0 2px 8px rgba(0,0,0,0.2)";
                        popup.style.zIndex = 1000;
                        popup.style.fontSize = "14px";
                        popup.style.opacity = "0";
                        popup.style.transition = "opacity 0.3s ease-in-out";
                        document.body.appendChild(popup);

                        // Fade in
                        setTimeout(() => popup.style.opacity = "1", 10);

                        // Remove after 2 seconds
                        setTimeout(() => {
                            popup.style.opacity = "0";
                            setTimeout(() => document.body.removeChild(popup), 300);
                        }, 2000);
                    }, function (err) {
                        console.error("Failed to copy: ", err);
                    });
                }
            });
            </script>
            </body>
            """


            html = html.replace("</body>", custom_js)
            f.write(html)
            f.truncate()

        webbrowser.open("graph_vis.html")
        print("Interactive graph saved to graph_vis.html and opened in your browser.")

    def insert_line_breaks(self, text, max_line_length=80):
        return '  \n'.join(text[i:i+max_line_length] for i in range(0, len(text), max_line_length))



if __name__ == "__main__":
    sam_maker = SAMmaker(model="gemini-2.5-flash-preview-04-17")  # You can change the model here
    
    # Example usage:

    ################################
    ######## text stimulus #########
    ################################

    # stimulus = r"""The capital of France is Paris. Paris is known for its art, fashion, and culture. The Eiffel Tower is a famous landmark in Paris."""""
    # graph = sam_maker.make("text", stimulus)
    # sam_maker.plot_memory_graph(graph)


    ################################
    ######## file/text stimulus #########
    ################################
    stimulus = r"H:\NOTHING\#Projects\bring_ckt_to_life_project\code\teaching_an_LLM\_situation_aware_memory\reference _material\baileylove_medical_text.txt"

    graph = sam_maker.make("file/text", stimulus)
    sam_maker.plot_memory_graph(graph)
