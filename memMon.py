import psutil
import numpy as np
import pyaudio
import time
import tkinter as tk
from tkinter import ttk
import os
import sys

def get_app_dir():
    if getattr(sys, 'frozen', False):  # Running as PyInstaller EXE
        return os.path.dirname(sys.executable)
    else:  # Running as script
        return os.path.dirname(os.path.abspath(__file__))

def generate_ping(frequency=880, duration=0.3, decay=0.5):
    sample_rate = 44100
    t = np.linspace(0, duration, int(sample_rate * duration))
    wave = np.sin(2 * np.pi * frequency * t)
    envelope = np.exp(-t/decay)
    ping = wave * envelope
    ping *= 0.5 / np.max(np.abs(ping))
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

        self.memory_label = ttk.Label(
            self,
            text="Memory usage: ? %",
            font=('Arial', 10),
            background="#333333",
            foreground="black"
        )
        self.memory_label.pack(pady=50)

        self.ping_sound = generate_ping()
        self.after(1000, self.update_memory_display)

        # Load saved window position
        self.load_window_position()

        # Bind window move event to save position
        self.bind("<Configure>", self.on_window_configure)

        # Bind window close to save position
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_window_position(self):
        try:
            with open(os.path.join(get_app_dir(), "memMon-settings.txt"), "r") as f:
                geometry = f.read().strip()
                self.geometry(geometry)
        except (FileNotFoundError, IOError):
            pass  # Use default geometry if file not found

    def save_window_position(self):
        with open(os.path.join(get_app_dir(), "memMon-settings.txt"), "w") as f:
            f.write(self.geometry())

    def on_window_configure(self, event):
        # Only save when window is being moved or resized by the user
        if event.widget == self:
            self.save_window_position()

    def on_close(self):
        self.save_window_position()
        self.destroy()

    def update_memory_display(self):
        mem = psutil.virtual_memory()
        usage = mem.percent

        if usage > 85:
            self.configure(bg="#ff0000")
            self.memory_label.configure(background="#ff0000", foreground="black")
            play_sound(self.ping_sound)
        else:
            self.configure(bg="#333333")
            self.memory_label.configure(background="#333333", foreground="black")

        self.memory_label.config(text=f"Memory usage: {usage:.1f} %")
        self.after(1000, self.update_memory_display)

if __name__ == "__main__":
    app = MemoryMonitorApp()
    app.mainloop()
