from PyQt5.QtWidgets import QInputDialog, QErrorMessage, QLabel, QLineEdit, QGridLayout, QHBoxLayout, QMainWindow, QApplication, \
    QWidget, QVBoxLayout, QPushButton, QComboBox, QRadioButton
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


def normalize_image(img):
    a = np.percentile(img, 5)
    b = np.percentile(img, 95)
    normalized = (img - a) / (b - a)
    return np.clip(256 * normalized, 0, 255).astype(np.uint8)


class ResizeableLabelWithImage(QLabel):
    def __init__(self, parent):
        QLabel.__init__(self, parent)
        self.setText("<IMAGE>")
        self._original_image = None

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


def add_binning_radio_button(parent, requester, layout, on_clicked, default_bin):
    possible_bins = requester.get_possible_binning()
    for index, bin in enumerate(possible_bins):
        logger.debug(f"Found binning: x{bin}")
        radiobutton = QRadioButton(f"bin x{bin}", parent)
        radiobutton.toggled.connect(on_clicked)
        if bin == default_bin:
            logger.debug(f"Setting default binning={default_bin}")
            radiobutton.setChecked(True)
        layout.addWidget(radiobutton, 0, index)


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

    def custom_request(self, url):
        return self._get_request(url)

    def set_binning(self, value):
        url = f"http://{self._ip}:{port_for_cameras}/camera/{self._camera_index}/set_binx"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {"value": str(value)}
        return standalone_post_request(url, headers, data, self._error_prompt)

    def get_last_image(self):
        return self._regular_get_url("get_last_image")

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

    def on_bin_radio_clicked(self):
        radio_button = self.sender()
        if radio_button.isChecked():
            bin_value = int(radio_button.text().split(" x")[-1])
            logger.debug(f"Chosen binning: {bin_value}")
            self.requester.set_binning(bin_value)

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
        radio_layout = QGridLayout()
        default_bin = self._read_default_bin(self.camera_name)
        logger.debug("Getting binning...")
        add_binning_radio_button(self, self.requester, radio_layout, self.on_bin_radio_clicked, default_bin)

        guiding_layout = QVBoxLayout()
        guiding_layout.addLayout(radio_layout)
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

    def _get_last_image(self):
        is_ok, (w, h) = self.requester.get_resolution()
        start_time = time.time()
        response = self.requester.get_last_image()
        time_elapsed = time.time() - start_time
        logger.debug(f"Time elapsed on receiving response: {time_elapsed}")
        start_time = time.time()
        logger.debug("Acquired response!")
        if response is None:
            return

        logger.debug(response.content[:1024])

        img = np.frombuffer(response.content, dtype=np.uint8)
        logger.debug(f"Reshaping into {w}x{h}...")
        original_img = img.reshape(w, h)
        logger.debug(f"dimension = {original_img.shape}, Max = {np.max(original_img)}, min = {np.min(original_img)}")
        final_img = normalize_image(original_img)

        qImg = QImage(final_img.data, final_img.shape[0], final_img.shape[1], QImage.Format_Grayscale8)
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

    def _read_default_bin(self, camera_name):
        defaults = self.config.get("camera_defaults", {})
        if not defaults:
            logger.warning(f"There are no camera defaults in config")
            return 1
        camera_config = defaults.get(camera_name, "")
        if not camera_config:
            logger.warning(f"Could not find defaults for {camera_name}")
            return 1
        default_bin = camera_config.get("default_bin", 1)
        return int(default_bin)

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
