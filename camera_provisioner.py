#!/usr/bin/env python3

import os
import json
import logging

import kubernetes

from hanwhacamera import update_camera_status, get_camera_credential
from networkswitch import get_ports_from_switch, get_cameras_from_nmap, get_networkswitch_credential
from utils import load_node_manifest


def print_logic():
    print("""
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
""")


def get_current_datashim(api, name='waggle-data-config'):
    # NOTE: Debug messages from Kubernetes client may contain sensitive information
    #       and thus disable debugging flag
    logger_level = logging.getLogger().level
    logging.getLogger().setLevel(logging.INFO)
    """ Returns waggle datashim"""
    configmaps = api.list_namespaced_config_map('default')
    logging.getLogger().setLevel(logger_level)
    for configmap in configmaps.items:
        if name in configmap.metadata.name:
            return json.loads(configmap.data['data-config.json'])
    return []


def set_datashim(api, datashim, name='waggle-data-config', namespace='default'):
    # NOTE: Debug messages from Kubernetes client may contain sensitive information
    #       and thus disable debugging flag
    logger_level = logging.getLogger().level
    logging.getLogger().setLevel(logging.INFO)
    patch={'data': {'data-config.json': json.dumps(datashim, indent=4)}}
    api.patch_namespaced_config_map(name, namespace, patch)
    logging.getLogger().setLevel(logger_level)


def update_manifest(manifest, cameras):
    for orientation, camera in manifest.iterrows():
        camera_found = cameras.loc[cameras.orientation == orientation]
        if len(camera_found) < 1:
            logging.error(f'No camera is found for {orientation}. Corresponding datashim will be removed')
            camera.orientation = orientation
            continue
        the_camera = camera_found.iloc[0]
        if the_camera.model.lower() != camera.model.lower():
            logging.error(f'{the_camera.model} is wrong for {orientation}. It should have been {camera.model}. datashim will be removed')
            continue
        logging.info(f'the camera for {orientation} found. datashim will be updated')
        the_camera = the_camera.rename(orientation)
        the_camera.state = 'registered'
        manifest.loc[orientation].update(the_camera)
    return manifest


def update_datashim_for_camera(datashim, camera):
    for entry in datashim:
        try:
            if entry['match']['id'] == camera.orientation:
                entry['handler']['args']['url'] = camera.stream
                return datashim
        except KeyError:
            pass
    datashim.append({
        "handler": {
            "args": {
                "url": camera.stream
            },
            "type": "video"
        },
        "match": {
            "id": camera.orientation,
            "orientation": camera.orientation,
            "resolution": "800x600",
            "type": "camera/video"
        },
        "name": camera.ip
    })
    return datashim


def drop_camera_from_datashim(datashim, camera):
    for entry in datashim:
        try:
            if entry['match']['id'] == camera.orientation:
                datashim.remove(entry)
        except KeyError:
            continue
    return datashim


def update_datashim(cameras):
    """ 
    Keyword Arguments:
    --------
    `cameras` -- a pandas Dataframe with cameras configured/notconfigured
    """
    kubernetes.config.load_incluster_config()
    api = kubernetes.client.CoreV1Api()
    datashim = get_current_datashim(api)
    for orientation, camera in cameras.iterrows():
        if camera.state != 'registered':
            logging.info(f'Dropping datashim for {camera.orientation}...')
            datashim = drop_camera_from_datashim(datashim, camera)
            continue
        logging.info(f'Updating datashim for {camera.orientation}...')
        datashim = update_datashim_for_camera(datashim, camera)
    set_datashim(api, datashim)
    return cameras


def run():
    waggle_path = '/etc/waggle'
    node_manifest_path = os.path.join(waggle_path, 'node_manifest.json')
    if not os.path.exists(node_manifest_path):
        logging.error(f'No {node_manifest_path} found. Exiting...')
        return 1
    cameras = load_node_manifest(node_manifest_path)
    logging.debug(f'Cameras found from node_manifest: {cameras}')

    if not all(get_networkswitch_credential()):
        logging.error('Could not get network switch credential. Exiting...')
        return 1
    
    if not all(get_camera_credential()):
        logging.error('Could not get camera credentials. Exiting...')
        return 1

    logging.info("Scanning cameras using nmap...")
    cameras_from_nmap = get_cameras_from_nmap()
    cameras_from_nmap = get_ports_from_switch(cameras_from_nmap)
    logging.debug(f'Cameras found from the network: {cameras_from_nmap}')

    # logging.info('Scanning cameras using network switch...')
    # cameras_from_switch = get_cameras_from_switch()
    # logging.debug(f'Cameras found from networkswitch: {cameras_from_switch}')

    logging.info('Updating recognized cameras...')
    cameras_from_switch = update_camera_status(cameras_from_nmap)
    logging.debug(f'Updated state of cameras: {cameras_from_switch}')
    logging.debug(f'manifest: {cameras}')
    cameras = update_manifest(cameras, cameras_from_switch)
    cameras = update_datashim(cameras)
    return 0

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(message)s',
    datefmt='%Y/%m/%d %H:%M:%S')

if __name__ == '__main__':
    exit(run())
