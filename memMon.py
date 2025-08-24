import psutil
import numpy as np
import pyaudio
import time
import tkinter as tk
from tkinter import ttk, simpledialog, Menu
import os
import sys

def get_app_dir():
    if getattr(sys, 'frozen', False):  # Running as PyInstaller EXE
        return os.path.dirname(sys.executable)
    else:  # Running as script
        return os.path.dirname(os.path.abspath(__file__))

def generate_ping(frequency=880, duration=0.3, decay=0.5):
    volume = 0.2
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration))
    wave = np.sin(2 * np.pi * frequency * t)
    envelope = np.exp(-t / decay)
    ping = wave * envelope
    ping *= volume * 0.5 / np.max(np.abs(ping))
    return ping.astype(np.float32)

def play_sound(sound):
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32,
                    channels=1,
                    rate=44100,
                    output=True)
    stream.write(sound.tobytes())
    stream.stop_stream()
    stream.close()
    p.terminate()

class MemoryMonitorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.wm_attributes("-toolwindow", True)
        self.title("Memory Monitor (Dark Mode)")
        self.geometry("400x200")
        self.configure(bg="#333333")

        # Default threshold
        self.usage_threshold = 75  

        self.memory_label = ttk.Label(
            self,
            text="Memory usage: ? %",
            font=('Arial', 10),
            background="#333333",
            foreground="white"
        )
        self.memory_label.pack(pady=50)

        self.ping_sound = generate_ping()
        self.after(1000, self.update_memory_display)

        # Load saved window position and threshold
        self.load_settings()

        # Bind window move event to save position
        self.bind("<Configure>", self.on_window_configure)

        # Bind window close to save settings
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Add right-click menu
        self.create_context_menu()

    def create_context_menu(self):
        self.menu = Menu(self, tearoff=0)
        self.menu.add_command(label="Set Threshold...", command=self.set_threshold)

        # Bind right-click (Windows/Linux) or Control-click (macOS)
        self.bind("<Button-3>", self.show_context_menu)
        self.bind("<Control-Button-1>", self.show_context_menu)

    def show_context_menu(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)

    def set_threshold(self):
        new_value = simpledialog.askinteger(
            "Set Threshold",
            "Enter memory usage limit (%)",
            initialvalue=self.usage_threshold,
            minvalue=1,
            maxvalue=100
        )
        if new_value is not None:
            self.usage_threshold = new_value
            self.save_settings()  # Save immediately

    def load_settings(self):
        try:
            with open(os.path.join(get_app_dir(), "memMon-settings.txt"), "r") as f:
                lines = f.read().splitlines()
                if lines:
                    # First line can be geometry, second can be threshold
                    self.geometry(lines[0])
                if len(lines) > 1:
                    self.usage_threshold = int(lines[1])
        except (FileNotFoundError, IOError, ValueError):
            pass  # Use defaults if no file

    def save_settings(self):
        with open(os.path.join(get_app_dir(), "memMon-settings.txt"), "w") as f:
            f.write(self.geometry() + "\n")
            f.write(str(self.usage_threshold))

    def on_window_configure(self, event):
        if event.widget == self:
            self.save_settings()

    def on_close(self):
        self.save_settings()
        self.destroy()

    def update_memory_display(self):
        mem = psutil.virtual_memory()
        usage = mem.percent

        if usage > self.usage_threshold:
            self.configure(bg="#ff0000")
            self.memory_label.configure(background="#ff0000", foreground="black")
            play_sound(self.ping_sound)
        else:
            self.configure(bg="#333333")
            self.memory_label.configure(background="#333333", foreground="white")

        self.memory_label.config(text=f"Memory usage: {usage:.1f} % (Limit: {self.usage_threshold}%)")
        self.after(1000, self.update_memory_display)

if __name__ == "__main__":
    app = MemoryMonitorApp()
    app.mainloop()