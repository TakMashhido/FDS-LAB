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
        self.is_proposing = False

    def get_next_proposal_number(self):
        with self.lock:
            self.proposal_number += 1
            return self.proposal_number

    def handle_prepare(self, proposal_number):
        """The core logic for an Acceptor handling a 'prepare' request."""
        with self.lock:
            print(f"[{self.node_id}][Acceptor] Received PREPARE for proposal_number={proposal_number}. My current promised_proposal_number is {self.promised_proposal_number}.")
            
            if proposal_number > self.promised_proposal_number:
                print(f"[{self.node_id}][Acceptor] --> Incoming proposal {proposal_number} is HIGHER than my last promise {self.promised_proposal_number}. I will promise and update my promised_proposal_number.")
                self.promised_proposal_number = proposal_number
                return {
                    "promised": True,
                    "accepted_proposal_number": self.accepted_proposal_number,
                    "accepted_value": self.accepted_value,
                }
            else:
                print(f"[{self.node_id}][Acceptor] --> Incoming proposal {proposal_number} is NOT HIGHER than my last promise {self.promised_proposal_number}. I will REJECT.")
                return {"promised": False}

    def handle_propose(self, proposal_number, value):
        """The core logic for an Acceptor handling an 'accept' request."""
        with self.lock:
            print(f"[{self.node_id}][Acceptor] Received ACCEPT for proposal_number={proposal_number} and value='{value}'. My current promised_proposal_number is {self.promised_proposal_number}.")

            if proposal_number >= self.promised_proposal_number:
                print(f"[{self.node_id}][Acceptor] --> Incoming proposal {proposal_number} is GTE my last promise {self.promised_proposal_number}. I will ACCEPT this value and update my state.")
                self.promised_proposal_number = proposal_number
                self.accepted_proposal_number = proposal_number
                self.accepted_value = value
                return {"accepted": True}
            else:
                print(f"[{self.node_id}][Acceptor] --> Incoming proposal {proposal_number} is LOWER than my last promise {self.promised_proposal_number}. I will REJECT this value.")
                return {"accepted": False}

    def learn_value(self, value):
        print(f"[{self.node_id}][Learner] Received LEARN for value='{value}'. Updating learned_value.")
        self.learned_value = value