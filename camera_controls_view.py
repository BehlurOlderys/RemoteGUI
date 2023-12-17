from exposure_dial_widget import ExposureDial
from gain_setter_widget import GainSetter
from binning_radio_widget import BinningRadio
from offset_dial_widget import OffsetDial
from format_chooser_widget import FormatChooser
from temperature_control_widget import TemperatureControl
from image_acquisition_widget import ImageAcquisition
from resizeable_label_with_image import ResizeableLabelWithImage
from camera_requester import CameraRequester
from canvas_widget import CanvasWidget
from utils import start_interval_polling
from general_settings_widget import GeneralSettings


from PyQt5.QtWidgets import QHBoxLayout, QWidget, QVBoxLayout, QPushButton, QTabWidget


import logging
from threading import Event


logger = logging.getLogger(__name__)


def get_widget_refresh_rate_or_none(w):
    logger.debug(f"Checking for refresh rate in {w}")
    if hasattr(w, "refresh_rate_s") and callable(getattr(w, "refresh_rate_s")):
        return w.refresh_rate_s()
    return None


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

    def __del__(self):
        if self._general_settings.should_turn_off_capture_on_exit():
            self._requester.stop_capturing()
        logger.debug("__del__ camera controls view")

    def close(self):
        logger.debug("Closing camera controls view")

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
        self._tabs = QTabWidget()
        self._camera_controls_tab = QWidget()
        self._image_controls_tab = QWidget()

        camera_controls_layout = QVBoxLayout()
        image_controls_layout = QHBoxLayout()

        self._camera_controls_tab.setLayout(camera_controls_layout)
        self._image_controls_tab.setLayout(image_controls_layout)

        self._tabs.addTab(self._camera_controls_tab, "Camera controls")
        self._tabs.addTab(self._image_controls_tab, "Image controls")

        general_stuff = QHBoxLayout()
        self._general_settings: GeneralSettings = self._add_custom_widget(
            general_stuff, GeneralSettings, self._requester)

        exp_gain_off = QHBoxLayout()
        self._add_custom_widget(exp_gain_off, ExposureDial, self._requester)
        self._add_custom_widget(exp_gain_off, GainSetter, self._requester)
        self._add_custom_widget(exp_gain_off, OffsetDial, self._requester)

        format_bin = QHBoxLayout()
        self._format_chooser: FormatChooser = self._add_custom_widget(format_bin, FormatChooser,
                                                                      self._requester, self._read_default_format())
        self._add_custom_widget(format_bin, BinningRadio, self._requester, self._read_default_bin())

        temp_control = QHBoxLayout()
        self._add_custom_widget(temp_control, TemperatureControl, self._requester)

        refresh_layout = QHBoxLayout()
        refresh_button = QPushButton("Refresh parameters", self)
        refresh_button.clicked.connect(self._refresh_all)
        refresh_layout.addWidget(refresh_button)

        self._image_label = ResizeableLabelWithImage(self)

        image_histogram = CanvasWidget()
        image_histogram.setMinimumSize(200, 200)
        image_histogram.setMaximumSize(500, 500)

        acquisition_layout = QHBoxLayout()
        self._add_custom_widget(acquisition_layout,
                                ImageAcquisition,
                                self._requester, self._format_chooser, self._image_label, image_histogram,
                                self._kill_event)

        camera_controls_layout.addLayout(general_stuff)
        camera_controls_layout.addLayout(exp_gain_off)
        camera_controls_layout.addLayout(format_bin)
        camera_controls_layout.addLayout(temp_control)
        camera_controls_layout.addLayout(refresh_layout)
        camera_controls_layout.addLayout(acquisition_layout)

        image_controls_layout.addWidget(image_histogram)

        image_layout = QHBoxLayout()
        image_layout.addWidget(self._image_label)

        self._main_layout.addWidget(self._tabs)
        self._main_layout.addLayout(image_layout)
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
