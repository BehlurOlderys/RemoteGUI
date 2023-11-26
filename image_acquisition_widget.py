import logging
from PyQt5.QtWidgets import QWidget, QLabel, QComboBox, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QSpinBox, \
    QProgressBar
from PyQt5.QtGui import QImage
from PyQt5.QtCore import Qt
from utils import start_interval_polling
from threading import Event
from time import time

import numpy as np


logger = logging.getLogger(__name__)


def normalize_image(img, is16b=False):
    a = np.percentile(img, 5)
    b = np.percentile(img, 95)
    normalized = (img - a) / (b - a)
    maxv = 65536 if is16b else 256
    typv = np.uint16 if is16b else np.uint8
    return np.clip(maxv * normalized, 0, maxv-1).astype(typv)


def qimage_from_buffer(content, resolution, image_format):
    logger.debug(f"Creating image with format {image_format}")
    is16b = (image_format == "RAW16")
    buffer_type = np.uint16 if is16b else np.uint8
    image_format = QImage.Format_Grayscale16 if is16b else QImage.Format_Grayscale8

    img = np.frombuffer(content, dtype=buffer_type)
    w, h = resolution
    logger.debug(f"Reshaping into {w}x{h}...")
    original_img = img.reshape(w, h)
    logger.debug(f"dimension = {original_img.shape}, Max = {np.max(original_img)}, min = {np.min(original_img)}")
    final_img = normalize_image(original_img, is16b=is16b)
    logger.debug("Normalized!")
    q_img = QImage(final_img.data, final_img.shape[0], final_img.shape[1], image_format)
    return q_img, final_img


def qimage_from_jpg(response):
    logger.debug(f"Creating jpeg image from response...")
    image = QImage()
    image.loadFromData(response.content)
    logger.debug(f"...succeeded!")
    return image


class ImageAcquisition(QWidget):
    def __init__(self, requester, format_chooser, image_label, hist_plotter, kill_event: Event):
        super(ImageAcquisition, self).__init__()
        self._requester = requester
        self._format_chooser = format_chooser
        self._image_label = image_label
        self._hist_plotter = hist_plotter
        self._continuous_polling = False
        self._polling_event = Event()
        self._kill_event = kill_event

        self._layout = QVBoxLayout()
        top_layout = QHBoxLayout()
        bottom_layout = QHBoxLayout()

        # self._get_last_image_button = QPushButton("Get last image", self)
        # self._get_last_image_button.setMaximumSize(100, 50)
        # self._get_last_image_button.clicked.connect(self._get_last_image)

        self._continuous_polling_button = QPushButton("Poll for images continuously", self)
        self._continuous_polling_button.setMaximumSize(150, 50)
        self._continuous_polling_button.setCheckable(True)
        self._continuous_polling_button.setStyleSheet("background-color : black")
        self._continuous_polling_button.clicked.connect(self._start_continuous_polling)

        self._continuous_poll_cb = QComboBox()
        self._continuous_poll_cb.setMaximumSize(100, 50)
        self._continuous_poll_cb.addItems(["0.5s", "1s", "2s"])
        self._continuous_poll_cb.setCurrentText("1s")

        self._save_button = QPushButton("Save images")
        self._save_button.setMaximumSize(100, 50)
        self._save_button.setCheckable(True)
        self._save_button.setStyleSheet("background-color : black")
        self._save_button.clicked.connect(self._start_saving)
        self._save_button.setDisabled(True)

        self._saved_number_spin = QSpinBox()
        self._saved_number_spin.setRange(1, 1000)
        self._saved_number_spin.setMaximumSize(50, 50)

        self._save_dir_edit = QLineEdit("Capture")
        self._save_dir_edit.setMaximumSize(150, 50)

        save_dir_label = QLabel("Save directory:")
        save_dir_label.setMaximumSize(100, 50)
        capture_type_label = QLabel("Type of images:")
        capture_type_label.setMaximumSize(100, 50)

        self._capture_type_cb = QComboBox()
        self._capture_type_cb.setMaximumSize(100, 50)
        self._capture_type_cb.addItems(["light", "dark", "bias", "flat"])
        self._capture_type_cb.setCurrentText("light")

        self._status_label = QLabel("Status: N/A")
        self._refresh_impl()

        self._capture_progress_bar = QProgressBar()
        # self._capture_progress_bar.setTextVisible(True)
        self._capture_progress_bar.setFormat("%v / %m")
        # self._capture_progress_bar.setValue(70)
        # self._capture_progress_bar.setAlignment(Qt.AlignCenter)

        # self._layout.addWidget(self._get_last_image_button)
        top_layout.addWidget(self._status_label)
        top_layout.addWidget(self._continuous_polling_button)
        top_layout.addWidget(self._continuous_poll_cb)

        bottom_layout.addWidget(self._save_button)
        bottom_layout.addWidget(self._saved_number_spin)
        bottom_layout.addWidget(save_dir_label)
        bottom_layout.addWidget(self._save_dir_edit)
        bottom_layout.addWidget(capture_type_label)
        bottom_layout.addWidget(self._capture_type_cb)

        self._layout.addLayout(top_layout)
        self._layout.addLayout(bottom_layout)
        self._layout.addWidget(self._capture_progress_bar)
        self.setLayout(self._layout)

    @staticmethod
    def refresh_rate_s():
        return 3

    def _start_saving(self):
        button: QPushButton = self.sender()
        if button.isChecked():
            button.setStyleSheet("background-color : #228822")

            dir_name = self._save_dir_edit.text()
            number = int(self._saved_number_spin.value())
            prefix = self._capture_type_cb.currentText()

            self._capture_progress_bar.setMaximum(number)
            self._capture_progress_bar.setValue(0)

            logger.debug(f"Starting to save {number} new images in dir{dir_name} with prefix {prefix}")
            response = self._requester.start_saving(number, dir_name, prefix)
            logger.debug(f"Start saving returned: {response.status_code} with content: {response.json()}")
        else:
            logger.debug("Stop saving clicked")
            self._stop_saving_impl()

    def _get_last_image(self):
        logger.debug("Getting last image")
        send_as_jpg = self._format_chooser.should_send_jpg()
        if send_as_jpg:
            logger.debug("Image will be send as jpg")
            start_time = time()
            response = self._requester.get_last_image(send_as_jpg)
            time_elapsed = time() - start_time
            logger.debug(f"Time elapsed on receiving response: {time_elapsed}")
            start_time = time()
            q_img = qimage_from_jpg(response)

        else:
            logger.debug("Image will be send raw")
            is_ok1, (w, h) = self._requester.get_resolution()
            is_ok2, current_format = self._requester.get_current_format()
            if not is_ok1 or not is_ok2:
                logger.error("Could not get required image parameters from camera")
                return
            start_time = time()
            response = self.requester.get_last_image(self._send_as_jpg)
            time_elapsed = time() - start_time
            logger.debug(f"Time elapsed on receiving response: {time_elapsed}")
            start_time = time()
            logger.debug("Acquired response!")
            if response is None:
                return
            q_img = qimage_from_buffer(response.content, [w, h], current_format)

        if q_img is not None:
            logger.debug("Setting new image...")
            self._image_label.set_image(q_img)
            if send_as_jpg:
                self._hist_plotter.plot_histogram(response.content)

        time_elapsed = time() - start_time
        logger.debug(f"Time elapsed on processing: {time_elapsed}")

    def _set_button_for_capture(self, button):
        button.setChecked(True)
        button.setStyleSheet("background-color : #228822")
        interval_str = self._continuous_poll_cb.currentText()
        self._continuous_poll_cb.setDisabled(True)
        logger.debug(f"Starting to poll for new images with interval {interval_str}")
        interval = float(interval_str[:-1])
        self._polling_event.clear()
        start_interval_polling(self._polling_event, self._get_last_image, interval, self._kill_event)
        self._continuous_polling = True
        self._save_button.setEnabled(True)

    def _start_continuous_polling(self):
        button: QPushButton = self.sender()
        if button.isChecked():
            response = self._requester.start_capturing()
            logger.debug(f"Start capturing returned: {response.status_code} with content: {response.json()}")
            if response.status_code == 200:
                self._set_button_for_capture(button)
            else:
                logger.error("Starting capturing failed!")

        else:
            self._stop_saving_impl()
            self._save_button.setDisabled(True)

            self._requester.stop_capturing()
            button.setStyleSheet("background-color : black")
            self._polling_event.set()
            self._continuous_polling = False
            self._continuous_poll_cb.setEnabled(True)

    def _saving_button_off(self):
        self._save_button.setChecked(False)
        self._save_button.setStyleSheet("background-color : black")

    def _stop_saving_impl(self):
        self._saving_button_off()
        self._requester.stop_saving()

    def _refresh_impl(self):
        logger.debug("Refreshing status label")
        is_ok, status = self._requester.get_status()
        if is_ok:
            logger.debug(f"Acquired status: {status}")
            state = status.get("state", "<UNKNOWN>")
            if state == "CAPTURE" or state == "SAVE":
                self._set_button_for_capture(self._continuous_polling_button)
            if state == "SAVE":
                number = int(status.get("number", "0"))
                self._capture_progress_bar.setValue(number+1)

            self._status_label.setText(f"Status: {state}")
            if self._save_button.isChecked() and (state != "SAVE"):
                # self._capture_progress_bar.reset()
                self._saving_button_off()

    def refresh(self):
        logger.debug("Refreshing acquisition controls...")
        self._refresh_impl()
