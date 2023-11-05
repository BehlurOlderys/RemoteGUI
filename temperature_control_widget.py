import logging
from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QSpinBox
from PyQt5.QtCore import Qt
from camera_requester import CameraRequester


logger = logging.getLogger(__name__)


class TemperatureControl(QWidget):
    def __init__(self, requester):
        super(TemperatureControl, self).__init__()
        self._requester: CameraRequester = requester
        self._layout = QHBoxLayout()

        self._current_temp_label = QLabel("-")
        self._cooler_on_button = QPushButton("Turn cooler on")

        self._layout.addWidget(QLabel("Current temp:"), alignment=Qt.AlignRight)
        self._layout.addWidget(self._current_temp_label, alignment=Qt.AlignLeft)

        is_ok, can_turn_on = self._requester.get_can_turn_on_cooler()
        logger.debug(f"Is ok? {is_ok}, Can turn cooler on: {can_turn_on}")
        if is_ok and can_turn_on:
            self._cooler_on_button.setCheckable(True)
            self._cooler_on_button.clicked.connect(self._turn_cooler_on)
        else:
            self._cooler_on_button.setDisabled(True)

        self._layout.addWidget(self._cooler_on_button)
        self._refresh_impl()

        set_temp_spin = QSpinBox()
        is_ok, can_set_temp = self._requester.get_can_set_temp()

        if not is_ok:
            set_temp_spin.setDisabled(True)
        elif can_set_temp:
            is_ok, set_temp = self._requester.get_set_temp()
            if is_ok:
                set_temp_spin.setValue(int(set_temp))
            set_temp_spin.valueChanged.connect(self._changed_set_temp)

        self._layout.addWidget(QLabel("Target temperature:"), alignment=Qt.AlignRight)
        self._layout.addWidget(set_temp_spin, alignment=Qt.AlignLeft)
        self._layout.addWidget(QLabel("°C"), alignment=Qt.AlignLeft)

        self.setLayout(self._layout)

    def _turn_cooler_on(self):
        button: QPushButton = self.sender()
        if button.isChecked():
            self._requester.set_cooler_on(True)
        else:
            self._requester.set_cooler_on(False)

    def _changed_set_temp(self, value: int):
        self._requester.set_set_temp(value)

    def _refresh_impl(self):
        is_ok, temp_raw = self._requester.get_temperature()
        if not is_ok:
            logger.error("Could not get current temperature value!")
            return

        self._current_temp_label.setText(str(temp_raw) + "°C")
        is_ok, is_on = self._requester.get_cooler_on()
        if is_ok:
            is_on = bool(is_on)
            logger.debug(f"Cooler is now on?: {is_on}")
            if is_on:
                self._cooler_on_button.setChecked(True)
            else:
                self._cooler_on_button.setChecked(False)

    def refresh(self):
        logger.debug("Refreshing temperature info...")
        self._refresh_impl()

    @staticmethod
    def refresh_rate_s():
        return 10
