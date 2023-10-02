from PyQt5.QtWidgets import QInputDialog, QErrorMessage, QLabel, QLineEdit, QHBoxLayout, QMainWindow, QApplication, \
    QWidget, QVBoxLayout, QPushButton, QComboBox
from PIL import ImageQt, Image
from PyQt5.QtGui import QPixmap, QImage
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


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.config = read_config()
        self.main_layout = QVBoxLayout()
        self._init_launcher()

    def _init_guiding(self, camera_index, camera_ip):
        self.camera_index = camera_index
        self.camera_ip = camera_ip

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
        logger.debug("Adding new widgets...")
        self.get_last_image_button = QPushButton("Get last image", self)
        self.get_last_image_button.clicked.connect(self._get_last_image)
        guiding_layout.addWidget(self.get_last_image_button)

        self.image_label = QLabel(self)
        self.image_label.setText("whatever")
        guiding_layout.addWidget(self.image_label)

        self.main_widget.setLayout(guiding_layout)
        logger.debug("Setting central widget")
        self.setCentralWidget(self.main_widget)
        self.show()

    def _get_request(self, try_ip, full_url):
        try:
            response = requests.get(full_url, timeout=5)
        except requests.exceptions.Timeout:
            logger.debug(f"Connection to {try_ip} timed out!")
            self._error_prompt(f"Connection to {try_ip} timed out!")
            return None

        except Exception as e:
            logger.debug(f"Unknown exception: {e}")
            self._error_prompt(f"Unknown exception when connecting to {try_ip}: {e}")
            return None

        if response.status_code != 200:
            logger.debug(f"HTTP error encountered while getting from {try_ip}: "
                         f"status code={response.status_code}")
            self._error_prompt(f"HTTP error encountered while getting from {try_ip}:\n"
                               f"status code={response.status_code}")
            return None
        return response

    def _get_last_image(self):
        start_time = time.time()
        url = f"http://{self.camera_ip}:{port_for_cameras}/camera/{self.camera_index}/get_last_image"
        logger.debug(f"Trying to get last image from camera on {url}")
        response = self._get_request(self.camera_ip, url)
        start_time = time.time()
        logger.debug("Acquired response!")
        if response is None:
            return

        print(response.content[:1024])

        # with open('logo.png', 'rb') as f:
        #     content = f.read()
        #
        # print(content[:1024])
        #
        # self.qImg = QImage()
        # self.qImg.loadFromData(content)
        #
        # # self.qImg = QImage(response.content, 1608, 1104, 1, QImage.Format_Grayscale8)
        img = np.frombuffer(response.content, dtype=np.uint8)



        a = np.percentile(img, 5)
        b = np.percentile(img, 95)
        normalized = (img - a) / (b - a)
        final_img = np.clip(256 * normalized, 0, 255).astype(np.uint8)




        logger.debug(f"Max = {np.max(final_img)}, min = {np.min(final_img)}")
        final_img = final_img.reshape(1608, 1104)

        qImg = QImage(final_img.data, final_img.shape[0], final_img.shape[1], QImage.Format_Grayscale8)
        qp = QPixmap(qImg)
        self.image_label.setPixmap(qp)
        time_elapsed = time.time() - start_time
        logger.debug(f"Time elapsed: {time_elapsed}")


    def _camera_demo(self):
        url = f"http://{self.camera_ip}:{port_for_cameras}/camera/{self.camera_index}/demo"
        logger.debug(f"Trying to demo camera on {url}")
        response = self._get_request(self.camera_ip, url)
        if response is None:
            return
        logger.debug(f"Got 200 OK from {url}")
        if response.headers.get('content-type') == 'application/json':
            logger.debug(f"Response content = {response.json()}")

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
        logger.debug(f"Getting cameras list from {full_url}")
        try:
            response = requests.get(full_url, timeout=5)
        except requests.exceptions.Timeout:
            logger.debug(f"Connection to {try_ip} timed out!")
            self._error_prompt(f"Connection to {try_ip} timed out!")
            return

        except Exception as e:
            logger.debug(f"Unknown exception: {e}")
            self._error_prompt(f"Unknown exception when connecting to {try_ip}: {e}")
            return

        if response.status_code != 200:
            logger.debug(f"Could not obtain cameras from {try_ip}: "
                         f"status code={response.status_code}")
            self._error_prompt(f"Could not obtain cameras from {try_ip}:\n"
                               f"status code={response.status_code}")
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
        init_camera_url = f"http://{current_ip}:{port_for_cameras}/init_camera"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {"name": camera_name}
        try:
            response = requests.post(init_camera_url, headers=headers, json=data, timeout=5)
        except requests.exceptions.Timeout:
            logger.debug(f"Connection to {init_camera_url} timed out!")
            self._error_prompt(f"Connection to {init_camera_url} timed out!")
            return

        except Exception as e:
            logger.debug(f"Unknown exception: {e}")
            self._error_prompt(f"Unknown exception when connecting to {init_camera_url}: {e}")
            return
        if response.status_code != 200:
            logger.debug(f"Could not initialize camera {camera_name} under {current_ip}: "
                         f"status code = {response.status_code}")
            self._error_prompt(f"Could not initialize camera {camera_name} under {current_ip}:\n"
                               f"status code={response.status_code}")
            return
        logger.debug(f"Acquired 200 OK and response: {response.json()}, camera {camera_name} initialized.")

        self._init_guiding(camera_index, current_ip)

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
