import logging
from PyQt5.QtWidgets import QWidget, QLabel, QDoubleSpinBox, QHBoxLayout, QComboBox


logger = logging.getLogger(__name__)


class ExposureDial(QWidget):
    def __init__(self, requester):
        super(ExposureDial, self).__init__()
        self._requester = requester
        self._layout = QHBoxLayout()
        self._exp_spin = QDoubleSpinBox()
        self._exposure_range = "seconds"
        self._exposure_us = 1000000

        self._exp_range_combo = QComboBox()
        self._exp_range_combo.addItems(["seconds", "milliseconds"])
        self._exp_range_combo.setCurrentText("seconds")
        self._exp_range_combo.currentTextChanged.connect(self._changed_time_range)
        self._exp_range_combo.setMaximumSize(100, 20)

        self._refresh_impl()

        self._exp_spin.valueChanged.connect(self._changed_exposure)
        self._exp_spin.setMaximumSize(120, 50)

        label = QLabel("Exposure time:")
        label.setMaximumSize(100, 20)

        self._layout.addWidget(label)
        self._layout.addWidget(self._exp_spin)
        self._layout.addWidget(self._exp_range_combo)

        self.setLayout(self._layout)
        self.setMaximumSize(250, 50)

    def _changed_exposure(self, value):
        self._exposure_us = value * 1000.0 if self._exposure_range == "milliseconds" else value * 1000000.0
        exp_s_str = str(self._exposure_us / 1000000)
        logger.debug(f"Exposure in us = {self._exposure_us}, seconds={exp_s_str}")
        self._requester.set_exposure(exp_s_str)

    def _changed_time_range(self, new_text):
        self._exposure_range = new_text
        new_value = self._exposure_us / 1000000.0 if new_text == "seconds" else self._exposure_us / 1000.0
        self._exp_spin.setValue(new_value)
        logger.debug(f"Exposure range set to: {self._exposure_range}")

    def _refresh_impl(self):
        is_ok, exp_raw = self._requester.get_exposure()
        if not is_ok:
            logger.error("Could not get current exposure value!")
            return
        logger.debug(f"Acquired current exposure: {exp_raw}")
        exp_us = int(exp_raw)
        self._exposure_us = exp_us
        exp_ms = exp_us // 1000
        exp_s = exp_ms // 1000

        self._exp_spin.setDecimals(2)
        self._exp_spin.setRange(0.01, 3600)

        if self._exp_range_combo.currentText() == "seconds":
            self._exp_spin.setValue(exp_s)
        else:
            self._exp_spin.setValue(exp_ms)

    def refresh(self):
        logger.debug("Refreshing exposure info...")
        self._refresh_impl()

