# Building a Hybrid Cloud-Edge Kubernetes Cluster (GCP + VMware over Tailscale)

This guide details how to build a 2-node Kubernetes cluster bridging a Google Cloud (GCP) Master node and a local VMware Worker node securely over the public internet. 

Because the nodes exist on completely different networks behind NATs and Firewalls, they communicate via a **Tailscale VPN** mesh. This guide is specifically tailored for **Debian 12/13** and resolves common networking, DNS, and Containerd sandbox issues encountered when running a distributed edge setup.

---

## Step 1: Prepare the OS and Networking (Run on BOTH Nodes)
Kubernetes requires specific kernel modules, network bridging, and swap to be disabled.

```bash
# 1. Disable Swap (Required for Kubelet)
sudo swapoff -a
sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab

# 2. Load Kernel Modules for Networking
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF
sudo modprobe overlay
sudo modprobe br_netfilter

# 3. Apply sysctl parameters
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sudo sysctl --system
```

## Step 2: Install and Configure `containerd` (Run on BOTH Nodes)

```bash
# 1. Install prerequisites and add Docker repo
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg apparmor

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Note: Using "bookworm" here specifically ensures compatibility even if running testing/Trixie
echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 2. Install containerd
sudo apt-get update
sudo apt-get install -y containerd.io

# 3. Force Containerd to use SystemdCgroup (Crucial for node stability)
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo systemctl restart containerd
sudo systemctl enable containerd
```

## Step 3: Install Kubernetes Components (Run on BOTH Nodes)
*Note: We use the `[trusted=yes]` flag here to bypass Debian 13/Trixie's strict OpenPGP v3 signature rejection policy on Google's repositories.*

```bash
sudo apt-get install -y apt-transport-https
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.35/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [trusted=yes] https://pkgs.k8s.io/core:/stable:/v1.35/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list

sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl
```

## Step 4: Establish the Tailscale VPN (Run on BOTH Nodes)
To route Pod traffic across the public internet between the GCP VM and the local VMware instance, both nodes must join a VPN. Crucially, we must disable Tailscale's Magic DNS, otherwise Kubelet will be unable to resolve and pull Google's container registries.

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Bring it up, but strictly disable DNS overriding
sudo tailscale up --accept-dns=false
```

## Step 5: Fix Debian Sandbox & DNS Issues (Run on WORKER Node ONLY)
Debian 12+ does not always enable `systemd-resolved` by default, which causes Kubelet sandbox creation to immediately crash. Local VMware NATs can also break DNS resolution when downloading K8s images.

```bash
# 1. Fix missing resolv.conf for the Kubelet Sandbox
sudo mkdir -p /run/systemd/resolve
sudo ln -sf /etc/resolv.conf /run/systemd/resolve/resolv.conf

# 2. Force Kubelet to use Google's Public DNS (Fixes "no such host" for registry.k8s.io)
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf > /dev/null

# 3. Inform Kubelet that it MUST broadcast its Tailscale IP to the Master, not its local WiFi IP
WORKER_IP=$(tailscale ip -4)
echo "KUBELET_EXTRA_ARGS=\"--node-ip=$WORKER_IP\"" | sudo tee /etc/default/kubelet > /dev/null
sudo systemctl daemon-reload
sudo systemctl restart kubelet
```

## Step 6: Initialize the Control Plane (Run on MASTER Node ONLY)
Initialize the Master, forcing it to listen **exclusively** on the Tailscale VPN network (`100.x.x.x`).

```bash
# 1. Get the Master's VPN IP
MASTER_IP=$(tailscale ip -4)

# 2. Initialize the cluster (Setting pod-network to 10.244.0.0/16 is required for Flannel)
sudo kubeadm init \
  --apiserver-advertise-address=$MASTER_IP \
  --pod-network-cidr=10.244.0.0/16

# 3. Setup local kubectl admin access
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# 4. Install the Flannel CNI Network Plugin
kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml
```

## Step 7: Join the Edge Node (Run on WORKER Node ONLY)
Copy the `kubeadm join` command generated at the end of Step 6 on the Master node, and paste it securely into your Worker node.

```bash
# Example syntax:
sudo kubeadm join <MASTER_TAILSCALE_IP>:6443 --token <token> --discovery-token-ca-cert-hash sha256:<hash>
```

Wait ~30 seconds for the node to safely pull the `pause` and `flannel` images from the internet, and checking `kubectl get nodes` on the Master will proudly display both machines running happily in the `Ready` state!
