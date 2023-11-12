from PyQt5.QtWidgets import QLabel
import logging
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt


logger = logging.getLogger(__name__)


class ResizeableLabelWithImage(QLabel):
    def __init__(self, parent):
        QLabel.__init__(self, parent)
        self._original_image = None
        bg_img = QImage(320, 200, QImage.Format_Grayscale8)
        bg_img.fill(Qt.black)
        self.set_image(bg_img)
        self.setMinimumSize(640, 480)

    def set_image(self, img: QImage):
        self._original_image = QPixmap(img)
        width = self.frameGeometry().width()
        height = self.frameGeometry().height()
        logger.debug(f"Label size is currently: {width}x{height} px")
        qp = self._original_image.scaled(width, height, Qt.KeepAspectRatio)
        self.setPixmap(qp)

    def resizeEvent(self, event):
        if self._original_image is not None:
            pixmap = self._original_image.scaled(self.width(), self.height())
            self.setPixmap(pixmap)
        self.resize(self.width(), self.height())
