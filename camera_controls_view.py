from PyQt5.QtWidgets import QLabel, QHBoxLayout, QWidget, QVBoxLayout, QPushButton, QComboBox
import logging
from exposure_dial_widget import ExposureDial
from gain_setter_widget import GainSetter
from binning_radio_widget import BinningRadio
import time
from camera_requester import CameraRequester
from config_manager import save_config


logger = logging.getLogger(__name__)


class CameraControlsView(QWidget):
    def __init__(self, config, ip, camera_index, camera_name, error_prompt):
        super(CameraControlsView, self).__init__()
        self._config = config
        self._camera_name = camera_name

        self._requester = CameraRequester(ip, camera_index, error_prompt)
        self._refreshable = []
        self._prepare_ui()

    def _prepare_ui(self):
        self._main_layout = QVBoxLayout()

        exposure_dial = ExposureDial(self._requester)
        gain_setter = GainSetter(self._requester)
        binning_radio = BinningRadio(self._requester, self._read_default_bin())

        self._refreshable.append(exposure_dial)
        self._refreshable.append(gain_setter)
        self._refreshable.append(binning_radio)

        self._main_layout.addWidget(exposure_dial)
        self._main_layout.addWidget(gain_setter)
        self._main_layout.addWidget(binning_radio)

        refresh_layout = QHBoxLayout()
        refresh_button = QPushButton("Refresh parameters", self)
        refresh_button.clicked.connect(self._refresh_all)
        refresh_layout.addWidget(refresh_button)
        self._main_layout.addLayout(refresh_layout)

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


    # def closeEvent(self, event):
    #     print("========= Shutting down! =========")
    #     if not self._polling_event.is_set():
    #         print("========= Stopping polling =========")
    #         self._polling_event.set()
    #     event.accept()
    #
    # def __del__(self):
    #     if not self._polling_event.is_set():
    #         print("========= Stopping polling =========")
    #         self._polling_event.set()
    #

    #
    # def _changed_offset(self, value):
    #     logger.debug(f"Setting offset to value: {value}")
    #     offset_str = str(value)
    #     self.requester.set_offset(offset_str)
    #
    # def _changed_format(self, t):
    #     logger.debug(f"New format chosen: {t}")
    #     self.requester.set_format(t)
    #
    # def _changed_jpg(self, j):
    #     if j == "jpeg":
    #         self._send_as_jpg = True
    #     elif j == "raw":
    #         self._send_as_jpg = False
    #
    #     logger.debug(f"Changed jpeg to: {j}, value = {str(self._send_as_jpg)}")
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
    # def _start_continuous_polling(self):
    #     button: QPushButton = self.sender()
    #     if button.isChecked():
    #         button.setStyleSheet("background-color : #228822")
    #         interval_str = self.continuous_poll_cb.currentText()
    #         logger.debug(f"Starting to poll for new images with interval {interval_str}")
    #         interval = int(interval_str[:-1])
    #         response = self.requester.start_capturing()
    #         logger.debug(f"Start capturing returned: {response.status_code} with content: {response.json()}")
    #         self._polling_event.clear()
    #         interval_polling(self._polling_event, self._get_last_image, interval)
    #         self._continuous_polling = True
    #
    #     else:
    #         self.requester.stop_capturing()
    #         button.setStyleSheet("background-color : black")
    #         self._polling_event.set()
    #         self._continuous_polling = False
    #
    #
    #
   #
    # def add_offset_dial(self, layout):
    #     is_ok, offset_raw = self.requester.get_offset()
    #     if not is_ok:
    #         logger.error("Could not get current offset value!")
    #         return
    #     logger.debug(f"Acquired current offset: {offset_raw}")
    #     offset = int(offset_raw)
    #     self._offset_spin = QSpinBox()
    #     self._offset_spin.setValue(offset)
    #     self._offset_spin.valueChanged.connect(self._changed_offset)
    #
    #     label = QLabel("Offset:")
    #     label.setMaximumSize(50, 20)
    #     layout.addWidget(label)
    #     layout.addWidget(self._offset_spin)
    #
    # def add_format_chooser(self, layout):
    #     self.format_combo = QComboBox()
    #     format_values = self._read_possible_formats()
    #     self.format_combo.addItems(format_values)
    #     self.format_combo.currentTextChanged.connect(self._changed_format)
    #     logger.debug(f"Trying to read default format...")
    #     default_format = self._read_default_format(self.camera_name)
    #     logger.debug(f"Default format = {default_format}")
    #     self.format_combo.setCurrentText(default_format)
    #
    #     self.jpg_combo = QComboBox()
    #     self.jpg_combo.addItems(["raw", "jpeg"])
    #     self.jpg_combo.setCurrentText("raw")
    #     self.jpg_combo.currentTextChanged.connect(self._changed_jpg)
    #
    #     format_label = QLabel("Image type:")
    #     format_label.setMaximumSize(100, 20)
    #
    #     transfer_label = QLabel("Send as:")
    #     transfer_label.setMaximumSize(60, 20)
    #
    #     layout.addWidget(format_label)
    #     layout.addWidget(self.format_combo)
    #     layout.addWidget(transfer_label)
    #     layout.addWidget(self.jpg_combo)
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
    #     self.get_last_image_button = QPushButton("Get last image", self)
    #     self.get_last_image_button.clicked.connect(self._get_last_image)
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
    # def _init_guiding(self, camera_index, camera_name, camera_ip):
    #     self.camera_index = camera_index
    #     self.camera_name = camera_name
    #     self.camera_ip = camera_ip
    #     self.requester = CameraRequester(self.camera_ip, self.camera_index, self._error_prompt)
    #
    #     logger.debug("Closing myself...")
    #     self.main_layout.removeWidget(self.main_widget)
    #     self.main_widget.setParent(None)
    #     self.main_widget = None
    #     self.close()
    #     logger.debug("...closed")
    #
    #     self.setWindowTitle("Guiding")
    #     self.setGeometry(100, 100, 400, 400)
    #     self.main_widget = QWidget(self)
    #
    #     logger.debug("Adding new widgets...")
    #     guiding_layout = QVBoxLayout()
    #
    #     bin_layout = QGridLayout()
    #     exposure_layout = QHBoxLayout()
    #     offset_layout = QHBoxLayout()
    #     format_layout = QHBoxLayout()
    #     status_info_layout = QHBoxLayout()
    #     acquisition_layout = QHBoxLayout()
    #
    #     self.add_binning_radio(bin_layout)
    #     self.add_exposure_dial(exposure_layout)
    #     self.add_offset_dial(offset_layout)
    #     self.add_format_chooser(format_layout)
    #     self.add_status_info(status_info_layout)
    #     self.add_acquisition(acquisition_layout)
    #
    #     guiding_layout.addLayout(bin_layout)
    #     guiding_layout.addLayout(exposure_layout)
    #     guiding_layout.addLayout(self._gain_setter.get_layout())
    #     guiding_layout.addLayout(offset_layout)
    #     guiding_layout.addLayout(format_layout)
    #     guiding_layout.addLayout(status_info_layout)
    #     guiding_layout.addLayout(acquisition_layout)
    #
    #     self.image_label = ResizeableLabelWithImage(self)
    #     guiding_layout.addWidget(self.image_label)
    #
    #     self.main_widget.setLayout(guiding_layout)
    #     logger.debug("Setting central widget")
    #     self.setCentralWidget(self.main_widget)
    #     self.show()
    #
    # def _read_possible_formats(self):
    #     response = self.requester.get_formats()
    #     if response is None:
    #         logger.error("Could not read formats from camera")
    #         return []
    #     formats = response.json()["value"]
    #     logger.debug(f"Formats = {formats}")
    #     return formats
    #
    # def createQImageFromJpg(self, response):
    #     logger.debug(f"Creating jpeg image from response...")
    #     image = QImage()
    #     image.loadFromData(response.content)
    #     logger.debug(f"...succeeded!")
    #     return image
    #
    # def createQImageFromBuffer(self, content, resolution, format):
    #     logger.debug(f"Creating image with format {format}")
    #     is16b = (format == "RAW16")
    #     bufferType = np.uint16 if is16b else np.uint8
    #     imageFormat = QImage.Format_Grayscale16 if is16b else QImage.Format_Grayscale8
    #
    #     img = np.frombuffer(content, dtype=bufferType)
    #     w, h = resolution
    #     logger.debug(f"Reshaping into {w}x{h}...")
    #     original_img = img.reshape(w, h)
    #     logger.debug(f"dimension = {original_img.shape}, Max = {np.max(original_img)}, min = {np.min(original_img)}")
    #     final_img = normalize_image(original_img, is16b=is16b)
    #     logger.debug("Normalized!")
    #     qImg = QImage(final_img.data, final_img.shape[0], final_img.shape[1], imageFormat)
    #     return qImg
    #
    # def _get_last_image(self):
    #     if not self._send_as_jpg:
    #         is_ok, (w, h) = self.requester.get_resolution()
    #         isOk, current_format = self.requester.get_current_format()
    #         start_time = time.time()
    #         response = self.requester.get_last_image(self._send_as_jpg)
    #         time_elapsed = time.time() - start_time
    #         logger.debug(f"Time elapsed on receiving response: {time_elapsed}")
    #         start_time = time.time()
    #         logger.debug("Acquired response!")
    #         if response is None:
    #             return
    #
    #         logger.debug(response.content[:1024])
    #         qImg = self.createQImageFromBuffer(response.content, [w, h], current_format)
    #     else:
    #         start_time = time.time()
    #         response = self.requester.get_last_image(self._send_as_jpg)
    #         time_elapsed = time.time() - start_time
    #         logger.debug(f"Time elapsed on receiving response: {time_elapsed}")
    #         start_time = time.time()
    #         qImg = self.createQImageFromJpg(response)
    #
    #     if qImg is not None:
    #         self.image_label.set_image(qImg)
    #
    #     # self.image_label.setScaledContents(True)
    #     time_elapsed = time.time() - start_time
    #     logger.debug(f"Time elapsed on processing: {time_elapsed}")

    # def _read_default_format(self, camera_name):
    #     return self._read_default_camera_setting(camera_name, "default_format", "RAW8")
    #
    # def _save_config(self):
    #     save_config(self.config)
    #
    # def _save_to_config(self, d: dict):
    #     self.config.update(d)
    #     self._save_config()
