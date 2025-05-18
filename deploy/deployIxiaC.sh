#!/usr/bin/env bash

# =============================================================================
# Ixia-C Traffic Generator Deployment Script
# =============================================================================
#
# This script automates the deployment of Ixia-C traffic generators on remote hosts
# using SSH. It supports multiple deployment modes for different testing scenarios,
# auto-detects available network interfaces, and ensures all prerequisites are met.
#
# DEPLOYMENT MODES:
# ----------------
# 1. one-arm:   Single interface mode - Traffic is sent and received on the same
#               physical interface. Ideal for basic gateway testing and single
#               interface scenarios.
#
#               [Host] --- eth0 --- [Traffic Generator]
#
# 2. two-arm:   Dual interface mode - Traffic flows between two physical interfaces.
#               Ideal for path testing, firewall testing, and basic routing tests.
#
#               [Host A] --- eth0 --- [Traffic Generator] --- eth1 --- [Host B]
#
# 3. three-arm: Triple interface mode - Most advanced setup allowing complex traffic
#               patterns. Useful for triangular routing tests, load balancer testing,
#               and multi-path routing scenarios.
#
#               [Host A] --- eth0 --- [Traffic Generator] --- eth1 --- [Host B]
#                                        |
#                                       eth2
#                                        |
#                                     [Host C]
#
# PREREQUISITES:
# -------------
# - SSH access to the remote host
# - Docker running on the remote host
# - Network utilities (installed automatically if missing)
# - Suitable network interfaces with appropriate MTU settings
#
# EXAMPLES:
# --------
# Basic deployment with auto-detected settings:
#   ./deployIxiaC.sh --remote fantasia-1x.heshlaw.local
#
# Custom deployment with specific mode and MTU:
#   ./deployIxiaC.sh --remote fantasia-1x.heshlaw.local --mode two-arm --mtu 9000
#
# Force redeployment of existing setup:
#   ./deployIxiaC.sh --remote fantasia-1x.heshlaw.local --force
#
# NETWORK TOPOLOGY USAGE:
# ---------------------
# After deployment, you can use the traffic generator in your tests:
#
# 1. For gateway testing (one-arm):
#    - Traffic is generated on one interface and sent to the target gateway
#    - Example: python simple_gateway_test.py --api https://hostname:8443
#
# 2. For path testing (two-arm):
#    - Traffic flows from one interface to another through the device under test
#    - Configure flows with different source/destination ports
#
# 3. For complex routing (three-arm):
#    - Create complex traffic patterns between multiple interfaces
#    - Test asymmetric routing, load balancing, etc.
#
# TROUBLESHOOTING:
# ---------------
# 1. Connection issues: Ensure SSH keys are set up correctly
# 2. Docker errors: Verify Docker is running on the remote host
# 3. Interface problems: Check interface names and MTU settings
# 4. Container startup failures: Check Docker logs for details
#
# =============================================================================

set -euo pipefail

REMOTE_HOST=""
MODE="one-arm"
FORCE=false
MTU=""
UPDATE_REPOS=false

IXIA_REPO="https://github.com/open-traffic-generator/ixia-c.git"
IXIA_DIR="ixia-c"
DEPLOYMENTS_DIR="deployments"

# Fixed commit IDs for stability
# These are known good versions that have been tested together
IXIA_COMMIT_ID="4e027bd" # v1.28.0-33
CONFORMANCE_COMMIT_ID="9a514ea0be7dddb312feb5789f5a8541291fbb5c" # May 5th stable

# Required network utilities
REQUIRED_NET_UTILS=(
    "arping"       # ARP ping utility
    "ethtool"      # Ethernet device configuration
    "ip"           # IP configuration
    "brctl"        # Bridge utilities
    "ping"         # Basic connectivity testing
    "traceroute"   # Path tracing
    "tcpdump"      # Packet capture
    "netstat"      # Network statistics
    "lsof"         # List open files/ports
    "ss"           # Socket statistics
    "iperf3"       # Network performance testing
    "mtr"          # Network diagnostic tool
    "nmap"         # Network exploration
    "lldpd"        # Link Layer Discovery Protocol
    "tshark"       # Wireshark CLI for packet analysis
    "conntrack"    # Connection tracking
    "curl"         # Required for otgen installation
)

# Install otgen for validation
install_otgen() {
  print_info "Installing OTGen tool for validation"

  # Define the installation directory and version
  local install_dir="/usr/local/bin"
  local latest_version="v0.6.3"
  local download_url="https://github.com/open-traffic-generator/otgen/releases/download/${latest_version}/otgen_${latest_version#v}_Linux_x86_64.tar.gz"

  print_info "Downloading OTGen ${latest_version} directly"

  # Create a temporary directory for download
  remote_exec "mkdir -p /tmp/otgen-install"

  # Download and install directly
  if remote_exec "curl -sL $download_url -o /tmp/otgen-install/otgen.tar.gz"; then
    print_info "Extracting OTGen binary"
    remote_exec "tar -xzf /tmp/otgen-install/otgen.tar.gz -C /tmp/otgen-install"

    print_info "Installing to $install_dir (may require sudo)"
    if remote_exec "sudo cp /tmp/otgen-install/otgen $install_dir/ && sudo chmod +x $install_dir/otgen"; then
      print_success "OTGen tool installed successfully"
      remote_exec "otgen version || $install_dir/otgen version"
    else
      print_error "Failed to install OTGen tool to $install_dir"
      print_info "This is not critical, continuing with deployment"
    fi
  else
    print_error "Failed to download OTGen"
    print_info "This is not critical, continuing with deployment"
  fi

  # Cleanup
  remote_exec "rm -rf /tmp/otgen-install"

  # Check if otgen is accessible in PATH
  if remote_exec "command -v otgen > /dev/null 2>&1"; then
    print_success "OTGen is available in PATH"
  else
    print_info "OTGen may not be in PATH but might be available at $install_dir/otgen"
  fi
}

# ANSI Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
  echo -e "${BLUE}Ixia-C Deployment Script${NC}"
  echo "Usage: $0 --remote <hostname> [--mode one-arm|two-arm|three-arm] [--mtu <size>] [--force] [--update]"
  echo
  echo "Arguments:"
  echo "  --remote HOSTNAME   Remote host where Ixia-C will be deployed (required)"
  echo "  --mode MODE         Deployment mode (one-arm, two-arm, three-arm) (default: one-arm)"
  echo "  --mtu SIZE          MTU size for interfaces (default: auto-detect)"
  echo "  --force             Force redeployment even if containers are already running"
  echo "  --update            Update repositories to latest version (otherwise use fixed commit IDs)"
  echo
  echo "Examples:"
  echo "  $0 --remote fantasia-1x.heshlaw.local"
  echo "  $0 --remote fantasia-1x.heshlaw.local --mode two-arm --mtu 9000"
  echo "  $0 --remote fantasia-1x.heshlaw.local --force --update"
  exit 1
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --remote)
        REMOTE_HOST="$2"; shift 2;;
      --mode)
        MODE="$2"; shift 2;;
      --mtu)
        MTU="$2"; shift 2;;
      --force)
        FORCE=true; shift;;
      --update)
        UPDATE_REPOS=true; shift;;
      *)
        echo -e "${RED}Unknown option: $1${NC}"
        usage;;
    esac
  done

  if [[ -z "$REMOTE_HOST" ]]; then
    echo -e "${RED}Error: --remote is required${NC}"
    usage
  fi

  # Validate mode
  if [[ ! "$MODE" =~ ^(one-arm|two-arm|three-arm)$ ]]; then
    echo -e "${RED}Error: Invalid mode '$MODE'. Must be one-arm, two-arm, or three-arm${NC}"
    usage
  fi
}

# Variables for password handling
SUDO_PASSWORD=""
USE_ASKPASS=false

remote_exec() {
  if [[ "$@" == *"sudo "* ]] && [[ -n "$SUDO_PASSWORD" ]]; then
    # If command contains sudo and we have a password, use it via stdin
    echo "$SUDO_PASSWORD" | ssh "$REMOTE_HOST" "sudo -S $*"
  else
    # Otherwise use normal execution
    ssh "$REMOTE_HOST" "$@"
  fi
}

remote_exec_tty() {
  if [[ "$@" == *"sudo "* ]] && [[ -n "$SUDO_PASSWORD" ]]; then
    # Even with TTY, use the password if we have it
    echo "$SUDO_PASSWORD" | ssh -t "$REMOTE_HOST" "sudo -S $*"
  else
    # Regular TTY execution
    ssh -t "$REMOTE_HOST" "$@"
  fi
}

# Function to ask for the sudo password if needed
ask_for_sudo_password() {
  print_info "Checking if sudo password is required on remote host..."

  # Try to run a simple sudo command without password to see if it works
  if ! ssh "$REMOTE_HOST" "sudo -n true" 2>/dev/null; then
    print_info "Sudo password is required for $REMOTE_HOST"

    # Prompt for password (securely)
    read -rsp "Enter sudo password for $REMOTE_HOST: " SUDO_PASSWORD
    echo

    # Verify the password works
    if ! echo "$SUDO_PASSWORD" | ssh "$REMOTE_HOST" "sudo -S true" 2>/dev/null; then
      print_error "Invalid sudo password"
      SUDO_PASSWORD=""
      # Try again
      read -rsp "Enter sudo password for $REMOTE_HOST (retry): " SUDO_PASSWORD
      echo

      if ! echo "$SUDO_PASSWORD" | ssh "$REMOTE_HOST" "sudo -S true" 2>/dev/null; then
        print_error "Invalid sudo password. Exiting."
        exit 1
      fi
    fi

    print_success "Sudo password validated"
  else
    print_success "No sudo password required (passwordless sudo configured)"
  fi
}

print_info() {
  echo -e "${YELLOW}➤ $1${NC}"
}

print_success() {
  echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
  echo -e "${RED}✗ $1${NC}"
}

# Function to install Docker on the remote host
install_docker() {
  print_info "Docker not detected. Attempting to install Docker on $REMOTE_HOST"

  # Determine OS distribution
  if remote_exec "test -f /etc/os-release && source /etc/os-release && echo \$ID"; then
    OS_ID=$(remote_exec "source /etc/os-release && echo \$ID")
    print_info "Detected OS: $OS_ID"

    case "$OS_ID" in
      ubuntu|debian)
        print_info "Installing Docker on Ubuntu/Debian"
        # Update package index
        remote_exec "sudo apt-get update"

        # Install prerequisites
        remote_exec "sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common gnupg lsb-release"

        # Add Docker's official GPG key
        remote_exec "sudo mkdir -p /etc/apt/keyrings"
        remote_exec "curl -fsSL https://download.docker.com/linux/$OS_ID/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg"

        # Set up the repository
        remote_exec "echo \"deb [arch=\$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$OS_ID \$(lsb_release -cs) stable\" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null"

        # Update apt and install Docker Engine
        remote_exec "sudo apt-get update"
        remote_exec "sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-buildx-plugin"
        ;;

      centos|rhel|fedora|amzn)
        print_info "Installing Docker on CentOS/RHEL/Fedora/Amazon Linux"
        # Install required packages
        remote_exec "sudo yum install -y yum-utils"

        # Add the Docker repository
        remote_exec "sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo"

        # Install Docker
        remote_exec "sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin docker-buildx-plugin"
        ;;

      *)
        print_error "Unsupported OS distribution: $OS_ID"
        print_info "Please install Docker manually using instructions from https://docs.docker.com/engine/install/"
        return 1
        ;;
    esac

    # Start and enable Docker service
    print_info "Starting Docker service"
    remote_exec "sudo systemctl start docker"
    remote_exec "sudo systemctl enable docker"

    # Add current user to the docker group
    print_info "Adding current user to docker group"
    remote_exec "sudo usermod -aG docker \$(whoami)"

    print_info "Docker installation complete. You may need to reconnect to the server for group changes to take effect."
    return 0
  else
    print_error "Could not detect OS distribution"
    print_info "Please install Docker manually using instructions from https://docs.docker.com/engine/install/"
    return 1
  fi
}

check_docker_running() {
  print_info "Checking Docker status on remote host"

  # Check if Docker is installed
  if ! remote_exec "command -v docker > /dev/null 2>&1"; then
    print_info "Docker is not installed on $REMOTE_HOST"

    # Attempt to install Docker
    if install_docker; then
      print_success "Docker installed successfully"
    else
      print_error "Failed to install Docker"
      echo "Please install Docker manually on $REMOTE_HOST"
      exit 1
    fi
  fi

  # Now check if Docker is running
  if remote_exec "docker ps > /dev/null 2>&1"; then
    print_success "Docker is running"
  else
    print_info "Docker is installed but not running. Attempting to start Docker service..."
    if remote_exec "sudo systemctl start docker"; then
      print_success "Docker service started successfully"
    else
      print_error "Failed to start Docker service on $REMOTE_HOST"
      echo "Please start Docker service manually with: sudo systemctl start docker"
      exit 1
    fi
  fi
}

check_and_install_network_utils() {
  print_info "Checking for required network utilities"

  # Determine package manager
  if remote_exec "command -v apt-get > /dev/null 2>&1"; then
    PKG_MANAGER="apt-get"
    INSTALL_CMD="apt-get install -y"
  elif remote_exec "command -v yum > /dev/null 2>&1"; then
    PKG_MANAGER="yum"
    INSTALL_CMD="yum install -y"
  elif remote_exec "command -v dnf > /dev/null 2>&1"; then
    PKG_MANAGER="dnf"
    INSTALL_CMD="dnf install -y"
  else
    print_error "Could not determine package manager on remote host"
    echo "Please install required utilities manually: ${REQUIRED_NET_UTILS[*]}"
    exit 1
  fi

  # Check required utilities
  missing_utils=()
  for util in "${REQUIRED_NET_UTILS[@]}"; do
    if ! remote_exec "command -v $util > /dev/null 2>&1"; then
      missing_utils+=("$util")
    fi
  done

  # Install missing required utilities
  if [ ${#missing_utils[@]} -gt 0 ]; then
    print_info "Installing missing required utilities: ${missing_utils[*]}"

    # Map utility names to package names (some might differ)
    install_packages=()
    for util in "${missing_utils[@]}"; do
      case "$util" in
        "arping")
          install_packages+=("iputils-arping");;
        "brctl")
          install_packages+=("bridge-utils");;
        "mtr")
          install_packages+=("mtr-tiny");;
        "iperf3")
          install_packages+=("iperf3");;
        "ip")
          install_packages+=("iproute2");;
        "netstat")
          install_packages+=("net-tools");;
        "ss")
          install_packages+=("iproute2");;
        "tshark")
          install_packages+=("tshark");;
        "conntrack")
          [[ "$PKG_MANAGER" == "apt-get" ]] && install_packages+=("conntrack") || install_packages+=("conntrack-tools");;
        *)
          install_packages+=("$util");;
      esac
    done

    # Ensure installation is non-interactive
    remote_exec "sudo DEBIAN_FRONTEND=noninteractive $INSTALL_CMD -q --yes --no-install-recommends ${install_packages[*]}"

    # Verify installation
    failed_installs=()
    for util in "${missing_utils[@]}"; do
      if ! remote_exec "command -v $util > /dev/null 2>&1"; then
        failed_installs+=("$util")
      fi
    done

    if [ ${#failed_installs[@]} -gt 0 ]; then
      print_error "Failed to install some utilities: ${failed_installs[*]}"
      echo "Please install them manually to ensure proper operation"
    else
      print_success "All required utilities are now installed"
    fi
  else
    print_success "All required network utilities are already installed"
  fi

  # Since all needed utilities are in the REQUIRED_NET_UTILS list,
  # we don't need to check for optional utilities anymore
}

clone_or_update_repo() {
  print_info "Checking for Ixia-C repository on remote host"

  if remote_exec "[ -d $IXIA_DIR ]"; then
    # Clean up any uncommitted changes
    print_info "Repository exists, cleaning up uncommitted changes"
    remote_exec "cd $IXIA_DIR && git reset --hard HEAD && git clean -fd"

    if [[ "$UPDATE_REPOS" == true ]]; then
      print_info "Updating repository to latest version (--update flag specified)"
      remote_exec "cd $IXIA_DIR && git pull --ff-only"
      remote_exec "cd $IXIA_DIR && git submodule foreach --recursive 'git reset --hard HEAD && git clean -fd && git checkout main && git pull --ff-only || true'"
      remote_exec "cd $IXIA_DIR && git submodule update --init --recursive"
    else
      print_info "Using fixed commit IDs for stability"
      # Set main repo to specific commit
      remote_exec "cd $IXIA_DIR && git fetch && git checkout $IXIA_COMMIT_ID"
      # Set conformance submodule to specific commit
      remote_exec "cd $IXIA_DIR && git submodule update --init conformance"
      remote_exec "cd $IXIA_DIR/conformance && git checkout $CONFORMANCE_COMMIT_ID"
      # Update other submodules
      remote_exec "cd $IXIA_DIR && git submodule update --init --recursive"
    fi
  else
    print_info "Cloning Ixia-C repository"
    remote_exec "git clone $IXIA_REPO"

    if [[ "$UPDATE_REPOS" == true ]]; then
      print_info "Using latest version (--update flag specified)"
      remote_exec "cd $IXIA_DIR && git submodule update --init --recursive"
    else
      print_info "Setting to fixed commit IDs for stability"
      remote_exec "cd $IXIA_DIR && git checkout $IXIA_COMMIT_ID"
      remote_exec "cd $IXIA_DIR && git submodule update --init conformance"
      remote_exec "cd $IXIA_DIR/conformance && git checkout $CONFORMANCE_COMMIT_ID"
      remote_exec "cd $IXIA_DIR && git submodule update --init --recursive"
    fi
  fi

  print_success "Ixia-C repo is ready on remote host"
}

detect_interfaces_and_set_env() {
  print_info "Detecting Ethernet interfaces for $MODE mode"

  # Show ALL interfaces for better debugging and visibility
  print_info "All available interfaces on remote host:"
  remote_exec "ip addr show | grep -E ': |inet'" || true

  # Get list of physical interfaces with verbose output
  print_info "Searching for active interfaces..."

  # First attempt: look for UP or NO-CARRIER interfaces (excluding virtual ones)
  ETH_INTERFACES=$(remote_exec "ip -o link show | grep -E 'state UP|NO-CARRIER' | awk -F': ' '{print \$2}' | grep -Ev 'lo|docker|veth|br-' | head -3") || true
  print_info "UP interfaces found: ${ETH_INTERFACES:-None}"

  if [[ -z "$ETH_INTERFACES" ]]; then
    print_info "No active interfaces found, looking for all physical interfaces"
    ETH_INTERFACES=$(remote_exec "ip -o link show | awk -F': ' '{print \$2}' | grep -E 'enp|eth|ens|em|eno' | grep -Ev 'lo|docker|veth|br-' | head -3") || true
    print_info "Physical interfaces found: ${ETH_INTERFACES:-None}"

    # If still empty, try an even broader approach
    if [[ -z "$ETH_INTERFACES" ]]; then
      print_info "No standard interfaces found, trying broader pattern..."
      ETH_INTERFACES=$(remote_exec "ip -o link show | grep -v 'link/loopback' | awk -F': ' '{print \$2}' | grep -Ev 'lo|docker|veth|br-' | head -3") || true
      print_info "Broader interfaces found: ${ETH_INTERFACES:-None}"
    fi
  fi

  if [[ -z "$ETH_INTERFACES" ]]; then
    print_error "No usable ethernet interfaces found on $REMOTE_HOST"
    exit 1
  fi

  IFS=$'\n' read -rd '' -a IFC <<<"$ETH_INTERFACES"

  # Check if we have enough interfaces for the selected mode
  interfaces_needed=1
  case "$MODE" in
    "one-arm") interfaces_needed=1 ;;
    "two-arm") interfaces_needed=2 ;;
    "three-arm") interfaces_needed=3 ;;
  esac

  if [ ${#IFC[@]} -lt "$interfaces_needed" ]; then
    print_error "Not enough interfaces available for $MODE mode (found ${#IFC[@]}, need $interfaces_needed)"
    echo "Available interfaces: ${IFC[*]}"
    echo "Please select a different mode or check network interfaces on the remote host"
    exit 1
  fi

  echo -e "Using interfaces: ${GREEN}${IFC[*]}${NC}"

  # Prepare deployment files
  print_info "Preparing deployment configuration"
  remote_exec "cd $IXIA_DIR && cp deployments/raw-${MODE}.yml deployments/docker-compose.yml"

  # Create the .env file with appropriate settings
  env_content="CONTROLLER_VERSION=latest
TRAFFIC_ENGINE_VERSION=latest
AUR_VERSION=latest
IFC1=${IFC[0]:-eth1}
TCP_PORT_IFC1=5555
CPU_CORES_IFC1=\"0,1,2\"
${IFC[1]:+IFC2=${IFC[1]}}
${IFC[1]:+TCP_PORT_IFC2=5556}
${IFC[1]:+CPU_CORES_IFC2=\"0,3,4\"}
${IFC[2]:+IFC3=${IFC[2]}}
${IFC[2]:+TCP_PORT_IFC3=5557}
${IFC[2]:+CPU_CORES_IFC3=\"0,5,6\"}"

  print_info "Docker-compose environment configuration:"
  echo -e "${YELLOW}----------- .env file content -----------${NC}"
  echo "$env_content"
  echo -e "${YELLOW}----------------------------------------${NC}"

  remote_exec "cat > $IXIA_DIR/deployments/.env << 'EOL'
$env_content
EOL"

  print_success ".env file prepared for $MODE mode"
}

calculate_mtu() {
  if [[ -n "$MTU" ]]; then
    # Validate the provided MTU
    if ! [[ "$MTU" =~ ^[0-9]+$ ]] || (( MTU < 68 )) || (( MTU > 9000 )); then
      print_error "Invalid MTU value: $MTU. Must be between 68 and 9000."
      exit 1
    fi
    print_info "Using provided MTU: $MTU"
    return
  fi

  print_info "Determining optimal MTU from available interfaces"
  MTU=$(remote_exec "ip link show | grep -Eo 'mtu [0-9]+' | awk '{print \$2}' | sort -nr | head -1")

  # Use standard MTU if detection fails
  if [[ -z "$MTU" || ! "$MTU" =~ ^[0-9]+$ ]]; then
    MTU=1500
    print_info "MTU detection failed, defaulting to standard MTU: $MTU"
  else
    print_success "MTU determined: $MTU"
  fi
}

check_containers_running() {
  print_info "Checking existing Ixia-C containers"

  # Check for both naming patterns - older keng-controller and newer deployments-controller
  running_old=$(remote_exec "docker ps --filter name=keng-controller -q")
  running_new=$(remote_exec "docker ps --filter name=deployments-controller -q")

  # Combine results
  running="$running_old$running_new"

  # If any container pattern found
  if [[ -n "$running" ]]; then
    # Show details of what's running
    print_info "Existing containers found:"
    remote_exec "docker ps --filter name=controller"

    if [[ "$FORCE" == true ]]; then
      print_info "Force flag is set - will redeploy existing containers"
      # We'll return 0 to indicate deployment should proceed
      return 0
    else
      print_success "Ixia-C containers are already running"
      echo -e "Use ${YELLOW}--force${NC} to redeploy if needed"

      # Extract controller container name for verification
      CONTROLLER=$(remote_exec "docker ps --format '{{.Names}}' | grep -E '(controller|keng-controller)' | head -1")
      print_info "Using existing controller container: $CONTROLLER"

      # Set SKIP_DEPLOYMENT flag to skip subsequent deployment steps
      SKIP_DEPLOYMENT=true
      return 1  # Return 1 to indicate deployment should be skipped
    fi
  else
    print_info "No running Ixia-C containers found - will proceed with deployment"
    SKIP_DEPLOYMENT=false
    return 0  # Return 0 to indicate deployment should proceed
  fi
}

deploy_ixia() {
  print_info "Deploying Ixia-C containers ($MODE mode) with MTU=$MTU"

  # Stop any existing containers first
  remote_exec "cd $IXIA_DIR/deployments && docker compose down || true"

  # Deploy new containers
  if ! remote_exec "cd $IXIA_DIR/deployments && MTU=$MTU docker compose up -d"; then
    print_error "Deployment failed"
    echo -e "Check docker compose logs with: ${YELLOW}ssh $REMOTE_HOST 'cd $IXIA_DIR/deployments && docker compose logs'${NC}"
    exit 1
  fi

  print_success "Deployment complete"
}

verify_deployment() {
  print_info "Verifying deployment"

  # Wait a moment for containers to stabilize
  sleep 5

  # Check different container naming patterns based on the observed output
  print_info "Looking for controller container..."

  # First check for docker-compose style names
  CONTROLLER_PATTERN=$(remote_exec "docker ps --format '{{.Names}}' | grep -E '(controller|keng-controller)'" || echo "")
  print_info "Found controller container(s): ${CONTROLLER_PATTERN:-None}"

  if [[ -z "$CONTROLLER_PATTERN" ]]; then
    print_error "Controller container is not running"
    echo "Deployment verification failed. Showing all containers:"
    remote_exec "docker ps -a"
    exit 1
  else
    print_success "Controller container found: $CONTROLLER_PATTERN"
  fi

  # Check if traffic engines are running based on mode
  engines_needed=1
  case "$MODE" in
    "one-arm") engines_needed=1 ;;
    "two-arm") engines_needed=2 ;;
    "three-arm") engines_needed=3 ;;
  esac

  # Check both naming patterns for traffic engines
  TRAFFIC_ENGINES=$(remote_exec "docker ps --format '{{.Names}}' | grep -E '(traffic[_-]engine|ixia-c-traffic-engine)' | wc -l")
  print_info "Found $TRAFFIC_ENGINES traffic engine container(s)"

  if (( TRAFFIC_ENGINES < engines_needed )); then
    print_error "Not all traffic engines are running (found $TRAFFIC_ENGINES, need $engines_needed)"
    remote_exec "docker ps -a | grep -E '(traffic[_-]engine|ixia-c-traffic-engine)'"
    exit 1
  else
    print_success "Found required traffic engines ($TRAFFIC_ENGINES)"
    # Show the actual container names
    print_info "Traffic engine containers:"
    remote_exec "docker ps --format '{{.Names}}' | grep -E '(traffic[_-]engine|ixia-c-traffic-engine)'"
  fi

  print_success "All required containers are running"
  print_info "All running containers:"
  remote_exec "docker ps"

  print_info "Extracting first controller container name for logs..."
  CONTROLLER=$(remote_exec "docker ps --format '{{.Names}}' | grep -E '(controller|keng-controller)' | head -1")
  print_info "Using controller container: $CONTROLLER"

  print_info "Verifying traffic generator functionality using otgen"

  # Wait a bit for controller API to be ready
  sleep 5

  # Create a temporary shell script to set environment variables and run otgen
  print_info "Setting up environment for otgen verification"

  remote_exec "cat > /tmp/otgen_verify.sh << 'EOL'
#!/bin/bash
# Set environment variables for otgen
export OTG_API=\"https://localhost:8443\"
export OTG_LOCATION_P1=\"localhost:5555\"
export OTG_LOCATION_P2=\"localhost:5556\"
export OTG_FLOW_SMAC_P1=\"02:00:00:00:01:aa\"
export OTG_FLOW_DMAC_P1=\"02:00:00:00:02:aa\"

# Run otgen verification
otgen create flow --rate 100 --count 100 | otgen run -k --metrics flow
EOL"

  # Make the script executable
  remote_exec "chmod +x /tmp/otgen_verify.sh"

  print_info "Executing otgen verification test..."

  # Try multiple times with increasing delays
  local max_attempts=5
  local attempt=1
  local success=false

  while [[ $attempt -le $max_attempts && "$success" != "true" ]]; do
    print_info "Attempt $attempt/$max_attempts: Running otgen flow test..."

    # Run the verification script we created
    verification_result=$(remote_exec "/tmp/otgen_verify.sh 2>&1") || true

    # Check if verification was successful by looking for tx frames in output
    if echo "$verification_result" | grep -q "frames_tx"; then
      success=true
      print_success "Traffic generator verified with otgen!"
      echo
      echo -e "${GREEN}========== OTGen Verification Results ==========${NC}"
      echo "$verification_result" | grep -E 'frames_tx|bytes_tx|transmit|metrics'
      echo -e "${GREEN}=============================================${NC}"
    else
      sleep_time=$((5 * attempt)) # Progressive backoff
      print_info "Verification failed, waiting ${sleep_time} seconds before retry..."
      # Show what went wrong
      print_info "otgen output:"
      echo "$verification_result" | tail -10
      sleep $sleep_time
      attempt=$((attempt + 1))
    fi
  done

  if [[ "$success" != "true" ]]; then
    print_error "Traffic generator verification failed after multiple attempts"
    print_info "This may be normal for the first deployment - services might need more time to initialize"
    print_info "Recent container logs from $CONTROLLER:"
    remote_exec "docker logs $CONTROLLER 2>&1 | tail -20" || true
    print_info "You can run a manual test with:"
    print_info "  ssh $REMOTE_HOST otgen create flow --rate 100 --count 100 | otgen run -k --metrics flow"
  fi
}

print_usage_guidance() {
  echo
  print_info "DEPLOYMENT COMPLETE - USAGE INSTRUCTIONS"
  echo
  echo -e "${BLUE}Controller API:${NC}"
  echo -e "  https://${REMOTE_HOST}:8443"
  echo

  # Different usage guidance based on mode
  case "$MODE" in
    "one-arm")
      echo -e "${BLUE}One-Arm Traffic Testing:${NC}"
      echo -e "  Useful for gateway testing and single interface testing"
      echo -e "  Example command: python simple_gateway_test.py --api https://${REMOTE_HOST}:8443"
      ;;
    "two-arm")
      echo -e "${BLUE}Two-Arm Traffic Testing:${NC}"
      echo -e "  Useful for path testing between two interfaces"
      echo -e "  Configure traffic between ${IFC[0]} and ${IFC[1]}"
      ;;
    "three-arm")
      echo -e "${BLUE}Three-Arm Traffic Testing:${NC}"
      echo -e "  Supports complex traffic patterns between three interfaces"
      echo -e "  Interfaces: ${IFC[0]}, ${IFC[1]}, ${IFC[2]}"
      ;;
  esac

  echo
  echo -e "${BLUE}Monitoring Interface Traffic:${NC}"
  echo -e "  ssh -t $REMOTE_HOST sudo tcpdump -i ${IFC[0]} -n not port 22"
  echo
  echo -e "${BLUE}Stopping Containers:${NC}"
  echo -e "  ssh $REMOTE_HOST cd $IXIA_DIR/deployments && docker compose down"
  echo
  echo -e "${BLUE}Viewing Container Logs:${NC}"
  echo -e "  ssh $REMOTE_HOST docker logs keng-controller"
}

# Trap for debugging - show where the script might be failing
trap 'echo "Error: Command failed at line $LINENO"' ERR

# Exit handler to ensure we provide useful output even if script fails
cleanup() {
  local exit_code=$?
  if [ $exit_code -ne 0 ]; then
    echo
    print_error "Script execution failed with exit code $exit_code"
    echo
    echo "=============== DEBUG INFORMATION ==============="
    echo "Last command executed: $BASH_COMMAND"
    echo "Line number: ${BASH_LINENO[0]}"
    echo
    echo "Remote host system information:"
    remote_exec "uname -a || echo 'Could not get system info'" || true
    echo
    echo "Docker container status:"
    remote_exec "docker ps -a || echo 'Could not check containers'" || true
    echo
    echo "==================== LOGS ======================="
    # Try to get logs from the controller container, using the docker-compose naming pattern
    CONTROLLER=$(remote_exec "docker ps --format '{{.Names}}' | grep -E '(controller|keng-controller|deployments-controller)' | head -1" 2>/dev/null || echo "")
    if [[ -n "$CONTROLLER" ]]; then
      print_info "Logs from controller container ($CONTROLLER):"
      remote_exec "docker logs $CONTROLLER 2>&1 | tail -20" || true
    else
      echo "No controller container found to retrieve logs"
    fi
    echo "================================================"
  fi
}

main() {
  # Set up exit trap for better debugging
  trap cleanup EXIT

  # Enable debugging output when DEBUG=1 is set
  if [[ "${DEBUG:-0}" == "1" ]]; then
    set -x
  fi

  echo
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}  Ixia-C Traffic Generator Deployment  ${NC}"
  echo -e "${GREEN}========================================${NC}"
  echo

  # Capture start time for performance measurement
  local start_time=$SECONDS

  parse_args "$@"
  print_info "Deploying Ixia-C on $REMOTE_HOST in $MODE mode"
  print_info "Starting deployment steps..."

  # Ask for sudo password before starting any operations that might need it
  print_info "Step 0/9: Checking sudo password requirements"
  ask_for_sudo_password
  echo

  print_info "Step 1/8: Checking Docker status"
  check_docker_running
  print_info "Docker version on remote host:"
  remote_exec "docker --version" || true
  remote_exec "docker info | grep 'Server Version\|Running\|Storage'" || true
  echo

  print_info "Step 2/9: Verifying network utilities"
  check_and_install_network_utils
  print_info "Installed networking utilities:"
  for util in "${REQUIRED_NET_UTILS[@]}"; do
    if remote_exec "command -v $util > /dev/null 2>&1"; then
      # Get version info using the appropriate flag based on the utility
      version_info=""
      case "$util" in
        "arping")
          version_info="installed";;
        "ip")
          version_info="$(remote_exec "$util -V 2>&1 | head -1" || echo "installed")";;
        "ping")
          version_info="$(remote_exec "$util -V 2>&1 | head -1" || echo "installed")";;
        "brctl")
          version_info="$(remote_exec "dpkg -l | grep bridge-utils | awk '{print \$2, \$3}'" || echo "installed")";;
        "lsof")
          version_info="$(remote_exec "$util -v 2>&1 | head -2 | tail -1" || echo "installed")";;
        "lldpd")
          version_info="$(remote_exec "$util -v 2>&1 | head -1" || echo "installed")";;
        *)
          # Default to --version for most utilities
          version_info="$(remote_exec "$util --version 2>&1 | head -1" || echo "installed")";;
      esac
      echo -e "  ${GREEN}✓ $util${NC} - ${version_info}"
    fi
  done
  echo

  # Install OTGen for validation
  print_info "Step 3/9: Installing OTGen validation tool"
  install_otgen
  echo

  print_info "Step 4/9: Preparing repository"
  clone_or_update_repo
  print_info "Repository status:"
  remote_exec "cd $IXIA_DIR && git status -s" || true
  remote_exec "cd $IXIA_DIR && echo 'Current commit: ' && git log -1 --oneline" || true
  echo

  # Initialize skip deployment flag
  SKIP_DEPLOYMENT=false

  print_info "Step 5/9: Checking existing containers"
  check_containers_running
  print_info "Current Docker containers:"
  remote_exec "docker ps -a" || true
  echo

  # Skip deployment steps if containers are already running and no force flag
  if [[ "$SKIP_DEPLOYMENT" == "true" ]]; then
    print_info "Using existing containers - skipping deployment steps"
    # Extract interfaces from running containers for usage guidance
    if [[ -z "${IFC[*]}" ]]; then
      print_info "Extracting interface information from existing deployment"
      if remote_exec "[ -f $IXIA_DIR/deployments/.env ]"; then
        IFC_INFO=$(remote_exec "grep -E '^IFC[0-9]=' $IXIA_DIR/deployments/.env" || echo "IFC1=eth0")
        # Extract interface names from the .env file
        IFC=($(echo "$IFC_INFO" | sed -E 's/IFC[0-9]=(.*)/\1/'))
        print_info "Detected interfaces from existing deployment: ${IFC[*]}"
      else
        print_info "Using default interface names for guidance"
        IFC=("eth0")
      fi
    fi
    # Get MTU for usage guidance
    if [[ -z "$MTU" ]]; then
      MTU="1500"
    fi
  else
    # Continue with normal deployment steps
    print_info "Step 6/9: Setting up network interfaces"
    detect_interfaces_and_set_env || {
      print_error "Interface detection failed, trying fallback approach"
      print_info "Setting default interface to 'eth0' and continuing"
      IFC=("eth0")
      echo -e "Using fallback interface: ${GREEN}${IFC[*]}${NC}"
    }
    echo

    print_info "Step 7/9: Configuring MTU"
    calculate_mtu || {
      print_error "MTU detection failed, using default"
      MTU=1500
      print_info "Using default MTU: $MTU"
    }
    echo

    print_info "Step 8/9: Deploying containers"
    deploy_ixia || {
      print_error "Deployment failed, but continuing with verification"
    }
    echo
    print_info "Deployed containers:"
    remote_exec "docker ps -a" || true
    echo
  fi

  print_info "Step 9/9: Verifying deployment"
  verify_deployment || {
    print_error "Verification encountered issues, check container logs for details"
    remote_exec "docker logs keng-controller 2>&1 | tail -20" || true
  }
  echo

  # Calculate duration
  local duration=$((SECONDS - start_time))
  local minutes=$((duration / 60))
  local seconds=$((duration % 60))

  print_usage_guidance
  print_success "Ixia-C deployment completed in ${minutes}m ${seconds}s!"
  echo -e "${GREEN}=================================================${NC}"
  echo -e "${GREEN}  Ixia-C is now ready for use!${NC}"
  echo -e "${GREEN}  API endpoint: https://${REMOTE_HOST}:8443${NC}"
  echo -e "${GREEN}  Interface(s): ${IFC[*]}${NC}"
  echo -e "${GREEN}  Mode: $MODE${NC}"
  echo -e "${GREEN}=================================================${NC}"

  # Remove the EXIT trap since we're exiting successfully
  trap - EXIT
}

# Set REMOTE_HOST from first argument if provided in old format for backward compatibility
if [[ $# -gt 0 && "$1" != "--"* ]]; then
  echo -e "${YELLOW}Warning: Using legacy format without named arguments${NC}"
  echo -e "${YELLOW}Please use: $0 --remote <hostname> [--mode <mode>] [--mtu <size>] [--force]${NC}"
  REMOTE_HOST="$1"
  shift
fi

# You can enable debug mode with: DEBUG=1 ./deployIxiaC.sh [args]
main "$@"
