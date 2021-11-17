import json
import pandas


def create_dataframe():
    """ Returns a dataframe representing the camera configuration table

    Columns:
    --------
    `ip` -- IP address of camera

    `mac` -- MAC address of camera

    `orientation` -- the intended orientation; one of top, bottom, left, and right

    `port` -- switch port being used for camera; one of top, bottom, left, and right

    `model` -- model of camera

    `stream` -- a stream URI for live camera feed

    `state` -- the current state of camera; one of unknown, untagged, tagged, registered

    `note` -- a note explaining the state

    Returns:
    --------
    `cameras` -- a pandas.DataFrame containing empty data with the columns
    """
    return pandas.DataFrame([], columns=['ip', 'mac', 'orientation', 'port', 'model', 'stream', 'state', 'note'])


def create_row(data, name=None):
    return pandas.Series(data, name=name)


def load_node_manifest(node_manifest_path):
    """ Creates a list of camera objects based on node_manifest.json

    Keyword Arguments:
    --------
    `node_manifest_path` -- a path to node_manifest.json

    Returns:
    --------
    `cameras` -- a pandas.DataFrame containing cameras recognized from node_manifest.json
    """
    cameras = create_dataframe()
    with open(node_manifest_path, 'r') as file:
        manifest = json.load(file)
    for camera in manifest['cameras']:
        if camera['present'] == True:
            data = { 'state': 'unknown' }
            if 'model' in camera and camera['model'] != "":
                data.update({'model': camera['model']})
            cameras = cameras.append(create_row(data, name=camera['orientation']))
    return cameras
