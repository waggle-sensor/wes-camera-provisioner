import re
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


def load_node_manifest(node_manifest_path):
    """Creates a list of camera objects based on node-manifest-v2.json

    Keyword Arguments:
    --------
    `node_manifest_path` -- a path to node-manifest-v2.json

    Returns:
    --------
    `cameras` -- a pandas.DataFrame containing cameras recognized from node-manifest-v2.json
    """
    with open(node_manifest_path, "r") as file:
        return json.load(file)


def does_networkswitch_exist(node_manifest_path):
    manifest = load_node_manifest(node_manifest_path)
    resources = manifest.get("resources", None)
    if resources is None:
        return False
    switch_matcher = ObjectMatcher("unifi switch", "UniFi", "ES-8-150W")
    for r in resources:
        h = r.get("hardware", None)
        if h is None:
            return False
        # get manufacturer and hardware model of camera from the manifest
        manufacturer = h.get("manufacturer", "")
        hw_model = h.get("hw_model", "")
        if switch_matcher.match(manufacturer, hw_model):
            return True
    return False


class CameraObject(object):
    def __init__(self, name, manufacturer, hw_model):
        self.name = name
        self.manufacturer = manufacturer
        self.hw_model = hw_model
        self.state = ""
        self.macaddress = ""
        self.serial_no = ""
        self.url = ""

    def set_state(self, new_state):
        self.state = new_state


class ObjectMatcher(object):
    def __init__(self, description="", manufacturer="", hw_model=[]):
        self.description = description
        self.manufacturer = manufacturer
        self.hw_model = hw_model

    # returns True/False based on if given manufacturer matches
    def match_manufacturer(self, manufacturer:str) ->bool:
        if self.manufacturer == "" or self.manufacturer == "*":
            return True
        match = re.search(self.manufacturer, manufacturer, flags=re.IGNORECASE)
        if match is not None:
            return True
        else:
            return False

    # returns True/False based on if given model is in the list
    # if the list has "*", then it always returns True
    def match_hw_model(self, hw_model:str) ->bool:
        if "*" in self.hw_model:
            return True
        expr = "(" + ")|(".join(self.hw_model) + ")"
        matches = re.search(expr, hw_model, flags=re.IGNORECASE)
        if matches is not None:
            return True
        return False

    # returns True/False based on if given manufacturer and hw_model match
    # with this camera object
    def match(self, manufacturer:str, hw_model:str) ->bool:
        matched = []
        matched.append(self.match_manufacturer(manufacturer))
        matched.append(self.match_hw_model(hw_model))
        return all(matched)


def create_object_matchers(matchers:dict):
    objects = []
    for m in matchers:
        d = m.get("description", "")
        m = m.get("manufacturer", "")
        hw = m.get("hw_model", "")
        objects.append(ObjectMatcher(d, m, hw))
    return objects
