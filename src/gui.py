import tkinter as tk
from tkinter import ttk, filedialog, simpledialog, messagebox
import threading
import keyboard
from pynput import keyboard as pynput_keyboard
from pynput import mouse as pynput_mouse
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
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

from settings import SettingsManager
from overlay import OverlayManager
from webhook import WebhookManager
from updater import UpdateManager
from fishing import FishingBot
from themes import ThemeManager

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
        tw.wm_attributes('-topmost', True)
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
        self.header_frame.columnconfigure(0, weight=1)
        
        # Title label with modern typography
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
        """Toggle the visibility of the content frame"""
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
        self.overlay_area = {
            'x': int(100 * self.dpi_scale),
            'y': int(100 * self.dpi_scale),
            'width': int(base_width * self.dpi_scale),
            'height': int(base_height * self.dpi_scale)
        }
        
        self.hotkeys = {'toggle_loop': 'f1', 'toggle_overlay': 'f2', 'exit': 'f3', 'toggle_tray': 'f4'}
        self.purchase_counter = 0
        self.purchase_delay_after_key = 2.0
        self.purchase_click_delay = 1.0
        self.purchase_after_type_delay = 1.0
        self.fish_count = 0
        
        # Discord webhook settings
        self.webhook_url = ""
        self.webhook_enabled = False
        self.webhook_interval = 10
        self.webhook_counter = 0
        
        # Auto-update settings
        self.auto_update_enabled = False
        self.last_update_check = 0
        self.update_check_interval = 300
        self.pending_update = None
        self.current_version = "1.5"
        self.repo_url = "https://api.github.com/repos/arielldev/gpo-fishing/commits/main"
        
        # Performance settings
        self.silent_mode = False
        self.verbose_logging = False
        
        # Smart Recovery System
        self.last_activity_time = time.time()
        self.last_fish_time = time.time()
        self.recovery_enabled = True
        self.smart_check_interval = 15.0
        self.last_smart_check = time.time()
        self.recovery_count = 0
        self.last_recovery_time = 0
        
        # Advanced state tracking
        self.current_state = "idle"
        self.state_start_time = time.time()
        self.state_details = {}
        self.stuck_actions = []
        
        # Smart timeouts for each specific action
        self.max_state_duration = {
            "fishing": 50.0,
            "purchasing": 60.0,
            "casting": 15.0,
            "menu_opening": 10.0,
            "typing": 8.0,
            "clicking": 5.0,
            "idle": 45.0
        }
        
        # Dev mode logging
        self.dev_mode = False
        
        # Runtime tracking
        self.start_time = None
        self.pause_time = None
        self.total_paused_time = 0
        self.is_paused = False
        
        # Check if running with pythonw (silent mode)
        if 'pythonw' in sys.executable.lower():
            self.silent_mode = True
        
        # Theme system
        self.current_theme = "default"  # default, christmas
        self.theme_window = None
        self.tray_icon = None
        self.collapsible_sections = {}
        
        # Preset management
        self.presets_dir = "presets"
        if not os.path.exists(self.presets_dir):
            os.makedirs(self.presets_dir)
        
        # Point buttons for auto-purchase
        self.point_buttons = {}
        self.point_coords = {1: None, 2: None, 3: None, 4: None}
        
        # Initialize theme manager
        self.theme_manager = ThemeManager(self)
        
        # Load basic settings before creating widgets
        self.load_basic_settings()
        
        self.create_widgets()
        
        # Load UI-specific settings after widgets are created
        self.load_ui_settings()
        
        self.apply_theme()
        self.register_hotkeys()
        
        # Set compact window size with modern scrolling
        self.root.geometry('420x700')
        self.root.resizable(True, True)
        self.root.update_idletasks()
        self.root.minsize(400, 450)
        
        # Setup system tray if available
        if TRAY_AVAILABLE:
            self.setup_system_tray()
        
        # Check for updates immediately on startup if enabled, then start regular loop
        if self.auto_update_enabled:
            self.root.after(2000, self.startup_update_check)
        self.root.after(5000, self.start_auto_update_loop)
        
        # Save settings when window is closed
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Save settings when window is closed
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def get_dpi_scale(self):
        """Get the DPI scaling factor for the current display"""
        try:
            dpi = self.root.winfo_fpixels('1i')
            scale = dpi / 96.0
            return scale
        except:
            return 1.0
    
    def log(self, message, level="info"):
        """Smart logging that respects silent mode"""
        if self.silent_mode and level == "verbose":
            return
        if not self.silent_mode or level in ["error", "important"]:
            print(message)
    
    def on_closing(self):
        """Handle window closing - save settings and cleanup"""
        try:
            # Save settings before closing
            self.auto_save_settings()
            print("Settings saved on exit")
        except Exception as e:
            print(f"Error saving settings on exit: {e}")
        finally:
            # Close the application
            self.exit_app()
    
    def create_scrollable_frame(self):
        """Create a modern scrollable frame using tkinter Canvas and Scrollbar"""
        # Create main container
        self.main_container = ttk.Frame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create canvas and scrollbar with theme-aware colors
        canvas_bg = '#0d1117' if self.current_theme == 'default' else '#0d4d0d'
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
        
        # Bind mouse wheel to canvas and main frame for better scrolling
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.main_frame.bind("<MouseWheel>", self._on_mousewheel)
        
        # Also bind to Enter/Leave events to ensure focus
        self.canvas.bind("<Enter>", self._on_canvas_enter)
        self.canvas.bind("<Leave>", self._on_canvas_leave)
        self.main_frame.bind("<Enter>", self._on_frame_enter)
        self.main_frame.bind("<Leave>", self._on_frame_leave)
        
    def _on_frame_configure(self, event):
        """Reset the scroll region to encompass the inner frame"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
    def _on_canvas_configure(self, event):
        """Configure the canvas window to match the canvas width"""
        canvas_width = event.width
        self.canvas.itemconfig(self.canvas_window, width=canvas_width)
        
    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        # Check if the canvas is scrollable
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def _on_canvas_enter(self, event):
        """Bind mouse wheel when entering canvas"""
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
    
    def _on_canvas_leave(self, event):
        """Unbind mouse wheel when leaving canvas"""
        self.canvas.unbind_all("<MouseWheel>")
    
    def _on_frame_enter(self, event):
        """Bind mouse wheel when entering main frame"""
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
    
    def _on_frame_leave(self, event):
        """Unbind mouse wheel when leaving main frame"""
        self.canvas.unbind_all("<MouseWheel>")
    
    def _bind_mousewheel_to_children(self, widget):
        """Recursively bind mouse wheel to all child widgets"""
        widget.bind("<MouseWheel>", self._on_mousewheel)
        for child in widget.winfo_children():
            self._bind_mousewheel_to_children(child)
    
    def create_widgets(self):
        # Create scrollable main container
        self.create_scrollable_frame()
        self.main_frame.columnconfigure(0, weight=1)
        
        # Bind mouse wheel to all widgets after they're created
        self.root.after(100, lambda: self._bind_mousewheel_to_children(self.main_frame))
        
        current_row = 0
        
        # Modern header section
        header_frame = ttk.Frame(self.main_frame)
        header_frame.grid(row=current_row, column=0, sticky='ew', pady=(0, 20))
        header_frame.columnconfigure(0, weight=1)
        
        # Logo placeholder (will be filled by theme)
        self.logo_frame = ttk.Frame(header_frame)
        self.logo_frame.grid(row=0, column=0, pady=(0, 10))
        
        # App title with modern styling
        title = ttk.Label(header_frame, text='GPO Autofish', style='Title.TLabel')
        title.grid(row=1, column=0, pady=(0, 5))
        
        # Subtitle
        credits = ttk.Label(header_frame, text='by Ariel', style='Subtitle.TLabel')
        credits.grid(row=2, column=0, pady=(0, 15))
        
        # Modern control panel
        control_panel = ttk.Frame(header_frame)
        control_panel.grid(row=3, column=0, sticky='ew', pady=(0, 10))
        control_panel.columnconfigure(1, weight=1)  # Center spacing
        
        # Left controls
        left_controls = ttk.Frame(control_panel)
        left_controls.grid(row=0, column=0, sticky='w')
        
        self.theme_btn = ttk.Button(left_controls, text='🎨 Themes', 
                                   command=self.open_theme_window, style='TButton')
        self.theme_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        # Right controls
        right_controls = ttk.Frame(control_panel)
        right_controls.grid(row=0, column=2, sticky='e')
        
        # Auto-update toggle button
        self.auto_update_btn = ttk.Button(right_controls, text='🔄 Auto Update: OFF', 
                                         command=self.toggle_auto_update, style='TButton')
        self.auto_update_btn.pack(side=tk.LEFT, padx=(0, 8))
        
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
        
        self.fish_counter_label = ttk.Label(status_frame, text='🐟 Fish: 0', style='Counter.TLabel')
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
        self.status_msg = ttk.Label(self.main_frame, text='Ready to fish! 🎣', 
                                   font=('Arial', 10, 'bold'), foreground='#58a6ff')
        self.status_msg.grid(row=current_row, column=0, pady=(10, 0))
    
    def open_theme_window(self):
        """Open the theme selection window"""
        self.theme_manager.open_theme_window()
    
    def update_status(self, message, status_type="info", icon="🎣"):
        """Update status message"""
        try:
            self.status_msg.configure(text=f'{icon} {message}')
        except Exception:
            pass
    
    def update_status(self, message, status_type="info", icon="🎣"):
        """Update status message with enhanced styling"""
        # Status type colors
        status_colors = {
            "success": {"bg": "#DCFCE7", "border": "#22C55E", "text": "#15803D"},
            "error": {"bg": "#FEE2E2", "border": "#EF4444", "text": "#DC2626"},
            "warning": {"bg": "#FEF3C7", "border": "#F59E0B", "text": "#D97706"},
            "info": {"bg": "#F8F9FA", "border": "#E5E7EB", "text": "#1F2937"}
        }
        
        colors = status_colors.get(status_type, status_colors["info"])
        
        # Update the status container colors
        self.status_content.configure(
            fg_color=colors["bg"],
            border_color=colors["border"]
        )
        
        # Update icon and message
        self.status_icon.configure(text=icon, text_color=colors["text"])
        self.status_msg.configure(text=message, text_color=colors["text"])
    
    def _create_scrollable_frame(self):
        # Set dark red background for the main window
        self.root.configure(fg_color="#DC2626")  # Consistent dark red
        
        self.main_container = ctk.CTkFrame(self.root, fg_color="#DC2626")  # Dark red background
        self.main_container.pack(fill="both", expand=True, padx=0, pady=0)
        
        self.scrollable_frame = ctk.CTkScrollableFrame(
            self.main_container,
            fg_color="#DC2626",  # Dark red background
            scrollbar_button_color=("#FFFFFF", "#F3F4F6"),  # White scrollbar
            scrollbar_button_hover_color=("#E5E7EB", "#D1D5DB")  # Light gray hover
        )
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.main_frame = self.scrollable_frame
    
    def auto_save_settings(self):
        self.settings_manager.auto_save()

    def _create_auto_purchase_section(self, start_row):
        section = CollapsibleFrame(self.main_frame, "Auto Purchase Settings", start_row, icon="🛒")
        self.collapsible_sections['auto_purchase'] = section
        frame = section.get_content_frame()
        
        # Active Toggle
        toggle_container = ctk.CTkFrame(frame, fg_color="transparent")
        toggle_container.pack(fill='x', pady=8)
        
        self.auto_purchase_toggle_btn = ToggleButton(
            toggle_container,
            text='🛒 Auto Purchase',
            enabled=False,
            on_toggle=self.on_auto_purchase_toggle,
            width=250,
            height=40
        )
        self.auto_purchase_toggle_btn.pack(expand=True)  # Center the button
        
        # Amount
        amount_frame = self._create_input_row(frame, "Amount:", 0)
        self.amount_var = tk.IntVar(value=10)
        amount_entry = ctk.CTkEntry(
            amount_frame, 
            textvariable=self.amount_var, 
            width=120,
            height=35,
            corner_radius=8,
            font=ctk.CTkFont(size=12)
        )
        amount_entry.pack(side='left', padx=(10, 5))
        self._create_help_button(amount_frame, "How much bait to buy each time")
        self.amount_var.trace_add('write', lambda *args: (setattr(self, 'auto_purchase_amount', self.amount_var.get()), self.auto_save_settings()))
        self.auto_purchase_amount = self.amount_var.get()
        
        # Loops per Purchase
        loops_frame = self._create_input_row(frame, "Loops per Purchase:", 0)
        self.loops_var = tk.IntVar(value=10)
        loops_entry = ctk.CTkEntry(
            loops_frame, 
            textvariable=self.loops_var, 
            width=120,
            height=35,
            corner_radius=8,
            font=ctk.CTkFont(size=12)
        )
        loops_entry.pack(side='left', padx=(10, 5))
        self._create_help_button(loops_frame, "Buy bait every X fish caught")
        self.loops_var.trace_add('write', lambda *args: (setattr(self, 'loops_per_purchase', self.loops_var.get()), self.auto_save_settings()))
        self.loops_per_purchase = self.loops_var.get()
        
        # Point Buttons
        tooltips = {
            1: "Click to set: yes/buy button",
            2: "Click to set: Input amount area", 
            3: "Click to set: Close button",
            4: "Click to set: Rod throw location"
        }
        
        for i in range(1, 5):
            point_frame = self._create_input_row(frame, f'Point {i}:', 0)
            self.point_buttons[i] = AnimatedButton(
                point_frame, 
                text=f'Set Point {i}', 
                command=lambda idx=i: self.capture_mouse_click(idx),
                width=180,
                height=35
            )
            self.point_buttons[i].pack(side='left', padx=(10, 5))
            self._create_help_button(point_frame, tooltips[i])
    
    def _create_pd_controller_section(self, start_row):
        section = CollapsibleFrame(self.main_frame, "PD Controller", start_row, icon="⚙️")
        section.is_expanded = False
        section.content_frame.pack_forget()
        section.toggle_btn.configure(text='+')
        self.collapsible_sections['pd_controller'] = section
        frame = section.get_content_frame()
        
        row = 0
        kp_frame = self._create_input_row(frame, "Kp (Proportional):", row)
        self.kp_var = tk.DoubleVar(value=self.kp)
        kp_entry = ctk.CTkEntry(kp_frame, textvariable=self.kp_var, width=120, height=35, corner_radius=8)
        kp_entry.pack(side='left', padx=(10, 5))
        self._create_help_button(kp_frame, "Reaction strength to fish position")
        self.kp_var.trace_add('write', lambda *args: setattr(self, 'kp', self.kp_var.get()))
        row += 1
        
        kd_frame = self._create_input_row(frame, "Kd (Derivative):", row)
        self.kd_var = tk.DoubleVar(value=self.kd)
        kd_entry = ctk.CTkEntry(kd_frame, textvariable=self.kd_var, width=120, height=35, corner_radius=8)
        kd_entry.pack(side='left', padx=(10, 5))
        self._create_help_button(kd_frame, "Movement smoothing factor")
        self.kd_var.trace_add('write', lambda *args: setattr(self, 'kd', self.kd_var.get()))
    
    def _create_timing_section(self, start_row):
        section = CollapsibleFrame(self.main_frame, "Timing Settings", start_row, icon="⏱️")
        section.is_expanded = False
        section.content_frame.pack_forget()
        section.toggle_btn.configure(text='+')
        self.collapsible_sections['timing'] = section
        frame = section.get_content_frame()
        
        row = 0
        timeout_frame = self._create_input_row(frame, "Scan Timeout (s):", row)
        self.timeout_var = tk.DoubleVar(value=self.scan_timeout)
        timeout_entry = ctk.CTkEntry(timeout_frame, textvariable=self.timeout_var, width=120, height=35, corner_radius=8)
        timeout_entry.pack(side='left', padx=(10, 5))
        self._create_help_button(timeout_frame, "Wait time before recasting")
        self.timeout_var.trace_add('write', lambda *args: setattr(self, 'scan_timeout', self.timeout_var.get()))
        row += 1
        
        wait_frame = self._create_input_row(frame, "Wait After Loss (s):", row)
        self.wait_var = tk.DoubleVar(value=self.wait_after_loss)
        wait_entry = ctk.CTkEntry(wait_frame, textvariable=self.wait_var, width=120, height=35, corner_radius=8)
        wait_entry.pack(side='left', padx=(10, 5))
        self._create_help_button(wait_frame, "Pause after losing fish")
        self.wait_var.trace_add('write', lambda *args: setattr(self, 'wait_after_loss', self.wait_var.get()))
    
    def _create_presets_section(self, start_row):
        section = CollapsibleFrame(self.main_frame, "Presets", start_row, icon="💾")
        frame = section.get_content_frame()
        
        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(fill='x', pady=8)
        button_frame.grid_columnconfigure((0, 1), weight=1)
        
        save_btn = AnimatedButton(
            button_frame, 
            text='💾 Save Preset', 
            command=self.save_preset,
            width=200,
            height=40
        )
        save_btn.grid(row=0, column=0, padx=(0, 8))
        
        load_btn = AnimatedButton(
            button_frame, 
            text='📁 Load Preset', 
            command=self.load_preset,
            width=200,
            height=40
        )
        load_btn.grid(row=0, column=1, padx=(8, 0))
    
    def _create_hotkeys_section(self, start_row):
        section = CollapsibleFrame(self.main_frame, "Hotkey Bindings", start_row, icon="⌨️")
        section.is_expanded = False
        section.content_frame.pack_forget()
        section.toggle_btn.configure(text='+')
        self.collapsible_sections['hotkeys'] = section
        frame = section.get_content_frame()
        
        hotkeys_data = [
            ('toggle_loop', 'Toggle Main Loop', 'Start/stop fishing'),
            ('toggle_overlay', 'Toggle Overlay', 'Show/hide detection area'),
            ('exit', 'Exit', 'Close application'),
            ('toggle_tray', 'Toggle Tray', 'Minimize to tray')
        ]
        
        for idx, (key, label, tooltip) in enumerate(hotkeys_data):
            hotkey_container = ctk.CTkFrame(frame, fg_color="transparent")
            hotkey_container.pack(fill='x', pady=6)
            
            label_widget = ctk.CTkLabel(
                hotkey_container, 
                text=f'{label}:',
                font=ctk.CTkFont(size=12),
                width=140,
                anchor='w'
            )
            label_widget.pack(side='left', padx=(0, 10))
            
            key_label = ctk.CTkLabel(
                hotkey_container,
                text=self.hotkeys[key].upper(),
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#DC2626",  # Dark red background
                text_color="white",
                corner_radius=8,
                width=80,
                height=35
            )
            key_label.pack(side='left', padx=(0, 10))
            
            rebind_btn = AnimatedButton(
                hotkey_container,
                text='Rebind',
                command=lambda k=key: self.start_rebind(k),
                width=100,
                height=35
            )
            rebind_btn.pack(side='left')
            
            if key == 'toggle_loop':
                self.loop_key_label = key_label
                self.loop_rebind_btn = rebind_btn
            elif key == 'toggle_overlay':
                self.overlay_key_label = key_label
                self.overlay_rebind_btn = rebind_btn
            elif key == 'exit':
                self.exit_key_label = key_label
                self.exit_rebind_btn = rebind_btn
            elif key == 'toggle_tray':
                self.tray_key_label = key_label
                self.tray_rebind_btn = rebind_btn
    
    def _create_webhook_section(self, start_row):
        section = CollapsibleFrame(self.main_frame, "Discord Webhook", start_row, icon="🔗")
        self.collapsible_sections['webhook'] = section
        frame = section.get_content_frame()
        
        # Enable Toggle
        toggle_container = ctk.CTkFrame(frame, fg_color="transparent")
        toggle_container.pack(fill='x', pady=8)
        
        self.webhook_toggle_btn = ToggleButton(
            toggle_container,
            text='🔗 Discord Webhook',
            enabled=self.webhook_enabled,
            on_toggle=self.on_webhook_toggle,
            width=250,
            height=40
        )
        self.webhook_toggle_btn.pack(expand=True)  # Center the button
        
        # Webhook URL
        url_container = ctk.CTkFrame(frame, fg_color="transparent")
        url_container.pack(fill='x', pady=6)
        
        ctk.CTkLabel(
            url_container,
            text="Webhook URL:",
            font=ctk.CTkFont(size=12),
            width=160,
            anchor='w'
        ).pack(side='left')
        
        self.webhook_url_var = tk.StringVar(value=self.webhook_url)
        webhook_entry = ctk.CTkEntry(
            url_container,
            textvariable=self.webhook_url_var,
            height=35,
            corner_radius=8,
            placeholder_text="https://discord.com/api/webhooks/..."
        )
        webhook_entry.pack(side='left', fill='x', expand=True, padx=(10, 5))
        self._create_help_button(url_container, "Discord webhook URL from server settings")
        self.webhook_url_var.trace_add('write', lambda *args: (setattr(self, 'webhook_url', self.webhook_url_var.get()), self.auto_save_settings()))
        
        # Interval
        interval_container = ctk.CTkFrame(frame, fg_color="transparent")
        interval_container.pack(fill='x', pady=6)
        
        ctk.CTkLabel(
            interval_container,
            text="Send Every X Fish:",
            font=ctk.CTkFont(size=12),
            width=160,
            anchor='w'
        ).pack(side='left')
        
        self.webhook_interval_var = tk.IntVar(value=self.webhook_interval)
        interval_entry = ctk.CTkEntry(
            interval_container,
            textvariable=self.webhook_interval_var,
            width=120,
            height=35,
            corner_radius=8
        )
        interval_entry.pack(side='left', padx=(10, 5))
        self._create_help_button(interval_container, "Webhook notification frequency")
        self.webhook_interval_var.trace_add('write', lambda *args: (setattr(self, 'webhook_interval', self.webhook_interval_var.get()), self.auto_save_settings()))
        
        # Test Button
        test_btn = AnimatedButton(
            frame,
            text='🧪 Test Webhook',
            command=self.webhook_manager.test,
            width=200,
            height=40
        )
        test_btn.pack(pady=10)
    
    def _create_discord_section(self, start_row):
        discord_frame = GlassFrame(self.main_frame)
        discord_frame.grid(row=start_row, column=0, sticky='ew', pady=(0, 15), padx=15)
        
        discord_btn = AnimatedButton(
            discord_frame,
            text='💬 Join our Discord Community!',
            command=self.open_discord,
            font=ctk.CTkFont(size=14, weight="bold"),
            height=50,
            hover_color="#B91C1C",  # Even darker red on hover
            normal_color="#DC2626"  # Dark red background
        )
        discord_btn.pack(pady=15, padx=15, fill='x')
    
    def _create_input_row(self, parent, label_text, row):
        row_frame = ctk.CTkFrame(parent, fg_color="transparent")
        row_frame.pack(fill='x', pady=6)
        
        ctk.CTkLabel(
            row_frame,
            text=label_text,
            font=ctk.CTkFont(size=12),
            width=160,
            anchor='w'
        ).pack(side='left')
        
        return row_frame
    
    def _create_help_button(self, parent, tooltip_text):
        help_btn = ctk.CTkButton(
            parent,
            text='💡',  # Light bulb icon for better visibility
            width=35,
            height=35,
            corner_radius=17,
            fg_color="#3B82F6",  # Blue background for help
            hover_color="#2563EB",  # Darker blue on hover
            text_color="white",
            font=ctk.CTkFont(size=14, weight="bold"),
            border_width=2,
            border_color="#60A5FA"  # Light blue border
        )
        help_btn.pack(side='left', padx=(5, 0))
        
        # Create tooltip with a small delay to ensure button is fully initialized
        self.root.after(100, lambda: ToolTip(help_btn, tooltip_text))
        return help_btn
    
    def open_discord(self):
        import webbrowser
        try:
            webbrowser.open('https://discord.gg/5Gtsgv46ce')
            self.update_status('Opened Discord invite', 'success', '✅')
        except Exception as e:
            self.update_status(f'Error opening Discord: {e}', 'error', '❌')

    def capture_mouse_click(self, idx):
        try:
            self.status_msg.configure(text=f'🖱️ Click anywhere to set Point {idx}...', text_color='#1F2937')

            def _on_click(x, y, button, pressed):
                if pressed:
                    self.point_coords[idx] = (x, y)
                    try:
                        self.root.after(0, lambda: self.update_point_button(idx))
                        self.root.after(0, lambda: self.update_status(f'Point {idx} set: ({x}, {y})', 'success', '✅'))
                        self.root.after(0, lambda: self.auto_save_settings())
                    except Exception:
                        pass
                    return False
            
            listener = pynput_mouse.Listener(on_click=_on_click)
            listener.start()
        except Exception as e:
            try:
                self.status_msg.configure(text=f'❌ Error: {e}', text_color='#f85149')
            except Exception:
                return None
    
    def update_point_button(self, idx):
        coords = self.point_coords.get(idx)
        if coords and idx in self.point_buttons:
            self.point_buttons[idx].configure(text=f'✓ Point {idx}: ({coords[0]}, {coords[1]})')
        return None
    
    def start_rebind(self, action):
        self.recording_hotkey = action
        self.status_msg.configure(text=f'⌨️ Press a key to rebind \'{action}\'...', text_color='#1F2937')
        self.loop_rebind_btn.configure(state='disabled')
        self.overlay_rebind_btn.configure(state='disabled')
        self.exit_rebind_btn.configure(state='disabled')
        self.tray_rebind_btn.configure(state='disabled')
        listener = pynput_keyboard.Listener(on_press=self.on_key_press)
        listener.start()
    
    def on_key_press(self, key):
        if self.recording_hotkey:
            try:
                if hasattr(key, 'char') and key.char:
                    key_str = key.char.lower()
                elif hasattr(key, 'name'):
                    key_str = key.name.lower()
                else:
                    key_str = str(key).split('.')[-1].lower()
                
                self.hotkeys[self.recording_hotkey] = key_str
                
                if self.recording_hotkey == 'toggle_loop':
                    self.loop_key_label.configure(text=key_str.upper())
                elif self.recording_hotkey == 'toggle_overlay':
                    self.overlay_key_label.configure(text=key_str.upper())
                elif self.recording_hotkey == 'exit':
                    self.exit_key_label.configure(text=key_str.upper())
                elif self.recording_hotkey == 'toggle_tray':
                    self.tray_key_label.configure(text=key_str.upper())
                
                self.recording_hotkey = None
                self.loop_rebind_btn.configure(state='normal')
                self.overlay_rebind_btn.configure(state='normal')
                self.exit_rebind_btn.configure(state='normal')
                self.tray_rebind_btn.configure(state='normal')
                self.status_msg.configure(text=f'✅ Hotkey set to {key_str.upper()}', text_color='#16A34A')
                self.register_hotkeys()
                return False
            except Exception as e:
                self.status_msg.configure(text=f'❌ Error: {e}', text_color='#f85149')
                self.recording_hotkey = None
                self.loop_rebind_btn.configure(state='normal')
                self.overlay_rebind_btn.configure(state='normal')
                self.exit_rebind_btn.configure(state='normal')
                self.tray_rebind_btn.configure(state='normal')
                return False
        return False
    
    def register_hotkeys(self):
        try:
            keyboard.unhook_all()
            keyboard.add_hotkey(self.hotkeys['toggle_loop'], self.toggle_main_loop)
            keyboard.add_hotkey(self.hotkeys['toggle_overlay'], self.toggle_overlay)
            keyboard.add_hotkey(self.hotkeys['exit'], self.exit_app)
            keyboard.add_hotkey(self.hotkeys['toggle_tray'], self.toggle_tray_hotkey)
        except Exception as e:
            print(f'Error registering hotkeys: {e}')
    
    def toggle_tray_hotkey(self):
        if TRAY_AVAILABLE:
            if self.root.state() == 'withdrawn':
                self.restore_from_tray()
            else:
                self.minimize_to_tray()
        else:
            print("System tray not available")
    
    def toggle_main_loop(self):
        if not self.main_loop_active and not self.is_paused:
            self.start_fishing()
        elif self.main_loop_active and not self.is_paused:
            self.pause_fishing()
        elif not self.main_loop_active and self.is_paused:
            self.resume_fishing()
    
    def start_fishing(self):
        if getattr(self, 'auto_purchase_var', None) and self.auto_purchase_var.get():
            pts = getattr(self, 'point_coords', {})
            missing = [i for i in [1, 2, 3, 4] if not pts.get(i)]
            if missing:
                messagebox.showwarning('Auto Purchase: Points missing', f'Please set Point(s) {missing} before starting Auto Purchase.')
                return
        
        self.main_loop_active = True
        self.is_paused = False
        self.start_time = time.time()
        self.total_paused_time = 0
        self.reset_fish_counter()
        
        if self.updater.pending_update:
            self.updater.pending_update = None
        
        self.loop_status_card.update_status('ACTIVE', 'active')
        
        if self.auto_update_enabled:
            self.status_msg.configure(text='⏸️ Auto-update paused during fishing', text_color='#f0883e')
        
        self.main_loop_thread = threading.Thread(target=self.fishing_bot.run_main_loop, daemon=True)
        self.main_loop_thread.start()
        
        self.update_runtime_timer()
        self.log('🎣 Started fishing!', "important")
    
    def pause_fishing(self):
        self.main_loop_active = False
        self.is_paused = True
        self.pause_time = time.time()
        
        if self.is_clicking:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self.is_clicking = False
        
        self.loop_status_card.update_status('PAUSED', 'paused')
        
        if self.updater.pending_update:
            self.root.after(1000, lambda: self.updater.show_pending())
        elif self.auto_update_enabled:
            threading.Thread(target=self.updater.check, daemon=True).start()
        
        self.log('⏸️ Fishing paused', "important")
    
    def resume_fishing(self):
        if self.pause_time:
            self.total_paused_time += time.time() - self.pause_time
            self.pause_time = None
        
        self.main_loop_active = True
        self.is_paused = False
        
        self.loop_status_card.update_status('ACTIVE', 'active')
        
        self.main_loop_thread = threading.Thread(target=self.fishing_bot.run_main_loop, daemon=True)
        self.main_loop_thread.start()
        
        self.update_runtime_timer()
        self.log('▶️ Fishing resumed', "important")
    
    def increment_fish_counter(self):
        self.fish_count += 1
        self.webhook_counter += 1
        
        self.last_fish_time = time.time()
        self.last_activity_time = time.time()
        
        try:
            self.root.after(0, lambda: self.fish_counter_card.update_value(str(self.fish_count), '#FF6B6B'))
        except Exception:
            pass
        self.log(f'🐟 Fish caught: {self.fish_count}', "important")
        
        if self.webhook_enabled and self.webhook_counter >= self.webhook_interval:
            self.webhook_manager.send_fishing_progress()
            self.webhook_counter = 0
    
    def reset_fish_counter(self):
        self.fish_count = 0
        self.webhook_counter = 0
        try:
            self.root.after(0, lambda: self.fish_counter_card.update_value('0'))
        except Exception:
            pass
    
    def update_runtime_timer(self):
        if not self.main_loop_active and not self.is_paused:
            return
            
        if self.start_time:
            current_time = time.time()
            if self.is_paused and self.pause_time:
                elapsed = (self.pause_time - self.start_time) - self.total_paused_time
            else:
                elapsed = (current_time - self.start_time) - self.total_paused_time
            
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            
            runtime_text = f'{hours:02d}:{minutes:02d}:{seconds:02d}'
            
            try:
                self.root.after(0, lambda: self.runtime_card.update_value(runtime_text))
            except Exception:
                pass
        
        if self.main_loop_active or self.is_paused:
            self.root.after(1000, self.update_runtime_timer)
    
    def check_recovery_needed(self):
        if not self.recovery_enabled or not self.main_loop_active:
            return False
            
        current_time = time.time()
        
        if current_time - self.last_smart_check < 10.0:
            return False
            
        self.last_smart_check = current_time
        
        state_duration = current_time - self.state_start_time
        max_duration = self.max_state_duration.get(self.current_state, 60.0)
        
        if self.current_state == "idle" and state_duration > 30.0:
            max_duration = 30.0
        
        if state_duration > max_duration:
            stuck_info = {
                "action": self.current_state,
                "duration": state_duration,
                "max_allowed": max_duration,
                "details": self.state_details.copy(),
                "timestamp": current_time
            }
            self.stuck_actions.append(stuck_info)
            
            self.log(f'⚠️ State "{self.current_state}" stuck for {state_duration:.0f}s', "error")
            
            if self.dev_mode or self.verbose_logging:
                self.log(f'🔍 DEV: {stuck_info}', "verbose")
            
            return True
            
        time_since_activity = current_time - self.last_activity_time
        if time_since_activity > 90:
            self.log(f'⚠️ No activity for {time_since_activity:.0f}s', "error")
            return True
            
        return False
    
    def set_recovery_state(self, state, details=None):
        self.current_state = state
        self.state_start_time = time.time()
        self.last_activity_time = time.time()
        self.state_details = details or {}
        
        if self.dev_mode or self.verbose_logging:
            detail_str = f" - {details}" if details else ""
            self.log(f'🔄 State: {state}{detail_str}', "verbose")
    
    def perform_recovery(self):
        if not self.main_loop_active:
            return
            
        current_time = time.time()
        
        if current_time - self.last_recovery_time < 10:
            return
            
        self.recovery_count += 1
        self.last_recovery_time = current_time
        
        recovery_info = {
            "recovery_number": self.recovery_count,
            "stuck_state": self.current_state,
            "stuck_duration": current_time - self.state_start_time,
            "state_details": self.state_details.copy(),
            "recent_stuck_actions": self.stuck_actions[-3:] if len(self.stuck_actions) > 0 else [],
            "timestamp": current_time
        }
        
        self.log(f'🔄 Recovery #{self.recovery_count} - Restarting...', "error")
        
        self.webhook_manager.send_recovery(recovery_info)
        
        if self.is_clicking:
            try:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                self.is_clicking = False
            except Exception as e:
                self.log(f'⚠️ Error releasing mouse: {e}', "error")
        
        self.last_activity_time = current_time
        self.last_fish_time = current_time
        self.set_recovery_state("idle", {"action": "recovery_reset"})
        self.stuck_actions.clear()
        
        self.main_loop_active = False
        self.loop_status_card.update_status('RECOVERING', 'error')
        threading.Event().wait(2.0)
        
        try:
            if hasattr(self, 'main_loop_thread') and self.main_loop_thread and self.main_loop_thread.is_alive():
                self.main_loop_thread.join(timeout=5.0)
        except Exception as e:
            self.log(f'⚠️ Error joining thread: {e}', "error")
        
        self.main_loop_active = True
        self.loop_status_card.update_status('ACTIVE', 'active')
        self.main_loop_thread = threading.Thread(target=self.fishing_bot.run_main_loop, daemon=True)
        self.main_loop_thread.start()
        
        self.log('✅ Recovery complete', "important")
    
    def toggle_overlay(self):
        self.overlay_active = not self.overlay_active
        if self.overlay_active:
            self.overlay_status_card.update_status('ACTIVE', 'active')
            self.overlay_manager.create()
            print(f'Overlay activated at: {self.overlay_area}')
        else:
            self.overlay_status_card.update_status('OFF', 'default')
            self.overlay_manager.destroy()
            print(f'Overlay deactivated. Saved area: {self.overlay_area}')
    
    def on_auto_update_toggle(self, enabled):
        """Callback for auto update toggle button"""
        self.auto_update_enabled = enabled
        self.auto_save_settings()
        
        if enabled:
            self.update_status('Auto Update enabled', 'success', '✅')
        else:
            self.update_status('Auto Update disabled', 'info', '🔄')
    
    def on_webhook_toggle(self, enabled):
        """Callback for webhook toggle button"""
        self.webhook_enabled = enabled
        # Note: Webhook settings are NOT saved to default_settings.json as requested
        
        if enabled:
            self.update_status('Discord Webhook enabled', 'success', '✅')
        else:
            self.update_status('Discord Webhook disabled', 'info', '🔗')
    
    def on_auto_purchase_toggle(self, enabled):
        """Callback for auto purchase toggle button"""
        # Create the auto_purchase_var if it doesn't exist for compatibility
        if not hasattr(self, 'auto_purchase_var'):
            self.auto_purchase_var = tk.BooleanVar()
        
        self.auto_purchase_var.set(enabled)
        self.auto_save_settings()
        
        if enabled:
            self.update_status('Auto Purchase enabled', 'success', '✅')
        else:
            self.update_status('Auto Purchase disabled', 'info', '🛒')
    
    def save_preset(self):
        try:
            preset_name = simpledialog.askstring("Save Preset", "Enter preset name:")
            if not preset_name:
                return
            
            import re
            preset_name = re.sub(r'[<>:"/\\|?*]', '_', preset_name)
            
            preset_data = {
                'auto_purchase_enabled': getattr(self, 'auto_purchase_var', None) and self.auto_purchase_var.get() if hasattr(self, 'auto_purchase_var') else False,
                'auto_purchase_amount': getattr(self, 'auto_purchase_amount', 100),
                'loops_per_purchase': getattr(self, 'loops_per_purchase', 1),
                'point_coords': getattr(self, 'point_coords', {}),
                'kp': getattr(self, 'kp', 0.1),
                'kd': getattr(self, 'kd', 0.5),
                'scan_timeout': getattr(self, 'scan_timeout', 15.0),
                'wait_after_loss': getattr(self, 'wait_after_loss', 1.0),
                'purchase_delay_after_key': getattr(self, 'purchase_delay_after_key', 2.0),
                'purchase_click_delay': getattr(self, 'purchase_click_delay', 1.0),
                'purchase_after_type_delay': getattr(self, 'purchase_after_type_delay', 1.0),
                'overlay_area': getattr(self, 'overlay_area', {}),
                'recovery_enabled': getattr(self, 'recovery_enabled', True),
                'silent_mode': getattr(self, 'silent_mode', False),
                'verbose_logging': getattr(self, 'verbose_logging', False),
                'dark_theme': getattr(self, 'dark_theme', True),
                'auto_update_enabled': getattr(self, 'auto_update_enabled', False),
            }
            
            preset_file = os.path.join(self.settings_manager.presets_dir, f"{preset_name}.json")
            with open(preset_file, 'w') as f:
                json.dump(preset_data, f, indent=2)
            
            self.status_msg.configure(text=f'✅ Preset "{preset_name}" saved!', text_color='#FF6B6B')
            print(f'✅ Preset saved: {preset_file}')
            
        except Exception as e:
            self.status_msg.configure(text=f'❌ Error: {e}', text_color='#f85149')
            print(f'❌ Error saving preset: {e}')
    
    def load_preset(self):
        try:
            preset_file = filedialog.askopenfilename(
                title="Load Preset",
                initialdir=self.settings_manager.presets_dir,
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if not preset_file:
                return
            
            with open(preset_file, 'r') as f:
                preset_data = json.load(f)
            
            if hasattr(self, 'auto_purchase_var'):
                self.auto_purchase_var.set(preset_data.get('auto_purchase_enabled', False))
            self.auto_purchase_amount = preset_data.get('auto_purchase_amount', 100)
            if hasattr(self, 'amount_var'):
                self.amount_var.set(self.auto_purchase_amount)
            
            self.loops_per_purchase = preset_data.get('loops_per_purchase', 1)
            if hasattr(self, 'loops_var'):
                self.loops_var.set(self.loops_per_purchase)
            
            self.point_coords = preset_data.get('point_coords', {})
            for idx in range(1, 5):
                if hasattr(self, 'point_buttons') and idx in self.point_buttons:
                    self.update_point_button(idx)
            
            self.kp = preset_data.get('kp', 0.1)
            if hasattr(self, 'kp_var'):
                self.kp_var.set(self.kp)
            
            self.kd = preset_data.get('kd', 0.5)
            if hasattr(self, 'kd_var'):
                self.kd_var.set(self.kd)
            
            self.scan_timeout = preset_data.get('scan_timeout', 15.0)
            if hasattr(self, 'timeout_var'):
                self.timeout_var.set(self.scan_timeout)
            
            self.wait_after_loss = preset_data.get('wait_after_loss', 1.0)
            if hasattr(self, 'wait_var'):
                self.wait_var.set(self.wait_after_loss)
            
            self.purchase_delay_after_key = preset_data.get('purchase_delay_after_key', 2.0)
            self.purchase_click_delay = preset_data.get('purchase_click_delay', 1.0)
            self.purchase_after_type_delay = preset_data.get('purchase_after_type_delay', 1.0)
            
            if 'overlay_area' in preset_data and preset_data['overlay_area']:
                self.overlay_area = preset_data['overlay_area']
            
            self.recovery_enabled = preset_data.get('recovery_enabled', True)
            self.silent_mode = preset_data.get('silent_mode', False)
            self.verbose_logging = preset_data.get('verbose_logging', False)
            
            new_theme = preset_data.get('dark_theme', True)
            if new_theme != self.dark_theme:
                self.dark_theme = new_theme
                self.apply_theme()
            
            self.auto_update_enabled = preset_data.get('auto_update_enabled', False)
            if hasattr(self, 'auto_update_btn'):
                self.auto_update_btn.configure(text=f'🔄 Update: {"ON" if self.auto_update_enabled else "OFF"}')
            
            preset_name = os.path.splitext(os.path.basename(preset_file))[0]
            self.status_msg.configure(text=f'✅ Preset "{preset_name}" loaded!', text_color='#FF6B6B')
            print(f'✅ Preset loaded: {preset_file}')
            
            self.auto_save_settings()
            
        except Exception as e:
            self.status_msg.configure(text=f'❌ Error: {e}', text_color='#f85149')
            print(f'❌ Error loading preset: {e}')
    
    def exit_app(self):
        print('Exiting application...')
        self.main_loop_active = False
        
        # Update status card to show stopped state
        if hasattr(self, 'loop_status_card'):
            self.loop_status_card.update_status('OFF', 'default')
        
        self.auto_save_settings()

        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass

        if self.overlay_manager.window is not None:
            try:
                self.overlay_manager.destroy()
            except Exception:
                pass

        try:
            keyboard.unhook_all()
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass

        sys.exit(0)
    
    def setup_system_tray(self):
        try:
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
        if self.tray_icon:
            self.root.withdraw()
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
    
    def show_from_tray(self):
        self.root.deiconify()
        self.root.lift()
        if self.tray_icon:
            self.tray_icon.stop()
    
    def restore_from_tray(self):
        self.show_from_tray()
    
    def apply_theme(self):
        # Light mode only
        ctk.set_appearance_mode("light")
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
        self.auto_purchase_var.trace_add('write', lambda *args: self.auto_save_settings())
        row += 1
        
        # Purchase Amount
        ttk.Label(frame, text='Amount:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.amount_var = tk.IntVar(value=10)
        amount_spinbox = ttk.Spinbox(frame, from_=0, to=1000000, increment=1, textvariable=self.amount_var, width=10)
        amount_spinbox.grid(row=row, column=1, pady=5, sticky='w')
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
        self.loops_var.trace_add('write', lambda *args: self.auto_save_settings())
        self.loops_per_purchase = self.loops_var.get()
        row += 1
        
        # Point buttons for auto-purchase
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
        section.is_expanded = False
        section.content_frame.pack_forget()
        section.toggle_btn.config(text='+')
        self.collapsible_sections['pd_controller'] = section
        frame = section.get_content_frame()
        
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
        section.is_expanded = False
        section.content_frame.pack_forget()
        section.toggle_btn.config(text='+')
        self.collapsible_sections['timing'] = section
        frame = section.get_content_frame()
        
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
        frame.columnconfigure(1, weight=1)
        
        row = 0
        ttk.Label(frame, text='Save:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        save_btn = ttk.Button(frame, text='💾 Save Preset', command=self.save_preset)
        save_btn.grid(row=row, column=1, pady=5, sticky='w')
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Save current settings (excluding webhooks and keybinds) to a preset file")
        row += 1
        
        ttk.Label(frame, text='Load:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        load_btn = ttk.Button(frame, text='📁 Load Preset', command=self.load_preset)
        load_btn.grid(row=row, column=1, pady=5, sticky='w')
        help_btn2 = ttk.Button(frame, text='?', width=3)
        help_btn2.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn2, "Load settings from a preset file")

    def create_hotkeys_section(self, start_row):
        """Create the hotkey bindings collapsible section"""
        section = CollapsibleFrame(self.main_frame, "⌨️ Hotkey Bindings", start_row)
        section.is_expanded = False
        section.content_frame.pack_forget()
        section.toggle_btn.config(text='+')
        self.collapsible_sections['hotkeys'] = section
        frame = section.get_content_frame()
        
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
        
        frame.columnconfigure((0, 1, 2, 3), weight=1)
        
        row = 0
        self.webhook_enabled_var = tk.BooleanVar(value=self.webhook_enabled)
        webhook_check = ttk.Checkbutton(frame, text='Enable Discord Webhook', variable=self.webhook_enabled_var)
        webhook_check.grid(row=row, column=0, columnspan=2, pady=5)
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Send fishing progress updates to Discord")
        self.webhook_enabled_var.trace_add('write', lambda *args: (setattr(self, 'webhook_enabled', self.webhook_enabled_var.get())))
        row += 1
        
        ttk.Label(frame, text='Webhook URL:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.webhook_url_var = tk.StringVar(value=self.webhook_url)
        webhook_entry = ttk.Entry(frame, textvariable=self.webhook_url_var, width=25)
        webhook_entry.grid(row=row, column=1, sticky='ew', pady=5)
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Discord webhook URL from your server settings")
        self.webhook_url_var.trace_add('write', lambda *args: (setattr(self, 'webhook_url', self.webhook_url_var.get())))
        row += 1
        
        ttk.Label(frame, text='Send Every X Fish:').grid(row=row, column=0, sticky='e', pady=5, padx=(0, 10))
        self.webhook_interval_var = tk.IntVar(value=self.webhook_interval)
        interval_spinbox = ttk.Spinbox(frame, from_=1, to=100, textvariable=self.webhook_interval_var, width=10)
        interval_spinbox.grid(row=row, column=1, pady=5, sticky='w')
        help_btn = ttk.Button(frame, text='?', width=3)
        help_btn.grid(row=row, column=2, padx=(10, 0), pady=5)
        ToolTip(help_btn, "Send webhook message every X fish caught (e.g., 10 = message every 10 fish)")
        self.webhook_interval_var.trace_add('write', lambda *args: (setattr(self, 'webhook_interval', self.webhook_interval_var.get())))
        row += 1
        
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
        
        discord_btn = ttk.Button(discord_frame, text='💬 Join our Discord Community!', 
                               command=self.open_discord, style='TButton')
        discord_btn.pack(pady=5, padx=10, fill='x')

    def open_discord(self):
        """Open Discord invite link in browser"""
        import webbrowser
        try:
            webbrowser.open('https://discord.gg/5Gtsgv46ce')
            self.update_status('Opened Discord invite', 'success', '✅')
        except Exception as e:
            self.update_status(f'Error opening Discord: {e}', 'error', '❌')
    
    def apply_theme(self):
        """Apply the current theme to the application"""
        style = ttk.Style()
        
        # Get theme colors
        theme_colors = self.theme_manager.themes[self.current_theme]["colors"]
        
        # Apply theme colors
        self.root.configure(bg=theme_colors["bg"])
        style.theme_use('clam')
        
        # Modern colors based on theme
        style.configure('TFrame', 
                      background=theme_colors["bg"],
                      relief='flat',
                      borderwidth=0)
        
        style.configure('TLabel', 
                      background=theme_colors["bg"], 
                      foreground=theme_colors["fg"],
                      font=('Arial', 10, 'bold'))
        
        # Modern button styling
        style.configure('TButton',
                      background=theme_colors["button_bg"],
                      foreground=theme_colors["fg"],
                      borderwidth=1,
                      focuscolor='none',
                      font=('Arial', 10, 'bold'),
                      relief='flat')
        style.map('TButton',
                 background=[('active', theme_colors["button_hover"]), ('pressed', theme_colors["button_bg"])],
                 bordercolor=[('active', theme_colors["accent"]), ('pressed', theme_colors["accent"])])
        
        style.configure('TCheckbutton',
                      background=theme_colors["bg"],
                      foreground=theme_colors["fg"],
                      focuscolor='none',
                      font=('Arial', 10, 'bold'))
        style.map('TCheckbutton',
                 background=[('active', theme_colors["bg"])])
        
        style.configure('TSpinbox',
                      fieldbackground=theme_colors["button_bg"],
                      background=theme_colors["button_bg"],
                      foreground=theme_colors["fg"],
                      bordercolor=theme_colors["button_hover"],
                      arrowcolor=theme_colors["fg"],
                      font=('Arial', 10, 'bold'))
        
        style.configure('TEntry',
                      fieldbackground=theme_colors["button_bg"],
                      background=theme_colors["button_bg"],
                      foreground=theme_colors["fg"],
                      bordercolor=theme_colors["button_hover"],
                      font=('Arial', 10, 'bold'))
        
        # Scrollbar styling
        style.configure('Vertical.TScrollbar',
                      background=theme_colors["button_bg"],
                      troughcolor=theme_colors["bg"],
                      bordercolor=theme_colors["button_hover"],
                      arrowcolor=theme_colors["fg"],
                      darkcolor=theme_colors["button_bg"],
                      lightcolor=theme_colors["button_hover"])
        style.map('Vertical.TScrollbar',
                 background=[('active', theme_colors["button_hover"]), ('pressed', theme_colors["accent"])])
        
        # Header styling
        style.configure('Title.TLabel',
                      background=theme_colors["bg"],
                      foreground=theme_colors["accent"],
                      font=('Arial', 20, 'bold'))
        
        style.configure('Subtitle.TLabel',
                      background=theme_colors["bg"],
                      foreground=theme_colors["fg"],
                      font=('Arial', 9, 'bold'))
        
        # Section title styling
        style.configure('SectionTitle.TLabel',
                      background=theme_colors["bg"],
                      foreground=theme_colors["accent"],
                      font=('Arial', 12, 'bold'))
        
        # Status labels
        style.configure('StatusOn.TLabel',
                      background=theme_colors["bg"],
                      foreground=theme_colors["success"],
                      font=('Arial', 9, 'bold'))
        
        style.configure('StatusOff.TLabel',
                      background=theme_colors["bg"],
                      foreground=theme_colors["error"],
                      font=('Arial', 9, 'bold'))
        
        style.configure('Counter.TLabel',
                      background=theme_colors["bg"],
                      foreground=theme_colors["fg"],
                      font=('Arial', 12, 'bold'))
        
        # Update canvas background
        if hasattr(self, 'canvas'):
            self.canvas.configure(bg=theme_colors["bg"])
        
        # Update theme button text
        theme_name = self.theme_manager.themes[self.current_theme]["name"]
        self.theme_btn.config(text=f'🎨 {theme_name}')
        
        # Update logo
        self.theme_manager.update_logo()

    def toggle_auto_update(self):
        """Toggle auto-update feature on/off"""
        self.auto_update_enabled = not self.auto_update_enabled
        
        if self.auto_update_enabled:
            self.auto_update_btn.config(text='🔄 Auto Update: ON')
            if self.main_loop_active:
                self.update_status('Auto-update enabled (will check when fishing stops)', 'info', '🔄')
            else:
                self.update_status('Auto-update enabled - checking for updates...', 'info', '🔄')
                threading.Thread(target=self.check_for_updates, daemon=True).start()
        else:
            self.auto_update_btn.config(text='🔄 Auto Update: OFF')
            self.update_status('Auto-update disabled', 'warning', '⏸️')
        
        self.auto_save_settings()

    def auto_save_settings(self):
        """Auto-save current settings to default.json"""
        if not hasattr(self, 'auto_purchase_var'):
            return
            
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
            'auto_update_enabled': getattr(self, 'auto_update_enabled', False),
            'current_theme': getattr(self, 'current_theme', 'default'),
            'hotkeys': getattr(self, 'hotkeys', {}),
            'last_saved': datetime.now().isoformat()
        }
        
        settings_file = "default_settings.json"
        try:
            with open(settings_file, 'w') as f:
                json.dump(preset_data, f, indent=2)
            print(f"Settings auto-saved successfully (excluding webhook settings)")
        except Exception as e:
            print(f'Error auto-saving settings: {e}')

    def load_basic_settings(self):
        """Load basic settings before UI creation"""
        settings_file = "default_settings.json"
        if not os.path.exists(settings_file):
            return
            
        try:
            with open(settings_file, 'r') as f:
                preset_data = json.load(f)
            
            self.auto_purchase_amount = preset_data.get('auto_purchase_amount', 100)
            self.loops_per_purchase = preset_data.get('loops_per_purchase', 1)
            self.point_coords = preset_data.get('point_coords', {})
            self.kp = preset_data.get('kp', 0.1)
            self.kd = preset_data.get('kd', 0.5)
            self.scan_timeout = preset_data.get('scan_timeout', 15.0)
            self.wait_after_loss = preset_data.get('wait_after_loss', 1.0)
            self.smart_check_interval = preset_data.get('smart_check_interval', 15.0)
            self.auto_update_enabled = preset_data.get('auto_update_enabled', False)
            self.current_theme = preset_data.get('current_theme', 'default')
            
            if 'hotkeys' in preset_data:
                self.hotkeys.update(preset_data['hotkeys'])
            
        except Exception as e:
            print(f'Error loading basic settings: {e}')

    def load_ui_settings(self):
        """Load UI-specific settings after widgets are created"""
        settings_file = "default_settings.json"
        if not os.path.exists(settings_file):
            return
            
        try:
            with open(settings_file, 'r') as f:
                preset_data = json.load(f)
            
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

    def update_auto_update_button(self):
        """Update auto-update button text based on current state"""
        try:
            if self.auto_update_enabled:
                self.auto_update_btn.config(text='🔄 Auto Update: ON')
            else:
                self.auto_update_btn.config(text='🔄 Auto Update: OFF')
        except AttributeError:
            pass

    # Placeholder methods for missing functionality
    def capture_mouse_click(self, idx):
        """Capture mouse click for point setting"""
        self.update_status(f'Click anywhere to set Point {idx}...', 'info', '🖱️')
        # Implementation would go here
        pass

    def start_rebind(self, action):
        """Start rebinding hotkey"""
        self.update_status(f'Press a key to rebind {action}...', 'info', '⌨️')
        # Implementation would go here
        pass

    def save_preset(self):
        """Save current settings to preset file"""
        self.update_status('Save preset functionality not implemented yet', 'warning', '💾')
        pass

    def load_preset(self):
        """Load settings from preset file"""
        self.update_status('Load preset functionality not implemented yet', 'warning', '📁')
        pass

    def test_webhook(self):
        """Test webhook functionality"""
        self.update_status('Test webhook functionality not implemented yet', 'warning', '🧪')
        pass

    def register_hotkeys(self):
        """Register hotkeys"""
        # Implementation would go here
        pass

    def setup_system_tray(self):
        """Setup system tray"""
        # Implementation would go here
        pass

    def minimize_to_tray(self):
        """Minimize to system tray"""
        self.update_status('Tray functionality not implemented yet', 'warning', '📌')
        pass

    def startup_update_check(self):
        """Check for updates on startup"""
        # Implementation would go here
        pass

    def start_auto_update_loop(self):
        """Start auto update loop"""
        # Implementation would go here
        pass

    def check_for_updates(self):
        """Check for updates"""
        # Implementation would go here
        pass

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

def main():
    root = tk.Tk()
    app = HotkeyGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()