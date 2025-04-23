import sqlite3
import networkx as nx
import os
import pickle
import re

# -------------------------------
# 1. Sample Netlist (as a multiline string)
# -------------------------------
sample_netlist = """
* Sample Netlist with Diverse Components and Commands
.PARAM Vdd=12 Vbias=2

* --- Passive and Active Components ---
R1 n1 n2 10k          ; Resistor between n1 and n2 (extended format)
+ ac=1m m=0.5 scale=1 temp=25 dtemp=0.5 tc1=0.01 tc2=0.02 noisy=0
C1 n2 GND 100nF       ; Capacitor between n2 and ground
L1 n3 n4 10mH         ; Inductor between n3 and n4
V1 n1 GND DC 5V       ; Independent voltage source (DC)
I1 n2 n3 DC 2mA       ; Independent current source (DC)
E1 n3 n4 n2 GND 10    ; Voltage-controlled voltage source (dependent V source)
G1 n4 n5 n2 GND 0.001 ; Voltage-controlled current source (dependent I source)
F1 n5 GND V1 0.5      ; Current-controlled current source (dependent I source)
H1 n1 n2 V1 GND 20    ; Current-controlled voltage source (dependent V source)

* --- Semiconductor Devices ---
Q1 n6 n2 GND NPN      ; Bipolar junction transistor (NPN)
M1 n7 n6 n8 n8 NMOS    ; MOS transistor (NMOS)
D1 n8 n9 Dmodel       ; Diode using predefined model

* --- Device Models ---
.model Dmodel D(Is=1e-14)       ; Diode model definition
.model NPN NPN(Bf=100)          ; BJT model definition
.model NMOS NMOS(VTO=1)           ; NMOS model definition

* --- Subcircuit Definition ---
.SUBCKT amplifier in out Vdd Vss
R2 in mid 1k                ; Resistor in subcircuit
R3 mid out 1k               ; Resistor in subcircuit
Q2 mid in Vss NPN           ; Transistor in subcircuit
.ENDS amplifier

* --- Subcircuit Instance ---
X1 n10 n11 n12 n13 amplifier  ; Instance of amplifier subcircuit
                              ; Ports: in = n10, out = n11, Vdd = n12, Vss = n13

* --- Simulation Commands ---
.tran 0 10ms                ; Transient analysis
.dc V1 0 5 0.5              ; DC sweep from 0 to 5V in 0.5V steps on V1
.ac dec 10 1 1k             ; AC analysis (decade sweep from 1Hz to 1kHz)
.op                         ; Operating point analysis
.print tran V(n1) V(n2)     ; Print transient voltages at n1 and n2
.meas tran delay TRIG V(n1) VAL=5 RISE=1  ; Measure delay when V(n1) rises through 5V
.plot tran V(n1) V(n2)      ; Plot transient waveforms of V(n1) and V(n2)
.save V(n1) V(n2)          ; Save node voltages for later viewing
.probe all                ; Probe all nodes for debugging/inspection

.end                      ; End of netlist

"""

# File paths for saving the databases:
SQLITE_DB_PATH = "DB/netlist.db"
GRAPH_DB_PATH = "DB/netlist_graph.gpickle"

# -------------------------------
# 2. Parse the Netlist
# -------------------------------
def parse_netlist(netlist_text):
    """
    Parses a Spice netlist into a list of entries while preserving the original physical line number
    (orig_line_no) for each logical entry (which may span multiple lines due to '+' continuations).
    
    Features:
      - Lines starting with '+' are concatenated to the previous line.
      - Inline comments (after ';') are removed.
      - Allowed component/command types are recognized (case-insensitive).
      - Heuristic: tokens starting with 'n' or equal to 'GND' (case-insensitive) are taken as nets.
      
    Returns:
      A list of dictionaries. Each dictionary contains:
        - orig_line_no: The physical line number of the first line of this logical entry.
        - raw_line: The complete, concatenated netlist line (without inline comments).
        - comp_id: The first token (component or command identifier).
        - nets: A list of tokens interpreted as connection nodes.
        - rest: The remaining tokens as a string.
    """
    combined_entries = []
    current_line = ""
    current_orig_line = None  # to hold the first physical line number for the logical entry
    
    # Iterate over physical lines with line number (starting at 1)
    for i, line in enumerate(netlist_text.splitlines(), start=1):
        line = line.rstrip()
        if not line or line.strip().startswith('*'):
            continue  # skip blank lines and full-line comments
        
        # Check for continuation line (starts with '+')
        if line.lstrip().startswith('+'):
            # Append (after stripping '+' and any extra whitespace)
            current_line += " " + line.lstrip()[1:].strip()
        else:
            # If there is a previous logical line, add it to the list.
            if current_line:
                combined_entries.append((current_orig_line, current_line))
            # Start a new logical line, and mark its originating physical line number.
            current_line = line.strip()
            current_orig_line = i
    if current_line:
        combined_entries.append((current_orig_line, current_line))
    
    # Allowed component/command regex (case-insensitive).
    allowed_pattern = re.compile(
        r"^(R|C|L|V|I|E|G|F|H|Q|M|D|X|\.MODEL|\.SUBCKT|\.TRAN|\.DC|\.AC|\.OP|\.PRINT|\.MEAS|\.PLOT|\.SAVE|\.PROBE|\.END|\.PARAM)",
        re.IGNORECASE
    )
    
    entries = []
    for orig_line_no, line in combined_entries:
        # Remove inline comments (anything after ';')
        if ';' in line:
            line = line.split(';')[0].strip()
        if not line:
            continue

        tokens = line.split()
        if not tokens:
            continue

        comp_id = tokens[0]
        # Optionally check if comp_id is allowed.
        if not allowed_pattern.match(comp_id):
            # Accepting any line for flexibility.
            pass

        nets = []
        rest_tokens = []
        for token in tokens[1:]:
            # Heuristic: token is a net if it is "GND" (any case) or starts with n/N.
            if token.upper() == "GND" or re.match(r"^[nN]\w*", token):
                nets.append(token)
            else:
                rest_tokens.append(token)
        
        entry = {
            "orig_line_no": orig_line_no,   # use the original physical line number
            "raw_line": line,
            "comp_id": comp_id,
            "nets": nets,
            "rest": " ".join(rest_tokens)
        }
        entries.append(entry)
    return entries

# -------------------------------
# 3. Build the SQLite (Tabular) Database
# -------------------------------
def create_sqlite_db(entries, db_path=SQLITE_DB_PATH):
    """
    Create an SQLite database to store netlist entries.
    Each entry uses the original physical line number (orig_line_no) as the line identifier.
    
    Table schema:
      - orig_line_no: INTEGER PRIMARY KEY (original line number from the netlist)
      - comp_id: TEXT
      - nets: TEXT (comma-separated)
      - rest: TEXT
      - raw_line: TEXT (the complete netlist line)
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS netlist")
    cur.execute('''
        CREATE TABLE netlist (
            orig_line_no INTEGER PRIMARY KEY,
            comp_id TEXT,
            nets TEXT,
            rest TEXT,
            raw_line TEXT
        )
    ''')
    for entry in entries:
        nets_str = ",".join(entry["nets"])
        cur.execute(
            "INSERT INTO netlist (orig_line_no, comp_id, nets, rest, raw_line) VALUES (?, ?, ?, ?, ?)",
            (entry["orig_line_no"], entry["comp_id"], nets_str, entry["rest"], entry["raw_line"])
        )
    conn.commit()
    conn.close()
    print(f"=========> SQLite DB saved at {db_path} <=========")

# -------------------------------
# 4. Build the Graph Database (Bipartite)
# -------------------------------
def create_graph_db(entries, graph_db_path=GRAPH_DB_PATH):
    """
    Create a bipartite graph from the netlist entries with two types of nodes:
      - Component nodes: Each node is named "COMP_{comp_id}_{orig_line_no}"
      - Net nodes: Each net is named "NET_{net}"
    
    An edge is added between a component node and every net node that appears in its nets list.
    The graph is saved to file using pickle.
    """
    G = nx.Graph()
    for entry in entries:
        comp_node = f"COMP_{entry['comp_id']}_{entry['orig_line_no']}"
        G.add_node(comp_node, type="component",
                   comp_id=entry["comp_id"],
                   orig_line_no=entry["orig_line_no"],
                   raw_line=entry["raw_line"])
        for net in entry["nets"]:
            net_node = f"NET_{net}"
            if not G.has_node(net_node):
                G.add_node(net_node, type="net", net=net)
            G.add_edge(comp_node, net_node)
    # Optionally store lists of component and net nodes.
    G.graph["components"] = [n for n, d in G.nodes(data=True) if d.get("type") == "component"]
    G.graph["nets"] = [n for n, d in G.nodes(data=True) if d.get("type") == "net"]
    
    with open(graph_db_path, "wb") as f:
        pickle.dump(G, f)
    print(f"=========> Graph DB saved at {graph_db_path} <=========")
    return G

# -------------------------------
# 5. Query and Traversal Functions
# -------------------------------
def query_component(comp_query, db_path=SQLITE_DB_PATH):
    """
    Query the SQLite DB for entries whose comp_id contains the comp_query substring.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    query = "SELECT * FROM netlist WHERE comp_id LIKE ?"
    cur.execute(query, (f"%{comp_query}%",))
    results = cur.fetchall()
    conn.close()
    return results

def bfs_network(component_node, depth, graph=None, graph_db_path=None):
    """
    Perform a BFS on the graph starting from the specified component node (e.g., "COMP_R1_1"),
    and return the induced subgraph containing all nodes within the specified depth.
    """
    if graph == None:
        with open(graph_db_path, 'rb') as f:
            graph = pickle.load(f)
    nodes_in_bfs = set()
    lengths = nx.single_source_shortest_path_length(graph, component_node, cutoff=depth)
    nodes_in_bfs.update(lengths.keys())
    return graph.subgraph(nodes_in_bfs).copy()

def extract_subckt_by_nodes(desired_nets, graph=None, graph_db_path=None):
    """
    Given a graph G and a list (or set) of desired net names (e.g., ["n1", "n2", "n4"]),
    attempt to extract a subcircuit (subgraph) that is completely bounded by those nets.
    
    Steps:
      1. Convert desired net names to graph node names (i.e., prefix with "NET_").
      2. For every component node in G, check if all of its connected nets are in the desired set.
         Those that are fully bounded are considered inside the subcircuit.
      3. Form the subgraph induced by the union of these component nodes and the desired net nodes.
      4. Verify that none of the component nodes in the subgraph has any edge to a net node outside
         the desired set (i.e. check for leakage).
    
    Returns:
      - subckt_graph: The induced subgraph (if any components are found).
      - leakage: A boolean flag indicating if any component node is connected to an external net.
      - subckt_netlist: A list of raw netlist lines (component snippets) forming the subcircuit,
                        if the subcircuit is properly bounded. If no component is bounded or leakage exists,
                        an appropriate message is returned.
    """
    if graph == None:
        with open(graph_db_path, 'rb') as f:
            graph = pickle.load(f)
    
    # Convert desired net names to the graph's naming convention.
    desired_net_nodes = set(f"NET_{net}" for net in desired_nets)
    
    # Identify component nodes that are completely bounded by the desired nets.
    bounded_components = set()
    for node, data in graph.nodes(data=True):
        if data.get("type") == "component":
            # Get all neighbor nodes (expected to be net nodes).
            neighbor_nets = set(n for n in graph.neighbors(node) if graph.nodes[n].get("type") == "net")
            # If all neighbor net nodes are within the desired set, include this component.
            if neighbor_nets.issubset(desired_net_nodes):
                bounded_components.add(node)
    
    if not bounded_components:
        return None, True, "No bounded components found for the given nets."
    
    # The subcircuit is induced by the union of bounded components and the desired net nodes.
    subckt_nodes = bounded_components.union(desired_net_nodes)
    subckt_graph = graph.subgraph(subckt_nodes).copy()
    
    # Check for leakage: any bounded component that still connects to a net outside desired_net_nodes.
    leakage = False
    for comp in bounded_components:
        # Consider all neighbor net nodes of the component.
        neighbor_nets = set(n for n in graph.neighbors(comp) if graph.nodes[n].get("type") == "net")
        if not neighbor_nets.issubset(desired_net_nodes):
            leakage = True
            break

    # Prepare the netlist snippet (only if no leakage is detected).
    if leakage:
        subckt_netlist = "Leakage detected: Some components connect to nets outside the desired set."
    else:
        # Retrieve the raw netlist line from each bounded component.
        lines = []
        for comp in sorted(bounded_components):  # Sorting for consistent order.
            raw_line = graph.nodes[comp].get("raw_line")
            if raw_line:
                lines.append(raw_line)
        subckt_netlist = "\n".join(lines) if lines else "No netlist lines found."
    
    return subckt_graph, leakage, subckt_netlist

# -------------------------------
# 6. Verification Function
# -------------------------------
def verify_database_functions(sqlite_db_path=SQLITE_DB_PATH,
                              graph_db_path=GRAPH_DB_PATH):
    """
    1) Build SQLite + Graph DBs from sample netlist.
    2) Query "R1", print results.
    3) BFS depth=2 around R1, print nodes & edges.
    4) Extract subckt by nets ["n1","n2","GND"], print snippet.
    5) Update R1 via update_component_line, then re-query & show updated rows.
    6) Inspect graph node attributes & BFS again to confirm wiring.
    """
    with open(graph_db_path, "rb") as f: 
        G = pickle.load(f)

    # 1) Component search
    print("\n--- Query Results for 'R1' ---")
    rows = query_component("R1", db_path=sqlite_db_path)
    if not rows:
        print("No 'R1' found.")
        return
    for r in rows:
        print(r)

    # 2) BFS (depth=2)
    orig_ln, comp_id, nets_str, rest, raw = rows[0]
    comp_node = f"COMP_{comp_id}_{orig_ln}"
    print(f"\n--- BFS Network from {comp_node} (depth=2) ---")
    subg = bfs_network(comp_node, depth=2, graph=G)
    print("Nodes:")
    for n,d in subg.nodes(data=True):
        print(" ", n, d)
    print("Edges:")
    for u,v in subg.edges():
        print(" ", u, "--", v)

    # 3) Subcircuit extraction
    desired = ["n1","n2","GND"]
    subckt_g, leakage, snippet = extract_subckt_by_nodes(graph=G, desired_nets=desired)
    print("\n--- Subcircuit Extraction ---")
    print("Leakage detected." if leakage else "Properly bounded.")
    print(snippet)

    # 4) Update R1 and re-verify
    new_line = "R1 n1 n2 20k ac=2m"
    print("\n--- Updating R1 to:", new_line, "---")
    update_component_line("R1", new_line,
                          sqlite_db_path=sqlite_db_path,
                          graph_db_path=graph_db_path)

    # Re-query SQLite
    print("\n--- Post‑update SQLite rows for 'R1' ---")
    updated = query_component("R1", db_path=sqlite_db_path)
    for r in updated:
        print(r)

    # Inspect graph node and BFS again
    orig_ln2, _, _, _, _ = updated[0]
    node2 = f"COMP_R1_{orig_ln2}"
    with open(graph_db_path, "rb") as f:
        G2 = pickle.load(f)
    print(f"\n[Graph] Attributes of {node2}:")
    print(G2.nodes[node2])

    print(f"\n[Graph] BFS from {node2} (depth=1):")
    subg2 = bfs_network(node2, depth=1, graph=G2)
    for nbr in subg2.neighbors(node2):
        print(" ", nbr)

    print("\nVerification complete.")

# -------------------------------
# 7. Update line(s) on DBs
# -------------------------------

def update_component_line(component_name,
                          new_line,
                          sqlite_db_path="netlist.db",
                          graph_db_path="netlist_graph.pkl"):
    """
    Update all entries in both the SQLite DB and the pickled NetworkX graph
    for the given comp_id == component_name, replacing them with new_line.
    """
    # 1) Parse the new line. Expect exactly one entry.
    new_entries = parse_netlist(new_line)
    if len(new_entries) != 1:
        raise ValueError(f"Expected exactly one parsed entry; got {len(new_entries)}")
    upd = new_entries[0]

    # 2) Update SQLite
    conn = sqlite3.connect(sqlite_db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT orig_line_no, comp_id FROM netlist WHERE comp_id = ?",
        (component_name,)
    )
    rows = cur.fetchall()
    if not rows:
        conn.close()
        raise KeyError(f"No rows found for component '{component_name}' in SQLite DB")

    for orig_ln, old_comp in rows:
        nets_str = ",".join(upd["nets"])
        cur.execute(
            """
            UPDATE netlist
               SET raw_line = ?, nets = ?, rest = ?
             WHERE orig_line_no = ?
            """,
            (upd["raw_line"], nets_str, upd["rest"], orig_ln)
        )
    conn.commit()
    conn.close()
    print(f"\t[SQLite] Updated {len(rows)} row(s) for comp_id='{component_name}'")

    # 3) Update Graph
    with open(graph_db_path, "rb") as f:
        G = pickle.load(f)

    for orig_ln, old_comp in rows:
        node = f"COMP_{old_comp}_{orig_ln}"
        if node not in G:
            print(f"[Graph] Warning: node '{node}' not found; skipping")
            continue

        # Overwrite attributes
        G.nodes[node]["raw_line"] = upd["raw_line"]
        G.nodes[node]["comp_id"] = upd["comp_id"]
        G.nodes[node]["rest"] = upd["rest"]

        # Remove existing edges to nets
        for nbr in list(G.neighbors(node)):
            if G.nodes[nbr].get("type") == "net":
                G.remove_edge(node, nbr)

        # Reconnect to new nets
        for net in upd["nets"]:
            net_node = f"NET_{net}"
            if net_node not in G:
                G.add_node(net_node, type="net", net=net)
            G.add_edge(node, net_node)

    with open(graph_db_path, "wb") as f:
        pickle.dump(G, f)
    print(f"\t[Graph] Updated component-node(s) for comp_id='{component_name}'")

# -------------------------------
# 8. Main
# -------------------------------

def main(New_Netlist=None, sqlite_path = None, graph_path = None, sample_test = True):
    global sample_netlist, SQLITE_DB_PATH, GRAPH_DB_PATH
    if New_Netlist != None:
        sample_netlist = New_Netlist
    if sqlite_path != None:
        SQLITE_DB_PATH = sqlite_path
    if graph_path != None:
        GRAPH_DB_PATH = graph_path
    # Parse the sample netlist.
    entries = parse_netlist(sample_netlist)
    # Create the SQLite (tabular) database.
    create_sqlite_db(entries)
    # Create the graph database.
    graph = create_graph_db(entries)

    if sample_test == True:
        verify_database_functions(SQLITE_DB_PATH, GRAPH_DB_PATH)

    return


if __name__ == "__main__":
    main(sample_test=True)
