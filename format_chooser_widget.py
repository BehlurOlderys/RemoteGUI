import logging
from PyQt5.QtWidgets import QWidget, QLabel, QComboBox, QHBoxLayout


logger = logging.getLogger(__name__)


class FormatChooser(QWidget):
    def __init__(self, requester, default_format):
        super(FormatChooser, self).__init__()
        self._requester = requester
        self._layout = QHBoxLayout()
        self._send_as_jpg = True

        self.format_combo = QComboBox()
        format_values = self._read_possible_formats()
        self.format_combo.addItems(format_values)
        self.format_combo.currentTextChanged.connect(self._changed_format)
        logger.debug(f"Default format = {default_format}")
        self.format_combo.setCurrentText(default_format)

        self.jpg_combo = QComboBox()
        self.jpg_combo.addItems(["jpg", "raw"])
        self.jpg_combo.setCurrentText("raw")
        self.jpg_combo.currentTextChanged.connect(self._changed_jpg)

        format_label = QLabel("Image type:")
        format_label.setMaximumSize(100, 20)

        transfer_label = QLabel("Send as:")
        transfer_label.setMaximumSize(60, 20)

        self._layout.addWidget(format_label)
        self._layout.addWidget(self.format_combo)
        self._layout.addWidget(transfer_label)
        self._layout.addWidget(self.jpg_combo)

        self.setLayout(self._layout)
        self.setMaximumSize(300, 50)

    def _read_possible_formats(self):
        is_ok, formats = self._requester.get_formats()
        if not is_ok:
            return None
        logger.debug(f"Formats = {formats}")
        return formats

    def _changed_format(self, t):
        logger.debug(f"New format chosen: {t}")
        self._requester.set_format(t)

    def _changed_jpg(self, j):
        if j == "jpg":
            self._send_as_jpg = True
        elif j == "raw":
            self._send_as_jpg = False

        logger.debug(f"Changed jpg to: {j}, value = {str(self._send_as_jpg)}")

    def should_send_jpg(self):
        return self._send_as_jpg

    def refresh(self):
        pass
