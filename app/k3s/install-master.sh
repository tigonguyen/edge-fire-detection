#!/usr/bin/env bash
set -euo pipefail

# Install k3s server (master) on cloud node.
# After install, token is at /var/lib/rancher/k3s/server/node-token

echo "Installing k3s server (master)..."
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server \
  --write-kubeconfig-mode 644 \
  --tls-san $(hostname -I | awk '{print $1}') \
  --node-label node-role=cloud" sh -

echo ""
echo "k3s master installed. Kubeconfig: /etc/rancher/k3s/k3s.yaml"
echo "Node token: $(cat /var/lib/rancher/k3s/server/node-token)"
echo ""
echo "On edge nodes, run:"
echo "  bash join-edge.sh <THIS_IP> <TOKEN>"
