from pyvis.network import Network
import webbrowser


class SAMmaker:
    def __init__(self, model="gpt-o3-mini"):
        from sam_maker_prompt import get_prompt
        from llm_model_streamer import LLMmodel

        self.model = model
        self.llm = LLMmodel(self.model)
        self.sys_prompt = get_prompt()

    def make(self, stimulus):

        """
            args:
                stimulus - what would be included as stimulus?
            returns:
                memory_snippet - a dictionary of format: {"id":"<>", "content":"<>", "source":"<>"}. all three field = None would mean, no memory snippet should be produced based on the stimulus provided
        """
        res, tc = self.llm.generate_response_basic(self.sys_prompt, stimulus)

    def plot_memory_graph(self, graph, short_label_length: int = 20):
        G = graph

        net = Network(notebook=True, directed=True, height="750px", width="100%", bgcolor="#FFFFFF", font_color="black")

        # Add nodes with short label and full text as tooltip/title
        for node_id, data in G.nodes(data=True):
            full_text = data['memory']
            short_label = full_text[:short_label_length] + "..." if len(full_text) > short_label_length else full_text
            net.add_node(
                node_id,
                label=short_label,
                title=full_text,
                color='#ADD8E6',
                size=20
            )

        # Add edges
        for source, target in G.edges():
            edge_label = G.edges[source, target].get('label', '')
            net.add_edge(source, target, label=edge_label[:short_label_length] + "..." if len(edge_label) > short_label_length else edge_label, title=edge_label)

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
                    var fullText = node.text;
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



        