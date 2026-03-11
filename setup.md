# Building a 2-Node Kubernetes Cluster with kubeadm and containerd

To build a 2-node Kubernetes cluster that resembles the standard Rancher Desktop environment (which typically relies on `containerd` as the Container Runtime and `Flannel` for networking), you can follow this step-by-step `kubeadm` guide.

You will need to run the following "Pre-requisites" and "Installation" steps on **both** your Master node and your Worker node.

### Step 1: Prepare the Nodes (Run on BOTH Nodes)
Kubernetes requires specific kernel modules and network bridging to be enabled.

```bash
# 1. Disable Swap (Required for kubelet to work properly)
sudo swapoff -a
sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab

# 2. Enable IPv4 packet forwarding and load necessary kernel modules
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

sudo modprobe overlay
sudo modprobe br_netfilter

# 3. Apply sysctl params required by setup
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF

sudo sysctl --system
```

### Step 2: Install the `containerd` CRI (Run on BOTH Nodes)
Rancher Desktop uses `containerd` by default. We will install it and configure it to use the Systemd cgroup driver.

```bash
# 1. Install prerequisites and Docker's apt repository (which hosts containerd)
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 2. Install containerd
sudo apt-get update
sudo apt-get install -y containerd.io

# 3. Configure containerd to use the systemd cgroup driver (Crucial for stability)
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml

# 4. Restart and enable containerd
sudo systemctl restart containerd
sudo systemctl enable containerd
```

### Step 3: Install `kubeadm`, `kubelet`, and `kubectl` (Run on BOTH Nodes)
We will install the core Kubernetes components from the official repositories.

```bash
# 1. Add Kubernetes apt repository
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gpg

# Download the public signing key for the Kubernetes package repositories (using v1.29 as example)
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.29/deb/Release.key | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.29/deb/ /' | sudo tee /etc/apt/sources.list.d/kubernetes.list

# 2. Install the tools and lock their versions
sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl
```

---

### Step 4: Initialize the Master Node (Run on MASTER Node ONLY)
Now that the prerequisites are installed everywhere, we bootstrap the control plane. We pass the `10.244.0.0/16` Pod Network CIDR because the Flannel CNI requires it by default.

```bash
# 1. Initialize the cluster
sudo kubeadm init --pod-network-cidr=10.244.0.0/16

# 2. Once this finishes, it will output a "kubeadm join" command at the very bottom. 
# COPY THAT COMMAND AND SAVE IT. It looks something like:
# sudo kubeadm join <MASTER_IP>:6443 --token <token> --discovery-token-ca-cert-hash sha256:<hash>

# 3. Setup your local Admin kubeconfig so you can use kubectl
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# 4. Install the Flannel CNI (This gives pods IP addresses and cross-node communication, identical to Rancher defaults)
kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml
```

---

### Step 5: Join the Worker Node (Run on WORKER Node ONLY)
Take the join command that was generated at the end of Step 4, and paste it securely into your second node.

```bash
# Replace with your actual join command from the Master node output
sudo kubeadm join <MASTER_IP>:6443 --token <token> \
        --discovery-token-ca-cert-hash sha256:<hash>
```

### Verification (Run on MASTER Node)
Wait a few minutes for the Flannel pods to start communicating, and then run:

```bash
kubectl get nodes
kubectl get pods -A
```
Once both nodes show the `Ready` status, you will have a production-lite Kubernetes cluster perfectly matching the underlying architecture of your local Rancher development environment! 

You can then apply the edge manifests we created right over top of it using `kubectl apply -f app/edge/binhphuoc/...`.
