import tkinter as tk
import ctypes
from gui import HotkeyGUI

def main():
    root = tk.Tk()
    
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    
    # Set window icon
    try:
        from PIL import Image, ImageTk
        import os
        icon_path = os.path.join(os.path.dirname(__file__), "..", "images", "icon.webp")
        if os.path.exists(icon_path):
            icon_image = Image.open(icon_path)
            # Convert to PhotoImage for tkinter
            photo = ImageTk.PhotoImage(icon_image)
            root.iconphoto(True, photo)
    except Exception as e:
        print(f"Could not load icon: {e}")
    
    app = HotkeyGUI(root)
    root.protocol('WM_DELETE_WINDOW', app.exit_app)
    root.mainloop()

if __name__ == '__main__':
    main()
