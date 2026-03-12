"""
Query Pipefy for cards currently in the '00OM | Log HQ Info/Send Instructions' phase.
Run this to get the phase_id first:
  python pipefy_query.py --get-phases
Then set PHASE_ID below and run normally to get cards.
"""

import requests
import json
import sys
import os

PIPEFY_TOKEN = os.environ.get("PIPEFY_TOKEN", "YOUR_TOKEN_HERE")
PIPE_ID = "304203599"

HEADERS = {
    "Authorization": f"Bearer {PIPEFY_TOKEN}",
    "Content-Type": "application/json"
}

def graphql(query, variables=None):
    body = {"query": query}
    if variables:
        body["variables"] = variables
    r = requests.post("https://api.pipefy.com/graphql", headers=HEADERS, json=body)
    r.raise_for_status()
    return r.json()

def get_phases():
    """Get all phases and their IDs for the pipe."""
    q = """
    query($pipe_id: ID!) {
      pipe(id: $pipe_id) {
        phases {
          id
          name
          cards_count
        }
      }
    }
    """
    data = graphql(q, {"pipe_id": PIPE_ID})
    phases = data["data"]["pipe"]["phases"]
    return phases

def get_cards_in_phase(phase_id):
    """Get all cards currently in a specific phase."""
    q = """
    query($phase_id: ID!) {
      phase(id: $phase_id) {
        name
        cards(first: 50) {
          edges {
            node {
              id
              title
              fields {
                field { id label }
                value
              }
            }
          }
        }
      }
    }
    """
    data = graphql(q, {"phase_id": phase_id})
    phase = data["data"]["phase"]
    cards = [edge["node"] for edge in phase["cards"]["edges"]]
    
    result = []
    for card in cards:
        fields_map = {}
        for f in card["fields"]:
            fields_map[f["field"]["id"]] = f["value"]
        
        result.append({
            "id": card["id"],
            "title": card["title"],
            "chain_name": fields_map.get("chain_name", card["title"]),
            "primary_hq_alias": fields_map.get("primary_hq_alias", ""),
            "secondary_hq_alias": fields_map.get("secondary_hq_alias", ""),
            "poc_first_name": fields_map.get("poc_first_name", ""),
            "poc_last_name": fields_map.get("poc_last_name", ""),
        })
    
    return phase["name"], result

if __name__ == "__main__":
    if "--get-phases" in sys.argv:
        phases = get_phases()
        print("Phases in pipe 304203599:")
        for p in phases:
            print(f"  [{p['id']}] {p['name']} — {p['cards_count']} cards")
    else:
        phase_id = sys.argv[1] if len(sys.argv) > 1 else None
        if not phase_id:
            print("Usage: python pipefy_query.py <phase_id>")
            print("       python pipefy_query.py --get-phases")
            sys.exit(1)
        name, cards = get_cards_in_phase(phase_id)
        print(f"Phase: {name}")
        print(json.dumps(cards, indent=2))
