import requests
import time
import os

# The primary node (node0) is the entry point for client requests
PRIMARY_NODE_URL = "http://node0:5000"
CLIENT_ID = int(os.getpid()) # Use process ID as a simple client ID

def print_log(message):
    """Prints a log message for the client."""
    print(f"[Client {CLIENT_ID}]: {message}", flush=True)

def send_request():
    """Sends a sample request to the PBFT network."""
    # Give the network a moment to initialize
    time.sleep(10)

    request_payload = {
        "client_id": CLIENT_ID,
        "timestamp": int(time.time()),
        "operation": {
            "type": "set",
            "key": "test",
            "value": "123"
        }
    }

    print_log(f"Sending request to set key 'test' to '123'.")

    try:
        # Client sends request to the primary node
        response = requests.post(f"{PRIMARY_NODE_URL}/request", json=request_payload, timeout=5)
        if response.status_code == 202:
            print_log("Request accepted by primary. Waiting for confirmation...")
        else:
            print_log(f"Request failed with status: {response.status_code}")
            print_log(f"Response: {response.text}")

    except requests.exceptions.RequestException as e:
        print_log(f"Error sending request: {e}")

if __name__ == "__main__":
    send_request()
    # In a real client, there would be logic to listen for reply messages
    # and confirm the operation based on f+1 identical replies.
    # For this simulation, we'll just check the node logs for confirmation.
    print_log("Client script finished.")