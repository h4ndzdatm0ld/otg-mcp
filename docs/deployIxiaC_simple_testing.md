# Simple Testing with Ixia-C Community Edition

This guide provides quick instructions for deploying and testing the Ixia-C Community Edition using the deployIxiaC.sh script.

## Quick Start

### 1. Basic Deployment
```bash
./deploy/deployIxiaC.sh --remote <hostname> --mode one-arm
```

### 2. Verifying the Deployment
After deployment, the controller API will be available at:
```
https://<hostname>:8443
```

### 3. Simple Traffic Testing
Run a quick traffic test using the otgen tool (automatically installed by the script):
```bash
ssh <hostname> "otgen create flow --rate 100 --count 100 | otgen run -k --metrics flow"
```

## Common Testing Scenarios

### Gateway Testing (one-arm mode)
Ideal for testing single-interface scenarios where traffic is sent and received on the same interface.
```bash
./deploy/deployIxiaC.sh --remote <hostname> --mode one-arm
```

Use cases:
- Testing gateway device performance
- Basic throughput measurements
- Simple protocol conformance testing

### Path Testing (two-arm mode)
For testing traffic flow between two separate interfaces, useful for firewall testing.
```bash
./deploy/deployIxiaC.sh --remote <hostname> --mode two-arm
```

Use cases:
- Firewall throughput and latency testing
- Routing performance measurement
- Bidirectional traffic testing

### Advanced Testing (three-arm mode)
For complex traffic patterns requiring three interfaces.
```bash
./deploy/deployIxiaC.sh --remote <hostname> --mode three-arm
```

Use cases:
- Load balancer testing
- Complex routing scenarios
- Multi-path performance testing

## Integration with OTG MCP Server

Use the deployed Ixia-C instance with the OTG MCP Server:

1. Update your configuration file to point to the deployed instance:
```json
{
  "targets": {
    "ixiac": {
      "apiVersion": "1.30.0",
      "ports": {
        "port1": {
          "name": "port1",
          "location": "localhost:5555"
        },
        "port2": {
          "name": "port2",
          "location": "localhost:5556"
        }
      }
    }
  }
}
```

2. Start the OTG MCP Server with this configuration:
```bash
python -m otg_mcp.server --config-file your_config.json
```

## Troubleshooting

### No Traffic Generated
If no traffic is being generated, verify:
1. Interface connectivity
2. MTU settings
3. Container status with `docker ps`

### Container Issues
If containers fail to start:
```bash
ssh <hostname> "cd ixia-c/deployments && docker compose logs"
```

### Network Interface Problems
Check which interfaces are available on the remote host:
```bash
ssh <hostname> "ip addr show | grep -E ': |inet'"
```

## Quick Reference
- **Force redeployment**: Add `--force` flag
- **Custom MTU**: Use `--mtu <size>` (default: auto-detected)
- **Update to latest version**: Add `--update` flag
- **View container logs**: `ssh <hostname> "docker logs keng-controller"`
- **Stop deployment**: `ssh <hostname> "cd ixia-c/deployments && docker compose down"`

## Performance Tips

1. **MTU Optimization**
   For best performance, use jumbo frames if your network supports them:
   ```bash
   ./deploy/deployIxiaC.sh --remote <hostname> --mode two-arm --mtu 9000
   ```

2. **Traffic Engine Monitoring**
   Monitor traffic engine performance:
   ```bash
   ssh <hostname> "docker stats"
   ```

3. **Interface Selection**
   For production testing, dedicate specific interfaces for traffic:
   ```bash
   # Check available interfaces
   ssh <hostname> "ip link show"
   ```
   The script will auto-detect and use available interfaces, but for consistent testing, consider using the same interfaces each time.
