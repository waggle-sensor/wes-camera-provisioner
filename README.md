# WES-Camera-Provisioner
A Waggle edge stack service managing cameras using Unifi network switch in a node. The service updates Waggle datashim for plugins to access cameras in the node.

# Install and Run
This service requires camera and switch credentials as well as node manifest. Please register these first before deploying the service.

To run,
```bash
kubectl apply -f kubernetes/wes-camera-provisioner.yaml
```