#!/bin/bash +x

cd /data

# Check if the directory exists and is not empty
if [ -d "hanwha_camera_client" ] && [ "$(ls -A hanwha_camera_client)" ]; then
    echo "Directory 'hanwha_camera_client' already exists and is not empty. Pulling latest changes."
    cd hanwha_camera_client
    git pull
else
    echo "Cloning repository."
    git clone git@github.com:waggle-sensor/hanwha_camera_client.git
    cd hanwha_camera_client
fi

# Build and install the package
python3 setup.py bdist_wheel
pip3 install dist/*.whl

# Start the application
cd /app
python3 -u camera_provisioner.py
exit $?
