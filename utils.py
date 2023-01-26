import json

import pandas




def create_dataframe():
    """Returns a dataframe representing the camera configuration table

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
    return pandas.DataFrame(
        [], columns=["ip", "mac", "orientation", "port", "model", "stream", "state", "note"]
    )


def create_row(data, name=None):
    return pandas.Series(data, name=name)


def get_cameras_from_manifest(node_manifest_path, target_cameras):
    """Creates a list of camera objects based on node-manifest-v2.json

    Keyword Arguments:
    --------
    `node_manifest_path` -- a path to node-manifest-v2.json

    Returns:
    --------
    `cameras` -- a pandas.DataFrame containing cameras recognized from node-manifest-v2.json
    """
    cameras = create_dataframe()
    with open(node_manifest_path, "r") as file:
        manifest = json.load(file)
    # this assumes all cameras in the manifest have the string "camera" in the "name"
    m_cameras = [s for s in manifest["sensors"] if s["hardware"]["hw_model"] in CAMERA_MODELS]
    for m_cam in m_cameras:
        data = {"state": "unknown", "model": m_cam["hardware"]["hw_model"]}
        # this assumes the "name" of the camera is "<orientation>_camera" (ex. "top_camera")
        orientation = m_cam["name"].split("_")[0]
        cameras = cameras.append(create_row(data, name=orientation))
    return cameras


def get_camera(node_ma)