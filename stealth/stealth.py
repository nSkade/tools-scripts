import sys
import os
import psutil
import win32gui
import win32process
import win32con
import ctypes
import traceback
import json
import time

from ctypes import wintypes, POINTER, c_ubyte, byref, windll, c_uint

from PyQt5.QtWidgets import (
	QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
	QScrollArea, QLineEdit, QPushButton, QFrame, QSizePolicy,
	QSystemTrayIcon, QMenu, QAction, QMessageBox, QDialog, QCheckBox,
	QListWidget, QListWidgetItem, QInputDialog, QSpinBox, QStyleFactory
)
from PyQt5.QtCore import (
	Qt, QTimer, pyqtSignal, QSettings, QThread, QObject, 
	QModelIndex, QSize, QVariant
)
from PyQt5.QtGui import QPainter, QPixmap, QIcon

from PyQt5.QtNetwork import QLocalServer, QLocalSocket

try:
	from PyQt5.QtWinExtras import QtWin
except ImportError:
	class DummyQtWin:
		def fromHICON(*args, **kwargs):
			return QPixmap()
	QtWin = DummyQtWin()

# --- Windows API Constants and Functions (Unchanged) ---
LWA_ALPHA = 0x00000002
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000

ICON_FILENAME = "icon.png"
SETTINGS_FILE = "stealth_settings.json"
SINGLE_INSTANCE_SERVER_NAME = "StealthApp_SingleInstance_f8d4e7g3h2" 

GetLayeredWindowAttributes = windll.user32.GetLayeredWindowAttributes
GetLayeredWindowAttributes.restype = wintypes.BOOL
GetLayeredWindowAttributes.argtypes = [
	wintypes.HWND,
	POINTER(wintypes.COLORREF),
	POINTER(c_ubyte),
	POINTER(wintypes.DWORD)
]

DEFAULT_SETTINGS = {
	"display_exe_name": False,
	"pinned_substrings": ["chrome.exe", "discord"],
	"ignored_substrings":[],
	"opacity_rules": [
		# Example Rule:
		# {"substring": "steam", "exe": "steam.exe", "opacity": 230}
	]
}
# --------------------------------------------------------

# --- Utility Functions (Mostly Unchanged) ---
def get_app_settings_path():
	"""
	Returns the path to the user-editable settings file (stealth_settings.json).
	Looks next to the EXE when bundled, or next to the .py script when run directly.
	"""
	if getattr(sys, 'frozen', False):
		# Running in a PyInstaller bundle (EXE) - use the executable's directory
		base_path = os.path.abspath(os.path.dirname(sys.executable))
	else:
		# Running as a script (.py) - use the script's directory
		base_path = os.path.abspath(os.path.dirname(__file__))
	
	return os.path.join(base_path, SETTINGS_FILE)

def load_settings():
	settings = DEFAULT_SETTINGS.copy()
	settings_path = get_app_settings_path()
	if os.path.exists(settings_path):
		try:
			with open(settings_path, "r") as f:
				loaded_settings = json.load(f)
				settings.update(loaded_settings)
		except Exception as e:
			print(f"Error loading settings: {e}")
			pass
	return settings

def save_settings(settings):
	settings_path = get_app_settings_path()
	try:
		# Clean up any empty/invalid rules before saving
		settings["opacity_rules"] = [
			r for r in settings.get("opacity_rules", []) 
			if r.get("substring") or r.get("exe")
		]
		with open(settings_path, "w") as f:
			json.dump(settings, f, indent=4)
	except Exception as e:
		print(f"Error saving settings: {e}")
		QMessageBox.critical(None, "Settings Error", f"Failed to save settings to {SETTINGS_FILE}:\n{e}")

def resource_path(relative_path):
	"""
	Returns the path to a bundled resource file (like an icon).
	Uses sys._MEIPASS when bundled by PyInstaller, or the script directory otherwise.
	(This function is already correct for internal files.)
	"""
	try:
		base_path = sys._MEIPASS
	except Exception:
		base_path = os.path.abspath(os.path.dirname(__file__))

	return os.path.join(base_path, relative_path)

def set_window_opacity(hwnd, opacity):
	style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
	win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, style | WS_EX_LAYERED)
	ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, opacity, LWA_ALPHA)

def get_window_opacity(hwnd):
	style = win32gui.GetWindowLong(hwnd, GWL_EXSTYLE)
	if not (style & WS_EX_LAYERED):
		return 255

	color_key = wintypes.COLORREF(0)
	alpha = c_ubyte(0)
	flags = wintypes.DWORD(0)

	success = GetLayeredWindowAttributes(
		hwnd,
		byref(color_key),
		byref(alpha),
		byref(flags)
	)

	if success and (flags.value & LWA_ALPHA):
		return alpha.value
	else:
		return 255

def get_visible_windows():
	pid_windows = {}

	def enum_windows_proc(hwnd, lParam):
		if win32gui.IsWindowVisible(hwnd):
			_, pid = win32process.GetWindowThreadProcessId(hwnd)
			title = win32gui.GetWindowText(hwnd).strip()
			if title:
				pid_windows.setdefault(pid, []).append((hwnd, title))
		return True

	win32gui.EnumWindows(enum_windows_proc, None)
	return pid_windows

def get_window_exe_info(hwnd):
	try:
		_, pid = win32process.GetWindowThreadProcessId(hwnd)
		proc = psutil.Process(pid)
		exe_name = proc.name() if proc.name() else ""
		return exe_name
	except (psutil.NoSuchProcess, Exception):
		return ""

# Helper function to check if a window matches an opacity rule
def check_rule_match(title_lower, exe_name_lower, rule):
	rule_sub = rule.get("substring", "").lower()
	rule_exe = rule.get("exe", "").lower()
	
	match_sub = not rule_sub or rule_sub in title_lower
	match_exe = not rule_exe or rule_exe == exe_name_lower
	
	# Rule must have at least one valid criterion, and both criteria must match (if specified)
	if (rule_sub or rule_exe) and match_sub and match_exe:
		return True
	return False

# --------------------------------------------------------

# --- Custom Qt Widgets ---

def get_icon_from_exe(exe_path):
	hIcon_big = wintypes.HANDLE()
	hIcon_small = wintypes.HANDLE()

	try:
		result = windll.shell32.ExtractIconExW(
			exe_path,
			0,
			byref(hIcon_big),
			byref(hIcon_small),
			1
		)

		if result <= 0: return None

		hIcon = hIcon_big.value if hIcon_big.value else hIcon_small.value

		if hIcon:
			pixmap = QtWin.fromHICON(hIcon)

			if hIcon_big.value: windll.user32.DestroyIcon(hIcon_big.value)
			if hIcon_small.value and hIcon_small.value != hIcon_big.value: windll.user32.DestroyIcon(hIcon_small.value)

			if not pixmap.isNull(): return pixmap

		return None

	except Exception:
		if hIcon_big.value: windll.user32.DestroyIcon(hIcon_big.value)
		if hIcon_small.value and hIcon_small.value != hIcon_big.value: windll.user32.DestroyIcon(hIcon_small.value)
		return None


def get_window_icon_pixmap(hwnd):
	icon_handle = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_SMALL, 0)
	if not icon_handle:
		icon_handle = win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_BIG, 0)

	if not icon_handle:
		icon_handle = win32gui.GetClassLong(hwnd, win32con.GCL_HICON)

	if icon_handle:
		try:
			pixmap = QtWin.fromHICON(icon_handle)
			if not pixmap.isNull(): return pixmap
		except Exception:
			pass

	try:
		_, pid = win32process.GetWindowThreadProcessId(hwnd)
		proc = psutil.Process(pid)
		exe_path = proc.exe()

		if exe_path and os.path.isfile(exe_path):
			pixmap = get_icon_from_exe(exe_path)

			if pixmap and not pixmap.isNull(): return pixmap
	except (psutil.NoSuchProcess, Exception):
		pass

	return None

class NoWheelSlider(QSlider):
	def wheelEvent(self, event):
		event.ignore()


class MarqueeLabel(QLabel):
	def __init__(self, text="", parent=None, speed=150):
		super().__init__(text, parent)
		self.setText(text)
		self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
		self.setMinimumWidth(1)
		self.offset = 0
		self.speed = speed
		self.timer = QTimer(self)
		self.timer.timeout.connect(self.update_offset)
		self.timer.start(self.speed)

	def update_offset(self):
		if self.fontMetrics().width(self.text()) > self.width():
			self.offset -= 2
			if abs(self.offset) > self.fontMetrics().width(self.text()):
				self.offset = self.width()
			self.update()
		else:
			self.offset = 0
			self.update()

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setPen(self.palette().color(self.foregroundRole()))
		text = self.text()
		fm = self.fontMetrics()
		text_width = fm.width(text)
		if text_width <= self.width():
			painter.drawText(self.rect(), Qt.AlignLeft | Qt.AlignVCenter, text)
		else:
			painter.drawText(self.offset, int((self.height() + fm.ascent() - fm.descent()) / 2), text)
		painter.end()

# --------------------------------------------------------

# --- Opacity Worker Thread ---
class OpacityWorker(QObject):
	set_opacity_signal = pyqtSignal(int, int) # (hwnd, opacity)
	update_gui_signal = pyqtSignal()

	def __init__(self, settings, parent=None):
		super().__init__(parent)
		self._settings = settings
		self._running = True
		self._active_windows = set()

	def run(self):
		while self._running:
			self.check_new_windows()
			time.sleep(1) # Check every 1 second

	def stop(self):
		self._running = False

	def check_new_windows(self):
		try:
			# Load the latest rules from the shared settings object
			rules = self._settings.get("opacity_rules", [])
			
			if not rules:
				return

			current_windows = get_visible_windows()
			
			# List of visible HWNDs to use for cleanup
			visible_hws = set() 

			for pid, window_list in current_windows.items():
				for hwnd, title in window_list:
					visible_hws.add(hwnd)
					
					if hwnd not in self._active_windows:
						exe_name = get_window_exe_info(hwnd)
						title_lower = title.lower()
						exe_name_lower = exe_name.lower()
						
						for rule in rules:
							if check_rule_match(title_lower, exe_name_lower, rule):
								opacity = rule.get("opacity", 255)
								
								# Check current opacity before setting (optional optimization)
								if get_window_opacity(hwnd) != opacity:
									self.set_opacity_signal.emit(hwnd, opacity)
									
								self._active_windows.add(hwnd)
								break

			# Cleanup: remove closed windows from tracking set for efficiency
			self._active_windows = self._active_windows.intersection(visible_hws)
							
		except Exception as e:
			# Log thread errors silently to avoid crashing the GUI
			# print(f"Opacity worker error: {e}") 
			pass

# --------------------------------------------------------

class OpacityRuleWidget(QWidget):
	# Custom widget for a single opacity rule entry in the QListWidget
	def __init__(self, rule_data, parent=None):
		super().__init__(parent)
		layout = QHBoxLayout(self)
		layout.setContentsMargins(5, 5, 5, 5)
		layout.setSpacing(5)
		
		self.rule = rule_data

		# Substring Label/Input
		self.sub_label = QLabel(f"Title Substring: **{self.rule.get('substring', '-')}**")
		self.sub_label.setStyleSheet("font-weight: normal;")
		layout.addWidget(self.sub_label, stretch=3)
		
		# EXE Name Label/Input
		self.exe_label = QLabel(f"EXE Name: **{self.rule.get('exe', '-')}**")
		self.exe_label.setStyleSheet("font-weight: normal;")
		layout.addWidget(self.exe_label, stretch=3)
		
		# Opacity Label
		self.op_label = QLabel(f"Opacity: **{self.rule.get('opacity', 255)}**")
		self.op_label.setStyleSheet("font-weight: bold;")
		layout.addWidget(self.op_label, stretch=1)
		
		self.setLayout(layout)
		self.setMinimumHeight(40)

	def get_rule_data(self):
		return self.rule


class SettingsDialog(QDialog):
	settings_updated = pyqtSignal()

	def __init__(self, app_settings, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Settings")
		self.resize(800, 650) # INCREASED WIDTH to accommodate two side-by-side lists
		self.current_settings = app_settings
		
		layout = QVBoxLayout(self)
		
		# --- General Settings Group ---
		layout.addWidget(QLabel("### General Settings"))
		general_group = QVBoxLayout()
		self.display_exe_checkbox = QCheckBox("Display Executable Name Instead of Window Title")
		self.display_exe_checkbox.setChecked(self.current_settings.get("display_exe_name", DEFAULT_SETTINGS["display_exe_name"]))
		general_group.addWidget(self.display_exe_checkbox)
		layout.addLayout(general_group)
		layout.addSpacing(10)
		
		# --- Pinned & Ignored Substrings Management (Side-by-Side) ---
		
		# 1. Pinned (Favorites) List
		substrings_hbox = QHBoxLayout()
		
		# LEFT COLUMN: Pinned Substrings
		pinned_vbox = QVBoxLayout()
		pinned_vbox.addWidget(QLabel("### 1. Pinned Substrings (Manual Order)"))
		pinned_vbox.addWidget(QLabel("Drag & Drop to reorder. Double-click to edit."))
		
		pin_layout = QHBoxLayout()
		self.pin_list = QListWidget()
		self.pin_list.setSelectionMode(QListWidget.SingleSelection)
		self.pin_list.setMinimumHeight(180)
		self.pin_list.setDragDropMode(QListWidget.InternalMove)
		self.pin_list.setDragEnabled(True)
		self.pin_list.setAcceptDrops(True)
		self.pin_list.setDropIndicatorShown(True)
		self.pin_list.itemDoubleClicked.connect(self.edit_substring) 
		pin_layout.addWidget(self.pin_list, stretch=1)

		button_column_pin = QVBoxLayout()
		self.add_pin_btn = QPushButton("➕ Add")
		self.add_pin_btn.clicked.connect(self.add_pinned_substring) # Renamed
		
		self.remove_pin_btn = QPushButton("❌ Remove")
		self.remove_pin_btn.clicked.connect(self.remove_pinned_substring) # Renamed
		
		button_column_pin.addWidget(self.add_pin_btn)
		button_column_pin.addWidget(self.remove_pin_btn)
		button_column_pin.addStretch(1) 
		
		pin_layout.addLayout(button_column_pin)
		pinned_vbox.addLayout(pin_layout)
		substrings_hbox.addLayout(pinned_vbox, stretch=1) # Add Pinned to HBox
		
		# RIGHT COLUMN: Ignored Substrings
		ignored_vbox = QVBoxLayout()
		ignored_vbox.addWidget(QLabel("### 2. Ignored Substrings (Not Shown)")) # NEW HEADING
		ignored_vbox.addWidget(QLabel("Windows matching these will be hidden.")) # NEW HINT
		
		ignore_layout = QHBoxLayout()
		self.ignore_list = QListWidget() # NEW LIST
		self.ignore_list.setSelectionMode(QListWidget.SingleSelection)
		self.ignore_list.setMinimumHeight(180)
		self.ignore_list.itemDoubleClicked.connect(self.edit_ignored_substring) # NEW CONNECT
		ignore_layout.addWidget(self.ignore_list, stretch=1)

		button_column_ignore = QVBoxLayout()
		self.add_ignore_btn = QPushButton("➕ Add") # NEW BUTTON
		self.add_ignore_btn.clicked.connect(self.add_ignored_substring) # NEW CONNECT
		
		self.remove_ignore_btn = QPushButton("❌ Remove") # NEW BUTTON
		self.remove_ignore_btn.clicked.connect(self.remove_ignored_substring) # NEW CONNECT
		
		button_column_ignore.addWidget(self.add_ignore_btn)
		button_column_ignore.addWidget(self.remove_ignore_btn)
		button_column_ignore.addStretch(1) 
		
		ignore_layout.addLayout(button_column_ignore)
		ignored_vbox.addLayout(ignore_layout)
		substrings_hbox.addLayout(ignored_vbox, stretch=1) # Add Ignored to HBox
		
		# Add the HBox to the main layout
		layout.addLayout(substrings_hbox)

		layout.addSpacing(15)

		# --- Opacity Rules Management (Automatic Opacity) ---
		layout.addWidget(QLabel("### 3. Automatic Opacity Rules")) # Updated Heading Number
		layout.addWidget(QLabel("Rule with matching Substring AND EXE Name applies opacity."))
		
		rule_layout = QHBoxLayout()
		self.rule_list = QListWidget()
		self.rule_list.setSelectionMode(QListWidget.SingleSelection)
		self.rule_list.setMinimumHeight(180)
		# Opacity rules order doesn't matter, so no drag/drop here
		self.rule_list.itemDoubleClicked.connect(self.edit_rule)
		rule_layout.addWidget(self.rule_list, stretch=1)

		button_column_rule = QVBoxLayout()
		self.add_rule_btn = QPushButton("➕ Add Rule")
		self.add_rule_btn.clicked.connect(self.add_rule)
		
		self.remove_rule_btn = QPushButton("❌ Remove Rule")
		self.remove_rule_btn.clicked.connect(self.remove_rule)
		
		button_column_rule.addWidget(self.add_rule_btn)
		button_column_rule.addWidget(self.remove_rule_btn)
		button_column_rule.addStretch(1)
		
		rule_layout.addLayout(button_column_rule)
		layout.addLayout(rule_layout)


		# --- Initialization and Footer ---
		self.load_pin_list()
		self.load_ignore_list()
		self.load_rule_list()

		button_row = QHBoxLayout()
		self.close_button = QPushButton("Close")
		self.close_button.clicked.connect(self.reject) # Use reject to save
		
		button_row.addStretch(1)
		button_row.addWidget(self.close_button)
		layout.addLayout(button_row)

	# --- Pinned Substring Methods (Renamed for clarity) ---
	def load_pin_list(self):
		self.pin_list.clear()
		for substring in self.current_settings.get("pinned_substrings", []):
			self.pin_list.addItem(substring)

	def add_pinned_substring(self): # Renamed
		text, ok = QInputDialog.getText(self, 'Add Pinned Substring', 'Enter substring (e.g., "Excel" or "slack.exe"):')
		if ok and text:
			text = text.strip()
			existing_texts = [self.pin_list.item(i).text() for i in range(self.pin_list.count())]
			if text and text not in existing_texts:
				self.pin_list.addItem(text)
			elif text in existing_texts:
				QMessageBox.warning(self, "Duplicate Entry", "This substring already exists in the Pinned list.")

	def edit_substring(self):
		current_item = self.pin_list.currentItem()
		if not current_item:
			QMessageBox.warning(self, "Edit Substring", "Please select an item to edit.")
			return
		
		current_text = current_item.text()
		text, ok = QInputDialog.getText(self, 'Edit Pinned Substring', 'Modify substring:', QLineEdit.Normal, current_text)
		
		if ok and text:
			new_text = text.strip()
			existing_texts = [self.pin_list.item(i).text() for i in range(self.pin_list.count()) if self.pin_list.item(i) is not current_item]
			
			if not new_text:
				QMessageBox.warning(self, "Invalid Input", "The substring cannot be empty.")
				return
			if new_text in existing_texts:
				QMessageBox.warning(self, "Duplicate Entry", "This substring already exists in the Pinned list.")
				return

			current_item.setText(new_text)

	def remove_pinned_substring(self): # Renamed
		selected_items = self.pin_list.selectedItems()
		if not selected_items: return
		for item in selected_items:
			self.pin_list.takeItem(self.pin_list.row(item))

	def get_pinned_substrings(self):
		return [self.pin_list.item(i).text() for i in range(self.pin_list.count())]

	# --- NEW Ignored Substring Methods ---
	def load_ignore_list(self):
		self.ignore_list.clear()
		for substring in self.current_settings.get("ignored_substrings", []):
			self.ignore_list.addItem(substring)

	def add_ignored_substring(self):
		text, ok = QInputDialog.getText(self, 'Add Ignored Substring', 'Enter substring (e.g., "Web Helper" or "launcher.exe"):')
		if ok and text:
			text = text.strip()
			existing_texts = [self.ignore_list.item(i).text() for i in range(self.ignore_list.count())]
			if text and text not in existing_texts:
				self.ignore_list.addItem(text)
			elif text in existing_texts:
				QMessageBox.warning(self, "Duplicate Entry", "This substring already exists in the Ignored list.")

	def edit_ignored_substring(self):
		current_item = self.ignore_list.currentItem()
		if not current_item:
			QMessageBox.warning(self, "Edit Substring", "Please select an item to edit.")
			return
		
		current_text = current_item.text()
		text, ok = QInputDialog.getText(self, 'Edit Ignored Substring', 'Modify substring:', QLineEdit.Normal, current_text)
		
		if ok and text:
			new_text = text.strip()
			existing_texts = [self.ignore_list.item(i).text() for i in range(self.ignore_list.count()) if self.ignore_list.item(i) is not current_item]
			
			if not new_text:
				QMessageBox.warning(self, "Invalid Input", "The substring cannot be empty.")
				return
			if new_text in existing_texts:
				QMessageBox.warning(self, "Duplicate Entry", "This substring already exists in the Ignored list.")
				return

			current_item.setText(new_text)

	def remove_ignored_substring(self):
		selected_items = self.ignore_list.selectedItems()
		if not selected_items: return
		for item in selected_items:
			self.ignore_list.takeItem(self.ignore_list.row(item))

	def get_ignored_substrings(self):
		return [self.ignore_list.item(i).text() for i in range(self.ignore_list.count())]

	# --- Opacity Rule Methods ---
	def load_rule_list(self):
		self.rule_list.clear()
		for rule_data in self.current_settings.get("opacity_rules", []):
			item = QListWidgetItem(self.rule_list)
			widget = OpacityRuleWidget(rule_data)
			item.setSizeHint(widget.sizeHint())
			self.rule_list.setItemWidget(item, widget)

	def open_rule_editor(self, rule_data=None):
		dlg = RuleEditorDialog(rule_data, self)
		if dlg.exec_() == QDialog.Accepted:
			new_rule_data = dlg.get_rule_data()
			
			if rule_data:
				# Editing existing rule
				try:
					index = self.current_settings["opacity_rules"].index(rule_data)
					self.current_settings["opacity_rules"][index] = new_rule_data
				except ValueError:
					# Should not happen
					pass
			else:
				# Adding new rule
				self.current_settings["opacity_rules"].append(new_rule_data)
				
			self.load_rule_list()
			return True
		return False


	def add_rule(self):
		self.open_rule_editor()

	def edit_rule(self):
		selected_item = self.rule_list.currentItem()
		if not selected_item:
			QMessageBox.warning(self, "Edit Rule", "Please select a rule to edit.")
			return
		
		widget = self.rule_list.itemWidget(selected_item)
		if widget:
			# Pass a copy of the rule data to the editor
			if self.open_rule_editor(widget.get_rule_data()):
				pass
			

	def remove_rule(self):
		selected_items = self.rule_list.selectedItems()
		if not selected_items: return

		for item in selected_items:
			widget = self.rule_list.itemWidget(item)
			if widget:
				rule_data = widget.get_rule_data()
				if rule_data in self.current_settings.get("opacity_rules", []):
					self.current_settings["opacity_rules"].remove(rule_data)
			
			self.rule_list.takeItem(self.rule_list.row(item))

	# --- Save/Close Methods ---
	def save_settings_and_close(self):
		self.current_settings["display_exe_name"] = self.display_exe_checkbox.isChecked()
		self.current_settings["pinned_substrings"] = self.get_pinned_substrings()
		self.current_settings["ignored_substrings"] = self.get_ignored_substrings()
		# Opacity rules are updated directly in the editor/add methods
		
		save_settings(self.current_settings)

		# NOTE: Settings must be saved BEFORE emitting the signal so App can reload them
		self.settings_updated.emit()
		self.done(0)
	
	def reject(self):
		# QDialog.reject() is called by closeEvent/Escape key/Close button
		self.save_settings_and_close()

	def closeEvent(self, event):
		self.reject()
		event.accept()

	def keyPressEvent(self, event):
		# Handle Esc or Ctrl+W to close the settings dialog first
		if event.key() == Qt.Key_Escape or (event.key() == Qt.Key_W and event.modifiers() & Qt.ControlModifier):
			self.reject()
		else:
			super().keyPressEvent(event)


class RuleEditorDialog(QDialog):
	def __init__(self, rule_data=None, parent=None):
		super().__init__(parent)
		self.setWindowTitle("Edit Opacity Rule")
		self.setModal(True)
		self.rule = rule_data.copy() if rule_data else {"substring": "", "exe": "", "opacity": 230}
		self.resize(350, 200)

		layout = QVBoxLayout(self)

		# Substring
		layout.addWidget(QLabel("Window Title Substring (Optional):"))
		self.sub_input = QLineEdit()
		self.sub_input.setPlaceholderText("e.g. 'Project Alpha' or leave empty")
		self.sub_input.setText(self.rule.get("substring", ""))
		layout.addWidget(self.sub_input)

		# EXE Name
		layout.addWidget(QLabel("Executable Name (Optional):"))
		self.exe_input = QLineEdit()
		self.exe_input.setPlaceholderText("e.g. 'excel.exe' or leave empty")
		self.exe_input.setText(self.rule.get("exe", ""))
		layout.addWidget(self.exe_input)
		
		# Opacity
		layout.addWidget(QLabel("Opacity (0-255):"))
		self.opacity_spin = QSpinBox()
		self.opacity_spin.setRange(0, 255)
		self.opacity_spin.setValue(self.rule.get("opacity", 230))
		layout.addWidget(self.opacity_spin)

		# Buttons
		button_row = QHBoxLayout()
		save_btn = QPushButton("Save")
		save_btn.clicked.connect(self.accept)
		cancel_btn = QPushButton("Cancel")
		cancel_btn.clicked.connect(self.reject)
		
		button_row.addStretch(1)
		button_row.addWidget(save_btn)
		button_row.addWidget(cancel_btn)
		layout.addLayout(button_row)

	def get_rule_data(self):
		return {
			"substring": self.sub_input.text().strip(),
			"exe": self.exe_input.text().strip(),
			"opacity": self.opacity_spin.value()
		}
	
	def accept(self):
		data = self.get_rule_data()
		if not data["substring"] and not data["exe"]:
			QMessageBox.warning(self, "Invalid Rule", "You must provide at least a Window Title Substring or an Executable Name.")
			return
		
		super().accept()


class ProcessEntry(QFrame):
	def __init__(self, app_instance, window_info, display_exe_name, rule_match=None, is_pinned=False):
		super().__init__()
		self.app_instance = app_instance
		self.hwnd, title = window_info
		self.rule_match = rule_match
		self.exe_name = get_window_exe_info(self.hwnd)
		self.initial_opacity = get_window_opacity(self.hwnd)
		
		self.setFrameShape(QFrame.StyledPanel)
		self.setMinimumWidth(0)
		self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
		
		display_text = title
		if display_exe_name:
			display_text = self.exe_name if self.exe_name else title

		main_layout = QHBoxLayout(self)
		main_layout.setContentsMargins(4, 4, 4, 4)
		main_layout.setSpacing(6)
		
		# Pinned Indicator (Star)
		if is_pinned:
			pin_label = QLabel("⭐")
			pin_label.setFixedSize(16, 16)
			main_layout.addWidget(pin_label, alignment=Qt.AlignLeft | Qt.AlignVCenter)

		# Icon Label 
		self.icon_label = QLabel()
		self.icon_label.setFixedSize(24, 24)
		icon_pixmap = get_window_icon_pixmap(self.hwnd)
		if icon_pixmap:
			self.icon_label.setPixmap(icon_pixmap.scaled(
				24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation
			))
		main_layout.addWidget(self.icon_label, alignment=Qt.AlignLeft | Qt.AlignVCenter)

		# NEW TITLE ROW for Marquee Label and Save Button
		title_row = QHBoxLayout()
		title_row.setContentsMargins(0, 0, 0, 0)
		title_row.setSpacing(6)

		self.label = MarqueeLabel(display_text)
		title_row.addWidget(self.label, stretch=1)
		
		# MOVED: Opacity Save Button
		self.save_opacity_btn = QPushButton("Save Rule")
		self.save_opacity_btn.setStyleSheet("font-size: 10pt; padding: 0px 0px; margin-top: 0px; margin-bottom: 0px;")
		self.save_opacity_btn.clicked.connect(self._save_opacity_rule)
		title_row.addWidget(self.save_opacity_btn, alignment=Qt.AlignRight | Qt.AlignVCenter) 

		# Left layout now contains the new title_row and the existing slider_row
		left_layout = QVBoxLayout()
		left_layout.setContentsMargins(0, 0, 0, 0)
		left_layout.setSpacing(2)
		
		left_layout.addLayout(title_row) # Add the new title row

		# Slider row (unchanged, but without the save button)
		slider_row = QHBoxLayout()
		slider_row.setContentsMargins(0, 0, 0, 0)
		slider_row.setSpacing(4)
		
		# NEW: Set 230 Button (same size as Save Rule button)
		self.set_230_btn = QPushButton("Set 230")
		self.set_230_btn.setStyleSheet("font-size: 10pt; padding: 0px 0px; margin-top: 0px; margin-bottom: 0px;")
		self.set_230_btn.clicked.connect(lambda: self._set_opacity_quick(230))
		slider_row.addWidget(self.set_230_btn, alignment=Qt.AlignLeft | Qt.AlignVCenter)

		# Opacity controls
		self.slider = NoWheelSlider(Qt.Horizontal)
		self.slider.setRange(0, 255)
		self.slider.setValue(self.initial_opacity)
		self.slider.valueChanged.connect(self._slider_changed)
		self.slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
		slider_row.addWidget(self.slider, stretch=1)

		self.opacity_label = QLabel(str(self.initial_opacity))
		self.opacity_label.setFixedWidth(30)
		slider_row.addWidget(self.opacity_label)
		
		left_layout.addLayout(slider_row)
		main_layout.addLayout(left_layout, stretch=1)

		# Initial Opacity Set
		if self.initial_opacity != 255:
			set_window_opacity(self.hwnd, self.initial_opacity)
			
		# Hide/show save button based on rule match
		self._update_save_button_state()

	def _set_opacity_quick(self, opacity):
		"""Sets the slider value and triggers the opacity change via the valueChanged signal."""
		self.slider.setValue(opacity)
		
	def _slider_changed(self, opacity):
		set_window_opacity(self.hwnd, opacity)
		self.opacity_label.setText(str(opacity))
		
		# If the window is already managed by a rule, update the rule and save settings automatically
		if self.rule_match:
			self.rule_match["opacity"] = opacity
			# Notify the App to save the settings (which are shared by reference)
			self.app_instance.save_settings()

	def _update_save_button_state(self):
		if self.rule_match:
			# If a rule matches, opacity changes auto-save, so the button is not needed
			self.save_opacity_btn.setToolTip("Opacity rule matched. Changes save automatically.")
			self.save_opacity_btn.setText("Rule Active")
		else:
			self.save_opacity_btn.setToolTip("Save current window title/exe as a new opacity rule.")
			self.save_opacity_btn.setText("Save Rule")


	def _save_opacity_rule(self):
		if self.rule_match:
			match_substring = self.rule_match['substring']
			match_exe = self.rule_match['exe']
			self.app_instance.settings["opacity_rules"] = [
				rule for rule in self.app_instance.settings["opacity_rules"]
				if not (rule.get('substring') == match_substring and
						rule.get('exe') == match_exe)
			]
			self.rule_match = None
			
			self.app_instance.save_settings()
			self.app_instance.update_list()
		else:
			current_opacity = self.slider.value()
			
			# Determine if we should save the rule by title, exe, or both
			title = win32gui.GetWindowText(self.hwnd).strip()
			exe = self.exe_name
			
			if not title and not exe:
				QMessageBox.warning(self, "Save Error", "Could not get title or executable name for this window.")
				return

			dlg = RuleEditorDialog(
				{"substring": title, "exe": exe, "opacity": current_opacity}, 
				self.app_instance
			)
			
			dlg.setWindowTitle("Save Opacity Rule")
			
			if dlg.exec_() == QDialog.Accepted:
				new_rule = dlg.get_rule_data()
				# Settings are shared by reference, so modifying here affects the App's settings object
				self.app_instance.settings["opacity_rules"].append(new_rule)
				self.app_instance.save_settings()
				
				# Re-trigger list update to reflect the new state and potentially hide the button
				self.app_instance.update_list()


class App(QWidget):
	# Signal to safely set opacity from the worker thread
	apply_opacity_signal = pyqtSignal(int, int)

	def __init__(self, server_instance):
		super().__init__()
		self.local_server = server_instance
		self.setWindowTitle("Stealth")
		self.resize(350, 400)
		self.setWindowIcon(QIcon(resource_path(ICON_FILENAME)))

		self.settings = load_settings()

		# Setup Worker Thread for Automatic Opacity
		self.opacity_thread = QThread()
		self.opacity_worker = OpacityWorker(self.settings)
		self.opacity_worker.moveToThread(self.opacity_thread)
		self.opacity_thread.started.connect(self.opacity_worker.run)
		
		self.apply_opacity_signal.connect(self.apply_opacity_safe)
		self.opacity_worker.set_opacity_signal.connect(self.apply_opacity_signal.emit)
		self.opacity_thread.start()

		# --- GUI setup ---
		main_layout = QVBoxLayout(self)
		top_row = QHBoxLayout()
		self.search_box = QLineEdit()
		self.search_box.setPlaceholderText("Search by process name or window title")
		self.search_box.textChanged.connect(self.update_list)
		top_row.addWidget(self.search_box, stretch=1)
		
		self.refresh_btn = QPushButton("🔄")
		self.refresh_btn.setToolTip("Refresh List")
		self.refresh_btn.setObjectName("refreshButton")
		self.refresh_btn.clicked.connect(self.update_list)
		top_row.addWidget(self.refresh_btn)

		self.settings_btn = QPushButton("⚙️")
		self.settings_btn.setToolTip("Settings")
		self.settings_btn.setObjectName("settingsButton")
		self.settings_btn.clicked.connect(self.open_settings)
		top_row.addWidget(self.settings_btn)
		
		main_layout.addLayout(top_row)
		
		self.scroll_area = QScrollArea()
		self.scroll_area.setWidgetResizable(True)
		self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
		self.scroll_content = QWidget()
		self.scroll_layout = QVBoxLayout(self.scroll_content)
		self.scroll_layout.setContentsMargins(0, 0, 0, 0)
		self.scroll_layout.setSpacing(2)
		self.scroll_area.setWidget(self.scroll_content)
		main_layout.addWidget(self.scroll_area)
		
		self.update_list()

		self.tray_icon = QSystemTrayIcon(self)
		self.tray_icon.setIcon(QIcon(resource_path(ICON_FILENAME)))
		tray_menu = QMenu()
		settings_action = QAction("Settings", self)
		settings_action.triggered.connect(self.open_settings)
		tray_menu.addAction(settings_action)
		tray_menu.addSeparator()
		exit_action = QAction("Exit", self)
		exit_action.triggered.connect(self.exit_app)
		tray_menu.addAction(exit_action)
		self.tray_icon.setContextMenu(tray_menu)
		self.tray_icon.activated.connect(self.on_tray_icon_activated)
		self.tray_icon.show()


	def apply_opacity_safe(self, hwnd, opacity):
		"""Safely applies opacity in the GUI thread."""
		try:
			set_window_opacity(hwnd, opacity)
		except Exception as e:
			# Window might have closed between signal emission and execution
			pass
			
	def save_settings(self):
		"""Wrapper to save settings after an automatic change."""
		save_settings(self.settings)
		# NOTE: No need to call update_list here; only necessary after a manual settings dialog update.

	def open_settings(self):
		dialog = SettingsDialog(self.settings, self)
		# Reload settings after the dialog is closed and saved
		dialog.settings_updated.connect(lambda: self.settings.update(load_settings()))
		dialog.settings_updated.connect(self.update_list)
		dialog.exec_()
	
	def show_window(self):
		self.showNormal()
		self.activateWindow()
		self.update_list()

	def hide_window(self):
		self.hide()

	def on_tray_icon_activated(self, reason):
		if reason == QSystemTrayIcon.DoubleClick or reason == QSystemTrayIcon.Trigger:
			if self.isVisible():
				self.hide_window()
			else:
				self.show_window()

	def keyPressEvent(self, event):
		# Handle Esc or Ctrl+W for search clear/window hide
		if event.key() == Qt.Key_Escape or (event.key() == Qt.Key_W and event.modifiers() & Qt.ControlModifier):
			search_text = self.search_box.text().strip()
			
			if search_text:
				# 1. Clear search bar if text is present
				self.search_box.clear()
				event.accept()
			else:
				# 2. Hide the main window if search bar is empty
				self.hide_window()
				event.accept()
		elif event.key() == Qt.Key_R:
			self.update_list()
		else:
			super().keyPressEvent(event)
			
	def exit_app(self):
		self.local_server.close()
		QLocalServer.removeServer(SINGLE_INSTANCE_SERVER_NAME)

		self.opacity_worker.stop()
		self.opacity_thread.quit()
		self.opacity_thread.wait()
		self.tray_icon.hide()
		QApplication.quit()
		
	def closeEvent(self, event):
		self.hide()
		event.ignore()

	def clear_list(self):
		while self.scroll_layout.count():
			item = self.scroll_layout.takeAt(0)
			widget = item.widget()
			if widget:
				widget.deleteLater()

	def update_list(self):
		display_exe_name = self.settings.get("display_exe_name", DEFAULT_SETTINGS["display_exe_name"])
		pinned_substrings_for_sort = [s.lower() for s in self.settings.get("pinned_substrings", [])]
		ignored_substrings = [s.lower() for s in self.settings.get("ignored_substrings", [])] # NEW: Load ignored list
		opacity_rules = self.settings.get("opacity_rules", [])
		
		self.clear_list()
		search = self.search_box.text().lower().strip()
		pid_windows = get_visible_windows()
		
		all_windows = []
		
		for pid, window_list in pid_windows.items():
			try:
				proc = psutil.Process(pid)
				pname = proc.name().lower()
			except psutil.NoSuchProcess:
				pname = ""
				
			for window_info in window_list:
				hwnd, title = window_info
				title_lower = title.lower()
				
				# 0. IGNORE FILTER CHECK (NEW)
				is_ignored = False
				for substring in ignored_substrings:
					if substring in title_lower or substring in pname:
						is_ignored = True
						break
				if is_ignored:
					continue # Skip this window
					
				# 1. Search Filter Check
				if search and search not in title_lower and search not in pname:
					continue
					
				# 2. Check for Opacity Rule Match (checking against the actual object in settings for binding)
				rule_match = None
				for rule in opacity_rules:
					if check_rule_match(title_lower, pname, rule):
						rule_match = rule
						break

				# 3. Check for Pinned Substring Match
				is_pinned = False
				sort_key = float('inf')
				for i, substring in enumerate(pinned_substrings_for_sort):
					if substring in title_lower or substring in pname:
						sort_key = i
						is_pinned = True
						break
						
				all_windows.append({
					'window_info': window_info, 
					'rule_match': rule_match,
					'sort_key': sort_key, 
					'is_pinned': is_pinned,
				})
		
		# Separate pinned windows from unpinned ones and sort
		pinned_windows = sorted([w for w in all_windows if w['is_pinned']], key=lambda x: x['sort_key'])
		unpinned_windows = sorted([w for w in all_windows if not w['is_pinned']], key=lambda x: x['window_info'][1].lower()) 

		sorted_windows = pinned_windows + unpinned_windows
		
		for window_data in sorted_windows:
			entry = ProcessEntry(
				self, 
				window_data['window_info'], 
				display_exe_name, 
				window_data['rule_match'],
				window_data['is_pinned']
			)
			self.scroll_layout.addWidget(entry)
			
		self.scroll_layout.addStretch()


if __name__ == "__main__":
	app = QApplication(sys.argv)
	app.setQuitOnLastWindowClosed(False)

	# --- 1. CHECK FOR EXISTING INSTANCE (The Client Logic) ---
	socket = QLocalSocket()
	socket.connectToServer(SINGLE_INSTANCE_SERVER_NAME)
	
	# Wait for the connection, giving the existing server a chance to respond.
	is_running = socket.waitForConnected(10)
	
	if is_running:
		# Instance is running. Send 'show' command and exit.
		socket.write(b"show\n") 
		#socket.waitForBytesWritten(1000) # Wait for the data to be written
		socket.disconnectFromServer()
		socket.close()
		sys.exit(0)

	server = QLocalServer()
	QLocalServer.removeServer(SINGLE_INSTANCE_SERVER_NAME) 

	if server.listen(SINGLE_INSTANCE_SERVER_NAME) is False:
		QMessageBox.critical(None, "Fatal Error", 
			"Could not start the application lock server.", QMessageBox.Ok)
		sys.exit(1)

	ICON_FILE_PATH = resource_path(ICON_FILENAME)
	try:
		app.setWindowIcon(QIcon(ICON_FILE_PATH))
	except Exception as e:
		pass
		
	app.setStyleSheet("""
	QWidget {
		background-color: #2b2b2b;
		color: #dddddd;
		font-size: 11pt; /* Slightly smaller font for more items */
	}
	QFrame {
		border: 1px solid #4A4A4A;
	}
	QLabel {
		font-size: 11pt;
	}
	QLabel[style*="font-weight: bold;"] {
		font-weight: bold;
	}
	QLineEdit, QScrollArea, QPushButton, QCheckBox, QDialog, QListWidget, QSpinBox {
		background-color: #3c3f41;
		border: 1px solid #555;
		padding: 4px;
	}
	/* ... (other styles) */
	QPushButton:hover {
		background-color: #505357;
	}
	QListWidget::item:selected {
		background-color: #4A4A4A;
		color: #ffffff;
	}
	""")

	win = App(server)

	def handle_new_connection():
		client_socket = server.nextPendingConnection()
		
		if client_socket.waitForReadyRead(20): # Wait longer to ensure command arrives
			command_data = client_socket.readAll()
			command = command_data.data().decode().strip()
			
			if command == "show":
				print("Received 'show' command. Bringing window to front.")
				win.show_window() 
		
		client_socket.disconnectFromServer()
		client_socket.close()

	# The signal must be connected BEFORE app.exec_() is called.
	server.newConnection.connect(handle_new_connection)
	
	# Run the event loop
	exit_code = app.exec_()
	
	# cleanup
	server.close()
	QLocalServer.removeServer(SINGLE_INSTANCE_SERVER_NAME)

	sys.exit(exit_code)