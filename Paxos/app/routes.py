import requests
import threading
from flask import Blueprint, request, jsonify
from .paxos import PaxosNode
import os
import time

bp = Blueprint('routes', __name__)

# --- Configuration ---
peers_str = os.getenv('PEERS', 'paxos-node-1:5000,paxos-node-2:5000,paxos-node-3:5000')
PEERS = peers_str.split(',')
NODE_ID = os.getenv('NODE_ID', 'paxos-node-1')
SELF_ADDRESS = f"{NODE_ID}:5000"

# --- LEADER ELECTION (SIMULATED) ---
LEADER_ADDRESS = 'paxos-node-1:5000'
IS_LEADER = (SELF_ADDRESS == LEADER_ADDRESS)

# --- Global Objects ---
paxos_node = PaxosNode(NODE_ID, PEERS)
session = requests.Session()


@bp.route('/propose', methods=['POST'])
def propose_value():
    value_to_propose = request.json.get('value')
    if not value_to_propose: return jsonify({"error": "Value is required"}), 400

    if not IS_LEADER:
        print(f"[{NODE_ID}][Forwarder] I am not the leader. Forwarding request to {LEADER_ADDRESS}")
        try:
            session.post(f'http://{LEADER_ADDRESS}/propose', json={'value': value_to_propose}, timeout=5)
        except requests.exceptions.RequestException as e:
            return jsonify({"error": "Could not forward request to leader.", "details": str(e)}), 503
        return jsonify({"message": f"Request forwarded to leader node {LEADER_ADDRESS}"})

    if paxos_node.is_proposing: return jsonify({"error": "A proposal is already in progress on this node. Please wait."}), 429

    thread = threading.Thread(target=run_paxos_proposer, args=(value_to_propose,))
    thread.start()
    return jsonify({"message": f"Proposal for value '{value_to_propose}' initiated by leader {NODE_ID}"}), 202


def run_paxos_proposer(value_to_propose):
    paxos_node.is_proposing = True
    try:
        quorum_size = len(PEERS) // 2 + 1
        print(f"-------------------- NEW PROPOSAL --------------------")
        print(f"[{NODE_ID}][Leader] Quorum size is {quorum_size}.")
        
        proposal_number = paxos_node.get_next_proposal_number()
        print(f"[{NODE_ID}][Leader] Starting Paxos for value '{value_to_propose}' with new proposal_number={proposal_number}")
        print(f"[{NODE_ID}][Leader] --- PHASE 1: PREPARE ---")

        promises = []
        for peer in PEERS:
            try:
                if peer == SELF_ADDRESS:
                    promise = paxos_node.handle_prepare(proposal_number)
                else:
                    response = session.post(f'http://{peer}/prepare', json={'proposal_number': proposal_number}, timeout=5)
                    promise = response.json() if response.status_code == 200 else {"promised": False}
                
                if promise.get("promised"):
                    promises.append(promise)
            except requests.exceptions.RequestException as e:
                print(f"[{NODE_ID}][Leader] ERROR: Could not connect to {peer} for prepare: {e}")

        print(f"[{NODE_ID}][Leader] PREPARE phase complete. Received {len(promises)} promises.")
        if len(promises) < quorum_size:
            print(f"[{NODE_ID}][Leader] FAILED TO GET QUORUM OF PROMISES. Aborting.")
            print(f"------------------------------------------------------")
            return

        print(f"[{NODE_ID}][Leader] QUORUM OF PROMISES ACHIEVED. Moving to phase 2.")
        
        highest_accepted_proposal = -1
        value_from_promises = None
        for p in promises:
            if p.get("accepted_proposal_number", -1) > highest_accepted_proposal:
                highest_accepted_proposal = p["accepted_proposal_number"]
                if p.get("accepted_value") is not None:
                    value_from_promises = p["accepted_value"]

        if value_from_promises:
            value_to_propose = value_from_promises
            print(f"[{NODE_ID}][Leader] A promise contained a previously accepted value ('{value_to_propose}' from proposal {highest_accepted_proposal}). This value MUST be proposed.")
        else:
            print(f"[{NODE_ID}][Leader] No previously accepted values found in promises. Proposing my own value: '{value_to_propose}'.")

        print(f"[{NODE_ID}][Leader] --- PHASE 2: ACCEPT ---")
        acceptances = 0
        for peer in PEERS:
            try:
                if peer == SELF_ADDRESS:
                    acceptance = paxos_node.handle_propose(proposal_number, value_to_propose)
                else:
                    response = session.post(f'http://{peer}/accept', json={'proposal_number': proposal_number, 'value': value_to_propose}, timeout=5)
                    acceptance = response.json() if response.status_code == 200 else {"accepted": False}

                if acceptance.get("accepted"):
                    acceptances += 1
            except requests.exceptions.RequestException as e:
                print(f"[{NODE_ID}][Leader] ERROR: Could not connect to {peer} for accept: {e}")

        print(f"[{NODE_ID}][Leader] ACCEPT phase complete. Received {acceptances} acceptances.")
        if acceptances >= quorum_size:
            print(f"[{NODE_ID}][Leader] QUORUM OF ACCEPTANCES ACHIEVED. CONSENSUS REACHED!")
            print(f"[{NODE_ID}][Leader] --- PHASE 3: LEARN ---")
            for peer in PEERS:
                try:
                    # In a real system, you might retry this. For us, it's fire-and-forget.
                    session.post(f'http://{peer}/learn', json={'value': value_to_propose}, timeout=2)
                except requests.exceptions.RequestException: pass
        else:
            print(f"[{NODE_ID}][Leader] FAILED TO GET QUORUM OF ACCEPTANCES. Consensus failed for this round.")
        
        print(f"------------------------------------------------------")

    finally:
        paxos_node.is_proposing = False


# (The rest of the file: /prepare, /accept, /learn, /status endpoints remain the same)
@bp.route('/prepare', methods=['POST'])
def prepare():
    return jsonify(paxos_node.handle_prepare(request.json.get('proposal_number')))

@bp.route('/accept', methods=['POST'])
def accept_proposal():
    return jsonify(paxos_node.handle_propose(request.json.get('proposal_number'), request.json.get('value')))

@bp.route('/learn', methods=['POST'])
def learn():
    paxos_node.learn_value(request.json.get('value'))
    return jsonify({"message": "Value learned successfully"})

@bp.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        "node_id": paxos_node.node_id,
        "proposal_number": paxos_node.proposal_number,
        "promised_proposal_number": paxos_node.promised_proposal_number,
        "accepted_proposal_number": paxos_node.accepted_proposal_number,
        "accepted_value": paxos_node.accepted_value,
        "learned_value": paxos_node.learned_value
    })