from PyQt5.QtWidgets import QStyleFactory, QInputDialog, QErrorMessage, QLabel, QLineEdit, QSlider,\
    QSpinBox, QDoubleSpinBox, QGridLayout, QHBoxLayout, QMainWindow, QApplication, \
    QWidget, QVBoxLayout, QPushButton, QComboBox, QRadioButton, QSizePolicy
from threading import Event, Timer
from PIL import Image
import PIL.ImageQt as PIQt
from skimage.transform import rescale
from camera_controls_view import CameraControlsView
from launcher_view import LauncherView
from config_manager import read_config, save_config, init_config
from camera_requester import CameraRequester
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
import qdarktheme


logger = logging.getLogger(__name__)


interval_last_time = time.time()


def interval_polling(stop_event: Event, callback, interval: int):
    global interval_last_time
    tick = time.time()
    callback()
    logger.debug(f"Passed time = {tick-interval_last_time}")
    interval_last_time = tick
    if not stop_event.is_set():
        Timer(interval, interval_polling, [stop_event, callback, interval]).start()

    else:
        logger.debug("Interval polling stopped!")


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


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowIcon(QIcon('logo.png'))
        self.config = read_config()
        self.main_layout = QVBoxLayout()
        self.setWindowTitle("Guiding Launcher")
        self.setGeometry(100, 100, 320, 100)

        self._launcher_view = LauncherView(self.config, self._switch_to_camera, self._error_prompt)
        self.setCentralWidget(self._launcher_view)
        self.show()
        # self._init_launcher()
        # self.requester: CameraRequester = None
        # self._exposure_range = "seconds"
        # self._exposure_us = 1000000
        # self._send_as_jpg = False
        # self._continuous_polling = False
        # self._polling_event = Event()
        #
        # self._gain_setter = GainSetter(self.requester)

    def _switch_to_camera(self, ip, camera_index, camera_name):
        logger.debug(f"Switching to camera: {camera_name}")
        camera_controls_view = CameraControlsView(self.config, ip, camera_index, camera_name, self._error_prompt)
        self.setCentralWidget(camera_controls_view)
        self.setWindowTitle("Remote camera controls")

    def _error_prompt(self, t):
        logger.error(t)
        error_dialog = QErrorMessage(self)
        error_dialog.showMessage(t)


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

    init_config()

    logger.debug("Now Qt app should start...")
    app = QApplication(sys.argv)

    qdarktheme.setup_theme()

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
