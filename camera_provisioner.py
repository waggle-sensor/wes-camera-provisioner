#!/usr/bin/env python3

import json
import logging
import os
import time

import kubernetes

from hanwhacamera import get_camera_credential, update_camera_status
from networkswitch import (
    get_cameras_from_nmap,
    get_networkswitch_credential,
    get_ports_from_switch,
)
from utils import load_node_manifest


def print_logic():
    print(
        """
A. get list of cameras from node_manifest.json

B. get list of cameras currently recognized from Unifi switch

C. check each camera in B. if the camera needs a provisioning

D. provision cameras that need it

Cameras in factory default state
|
|
States:
unknown -- the state of camera is unknown

error -- there is an error on the camera. Check the note column to get more information

factory -- the camera is in factory default state

configured -- the camera is configured using node_manifest.json
"""
    )


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


def update_manifest(manifest, cameras):
    for orientation, camera in manifest.iterrows():
        # get the camera that matches with the orientation and is configured
        camera_found = cameras.loc[
            (cameras.orientation == orientation) & cameras.state.str.contains("configured")
        ]
        if len(camera_found) < 1:
            logging.error(
                f"No camera is found for {orientation}. Corresponding datashim will be removed"
            )
            camera.orientation = orientation
            continue
        the_camera = camera_found.iloc[0]
        if the_camera.model.lower() != camera.model.lower():
            logging.error(
                f"{the_camera.model} is wrong for {orientation}. It should have been {camera.model}. datashim will be removed"
            )
            continue
        logging.info(f"the camera for {orientation} found. datashim will be updated")
        the_camera = the_camera.rename(orientation)
        the_camera.state = "registered"
        manifest.loc[orientation].update(the_camera)
    return manifest


def update_datashim_for_camera(datashim, camera):
    for entry in datashim:
        try:
            if entry["match"]["id"] == camera.orientation:
                entry["handler"]["args"]["url"] = camera.stream
                return datashim
        except KeyError:
            pass
    datashim.append(
        {
            "handler": {"args": {"url": camera.stream}, "type": "video"},
            "match": {
                "id": camera.orientation,
                "orientation": camera.orientation,
                "resolution": "800x600",
                "type": "camera/video",
            },
            "name": camera.ip,
        }
    )
    return datashim


def drop_camera_from_datashim(datashim, camera):
    for entry in datashim:
        try:
            if entry["match"]["id"] == camera.orientation:
                datashim.remove(entry)
        except KeyError:
            continue
    return datashim


def update_datashim(cameras):
    """Updates the datashim Kubernetes Configmap based on camera status

    This updates the datashim on "ses" namespace as well to affect plugins running in
    the namespace.

    Keyword Arguments:
    --------
    `cameras` -- a pandas Dataframe with cameras configured/notconfigured
    """
    # NOTE: Debug messages from Kubernetes client may contain sensitive information
    #       and thus disable debugging flag
    logger_level = logging.getLogger().level
    logging.getLogger().setLevel(logging.INFO)
    kubernetes.config.load_incluster_config()
    api = kubernetes.client.CoreV1Api()
    configmap = get_configmap(api, "waggle-data-config")
    if configmap == None:
        logging.warning("Not found waggle-data-config in default namespace")
        datashim = []
    else:
        datashim = json.loads(configmap.data["data-config.json"])
    for _, camera in cameras.iterrows():
        if camera.state != "registered":
            logging.info(f"Dropping datashim for {camera.orientation}...")
            datashim = drop_camera_from_datashim(datashim, camera)
            continue
        logging.info(f"Updating datashim for {camera.orientation}...")
        datashim = update_datashim_for_camera(datashim, camera)
    set_datashim(api, datashim, "waggle-data-config")
    namespaces_to_apply = ["ses", "dev"]
    existing_namespaces = api.list_namespace()
    for namespace in existing_namespaces.items:
        if namespace.metadata.name in namespaces_to_apply:
            logging.info(f"applygin datashim to {namespace.metadata.name}...")
            set_datashim(api, datashim, "waggle-data-config", namespace=namespace.metadata.name)
    logging.getLogger().setLevel(logger_level)
    return cameras


def run():
    waggle_path = "/etc/waggle"
    node_manifest_path = os.path.join(waggle_path, "node_manifest.json")
    if not os.path.exists(node_manifest_path):
        logging.error(f"No {node_manifest_path} found. Exiting...")
        return 1
    cameras = load_node_manifest(node_manifest_path)
    logging.debug(f"Cameras found from node_manifest: {cameras}")

    if not all(get_networkswitch_credential()):
        logging.error("Could not get network switch credential. Exiting...")
        return 1

    if not all(get_camera_credential()):
        logging.error("Could not get camera credentials. Exiting...")
        return 1

    logging.info("Scanning cameras using nmap...")
    cameras_from_nmap = get_cameras_from_nmap()
    logging.info("Sleep 3 seconds for the switch to update its network table")
    time.sleep(3)
    cameras_from_nmap = get_ports_from_switch(cameras_from_nmap)
    logging.debug(f"Cameras found from the network: {cameras_from_nmap}")

    # logging.info('Scanning cameras using network switch...')
    # cameras_from_switch = get_cameras_from_switch()
    # logging.debug(f'Cameras found from networkswitch: {cameras_from_switch}')

    logging.info("Updating recognized cameras...")
    cameras_from_switch = update_camera_status(cameras_from_nmap)
    logging.debug(f"Updated state of cameras: {cameras_from_switch}")
    logging.debug(f"manifest: {cameras}")
    cameras = update_manifest(cameras, cameras_from_switch)
    cameras = update_datashim(cameras)
    return 0


logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s %(message)s", datefmt="%Y/%m/%d %H:%M:%S"
)

if __name__ == "__main__":
    exit(run())
