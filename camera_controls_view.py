from PyQt5.QtWidgets import QLabel, QHBoxLayout, QWidget, QVBoxLayout, QPushButton
import logging
from exposure_dial_widget import ExposureDial
from gain_setter_widget import GainSetter
from binning_radio_widget import BinningRadio
from offset_dial_widget import OffsetDial
from format_chooser_widget import FormatChooser
from temperature_control_widget import TemperatureControl
from PyQt5.QtGui import QPixmap, QImage, QIcon
from PyQt5.QtCore import Qt
import time
import numpy as np
from camera_requester import CameraRequester
from config_manager import save_config
from PIL import Image
import PIL.ImageQt as PIQt
from skimage.transform import rescale
from threading import Event
from utils import start_interval_polling


logger = logging.getLogger(__name__)


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
        self.setMinimumSize(640, 480)

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


def get_widget_refresh_rate_or_none(w):
    logger.debug(f"Checking for refresh rate in {w}")
    if hasattr(w, "refresh_rate_s") and callable(getattr(w, "refresh_rate_s")):
        return w.refresh_rate_s()
    return None


def createQImageFromBuffer(content, resolution, format):
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


def createQImageFromJpg(response):
    logger.debug(f"Creating jpeg image from response...")
    image = QImage()
    image.loadFromData(response.content)
    logger.debug(f"...succeeded!")
    return image


class CameraControlsView(QWidget):
    def __init__(self, config, ip, camera_index, camera_name, error_prompt, kill_event):
        super(CameraControlsView, self).__init__()
        self._config = config
        self._camera_name = camera_name
        self._kill_event = kill_event

        self._requester = CameraRequester(ip, camera_index, error_prompt)
        self._refreshable = []
        self._auto_refresh = []
        self._continuous_polling = False
        self._polling_event = Event()
        self._prepare_ui()

    def _add_auto_task(self, refresh_rate, callback):
        new_refresh_event = Event()
        self._auto_refresh.append(new_refresh_event)
        start_interval_polling(new_refresh_event, callback, refresh_rate, self._kill_event)


    def _add_custom_widget(self, layout, ctor, *args):
        widget = ctor(*args)
        rr = get_widget_refresh_rate_or_none(widget)
        if rr is not None:
            self._add_auto_task(rr, widget.refresh)

        self._refreshable.append(widget)
        layout.addWidget(widget)
        return widget

    def _prepare_ui(self):
        self._main_layout = QVBoxLayout()

        exp_gain_off = QHBoxLayout()
        self._add_custom_widget(exp_gain_off, ExposureDial, self._requester)
        self._add_custom_widget(exp_gain_off, GainSetter, self._requester)
        self._add_custom_widget(exp_gain_off, OffsetDial, self._requester)
        self._main_layout.addLayout(exp_gain_off)

        format_bin = QHBoxLayout()
        self._format_chooser: FormatChooser = self._add_custom_widget(format_bin, FormatChooser, self._requester, self._read_default_format())
        self._add_custom_widget(format_bin, BinningRadio, self._requester, self._read_default_bin())
        self._main_layout.addLayout(format_bin)

        self._add_custom_widget(self._main_layout, TemperatureControl, self._requester)

        refresh_layout = QHBoxLayout()
        refresh_button = QPushButton("Refresh parameters", self)
        refresh_button.clicked.connect(self._refresh_all)
        refresh_layout.addWidget(refresh_button)
        self._main_layout.addLayout(refresh_layout)

        acquisition_layout = QHBoxLayout()
        self._get_last_image_button = QPushButton("Get last image", self)
        self._get_last_image_button.clicked.connect(self._get_last_image)
        acquisition_layout.addWidget(self._get_last_image_button)

        continuous_polling_button = QPushButton("Poll for images continuously", self)
        continuous_polling_button.setCheckable(True)
        continuous_polling_button.setStyleSheet("background-color : black")
        continuous_polling_button.clicked.connect(self._start_continuous_polling)
        acquisition_layout.addWidget(continuous_polling_button)

        status_label = QLabel("Status: N/A")

        def refresh_status():
            logger.debug("Refreshing status label")
            is_ok, status = self._requester.get_status()
            if is_ok:
                status_label.setText(f"Status: {status}")

        refresh_status()
        acquisition_layout.addWidget(status_label)
        self._add_auto_task(3, refresh_status)

        self._main_layout.addLayout(acquisition_layout)

        self._image_label = ResizeableLabelWithImage(self)

        self._main_layout.addWidget(self._image_label)
        self.setLayout(self._main_layout)

    def _refresh_all(self):
        list(map(lambda x: x.refresh(), self._refreshable))

    def _read_default_camera_setting(self, setting_name, returned_if_not_found):
        defaults = self._config.get("camera_defaults", {})
        if not defaults:
            logger.warning(f"There are no camera defaults in config")
            return returned_if_not_found
        camera_config = defaults.get(self._camera_name, "")
        if not camera_config:
            logger.warning(f"Could not find defaults for {self._camera_name}")
            return returned_if_not_found
        return camera_config.get(setting_name, returned_if_not_found)

    def _read_default_bin(self):
        return int(self._read_default_camera_setting("default_bin", 1))

    def _read_default_format(self):
        return self._read_default_camera_setting("default_format", "RAW8")

    def _start_continuous_polling(self):
        button: QPushButton = self.sender()
        if button.isChecked():
            button.setStyleSheet("background-color : #228822")
            interval_str = "1s"  # self.continuous_poll_cb.currentText()
            logger.debug(f"Starting to poll for new images with interval {interval_str}")
            interval = int(interval_str[:-1])
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

    #

    #

    # def _refresh_status(self):
    #     is_ok, status = self.requester.get_temp_and_status()
    #     if is_ok:
    #         logger.debug(f"Status = {status}")
    #         self._status_label.setText(status["capture_status"])
    #         self._temp_label.setText(str(status["temperature"]) + "°C")
    #     else:
    #         logger.error(f"Error while getting status from camera!")
    #
    # def _change_polling_interval(self, text_value):
    #     logger.debug(f"Changing polling interval to {text_value}")
    #

    #
    #
    #
   #
    #
    #

    # def add_status_info(self, layout):
    #     get_info = QPushButton("Refresh status", self)
    #     get_info.clicked.connect(self._refresh_status)
    #     self._status_label = QLabel("N/A")
    #     self._temp_label = QLabel("N/A")
    #     is_ok, status = self.requester.get_temp_and_status()
    #     if is_ok:
    #         self._status_label.setText(status["capture_status"])
    #         self._temp_label.setText(str(status["temperature"]) + "°C")
    #     layout.addWidget(QLabel("Capture status:"))
    #     layout.addWidget(self._status_label)
    #     layout.addWidget(QLabel("Temperature:"))
    #     layout.addWidget(self._temp_label)
    #     layout.addWidget(get_info)
    #
    # def add_acquisition(self, layout):
    #
    #     continuous_polling_button = QPushButton("Poll for images continuously", self)
    #     continuous_polling_button.setCheckable(True)
    #     continuous_polling_button.setStyleSheet("background-color : black")
    #     continuous_polling_button.clicked.connect(self._start_continuous_polling)
    #
    #     self.continuous_poll_cb = QComboBox()
    #     self.continuous_poll_cb.addItems(["0.5s", "1s", "2s"])
    #     self.continuous_poll_cb.setCurrentText("1s")
    #     self.continuous_poll_cb.currentTextChanged.connect(self._change_polling_interval)
    #
    #     layout.addWidget(self.get_last_image_button)
    #     layout.addWidget(continuous_polling_button)
    #     layout.addWidget(self.continuous_poll_cb)


    #

    #

    #

    def _get_last_image(self):
        logger.debug("Getting last image")
        send_as_jpg = self._format_chooser.should_send_jpg()
        if send_as_jpg:
            logger.debug("Image will be send as jpg")
            start_time = time.time()
            response = self._requester.get_last_image(send_as_jpg)
            time_elapsed = time.time() - start_time
            logger.debug(f"Time elapsed on receiving response: {time_elapsed}")
            start_time = time.time()
            qImg = createQImageFromJpg(response)
        else:
            logger.debug("Image will be send raw")
            is_ok, (w, h) = self.requester.get_resolution()
            isOk, current_format = self.requester.get_current_format()
            start_time = time.time()
            response = self.requester.get_last_image(self._send_as_jpg)
            time_elapsed = time.time() - start_time
            logger.debug(f"Time elapsed on receiving response: {time_elapsed}")
            start_time = time.time()
            logger.debug("Acquired response!")
            if response is None:
                return
            qImg = createQImageFromBuffer(response.content, [w, h], current_format)

        if qImg is not None:
            logger.debug("Setting new image...")
            self._image_label.set_image(qImg)

        time_elapsed = time.time() - start_time
        logger.debug(f"Time elapsed on processing: {time_elapsed}")

    # def _save_config(self):
    #     save_config(self.config)
    #
    # def _save_to_config(self, d: dict):
    #     self.config.update(d)
    #     self._save_config()
