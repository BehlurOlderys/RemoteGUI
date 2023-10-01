from PyQt5.QtWidgets import QInputDialog, QErrorMessage, QLabel, QLineEdit, QHBoxLayout, QMainWindow, QApplication, QWidget, QVBoxLayout, QPushButton, QComboBox
import sys
import json
import os
import logging
from logging.handlers import RotatingFileHandler
import requests


logger = logging.getLogger(__name__)


config_file_path = "config.json"
port_for_cameras = 8080


def read_json_file_content(fp):
    with open(fp, 'r') as infile:
        return json.load(infile)


def write_empty_config_to_file(fp):
    with open(fp, 'w') as outfile:
        json.dump({
            "saved_ips": {}
        }, outfile)


def read_preset_ip_from_config():
    config = read_json_file_content(config_file_path)
    return config["saved_ips"]


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.setWindowTitle("Guiding")
        self.setGeometry(100, 100, 320, 100)

        layout1 = QVBoxLayout()
        layout2 = QHBoxLayout()
        layout3 = QHBoxLayout()
        layout4 = QHBoxLayout()
        layout5 = QHBoxLayout()

        self.preset_ip_combo = QComboBox()
        self.preset_ip_items = read_preset_ip_from_config()
        self.preset_ip_combo.addItems(self.preset_ip_items.keys())
        self.preset_ip_combo.currentTextChanged.connect(self._load_ip_from_preset)

        layout2.addWidget(QLabel('Enter IP:', self))

        self.ip_edit = QLineEdit(self, placeholderText='enter ip here...')
        self.ip_edit.setInputMask( "000.000.000.000")

        layout2.addWidget(self.ip_edit)

        self.save_ip_button = QPushButton("save as...", self)
        self.save_ip_button.clicked.connect(self._save_preset_ip_in_config)
        layout2.addWidget(self.save_ip_button)

        layout1.addLayout(layout2)

        layout3.addWidget(QLabel('Or choose saved:', self))
        layout3.addWidget(self.preset_ip_combo)

        layout1.addLayout(layout3)

        self.camera_chooser_combo = QComboBox()

        self.connect_ip_button = QPushButton("Get cameras list", self)
        self.connect_ip_button.clicked.connect(self._get_cameras_list)
        layout4.addWidget(self.connect_ip_button)
        layout1.addLayout(layout4)

        self.connect_camera_button = QPushButton("OK", self)
        self.connect_camera_button.clicked.connect(self._connect_to_camera)
        layout5.addWidget(QLabel("Choose camera:", self))
        layout5.addWidget(self.camera_chooser_combo)
        layout5.addWidget(self.connect_camera_button)

        layout1.addLayout(layout5)

        widget = QWidget()
        widget.setLayout(layout1)
        self.setCentralWidget(widget)
        self.show()

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
            return []

        except Exception as e:
            logger.debug(f"Unknown exception: {e}")
            self._error_prompt(f"Unknown exception when connecting to {try_ip}: {e}")
            return []

        if response.status_code != 200:
            logger.debug(f"Could not obtain cameras from {try_ip}: status code={response.status_code}")
            self._error_prompt(f"Could not obtain cameras from {try_ip}:\n status code={response.status_code}")
            return []
        else:
            cameras_list = response.json()["cameras"]
            logger.debug(f"Successfully got list of cameras at {try_ip} : {cameras_list}")
            return cameras_list

    def _connect_to_camera(self):
        logger.debug(f"Connecting to camera {self.camera_chooser_combo.currentText()} at {self.ip_edit.text()}")

    def _load_ip_from_preset(self, t):
        new_ip = self.preset_ip_items[t]
        logger.debug(f"New ip chosen from preset {t}: {new_ip}")
        self.ip_edit.setText(new_ip)

    def _save_preset_ip_in_config(self):
        ip_alias, dialog_ok = QInputDialog.getText(self, 'Save IP', 'Save current ip as:')
        if dialog_ok:
            config = read_json_file_content(config_file_path)
            config["saved_ips"][ip_alias] = self.ip_edit.text()

            with open(config_file_path, 'w') as outfile:
                json.dump(config, outfile)


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
