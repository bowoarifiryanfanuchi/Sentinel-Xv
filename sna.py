import networkx as nx
import json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "sentinel_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "password")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

ALPHA = 0.6  # Weight for Views
BETA = 0.4   # Weight for Likes

def generate_sna_graph(output_file="output_graph.gexf"):
    """Generates an SNA graph from database records and exports to GEXF."""
    G = nx.DiGraph()  # Directed graph to show who attacks/defends whom
    
    print("Fetching data from database...")
    try:
        with engine.connect() as conn:
            # We use text() explicitly for the raw SQL query
            result = conn.execute(text("""
                SELECT akun, views, likes, attacked_json, defended_json
                FROM analytics_data
                WHERE attacked_json IS NOT NULL OR defended_json IS NOT NULL
            """))
            rows = result.fetchall()
            
    except Exception as e:
        print(f"Database error: {e}")
        return

    print(f"Processing {len(rows)} records for graph generation...")

    for row in rows:
        akun = row[0]
        views = row[1] if row[1] is not None else 0
        likes = row[2] if row[2] is not None else 0
        
        # Parse JSON lists safely
        try:
            attacked = json.loads(row[3]) if row[3] else []
            defended = json.loads(row[4]) if row[4] else []
        except:
            attacked = []
            defended = []

        # Ensure akun node exists and add weight
        if not G.has_node(akun):
            G.add_node(akun, type="account", weight=0)
            
        # Update node weight
        node_weight = (ALPHA * views) + (BETA * likes)
        G.nodes[akun]['weight'] = G.nodes[akun].get('weight', 0) + node_weight

        # Add edges and nodes for attacked entities
        for entity in attacked:
            if not G.has_node(entity):
                G.add_node(entity, type="entity", weight=0)
            
            # Add or update edge weight
            if G.has_edge(akun, entity):
                G[akun][entity]['weight'] += 1
            else:
                G.add_edge(akun, entity, type="attacks", weight=1)

        # Add edges and nodes for defended entities
        for entity in defended:
            if not G.has_node(entity):
                G.add_node(entity, type="entity", weight=0)
                
            # Add or update edge weight
            if G.has_edge(akun, entity):
                G[akun][entity]['weight'] += 1
            else:
                G.add_edge(akun, entity, type="defends", weight=1)
                
        # Co-occurrence Edges (Undirected logically, but we add to DiGraph)
        # If A and B appear in the same row as targets, they are connected
        all_targets = attacked + defended
        for i in range(len(all_targets)):
            for j in range(i + 1, len(all_targets)):
                ent1, ent2 = all_targets[i], all_targets[j]
                
                # Check for existing edge in either direction
                if G.has_edge(ent1, ent2):
                     G[ent1][ent2]['weight'] += 1
                     G[ent1][ent2]['type'] = 'co-occurrence'
                elif G.has_edge(ent2, ent1):
                     G[ent2][ent1]['weight'] += 1
                     G[ent2][ent1]['type'] = 'co-occurrence'
                else:
                     G.add_edge(ent1, ent2, type="co-occurrence", weight=1)


    print(f"Graph generated: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges.")
    
    try:
        nx.write_gexf(G, output_file)
        print(f"Graph successfully exported to {output_file}")
    except Exception as e:
         print(f"Error exporting graph: {e}")

if __name__ == "__main__":
    generate_sna_graph()
