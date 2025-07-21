from PyQt5.QtWidgets import (
	QApplication, QLabel, QWidget, QMenu, QSpinBox,
	QPushButton, QHBoxLayout, QGridLayout, QDialog
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

import os
import sys
import threading
import time
import json
from pynput import keyboard

WINDOW_WIDTH = 30
WINDOW_HEIGHT = 30
SETTINGS_FILE = "taskbarRune-settings.json"

plugin_state = {"enabled": False}
RUNE_MAP = {}
MAX_COMBO_LENGTH = 1

# --------- Settings loading from JSON ---------

def get_app_dir():
	return os.path.dirname(getattr(sys, '_MEIPASS', os.path.abspath(__file__)))

def load_settings(screen_width, screen_height):
	global MAX_COMBO_LENGTH, RUNE_MAP

	path = os.path.join(get_app_dir(), SETTINGS_FILE)
	if not os.path.exists(path):
		# Default fallback settings
		default_settings = {
			"x": 1565,
			"y": 1050,
			"rune_map": {
				"a": "ᚪ",
				"b": "ᛒ",
				"c": "ᚳ",
				"d": "ᛞ",
				"e": "ᛖ",
				"f": "ᚠ",
				"g": "ᚷ",
				"G": "ᚸ",
				"h": "ᚻ",
				"i": "ᛁ",
				"j": "ᛄ",
				"J": "ᛡ",
				"k": "ᛣ",
				"K": "ᛤ",
				"l": "ᛚ",
				"m": "ᛗ",
				"n": "ᚾ",
				"o": "ᚩ",
				"p": "ᛈ",
				"q": "ᛢ",
				"r": "ᚱ",
				"s": "ᛋ",
				"t": "ᛏ",
				"u": "ᚢ",
				"v": "ᚠ",
				"w": "ᚹ",
				"x": "ᛉ",
				"y": "ᚣ",
				"z": "ᛇ",
				
				"th": "ᚦ",
				"ng": "ᛝ",
				"oe": "ᛟ",
				"ö": "ᛟ",
				"ae": "ᚫ",
				"ä": "ᚫ",
				"ea": "ᛠ",
				"st": "ᛥ",
				
				",": "᛫",
				".": "᛫",
				":": "᛬",
				"+": "᛭",
			}
		}
		with open(path, "w", encoding="utf-8") as f:
			json.dump(default_settings, f, indent=4, ensure_ascii=False)
		return default_settings

	with open(path, "r", encoding="utf-8") as f:
		settings = json.load(f)

	RUNE_MAP = settings.get("rune_map", {})
	MAX_COMBO_LENGTH = max(len(k) for k in RUNE_MAP.keys()) if RUNE_MAP else 1
	return settings

def save_settings(settings):
	with open(os.path.join(get_app_dir(), SETTINGS_FILE), "r+", encoding="utf-8") as f:
		data = json.load(f)
		data["x"] = settings["x"]
		data["y"] = settings["y"]
		f.seek(0)
		json.dump(data, f, indent=4, ensure_ascii=False)
		f.truncate()

# --------- UI Classes ---------

class PositionDialog(QDialog):
	def __init__(self, parent, x, y, max_x, max_y):
		super().__init__(parent)
		self.setWindowTitle("Set Window Position")
		self.setFixedSize(220, 120)

		self.x_spin = QSpinBox()
		self.x_spin.setRange(0, max_x)
		self.x_spin.setValue(x)

		self.y_spin = QSpinBox()
		self.y_spin.setRange(0, max_y)
		self.y_spin.setValue(y)

		ok_button = QPushButton("OK")
		cancel_button = QPushButton("Cancel")

		layout = QGridLayout()
		layout.addWidget(QLabel("X:"), 0, 0)
		layout.addWidget(self.x_spin, 0, 1)
		layout.addWidget(QLabel("Y:"), 1, 0)
		layout.addWidget(self.y_spin, 1, 1)

		btn_layout = QHBoxLayout()
		btn_layout.addWidget(ok_button)
		btn_layout.addWidget(cancel_button)
		layout.addLayout(btn_layout, 2, 0, 1, 2)

		self.setLayout(layout)

		ok_button.clicked.connect(self.accept)
		cancel_button.clicked.connect(self.reject)

		self.x_spin.valueChanged.connect(self.preview_move)
		self.y_spin.valueChanged.connect(self.preview_move)

	def preview_move(self):
		self.parent().move(self.x_spin.value(), self.y_spin.value())

class TransparentRuneWidget(QWidget):
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
		self.label.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
		self.label.setAlignment(Qt.AlignCenter)
		self.label.setFont(QFont("DejaVu Sans Mono", 11, QFont.Bold))
		self.label.setStyleSheet("QLabel { color: white; background-color: rgba(0, 0, 0, 20); }")

		self.update_label()

		self.timer = QTimer()
		self.timer.timeout.connect(self.bring_to_front)
		self.timer.start(10000)

	def update_label(self):
		self.label.setText("ᚱᛚ" if plugin_state["enabled"] else "RL")

	def toggle_mode(self):
		plugin_state["enabled"] = not plugin_state["enabled"]
		self.update_label()

	def mousePressEvent(self, event):
		if event.button() == Qt.LeftButton:
			self.toggle_mode()

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
			x, y = dlg.x_spin.value(), dlg.y_spin.value()
			self.move(x, y)
			self.settings["x"], self.settings["y"] = x, y
			save_settings(self.settings)
		else:
			self.move(old_x, old_y)

	def moveEvent(self, event):
		x = max(0, min(self.x(), self.screen_width - WINDOW_WIDTH))
		y = max(0, min(self.y(), self.screen_height - WINDOW_HEIGHT))
		self.move(x, y)
		self.settings["x"], self.settings["y"] = x, y
		save_settings(self.settings)

	def bring_to_front(self):
		self.setAttribute(Qt.WA_ShowWithoutActivating, True)
		self.raise_()
		self.show()

# --------- Keyboard Listener ---------

def run_keyboard_listener():
	kb_controller = keyboard.Controller()
	last_two_chars = [None, None]
	ignore_next_chars = []

	def on_press(key):
		nonlocal last_two_chars, ignore_next_chars

		if not plugin_state["enabled"]:
			return

		try:
			if hasattr(key, "char") and key.char and key.char.isprintable():
				c = key.char

				if c in ignore_next_chars:
					ignore_next_chars.remove(c)
					return

				last_two_chars[0] = last_two_chars[1]
				last_two_chars[1] = c
				
				# Only check combo if both are not None
				if last_two_chars[0] is not None and last_two_chars[1] is not None:
					combo = ''.join(last_two_chars)
					if combo in RUNE_MAP and len(combo) == 2:
						kb_controller.press(keyboard.Key.backspace)
						kb_controller.release(keyboard.Key.backspace)
						kb_controller.press(keyboard.Key.backspace)
						kb_controller.release(keyboard.Key.backspace)
						kb_controller.press(RUNE_MAP[combo])
						kb_controller.release(RUNE_MAP[combo])
						ignore_next_chars.append(RUNE_MAP[combo])
						last_two_chars = [None, None]
						return

				if c in RUNE_MAP and len(c) == 1:
					kb_controller.press(keyboard.Key.backspace)
					kb_controller.release(keyboard.Key.backspace)
					kb_controller.press(RUNE_MAP[c])
					kb_controller.release(RUNE_MAP[c])
					ignore_next_chars.append(RUNE_MAP[c])
			else:
				if key == keyboard.Key.backspace:
					return
				last_two_chars[0] = last_two_chars[1]
				last_two_chars[1] = None
			#print(last_two_chars)
			#print(ignore_next_chars)
			
		except Exception as e:
			print("[RunePlugin] Key press error:", e)

	with keyboard.Listener(on_press=on_press) as listener:
		listener.join()

# --------- Main ---------

if __name__ == "__main__":
	threading.Thread(target=run_keyboard_listener, daemon=True).start()
	app = QApplication(sys.argv)
	window = TransparentRuneWidget()
	window.show()
	sys.exit(app.exec_())
