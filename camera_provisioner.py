#!/usr/bin/env python3
import os
import json
import logging
import os
import time
import re

import kubernetes

from hanwhacamera import get_camera_credential, update_hanwha_camera
from networkswitch import (
    get_cameras_from_nmap,
    get_networkswitch_credential,
    get_ports_from_switch,
)
import utils

WAGGLE_MANIFEST_V2_PATH = os.getenv("WAGGLE_MANIFEST_V2_PATH", "")

TARGET_CAMERA_REGEX = os.getenv("TARGET_CAMERA_REGEX", [
    {
        "description": "hanwha cameras",
        "manufacturer": "hanwha",
        "hw_model": ["XNV-8082R", "XNV-8080R", "XNP-6400RW", "XNF-8010RV", "XNV-8081Z"],
    },
    {
        "description": "mobotix cameras",
        "manufacturer": "mobotix",
        "hw_model": ["*"],
    },
    {
        "description": "NEON stardot cameras",
        "manufacturer": "stardot",
        "hw_model": ["NetCam CS"],
    }
])

def print_logic():
    print(
        """
A. get list of cameras from node-manifest-v2.json

B. get list of cameras currently recognized from Unifi switch

C. check each of recognized cameras in B., if the camera needs a provisioning

D. provision cameras that need it

Cameras in factory default state
|
|
States:
unknown -- the state of camera is unknown

error -- there is an error on the camera. Check the note column to get more information

factory -- the camera is in factory default state

configured -- the camera is configured using node-manifest-v2.json
"""
    )


def get_cameras_from_manifest(manifest_path, camera_matchers:list) -> list:
    logging.info(f'loading manifest from {manifest_path}')
    manifest = utils.load_node_manifest(manifest_path)
    logging.info(f'finding cameras from given manifest')
    if "sensors" not in manifest or len(manifest["sensors"]) == 0:
        logging.info("no sensors found from manifest")
        return []
    found_cameras = []
    # get nodes' global sensors that include camera
    for m_sensor in manifest["sensors"]:
        sensor_name = m_sensor.get("name", "")
        if sensor_name == "":
            logging.warn('found a sensor with no name. skipping.')
            continue
        logging.info(f'found sensor {sensor_name} from manifest')
        manifest_hardware = m_sensor.get("hardware", None)
        if manifest_hardware is None:
            logging.warn(f'no hardware information found from {sensor_name}. skipping.')
            continue
        # get manufacturer and hardware model of camera from the manifest
        manifest_manufacturer = manifest_hardware.get("manufacturer", "")
        manifest_hw_model = manifest_hardware.get("hw_model", "")
        for camera_matcher in camera_matchers:
            if camera_matcher.match(manifest_manufacturer, manifest_hw_model):
                logging.info(f'found a match {sensor_name}')
                c = utils.CameraObject(sensor_name, manifest_manufacturer, manifest_hw_model)
                c.serial_no = m_sensor.get("serial_no", "")
                c.url = m_sensor.get("uri", "")
                c.set_state("unknown")
                found_cameras.append(c)
                break
    return found_cameras


def get_configmap(api, name, namespace="default"):
    configmaps = api.list_namespaced_config_map(namespace)
    for configmap in configmaps.items:
        if name in configmap.metadata.name:
            return configmap
    return None


def set_datashim(api, datashim, name, namespace="default"):
    configmap = get_configmap(api, name, namespace)
    if configmap == None:
        configmap = kubernetes.client.V1ConfigMap()
        configmap.metadata = kubernetes.client.V1ObjectMeta(name=name)
        configmap.data = {"data-config.json": json.dumps(datashim, indent=4)}
        api.create_namespaced_config_map(namespace, configmap)
    else:
        patch = {"data": {"data-config.json": json.dumps(datashim, indent=4)}}
        api.patch_namespaced_config_map(name, namespace, patch)


def temp_update_manifest_cameras(manifest_cameras, node_cameras):
    for _, camera in node_cameras.iterrows():
        # get the camera that matches with the orientation and is configured
        orientation = camera["orientation"]
        for m_camera in manifest_cameras:
            if orientation in m_camera.name:
                logging.info(f"the camera for {orientation} found. datashim will be updated")
                m_camera.set_state("registered")
                m_camera.url = camera["stream"]
                m_camera.serial_no = camera["mac"]
    return manifest_cameras


def update_datashim_for_camera(datashim, camera):
    for entry in datashim:
        try:
            if entry["match"]["id"] == camera.name:
                entry["handler"]["args"]["url"] = camera.url
                return datashim
        except KeyError:
            pass
    datashim.append(
        {
            "handler": {"args": {"url": camera.url}, "type": "video"},
            "match": {
                "id": camera.name,
                "orientation": camera.name,
                "resolution": "800x600",
                "type": "camera/video",
            },
            "name": camera.name,
        }
    )
    return datashim


def drop_camera_from_datashim(datashim, camera):
    for entry in datashim:
        try:
            if entry["match"]["id"] == camera.name:
                datashim.remove(entry)
        except KeyError:
            continue
    return datashim


def update_datashim(manifest_cameras:list):
    """Updates the datashim Kubernetes Configmap based on camera status

    This updates the datashim on "ses" namespace as well to affect plugins running in
    the namespace.

    Keyword Arguments:
    --------
    `manifest_cameras` -- a list of utils.CameraObject that are configured
    """
    # NOTE: Debug messages from Kubernetes client may contain sensitive information
    #       and thus disable debugging flag
    logger_level = logging.getLogger().level
    logging.getLogger().setLevel(logging.INFO)
    kubernetes.config.load_incluster_config()
    api = kubernetes.client.CoreV1Api()
    configmap = get_configmap(api, "waggle-data-config")
    if configmap == None:
        logging.warning("not found waggle-data-config in default namespace")
        datashim = []
    else:
        datashim = json.loads(configmap.data["data-config.json"])
    for camera in manifest_cameras:
        if camera.state != "registered":
            logging.info(f"dropping datashim for {camera.name}...")
            datashim = drop_camera_from_datashim(datashim, camera)
            continue
        logging.info(f"updating datashim for {camera.name}...")
        datashim = update_datashim_for_camera(datashim, camera)
    set_datashim(api, datashim, "waggle-data-config")
    namespaces_to_apply = ["ses", "dev"]
    existing_namespaces = api.list_namespace()
    for namespace in existing_namespaces.items:
        if namespace.metadata.name in namespaces_to_apply:
            logging.info(f"applying datashim to {namespace.metadata.name}...")
            set_datashim(api, datashim, "waggle-data-config", namespace=namespace.metadata.name)
    logging.getLogger().setLevel(logger_level)
    return manifest_cameras


def run():
    logging.info(f'get node manifest from {WAGGLE_MANIFEST_V2_PATH}')
    if not os.path.exists(WAGGLE_MANIFEST_V2_PATH):
        logging.error(f"no {WAGGLE_MANIFEST_V2_PATH} found. Exiting.")
        return 1
    camera_matchers = utils.create_object_matchers(TARGET_CAMERA_REGEX)
    manifest_cameras = get_cameras_from_manifest(WAGGLE_MANIFEST_V2_PATH, camera_matchers)
    if len(manifest_cameras) < 1:
        logging.info(f'no matching camera found. no further action will be taken.')
        return 0
    else:
        logging.info(f"found {len(manifest_cameras)} cameras from manifest")

    logging.info('fetching network switch credential.')
    if not all(get_networkswitch_credential()):
        logging.error("could not get network switch credential. Exiting...")
        return 1

    logging.info('fetching camera user credential.')
    if not all(get_camera_credential()):
        logging.error("could not get camera credentials. Exiting...")
        return 1

    logging.info("scanning cameras using nmap...")
    cameras_from_nmap = get_cameras_from_nmap()
    logging.info("sleep 3 seconds for the switch to update its network table")
    time.sleep(3)
    if utils.does_networkswitch_exist(WAGGLE_MANIFEST_V2_PATH):
        node_cameras = get_ports_from_switch(cameras_from_nmap)
        for _, camera in node_cameras.iterrows():
            logging.info(f'camera found from the network: {camera.mac} at {camera.ip}')
    else:
        node_cameras = cameras_from_nmap
        logging.info('network switch does not exist in manifest. skip getting information on switch port for cameras')

    # logging.info('Scanning cameras using network switch...')
    # cameras_from_switch = get_cameras_from_switch()
    # logging.debug(f'Cameras found from networkswitch: {cameras_from_switch}')

    logging.info("updating or provision Hanwha cameras...")
    node_cameras = update_hanwha_camera(manifest_cameras, node_cameras)
    logging.debug(f"updated state of cameras: {node_cameras}")

    # TODO(Yongho): this uses hardcoded names. We should use camera's serial_no to match between
    # the manifest cameras and node cameras
    manifest_cameras = temp_update_manifest_cameras(manifest_cameras, node_cameras)
    for m_c in manifest_cameras:
        if m_c.url != "" and m_c.state != "registered":
            logging.info(f'we will register {m_c.name} as it has its url {m_c.url} already set')
            m_c.set_state("registered")
    cameras = update_datashim(manifest_cameras)
    return 0


logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s %(message)s", datefmt="%Y/%m/%d %H:%M:%S"
)

if __name__ == "__main__":
    exit(run())
