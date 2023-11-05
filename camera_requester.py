import logging
import requests


logger = logging.getLogger(__name__)

port_for_cameras = 8080


def null_handler(s):
    pass


def handle_request_call(request_call, full_url, error_prompt):
    logger.debug(f"Trying to reach {full_url}...")
    try:
        response = request_call()
    except requests.exceptions.Timeout:
        logger.error(f"Connection to {full_url} timed out!")
        error_prompt(f"Connection to {full_url} timed out!")
        return None

    except Exception as e:
        logger.error(f"Unknown exception: {e}")
        error_prompt(f"Unknown exception when connecting to {full_url}: {e}")
        return None

    logger.debug(f"Acquired response from {full_url}")
    if response.status_code != 200:
        if response.status_code == 422:
            print(response.content)
        logger.error(f"HTTP error encountered while getting from {full_url}: "
                     f"status code={response.status_code}")
        error_prompt(f"HTTP error encountered while getting from {full_url}:\n"
                     f"status code={response.status_code}")
        return None
    return response


def standalone_get_request(url, error_prompt=null_handler):
    def request_call():
        return requests.get(url, timeout=5)

    return handle_request_call(request_call, url, error_prompt)


def standalone_post_request(url, headers, data, error_prompt=null_handler):
    logger.debug(f"Trying to POST on {url}")

    def request_call():
        return requests.post(url, headers=headers, json=data, timeout=5)

    return handle_request_call(request_call, url, error_prompt)


class CameraRequester:
    def __init__(self, ip, camera_index, error_prompt):
        self._ip = ip
        self._camera_index = camera_index
        self._error_prompt = error_prompt

    def _get_request(self, full_url):
        return standalone_get_request(full_url, self._error_prompt)

    def _regular_get_url(self, what_to_get):
        url = f"http://{self._ip}:{port_for_cameras}/camera/{self._camera_index}/{what_to_get}"
        logger.debug(f"Using URL for next request: {url}")
        return self._get_request(url)

    def _regular_set_url(self, what_to_set, value):
        url = f"http://{self._ip}:{port_for_cameras}/camera/{self._camera_index}/{what_to_set}"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {"value": str(value)}
        logger.debug(f"Sending POST with data: {data}")
        response = standalone_post_request(url, headers, data, self._error_prompt)
        logger.debug(f"Acquired response from POST: {response.content}")
        return response

    def _get_pair_success_and_value(self, endpoint):
        response = self._regular_get_url(endpoint)
        if response is None:
            return False, None
        try:
            value = response.json()["value"]
        except Exception as e:
            logger.error(e)
            return False, None
        return True, value

    def custom_request(self, url):
        return self._get_request(url)

    def start_capturing(self):
        return self._regular_set_url("set_status", "CAPTURE")

    def stop_capturing(self):
        return self._regular_set_url("set_status", "IDLE")

    def set_binning(self, value):
        url = f"http://{self._ip}:{port_for_cameras}/camera/{self._camera_index}/set_binx"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {"value": str(value)}
        return standalone_post_request(url, headers, data, self._error_prompt)

    def set_format(self, value):
        return self._regular_set_url("set_readoutmode_str", value)

    def set_gain(self, value):
        return self._regular_set_url("set_gain", value)

    def get_gain(self):
        return self._get_pair_success_and_value("get_gain")

    def get_offset(self):
        return self._get_pair_success_and_value("get_offset")

    def set_offset(self, value):
        return self._regular_set_url("set_offset", value)

    def get_formats(self):
        return self._get_pair_success_and_value("get_readoutmodes")

    def get_last_image(self, send_as_jpg: bool):
        url = f"http://{self._ip}:{port_for_cameras}/camera/{self._camera_index}/get_last_image"
        logger.debug(f"Trying to get last image from {url}")

        def request_call():
            return requests.get(url, params={"format": "jpg" if send_as_jpg else "raw"}, timeout=5)

        return handle_request_call(request_call, url, self._error_prompt)

    def get_current_format(self):
        return self._get_pair_success_and_value("get_readoutmode_str")

    def get_exposure(self):
        return self._get_pair_success_and_value("get_exposure")

    def get_temp_and_status(self):
        return self._get_pair_success_and_value("get_tempandstatus")

    def set_exposure(self, value):
        return self._regular_set_url("set_exposure", value)

    def get_temperature(self):
        return self._get_pair_success_and_value("get_ccdtemperature")

    def get_cooler_on(self):
        return self._get_pair_success_and_value("get_cooleron")

    def get_can_turn_on_cooler(self):
        return self._get_pair_success_and_value("get_cansetcooleron")

    def get_can_set_temp(self):
        return self._get_pair_success_and_value("get_cansetccdtemperature")

    def get_set_temp(self):
        return self._get_pair_success_and_value("get_setccdtemperature")

    def set_set_temp(self, value: int):
        return self._regular_set_url("set_setccdtemperature", value)

    def set_cooler_on(self, value: bool):
        return self._regular_set_url("set_cooleron", bool(value))

    def get_resolution(self):
        logger.debug(f"Trying to get camera resolution...")
        logger.debug(f"X...")

        is_okx, numx = self._get_pair_success_and_value("get_numx")
        is_oky, numy = self._get_pair_success_and_value("get_numy")

        if not is_oky or not is_okx:
            return False, None

        xres = int(numx)
        yres = int(numy)

        logger.debug(f"Resolution = {xres}x{yres}")
        return True, (xres, yres)

    def get_possible_binning(self):
        is_ok, maxbin = self._get_pair_success_and_value("get_maxbinx")
        if not is_ok:
            return []
        logger.debug(f"Max possible bin is {maxbin}")
        return list(range(1, maxbin+1))
