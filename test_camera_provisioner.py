import unittest
import json
from camera_provisioner import get_cameras_from_manifest
import utils

class TestFindingCameraFromManifest(unittest.TestCase):
    test_manifest = """
{"vsn":"V002","name":"00004CD98FC67B75","gps_lat":39.09564,"gps_lon":-77.98322,"tags":[],"computes":[{"name":"sbcore","serial_no":"4CD98FC67B75","zone":"core","hardware":{"hardware":"dell-xr2","hw_model":"PowerEdge XR2","hw_version":"","sw_version":"","manufacturer":"Dell","datasheet":"https://www.dell.com/en-us/shop/productdetailstxn/poweredge-xr2","capabilities":["gpu","cuda110","amd64"],"cpu":"16000","cpu_ram":"32768","gpu_ram":"16384","shared_ram":true}}],"sensors":[{"name":"aquatic/stream-gauge camera","scope":"global","labels":[],"serial_no":"NEON.D02.LEWI.DP1.20002","uri":"http://10.102.144.40/nph-mjpeg.cgi","hardware":{"hardware":"stardot netcam","hw_model":"Stardot NetCam CS CAM-SEC5IR-B","hw_version":"","sw_version":"","manufacturer":"stardot","datasheet":"http://stardot-tech.com/netcamsc/index.html","capabilities":[]}}],"resources":[]}
"""
    TARGET_CAMERA_REGEX = [
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
    ]
    def test_find_camera_from_manifest(self):
        camera_matchers = utils.create_camera_object_matchers(self.TARGET_CAMERA_REGEX)
        manifest_cameras = get_cameras_from_manifest("V002", camera_matchers)
        print(manifest_cameras)

if __name__ == '__main__':
    unittest.main()