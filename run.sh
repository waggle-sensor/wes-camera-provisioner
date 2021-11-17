#!/bin/bash +x

cd /tmp
git clone git@github.com:waggle-sensor/hanwha_camera_client.git
cd hanwha_camera_client
python3 setup.py install
pip3 install dist/*.whl
cd /app
exit python3 -u camera_provisioner.py