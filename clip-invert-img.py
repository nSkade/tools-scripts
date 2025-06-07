import customtkinter as ctk
from PIL import ImageGrab, ImageOps, Image
import io
import win32clipboard

def invert_clipboard_image():
    img = ImageGrab.grabclipboard()
    if isinstance(img, Image.Image):
        inverted_img = ImageOps.invert(img.convert("RGB"))
        output = io.BytesIO()
        inverted_img.save(output, 'BMP')
        data = output.getvalue()[14:]  # Skip BMP header for DIB
        output.close()

        # Set image to clipboard using win32clipboard
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
        btn.configure(text="Inverted and copied!")
        root.after(1000, lambda: btn.configure(text=default_btn_text))
    else:
        btn.configure(text="No image in clipboard")
        root.after(1000, lambda: btn.configure(text=default_btn_text))

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

root = ctk.CTk()
root.title("Invert Clipboard Image (Dark Mode)")

default_btn_text = "Invert Clipboard Image"
btn = ctk.CTkButton(root, text=default_btn_text, command=invert_clipboard_image, width=240, height=40)
btn.pack(padx=40, pady=40)

root.mainloop()
