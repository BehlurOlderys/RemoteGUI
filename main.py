from PyQt5.QtWidgets import QInputDialog, QErrorMessage, QLabel, QLineEdit, QSlider,\
    QSpinBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QMainWindow, QApplication, \
    QWidget, QVBoxLayout, QPushButton, QComboBox, QRadioButton, QSizePolicy
from PIL import ImageQt, Image
from skimage.transform import rescale
from PyQt5.QtGui import QPixmap, QImage, QIcon
from PyQt5.QtCore import Qt
import sys
import json
import os
import logging
from logging.handlers import RotatingFileHandler
import requests
import io
import time
import numpy as np


logger = logging.getLogger(__name__)


config_file_path = "config.json"
port_for_cameras = 8080


def read_json_file_content(fp):
    with open(fp, 'r') as infile:
        return json.load(infile)


def read_config():
    return read_json_file_content(config_file_path)


def save_config(c):
    with open(config_file_path, 'w') as outfile:
        json.dump(c, outfile)


def write_empty_config_to_file(fp):
    with open(fp, 'w') as outfile:
        json.dump({}, outfile)


def normalize_image(img, is16b=False):
    a = np.percentile(img, 5)
    b = np.percentile(img, 95)
    normalized = (img - a) / (b - a)
    maxv = 65536 if is16b else 256
    typv = np.uint16 if is16b else np.uint8
    return np.clip(maxv * normalized, 0, maxv-1).astype(typv)


class ResizeableLabelWithImage(QLabel):
    def __init__(self, parent):
        QLabel.__init__(self, parent)
        bg_img = QImage(320, 200, QImage.Format_Grayscale8)
        bg_img.fill(Qt.black)
        self.set_image(bg_img)

    def set_image(self, img: QImage):
        self._original_image = QPixmap(img)
        width = self.frameGeometry().width()
        height = self.frameGeometry().height()
        logger.debug(f"Label size is currently: {width}x{height} px")
        qp = self._original_image.scaled(width, height, Qt.KeepAspectRatio)
        self.setPixmap(qp)
        self.setMinimumSize(1, 1)

    def resizeEvent(self, event):
        if self._original_image is not None:
            pixmap = self._original_image.scaled(self.width(), self.height())
            self.setPixmap(pixmap)
        self.resize(self.width(), self.height())


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

    def custom_request(self, url):
        return self._get_request(url)

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
        response = self._regular_get_url("get_gain")
        if response is None:
            return False, None
        exposure = response.json()["value"]
        return True, exposure

    def get_offset(self):
        response = self._regular_get_url("get_offset")
        if response is None:
            return False, None
        offset = response.json()["value"]
        return True, offset

    def set_offset(self, value):
        return self._regular_set_url("set_offset", value)

    def get_formats(self):
        return self._regular_get_url("get_readoutmodes")

    def get_last_image(self):
        return self._regular_get_url("get_last_image")

    def get_current_format(self):
        response = self._regular_get_url("get_readoutmode_str")
        if response is None:
            return False, None
        format = response.json()["value"]
        return True, format

    def get_exposure(self):
        response = self._regular_get_url("get_exposure")
        if response is None:
            return False, None
        exposure = response.json()["value"]
        return True, exposure

    def set_exposure(self, value):
        return self._regular_set_url("set_exposure", value)

    def get_resolution(self):
        logger.debug(f"Trying to get camera resolution...")
        logger.debug(f"X...")

        response = self._regular_get_url("get_numx")
        if response is None:
            return False, None
        xres = int(response.json()["value"])
        response = self._regular_get_url("get_numy")
        if response is None:
            return False, None
        yres = int(response.json()["value"])
        logger.debug(f"Resolution = {xres}x{yres}")
        return True, (xres, yres)

    def get_possible_binning(self):
        response = self._regular_get_url("get_maxbinx")
        if response is None:
            return []
        maxbinx = int(response.json()["value"])
        logger.debug(f"Max possible bin is {maxbinx}")
        return list(range(1, maxbinx+1))


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowIcon(QIcon('logo.png'))
        self.config = read_config()
        self.main_layout = QVBoxLayout()
        self._init_launcher()
        self.requester = None
        self._exposure_range = "seconds"
        self._exposure_us = 1000000

    def _changed_exposure(self, value):
        self._exposure_us = value * 1000.0 if self._exposure_range == "milliseconds" else value * 1000000.0
        exp_s_str = str(self._exposure_us / 1000000)
        logger.debug(f"Exposure in us = {self._exposure_us}, seconds={exp_s_str}")
        self.requester.set_exposure(exp_s_str)

    def _changed_time_range(self, newText):
        self._exposure_range = newText
        newValue = self._exposure_us / 1000000.0 if newText == "seconds" else self._exposure_us / 1000.0
        self._exp_spin.setValue(newValue)
        logger.debug(f"Exposure range set to: {self._exposure_range}")

    def _changed_binning(self):
        radio_button = self.sender()
        if radio_button.isChecked():
            bin_value = int(radio_button.text().split(" x")[-1])
            logger.debug(f"Chosen binning: {bin_value}")
            self.requester.set_binning(bin_value)

    def _changed_gain(self, value):
        logger.debug(f"Setting gain to value: {value}")
        gain_str = str(value)
        self.requester.set_gain(gain_str)

    def _changed_offset(self, value):
        logger.debug(f"Setting offset to value: {value}")
        offset_str = str(value)
        self.requester.set_offset(offset_str)

    def _changed_format(self, t):
        logger.debug(f"New format chosen: {t}")
        self.requester.set_format(t)

    def add_binning_radio(self, layout):
        default_bin = self._read_default_bin(self.camera_name)
        logger.debug("Getting binning...")
        possible_bins = self.requester.get_possible_binning()
        label = QLabel("Binning:")
        label.setMaximumSize(100, 20)
        layout.addWidget(label, 0, 0)
        for index, bin in enumerate(possible_bins):
            logger.debug(f"Found binning: x{bin}")
            radiobutton = QRadioButton(f"bin x{bin}", self)
            radiobutton.toggled.connect(self._changed_binning)
            if bin == default_bin:
                logger.debug(f"Setting default binning={default_bin}")
                radiobutton.setChecked(True)

            layout.addWidget(radiobutton, 0, index + 1)

    def add_exposure_dial(self, layout):
        is_ok, exp_raw = self.requester.get_exposure()
        if not is_ok:
            logger.error("Could not get current exposure value!")
            return
        logger.debug(f"Acquired current exposure: {exp_raw}")
        exp_us = int(exp_raw)
        self._exposure_us = exp_us
        exp_ms = exp_us // 1000
        exp_s = exp_ms // 1000

        self._exp_spin = QDoubleSpinBox()
        self._exp_spin.setDecimals(2)
        self._exp_spin.setRange(0.01, 3600)
        self._exp_spin.setValue(exp_s)
        self._exp_spin.valueChanged.connect(self._changed_exposure)
        label = QLabel("Exposure time:")
        label.setMaximumSize(100, 20)

        ec = QComboBox()
        ec.addItems(["seconds", "milliseconds"])

        ec.currentTextChanged.connect(self._changed_time_range)
        ec.setMaximumSize(100, 20)

        layout.addWidget(label)
        layout.addWidget(self._exp_spin)
        layout.addWidget(ec)

    def add_gain_dial(self, layout):
        is_ok, gain_raw = self.requester.get_gain()
        if not is_ok:
            logger.error("Could not get current gain value!")
            return
        logger.debug(f"Acquired current gain: {gain_raw}")
        gain = int(gain_raw)
        self._gain_spin = QSpinBox()
        self._gain_spin.setRange(0, 1000)
        self._gain_spin.setValue(gain)
        self._gain_spin.valueChanged.connect(self._changed_gain)

        label = QLabel("Gain:")
        label.setMaximumSize(40, 20)
        layout.addWidget(label)
        layout.addWidget(self._gain_spin)

    def add_offset_dial(self, layout):
        is_ok, offset_raw = self.requester.get_offset()
        if not is_ok:
            logger.error("Could not get current offset value!")
            return
        logger.debug(f"Acquired current offset: {offset_raw}")
        offset = int(offset_raw)
        self._offset_spin = QSpinBox()
        self._offset_spin.setValue(offset)
        self._offset_spin.valueChanged.connect(self._changed_offset)

        label = QLabel("Offset:")
        label.setMaximumSize(50, 20)
        layout.addWidget(label)
        layout.addWidget(self._offset_spin)

    def add_format_chooser(self, layout):
        self.format_combo = QComboBox()
        format_values = self._read_possible_formats()
        self.format_combo.addItems(format_values)
        self.format_combo.currentTextChanged.connect(self._changed_format)
        logger.debug(f"Trying to read default format...")
        default_format = self._read_default_format(self.camera_name)
        logger.debug(f"Default format = {default_format}")
        self.format_combo.setCurrentText(default_format)

        format_label = QLabel("Image type:")
        format_label.setMaximumSize(100, 20)
        layout.addWidget(format_label)
        layout.addWidget(self.format_combo)

    def _init_guiding(self, camera_index, camera_name, camera_ip):
        self.camera_index = camera_index
        self.camera_name = camera_name
        self.camera_ip = camera_ip
        self.requester = CameraRequester(self.camera_ip, self.camera_index, self._error_prompt)

        logger.debug("Closing myself...")
        self.main_layout.removeWidget(self.main_widget)
        self.main_widget.setParent(None)
        self.main_widget = None
        self.close()
        logger.debug("...closed")

        self.setWindowTitle("Guiding")
        self.setGeometry(100, 100, 320, 200)
        self.main_widget = QWidget(self)

        guiding_layout = QVBoxLayout()

        bin_layout = QGridLayout()
        exposure_layout = QHBoxLayout()
        gain_layout = QHBoxLayout()
        offset_layout = QHBoxLayout()
        format_layout = QHBoxLayout()

        self.add_binning_radio(bin_layout)
        self.add_exposure_dial(exposure_layout)
        self.add_gain_dial(gain_layout)
        self.add_offset_dial(offset_layout)
        self.add_format_chooser(format_layout)

        guiding_layout.addLayout(bin_layout)
        guiding_layout.addLayout(exposure_layout)
        guiding_layout.addLayout(gain_layout)
        guiding_layout.addLayout(offset_layout)
        guiding_layout.addLayout(format_layout)

        logger.debug("Adding new widgets...")
        self.get_last_image_button = QPushButton("Get last image", self)
        self.get_last_image_button.clicked.connect(self._get_last_image)
        guiding_layout.addWidget(self.get_last_image_button)

        self.image_label = ResizeableLabelWithImage(self)
        guiding_layout.addWidget(self.image_label)

        self.main_widget.setLayout(guiding_layout)
        logger.debug("Setting central widget")
        self.setCentralWidget(self.main_widget)
        self.show()

    def _read_possible_formats(self):
        response = self.requester.get_formats()
        if response is None:
            logger.error("Could not read formats from camera")
            return []
        formats = response.json()["value"]
        logger.debug(f"Formats = {formats}")
        return formats

    def createQImageFromBuffer(self, content, resolution, format):
        logger.debug(f"Creating image with format {format}")
        is16b = (format == "RAW16")
        bufferType = np.uint16 if is16b else np.uint8
        imageFormat = QImage.Format_Grayscale16 if is16b else QImage.Format_Grayscale8

        img = np.frombuffer(content, dtype=bufferType)
        w, h = resolution
        logger.debug(f"Reshaping into {w}x{h}...")
        original_img = img.reshape(w, h)
        logger.debug(f"dimension = {original_img.shape}, Max = {np.max(original_img)}, min = {np.min(original_img)}")
        final_img = normalize_image(original_img, is16b=is16b)
        logger.debug("Normalized!")
        qImg = QImage(final_img.data, final_img.shape[0], final_img.shape[1], imageFormat)
        return qImg

    def _get_last_image(self):
        is_ok, (w, h) = self.requester.get_resolution()
        isOk, current_format = self.requester.get_current_format()
        start_time = time.time()
        response = self.requester.get_last_image()
        time_elapsed = time.time() - start_time
        logger.debug(f"Time elapsed on receiving response: {time_elapsed}")
        start_time = time.time()
        logger.debug("Acquired response!")
        if response is None:
            return

        logger.debug(response.content[:1024])

        qImg = self.createQImageFromBuffer(response.content, [w, h], current_format)

        self.image_label.set_image(qImg)

        # self.image_label.setScaledContents(True)
        time_elapsed = time.time() - start_time
        logger.debug(f"Time elapsed on processing: {time_elapsed}")

    def _init_launcher(self):
        self.setWindowTitle("Guiding Launcher")
        self.setGeometry(100, 100, 320, 100)

        layout2 = QHBoxLayout()
        layout3 = QHBoxLayout()
        layout4 = QHBoxLayout()
        layout5 = QHBoxLayout()

        self.preset_ip_combo = QComboBox()
        self.preset_ip_items = self._read_preset_ips()
        self.preset_ip_combo.addItems(self.preset_ip_items.keys())
        self.preset_ip_combo.currentTextChanged.connect(self._load_ip_from_preset)

        layout2.addWidget(QLabel('Enter IP:', self))

        placeholder_text = self._get_ip_initial_text()
        self.ip_edit = QLineEdit(self)
        self.ip_edit.setInputMask("000.000.000.000")
        self.ip_edit.setText(placeholder_text)

        layout2.addWidget(self.ip_edit)

        self.save_ip_button = QPushButton("save as...", self)
        self.save_ip_button.clicked.connect(self._save_preset_ip_in_config)
        layout2.addWidget(self.save_ip_button)

        self.main_layout.addLayout(layout2)

        layout3.addWidget(QLabel('Or choose saved:', self))
        layout3.addWidget(self.preset_ip_combo)

        self.main_layout.addLayout(layout3)

        self.camera_chooser_combo = QComboBox()

        self.connect_ip_button = QPushButton("Get cameras list", self)
        self.connect_ip_button.clicked.connect(self._get_cameras_list)
        layout4.addWidget(self.connect_ip_button)
        self.main_layout.addLayout(layout4)

        self.connect_camera_button = QPushButton("Go!", self)
        self.connect_camera_button.setEnabled(False)
        self.connect_camera_button.clicked.connect(self._connect_to_camera)
        layout5.addWidget(QLabel("Choose camera:", self))
        layout5.addWidget(self.camera_chooser_combo)
        layout5.addWidget(self.connect_camera_button)

        self.main_layout.addLayout(layout5)

        self.main_widget = QWidget(self)
        self.main_widget.setLayout(self.main_layout)
        self.setCentralWidget(self.main_widget)
        self.show()

    def _read_default_camera_setting(self, camera_name, setting_name, returned_if_not_found):
        defaults = self.config.get("camera_defaults", {})
        if not defaults:
            logger.warning(f"There are no camera defaults in config")
            return returned_if_not_found
        camera_config = defaults.get(camera_name, "")
        if not camera_config:
            logger.warning(f"Could not find defaults for {camera_name}")
            return returned_if_not_found
        return camera_config.get(setting_name, returned_if_not_found)

    def _read_default_bin(self, camera_name):
        return int(self._read_default_camera_setting(camera_name, "default_bin", 1))

    def _read_default_format(self, camera_name):
        return self._read_default_camera_setting(camera_name, "default_format", "RAW8")

    def _read_preset_ips(self):
        d = {"": ""}
        d.update(self.config.get("saved_ips", {}))
        logger.debug(f"Read preset ids = {d}")
        return d

    def _get_ip_initial_text(self):
        last_used_ip = self.config.get("last_used_ip", "")
        logger.debug(f"Obtained last used ip from config: {last_used_ip}")
        return last_used_ip

    def _error_prompt(self, t):
        error_dialog = QErrorMessage(self)
        error_dialog.showMessage(t)

    def _get_cameras_list(self):
        try_ip = self.ip_edit.text()
        full_url = f"http://{try_ip}:{port_for_cameras}/cameras_list"
        response = standalone_get_request(full_url, self._error_prompt)
        if response is None:
            return

        self._save_to_config({"last_used_ip": try_ip})
        cameras_list = response.json()["cameras"]
        logger.debug(f"Successfully got list of cameras at {try_ip} : {cameras_list}")
        self.camera_chooser_combo.clear()
        self.camera_chooser_combo.addItems(cameras_list)
        self.connect_camera_button.setEnabled(len(cameras_list) > 0)

    def _save_config(self):
        save_config(self.config)

    def _save_to_config(self, d: dict):
        self.config.update(d)
        self._save_config()

    def _connect_to_camera(self):
        camera_name = self.camera_chooser_combo.currentText()
        camera_index = self.camera_chooser_combo.currentIndex()
        current_ip = self.ip_edit.text()
        logger.debug(f"Connecting to camera {camera_name} at {current_ip}")

        url = f"http://{current_ip}:{port_for_cameras}/camera/{camera_index}/init_camera"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {}

        logger.debug(f"About to call POST...")
        response = standalone_post_request(url, headers, data, self._error_prompt)
        if response is not None and response.status_code == 200:
            self._init_guiding(camera_index, camera_name, current_ip)

    def _load_ip_from_preset(self, t):
        new_ip = self.preset_ip_items[t]
        logger.debug(f"New ip chosen from preset {t}: {new_ip}")
        self.ip_edit.setText(new_ip)

    def _save_preset_ip_in_config(self):
        ip_alias, dialog_ok = QInputDialog.getText(self, 'Save IP', 'Save current ip as:')
        if dialog_ok:
            new_config_entry = {"saved_ips": {ip_alias: self.ip_edit.text()}}
            logger.debug(f"Saving new config entry: {new_config_entry}")
            self._save_to_config(new_config_entry)


def configure_logging(logfile_path):
    default_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] [%(funcName)s():%(lineno)s] [PID:%(process)d] %(message)s",
        "%d/%m/%Y %H:%M:%S")

    file_handler = RotatingFileHandler(logfile_path, maxBytes=10485760, backupCount=300, encoding='utf-8')
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    file_handler.setFormatter(default_formatter)
    console_handler.setFormatter(default_formatter)

    logging.root.setLevel(logging.DEBUG)
    logging.root.addHandler(file_handler)
    logging.root.addHandler(console_handler)


if __name__ == '__main__':
    configure_logging("main_gui.log")
    logger.debug("Logging works")

    if not os.path.isfile(config_file_path):
        logger.debug("Writing new config file")
        write_empty_config_to_file(config_file_path)

    logger.debug("Now Qt app should start...")
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
