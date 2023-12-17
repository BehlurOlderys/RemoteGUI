import logging

from PIL.Image import Image
from PyQt5.QtWidgets import QWidget, QVBoxLayout
import matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from io import BytesIO
from PIL import Image
import numpy as np
from numpy import ndarray

matplotlib.use('Qt5Agg')


logger = logging.getLogger(__name__)


class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, width=2, height=1, dpi=50):
        fig = Figure(figsize=(width, height), dpi=dpi)
        fig.patch.set_facecolor('#212121')
        self.axes = fig.add_subplot(111)
        self.axes.set_facecolor('#212121')
        super(MplCanvas, self).__init__(fig)


class CanvasWidget(QWidget):
    def __init__(self, *args, **kwargs):
        super(CanvasWidget, self).__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self._sc = MplCanvas(width=5, height=4, dpi=100)
        self._sc.axes.plot([0, 1, 2, 3, 4], [10, 1, 20, 3, 40])
        layout.addWidget(self._sc)
        self.setLayout(layout)

    def plot_histogram(self, data):
        im: Image = Image.open(BytesIO(data))
        # noinspection PyTypeChecker
        np_array: ndarray = np.asarray(im)
        logger.debug(f"Shape = {np_array.shape}, max = {np.max(np_array)}")
        values, bins = np.histogram(np_array, bins=100)
        bins = bins[1:]
        logger.debug(f"Values = {values.shape}, Bins = {bins.shape}")

        self._sc.axes.cla()
        self._sc.axes.plot(bins, values)
        self._sc.draw()
        logger.debug(f"Histogram updated!")
