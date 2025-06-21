# node.py
# This script simulates a single general in the Byzantine army.

import os
import sys
import time
import requests
from flask import Flask, request, jsonify
from collections import defaultdict

# --- Configuration ---
app = Flask(__name__)

# Node's identity is set from environment variables
NODE_ID = int(os.environ.get('NODE_ID', 0))
IS_COMMANDER = os.environ.get('IS_COMMANDER', 'false').lower() == 'true'
IS_TRAITOR = os.environ.get('IS_TRAITOR', 'false').lower() == 'true'
INITIAL_ORDER = os.environ.get('ORDER', 'attack') # Commander's initial order

# Get peer nodes from command-line arguments
PEERS = sys.argv[1:]
LIEUTENANT_PEERS = [p for p in PEERS if f"node{NODE_ID}" not in p and "node0" not in p]
COMMANDER_URL = f"http://node0:5000"

# State variables
# Stores the initial order received from the commander
order_from_commander = None
# Stores orders relayed from other lieutenants, e.g., {'from_node2': 'attack'}
orders_from_peers = {}
# Total number of lieutenants in the system
num_lieutenants = len(PEERS) if IS_COMMANDER else len(PEERS) -1

# --- Helper Functions ---
def print_log(message):
    """Prints a log message with the node's identity."""
    # Flush ensures the logs appear in order when running with docker-compose
    print(f"[Node {NODE_ID}{' (C)' if IS_COMMANDER else ''}{' (T)' if IS_TRAITOR else ''}]: {message}", flush=True)

def decide_majority(orders):
    """Calculates the majority vote from a dictionary of received orders."""
    if not orders:
        return "no majority"
    
    votes = list(orders.values())
    vote_counts = defaultdict(int)
    for vote in votes:
        vote_counts[vote] += 1

    # Check for a clear majority
    max_votes = 0
    majority_order = "no majority"
    
    # Find the order with the most votes
    for order, count in vote_counts.items():
        if count > max_votes:
            max_votes = count
            majority_order = order
            
    # Check if there's a tie
    contenders = [order for order, count in vote_counts.items() if count == max_votes]
    if len(contenders) > 1:
        return "no majority" # Tie means no consensus
        
    return majority_order

# --- API Endpoints ---
@app.route('/order', methods=['POST'])
def receive_order():
    """Endpoint for lieutenants to receive orders."""
    global order_from_commander, orders_from_peers
    data = request.json
    sender_id = data.get('sender_id')
    order = data.get('order')
    
    print_log(f"Received order '{order}' from Node {sender_id}.")

    # If the order is from the commander (Node 0)
    if sender_id == 0:
        order_from_commander = order
        
        # Now, as a lieutenant, relay this order to all other lieutenants
        relay_order = order
        # A traitorous lieutenant changes the order before relaying
        if IS_TRAITOR:
            relay_order = "retreat" if order == "attack" else "attack"
            print_log(f"As a traitor, I will relay '{relay_order}' instead.")
        
        for peer in LIEUTENANT_PEERS:
            try:
                requests.post(f"{peer}/order", json={'sender_id': NODE_ID, 'order': relay_order}, timeout=2)
            except requests.exceptions.RequestException as e:
                print_log(f"Could not relay order to {peer}. Error: {e}")

    # If the order is from another lieutenant (a relayed order)
    else:
        orders_from_peers[f"from_node{sender_id}"] = order

    return jsonify({"status": "ack"})

# --- Main Application Logic ---
def run_simulation():
    """Main function to start the Byzantine agreement process."""
    # Give all nodes a moment to start up
    time.sleep(5) 
    
    if IS_COMMANDER:
        print_log("I am the Commander.")
        # Traitorous commander sends conflicting orders
        if IS_TRAITOR:
            print_log("As a traitorous commander, I will send conflicting orders.")
            order1, order2 = "attack", "retreat"
            for i, peer in enumerate(PEERS):
                order_to_send = order1 if i % 2 == 0 else order2
                try:
                    print_log(f"Sending '{order_to_send}' to {peer}")
                    requests.post(f"{peer}/order", json={'sender_id': NODE_ID, 'order': order_to_send}, timeout=2)
                except requests.exceptions.RequestException as e:
                    print_log(f"Could not send order to {peer}. Error: {e}")
        # Loyal commander sends the same order to everyone
        else:
            print_log(f"Sending order to all lieutenants: '{INITIAL_ORDER}'")
            for peer in PEERS:
                try:
                    requests.post(f"{peer}/order", json={'sender_id': NODE_ID, 'order': INITIAL_ORDER}, timeout=2)
                except requests.exceptions.RequestException as e:
                    print_log(f"Could not send order to {peer}. Error: {e}")
    else:
        print_log(f"I am a Lieutenant, awaiting orders.")
        # Lieutenants wait to receive all messages. The number of expected peer
        # messages is the number of other lieutenants.
        expected_peer_messages = num_lieutenants - 1
        
        start_time = time.time()
        # Wait for messages for up to 10 seconds
        while time.time() - start_time < 10:
            if order_from_commander is not None and len(orders_from_peers) == expected_peer_messages:
                break
            time.sleep(0.5)

        # After waiting, make a decision
        final_orders = {'commander': order_from_commander}
        final_orders.update(orders_from_peers)
        
        majority = decide_majority(final_orders)
        
        if majority != "no majority":
            decision_str = "ATTACK" if majority == "attack" else "RETREAT"
            print_log(f"Lieutenant {NODE_ID} received orders: {final_orders}. Majority is '{majority}'. DECISION: {decision_str}")
        else:
            print_log(f"Lieutenant {NODE_ID} received orders: {final_orders}. No majority found! CONSENSUS FAILED.")


if __name__ == '__main__':
    # Start the simulation logic in a separate thread so the Flask app can run
    from threading import Thread
    simulation_thread = Thread(target=run_simulation)
    simulation_thread.start()
    
    # Run the Flask web server
    app.run(host='0.0.0.0', port=5000)
