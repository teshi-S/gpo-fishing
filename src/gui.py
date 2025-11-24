import tkinter as tk
from tkinter import ttk, filedialog, simpledialog
import threading
import keyboard
from pynput import keyboard as pynput_keyboard
from pynput import mouse as pynput_mouse
from tkinter import messagebox
import sys
import ctypes
import mss
import numpy as np
import win32api
import win32con
import json
import os
import time
from datetime import datetime
try:
    import pystray
    from PIL import Image, ImageDraw, ImageTk
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

# Import the theme manager
from themes import ThemeManager
from fishing import FishingBot

class ToolTip:
    """Simple tooltip class for hover explanations"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
    
    def on_enter(self, event=None):
        if self.tooltip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_attributes('-topmost', True)  # Force tooltip to stay on top
        tw.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(tw, text=self.text, justify='left',
                        background="#ffffe0", relief='solid', borderwidth=1,
                        font=("Arial", 9), wraplength=300, padx=5, pady=3)
        label.pack()
    
    def on_leave(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class CollapsibleFrame:
    """Modern collapsible frame widget with sleek styling"""
    def __init__(self, parent, title, row, columnspan=4):
        self.parent = parent
        self.title = title
        self.row = row
        self.columnspan = columnspan
        self.is_expanded = True
        
        # Main container with modern styling
        self.container = ttk.Frame(parent)
        self.container.grid(row=row, column=0, columnspan=columnspan, sticky='ew', pady=(8, 0), padx=10)
        
        # Header frame with modern card-like appearance
        self.header_frame = ttk.Frame(self.container)
        self.header_frame.pack(fill='x', pady=(0, 2))
        self.header_frame.columnconfigure(0, weight=1)  # Make title expand
        
        # Title label with modern typography (left side) - using blue section title style
        self.title_label = ttk.Label(self.header_frame, text=title, 
                                   style='SectionTitle.TLabel')
        self.title_label.grid(row=0, column=0, sticky='w', padx=(10, 0), pady=5)
        
        # Modern toggle button on the right side
        self.toggle_btn = ttk.Button(self.header_frame, text='−', width=3, 
                                   command=self.toggle, style='TButton')
        self.toggle_btn.grid(row=0, column=1, sticky='e', padx=(0, 10), pady=2)
        
        # Separator line for visual separation
        separator = ttk.Frame(self.container, height=1)
        separator.pack(fill='x', pady=(0, 8))
        
        # Content frame with padding
        self.content_frame = ttk.Frame(self.container)
        self.content_frame.pack(fill='both', expand=True, padx=15, pady=(0, 10))
        
        # Configure grid weights for responsive design
        parent.grid_rowconfigure(row, weight=0)
        self.container.columnconfigure(0, weight=1)
        
    def toggle(self):
        """Toggle the visibility of the content frame with smooth animation"""
        if self.is_expanded:
            self.content_frame.pack_forget()
            self.toggle_btn.config(text='+')
            self.is_expanded = False
        else:
            self.content_frame.pack(fill='both', expand=True, padx=15, pady=(0, 10))
            self.toggle_btn.config(text='−')
            self.is_expanded = True
    
    def get_content_frame(self):
        """Return the content frame for adding widgets"""
        return self.content_frame

class HotkeyGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('GPO Autofish')
        self.root.attributes('-topmost', True)
        
        # Set window icon
        try:
            if os.path.exists("images/icon.webp"):
                icon_image = Image.open("images/icon.webp")
                icon_image = icon_image.resize((32, 32), Image.Resampling.LANCZOS)
                icon_photo = ImageTk.PhotoImage(icon_image)
                self.root.iconphoto(True, icon_photo)
        except Exception as e:
            print(f"Could not set window icon: {e}")
        
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.main_loop_active = False
        self.overlay_active = False
        self.main_loop_thread = None
        self.recording_hotkey = None
        self.overlay_window = None
        self.overlay_drag_data = {'x': 0, 'y': 0, 'resize_edge': None, 'start_width': 0, 'start_height': 0, 'start_x': 0, 'start_y': 0}
        self.real_area = None
        self.is_clicking = False
        self.kp = 0.1
        self.kd = 0.5
        self.previous_error = 0
        self.scan_timeout = 15.0
        self.wait_after_loss = 1.0
        self.dpi_scale = self.get_dpi_scale()
        base_width = 172
        base_height = 495
        self.overlay_area = {'x': int(100 * self.dpi_scale), 'y': int(100 * self.dpi_scale), 'width': int(base_width * self.dpi_scale), 'height': int(base_height * self.dpi_scale)}
        self.hotkeys = {'toggle_loop': 'f1', 'toggle_overlay': 'f2', 'exit': 'f3', 'toggle_tray': 'f4'}
        self.purchase_counter = 0
        self.purchase_delay_after_key = 2.0
        self.purchase_click_delay = 1.0
        self.purchase_after_type_delay = 1.0
        self.fish_count = 0  # Track successful fishing attempts
        
        # Discord webhook settings
        self.webhook_url = ""
        self.webhook_enabled = False
        self.webhook_interval = 10  # Send webhook every X loops
        self.webhook_counter = 0  # Track loops for webhook
        
        # Update manager - will be initialized after GUI is ready
        self.update_manager = None
        
        # Performance settings
        self.silent_mode = False  # Reduce console logging
        self.verbose_logging = False  # Detailed logging for debugging
        
        # Smart Recovery System with detailed detection
        self.last_activity_time = time.time()
        self.last_fish_time = time.time()
        self.recovery_enabled = True
        self.smart_check_interval = 15.0  # Check every 15 seconds
        self.last_smart_check = time.time()
        self.recovery_count = 0
        self.last_recovery_time = 0
        
        # Advanced state tracking for smart recovery
        self.current_state = "idle"  # idle, fishing, purchasing, casting, menu_opening, typing, clicking
        self.state_start_time = time.time()
        self.state_details = {}  # Store additional state info
        self.stuck_actions = []  # Track what got stuck for logging
        
        # Smart timeouts for each specific action
        self.max_state_duration = {
            "fishing": 50.0,        # Blue bar detection (rarely gets stuck)
            "purchasing": 60.0,     # Full purchase sequence
            "casting": 15.0,        # Line casting
            "menu_opening": 10.0,   # Opening shop menu with 'E'
            "typing": 8.0,          # Typing purchase amount
            "clicking": 5.0,        # Individual clicks
            "idle": 45.0           # Between actions
        }
        
        # Dev mode logging
        self.dev_mode = False  # Will be set based on verbose_logging
        
        # Runtime tracking
        self.start_time = None
        self.pause_time = None
        self.total_paused_time = 0
        self.is_paused = False
        
        # Check if running with pythonw (silent mode)
        import sys
        if 'pythonw' in sys.executable.lower():
            self.silent_mode = True
        
        # UI/UX improvements
        self.dark_theme = True  # Default to dark theme
        self.current_theme = "default"  # Default theme
        self.tray_icon = None
        self.collapsible_sections = {}
        self.theme_window = None
        
        # Initialize theme manager
        self.theme_manager = ThemeManager(self)
        
        # Initialize webhook manager
        from webhook import WebhookManager
        self.webhook_manager = WebhookManager(self)
        
        # Initialize fishing bot
        self.fishing_bot = FishingBot(self)
        
        # Preset management
        self.presets_dir = "presets"
        if not os.path.exists(self.presets_dir):
            os.makedirs(self.presets_dir)
        
        # Load basic settings before creating widgets
        self.load_basic_settings()
        
        self.create_widgets()
        
        # Load UI-specific settings after widgets are created
        self.load_ui_settings()
        
        self.apply_theme()
        self.register_hotkeys()
        
        # Set compact window size with modern scrolling
        self.root.geometry('420x550')
        self.root.resizable(True, True)
        self.root.update_idletasks()
        self.root.minsize(400, 450)
        
        # Setup system tray if available
        if TRAY_AVAILABLE:
            self.setup_system_tray()
        
        # Initialize UpdateManager after GUI is ready
        try:
            from updater import UpdateManager
            self.update_manager = UpdateManager(self)
            print("✅ Simple UpdateManager initialized")
        except Exception as e:
            print(f"❌ Failed to initialize UpdateManager: {e}")
            self.update_manager = None
    
    def create_scrollable_frame(self):
        """Create a modern scrollable frame using tkinter Canvas and Scrollbar"""
        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create canvas and scrollbar with theme-aware colors
        canvas_bg = '#0d1117' if self.dark_theme else '#fafbfc'
        self.canvas = tk.Canvas(self.main_container, highlightthickness=0, bg=canvas_bg)
        self.scrollbar = ttk.Scrollbar(self.main_container, orient="vertical", command=self.canvas.yview)
        
        # Create the scrollable frame
        self.main_frame = ttk.Frame(self.canvas, padding='10')
        
        # Configure scrolling
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack scrollbar and canvas
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Create window in canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        
        # Bind events for proper scrolling
        self.main_frame.bind('<Configure>', self._on_frame_configure)
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
    def _on_frame_configure(self, event):
        """Reset the scroll region to encompass the inner frame"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
    def _on_canvas_configure(self, event):
        """Configure the canvas window to match the canvas width"""
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
        
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def log(self, message, level="info"):
        """Smart logging that respects silent mode"""
        if self.silent_mode and level == "verbose":
            return
        if not self.silent_mode or level in ["error", "important"]:
            print(message)

    def get_dpi_scale(self):
        """Get the DPI scaling factor for the current display"""  # inserted
        try:
            dpi = self.root.winfo_fpixels('1i')
            scale = dpi / 96.0
            return scale
        except:
            return 1.0

    def create_widgets(self):
        # Create scrollable main container with more width
        self.create_scrollable_frame()
        self.main_frame.columnconfigure(0, weight=1)
        
        current_row = 0
        
        # Modern header section
        header_frame = ttk.Frame(self.main_frame)
        header_frame.grid(row=current_row, column=0, sticky='ew', pady=(0, 20))
        header_frame.columnconfigure(0, weight=1)
        
        # Logo at the top
        try:
            if os.path.exists("images/icon.webp"):
                logo_image = Image.open("images/icon.webp")
                # Resize logo to appropriate size for header
                logo_image = logo_image.resize((64, 64), Image.Resampling.LANCZOS)
                logo_photo = ImageTk.PhotoImage(logo_image)
                logo_label = ttk.Label(header_frame, image=logo_photo)
                logo_label.image = logo_photo  # Keep a reference to prevent garbage collection
                logo_label.grid(row=0, column=0, pady=(0, 10))
        except Exception as e:
            print(f"Could not load header logo: {e}")
        
        # App title with modern styling
        title = ttk.Label(header_frame, text='GPO Autofish', style='Title.TLabel')
        title.grid(row=1, column=0, pady=(0, 5))
        
        # Subtitle
        credits = ttk.Label(header_frame, text='by Ariel', 
                           style='Subtitle.TLabel')
        credits.grid(row=2, column=0, pady=(0, 15))
        
        # Modern control panel
        control_panel = ttk.Frame(header_frame)
        control_panel.grid(row=3, column=0, sticky='ew', pady=(0, 10))
        control_panel.columnconfigure(1, weight=1)  # Center spacing
        
        # Left controls
        left_controls = ttk.Frame(control_panel)
        left_controls.grid(row=0, column=0, sticky='w')
        
        self.theme_btn = ttk.Button(left_controls, text='🎨 Themes', 
                                   command=self.theme_manager.open_theme_window, style='TButton')
        self.theme_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        # Right controls - removed Load button, only auto-save now
        right_controls = ttk.Frame(control_panel)
        right_controls.grid(row=0, column=2, sticky='e')
        
        # Manual update button
        self.update_btn = ttk.Button(right_controls, text='🔄 Update', 
                                    command=self.check_for_updates, style='TButton')
        self.update_btn.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(self.update_btn, "Check for and install updates from GitHub")
        
        if TRAY_AVAILABLE:
            ttk.Button(right_controls, text='📌 Tray', command=self.minimize_to_tray,
                      style='TButton').pack(side=tk.LEFT)
        
        current_row += 1
        
        # Modern status dashboard
        status_frame = ttk.Frame(self.main_frame)
        status_frame.grid(row=current_row, column=0, sticky='ew', pady=(0, 25))
        status_frame.columnconfigure((0, 1, 2), weight=1)
        
        # Status cards - First row
        self.loop_status = ttk.Label(status_frame, text='● Main Loop: OFF', style='StatusOff.TLabel')
        self.loop_status.grid(row=0, column=0, padx=10, pady=8)
        
        self.overlay_status = ttk.Label(status_frame, text='● Overlay: OFF', style='StatusOff.TLabel')
        self.overlay_status.grid(row=0, column=1, padx=10, pady=8)
        
        self.fish_counter_label = ttk.Label(status_frame, text='Fish: 0', style='Counter.TLabel')
        self.fish_counter_label.grid(row=0, column=2, padx=10, pady=8)
        
        # Second row - Just runtime (centered)
        self.runtime_label = ttk.Label(status_frame, text='⏱️ Runtime: 00:00:00', style='Counter.TLabel')
        self.runtime_label.grid(row=1, column=0, columnspan=3, padx=10, pady=8)
        
        current_row += 1
        
        # Create modern collapsible sections
        self.create_auto_purchase_section(current_row)
        current_row += 1
        
        self.create_pd_controller_section(current_row)
        current_row += 1
        
        self.create_timing_section(current_row)
        current_row += 1
        
        self.create_presets_section(current_row)
        current_row += 1
        
        self.create_hotkeys_section(current_row)
        current_row += 1
        
        self.create_webhook_section(current_row)
        current_row += 1
        
        # Discord join section at bottom
        self.create_discord_section(current_row)
        current_row += 1
        
        # Status message for dynamic updates
        self.status_msg = ttk.Label(self.main_frame, text='Ready to fish!', 
                                   font=('Segoe UI', 9), foreground='#58a6ff')
        self.status_msg.grid(row=current_row, column=0, pady=(10, 0))

    def update_status(self, message, status_type='info', icon='ℹ️'):
        """Update the status message with color coding"""
        try:
            theme_colors = self.theme_manager.themes[self.current_theme]["colors"]
            color_map = {
                'info': theme_colors["accent"],
                'success': theme_colors["success"],
                'error': theme_colors["error"],
                'warning': theme_colors["warning"]
            }
            color = color_map.get(status_type, theme_colors["fg"])
            self.status_msg.config(text=f'{icon} {message}', foreground=color)
        except Exception:
            # Fallback if theme system fails
            self.status_msg.config(text=f'{icon} {message}', foreground='blue')

    def capture_mouse_click(self, idx):
        """Start a listener to capture the next mouse click and store its coordinates."""  # inserted
        try:
            self.status_msg.config(text=f'Click anywhere to set Point {idx}...', foreground='blue')

            def _on_click(x, y, button, pressed):
                if pressed:
                    self.point_coords[idx] = (x, y)
                    try:
                        self.root.after(0, lambda: self.update_point_button(idx))
                        self.root.after(0, lambda: self.status_msg.config(text=f'Point {idx} set: ({x}, {y})', foreground='green'))
                        self.root.after(0, lambda: self.auto_save_settings())  # Auto-save when point is set
                    except Exception:
                        pass
                    return False  # Stop listener after first click
            
            listener = pynput_mouse.Listener(on_click=_on_click)
            listener.start()
        except Exception as e:
            try:
                self.status_msg.config(text=f'Error capturing point: {e}', foreground='red')
            except Exception:
                return None

    def update_point_button(self, idx):
        coords = self.point_coords.get(idx)
        if coords and idx in self.point_buttons:
            self.point_buttons[idx].config(text=f'Point {idx}: {coords}')
        return None

    def _click_at(self, coords):
        """Move cursor to coords and perform a left click."""  # inserted
        try:
            x, y = (int(coords[0]), int(coords[1]))
            win32api.SetCursorPos((x, y))
            try:
                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 0, 1, 0, 0)
                threading.Event().wait(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                threading.Event().wait(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            except Exception:
                pass
        except Exception as e:
            print(f'Error clicking at {coords}: {e}')

    def _right_click_at(self, coords):
        """Move cursor to coords and perform a right click."""  # inserted
        try:
            x, y = (int(coords[0]), int(coords[1]))
            win32api.SetCursorPos((x, y))
            try:
                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 0, 1, 0, 0)
                threading.Event().wait(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                threading.Event().wait(0.05)
                win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
            except Exception:
                pass
        except Exception as e:
            print(f'Error right-clicking at {coords}: {e}')

    def perform_auto_purchase_sequence(self):
        """Perform the auto-purchase sequence using saved points and amount.

Sequence (per user spec):
- press 'e', wait
- click point1, wait
- click point2, wait
- type amount, wait
- click point1, wait
- click point3, wait
- click point2, wait
- right-click point4 to close menu
"""
        from datetime import datetime
        pts = self.point_coords
        if not pts or not pts.get(1) or not pts.get(2) or not pts.get(3) or not pts.get(4):
            print('Auto purchase aborted: points not fully set (need points 1-4).')
            return
        
        # Check if main loop is still active before starting
        if not self.main_loop_active:
            print('Auto purchase aborted: main loop stopped.')
            return
        
        amount = str(self.auto_purchase_amount)
        
        # Press 'e' key with detailed state tracking
        self.set_recovery_state("menu_opening", {"action": "pressing_e_key", "amount": amount})
        self.log('Pressing E key...', "verbose")
        keyboard.press_and_release('e')
        threading.Event().wait(self.purchase_delay_after_key)
        
        if not self.main_loop_active:
            return
        
        # Click point 1 with state tracking
        self.set_recovery_state("clicking", {"action": "click_point_1", "point": pts[1]})
        self.log(f'Clicking Point 1: {pts[1]}', "verbose")
        self._click_at(pts[1])
        threading.Event().wait(self.purchase_click_delay)
        
        if not self.main_loop_active:
            return
        
        # Click point 2 with state tracking
        self.set_recovery_state("clicking", {"action": "click_point_2", "point": pts[2]})
        self.log(f'Clicking Point 2: {pts[2]}', "verbose")
        self._click_at(pts[2])
        threading.Event().wait(self.purchase_click_delay)
        
        if not self.main_loop_active:
            return
        
        # Type amount with state tracking
        self.set_recovery_state("typing", {"action": "typing_amount", "amount": amount})
        self.log(f'Typing amount: {amount}', "verbose")
        keyboard.write(amount)
        threading.Event().wait(self.purchase_after_type_delay)
        
        if not self.main_loop_active:
            return
        
        # Click point 1 again with state tracking
        self.set_recovery_state("clicking", {"action": "click_point_1_confirm", "point": pts[1]})
        print(f'Clicking Point 1: {pts[1]}')
        self._click_at(pts[1])
        threading.Event().wait(self.purchase_click_delay)
        
        if not self.main_loop_active:
            return
        
        # Click point 3 with state tracking
        self.set_recovery_state("clicking", {"action": "click_point_3", "point": pts[3]})
        print(f'Clicking Point 3: {pts[3]}')
        self._click_at(pts[3])
        threading.Event().wait(self.purchase_click_delay)
        
        if not self.main_loop_active:
            return
        
        # Click point 2 with state tracking
        self.set_recovery_state("clicking", {"action": "click_point_2_final", "point": pts[2]})
        print(f'Clicking Point 2: {pts[2]}')
        self._click_at(pts[2])
        threading.Event().wait(self.purchase_click_delay)
        
        if not self.main_loop_active:
            return
        
        # Right-click point 4 to close menu with state tracking
        self.set_recovery_state("clicking", {"action": "right_click_point_4_close", "point": pts[4]})
        print(f'Right-clicking Point 4: {pts[4]}')
        self._right_click_at(pts[4])
        threading.Event().wait(self.purchase_click_delay)
        
        # Send webhook notification for auto purchase
        self.webhook_manager.send_purchase(amount)
        print()

    def start_rebind(self, action):
        """Start recording a new hotkey"""  # inserted
        self.recording_hotkey = action
        self.status_msg.config(text=f'Press a key to rebind \'{action}\'...', foreground='blue')
        self.loop_rebind_btn.config(state='disabled')
        self.overlay_rebind_btn.config(state='disabled')
        self.exit_rebind_btn.config(state='disabled')
        self.tray_rebind_btn.config(state='disabled')
        listener = pynput_keyboard.Listener(on_press=self.on_key_press)
        listener.start()

    def on_key_press(self, key):
        """Handle key press during rebinding"""
        if self.recording_hotkey:
            try:
                if hasattr(key, 'char') and key.char:
                    key_str = key.char.lower()
                elif hasattr(key, 'name'):
                    key_str = key.name.lower()
                else:
                    key_str = str(key).split('.')[-1].lower()
                
                self.hotkeys[self.recording_hotkey] = key_str
                
                # Update the label
                if self.recording_hotkey == 'toggle_loop':
                    self.loop_key_label.config(text=key_str.upper())
                elif self.recording_hotkey == 'toggle_overlay':
                    self.overlay_key_label.config(text=key_str.upper())
                elif self.recording_hotkey == 'exit':
                    self.exit_key_label.config(text=key_str.upper())
                elif self.recording_hotkey == 'toggle_tray':
                    self.tray_key_label.config(text=key_str.upper())
                
                self.recording_hotkey = None
                self.loop_rebind_btn.config(state='normal')
                self.overlay_rebind_btn.config(state='normal')
                self.exit_rebind_btn.config(state='normal')
                self.tray_rebind_btn.config(state='normal')
                self.status_msg.config(text=f'Hotkey set to {key_str.upper()}', foreground='green')
                self.register_hotkeys()
                return False  # Stop the listener
            except Exception as e:
                self.status_msg.config(text=f'Error setting hotkey: {e}', foreground='red')
                self.recording_hotkey = None
                self.loop_rebind_btn.config(state='normal')
                self.overlay_rebind_btn.config(state='normal')
                self.exit_rebind_btn.config(state='normal')
                self.tray_rebind_btn.config(state='normal')
                return False
        return False

    def register_hotkeys(self):
        """Register all hotkeys"""  # inserted
        try:
            keyboard.unhook_all()
            keyboard.add_hotkey(self.hotkeys['toggle_loop'], self.toggle_main_loop)
            keyboard.add_hotkey(self.hotkeys['toggle_overlay'], self.toggle_overlay)
            keyboard.add_hotkey(self.hotkeys['exit'], self.exit_app)
            keyboard.add_hotkey(self.hotkeys['toggle_tray'], self.toggle_tray_hotkey)
        except Exception as e:
            print(f'Error registering hotkeys: {e}')
    
    def toggle_tray_hotkey(self):
        """Toggle between tray and normal window via F4 hotkey"""
        if TRAY_AVAILABLE:
            if self.root.state() == 'withdrawn':
                self.restore_from_tray()
            else:
                self.minimize_to_tray()
        else:
            print("System tray not available")
    



    def toggle_main_loop(self):
        """Toggle between Start/Pause/Resume with smart detection"""
        if not self.main_loop_active and not self.is_paused:
            # Starting fresh
            self.start_fishing()
        elif self.main_loop_active and not self.is_paused:
            # Currently running - pause it
            self.pause_fishing()
        elif not self.main_loop_active and self.is_paused:
            # Currently paused - resume it
            self.resume_fishing()
    
    def start_fishing(self):
        """Start fishing from scratch"""
        # Check auto-purchase points if enabled
        if getattr(self, 'auto_purchase_var', None) and self.auto_purchase_var.get():
            pts = getattr(self, 'point_coords', {})
            missing = [i for i in [1, 2, 3, 4] if not pts.get(i)]
            if missing:
                messagebox.showwarning('Auto Purchase: Points missing', f'Please set Point(s) {missing} before starting Auto Purchase.')
                return
        
        # Reset everything for fresh start
        self.main_loop_active = True
        self.is_paused = False
        self.start_time = time.time()
        self.total_paused_time = 0
        self.reset_fish_counter()
        
        # Update UI
        self.loop_status.config(text='● Main Loop: ACTIVE', style='StatusOn.TLabel')
        
        # Start the loop
        self.main_loop_thread = threading.Thread(target=self.main_loop, daemon=True)
        self.main_loop_thread.start()
        
        # Start runtime timer
        self.update_runtime_timer()
        
        self.log('🎣 Started fishing!', "important")
    
    def pause_fishing(self):
        """Pause the current fishing session"""
        self.main_loop_active = False
        self.is_paused = True
        self.pause_time = time.time()
        
        # Release mouse if clicking
        if self.is_clicking:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self.is_clicking = False
        
        # Update UI
        self.loop_status.config(text='● Main Loop: PAUSED', style='StatusOff.TLabel')
        
        self.log('⏸️ Fishing paused', "important")
    
    def resume_fishing(self):
        """Resume fishing with smart detection"""
        # Update pause tracking
        if self.pause_time:
            self.total_paused_time += time.time() - self.pause_time
            self.pause_time = None
        
        self.main_loop_active = True
        self.is_paused = False
        
        # Update UI
        self.loop_status.config(text='● Main Loop: ACTIVE', style='StatusOn.TLabel')
        
        # Start the loop with smart detection
        self.main_loop_thread = threading.Thread(target=self.smart_resume_loop, daemon=True)
        self.main_loop_thread.start()
        
        # Resume runtime timer
        self.update_runtime_timer()
        
        self.log('▶️ Fishing resumed with smart detection', "important")
    
    def smart_resume_loop(self):
        """Resume loop with smart detection of current state"""
        import mss
        import numpy as np
        
        # Check if there's already a blue fishing bar visible
        target_color = (85, 170, 255)
        
        with mss.mss() as sct:
            x = self.overlay_area['x']
            y = self.overlay_area['y']
            width = self.overlay_area['width']
            height = self.overlay_area['height']
            monitor = {'left': x, 'top': y, 'width': width, 'height': height}
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            
            # Look for blue fishing bar
            blue_found = False
            for row_idx in range(height):
                for col_idx in range(width):
                    b, g, r = img[row_idx, col_idx, 0:3]
                    if r == target_color[0] and g == target_color[1] and b == target_color[2]:
                        blue_found = True
                        break
                if blue_found:
                    break
        
        if blue_found:
            self.log('🎯 Blue fishing bar detected - resuming from current state', "important")
            # Jump directly into the main loop detection
            self.fishing_bot.run_main_loop()
        else:
            self.log('🎣 No fishing bar detected - starting fresh', "important")
            # Start from scratch with auto-purchase check and casting
            self.fishing_bot.run_main_loop()

    def increment_fish_counter(self):
        """Increment fish counter and update display"""
        self.fish_count += 1
        self.webhook_counter += 1
        
        # Update recovery tracking
        self.last_fish_time = time.time()
        self.last_activity_time = time.time()
        
        try:
            self.root.after(0, lambda: self.fish_counter_label.config(text=f'🐟 Fish: {self.fish_count}'))
        except Exception:
            pass
        self.log(f'🐟 Fish caught: {self.fish_count}', "important")
        
        # Check if we should send webhook
        if self.webhook_enabled and self.webhook_counter >= self.webhook_interval:
            self.webhook_manager.send_fishing_progress()
            self.webhook_counter = 0

    def reset_fish_counter(self):
        """Reset fish counter when main loop starts"""
        self.fish_count = 0
        self.webhook_counter = 0
        try:
            self.root.after(0, lambda: self.fish_counter_label.config(text=f'🐟 Fish: {self.fish_count}'))
        except Exception:
            pass

    def check_and_purchase(self):
        """Check if we need to auto-purchase and run sequence if needed"""  # inserted
        if getattr(self, 'auto_purchase_var', None) and self.auto_purchase_var.get():
            self.purchase_counter += 1
            loops_needed = int(getattr(self, 'loops_per_purchase', 1)) if getattr(self, 'loops_per_purchase', None) is not None else 1
            print(f'🔄 Purchase counter: {self.purchase_counter}/{loops_needed}')
            if self.purchase_counter >= max(1, loops_needed):
                try:
                    self.perform_auto_purchase_sequence()
                    self.purchase_counter = 0
                except Exception as e:
                    print(f'❌ AUTO-PURCHASE ERROR: {e}')

    def cast_line(self):
        """Perform the casting action: hold click for 1 second then release"""  # inserted
        self.log('Casting line...', "verbose")
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        threading.Event().wait(1.0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self.is_clicking = False
        
        # Update activity tracking
        self.last_activity_time = time.time()
        
        self.log('Line cast', "verbose")

    def main_loop(self):
        """Main loop that runs when activated - delegates to fishing bot"""
        self.fishing_bot.run_main_loop()
    

    
    def set_recovery_state(self, state, details=None):
        """Update current state for smart recovery tracking"""
        self.current_state = state
        self.state_start_time = time.time()
        self.last_activity_time = time.time()
        self.state_details = details or {}
        
        # Dev mode state tracking
        if self.dev_mode or self.verbose_logging:
            detail_str = f" - {details}" if details else ""
            self.log(f'🔄 State: {state}{detail_str}', "verbose")
    

    
    def update_runtime_timer(self):
        """Update the runtime display"""
        if not self.main_loop_active and not self.is_paused:
            return
            
        if self.start_time:
            current_time = time.time()
            if self.is_paused and self.pause_time:
                # Currently paused - don't count pause time
                elapsed = (self.pause_time - self.start_time) - self.total_paused_time
            else:
                # Currently running - count total time minus pauses
                elapsed = (current_time - self.start_time) - self.total_paused_time
            
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            
            runtime_text = f'⏱️ Runtime: {hours:02d}:{minutes:02d}:{seconds:02d}'
            
            try:
                self.root.after(0, lambda: self.runtime_label.config(text=runtime_text))
            except Exception:
                pass
        
        # Schedule next update if still active
        if self.main_loop_active or self.is_paused:
            self.root.after(1000, self.update_runtime_timer)


    def toggle_overlay(self):
        """Toggle the overlay on/off"""
        self.overlay_active = not self.overlay_active
        if self.overlay_active:
            self.overlay_status.config(text='● Overlay: ACTIVE', style='StatusOn.TLabel')
            self.create_overlay()
            print(f'Overlay activated at: {self.overlay_area}')
        else:
            self.overlay_status.config(text='● Overlay: OFF', style='StatusOff.TLabel')
            self.destroy_overlay()
            print(f'Overlay deactivated. Saved area: {self.overlay_area}')

    def create_overlay(self):
        """Create a draggable, resizable overlay window"""
        if self.overlay_window is not None:
            return
        
        # Create overlay window
        self.overlay_window = tk.Toplevel(self.root)
        
        # Remove window decorations (title bar, borders)
        self.overlay_window.overrideredirect(True)
        
        # Set window properties
        self.overlay_window.attributes('-alpha', 0.5)  # Semi-transparent
        self.overlay_window.attributes('-topmost', True)  # Always on top
        
        # Remove minimum size restrictions
        self.overlay_window.minsize(1, 1)
        
        # Set geometry from saved area
        x = self.overlay_area['x']
        y = self.overlay_area['y']
        width = self.overlay_area['width']
        height = self.overlay_area['height']
        geometry = f"{width}x{height}+{x}+{y}"
        self.overlay_window.geometry(geometry)
        
        # Create frame with border (using #55aaff color)
        frame = tk.Frame(self.overlay_window, bg='#55aaff', highlightthickness=2, highlightbackground='#55aaff')
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Bind mouse events for dragging and resizing
        self.overlay_window.bind("<ButtonPress-1>", self.start_overlay_action)
        self.overlay_window.bind("<B1-Motion>", self.overlay_motion)
        self.overlay_window.bind("<Motion>", self.update_cursor)
        self.overlay_window.bind("<Configure>", self.on_overlay_configure)
        
        # Bind to frame as well
        frame.bind("<ButtonPress-1>", self.start_overlay_action)
        frame.bind("<B1-Motion>", self.overlay_motion)
        frame.bind("<Motion>", self.update_cursor)

    def get_resize_edge(self, x, y):
        """Determine which edge/corner is near the mouse"""
        width = self.overlay_window.winfo_width()
        height = self.overlay_window.winfo_height()
        edge_size = 10
        on_left = x < edge_size
        on_right = x > width - edge_size
        on_top = y < edge_size
        on_bottom = y > height - edge_size
        
        if on_top and on_left:
            return "nw"
        elif on_top and on_right:
            return "ne"
        elif on_bottom and on_left:
            return "sw"
        elif on_bottom and on_right:
            return "se"
        elif on_left:
            return "w"
        elif on_right:
            return "e"
        elif on_top:
            return "n"
        elif on_bottom:
            return "s"
        return None

    def update_cursor(self, event):
        """Update cursor based on position"""  # inserted
        edge = self.get_resize_edge(event.x, event.y)
        cursor_map = {'nw': 'size_nw_se', 'ne': 'size_ne_sw', 'sw': 'size_ne_sw', 'se': 'size_nw_se', 'n': 'size_ns', 's': 'size_ns', 'e': 'size_we', 'w': 'size_we', None: 'arrow'}
        self.overlay_window.config(cursor=cursor_map.get(edge, 'arrow'))

    def start_overlay_action(self, event):
        """Start dragging or resizing the overlay"""  # inserted
        self.overlay_drag_data['x'] = event.x
        self.overlay_drag_data['y'] = event.y
        self.overlay_drag_data['resize_edge'] = self.get_resize_edge(event.x, event.y)
        self.overlay_drag_data['start_width'] = self.overlay_window.winfo_width()
        self.overlay_drag_data['start_height'] = self.overlay_window.winfo_height()
        self.overlay_drag_data['start_x'] = self.overlay_window.winfo_x()
        self.overlay_drag_data['start_y'] = self.overlay_window.winfo_y()

    def overlay_motion(self, event):
        """Handle dragging or resizing the overlay"""
        edge = self.overlay_drag_data['resize_edge']
        
        if edge is None:
            # Dragging
            x = self.overlay_window.winfo_x() + event.x - self.overlay_drag_data['x']
            y = self.overlay_window.winfo_y() + event.y - self.overlay_drag_data['y']
            self.overlay_window.geometry(f'+{x}+{y}')
        else:
            # Resizing
            dx = event.x - self.overlay_drag_data['x']
            dy = event.y - self.overlay_drag_data['y']
            
            new_width = self.overlay_drag_data['start_width']
            new_height = self.overlay_drag_data['start_height']
            new_x = self.overlay_drag_data['start_x']
            new_y = self.overlay_drag_data['start_y']
            
            # Handle horizontal resize
            if 'e' in edge:
                new_width = max(1, self.overlay_drag_data['start_width'] + dx)
            elif 'w' in edge:
                new_width = max(1, self.overlay_drag_data['start_width'] - dx)
                new_x = self.overlay_drag_data['start_x'] + dx
            
            # Handle vertical resize
            if 's' in edge:
                new_height = max(1, self.overlay_drag_data['start_height'] + dy)
            elif 'n' in edge:
                new_height = max(1, self.overlay_drag_data['start_height'] - dy)
                new_y = self.overlay_drag_data['start_y'] + dy
            
            self.overlay_window.geometry(f"{new_width}x{new_height}+{new_x}+{new_y}")

    def on_overlay_configure(self, event=None):
        """Save overlay position and size when it changes"""  # inserted
        if self.overlay_window is not None:
            self.overlay_area['x'] = self.overlay_window.winfo_x()
            self.overlay_area['y'] = self.overlay_window.winfo_y()
            self.overlay_area['width'] = self.overlay_window.winfo_width()
            self.overlay_area['height'] = self.overlay_window.winfo_height()
        return None

    def destroy_overlay(self):
        """Destroy the overlay window"""
        if self.overlay_window is not None:
            self.overlay_area['x'] = self.overlay_window.winfo_x()
            self.overlay_area['y'] = self.overlay_window.winfo_y()
            self.overlay_area['width'] = self.overlay_window.winfo_width()
            self.overlay_area['height'] = self.overlay_window.winfo_height()
            self.overlay_window.destroy()
            self.overlay_window = None

    def exit_app(self):
        """Exit the application"""
        print('Exiting application...')
        self.main_loop_active = False
        
        # Auto-save settings before exit
        self.auto_save_settings()

        # Stop system tray if running
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass

        # Destroy overlay window if it exists
        if self.overlay_window is not None:
            try:
                self.overlay_window.destroy()
                self.overlay_window = None
            except Exception:
                pass

        # Unhook all keyboard events
        try:
            keyboard.unhook_all()
        except Exception:
            pass

        # Destroy main root window
        try:
            self.root.destroy()
        except Exception:
            pass

        # Exit the program
        sys.exit(0)

    def create_auto_purchase_section(self, start_row):
        """Create the auto purchase collapsible section"""
        section = CollapsibleFrame(self.main_frame, "🛒 Auto Purchase Settings", start_row)
        self.collapsible_sections['auto_purchase'] = section
        frame = section.get_content_frame()
        
        # Configure frame for centering
        frame.columnconfigure((0, 1, 2, 3), weight=1)
        
        # Auto Purchase Active
        row = 0
        ttk.Label(frame, text='Active:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.auto_purchase_var = tk.BooleanVar(value=False)
        auto_check = ttk.Checkbutton(frame, variable=self.auto_purchase_var, text='Enabled')
        auto_check.grid(row=row, column=1, pady=5, sticky='w')
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Automatically buy bait after catching fish. Requires setting Points 1-4.")
        # Auto-save when auto-purchase is toggled
        self.auto_purchase_var.trace_add('write', lambda *args: self.auto_save_settings())
        row += 1
        
        # Purchase Amount
        ttk.Label(frame, text='Amount:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.amount_var = tk.IntVar(value=10)
        amount_spinbox = ttk.Spinbox(frame, from_=0, to=1000000, increment=1, textvariable=self.amount_var, width=10)
        amount_spinbox.grid(row=row, column=1, pady=5, sticky='w')
        # Auto-save when amount changes
        self.amount_var.trace_add('write', lambda *args: self.auto_save_settings())
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "How much bait to buy each time (e.g., 10 = buy 10 bait)")
        self.amount_var.trace_add('write', lambda *args: setattr(self, 'auto_purchase_amount', self.amount_var.get()))
        self.auto_purchase_amount = self.amount_var.get()
        row += 1
        
        # Loops per Purchase
        ttk.Label(frame, text='Loops per Purchase:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.loops_var = tk.IntVar(value=10)
        loops_spinbox = ttk.Spinbox(frame, from_=1, to=1000000, increment=1, textvariable=self.loops_var, width=10)
        loops_spinbox.grid(row=row, column=1, pady=5, sticky='w')
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Buy bait every X fish caught (e.g., 10 = buy bait after every 10 fish)")
        self.loops_var.trace_add('write', lambda *args: setattr(self, 'loops_per_purchase', self.loops_var.get()))
        # Auto-save when loops per purchase changes
        self.loops_var.trace_add('write', lambda *args: self.auto_save_settings())
        self.loops_per_purchase = self.loops_var.get()
        row += 1
        
        # Point buttons for auto-purchase
        self.point_buttons = {}
        self.point_coords = {1: None, 2: None, 3: None, 4: None}
        
        for i in range(1, 5):
            ttk.Label(frame, text=f'Point {i}:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
            self.point_buttons[i] = ttk.Button(frame, text=f'Point {i}', command=lambda idx=i: self.capture_mouse_click(idx))
            self.point_buttons[i].grid(row=row, column=1, pady=5, sticky='w')
            help_btn = ttk.Button(frame, text='?', width=3)
            help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
            
            tooltips = {
                1: "Click to set: yes/buy button (same area)",
                2: "Click to set: Input amount area (also ... area)", 
                3: "Click to set: Close button",
                4: "Click to set: Where you want to throw the rod at. (location on the screen where the water is)"
            }
            ToolTip(help_btn, tooltips[i])
            row += 1

    def create_pd_controller_section(self, start_row):
        """Create the PD controller collapsible section"""
        section = CollapsibleFrame(self.main_frame, "⚙️ PD Controller", start_row)
        # Start collapsed by default
        section.is_expanded = False
        section.content_frame.pack_forget()
        section.toggle_btn.config(text='+')
        self.collapsible_sections['pd_controller'] = section
        frame = section.get_content_frame()
        
        # Configure frame for centering
        frame.columnconfigure((0, 1, 2), weight=1)
        
        row = 0
        ttk.Label(frame, text='Kp (Proportional):').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.kp_var = tk.DoubleVar(value=self.kp)
        kp_spinbox = ttk.Spinbox(frame, from_=0.0, to=2.0, increment=0.1, textvariable=self.kp_var, width=10)
        kp_spinbox.grid(row=row, column=1, pady=5)
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "How strongly to react to fish position. Higher = more aggressive corrections")
        self.kp_var.trace_add('write', lambda *args: setattr(self, 'kp', self.kp_var.get()))
        row += 1
        
        ttk.Label(frame, text='Kd (Derivative):').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.kd_var = tk.DoubleVar(value=self.kd)
        kd_spinbox = ttk.Spinbox(frame, from_=0.0, to=1.0, increment=0.01, textvariable=self.kd_var, width=10)
        kd_spinbox.grid(row=row, column=1, pady=5)
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Smooths movement to prevent overshooting. Higher = smoother but slower")
        self.kd_var.trace_add('write', lambda *args: setattr(self, 'kd', self.kd_var.get()))

    def create_timing_section(self, start_row):
        """Create the timing settings collapsible section"""
        section = CollapsibleFrame(self.main_frame, "⏱️ Timing Settings", start_row)
        # Start collapsed by default
        section.is_expanded = False
        section.content_frame.pack_forget()
        section.toggle_btn.config(text='+')
        self.collapsible_sections['timing'] = section
        frame = section.get_content_frame()
        
        # Configure frame for centering
        frame.columnconfigure((0, 1, 2), weight=1)
        
        row = 0
        ttk.Label(frame, text='Scan Timeout (s):').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.timeout_var = tk.DoubleVar(value=self.scan_timeout)
        timeout_spinbox = ttk.Spinbox(frame, from_=1.0, to=60.0, increment=1.0, textvariable=self.timeout_var, width=10)
        timeout_spinbox.grid(row=row, column=1, pady=5)
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "How long to wait for fish before recasting line (seconds)")
        self.timeout_var.trace_add('write', lambda *args: setattr(self, 'scan_timeout', self.timeout_var.get()))
        row += 1
        
        ttk.Label(frame, text='Wait After Loss (s):').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.wait_var = tk.DoubleVar(value=self.wait_after_loss)
        wait_spinbox = ttk.Spinbox(frame, from_=0.0, to=10.0, increment=0.1, textvariable=self.wait_var, width=10)
        wait_spinbox.grid(row=row, column=1, pady=5)
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Pause time after losing a fish before recasting (seconds)")
        self.wait_var.trace_add('write', lambda *args: setattr(self, 'wait_after_loss', self.wait_var.get()))

    def create_presets_section(self, start_row):
        """Create the presets save/load section"""
        section = CollapsibleFrame(self.main_frame, "💾 Presets", start_row)
        frame = section.get_content_frame()
        frame.columnconfigure(1, weight=1)  # Center column expands
        
        row = 0
        
        # Save preset button (centered layout like point buttons)
        ttk.Label(frame, text='Save:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        save_btn = ttk.Button(frame, text='💾 Save Preset', command=self.save_preset)
        save_btn.grid(row=row, column=1, pady=5, sticky='w')
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Save current settings (excluding webhooks and keybinds) to a preset file")
        row += 1
        
        # Load preset button (centered layout like point buttons)
        ttk.Label(frame, text='Load:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        load_btn = ttk.Button(frame, text='📁 Load Preset', command=self.load_preset)
        load_btn.grid(row=row, column=1, pady=5, sticky='w')
        help_btn2 = ttk.Button(frame, text='?', width=3)
        help_btn2.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn2, "Load settings from a preset file")

    def create_hotkeys_section(self, start_row):
        """Create the hotkey bindings collapsible section"""
        section = CollapsibleFrame(self.main_frame, "⌨️ Hotkey Bindings", start_row)
        # Start collapsed by default
        section.is_expanded = False
        section.content_frame.pack_forget()
        section.toggle_btn.config(text='+')
        self.collapsible_sections['hotkeys'] = section
        frame = section.get_content_frame()
        
        # Configure frame for centering
        frame.columnconfigure((0, 1, 2, 3), weight=1)
        
        row = 0
        ttk.Label(frame, text='Toggle Main Loop:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.loop_key_label = ttk.Label(frame, text=self.hotkeys['toggle_loop'].upper(), relief=tk.RIDGE, padding=5, width=10)
        self.loop_key_label.grid(row=row, column=1, pady=5)
        self.loop_rebind_btn = ttk.Button(frame, text='Rebind', command=lambda: self.start_rebind('toggle_loop'))
        self.loop_rebind_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=3, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Start/stop the fishing bot")
        row += 1
        
        ttk.Label(frame, text='Toggle Overlay:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.overlay_key_label = ttk.Label(frame, text=self.hotkeys['toggle_overlay'].upper(), relief=tk.RIDGE, padding=5, width=10)
        self.overlay_key_label.grid(row=row, column=1, pady=5)
        self.overlay_rebind_btn = ttk.Button(frame, text='Rebind', command=lambda: self.start_rebind('toggle_overlay'))
        self.overlay_rebind_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=3, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Show/hide blue detection area overlay")
        row += 1
        
        ttk.Label(frame, text='Exit:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.exit_key_label = ttk.Label(frame, text=self.hotkeys['exit'].upper(), relief=tk.RIDGE, padding=5, width=10)
        self.exit_key_label.grid(row=row, column=1, pady=5)
        self.exit_rebind_btn = ttk.Button(frame, text='Rebind', command=lambda: self.start_rebind('exit'))
        self.exit_rebind_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=3, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Close the application completely")
        row += 1
        
        ttk.Label(frame, text='Toggle Tray:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.tray_key_label = ttk.Label(frame, text=self.hotkeys['toggle_tray'].upper(), relief=tk.RIDGE, padding=5, width=10)
        self.tray_key_label.grid(row=row, column=1, pady=5)
        self.tray_rebind_btn = ttk.Button(frame, text='Rebind', command=lambda: self.start_rebind('toggle_tray'))
        self.tray_rebind_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=3, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Toggle between system tray and normal window")

    def create_webhook_section(self, start_row):
        """Create the Discord webhook collapsible section"""
        section = CollapsibleFrame(self.main_frame, "🔗 Discord Webhook", start_row)
        self.collapsible_sections['webhook'] = section
        frame = section.get_content_frame()
        
        # Configure frame for centering
        frame.columnconfigure((0, 1, 2, 3), weight=1)
        
        row = 0
        # Enable webhook checkbox
        self.webhook_enabled_var = tk.BooleanVar(value=self.webhook_enabled)
        webhook_check = ttk.Checkbutton(frame, text='Enable Discord Webhook', variable=self.webhook_enabled_var)
        webhook_check.grid(row=row, column=0, columnspan=2, pady=5)
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Send fishing progress updates to Discord")
        self.webhook_enabled_var.trace_add('write', lambda *args: (setattr(self, 'webhook_enabled', self.webhook_enabled_var.get()), self.auto_save_settings()))
        row += 1
        
        # Webhook URL
        ttk.Label(frame, text='Webhook URL:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.webhook_url_var = tk.StringVar(value=self.webhook_url)
        webhook_entry = ttk.Entry(frame, textvariable=self.webhook_url_var, width=25)
        webhook_entry.grid(row=row, column=1, sticky='ew', pady=5)
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Discord webhook URL from your server settings")
        self.webhook_url_var.trace_add('write', lambda *args: (setattr(self, 'webhook_url', self.webhook_url_var.get()), self.auto_save_settings()))
        row += 1
        
        # Webhook interval
        ttk.Label(frame, text='Send Every X Fish:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.webhook_interval_var = tk.IntVar(value=self.webhook_interval)
        interval_spinbox = ttk.Spinbox(frame, from_=1, to=100, textvariable=self.webhook_interval_var, width=10)
        interval_spinbox.grid(row=row, column=1, pady=5, sticky='w')
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Send webhook message every X fish caught (e.g., 10 = message every 10 fish)")
        self.webhook_interval_var.trace_add('write', lambda *args: (setattr(self, 'webhook_interval', self.webhook_interval_var.get()), self.auto_save_settings()))
        row += 1
        
        # Test webhook button
        test_btn = ttk.Button(frame, text='Test Webhook', command=self.test_webhook)
        test_btn.grid(row=row, column=0, columnspan=2, pady=10)
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Send a test message to verify webhook is working")

    def create_discord_section(self, start_row):
        """Create the Discord join section at the bottom"""
        discord_frame = ttk.Frame(self.main_frame)
        discord_frame.grid(row=start_row, column=0, sticky='ew', pady=(25, 10))
        discord_frame.columnconfigure(0, weight=1)
        
        # Try to load Discord icon, fallback to text if not available
        discord_icon = None
        try:
            from PIL import Image, ImageTk
            import os
            if os.path.exists("images/discord.png"):
                img = Image.open("images/discord.png")
                img = img.resize((24, 24), Image.Resampling.LANCZOS)
                discord_icon = ImageTk.PhotoImage(img)
        except:
            pass  # Fallback to text-only button
        
        button_bg = '#21262d' if self.dark_theme else '#f6f8fa'
        button_fg = '#58a6ff' if self.dark_theme else '#0969da'
        button_hover_bg = '#30363d' if self.dark_theme else '#f3f4f6'
        
        if discord_icon:
            discord_btn = tk.Button(discord_frame, text='  Join our Discord!', 
                                  image=discord_icon, compound='left',
                                  command=self.open_discord,
                                  bg=button_bg, fg=button_fg,
                                  activebackground=button_hover_bg,
                                  activeforeground=button_fg,
                                  relief='flat', borderwidth=1,
                                  font=('Segoe UI', 9),
                                  cursor='hand2',
                                  padx=10, pady=5)
            discord_btn.image = discord_icon
        else:
            discord_btn = tk.Button(discord_frame, text='💬 Join our Discord!', 
                                  command=self.open_discord,
                                  bg=button_bg, fg=button_fg,
                                  activebackground=button_hover_bg,
                                  activeforeground=button_fg,
                                  relief='flat', borderwidth=1,
                                  font=('Segoe UI', 9),
                                  cursor='hand2',
                                  padx=10, pady=5)
        
        discord_btn.pack(pady=5, padx=10, fill='x')
        
        # Add combined hover effects and tooltip
        tooltip_window = None
        
        def on_enter(e):
            nonlocal tooltip_window
            discord_btn.config(bg=button_hover_bg)
            
            # Show tooltip
            if tooltip_window is None:
                x = discord_btn.winfo_rootx() + 20
                y = discord_btn.winfo_rooty() + 20
                
                tooltip_window = tk.Toplevel(discord_btn)
                tooltip_window.wm_overrideredirect(True)
                tooltip_window.wm_attributes('-topmost', True)
                tooltip_window.wm_geometry(f"+{x}+{y}")
                
                label = tk.Label(tooltip_window, text="Click to join our Discord community!", 
                               justify='left', background="#ffffe0", relief='solid', 
                               borderwidth=1, font=("Arial", 9), padx=5, pady=3)
                label.pack()
        
        def on_leave(e):
            nonlocal tooltip_window
            discord_btn.config(bg=button_bg)
            
            # Hide tooltip
            if tooltip_window:
                tooltip_window.destroy()
                tooltip_window = None
        
        discord_btn.bind("<Enter>", on_enter)
        discord_btn.bind("<Leave>", on_leave)

    def open_discord(self):
        """Open Discord invite link in browser"""
        import webbrowser
        try:
            webbrowser.open('https://discord.gg/5Gtsgv46ce')
            self.status_msg.config(text='Opened Discord invite', foreground='#0DA50DFF')
        except Exception as e:
            self.status_msg.config(text=f'Error opening Discord: {e}', foreground='red')

    def check_for_updates(self):
        """Manual update check triggered by user"""
        if not self.update_manager:
            self.update_status('UpdateManager not available', 'error', '❌')
            return
        
        # Run update check in background thread
        threading.Thread(target=self.update_manager.check_for_updates_manual, daemon=True).start()


    
    def update_status(self, message, status_type='info', icon=''):
        """Update status message from UpdateManager"""
        color_map = {
            'success': 'green',
            'error': 'red',
            'warning': 'orange',
            'info': '#58a6ff'
        }
        color = color_map.get(status_type, '#58a6ff')
        
        full_message = f'{icon} {message}' if icon else message
        self.status_msg.config(text=full_message, foreground=color)

    def test_webhook(self):
        """Send a test webhook message"""
        self.webhook_manager.test()

    def apply_theme(self):
        """Apply the current theme to the application"""
        style = ttk.Style()
        
        # Get theme colors from theme manager
        theme_colors = self.theme_manager.themes[self.current_theme]["colors"]
        is_dark = theme_colors["bg"] == "#0d1117"
        
        if is_dark:
            # Modern dark theme with gradients and rounded corners
            self.root.configure(bg=theme_colors["bg"])
            style.theme_use('clam')
            
            # Modern dark colors
            style.configure('TFrame', 
                          background=theme_colors["bg"],
                          relief='flat',
                          borderwidth=0)
            
            style.configure('TLabel', 
                          background=theme_colors["bg"], 
                          foreground=theme_colors["fg"],
                          font=('Segoe UI', 9))
            
            # Modern button styling
            style.configure('TButton',
                          background=theme_colors["button_bg"],
                          foreground=theme_colors["fg"],
                          borderwidth=1,
                          focuscolor='none',
                          font=('Segoe UI', 9),
                          relief='flat')
            style.map('TButton',
                     background=[('active', theme_colors["button_hover"]), ('pressed', theme_colors["button_hover"])],
                     bordercolor=[('active', theme_colors["accent"]), ('pressed', theme_colors["accent"])])
            
            # Accent button for primary actions
            style.configure('Accent.TButton',
                          background='#238636',
                          foreground='#ffffff',
                          borderwidth=0,
                          font=('Segoe UI', 9, 'bold'))
            style.map('Accent.TButton',
                     background=[('active', '#2ea043'), ('pressed', '#1a7f37')])
            
            # Status buttons
            style.configure('Status.TButton',
                          background='#1f6feb',
                          foreground='#ffffff',
                          borderwidth=0,
                          font=('Segoe UI', 9))
            style.map('Status.TButton',
                     background=[('active', '#388bfd'), ('pressed', '#0969da')])
            
            style.configure('TCheckbutton',
                          background='#0d1117',
                          foreground='#f0f6fc',
                          focuscolor='none',
                          font=('Segoe UI', 9))
            style.map('TCheckbutton',
                     background=[('active', '#0d1117')])
            
            style.configure('TSpinbox',
                          fieldbackground='#21262d',
                          background='#21262d',
                          foreground='#f0f6fc',
                          bordercolor='#30363d',
                          arrowcolor='#f0f6fc',
                          font=('Segoe UI', 9))
            
            # Scrollbar styling for dark mode
            style.configure('Vertical.TScrollbar',
                          background='#21262d',
                          troughcolor='#0d1117',
                          bordercolor='#30363d',
                          arrowcolor='#8b949e',
                          darkcolor='#21262d',
                          lightcolor='#30363d')
            style.map('Vertical.TScrollbar',
                     background=[('active', '#30363d'), ('pressed', '#484f58')])
            
            # Header styling
            style.configure('Title.TLabel',
                          background=theme_colors["bg"],
                          foreground=theme_colors["accent"],
                          font=('Segoe UI', 18, 'bold'))
            
            style.configure('Subtitle.TLabel',
                          background=theme_colors["bg"],
                          foreground=theme_colors["fg"],
                          font=('Segoe UI', 8))
            
            # Section title styling
            style.configure('SectionTitle.TLabel',
                          background=theme_colors["bg"],
                          foreground=theme_colors["accent"],
                          font=('Segoe UI', 11, 'bold'))
            
            # Status labels
            style.configure('StatusOn.TLabel',
                          background=theme_colors["bg"],
                          foreground=theme_colors["success"],
                          font=('Segoe UI', 10, 'bold'))
            
            style.configure('StatusOff.TLabel',
                          background=theme_colors["bg"],
                          foreground=theme_colors["error"],
                          font=('Segoe UI', 10))
            
            style.configure('Counter.TLabel',
                          background=theme_colors["bg"],
                          foreground=theme_colors["fg"],
                          font=('Segoe UI', 11, 'bold'))
            
            # Update canvas background for dark mode
            if hasattr(self, 'canvas'):
                self.canvas.configure(bg=theme_colors["bg"])
            
            self.theme_btn.config(text='🎨 Themes')
        else:
            # Modern light theme with clean styling
            self.root.configure(bg=theme_colors["bg"])
            style.theme_use('clam')
            
            # Light theme colors
            style.configure('TFrame', 
                          background=theme_colors["bg"],
                          relief='flat',
                          borderwidth=0)
            
            style.configure('TLabel', 
                          background=theme_colors["bg"], 
                          foreground=theme_colors["fg"],
                          font=('Segoe UI', 9))
            
            # Modern button styling for light mode
            style.configure('TButton',
                          background=theme_colors["button_bg"],
                          foreground=theme_colors["fg"],
                          borderwidth=1,
                          focuscolor='none',
                          font=('Segoe UI', 9),
                          relief='flat')
            style.map('TButton',
                     background=[('active', theme_colors["button_hover"]), ('pressed', theme_colors["button_hover"])],
                     bordercolor=[('active', theme_colors["accent"]), ('pressed', theme_colors["accent"])])
            
            # Accent button for primary actions
            style.configure('Accent.TButton',
                          background='#2da44e',
                          foreground='#ffffff',
                          borderwidth=0,
                          font=('Segoe UI', 9, 'bold'))
            style.map('Accent.TButton',
                     background=[('active', '#2c974b'), ('pressed', '#298e46')])
            
            # Status buttons
            style.configure('Status.TButton',
                          background='#0969da',
                          foreground='#ffffff',
                          borderwidth=0,
                          font=('Segoe UI', 9))
            style.map('Status.TButton',
                     background=[('active', '#0860ca'), ('pressed', '#0757ba')])
            
            style.configure('TCheckbutton',
                          background='#fafbfc',
                          foreground='#24292f',
                          focuscolor='none',
                          font=('Segoe UI', 9))
            style.map('TCheckbutton',
                     background=[('active', '#fafbfc')])
            
            style.configure('TSpinbox',
                          fieldbackground='#f6f8fa',
                          background='#e1e4e8',
                          foreground='#24292f',
                          bordercolor='#d0d7de',
                          arrowcolor='#24292f',
                          font=('Segoe UI', 9))
            
            # Entry styling to match the gray theme
            style.configure('TEntry',
                          fieldbackground='#f6f8fa',
                          background='#e1e4e8',
                          foreground='#24292f',
                          bordercolor='#d0d7de',
                          font=('Segoe UI', 9))
            
            # Scrollbar styling for light mode
            style.configure('Vertical.TScrollbar',
                          background='#e1e4e8',
                          troughcolor='#fafbfc',
                          bordercolor='#d0d7de',
                          arrowcolor='#656d76',
                          darkcolor='#e1e4e8',
                          lightcolor='#f6f8fa')
            style.map('Vertical.TScrollbar',
                     background=[('active', '#d0d7de'), ('pressed', '#c6cbd1')])
            
            # Header styling
            style.configure('Title.TLabel',
                          background=theme_colors["bg"],
                          foreground=theme_colors["accent"],
                          font=('Segoe UI', 18, 'bold'))
            
            style.configure('Subtitle.TLabel',
                          background=theme_colors["bg"],
                          foreground=theme_colors["fg"],
                          font=('Segoe UI', 8))
            
            # Section title styling
            style.configure('SectionTitle.TLabel',
                          background=theme_colors["bg"],
                          foreground=theme_colors["accent"],
                          font=('Segoe UI', 11, 'bold'))
            
            # Status labels
            style.configure('StatusOn.TLabel',
                          background=theme_colors["bg"],
                          foreground=theme_colors["success"],
                          font=('Segoe UI', 10, 'bold'))
            
            style.configure('StatusOff.TLabel',
                          background=theme_colors["bg"],
                          foreground=theme_colors["error"],
                          font=('Segoe UI', 10))
            
            style.configure('Counter.TLabel',
                          background=theme_colors["bg"],
                          foreground=theme_colors["fg"],
                          font=('Segoe UI', 11, 'bold'))
            
            # Update canvas background for light mode
            if hasattr(self, 'canvas'):
                self.canvas.configure(bg=theme_colors["bg"])
            
            self.theme_btn.config(text='🎨 Themes')
        




    def auto_save_settings(self):
        """Auto-save current settings to default.json"""
        if not hasattr(self, 'auto_purchase_var'):
            return  # Skip if not fully initialized
            
        preset_data = {
            'auto_purchase_enabled': getattr(self.auto_purchase_var, 'get', lambda: False)(),
            'auto_purchase_amount': getattr(self.amount_var, 'get', lambda: getattr(self, 'auto_purchase_amount', 100))(),
            'loops_per_purchase': getattr(self.loops_var, 'get', lambda: getattr(self, 'loops_per_purchase', 1))(),
            'point_coords': getattr(self, 'point_coords', {}),
            'kp': getattr(self, 'kp', 0.1),
            'kd': getattr(self, 'kd', 0.5),
            'scan_timeout': getattr(self, 'scan_timeout', 15.0),
            'wait_after_loss': getattr(self, 'wait_after_loss', 1.0),
            'smart_check_interval': getattr(self, 'smart_check_interval', 15.0),
            'webhook_url': getattr(self, 'webhook_url', ''),
            'webhook_enabled': getattr(self, 'webhook_enabled', False),
            'webhook_interval': getattr(self, 'webhook_interval', 10),
            'dark_theme': getattr(self, 'dark_theme', True),
            'current_theme': getattr(self, 'current_theme', 'default'),
            'last_saved': datetime.now().isoformat()
        }
        
        settings_file = "default_settings.json"
        try:
            with open(settings_file, 'w') as f:
                json.dump(preset_data, f, indent=2)
        except Exception as e:
            print(f'Error auto-saving settings: {e}')

    def save_preset(self):
        """Save current settings to a preset file (excluding webhooks and keybinds)"""
        try:
            # Ask user for preset name
            preset_name = simpledialog.askstring("Save Preset", "Enter preset name:")
            if not preset_name:
                return
            
            # Clean filename
            import re
            preset_name = re.sub(r'[<>:"/\\|?*]', '_', preset_name)
            
            # Collect all settings except webhooks and keybinds
            preset_data = {
                # Auto-purchase settings
                'auto_purchase_enabled': getattr(self, 'auto_purchase_var', None) and self.auto_purchase_var.get() if hasattr(self, 'auto_purchase_var') else False,
                'auto_purchase_amount': getattr(self, 'auto_purchase_amount', 100),
                'loops_per_purchase': getattr(self, 'loops_per_purchase', 1),
                'point_coords': getattr(self, 'point_coords', {}),
                
                # PD Controller settings
                'kp': getattr(self, 'kp', 0.1),
                'kd': getattr(self, 'kd', 0.5),
                
                # Timing settings
                'scan_timeout': getattr(self, 'scan_timeout', 15.0),
                'wait_after_loss': getattr(self, 'wait_after_loss', 1.0),
                'purchase_delay_after_key': getattr(self, 'purchase_delay_after_key', 2.0),
                'purchase_click_delay': getattr(self, 'purchase_click_delay', 1.0),
                'purchase_after_type_delay': getattr(self, 'purchase_after_type_delay', 1.0),
                
                # Overlay settings
                'overlay_area': getattr(self, 'overlay_area', {}),
                
                # Recovery settings
                'recovery_enabled': getattr(self, 'recovery_enabled', True),
                
                # Performance settings
                'silent_mode': getattr(self, 'silent_mode', False),
                'verbose_logging': getattr(self, 'verbose_logging', False),
                
                # Theme settings
                'dark_theme': getattr(self, 'dark_theme', True),
            }
            
            # Save to presets folder
            preset_file = os.path.join(self.presets_dir, f"{preset_name}.json")
            with open(preset_file, 'w') as f:
                json.dump(preset_data, f, indent=2)
            
            self.status_msg.config(text=f'Preset "{preset_name}" saved successfully!', foreground='green')
            print(f'✅ Preset saved: {preset_file}')
            
        except Exception as e:
            self.status_msg.config(text=f'Error saving preset: {e}', foreground='red')
            print(f'❌ Error saving preset: {e}')

    def load_preset(self):
        """Load settings from a preset file"""
        try:
            # Show file dialog to select preset
            preset_file = filedialog.askopenfilename(
                title="Load Preset",
                initialdir=self.presets_dir,
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if not preset_file:
                return
            
            # Load preset data
            with open(preset_file, 'r') as f:
                preset_data = json.load(f)
            
            # Apply settings (excluding webhooks and keybinds)
            
            # Auto-purchase settings
            if hasattr(self, 'auto_purchase_var'):
                self.auto_purchase_var.set(preset_data.get('auto_purchase_enabled', False))
            self.auto_purchase_amount = preset_data.get('auto_purchase_amount', 100)
            if hasattr(self, 'amount_var'):
                self.amount_var.set(self.auto_purchase_amount)
            
            self.loops_per_purchase = preset_data.get('loops_per_purchase', 1)
            if hasattr(self, 'loops_var'):
                self.loops_var.set(self.loops_per_purchase)
            
            # Convert string keys back to integers for point_coords
            loaded_coords = preset_data.get('point_coords', {})
            self.point_coords = {}
            for key, value in loaded_coords.items():
                try:
                    int_key = int(key)
                    self.point_coords[int_key] = value
                except (ValueError, TypeError):
                    pass
            # Update point buttons if they exist
            for idx in range(1, 5):
                if hasattr(self, 'point_buttons') and idx in self.point_buttons:
                    self.update_point_button(idx)
            
            # PD Controller settings
            self.kp = preset_data.get('kp', 0.1)
            if hasattr(self, 'kp_var'):
                self.kp_var.set(self.kp)
            
            self.kd = preset_data.get('kd', 0.5)
            if hasattr(self, 'kd_var'):
                self.kd_var.set(self.kd)
            
            # Timing settings
            self.scan_timeout = preset_data.get('scan_timeout', 15.0)
            if hasattr(self, 'timeout_var'):
                self.timeout_var.set(self.scan_timeout)
            
            self.wait_after_loss = preset_data.get('wait_after_loss', 1.0)
            if hasattr(self, 'wait_var'):
                self.wait_var.set(self.wait_after_loss)
            
            self.purchase_delay_after_key = preset_data.get('purchase_delay_after_key', 2.0)
            self.purchase_click_delay = preset_data.get('purchase_click_delay', 1.0)
            self.purchase_after_type_delay = preset_data.get('purchase_after_type_delay', 1.0)
            
            # Overlay settings
            if 'overlay_area' in preset_data and preset_data['overlay_area']:
                self.overlay_area = preset_data['overlay_area']
            
            # Recovery settings
            self.recovery_enabled = preset_data.get('recovery_enabled', True)
            
            # Performance settings
            self.silent_mode = preset_data.get('silent_mode', False)
            self.verbose_logging = preset_data.get('verbose_logging', False)
            
            # Theme settings
            new_theme = preset_data.get('dark_theme', True)
            if new_theme != self.dark_theme:
                self.dark_theme = new_theme
                self.apply_theme()
                self.theme_btn.config(text='☀ Light Mode' if self.dark_theme else '🌙 Dark Mode')
            

            
            preset_name = os.path.splitext(os.path.basename(preset_file))[0]
            self.status_msg.config(text=f'Preset "{preset_name}" loaded successfully!', foreground='green')
            print(f'✅ Preset loaded: {preset_file}')
            
            # Auto-save the loaded settings as current defaults
            self.auto_save_settings()
            
        except Exception as e:
            self.status_msg.config(text=f'Error loading preset: {e}', foreground='red')
            print(f'❌ Error loading preset: {e}')

    def load_basic_settings(self):
        """Load basic settings before UI creation"""
        settings_file = "default_settings.json"
        if not os.path.exists(settings_file):
            return  # No saved settings, use defaults
            
        try:
            with open(settings_file, 'r') as f:
                preset_data = json.load(f)
            
            # Load basic settings that don't require UI elements
            self.auto_purchase_amount = preset_data.get('auto_purchase_amount', 100)
            self.loops_per_purchase = preset_data.get('loops_per_purchase', 1)
            
            # Convert string keys back to integers for point_coords
            loaded_coords = preset_data.get('point_coords', {})
            self.point_coords = {}
            for key, value in loaded_coords.items():
                try:
                    int_key = int(key)
                    self.point_coords[int_key] = value
                except (ValueError, TypeError):
                    pass
            self.kp = preset_data.get('kp', 0.1)
            self.kd = preset_data.get('kd', 0.5)
            self.scan_timeout = preset_data.get('scan_timeout', 15.0)
            self.wait_after_loss = preset_data.get('wait_after_loss', 1.0)
            self.smart_check_interval = preset_data.get('smart_check_interval', 15.0)
            self.webhook_url = preset_data.get('webhook_url', '')
            self.webhook_enabled = preset_data.get('webhook_enabled', False)
            self.webhook_interval = preset_data.get('webhook_interval', 10)
            self.dark_theme = preset_data.get('dark_theme', True)
            self.current_theme = preset_data.get('current_theme', 'default')
            
        except Exception as e:
            print(f'Error loading basic settings: {e}')

    def load_ui_settings(self):
        """Load UI-specific settings after widgets are created"""
        settings_file = "default_settings.json"
        if not os.path.exists(settings_file):
            return  # No saved settings, use defaults
            
        try:
            with open(settings_file, 'r') as f:
                preset_data = json.load(f)
            
            # Update UI variables if they exist
            if hasattr(self, 'auto_purchase_var'):
                self.auto_purchase_var.set(preset_data.get('auto_purchase_enabled', False))
            if hasattr(self, 'amount_var'):
                self.amount_var.set(self.auto_purchase_amount)
            if hasattr(self, 'loops_var'):
                self.loops_var.set(self.loops_per_purchase)
            if hasattr(self, 'webhook_enabled_var'):
                self.webhook_enabled_var.set(self.webhook_enabled)
            if hasattr(self, 'webhook_url_var'):
                self.webhook_url_var.set(self.webhook_url)
            if hasattr(self, 'webhook_interval_var'):
                self.webhook_interval_var.set(self.webhook_interval)
            
            # Update UI elements
            if hasattr(self, 'point_buttons'):
                self.update_point_buttons()
            if hasattr(self, 'auto_update_btn'):
                self.update_auto_update_button()
            
        except Exception as e:
            print(f'Error loading UI settings: {e}')

    def update_point_buttons(self):
        """Update point button texts with coordinates"""
        for idx, coords in self.point_coords.items():
            if coords and idx in self.point_buttons:
                self.point_buttons[idx].config(text=f'Point {idx}: {coords}')

    def update_hotkey_labels(self):
        """Update hotkey label texts"""
        try:
            self.loop_key_label.config(text=self.hotkeys['toggle_loop'].upper())
            self.overlay_key_label.config(text=self.hotkeys['toggle_overlay'].upper())
            self.exit_key_label.config(text=self.hotkeys['exit'].upper())
            self.tray_key_label.config(text=self.hotkeys['toggle_tray'].upper())
        except AttributeError:
            pass  # Labels not created yet



    def setup_system_tray(self):
        """Setup system tray functionality"""
        try:
            # Create a simple icon
            image = Image.new('RGB', (64, 64), color='blue')
            draw = ImageDraw.Draw(image)
            draw.text((10, 20), "GPO", fill='white')
            
            menu = pystray.Menu(
                pystray.MenuItem("Show", self.show_from_tray),
                pystray.MenuItem("Toggle Loop", self.toggle_main_loop),
                pystray.MenuItem("Toggle Overlay", self.toggle_overlay),
                pystray.MenuItem("Exit", self.exit_app)
            )
            
            self.tray_icon = pystray.Icon("GPO Autofish", image, menu=menu)
        except Exception as e:
            print(f"Error setting up system tray: {e}")

    def minimize_to_tray(self):
        """Minimize the application to system tray"""
        if self.tray_icon:
            self.root.withdraw()
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_from_tray(self):
        """Show the application from system tray"""
        self.root.deiconify()
        self.root.lift()
        if self.tray_icon:
            self.tray_icon.stop()
    
    def restore_from_tray(self):
        """Alias for show_from_tray for consistency"""
        self.show_from_tray()

def main():
    root = tk.Tk()
    app = HotkeyGUI(root)
    root.protocol('WM_DELETE_WINDOW', app.exit_app)
    root.mainloop()
if __name__ == '__main__':
    main()

def main():
    root = tk.Tk()
    app = HotkeyGUI(root)
    root.protocol('WM_DELETE_WINDOW', app.exit_app)
    root.mainloop()

if __name__ == '__main__':
    main()