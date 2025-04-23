import re
import sqlite3
import networkx as nx
import pickle
import os
from tempfile import NamedTemporaryFile

# -------------------------------
# CONFIGURATION
# -------------------------------
SQLITE_DB_PATH = "netlist.db"
GRAPH_DB_PATH  = "netlist_graph.pkl"

# Simulation commands (always go at end if no same type instance exists)
SIM_CMDS = {
    ".TRAN", ".DC", ".AC", ".OP", ".PRINT",
    ".MEAS", ".PLOT", ".SAVE", ".PROBE", ".END", ".PARAM"
}

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


# -------------------------------
# 1) PARSE NETLIST LINES
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
    current_orig_line = None

    for i, line in enumerate(netlist_text.splitlines(), start=1):
        line = line.rstrip()
        if not line or line.strip().startswith('*'):
            continue
        if line.lstrip().startswith('+'):
            current_line += " " + line.lstrip()[1:].strip()
        else:
            if current_line:
                combined_entries.append((current_orig_line, current_line))
            current_line = line.strip()
            current_orig_line = i
    if current_line:
        combined_entries.append((current_orig_line, current_line))

    allowed_pattern = re.compile(
        r"^(R|C|L|V|I|E|G|F|H|Q|M|D|X|\\.MODEL|\\.SUBCKT|\\.TRAN|\\.DC|\\.AC|\\.OP|\\.PRINT|\\.MEAS|\\.PLOT|\\.SAVE|\\.PROBE|\\.END|\\.PARAM)",
        re.IGNORECASE
    )

    entries = []
    for orig_line_no, line in combined_entries:
        if ';' in line:
            line = line.split(';')[0].strip()
        if not line:
            continue

        tokens = line.split()
        if not tokens:
            continue

        comp_id = tokens[0]
        if not allowed_pattern.match(comp_id):
            pass

        nets = []
        rest_tokens = []
        for token in tokens[1:]:
            if token.upper() == "GND" or re.match(r"^[nN]\\w*", token):
                nets.append(token)
            else:
                rest_tokens.append(token)

        entry = {
            "orig_line_no": orig_line_no,
            "raw_line": line,
            "comp_id": comp_id,
            "nets": nets,
            "rest": " ".join(rest_tokens)
        }
        entries.append(entry)
    return entries

# -------------------------------
# 2) REBUILD SQLITE + GRAPH DB
# -------------------------------
def create_sqlite_db(entries, sqlite_db_path=SQLITE_DB_PATH):
    conn = sqlite3.connect(sqlite_db_path)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS netlist")
    cur.execute("""
        CREATE TABLE netlist (
            orig_line_no INTEGER PRIMARY KEY,
            comp_id TEXT,
            nets TEXT,
            rest TEXT,
            raw_line TEXT
        )
    """ )
    for idx, e in enumerate(entries, start=1):
        cur.execute(
            """
            INSERT INTO netlist (orig_line_no, comp_id, nets, rest, raw_line)
            VALUES (?, ?, ?, ?, ?)
            """,
            (idx, e["comp_id"], ",".join(e["nets"]), e["rest"], e["raw_line"])  
        )
    conn.commit()
    conn.close()

def create_graph_db(entries, graph_db_path=GRAPH_DB_PATH):
    G = nx.Graph()
    for idx, e in enumerate(entries, start=1):
        comp_node = f"COMP_{e['comp_id']}_{idx}"
        G.add_node(comp_node, type="component",
                   comp_id=e['comp_id'], orig_line_no=idx, raw_line=e['raw_line'])
        for net in e['nets']:
            net_node = f"NET_{net}"
            if not G.has_node(net_node):
                G.add_node(net_node, type="net", net=net)
            G.add_edge(comp_node, net_node)
    with NamedTemporaryFile("wb", delete=False) as tmp:
        pickle.dump(G, tmp)
    os.replace(tmp.name, graph_db_path)
    return G

def rebuild_databases_from_lines(lines, sqlite_db_path, graph_db_path):
    if isinstance(lines, (list, tuple)) and all(isinstance(item, str) for item in lines):
        text = "\n".join(lines)
    elif isinstance(lines, str):
        text = lines
    else:
        print("=====> Invalid input for building a netlist database...")
    entries = parse_netlist(text)
    create_sqlite_db(entries, sqlite_db_path)
    create_graph_db(entries, graph_db_path)

# -------------------------------
# 3) CORE QUERY & GRAPH HELPERS
# -------------------------------
def query_component(comp_query, db_path=SQLITE_DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT orig_line_no, comp_id, nets, rest, raw_line
          FROM netlist
         WHERE comp_id LIKE ?
        """, (f"%{comp_query}%",)
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def load_graph(graph_path=GRAPH_DB_PATH):
    with open(graph_path, "rb") as f:
        return pickle.load(f)

def bfs_network(start_node, depth, graph):
    nodes = nx.single_source_shortest_path_length(graph, start_node, cutoff=depth).keys()
    return graph.subgraph(nodes).copy()

def extract_subckt_by_nodes(graph, desired_nets):
    desired_set = set(f"NET_{n}" for n in desired_nets)
    bounded = []
    for n, d in graph.nodes(data=True):
        if d.get("type") == "component":
            nbrs = {nbr for nbr in graph.neighbors(n) if graph.nodes[nbr]["type"] == "net"}
            if nbrs.issubset(desired_set):
                bounded.append(n)
    if not bounded:
        return None, True, "No bounded components."
    sub_nodes = set(bounded) | desired_set
    subg = graph.subgraph(sub_nodes).copy()
    leakage = any(
        any(nbr not in desired_set for nbr in graph.neighbors(comp))
        for comp in bounded
    )
    if leakage:
        snippet = "Leakage detected."
    else:
        lines = []
        for comp in sorted(bounded, key=lambda x: graph.nodes[x]["orig_line_no"]):
            lines.append(graph.nodes[comp]["raw_line"])
        snippet = "\n".join(lines)
    return subg, leakage, snippet

# -------------------------------
# 4) LINE BUFFER HELPER
# -------------------------------
def get_all_lines(sqlite_db_path=SQLITE_DB_PATH):
    conn = sqlite3.connect(sqlite_db_path)
    cur = conn.cursor()
    cur.execute("SELECT raw_line FROM netlist ORDER BY orig_line_no")
    lines = [row[0] for row in cur.fetchall()]
    conn.close()
    return lines

# -------------------------------
# 5) ADD / DELETE
# -------------------------------
def add_line(new_line, sqlite_db_path=SQLITE_DB_PATH):
    lines = get_all_lines(sqlite_db_path=sqlite_db_path)
    entries = parse_netlist(new_line)
    if not entries:
        raise ValueError("Cannot parse new line")
    
    for k in range(entries.__len__()):
        comp_id = entries[k]["comp_id"]
        typ = comp_id[k].upper()
        is_cmd = comp_id.upper() in SIM_CMDS
        idx = None
        if not is_cmd:
            for i, line in enumerate(lines):
                ci = line.split()[0]
                if ci and ci[0].upper() == typ:
                    idx = i
                    break
            idx = 0 if idx is None else idx
        else:
            idx = len(lines)
        lines.insert(idx, new_line.strip())
        
    rebuild_databases_from_lines(lines)
    print(f"Added line at position {idx+1}: {new_line.strip()}")

def delete_by_line(orig_line_no):
    lines = get_all_lines()
    if orig_line_no < 1 or orig_line_no > len(lines):
        raise IndexError("orig_line_no out of range")
    removed = lines.pop(orig_line_no - 1)
    rebuild_databases_from_lines(lines)
    print(f"Deleted line {orig_line_no}: {removed}")

def delete_by_component(component_name):
    rows = query_component(component_name)
    if not rows:
        raise KeyError(f"No entries found for {component_name}")
    lines = get_all_lines()
    for orig_ln, *_ in sorted(rows, key=lambda r: -r[0]):
        removed = lines.pop(orig_ln - 1)
        print(f"  → Removed line {orig_ln}: {removed}")
    rebuild_databases_from_lines(lines)
    print(f"Deleted all {len(rows)} entries for '{component_name}'")

# -------------------------------
# 6) DIRECT UPDATE (no full rebuild)
# -------------------------------
def update_component_line(component_name, new_line,
                          sqlite_db_path=SQLITE_DB_PATH,
                          graph_db_path=GRAPH_DB_PATH):
    """
    Directly update entries with comp_id == component_name in both SQLite and Graph,
    without full rebuild.
    """
    # 1) Parse new line
    parsed = parse_netlist(new_line)
    if len(parsed) != 1:
        raise ValueError(f"Expected one parsed entry; got {len(parsed)}")
    upd = parsed[0]

    # 2) SQLite update
    conn = sqlite3.connect(sqlite_db_path)
    cur = conn.cursor()
    cur.execute("SELECT orig_line_no, comp_id FROM netlist WHERE comp_id = ?", (component_name,))
    rows = cur.fetchall()
    if not rows:
        conn.close()
        raise KeyError(f"No rows found for component '{component_name}'")
    for orig_ln, old_comp in rows:
        nets_str = ",".join(upd['nets'])
        cur.execute(
            """
            UPDATE netlist
               SET raw_line = ?, nets = ?, rest = ?
             WHERE orig_line_no = ?
            """,
            (upd['raw_line'], nets_str, upd['rest'], orig_ln)
        )
    conn.commit()
    conn.close()
    print(f"[SQLite] Updated {len(rows)} row(s) for '{component_name}'")

    # 3) Graph update
    with open(graph_db_path, "rb") as f:
        G = pickle.load(f)
    for orig_ln, old_comp in rows:
        node = f"COMP_{old_comp}_{orig_ln}"
        if node not in G:
            print(f"[Graph] Warning: node '{node}' not found; skipping")
            continue
        G.nodes[node]['raw_line'] = upd['raw_line']
        G.nodes[node]['rest'] = upd['rest']
        G.nodes[node]['comp_id'] = upd['comp_id']
        for nbr in list(G.neighbors(node)):
            if G.nodes[nbr].get('type') == 'net':
                G.remove_edge(node, nbr)
        for net in upd['nets']:
            net_node = f"NET_{net}"
            if net_node not in G:
                G.add_node(net_node, type='net', net=net)
            G.add_edge(node, net_node)
    # Save graph atomically
    with NamedTemporaryFile("wb", delete=False) as tmp:
        pickle.dump(G, tmp)
    os.replace(tmp.name, graph_db_path)
    print(f"[Graph] Updated component-node(s) for '{component_name}'")

def verify_database_functions(sqlite_db_path=SQLITE_DB_PATH,
                              graph_db_path=GRAPH_DB_PATH):
    """
    End-to-end sanity check of the netlist DB + graph pipeline:
      1) Build from a representative multi-line netlist.
      2) Query component “R1” and print rows.
      3) BFS to depth=2 on “R1” and list nodes & edges.
      4) Extract a subcircuit bounded by ['n1','n2','GND'] and print result.
      5) Update R1 in place, re-query and print updated rows.
      6) Inspect the updated graph node attributes.
      7) BFS to depth=1 on the updated node and list its neighbors.
    """
    # 1) Sample netlist (with a continuation line)
    sample = sample_netlist

    G = load_graph(graph_path=graph_db_path)

    # 2) Query “R1”
    print("\n--- Query Results for 'R1' ---")
    rows = query_component("R1", db_path=sqlite_db_path)
    if not rows:
        print("No 'R1' found.")
        return
    for r in rows:
        print(r)

    # 3) BFS (depth=2) around R1
    orig_ln, comp_id, nets_str, rest, raw = rows[0]
    comp_node = f"COMP_{comp_id}_{orig_ln}"
    print(f"\n--- BFS from {comp_node} (depth=2) ---")
    subg = bfs_network(comp_node, depth=2, graph=G)
    print("Nodes:")
    for n, d in subg.nodes(data=True):
        print("  ", n, d)
    print("Edges:")
    for u, v in subg.edges():
        print("  ", u, "--", v)

    # 4) Subcircuit extraction
    desired = ["n1", "n2", "GND"]
    subckt_g, leakage, snippet = extract_subckt_by_nodes(graph=G, desired_nets=desired)
    print("\n--- Subcircuit Extraction ---")
    print("Leakage detected." if leakage else "Properly bounded.")
    print(snippet)

    # 5) Update R1
    new_line = "R1 n1 n2 20k ac=2m"
    print(f"\n--- Updating R1 to: {new_line} ---")
    update_component_line("R1", new_line,
                          sqlite_db_path=sqlite_db_path,
                          graph_db_path=graph_db_path)

    # Re-query in SQLite
    print("\n--- Post-update Rows for 'R1' ---")
    updated = query_component("R1", db_path=sqlite_db_path)
    for r in updated:
        print(r)

    # 6) Inspect updated graph node
    new_ln = updated[0][0]
    node2 = f"COMP_R1_{new_ln}"
    G2 = load_graph(graph_db_path)
    print(f"\n--- Graph Node Attributes for {node2} ---")
    print(G2.nodes[node2])

    # 7) BFS (depth=1) around the updated node
    print(f"\n--- BFS from {node2} (depth=1) ---")
    subg2 = bfs_network(node2, depth=1, graph=G2)
    for nbr in subg2.neighbors(node2):
        print("  ", nbr)

    print("\nVerification complete.")

def main(New_Netlist=None, sqlite_path = None, graph_path = None, sample_test = True):
    global sample_netlist, SQLITE_DB_PATH, GRAPH_DB_PATH
    if New_Netlist != None:
        with open("sample_netlist.cir", 'r') as f:
            sample_netlist = f.read()
    if sqlite_path != None:
        SQLITE_DB_PATH = sqlite_path
    if graph_path != None:
        GRAPH_DB_PATH = graph_path
    # Parse the sample netlist.
    entries = rebuild_databases_from_lines(sample_netlist,SQLITE_DB_PATH, GRAPH_DB_PATH)

    lines = get_all_lines(SQLITE_DB_PATH)
    print("=====> Printed from database:\n")
    print(lines)

    if sample_test == True:
        verify_database_functions(SQLITE_DB_PATH, GRAPH_DB_PATH)

    return

# -------------------------------
# 7) Example Usage
# -------------------------------
if __name__ == "__main__":
    main(New_Netlist=None, sqlite_path=SQLITE_DB_PATH, graph_path=GRAPH_DB_PATH, sample_test=True)