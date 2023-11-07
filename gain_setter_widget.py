import logging
from PyQt5.QtWidgets import QWidget, QLabel, QSpinBox, QHBoxLayout


logger = logging.getLogger(__name__)


class GainSetter(QWidget):
    def __init__(self, requester):
        super(GainSetter, self).__init__()
        self._requester = requester
        self._layout = QHBoxLayout()
        self._gain_spin = QSpinBox()
        self._gain_spin.setRange(0, 1000)
        self._refresh_impl()

        self._gain_spin.valueChanged.connect(self._changed_gain)

        label = QLabel("Gain:")
        label.setMaximumSize(40, 20)
        self._layout.addWidget(label)
        self._layout.addWidget(self._gain_spin)
        self.setLayout(self._layout)
        self.setMaximumSize(150, 50)

    def _refresh_impl(self):
        is_ok, gain_raw = self._requester.get_gain()
        if not is_ok:
            logger.error("Could not get current gain value!")
            return
        logger.debug(f"Acquired current gain: {gain_raw}")
        gain = int(gain_raw)
        self._gain_spin.setValue(gain)

    def _changed_gain(self, value):
        logger.debug(f"Setting gain to value: {value}")
        gain_str = str(value)
        self._requester.set_gain(gain_str)

    def refresh(self):
        logger.debug("Refreshing gain info...")
        self._refresh_impl()
