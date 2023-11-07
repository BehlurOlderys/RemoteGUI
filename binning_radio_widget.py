import logging
from PyQt5.QtWidgets import QWidget, QLabel, QRadioButton, QGridLayout


logger = logging.getLogger(__name__)


class BinningRadio(QWidget):
    def __init__(self, requester, default_bin):
        super(BinningRadio, self).__init__()
        self._requester = requester
        self._default_bin = default_bin

        self._layout =  QGridLayout()
        self._radios = []
        label = QLabel("Binning:")
        label.setMaximumSize(100, 20)

        possible_bins = self._requester.get_possible_binning()

        for index, binning in enumerate(possible_bins):
            logger.debug(f"Found binning: x{binning}")
            radiobutton = QRadioButton(f"x{binning}", self)
            self._radios.append(radiobutton)
            radiobutton.toggled.connect(self._changed_binning)
            if binning == self._default_bin:
                logger.debug(f"Setting default binning={binning}")
                radiobutton.setChecked(True)

            self._layout.addWidget(radiobutton, 0, index + 1)
        self._layout.addWidget(label, 0, 0)

        self.setLayout(self._layout)
        self.setMaximumSize(300, 50)

    def _changed_binning(self):
        radio_button = self.sender()
        if radio_button.isChecked():
            bin_value = int(radio_button.text().split("x")[-1])
            logger.debug(f"Chosen binning: {bin_value}")
            self._requester.set_binning(bin_value)

    def _refresh_impl(self):
        pass  # TODO when get_binx implemented

    def refresh(self):
        logger.debug("Refreshing binning info...")
        self._refresh_impl()
