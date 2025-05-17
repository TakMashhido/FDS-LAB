import os, threading, time, requests
from flask import Flask, request

app = Flask(__name__)

# Environment variables passed by Docker Compose
NODE_ID       = int(os.environ['NODE_ID'])
ALL_NODES     = [int(x) for x in os.environ['ALL_NODES'].split(',')]
BASE_PORT     = 5000

leader_id     = None
election_lock = threading.Lock()

def log(msg):
    print(f"[Node {NODE_ID}] {msg}", flush=True)

@app.route('/election', methods=['POST'])
def on_election():
    sender = int(request.json['sender'])
    log(f"Received ELECTION from Node {sender}")
    # Reply OK if this node has higher ID
    if NODE_ID > sender:
        requests.post(f'http://node{sender}:{BASE_PORT}/ok', json={'sender': NODE_ID})
        threading.Thread(target=start_election, daemon=True).start()
    return ('', 200)

@app.route('/ok', methods=['POST'])
def on_ok():
    sender = int(request.json['sender'])
    log(f"Received OK from Node {sender}")
    # someone higher is alive—wait for their coordinator announcement
    return ('', 200)

@app.route('/coordinator', methods=['POST'])
def on_coordinator():
    global leader_id
    sender = int(request.json['sender'])
    leader_id = sender
    log(f"Node {sender} is the new Leader")
    return ('', 200)

def start_election():
    global leader_id
    with election_lock:
        leader_id = None
        log("Starting election")
        higher = [n for n in ALL_NODES if n > NODE_ID]
        for peer in higher:
            try:
                requests.post(f'http://node{peer}:{BASE_PORT}/election', json={'sender': NODE_ID}, timeout=2)
            except:
                log(f"No response from Node {peer}")
        # wait briefly for OKs
        time.sleep(3)
        if leader_id is None:
            # I am the highest alive
            leader_id = NODE_ID
            log("I won election; announcing as Leader")
            for peer in ALL_NODES:
                if peer != NODE_ID:
                    try:
                        requests.post(f'http://node{peer}:{BASE_PORT}/coordinator', json={'sender': NODE_ID}, timeout=2)
                    except:
                        pass

def heartbeat_monitor():
    global leader_id
    while True:
        time.sleep(5)
        if leader_id is None or leader_id == NODE_ID:
            continue
        # ping leader
        try:
            requests.get(f'http://node{leader_id}:{BASE_PORT}/heartbeat', timeout=2)
        except:
            log(f"Leader {leader_id} down. Triggering election.")
            start_election()

@app.route('/heartbeat', methods=['GET'])
def heartbeat():
    return ('', 200)

if __name__ == '__main__':
    # start heartbeat thread
    threading.Thread(target=heartbeat_monitor, daemon=True).start()
    # give everyone time to come up before first election
    time.sleep(2)
    start_election()
    app.run(host='0.0.0.0', port=BASE_PORT)
