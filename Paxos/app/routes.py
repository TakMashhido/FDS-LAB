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
    """
    Client-facing endpoint to propose a value.
    If this node is the leader, it starts the Paxos algorithm.
    If not, it forwards the request to the designated leader.
    """
    value_to_propose = request.json.get('value')
    if not value_to_propose:
        return jsonify({"error": "Value is required"}), 400

    if not IS_LEADER:
        print(f"[{NODE_ID}][Forwarder] I am not the leader. Forwarding request to {LEADER_ADDRESS}")
        try:
            session.post(f'http://{LEADER_ADDRESS}/propose', json={'value': value_to_propose}, timeout=5)
        except requests.exceptions.RequestException as e:
            return jsonify({"error": "Could not forward request to leader.", "details": str(e)}), 503
        return jsonify({"message": f"Request forwarded to leader node {LEADER_ADDRESS}"})

    if paxos_node.is_proposing:
        return jsonify({"error": "A proposal is already in progress on this node. Please wait."}), 429

    thread = threading.Thread(target=run_paxos_proposer, args=(value_to_propose,))
    thread.start()
    return jsonify({"message": f"Proposal for value '{value_to_propose}' initiated by leader {NODE_ID}"}), 202


def run_paxos_proposer(value_to_propose):
    """This function implements the Proposer role in Paxos. ONLY THE LEADER RUNS THIS."""
    paxos_node.is_proposing = True
    try:
        time.sleep(1)
        proposal_number = paxos_node.get_next_proposal_number()
        print(f"[{NODE_ID}][Leader] Starting Paxos for value '{value_to_propose}' with proposal number {proposal_number}")

        # === Phase 1: Prepare ===
        promises = []
        highest_accepted_proposal = -1
        value_from_promises = None
        quorum_size = len(PEERS) // 2 + 1

        for peer in PEERS:
            if peer == SELF_ADDRESS:
                promise = paxos_node.handle_prepare(proposal_number)
                if promise["promised"]: promises.append(promise)
                continue
            try:
                response = session.post(f'http://{peer}/prepare', json={'proposal_number': proposal_number}, timeout=5)
                if response.status_code == 200 and response.json().get("promised"):
                    promises.append(response.json())
            except requests.exceptions.RequestException as e:
                print(f"[{NODE_ID}][Leader] ERROR: Could not connect to {peer} for prepare: {e}")

        if len(promises) < quorum_size:
            print(f"[{NODE_ID}][Leader] WARN: Quorum not reached for prepare phase ({len(promises)}/{quorum_size}). Aborting.")
            return

        for p in promises:
            if p.get("accepted_proposal_number", -1) > highest_accepted_proposal:
                highest_accepted_proposal = p["accepted_proposal_number"]
                if p.get("accepted_value") is not None: value_from_promises = p["accepted_value"]

        if value_from_promises:
            value_to_propose = value_from_promises
            print(f"[{NODE_ID}][Leader] INFO: A previously accepted value '{value_to_propose}' was found. Proposing it instead.")

        # === Phase 2: Propose ===
        acceptances = 0
        for peer in PEERS:
            if peer == SELF_ADDRESS:
                if paxos_node.handle_propose(proposal_number, value_to_propose)["accepted"]:
                    acceptances += 1
                continue
            try:
                # *** THIS IS THE FIX: The URL is now /accept ***
                response = session.post(
                    f'http://{peer}/accept',
                    json={'proposal_number': proposal_number, 'value': value_to_propose},
                    timeout=5
                )
                if response.status_code == 200 and response.json().get("accepted"):
                    acceptances += 1
            except requests.exceptions.RequestException as e:
                print(f"[{NODE_ID}][Leader] ERROR: Could not connect to {peer} for accept: {e}")

        if acceptances >= quorum_size:
            print(f"[{NODE_ID}][Leader] SUCCESS: Consensus reached for value '{value_to_propose}'!")
            for peer in PEERS:
                try:
                    session.post(f'http://{peer}/learn', json={'value': value_to_propose}, timeout=2)
                except requests.exceptions.RequestException: pass
        else:
            print(f"[{NODE_ID}][Leader] FAILURE: Quorum not reached for propose phase ({acceptances}/{quorum_size}).")
    finally:
        paxos_node.is_proposing = False


@bp.route('/prepare', methods=['POST'])
def prepare():
    proposal_number = request.json.get('proposal_number')
    result = paxos_node.handle_prepare(proposal_number)
    print(f"[{NODE_ID}][Acceptor] Received prepare for proposal {proposal_number}. Promising: {result['promised']}")
    return jsonify(result)


@bp.route('/accept', methods=['POST'])
def accept_proposal():
    """Internal endpoint for nodes to accept a proposal from the leader."""
    proposal_number = request.json.get('proposal_number')
    value = request.json.get('value')
    result = paxos_node.handle_propose(proposal_number, value)
    if result['accepted']:
        print(f"[{NODE_ID}][Acceptor] Accepted proposal {proposal_number} with value '{value}'")
    else:
        print(f"[{NODE_ID}][Acceptor] Rejected proposal {proposal_number} with value '{value}'")
    return jsonify(result)

@bp.route('/learn', methods=['POST'])
def learn():
    value = request.json.get('value')
    paxos_node.learn_value(value)
    print(f"[{NODE_ID}][Learner] Learned value: '{value}'")
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