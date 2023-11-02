from PyQt5.QtWidgets import QInputDialog, QLabel, QLineEdit, QHBoxLayout, QWidget, QVBoxLayout, QPushButton, QComboBox
import logging
from camera_requester import port_for_cameras, standalone_get_request, standalone_post_request
from config_manager import save_config


logger = logging.getLogger(__name__)


class LauncherView(QWidget):
    def __init__(self, config, connect_callback, error_prompt):
        super(LauncherView, self).__init__()
        self._config = config
        self._connect_callback = connect_callback
        self._error_prompt = error_prompt

        self._prepare_ui()

    def _prepare_ui(self):
        self._main_layout = QVBoxLayout()
        layout2 = QHBoxLayout()
        layout3 = QHBoxLayout()
        layout4 = QHBoxLayout()
        layout5 = QHBoxLayout()

        self._preset_ip_combo = QComboBox()
        self._preset_ip_items = self._read_preset_ips()
        self._preset_ip_combo.addItems(self._preset_ip_items.keys())
        self._preset_ip_combo.currentTextChanged.connect(self._load_ip_from_preset)

        layout2.addWidget(QLabel('Enter IP:', self))

        placeholder_text = self._get_ip_initial_text()
        self._ip_edit = QLineEdit(self)
        self._ip_edit.setInputMask("000.000.000.000")
        self._ip_edit.setText(placeholder_text)

        layout2.addWidget(self._ip_edit)

        save_ip_button = QPushButton("save as...", self)
        save_ip_button.clicked.connect(self._save_preset_ip_in_config)
        layout2.addWidget(save_ip_button)

        self._main_layout.addLayout(layout2)

        layout3.addWidget(QLabel('Or choose saved:', self))
        layout3.addWidget(self._preset_ip_combo)

        self._main_layout.addLayout(layout3)

        self._camera_chooser_combo = QComboBox()

        connect_ip_button = QPushButton("Get cameras list", self)
        connect_ip_button.clicked.connect(self._get_cameras_list)
        layout4.addWidget(connect_ip_button)
        self._main_layout.addLayout(layout4)

        self._connect_camera_button = QPushButton("Go!", self)
        self._connect_camera_button.setEnabled(False)
        self._connect_camera_button.clicked.connect(self._connect_to_camera)
        layout5.addWidget(QLabel("Choose camera:", self))
        layout5.addWidget(self._camera_chooser_combo)
        layout5.addWidget(self._connect_camera_button)
        self._main_layout.addLayout(layout5)

        self.setLayout(self._main_layout)

    def _save_to_config(self, d: dict):
        self._config.update(d)
        save_config(self._config)

    def _get_ip_initial_text(self):
        last_used_ip = self._config.get("last_used_ip", "")
        logger.debug(f"Obtained last used ip from config: {last_used_ip}")
        return last_used_ip

    def _read_preset_ips(self):
        d = {"": ""}
        d.update(self._config.get("saved_ips", {}))
        logger.debug(f"Read preset ids = {d}")
        return d

    def _load_ip_from_preset(self, t):
        new_ip = self._preset_ip_items[t]
        logger.debug(f"New ip chosen from preset {t}: {new_ip}")
        self._ip_edit.setText(new_ip)

    def _save_preset_ip_in_config(self):
        ip_alias, dialog_ok = QInputDialog.getText(self, 'Save IP', 'Save current ip as:')
        if dialog_ok:
            new_config_entry = {"saved_ips": {ip_alias: self._ip_edit.text()}}
            logger.debug(f"Saving new config entry: {new_config_entry}")
            self._save_to_config(new_config_entry)

    def _get_cameras_list(self):
        try_ip = self._ip_edit.text()
        full_url = f"http://{try_ip}:{port_for_cameras}/cameras_list"
        response = standalone_get_request(full_url, self._error_prompt)
        if response is None:
            return

        self._save_to_config({"last_used_ip": try_ip})
        cameras_list = response.json()["cameras"]
        logger.debug(f"Successfully got list of cameras at {try_ip} : {cameras_list}")
        self._camera_chooser_combo.clear()
        self._camera_chooser_combo.addItems(cameras_list)
        self._connect_camera_button.setEnabled(len(cameras_list) > 0)

    def _connect_to_camera(self):
        camera_name = self._camera_chooser_combo.currentText()
        camera_index = self._camera_chooser_combo.currentIndex()
        current_ip = self._ip_edit.text()
        logger.debug(f"Connecting to camera {camera_name} at {current_ip}")

        url = f"http://{current_ip}:{port_for_cameras}/camera/{camera_index}/init_camera"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        data = {}

        logger.debug(f"About to call POST...")
        response = standalone_post_request(url, headers, data, self._error_prompt)
        if response is not None and response.status_code == 200:
            # self._init_guiding(camera_index, camera_name, current_ip)
            self._connect_callback(current_ip, camera_index, camera_name)
