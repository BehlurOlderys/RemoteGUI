from PyQt5.QtWidgets import QErrorMessage, QLabel, QMainWindow, QApplication, QVBoxLayout
from camera_controls_view import CameraControlsView
from launcher_view import LauncherView
from config_manager import read_config, init_config
from PyQt5.QtGui import QPixmap, QImage, QIcon
from PyQt5.QtCore import Qt
import sys
import logging
from logging.handlers import RotatingFileHandler
import qdarktheme
from threading import Event


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowIcon(QIcon('logo.png'))
        self.config = read_config()
        self.main_layout = QVBoxLayout()
        self.setWindowTitle("Guiding Launcher")
        self.setGeometry(100, 100, 320, 100)

        self._launcher_view = LauncherView(self.config, self._switch_to_camera, self._error_prompt)
        self.setCentralWidget(self._launcher_view)
        self._kill_event = Event()
        self.show()

    def _switch_to_camera(self, ip, camera_index, camera_name):
        logger.debug(f"Switching to camera: {camera_name}")
        camera_controls_view = CameraControlsView(self.config, ip, camera_index, camera_name, self._error_prompt,
                                                  self._kill_event)
        self.setCentralWidget(camera_controls_view)
        self.setWindowTitle("Remote camera controls")

    def _error_prompt(self, t):
        logger.error(t)
        error_dialog = QErrorMessage(self)
        error_dialog.showMessage(t)

    def _send_kill(self):
        if not self._kill_event.is_set():
            print("========= Sending kill =========")
            self._kill_event.set()

    def closeEvent(self, event):
        print("========= Shutting down! =========")
        self._send_kill()
        event.accept()

    def __del__(self):
        self._send_kill()


def configure_logging(logfile_path):
    default_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] [%(funcName)s():%(lineno)s] [PID:%(process)d] %(message)s",
        "%d/%m/%Y %H:%M:%S")

    file_handler = RotatingFileHandler(logfile_path, maxBytes=10485760, backupCount=300, encoding='utf-8')
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    file_handler.setFormatter(default_formatter)
    console_handler.setFormatter(default_formatter)

    logging.root.setLevel(logging.DEBUG)
    logging.root.addHandler(file_handler)
    logging.root.addHandler(console_handler)


if __name__ == '__main__':
    configure_logging("main_gui.log")
    logger.debug("Logging works")

    init_config()

    logger.debug("Now Qt app should start...")
    app = QApplication(sys.argv)

    qdarktheme.setup_theme()

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
