import logging
from PyQt5.QtWidgets import QWidget, QLabel, QComboBox, QHBoxLayout, QPushButton
from PyQt5.QtGui import QImage
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
    return q_img


def qimage_from_jpg(response):
    logger.debug(f"Creating jpeg image from response...")
    image = QImage()
    image.loadFromData(response.content)
    logger.debug(f"...succeeded!")
    return image


class ImageAcquisition(QWidget):
    def __init__(self, requester, format_chooser, image_label, kill_event: Event):
        super(ImageAcquisition, self).__init__()
        self._requester = requester
        self._format_chooser = format_chooser
        self._image_label = image_label
        self._continuous_polling = False
        self._polling_event = Event()
        self._kill_event = kill_event

        self._layout = QHBoxLayout()

        self._get_last_image_button = QPushButton("Get last image", self)
        self._get_last_image_button.clicked.connect(self._get_last_image)

        continuous_polling_button = QPushButton("Poll for images continuously", self)
        continuous_polling_button.setCheckable(True)
        continuous_polling_button.setStyleSheet("background-color : black")
        continuous_polling_button.clicked.connect(self._start_continuous_polling)

        self._continuous_poll_cb = QComboBox()
        self._continuous_poll_cb.addItems(["0.5s", "1s", "2s"])
        self._continuous_poll_cb.setCurrentText("1s")

        self._status_label = QLabel("Status: N/A")
        self._refresh_impl()

        self._layout.addWidget(self._get_last_image_button)
        self._layout.addWidget(continuous_polling_button)
        self._layout.addWidget(self._continuous_poll_cb)
        self._layout.addWidget(self._status_label)
        self.setLayout(self._layout)

    @staticmethod
    def refresh_rate_s():
        return 3

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

        time_elapsed = time() - start_time
        logger.debug(f"Time elapsed on processing: {time_elapsed}")

    def _start_continuous_polling(self):
        button: QPushButton = self.sender()
        if button.isChecked():
            button.setStyleSheet("background-color : #228822")
            interval_str = self._continuous_poll_cb.currentText()
            self._continuous_poll_cb.setDisabled(True)
            logger.debug(f"Starting to poll for new images with interval {interval_str}")
            interval = float(interval_str[:-1])
            response = self._requester.start_capturing()
            logger.debug(f"Start capturing returned: {response.status_code} with content: {response.json()}")
            self._polling_event.clear()
            start_interval_polling(self._polling_event, self._get_last_image, interval, self._kill_event)
            self._continuous_polling = True

        else:
            self._requester.stop_capturing()
            button.setStyleSheet("background-color : black")
            self._polling_event.set()
            self._continuous_polling = False
            self._continuous_poll_cb.setEnabled(True)

    def _refresh_impl(self):
        logger.debug("Refreshing status label")
        is_ok, status = self._requester.get_status()
        if is_ok:
            self._status_label.setText(f"Status: {status}")

    def refresh(self):
        logger.debug("Refreshing acquisition controls...")
        self._refresh_impl()
