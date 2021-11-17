import os
import logging
import json
import time

from hanwha_camera_client import HanwhaCameraClient


def get_camera_credential():
    return os.getenv('WAGGLE_CAMERA_ADMIN'), os.getenv('WAGGLE_CAMERA_ADMIN_PASSWORD'), os.getenv('WAGGLE_CAMERA_USER'), os.getenv('WAGGLE_CAMERA_USER_PASSWORD')


def configure_camera(ip_address, orientation, out_dir='/tmp'):
    """ Configure Hanwha camera

    Configures Hanwha camera in the following ways,

    - Set the meta information into the camera firmware

    - Set system time using host time

    - Create waggle user if not exists

    - Create device_information.json

    - Back up the current configuration

    - Take a snapshot

    Keyword Arguments:
    --------
    `ip_address` -- IP address of the camera

    `mac_address` -- (Optional) MAC address of the camera

    `admin_password` -- if the camera is in factory default state this password will be used as admin password

    `waggle_user_password` -- The waggle user is set with this password

    `out_dir` -- Directory path where camera configuration back up and a snapshot will be stored

    Returns:
    --------
    `success` -- boolean indicating whether the configuration succeeded
    """
    admin, admin_password, user, user_password = get_camera_credential()
    with HanwhaCameraClient(host=f'http://{ip_address}', user=admin, password=admin_password) as client:
        logging.info(f'{ip_address}: Updating device information')
        ret = client.update_device_information(description=f'{ip_address}', location=f'{orientation}')
        if ret == False:
            logging.error(f'{ip_address}: Failed to set device information')
            return False

        logging.info(f'{ip_address}: Updating system time')
        ret = client.update_system_time_using_host_time()
        if ret == False:
            logging.error(f'{ip_address}: Failed to set system time')
            return False

        logging.info(f'{ip_address}: Getting waggle user')
        ret, user_info = client.get_user('waggle')
        if ret == False:
            logging.error(f'{ip_address}: Failed to retreive waggle user information')
            return False
        if user_info == None:
            logging.info(f'{ip_address}: User waggle not exist. Creating.')
            ret = client.remove_user(user_index=1)
            if ret == False:
                logging.error(f'{ip_address}: Failed to remove user 1')
                return False
            ret = client.add_user(user_index=1, user_ID=user, plain_password=user_password, enable=True)
            if ret == False:
                logging.error(f'{ip_address}: Failed to create waggle user')
                return False
        else:
            logging.info(f'{ip_address}: User waggle already exists. Skipping. ')
        
        logging.info(f'{ip_address}: Creating device info under {out_dir}')
        ret, device_info = client.get_device_information()
        if ret == False:
            logging.error(f'{ip_address}: Failed to get device information')
            return False
        with open(os.path.join(out_dir, f'device_info_{ip_address}.json'), 'w') as file:
            json.dump(device_info, file, indent=4)
        
        logging.info(f'{ip_address}: Backing up the current camera configuration')
        ret = client.backup_configuration(os.path.join(out_dir, f'configuration_{ip_address}.backup'))
        if ret == False:
            logging.error(f'{ip_address}: Failed to save camera configuration')

        logging.info(f'{ip_address}: Taking a snapshot')
        ret = client.take_snapshot(os.path.join(out_dir, f'snapshot_{ip_address}.jpg'))
        if ret == False:
            logging.error(f'{ip_address}: Failed to take a snapshot')
    return True


def initialize_camera(camera):
    admin, admin_password, _, _ = get_camera_credential()
    with HanwhaCameraClient(host=f'http://{camera.ip}', user=admin, password=admin_password) as client:
        ret, initialized, _ = client.is_factory_admin_password_set()
        if ret == False:
            logging.error(f'{camera.ip}: Failed to query if the camera is in factory default state')
            return False
        if initialized:
            logging.info(f'{camera.ip}: Already initialized')
            return True
        logging.info(f'{camera.ip} is not initialized. Initializing...')
        ret = client.set_factory_admin_password(admin_password)
        if ret == False:
            logging.error(f'{camera.ip}: Failed to set admin password in factory default state')
            return False
    logging.info(f'Waiting for 5 seconds to see {camera.ip} come back')
    time.sleep(5)
    logging.info(f'{camera.ip} is being configured...')
    return configure_camera(ip_address=camera.ip, orientation=camera.name)


def update_camera_status(cameras):
    """ Updates status of cameras

    Keyword Arguments:
    --------
    `cameras` -- a pandas DataFrame containing list of cameras to be updated

    Returns:
    --------
    `cameras` -- a pandas DataFrame with updated cameras
    """
    admin, admin_password, _, _ = get_camera_credential()
    for _, camera in cameras.iterrows():
        logging.info(f'Updating status of camera {camera.ip} ({camera.mac})')
        if initialize_camera(camera) == False:
            logging.error(f'{camera.ip}: Failed to initialize the camera. Skipping...')
            continue
        with HanwhaCameraClient(host=f'http://{camera.ip}', user=admin, password=admin_password) as client:
            ret, device_info = client.get_device_information()
            if ret == False:
                logging.error(f'{camera.ip}: Failed to get device information. Skipping...')
                continue
            logging.debug(json.dumps(device_info, indent=4))
            camera_ip = device_info['DeviceDescription']
            camera_orientation = device_info['DeviceLocation']
            camera_model = device_info['Model']
            camera_mac = device_info['ConnectedMACAddress'].lower()
            if camera.ip != camera_ip:
                logging.warning(f'{camera_ip} does not match with {camera.ip}')
            ret, stream = client.get_rtsp_stream_uri()
            if ret == False:
                logging.error(f'{camera.ip}: Failed to get RTSP stream URI. Skipping...')
                continue
            camera.orientation = camera_orientation
            camera.model = camera_model
            camera.mac = camera_mac
            camera.stream = stream
            camera.state = 'configured'
    return cameras