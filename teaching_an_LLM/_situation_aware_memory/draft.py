import networkx as nx


from pyvis.network import Network
import webbrowser
def plot_graph(graph, short_label_length: int = 20):
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



# Create a directed graph
G = nx.DiGraph()

# nodes = {
#     1: "ngspice",
#     2: "it is a circuit simulator",
#     3: "there are 4 ways to measure current in ngspice",
#     4: "use .probe command",
#     5: ".probe command can be used to measure current, power, and voltages",
#     6: "use 0V voltage source in series to measure branch current",
#     7: "use .options savecurrents to automatically save current for supported devices",
# }

# edges = [
#     (1, 2, "what is it?"),
#     (1, 3, "how to measure current?"),
#     (3, 4, "what is way 1?"),
#     (4, 5, "what can be measured with .probe?"),
#     (3, 6, "what is way 2?"),
#     (3, 7, "what is way 3?")
# ]

nodes = {
  "n1": "Ngspice allows current measurement through device terminals using various techniques.",
  "n2": "Using `I(Xdevice)` or `I(Vname)` syntax in the netlist, Ngspice measures current through subcircuits or voltage sources.",
  "n3": "Ngspice can use a voltage source with `dc 0V` in series with a component to extract current via `vsource#branch`.",
  "n4": "The `.probe` command is used to measure device node currents, power dissipation, and differential voltages.",
  "n5": "`.probe I(device)` and `.probe I(device,node)` are used to measure current at all or specific terminals of a device.",
  "n6": "Voltage sources introduced by `.probe` have `0V` to avoid altering circuit behavior.",
  "n7": "`.probe` also supports differential voltage (`vd`) and power (`p`) measurements using internal mechanisms.",
  "n8": "`.options savecurrents` automatically saves terminal currents using `.save @device[i]` syntax.",
  "n9": "Unlike `.probe`, `.options savecurrents` does not create new nodes but consumes more memory.",
  "n10": "`.options savecurrents` does not support AC simulations; vectors will be empty.",
  "n11": "MOSFET-specific options like `.options savecurrents_bsim3` allow model-specific current tracking.",
  "n12": "All current measurement approaches rely on inserting voltage sources or saving internal current vectors."
}

edges = [
  ("n1", "n2", "How can Ngspice syntax be used directly to measure current?"),
  ("n1", "n3", "What method involves using a zero-volt voltage source for measuring current?"),
  ("n1", "n4", "What command in Ngspice provides current and voltage probing features?"),
  ("n4", "n5", "How does `.probe` command measure current at device terminals?"),
  ("n5", "n6", "Why does `.probe` use 0V voltage sources when measuring current?"),
  ("n4", "n7", "What else can `.probe` measure besides current?"),
  ("n1", "n8", "What `.options` setting enables auto-saving of terminal currents?"),
  ("n8", "n9", "What is the memory impact of using `.options savecurrents`?"),
  ("n8", "n10", "What are the simulation-type limitations of `.options savecurrents`?"),
  ("n8", "n11", "What MOSFET-specific options are available for saving currents?"),
  ("n2", "n12", "How are internal voltage sources or vectors used in current measurements?"),
  ("n3", "n12", "How does adding a 0V voltage source affect current measurement?"),
  ("n4", "n12", "How does `.probe` enable current vector generation internally?"),
  ("n8", "n12", "How does `.options savecurrents` generate current output vectors?")
]


for node_id, description in nodes.items():
    G.add_node(node_id, memory=description)

for src, dst, label in edges:
    G.add_edge(src, dst, label=label)


plot_graph(G)


