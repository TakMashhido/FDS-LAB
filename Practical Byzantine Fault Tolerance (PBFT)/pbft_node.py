import os
import sys
import time
import requests
import json
from flask import Flask, request, jsonify
from collections import defaultdict
from threading import Thread, Lock

# --- Configuration ---
app = Flask(__name__)

# Node's identity from environment variables
NODE_ID = int(os.environ.get('NODE_ID', 0))
IS_PRIMARY = os.environ.get('IS_PRIMARY', 'false').lower() == 'true'
IS_TRAITOR = os.environ.get('IS_TRAITOR', 'false').lower() == 'true'

# Get peer nodes from command-line arguments
PEERS = sys.argv[1:]
TOTAL_NODES = len(PEERS) + 1
FAULT_TOLERANCE = (TOTAL_NODES - 1) // 3

# State variables
state = {} # Simple key-value store
sequence_number = 0
request_log = [] # To store client requests
prepare_log = defaultdict(list) # To log prepare messages
commit_log = defaultdict(list) # To log commit messages
committed_requests = set() # To track committed requests
lock = Lock()

# --- Helper Functions ---
def print_log(message):
    """Prints a formatted log message."""
    print(f"[Node {NODE_ID}{' (P)' if IS_PRIMARY else ''}{' (T)' if IS_TRAITOR else ''}]: {message}", flush=True)

def broadcast(endpoint, message):
    """Broadcasts a message to all peers."""
    if IS_TRAITOR:
        print_log("As a traitor, I will not broadcast.")
        return
        
    for peer in PEERS:
        try:
            requests.post(f"{peer}{endpoint}", json=message, timeout=2)
        except requests.exceptions.RequestException as e:
            print_log(f"Could not send message to {peer}. Error: {e}")

# --- PBFT Logic ---
def handle_request(client_request):
    """Primary node handles a client request."""
    global sequence_number
    with lock:
        sequence_number += 1
        request_log.append(client_request)

        pre_prepare_message = {
            "type": "pre-prepare",
            "view": 1, # Simplified: view is always 1
            "seq_num": sequence_number,
            "digest": hash(json.dumps(client_request, sort_keys=True)),
            "request": client_request,
            "sender_id": NODE_ID
        }
        print_log(f"Broadcasting PRE-PREPARE for seq_num {sequence_number}")
        broadcast("/pre-prepare", pre_prepare_message)

def handle_pre_prepare(message):
    """Backup nodes handle a pre-prepare message."""
    with lock:
        seq_num = message['seq_num']
        print_log(f"Received PRE-PREPARE for seq_num {seq_num}")

        # Basic validation (in a real system, would check view, signature, etc.)
        request_log.append(message['request'])
        
        prepare_message = {
            "type": "prepare",
            "view": 1,
            "seq_num": seq_num,
            "digest": message['digest'],
            "sender_id": NODE_ID
        }
        print_log(f"Broadcasting PREPARE for seq_num {seq_num}")
        broadcast("/prepare", prepare_message)

def handle_prepare(message):
    """All nodes handle a prepare message."""
    with lock:
        seq_num = message['seq_num']
        prepare_log[seq_num].append(message['sender_id'])
        
        # Check if we have enough prepare messages to be "prepared"
        if len(prepare_log[seq_num]) >= 2 * FAULT_TOLERANCE and seq_num not in committed_requests:
            print_log(f"Reached PREPARED state for seq_num {seq_num}")
            
            commit_message = {
                "type": "commit",
                "view": 1,
                "seq_num": seq_num,
                "digest": message['digest'],
                "sender_id": NODE_ID
            }
            print_log(f"Broadcasting COMMIT for seq_num {seq_num}")
            broadcast("/commit", commit_message)

def handle_commit(message):
    """All nodes handle a commit message."""
    with lock:
        seq_num = message['seq_num']
        commit_log[seq_num].append(message['sender_id'])

        # Check if we have enough commit messages to be "committed"
        if len(commit_log[seq_num]) >= 2 * FAULT_TOLERANCE + 1 and seq_num not in committed_requests:
            committed_requests.add(seq_num)
            print_log(f"Reached COMMITTED state for seq_num {seq_num}")
            execute_request(seq_num)

def execute_request(seq_num):
    """Executes the request and updates the state."""
    # Find the request corresponding to the sequence number
    # This is simplified; a real system would use a more robust mapping
    if seq_num - 1 < len(request_log):
        client_request = request_log[seq_num - 1]
        op = client_request['operation']
        if op['type'] == 'set':
            state[op['key']] = op['value']
            print_log(f"State updated: {state}")
            
            # In a real implementation, this node would now send a REPLY to the client.

# --- Flask API Endpoints ---
@app.route('/request', methods=['POST'])
def client_request_endpoint():
    """Endpoint for the primary to receive client requests."""
    if not IS_PRIMARY:
        return jsonify({"error": "I am not the primary node"}), 400
    if IS_TRAITOR:
        print_log("As a traitor, ignoring client request.")
        return jsonify({"status": "ignored"}), 202

    client_request = request.json
    print_log(f"Received request from Client {client_request.get('client_id')}")
    # Handle the request in a separate thread to not block the client
    Thread(target=handle_request, args=(client_request,)).start()
    return jsonify({"status": "accepted"}), 202

@app.route('/pre-prepare', methods=['POST'])
def pre_prepare_endpoint():
    if IS_TRAITOR: return jsonify({}), 200 # Traitors do nothing
    message = request.json
    Thread(target=handle_pre_prepare, args=(message,)).start()
    return jsonify({"status": "ack"})

@app.route('/prepare', methods=['POST'])
def prepare_endpoint():
    if IS_TRAITOR: return jsonify({}), 200
    message = request.json
    Thread(target=handle_prepare, args=(message,)).start()
    return jsonify({"status": "ack"})

@app.route('/commit', methods=['POST'])
def commit_endpoint():
    if IS_TRAITOR: return jsonify({}), 200
    message = request.json
    Thread(target=handle_commit, args=(message,)).start()
    return jsonify({"status": "ack"})

if __name__ == '__main__':
    print_log(f"Starting Node. N={TOTAL_NODES}, k={FAULT_TOLERANCE}")
    app.run(host='0.0.0.0', port=5000)

