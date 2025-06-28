import threading

class PaxosNode:
    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers
        self.proposal_number = 0
        self.promised_proposal_number = -1
        self.accepted_proposal_number = -1
        self.accepted_value = None
        self.learned_value = None
        self.lock = threading.Lock()
        self.is_proposing = False  # Add this line

    def get_next_proposal_number(self):
        with self.lock:
            self.proposal_number += 1
            return self.proposal_number

    def handle_prepare(self, proposal_number):
        with self.lock:
            if proposal_number > self.promised_proposal_number:
                self.promised_proposal_number = proposal_number
                return {
                    "promised": True,
                    "accepted_proposal_number": self.accepted_proposal_number,
                    "accepted_value": self.accepted_value,
                }
            else:
                return {"promised": False}

    def handle_propose(self, proposal_number, value):
        with self.lock:
            if proposal_number >= self.promised_proposal_number:
                self.promised_proposal_number = proposal_number
                self.accepted_proposal_number = proposal_number
                self.accepted_value = value
                return {"accepted": True}
            else:
                return {"accepted": False}

    def learn_value(self, value):
        self.learned_value = value