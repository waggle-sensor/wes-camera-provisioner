import os
import subprocess
import logging
import re

from utils import create_dataframe, create_row
from unifi_switch_client import UnifiSwitchClient


# Unifi switch port mapping into camera orientations
# --------
# port 1: R = Right camera or S = Shield
# port 2: T = top
# port 3: n/a
# port 4: N = node controller (NX core)
# port 5: E = Edge processor (NX agent)
# port 6: n/a
# port 7: B = Bottom
# port 8: L = Left
mapping = {
    '0/1': 'right',
    '0/2': 'top',
    '0/3': 'port3',
    '0/4': 'nxcore',
    '0/5': 'nxagent',
    '0/6': 'port6',
    '0/7': 'bottom',
    '0/8': 'left',
}


def get_networkswitch_credential():
    return os.getenv('WAGGLE_SWITCH_ADDRESS', '10.31.81.2'), os.getenv('WAGGLE_SWITCH_USER'), os.getenv('WAGGLE_SWITCH_PASSWORD')


def get_cameras_from_switch(skip_pinging=False):
    """ Returns updated list of cameras from Unifi edgeswitch 8
    
    Because cameras may go into sleep the function pings them one by one, which takes time, before getting the camera table

    Keyword Arguments:
    --------
    `address` -- an HTTPS endpoint of the switch

    `username` -- username of the switch

    `password` -- password of the switch

    `skip_pinging` -- does not ping each camera to get Mac Table; should not be set to True unless the cameras are active

    Returns:
    --------
    `cameras` -- a pandas.Dataframe with cameras recognized from switch
    """
    address, username, password = get_networkswitch_credential()
    cameras = create_dataframe()
    with UnifiSwitchClient(host=f'https://{address}', username=username, password=password) as client:
        if skip_pinging == False:
            for i in range(10, 20):
                _, _ = client.ping(f'10.31.81.{i}', trial=1)
        ret, table = client.get_mac_table()
        if ret is False:
            logging.error('Failed to retreive cameras from the switch')
            return cameras
    for camera in table:
        ip = camera['address']
        # Accept only IPs betwen 10.31.81.10 - 10.31.81.20 for cameras
        if not re.search('10.31.81.(1[0-9]|20)$', ip):
            continue
        port = camera['port']['id']
        data = {
            'ip': ip,
            'mac': camera['mac'].lower(),
            'orientation': mapping[port],
            'port': port
        }
        orientation = mapping[port]

        cameras = cameras.append(create_row(data, name=orientation))
    return cameras


def get_ports_from_switch(cameras):
    address, username, password = get_networkswitch_credential()
    with UnifiSwitchClient(host=f'https://{address}', username=username, password=password) as client:
        ret, table = client.get_mac_table()
        if ret == False:
            logging.error("Failed to get mac table from network switch")
            return cameras
    for row in table:
        mac = row['mac']
        port = row['port']['id']
        cameras.loc[cameras.mac == mac, 'orientation'] = mapping[port]
    return cameras

def get_cameras_from_nmap():
    """ Returns a list of cameras from nmap over 10.31.81.10-20

    Execution of nmap returns MAC address of recognized devices when the network privilege
    is granted. Please make sure the privilege is given when calling.

    WARNING: This function does not work if the IP range isn't properly set.
    For example, it will catch 10.31.81.114 as camera because of the regex rule
    in the function

    Expected output would be,
    ```
    Starting Nmap 7.80 ( https://nmap.org ) at 2022-01-24 17:36 UTC
    Nmap scan report for XNV-8081Z-E43022248D35 (10.31.81.10)
    Host is up (0.0011s latency).
    MAC Address: E4:30:22:24:8D:35 (Hanwha Techwin Security Vietnam)
    Nmap scan report for XNV-8081Z-E430222653AB (10.31.81.16)
    Host is up (0.0011s latency).
    MAC Address: E4:30:22:26:53:AB (Hanwha Techwin Security Vietnam)
    Nmap scan report for XNF-8010RV-E43022239E8E (10.31.81.17)
    Host is up (0.0011s latency).
    MAC Address: E4:30:22:23:9E:8E (Hanwha Techwin Security Vietnam)
    Nmap done: 11 IP addresses (3 hosts up) scanned in 0.50 seconds
    ```

    Returns:
    --------
    `cameras` -- a pandas.Dataframe with cameras recognized from nmap
    """
    cameras = create_dataframe()
    output = subprocess.check_output(('nmap', '-sP', '10.31.81.10-20'))
    output_newlined = output.decode().strip().split('\n')
    ret = []
    found_ip = None
    for line in output_newlined:
        found = re.search('10.31.81.[0-9]{2}', line)
        if found:
            if found_ip is not None:
                data = {
                    'ip': found_ip['ip'],
                    'mac': found_ip['mac'].lower()
                }
                cameras = cameras.append(create_row(data, name='unknown'))
            found_ip = {'ip': found.string[found.start():found.end()]}
            continue
        found = re.search('(?:[0-9a-zA-Z]:?){12}', line)
        if found:
            if found_ip is not None:
                found_ip.update({'mac': found.string[found.start():found.end()]})
    if found_ip is not None:
        data = {
            'ip': found_ip['ip'],
            'mac': found_ip['mac'].lower()
        }
        cameras = cameras.append(create_row(data, name='unknown'))
    return cameras