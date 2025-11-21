import tkinter as tk
from tkinter import ttk
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

class HotkeyGUI:
    def __init__(self, root):
        self.root = root
        self.root.title('GPO Autofish - by asphalt_cake | Public Release by Ariel')
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
        self.overlay_area = {'x': int(100 * self.dpi_scale), 'y': int(100 * self.dpi_scale), 'width': int(base_width * self.dpi_scale), 'height': int(base_height * self.dpi_scale)}
        self.hotkeys = {'toggle_loop': 'f1', 'toggle_overlay': 'f2', 'exit': 'f3'}
        self.purchase_counter = 0
        self.purchase_delay_after_key = 2.0
        self.purchase_click_delay = 1.0
        self.purchase_after_type_delay = 1.0
        self.create_widgets()
        self.register_hotkeys()
        self.root.update_idletasks()
        self.root.minsize(self.root.winfo_width(), self.root.winfo_height())

    def get_dpi_scale(self):
        """Get the DPI scaling factor for the current display"""  # inserted
        try:
            dpi = self.root.winfo_fpixels('1i')
            scale = dpi / 96.0
            return scale
        except:
            return 1.0

    def create_widgets(self):
        self.root.configure(bg='#191919')
        main_frame = ttk.Frame(self.root, padding='20')
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=0)
        main_frame.columnconfigure(2, weight=0)
        title = ttk.Label(main_frame, text='🎣 GPO Autofish', font=('Arial', 16, 'bold'))
        title.grid(row=0, column=0, columnspan=3, pady=(0, 5))
        credits = ttk.Label(main_frame, text='by asphalt_cake | Public Release by Ariel', font=('Arial', 8), foreground='#888888')
        credits.grid(row=1, column=0, columnspan=3, pady=(0, 10))
        self.loop_status = ttk.Label(main_frame, text='Main Loop: OFF', foreground='#55aaff')
        self.loop_status.grid(row=2, column=0, columnspan=3, pady=5)
        self.overlay_status = ttk.Label(main_frame, text='Overlay: OFF', foreground='#55aaff')
        self.overlay_status.grid(row=3, column=0, columnspan=3, pady=5)
        ttk.Separator(main_frame, orient='horizontal').grid(row=4, column=0, columnspan=3, sticky='ew', pady=20)
        ttk.Label(main_frame, text='Auto Purchase Settings:', font=('Arial', 12, 'bold')).grid(row=5, column=0, columnspan=3, pady=(0, 10))
        ttk.Label(main_frame, text='Active:').grid(row=6, column=0, sticky=tk.W, pady=5)
        ttk.Label(main_frame, text='Active:').grid(row=6, column=0, sticky=tk.W, pady=5)
        self.auto_purchase_var = tk.BooleanVar(value=True)
        auto_check = ttk.Checkbutton(main_frame, variable=self.auto_purchase_var, text='Enabled')
        auto_check.grid(row=6, column=1, columnspan=2, pady=5, sticky=tk.W)
        ttk.Label(main_frame, text='Amount:').grid(row=7, column=0, sticky=tk.W, pady=5)
        self.amount_var = tk.IntVar(value=10)
        amount_spinbox = ttk.Spinbox(main_frame, from_=0, to=1000000, increment=1, textvariable=self.amount_var, width=10)
        amount_spinbox.grid(row=7, column=1, columnspan=2, pady=5, sticky=tk.W)
        self.amount_var.trace_add('write', lambda *args: setattr(self, 'auto_purchase_amount', self.amount_var.get()))
        self.auto_purchase_amount = self.amount_var.get()
        ttk.Label(main_frame, text='Loops per Purchase:').grid(row=8, column=0, sticky=tk.W, pady=5)
        self.loops_var = tk.IntVar(value=10)
        loops_spinbox = ttk.Spinbox(main_frame, from_=1, to=1000000, increment=1, textvariable=self.loops_var, width=10)
        loops_spinbox.grid(row=8, column=1, columnspan=2, pady=5, sticky=tk.W)
        self.loops_var.trace_add('write', lambda *args: setattr(self, 'loops_per_purchase', self.loops_var.get()))
        self.loops_per_purchase = self.loops_var.get()
        ttk.Label(main_frame, text='Point 1:').grid(row=9, column=0, sticky=tk.W, pady=5)
        self.point_buttons = {}
        self.point_coords = {1: None, 2: None, 3: None, 4: None}
        self.point_buttons[1] = ttk.Button(main_frame, text='Point 1', command=lambda: self.capture_mouse_click(1))
        self.point_buttons[1].grid(row=9, column=1, columnspan=2, pady=5, sticky=tk.W)
        ttk.Label(main_frame, text='Point 2:').grid(row=10, column=0, sticky=tk.W, pady=5)
        self.point_buttons[2] = ttk.Button(main_frame, text='Point 2', command=lambda: self.capture_mouse_click(2))
        self.point_buttons[2].grid(row=10, column=1, columnspan=2, pady=5, sticky=tk.W)
        ttk.Label(main_frame, text='Point 3:').grid(row=11, column=0, sticky=tk.W, pady=5)
        self.point_buttons[3] = ttk.Button(main_frame, text='Point 3', command=lambda: self.capture_mouse_click(3))
        self.point_buttons[3].grid(row=11, column=1, columnspan=2, pady=5, sticky=tk.W)
        ttk.Label(main_frame, text='Point 4:').grid(row=12, column=0, sticky=tk.W, pady=5)
        self.point_buttons[4] = ttk.Button(main_frame, text='Point 4', command=lambda: self.capture_mouse_click(4))
        self.point_buttons[4].grid(row=12, column=1, columnspan=2, pady=5, sticky=tk.W)
        ttk.Separator(main_frame, orient='horizontal').grid(row=13, column=0, columnspan=3, sticky='ew', pady=20)
        ttk.Label(main_frame, text='PD Controller:', font=('Arial', 12, 'bold')).grid(row=14, column=0, columnspan=3, pady=(0, 10))
        ttk.Label(main_frame, text='Kp (Proportional):').grid(row=15, column=0, sticky=tk.W, pady=5)
        self.kp_var = tk.DoubleVar(value=self.kp)
        kp_spinbox = ttk.Spinbox(main_frame, from_=0.0, to=2.0, increment=0.1, textvariable=self.kp_var, width=10)
        kp_spinbox.grid(row=15, column=1, columnspan=2, pady=5, sticky=tk.W)
        self.kp_var.trace_add('write', lambda *args: setattr(self, 'kp', self.kp_var.get()))
        ttk.Label(main_frame, text='Kd (Derivative):').grid(row=16, column=0, sticky=tk.W, pady=5)
        self.kd_var = tk.DoubleVar(value=self.kd)
        kd_spinbox = ttk.Spinbox(main_frame, from_=0.0, to=1.0, increment=0.01, textvariable=self.kd_var, width=10)
        kd_spinbox.grid(row=16, column=1, columnspan=2, pady=5, sticky=tk.W)
        self.kd_var.trace_add('write', lambda *args: setattr(self, 'kd', self.kd_var.get()))
        ttk.Separator(main_frame, orient='horizontal').grid(row=17, column=0, columnspan=3, sticky='ew', pady=20)
        ttk.Label(main_frame, text='Timing Settings:', font=('Arial', 12, 'bold')).grid(row=18, column=0, columnspan=3, pady=(0, 10))
        ttk.Label(main_frame, text='Scan Timeout (s):').grid(row=19, column=0, sticky=tk.W, pady=5)
        self.timeout_var = tk.DoubleVar(value=self.scan_timeout)
        timeout_spinbox = ttk.Spinbox(main_frame, from_=1.0, to=60.0, increment=1.0, textvariable=self.timeout_var, width=10)
        timeout_spinbox.grid(row=19, column=1, columnspan=2, pady=5, sticky=tk.W)
        self.timeout_var.trace_add('write', lambda *args: setattr(self, 'scan_timeout', self.timeout_var.get()))
        ttk.Label(main_frame, text='Wait After Loss (s):').grid(row=20, column=0, sticky=tk.W, pady=5)
        self.wait_var = tk.DoubleVar(value=self.wait_after_loss)
        wait_spinbox = ttk.Spinbox(main_frame, from_=0.0, to=10.0, increment=0.1, textvariable=self.wait_var, width=10)
        wait_spinbox.grid(row=20, column=1, columnspan=2, pady=5, sticky=tk.W)
        self.wait_var.trace_add('write', lambda *args: setattr(self, 'wait_after_loss', self.wait_var.get()))
        ttk.Separator(main_frame, orient='horizontal').grid(row=21, column=0, columnspan=3, sticky='ew', pady=20)
        ttk.Label(main_frame, text='Hotkey Bindings:', font=('Arial', 12, 'bold')).grid(row=22, column=0, columnspan=3, pady=(0, 10))
        ttk.Label(main_frame, text='Toggle Main Loop:').grid(row=23, column=0, sticky=tk.W, pady=5)
        self.loop_key_label = ttk.Label(main_frame, text=self.hotkeys['toggle_loop'].upper(), relief=tk.RIDGE, padding=5, width=10)
        self.loop_key_label.grid(row=23, column=1, pady=5)
        self.loop_rebind_btn = ttk.Button(main_frame, text='Rebind', command=lambda: self.start_rebind('toggle_loop'))
        self.loop_rebind_btn.grid(row=23, column=2, padx=5, pady=5)
        ttk.Label(main_frame, text='Toggle Overlay:').grid(row=24, column=0, sticky=tk.W, pady=5)
        self.overlay_key_label = ttk.Label(main_frame, text=self.hotkeys['toggle_overlay'].upper(), relief=tk.RIDGE, padding=5, width=10)
        self.overlay_key_label.grid(row=24, column=1, pady=5)
        self.overlay_rebind_btn = ttk.Button(main_frame, text='Rebind', command=lambda: self.start_rebind('toggle_overlay'))
        self.overlay_rebind_btn.grid(row=24, column=2, padx=5, pady=5)
        ttk.Label(main_frame, text='Exit:').grid(row=25, column=0, sticky=tk.W, pady=5)
        self.exit_key_label = ttk.Label(main_frame, text=self.hotkeys['exit'].upper(), relief=tk.RIDGE, padding=5, width=10)
        self.exit_key_label.grid(row=25, column=1, pady=5)
        self.exit_rebind_btn = ttk.Button(main_frame, text='Rebind', command=lambda: self.start_rebind('exit'))
        self.exit_rebind_btn.grid(row=25, column=2, padx=5, pady=5)
        self.status_msg = ttk.Label(main_frame, text='', foreground='blue')
        self.status_msg.grid(row=26, column=0, columnspan=3, pady=(20, 0))

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

    def perform_auto_purchase_sequence(self):
        """Perform the auto-purchase sequence using saved points and amount.

Sequence (per user spec):
- press 'e', wait
- click point1, wait
- click point2, wait
- type amount, wait
- click point3, wait
- click point4, wait
"""
        print('=== AUTO-PURCHASE SEQUENCE START ===')
        pts = self.point_coords
        if not pts or not pts.get(1) or not pts.get(2) or not pts.get(3) or not pts.get(4):
            print('Auto purchase aborted: points not fully set (need points 1-4).')
            return
        
        amount = str(self.auto_purchase_amount)
        
        # Press 'e' key
        print('Pressing E key...')
        keyboard.press_and_release('e')
        threading.Event().wait(self.purchase_delay_after_key)
        
        # Click point 1
        print(f'Clicking Point 1: {pts[1]}')
        self._click_at(pts[1])
        threading.Event().wait(self.purchase_click_delay)
        
        # Click point 2
        print(f'Clicking Point 2: {pts[2]}')
        self._click_at(pts[2])
        threading.Event().wait(self.purchase_click_delay)
        
        # Type amount
        print(f'Typing amount: {amount}')
        keyboard.write(amount)
        threading.Event().wait(self.purchase_after_type_delay)
        
        # Click point 3
        print(f'Clicking Point 3: {pts[3]}')
        self._click_at(pts[3])
        threading.Event().wait(self.purchase_click_delay)
        
        # Click point 4
        print(f'Clicking Point 4: {pts[4]}')
        self._click_at(pts[4])
        threading.Event().wait(self.purchase_click_delay)
        
        print('=== AUTO-PURCHASE SEQUENCE COMPLETE ===')
        print()

    def start_rebind(self, action):
        """Start recording a new hotkey"""  # inserted
        self.recording_hotkey = action
        self.status_msg.config(text=f'Press a key to rebind \'{action}\'...', foreground='blue')
        self.loop_rebind_btn.config(state='disabled')
        self.overlay_rebind_btn.config(state='disabled')
        self.exit_rebind_btn.config(state='disabled')
        listener = pynput_keyboard.Listener(on_press=self.on_key_press)
        listener.start()

    def on_key_press(self, key):
        """Handle key press during rebinding"""  # inserted
        if self.recording_hotkey is None:
            pass  # postinserted
        return False

    def register_hotkeys(self):
        """Register all hotkeys"""  # inserted
        try:
            keyboard.unhook_all()
            keyboard.add_hotkey(self.hotkeys['toggle_loop'], self.toggle_main_loop)
            keyboard.add_hotkey(self.hotkeys['toggle_overlay'], self.toggle_overlay)
            keyboard.add_hotkey(self.hotkeys['exit'], self.exit_app)
        except Exception as e:
            print(f'Error registering hotkeys: {e}')

    def toggle_main_loop(self):
        """Toggle the main loop on/off"""
        new_state = not self.main_loop_active
        
        if new_state:
            # We're turning the loop ON. If Auto Purchase is active, ensure points are set.
            if getattr(self, 'auto_purchase_var', None) and self.auto_purchase_var.get():
                pts = getattr(self, 'point_coords', {})
                missing = [i for i in [1, 2, 3, 4] if not pts.get(i)]
                if missing:
                    messagebox.showwarning('Auto Purchase: Points missing', f'Please set Point(s) {missing} before starting Auto Purchase.')
                    return
        
        # Apply new state
        self.main_loop_active = new_state
        
        if self.main_loop_active:
            self.loop_status.config(text='Main Loop: ON', foreground='#00ff00')
            self.main_loop_thread = threading.Thread(target=self.main_loop, daemon=True)
            self.main_loop_thread.start()
        else:
            self.loop_status.config(text='Main Loop: OFF', foreground='#55aaff')
            # Release mouse button if it's being held when stopping
            if self.is_clicking:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                self.is_clicking = False
            # Reset PD controller state
            self.previous_error = 0

    def check_and_purchase(self):
        """Check if we need to auto-purchase and run sequence if needed"""  # inserted
        if getattr(self, 'auto_purchase_var', None) and self.auto_purchase_var.get():
            self.purchase_counter += 1
            loops_needed = int(getattr(self, 'loops_per_purchase', 1)) if getattr(self, 'loops_per_purchase', None) is not None else 1
            print(f'Purchase counter: {self.purchase_counter}/{loops_needed}')
            if self.purchase_counter >= max(1, loops_needed):
                print('Triggering auto-purchase sequence...')
                try:
                    self.perform_auto_purchase_sequence()
                    self.purchase_counter = 0
                except Exception as e:
                    print(f'Error during auto-purchase: {e}')

    def cast_line(self):
        """Perform the casting action: hold click for 1 second then release"""  # inserted
        print('Casting line...')
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        threading.Event().wait(1.0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self.is_clicking = False
        print('Line cast')

    def main_loop(self):
        """Main loop that runs when activated"""
        print('Main loop started')
        target_color = (85, 170, 255)
        dark_color = (25, 25, 25)
        white_color = (255, 255, 255)
        import time
        
        with mss.mss() as sct:
            if getattr(self, 'auto_purchase_var', None) and self.auto_purchase_var.get():
                print('Running initial auto-purchase...')
                self.perform_auto_purchase_sequence()
            self.cast_line()
            last_detection_time = time.time()
            was_detecting = False
            print('Entering main detection loop...')
            
            while self.main_loop_active:
                x = self.overlay_area['x']
                y = self.overlay_area['y']
                width = self.overlay_area['width']
                height = self.overlay_area['height']
                monitor = {'left': x, 'top': y, 'width': width, 'height': height}
                screenshot = sct.grab(monitor)
                img = np.array(screenshot)
                point1_x = None
                point1_y = None
                found_first = False
                for row_idx in range(height):
                    for col_idx in range(width):
                        b, g, r = img[row_idx, col_idx, 0:3]
                        if r == target_color[0] and g == target_color[1] and b == target_color[2]:
                            point1_x = x + col_idx
                            point1_y = y + row_idx
                            found_first = True
                            break
                    if found_first:
                        break
                if not found_first:
                    current_time = time.time()
                    if was_detecting:
                        print('Lost detection, waiting...')
                        threading.Event().wait(self.wait_after_loss)
                        was_detecting = False
                        self.check_and_purchase()
                        self.cast_line()
                        last_detection_time = time.time()
                    threading.Event().wait(0.1)
                    continue
                point2_x = None
                row_idx = point1_y - y
                for col_idx in range(width - 1, -1, -1):
                    b, g, r = img[row_idx, col_idx, 0:3]
                    if r == target_color[0] and g == target_color[1] and b == target_color[2]:
                        point2_x = x + col_idx
                        break
                if point2_x is None:
                    threading.Event().wait(0.1)
                    continue
                temp_area_x = point1_x
                temp_area_width = point2_x - point1_x + 1
                temp_monitor = {'left': temp_area_x, 'top': y, 'width': temp_area_width, 'height': height}
                temp_screenshot = sct.grab(temp_monitor)
                temp_img = np.array(temp_screenshot)
                dark_color = (25, 25, 25)
                top_y = None
                for row_idx in range(height):
                    found_dark = False
                    for col_idx in range(temp_area_width):
                        b, g, r = temp_img[row_idx, col_idx, 0:3]
                        if r == dark_color[0] and g == dark_color[1] and b == dark_color[2]:
                            top_y = y + row_idx
                            found_dark = True
                            break
                    if found_dark:
                        break
                bottom_y = None
                for row_idx in range(height - 1, -1, -1):
                    found_dark = False
                    for col_idx in range(temp_area_width):
                        b, g, r = temp_img[row_idx, col_idx, 0:3]
                        if r == dark_color[0] and g == dark_color[1] and b == dark_color[2]:
                            bottom_y = y + row_idx
                            found_dark = True
                            break
                    if found_dark:
                        break
                if top_y is None or bottom_y is None:
                    threading.Event().wait(0.1)
                    continue
                self.real_area = {'x': temp_area_x, 'y': top_y, 'width': temp_area_width, 'height': bottom_y - top_y + 1}
                real_x = self.real_area['x']
                real_y = self.real_area['y']
                real_width = self.real_area['width']
                real_height = self.real_area['height']
                real_monitor = {'left': real_x, 'top': real_y, 'width': real_width, 'height': real_height}
                real_screenshot = sct.grab(real_monitor)
                real_img = np.array(real_screenshot)
                white_color = (255, 255, 255)
                white_top_y = None
                white_bottom_y = None
                for row_idx in range(real_height):
                    for col_idx in range(real_width):
                        b, g, r = real_img[row_idx, col_idx, 0:3]
                        if r == white_color[0] and g == white_color[1] and b == white_color[2]:
                            white_top_y = real_y + row_idx
                            break
                    if white_top_y is not None:
                        break
                for row_idx in range(real_height - 1, -1, -1):
                    for col_idx in range(real_width):
                        b, g, r = real_img[row_idx, col_idx, 0:3]
                        if r == white_color[0] and g == white_color[1] and b == white_color[2]:
                            white_bottom_y = real_y + row_idx
                            break
                    if white_bottom_y is not None:
                        break
                if white_top_y is not None and white_bottom_y is not None:
                    white_height = white_bottom_y - white_top_y + 1
                    max_gap = white_height * 2
                dark_sections = []
                current_section_start = None
                gap_counter = 0
                for row_idx in range(real_height):
                    has_dark = False
                    for col_idx in range(real_width):
                        b, g, r = real_img[row_idx, col_idx, 0:3]
                        if r == dark_color[0] and g == dark_color[1] and b == dark_color[2]:
                            has_dark = True
                            break
                    if has_dark:
                        gap_counter = 0
                        if current_section_start is None:
                            current_section_start = real_y + row_idx
                    else:
                        if current_section_start is not None:
                            gap_counter += 1
                            if gap_counter > max_gap:
                                section_end = real_y + row_idx - gap_counter
                                dark_sections.append({'start': current_section_start, 'end': section_end, 'middle': (current_section_start + section_end) // 2})
                                current_section_start = None
                                gap_counter = 0
                if current_section_start is not None:
                    section_end = real_y + real_height - 1 - gap_counter
                    dark_sections.append({'start': current_section_start, 'end': section_end, 'middle': (current_section_start + section_end) // 2})
                if dark_sections and white_top_y is not None:
                    was_detecting = True
                    last_detection_time = time.time()
                    for section in dark_sections:
                        section['size'] = section['end'] - section['start'] + 1
                    largest_section = max(dark_sections, key=lambda s: s['size'])
                    print(f'y:{white_top_y}')
                    print(f"y:{largest_section['middle']}")
                    raw_error = largest_section['middle'] - white_top_y
                    normalized_error = raw_error / real_height if real_height > 0 else raw_error
                    derivative = normalized_error - self.previous_error
                    self.previous_error = normalized_error
                    pd_output = self.kp * normalized_error + self.kd * derivative
                    print(f'Error: {raw_error}px ({normalized_error:.3f} normalized), PD Output: {pd_output:.2f}')
                    
                    # Decide whether to hold or release based on PD output
                    # Positive error/output = middle is below, need to go up = hold click
                    # Negative error/output = middle is above, need to go down = release click
                    if pd_output > 0:
                        # Need to accelerate up - hold left click
                        if not self.is_clicking:
                            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                            self.is_clicking = True
                    else:
                        # Need to accelerate down - release left click
                        if self.is_clicking:
                            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                            self.is_clicking = False
                    
                    print()
                threading.Event().wait(0.1)
        print('Main loop stopped')


    def toggle_overlay(self):
        """Toggle the overlay on/off"""
        self.overlay_active = not self.overlay_active
        if self.overlay_active:
            self.overlay_status.config(text='Overlay: ON', foreground='#00ff00')
            self.create_overlay()
            print(f'Overlay activated at: {self.overlay_area}')
        else:
            self.overlay_status.config(text='Overlay: OFF', foreground='#55aaff')
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
    root.protocol('WM_DELETE_WINDOW', app.exit_app)
    root.mainloop()
if __name__ == '__main__':
    main()