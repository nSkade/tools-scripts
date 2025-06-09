import customtkinter as ctk
import pyperclip
import re
import markdown
import win32clipboard

def extract_fragments(text):
    result_lines = []
    for line in text.splitlines():
        # Check for ==highlight== or **bold**
        if '==' in line or '**' in line:
            prefix = ''
            match = re.match(r'^(-\s*)', line)
            if match:
                prefix = match.group(0)
            highlights = re.findall(r'==(.+?)==', line)
            bolds = re.findall(r'\*\*(.+?)\*\*', line)
            fragments = ['=={}=='.format(h) for h in highlights] + ['**{}**'.format(b) for b in bolds]
            if fragments:
                result_lines.append(prefix + ' '.join(fragments))
    return '\n'.join(result_lines)

def extract_as_markdown():
    text = pyperclip.paste()
    result = extract_fragments(text)
    pyperclip.copy(result)
    btn_md.configure(text="Copied as Markdown!")
    root.after(1000, lambda: btn_md.configure(text=default_btn_text_md))

def extract_as_html():
    text = pyperclip.paste()
    md = extract_fragments(text)
    # Replace ==highlight== with <mark>highlight</mark>
    html_ready = re.sub(r'==(.+?)==', r'<mark>\1</mark>', md)
    # Replace **bold** with <strong>bold</strong>
    html_ready = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_ready)
    # Wrap in minimal HTML for clipboard
    html_full = (
        "Version:0.9\r\n"
        "StartHTML:00000097\r\n"
        "EndHTML:{end_html:08d}\r\n"
        "StartFragment:00000131\r\n"
        "EndFragment:{end_fragment:08d}\r\n"
        "<html><body><!--StartFragment-->{html}<!--EndFragment--></body></html>"
    )
    html_body = html_ready.replace('\n', '<br>')
    html_clip = html_full.format(
        end_html=131 + len(html_body) + 20,
        end_fragment=131 + len(html_body),
        html=html_body
    )
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.RegisterClipboardFormat("HTML Format"), html_clip.encode('utf-8'))
    win32clipboard.CloseClipboard()
    btn_html.configure(text="Copied as HTML!")
    root.after(1000, lambda: btn_html.configure(text=default_btn_text_html))

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

root = ctk.CTk()
root.title("Extract Highlights/Bold for Joplin")

default_btn_text_md = "Extract as Markdown"
default_btn_text_html = "Extract as HTML"

btn_md = ctk.CTkButton(root, text=default_btn_text_md, command=extract_as_markdown, width=200, height=40)
btn_md.pack(padx=20, pady=10)

btn_html = ctk.CTkButton(root, text=default_btn_text_html, command=extract_as_html, width=200, height=40)
btn_html.pack(padx=20, pady=10)

root.mainloop()
