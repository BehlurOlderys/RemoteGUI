import logging
from PyQt5.QtWidgets import QWidget, QLabel, QSpinBox, QHBoxLayout


logger = logging.getLogger(__name__)


class OffsetDial(QWidget):
    def __init__(self, requester):
        super(OffsetDial, self).__init__()
        self._requester = requester
        self._layout = QHBoxLayout()

        self._offset_spin = QSpinBox()
        self._refresh_impl()
        self._offset_spin.valueChanged.connect(self._changed_offset)

        label = QLabel("Offset:")
        label.setMaximumSize(50, 20)
        self._layout.addWidget(label)
        self._layout.addWidget(self._offset_spin)
        self.setLayout(self._layout)
        self.setMaximumSize(150, 50)

    def _changed_offset(self, value):
        logger.debug(f"Setting offset to value: {value}")
        offset_str = str(value)
        self._requester.set_offset(offset_str)

    def _refresh_impl(self):
        is_ok, offset_raw = self._requester.get_offset()
        if not is_ok:
            logger.error("Could not get current offset value!")
            return
        logger.debug(f"Acquired current offset: {offset_raw}")
        offset = int(offset_raw)
        self._offset_spin.setValue(offset)

    def refresh(self):
        logger.debug("Refreshing offset info...")
        self._refresh_impl()
