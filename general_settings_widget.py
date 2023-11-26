import logging
from PyQt5.QtWidgets import QWidget, QLabel, QCheckBox, QHBoxLayout, QSpacerItem, QSizePolicy


logger = logging.getLogger(__name__)


class GeneralSettings(QWidget):
    def __init__(self, requester):
        super(GeneralSettings, self).__init__()
        self._requester = requester
        self._layout = QHBoxLayout()

        turn_off_capture_label = QLabel("Turn off capturing on exit?")
        turn_off_capture_label.setMaximumSize(200, 50)

        self._turn_off_capture_checkbox = QCheckBox()
        self._turn_off_capture_checkbox.setChecked(False)
        self._turn_off_capture_checkbox.setMaximumSize(50, 50)

        hspacer = QSpacerItem(20, 40, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self._layout.addWidget(turn_off_capture_label)

        self._layout.addItem(hspacer)
        self._layout.addWidget(self._turn_off_capture_checkbox)

        self.setLayout(self._layout)

    def should_turn_off_capture_on_exit(self):
        return self._turn_off_capture_checkbox.isChecked()
