#!/bin/bash +x

cd /data
git clone git@github.com:waggle-sensor/hanwha_camera_client.git
cd hanwha_camera_client
python3 setup.py bdist_wheel
pip3 install dist/*.whl
cd /app
python3 -u camera_provisioner.py
exit $?