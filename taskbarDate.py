from PyQt5.QtWidgets import (
    QApplication, QLabel, QWidget, QMenu, QInputDialog, QDialog, QSpinBox,
    QPushButton, QHBoxLayout, QVBoxLayout, QGridLayout
)
from PyQt5.QtCore import Qt, QTimer, QDate, QPoint
from PyQt5.QtGui import QPainter, QColor, QFont
import os
import sys

def get_app_dir():
    if getattr(sys, 'frozen', False):  # Running as PyInstaller EXE
        return os.path.dirname(sys.executable)
    else:  # Running as script
        return os.path.dirname(os.path.abspath(__file__))

SETTINGS_FILE = "taskbarDate-settings.txt"
WINDOW_WIDTH = 80
WINDOW_HEIGHT = 30

def load_settings(screen_width, screen_height):
    settings = {
        "x": screen_width - WINDOW_WIDTH - 20,
        "y": screen_height - WINDOW_HEIGHT,
    }
    if os.path.exists(os.path.join(get_app_dir(),SETTINGS_FILE)):
        try:
            with open(os.path.join(get_app_dir(),SETTINGS_FILE), "r") as f:
                for line in f:
                    key, value = line.strip().split("=")
                    if key in ("x", "y"):
                        settings[key] = int(value)
        except Exception:
            pass
    return settings

def save_settings(settings):
    with open(os.path.join(get_app_dir(),SETTINGS_FILE), "w") as f:
        f.write(f"x={settings['x']}\n")
        f.write(f"y={settings['y']}\n")

class PositionDialog(QDialog):
    def __init__(self, parent, x, y, max_x, max_y):
        super().__init__(parent)
        self.setWindowTitle("Set Window Position")
        self.setModal(True)
        self.setFixedSize(220, 120)
        self.dragging = False
        self.offset = QPoint()
        self.max_x = max_x
        self.max_y = max_y

        self.x_spin = QSpinBox(self)
        self.x_spin.setRange(0, max_x)
        self.x_spin.setValue(x)
        self.y_spin = QSpinBox(self)
        self.y_spin.setRange(0, max_y)
        self.y_spin.setValue(y)

        self.ok_btn = QPushButton("OK", self)
        self.cancel_btn = QPushButton("Cancel", self)

        layout = QGridLayout()
        layout.addWidget(QLabel("X:"), 0, 0)
        layout.addWidget(self.x_spin, 0, 1)
        layout.addWidget(QLabel("Y:"), 1, 0)
        layout.addWidget(self.y_spin, 1, 1)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout, 2, 0, 1, 2)
        self.setLayout(layout)

        self.x_spin.valueChanged.connect(self.preview_move)
        self.y_spin.valueChanged.connect(self.preview_move)
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)

    def preview_move(self):
        x = self.x_spin.value()
        y = self.y_spin.value()
        self.parent().move(x, y)

class TransparentWindow(QWidget):
    def __init__(self):
        super().__init__()
        screen = QApplication.primaryScreen().geometry()
        self.screen_width = screen.width()
        self.screen_height = screen.height()

        self.settings = load_settings(self.screen_width, self.screen_height)
        self.setGeometry(self.settings["x"], self.settings["y"], WINDOW_WIDTH, WINDOW_HEIGHT)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.label = QLabel(self)
        self.label.setFont(QFont("DejaVu Sans Mono", 9))
        self.label.setStyleSheet("color: white; background: transparent;")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        self.update_label()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_label)
        self.timer.start(60000)  # TODO: set back to 60000 for minute updates

        self.top_timer = QTimer(self)
        self.top_timer.timeout.connect(self.bring_to_front)
        self.top_timer.start(10000) # bring back to front timer

    def bring_to_front(self):
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.raise_()
        self.show()

    def update_label(self):
        today = QDate.currentDate()
        self.label.setText(today.toString("dd.MM.yyyy"))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1)) # QColor(0, 0, 0, 60) to see the box

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("Set Position", self.set_position_dialog)
        menu.addSeparator()
        menu.addAction("Exit", QApplication.quit)
        menu.exec_(event.globalPos())

    def set_position_dialog(self):
        max_x = self.screen_width - WINDOW_WIDTH
        max_y = self.screen_height - WINDOW_HEIGHT
        dlg = PositionDialog(self, self.x(), self.y(), max_x, max_y)
        old_x, old_y = self.x(), self.y()
        if dlg.exec_():
            x = dlg.x_spin.value()
            y = dlg.y_spin.value()
            self.move(x, y)
            self.settings["x"] = x
            self.settings["y"] = y
            save_settings(self.settings)
        else:
            # Restore old position if cancelled
            self.move(old_x, old_y)

    def moveEvent(self, event):
        # Clamp position within screen bounds
        x = min(max(0, self.x()), self.screen_width - WINDOW_WIDTH)
        y = min(max(0, self.y()), self.screen_height - WINDOW_HEIGHT)
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)
        self.settings["x"] = x
        self.settings["y"] = y
        save_settings(self.settings)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TransparentWindow()
    window.show()
    sys.exit(app.exec_())
