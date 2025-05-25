#!/usr/bin/env python3
import etcd3, time
from colorama import Fore, Style, init

# initialize colorama
init(autoreset=True)

# your three etcd endpoints
ENDPOINTS = [
    ('127.0.0.1', 2379),
    ('127.0.0.1', 2380),
    ('127.0.0.1', 2381),
]

def get_client():
    """Try each endpoint in order, return the first working client."""
    for host, port in ENDPOINTS:
        try:
            cli = etcd3.client(host=host, port=port, timeout=2)
            # quick health check
            cli.status()
            print(f"{Fore.GREEN}→ Connected to {host}:{port}{Style.RESET_ALL}")
            return cli
        except Exception as e:
            print(f"{Fore.RED}✗ {host}:{port} → {e.__class__.__name__}{Style.RESET_ALL}")
    raise RuntimeError("All etcd endpoints failed")

def write_key(client, key, value):
    print(f"{Fore.GREEN}[WRITE]{Style.RESET_ALL} {key} → {Fore.CYAN}{value}{Style.RESET_ALL}")
    client.put(key, value)

def read_key(client, key):
    val, _ = client.get(key)
    print(f"{Fore.YELLOW}[READ]{Style.RESET_ALL} {key} = {Fore.MAGENTA}{(val or b'').decode()}{Style.RESET_ALL}")

if __name__ == "__main__":
    print(f"\n{Fore.BLUE}>>> Establishing connection…{Style.RESET_ALL}")
    client = get_client()

    print(f"\n{Fore.BLUE}>>> Writing 5 keys…{Style.RESET_ALL}")
    for i in range(1, 6):
        write_key(client, f"foo{i}", f"bar{i}")
        time.sleep(0.5)

    print(f"\n{Fore.BLUE}>>> Reading them back…{Style.RESET_ALL}")
    for i in range(1, 6):
        read_key(client, f"foo{i}")
        time.sleep(0.5)

    print(f"\n{Fore.BLUE}>>> Demo complete.{Style.RESET_ALL}\n")
