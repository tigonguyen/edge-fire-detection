#!/usr/bin/env bash
set -euo pipefail

MASTER_IP="${1:?Usage: $0 <MASTER_IP> <TOKEN>}"
TOKEN="${2:?Usage: $0 <MASTER_IP> <TOKEN>}"

echo "Joining k3s cluster at ${MASTER_IP} as edge node..."
curl -sfL https://get.k3s.io | K3S_URL="https://${MASTER_IP}:6443" \
  K3S_TOKEN="${TOKEN}" \
  INSTALL_K3S_EXEC="agent --node-label node-role=edge" sh -

echo "Edge node joined. Verify with: kubectl get nodes"
