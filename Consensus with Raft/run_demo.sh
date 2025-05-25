#!/usr/bin/env bash
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}1) Spinning up 3-node etcd cluster…${NC}"
docker-compose up -d

echo -e "${BLUE}2) Waiting for leader election (10s)…${NC}"
sleep 10

echo -e "${BLUE}3) Checking cluster status:${NC}"
docker exec etcd1 etcdctl --endpoints=http://etcd1:2379 endpoint status --write-out=table
docker exec etcd2 etcdctl --endpoints=http://etcd2:2379 endpoint status --write-out=table
docker exec etcd3 etcdctl --endpoints=http://etcd3:2379 endpoint status --write-out=table

echo -e "${BLUE}\n4) Running Python client: writes & reads${NC}"
uv run demo_client.py

echo -e "${BLUE}\n5) Which etcd node should we kill?${NC}"
echo -e "   Available containers: etcd1, etcd2, etcd3"
read -p "   Enter container name to kill: " TARGET

# insist until the user actually types something
while [ -z "$TARGET" ]; do
  echo -e "${RED}   You must enter a container name!${NC}"
  read -p "   Enter container name to kill: " TARGET
done

echo -e "${BLUE}   Killing container ${TARGET}…${NC}"
docker kill "$TARGET"
echo -e "${GREEN}   ${TARGET} has been killed.${NC}"

echo -e "${BLUE}\n6) Waiting for leader re-election after killing ${TARGET} (10s)…${NC}"

sleep 10

echo -e "${BLUE}\n6) Rerunning Python client to prove failover…${NC}"
uv run demo_client.py

echo -e "${BLUE}\n7) Tailing etcd logs (press Ctrl+Z to stop)${NC}"
echo -e "${GREEN}— etcd1 —${NC}"; docker logs -f etcd1 &
echo -e "${GREEN}— etcd2 —${NC}"; docker logs -f etcd2 &
echo -e "${GREEN}— etcd3 —${NC}"; docker logs -f etcd3 &

wait