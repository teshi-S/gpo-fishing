#!/usr/bin/env python3
"""
GPO Autofish - Installation
A user-friendly graphical installer for GPO Autofish dependencies
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import threading
import re
import os
from pathlib import Path

class CollapsibleFrame:
    """Collapsible frame widget matching the main app design"""
    def __init__(self, parent, title, row, columnspan=1, default_open=False):
        self.parent = parent
        self.title = title
        self.row = row
        self.columnspan = columnspan
        self.is_expanded = default_open
        
        # Main container
        self.container = tk.Frame(parent, bg="#ffffff")
        self.container.grid(row=row, column=0, columnspan=columnspan, sticky='ew', pady=(8, 0), padx=10)
        
        # Header frame
        self.header_frame = tk.Frame(self.container, bg="#ffffff")
        self.header_frame.pack(fill='x', pady=(0, 2))
        self.header_frame.columnconfigure(0, weight=1)
        
        # Title label
        self.title_label = tk.Label(self.header_frame, text=title, 
                                   font=('Segoe UI', 11, 'bold'),
                                   bg="#ffffff", fg="#dc143c")
        self.title_label.grid(row=0, column=0, sticky='w', padx=(10, 0), pady=5)
        
        # Toggle button
        toggle_text = '−' if default_open else '+'
        self.toggle_btn = tk.Button(self.header_frame, text=toggle_text, width=3, 
                                   command=self.toggle, bg="#f0fff0", fg="#2d1b1b",
                                   font=('Segoe UI', 10, 'bold'), relief='flat')
        self.toggle_btn.grid(row=0, column=1, sticky='e', padx=(0, 10), pady=2)
        
        # Separator line
        separator = tk.Frame(self.container, height=1, bg="#e0e0e0")
        separator.pack(fill='x', pady=(0, 8))
        
        # Content frame
        self.content_frame = tk.Frame(self.container, bg="#ffffff")
        if default_open:
            self.content_frame.pack(fill='both', expand=True, padx=15, pady=(0, 10))
        
        # Configure grid weights
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

class InstallerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("GPO Autofish - Installation")
        self.root.geometry("500x500")
        self.root.resizable(True, True)
        self.root.configure(bg="#ffffff")
        
        # Variables
        self.python_version = ""
        self.is_python_314 = False
        self.installation_complete = False
        self.installation_running = False
        
        # Create widgets and check Python
        self.create_widgets()
        self.check_python()
        
    def create_scrollable_frame(self):
        """Create a scrollable frame matching the main app design"""
        # Main container
        self.main_container = tk.Frame(self.root, bg="#ffffff")
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Canvas and scrollbar
        self.canvas = tk.Canvas(self.main_container, highlightthickness=0, bg="#ffffff")
        self.scrollbar = ttk.Scrollbar(self.main_container, orient="vertical", command=self.canvas.yview)
        
        # Scrollable frame
        self.main_frame = tk.Frame(self.canvas, bg="#ffffff")
        
        # Configure scrolling
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack scrollbar and canvas
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Create window in canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")
        
        # Bind events
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
        
    def create_widgets(self):
        """Create and layout all GUI widgets matching the main app design"""
        # Create scrollable main container
        self.create_scrollable_frame()
        self.main_frame.columnconfigure(0, weight=1)
        
        current_row = 0
        
        # Header section matching main app
        header_frame = tk.Frame(self.main_frame, bg="#ffffff")
        header_frame.grid(row=current_row, column=0, sticky='ew', pady=(0, 20))
        header_frame.columnconfigure(0, weight=1)
        
        # App title with main app styling
        title = tk.Label(header_frame, text='GPO Autofish', 
                        font=('Segoe UI', 24, 'bold'),
                        bg="#ffffff", fg="#dc143c")
        title.grid(row=0, column=0, pady=(0, 5))
        
        # Subtitle
        subtitle = tk.Label(header_frame, text='Installation', 
                           font=('Segoe UI', 16),
                           bg="#ffffff", fg="#2d1b1b")
        subtitle.grid(row=1, column=0, pady=(0, 15))
        
        current_row += 1
        
        # System Status Section (non-collapsible)
        status_frame = tk.LabelFrame(self.main_frame, text="🔧 System Status", 
                                    bg="#ffffff", fg="#dc143c",
                                    font=('Segoe UI', 11, 'bold'), padx=20, pady=15)
        status_frame.grid(row=current_row, column=0, sticky='ew', pady=(0, 20), padx=10)
        status_frame.columnconfigure(1, weight=1)
        
        # Python version status
        tk.Label(status_frame, text="Python Version:", 
                bg="#ffffff", fg="#2d1b1b", font=('Segoe UI', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
        self.python_status_label = tk.Label(status_frame, text="Checking...", 
                                           bg="#ffffff", fg="#2d1b1b")
        self.python_status_label.grid(row=0, column=1, sticky='w', padx=(10, 0), pady=5)
        
        # Python 3.14 warning
        self.python_314_warning = tk.Label(status_frame, text="", 
                                          bg="#ffffff", fg="#ff9800", font=('Segoe UI', 9))
        self.python_314_warning.grid(row=1, column=0, columnspan=2, sticky='w', pady=(5, 0))
        
        current_row += 1
        
        # Progress bar (above logs)
        progress_frame = tk.Frame(self.main_frame, bg="#ffffff")
        progress_frame.grid(row=current_row, column=0, sticky='ew', pady=(0, 10), padx=10)
        progress_frame.columnconfigure(0, weight=1)
        
        # Progress bar
        self.progress = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress.grid(row=0, column=0, sticky='ew', pady=(0, 5))
        
        # Progress label
        self.progress_label = tk.Label(progress_frame, text="Ready to install", 
                                      bg="#ffffff", fg="#2d1b1b", font=('Segoe UI', 10))
        self.progress_label.grid(row=1, column=0)
        
        current_row += 1
        
        # Installation Log (collapsible, closed by default)
        self.log_section = CollapsibleFrame(self.main_frame, "📋 Installation Log", current_row, default_open=False)
        log_content = self.log_section.get_content_frame()
        
        # Log text area with white background
        log_frame = tk.Frame(log_content, bg="#ffffff")
        log_frame.pack(fill='both', expand=True)
        
        self.log_text = tk.Text(log_frame, height=12, width=60, wrap=tk.WORD,
                               bg="#ffffff", fg="#2d1b1b", font=('Consolas', 9),
                               relief='solid', bd=1)
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scrollbar.pack(side="right", fill="y")
        
        current_row += 1
        
        # Button frame - centered
        button_frame = tk.Frame(self.main_frame, bg="#ffffff")
        button_frame.grid(row=current_row, column=0, pady=(30, 20), padx=10)
        
        # Centered install button with better design
        self.install_button = tk.Button(button_frame, text="🚀 Start Installation", 
                                       command=self.start_installation,
                                       bg="#dc143c", fg="#ffffff", 
                                       font=('Segoe UI', 14, 'bold'),
                                       relief='flat', padx=40, pady=12,
                                       cursor='hand2', borderwidth=0)
        self.install_button.pack()
        
        # Add hover effects
        def on_enter(e):
            if self.install_button['state'] != 'disabled':
                self.install_button.config(bg="#b22222")
        
        def on_leave(e):
            if self.install_button['state'] != 'disabled':
                self.install_button.config(bg="#dc143c")
        
        self.install_button.bind("<Enter>", on_enter)
        self.install_button.bind("<Leave>", on_leave)
        
        # Status message
        self.status_msg = tk.Label(self.main_frame, text='Ready to install dependencies!', 
                                  font=('Segoe UI', 9), bg="#ffffff", fg="#228b22")
        self.status_msg.grid(row=current_row+1, column=0, pady=(10, 0))
        
    def log_message(self, message, level="INFO"):
        """Add a message to the log with timestamp and level"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        # Insert message with timestamp
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        
        # Auto-scroll to bottom
        self.log_text.see(tk.END)
        
        # Update GUI
        self.root.update_idletasks()
        
    def check_python(self):
        """Check Python installation and version"""
        try:
            result = subprocess.run([sys.executable, "--version"], 
                                  capture_output=True, text=True, check=True)
            version_output = result.stdout.strip()
            
            # Extract version number
            version_match = re.search(r'Python (\d+\.\d+\.\d+)', version_output)
            if version_match:
                self.python_version = version_match.group(1)
                self.python_status_label.config(text=f"✓ {version_output}", fg="#228b22")
                
                # Check for Python 3.14
                if self.python_version.startswith("3.14"):
                    self.is_python_314 = True
                    self.python_314_warning.config(
                        text="⚠️ Python 3.14 detected - Will use nightly builds for compatibility"
                    )
                    
                self.log_message(f"Python {self.python_version} detected")
                if self.is_python_314:
                    self.log_message("Python 3.14 compatibility mode enabled")
                    
            else:
                raise ValueError("Could not parse Python version")
                
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
            self.python_status_label.config(text="✗ Python not found or invalid", fg="#b22222")
            self.log_message(f"Python check failed: {e}")
            self.install_button.config(state='disabled')
            
    def update_progress(self, text):
        """Update progress label and status"""
        self.progress_label.config(text=text)
        self.status_msg.config(text=text, fg="#2d1b1b")
        self.root.update_idletasks()
        
    def run_pip_install(self, packages, extra_args=None, description=""):
        """Run pip install with given packages"""
        if extra_args is None:
            extra_args = []
            
        cmd = [sys.executable, "-m", "pip", "install"] + extra_args + packages
        
        self.log_message(f"Installing {description}: {' '.join(packages)}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                universal_newlines=True
            )
            
            # Read output in real-time
            for line in process.stdout:
                line = line.strip()
                if line:
                    self.log_message(f"  {line}")
                    
            process.wait()
            
            if process.returncode == 0:
                self.log_message(f"✓ {description} installed successfully")
                return True
            else:
                self.log_message(f"✗ {description} installation failed (exit code: {process.returncode})")
                return False
                
        except Exception as e:
            self.log_message(f"✗ Error installing {description}: {e}")
            return False
            
    def install_dependencies(self):
        """Main installation process"""
        try:
            # Step 1: Upgrade pip
            self.update_progress("🔧 Upgrading pip...")
            self.log_message("=== Step 1: Upgrading pip ===")
            self.run_pip_install(["--upgrade", "pip"], description="pip upgrade")
            
            # Step 2: Install core packages (same as install.bat)
            self.update_progress("📦 Installing core packages...")
            self.log_message("=== Step 2: Installing core packages ===")
            self.log_message("Installing essential dependencies directly...")
            
            # Install core packages one by one (exactly like install.bat)
            core_packages = [
                "keyboard==0.13.5",
                "pynput==1.8.1", 
                "mss==10.1.0",
                "numpy",
                "pillow",
                "requests",
                "pywin32",
                "pystray"
            ]
            
            for package in core_packages:
                self.run_pip_install([package], ["--no-warn-script-location"], package)
                
            # Step 3: Handle Python 3.14 compatibility (exactly like install.bat)
            self.update_progress("👁️ Installing OCR packages...")
            self.log_message("=== Step 3: Installing OCR packages ===")
            
            # Handle Python 3.14 compatibility issues (same as install.bat)
            if self.is_python_314:
                self.log_message("Python 3.14 detected - installing compatible packages...")
                self.log_message("Installing scikit-image nightly build for Python 3.14 compatibility...")
                nightly_index = "https://pypi.anaconda.org/scientific-python-nightly-wheels/simple"
                success = self.run_pip_install(
                    ["scikit-image"],
                    ["-i", nightly_index, "--no-warn-script-location"],
                    "scikit-image (nightly build)"
                )
                
                if not success:
                    self.log_message("Warning: Nightly scikit-image installation failed, trying standard method...")
                else:
                    self.log_message("✓ scikit-image nightly build installed")
                    
            # Install EasyOCR (exactly like install.bat logic)
            self.log_message("Installing EasyOCR (primary text recognition)...")
            easyocr_success = self.run_pip_install(["easyocr"], description="EasyOCR")
            
            if not easyocr_success:
                self.log_message("EasyOCR installation failed, trying alternative methods...")
                
                # For Python 3.14, try nightly builds first (same as install.bat)
                if self.is_python_314:
                    self.log_message("Method 1: Installing EasyOCR dependencies with nightly builds...")
                    self.run_pip_install(["torch", "torchvision"], ["--no-warn-script-location"], "PyTorch")
                    nightly_index = "https://pypi.anaconda.org/scientific-python-nightly-wheels/simple"
                    self.run_pip_install(["scikit-image"], ["-i", nightly_index, "--no-warn-script-location"], "scikit-image (nightly)")
                    self.run_pip_install(["opencv-python", "pillow", "numpy"], ["--no-warn-script-location"], "image processing")
                    easyocr_success = self.run_pip_install(["easyocr"], ["--no-warn-script-location"], "EasyOCR (with nightly builds)")
                    
                    if easyocr_success:
                        self.log_message("✓ EasyOCR installed with nightly builds")
                    else:
                        self.log_message("Nightly build method failed, trying standard methods...")
                
                if not easyocr_success:
                    # Method 2: Installing with --user flag (same as install.bat)
                    self.log_message("Method 2: Installing with --user flag...")
                    easyocr_success = self.run_pip_install(["easyocr"], ["--user"], "EasyOCR (user)")
                    
                if not easyocr_success:
                    # Method 3: Installing with --force-reinstall (same as install.bat)
                    self.log_message("Method 3: Installing with --force-reinstall...")
                    easyocr_success = self.run_pip_install(["easyocr"], ["--force-reinstall"], "EasyOCR (force-reinstall)")
                    
                if not easyocr_success:
                    # Method 4: Installing dependencies separately (same as install.bat)
                    self.log_message("Method 4: Installing dependencies separately...")
                    self.run_pip_install(["torch", "torchvision"], description="PyTorch")
                    self.run_pip_install(["opencv-python"], description="OpenCV")
                    self.run_pip_install(["pillow"], description="Pillow")
                    self.run_pip_install(["numpy"], description="NumPy")
                    easyocr_success = self.run_pip_install(["easyocr"], description="EasyOCR (final attempt)")
                    
                    if not easyocr_success:
                        self.log_message("WARNING: EasyOCR installation failed completely")
                        if self.is_python_314:
                            self.log_message("This is likely due to Python 3.14 compatibility issues.")
                            self.log_message("Manual installation options:")
                            self.log_message("1. Install nightly builds manually:")
                            self.log_message("   pip install -i https://pypi.anaconda.org/scientific-python-nightly-wheels/simple scikit-image")
                            self.log_message("   pip install easyocr")
                            self.log_message("2. Consider using Python 3.13 for better compatibility")
                            self.log_message("3. Wait for official Python 3.14 support")
                        else:
                            self.log_message("Manual installation required:")
                            self.log_message("1. Open Command Prompt as Administrator")
                            self.log_message("2. Run: pip install easyocr")
                            self.log_message("3. If that fails, try: pip install --user easyocr")
                        self.log_message("The app will use fallback text detection without OCR")
                    else:
                        self.log_message("✓ EasyOCR installed via dependency method")
                else:
                    self.log_message("✓ EasyOCR installed via force-reinstall")
            else:
                self.log_message("✓ EasyOCR installed successfully")
                    
            # Install OpenCV (same as install.bat)
            self.update_progress("🖼️ Installing OpenCV...")
            self.log_message("Installing OpenCV for image processing...")
            opencv_success = self.run_pip_install(["opencv-python"], description="OpenCV")
            if not opencv_success:
                self.log_message("OpenCV installation failed, trying --user flag...")
                self.run_pip_install(["opencv-python"], ["--user"], "OpenCV (user)")
                
            # Verification (same as install.bat)
            self.update_progress("✅ Verifying installation...")
            self.log_message("=== Final verification ===")
            self.log_message("Checking essential modules...")
            
            # Test core modules (same as install.bat)
            core_modules = [
                ("keyboard", "keyboard"),
                ("pynput", "pynput"), 
                ("mss", "mss"),
                ("numpy", "numpy"),
                ("PIL", "pillow"),
                ("requests", "requests"),
                ("win32api", "pywin32"),
                ("pystray", "pystray")
            ]
            
            for module, name in core_modules:
                try:
                    __import__(module)
                    self.log_message(f"✓ {name}")
                except ImportError:
                    self.log_message(f"✗ {name} MISSING")
                        
            # Test optional modules (same as install.bat)
            self.log_message("Checking optional modules...")
            try:
                import easyocr
                self.log_message("✓ EasyOCR (text recognition available)")
            except ImportError:
                self.log_message("✗ EasyOCR (text recognition disabled - using fallback detection)")
                
            try:
                import cv2
                self.log_message("✓ opencv-python (image processing)")
            except ImportError:
                self.log_message("✗ opencv-python (image processing disabled)")
                
            # Test basic functionality (same as install.bat)
            self.log_message("Testing basic functionality...")
            try:
                import keyboard, pynput, mss, numpy, PIL, requests, win32api, pystray
                self.log_message("✓ All essential modules working")
            except ImportError as e:
                self.log_message(f"✗ Missing module: {e}")
                self.log_message("WARNING: Some essential modules are missing")
                self.log_message("The program may not work correctly")
                self.log_message("Try running the installer as administrator")
                
            self.log_message("=== Installation Complete! ===")
            self.installation_complete = True
            
        except Exception as e:
            self.log_message(f"Installation failed with error: {e}")
            
        finally:
            # Stop progress bar and update UI
            self.progress.stop()
            self.installation_running = False
            
            if self.installation_complete:
                self.update_progress("🎉 Installation completed successfully!")
                self.status_msg.config(text="Installation completed! You can now close this window.", fg="#228b22")
                self.install_button.config(text="✅ Installation Complete", state='disabled', 
                                         bg="#228b22", fg="#ffffff")
                self.show_completion_dialog()
            else:
                self.update_progress("❌ Installation failed")
                self.status_msg.config(text="Installation failed. Check the logs for details.", fg="#b22222")
                self.install_button.config(text="❌ Installation Failed", state='disabled', 
                                         bg="#b22222", fg="#ffffff")
                
    def start_installation(self):
        """Start the installation process in a separate thread"""
        if self.installation_running:
            return
            
        self.installation_running = True
        self.install_button.config(state='disabled', text="🔄 Installing...", 
                                 bg="#666666", fg="#ffffff")
        self.progress.start()
        self.log_message("Starting installation process...")
        
        # Open the log section automatically when installation starts
        if not self.log_section.is_expanded:
            self.log_section.toggle()
        
        # Run installation in separate thread to keep GUI responsive
        install_thread = threading.Thread(target=self.install_dependencies)
        install_thread.daemon = True
        install_thread.start()
        
    def show_completion_dialog(self):
        """Show completion dialog with next steps"""
        message = """🎉 Installation completed successfully!

To run GPO Autofish:
• Double-click "run.bat" (recommended)
• Or run "python src/main.py" in command prompt

✅ Features available:
• Auto-fishing with PD controller
• Auto-purchase system  
• Discord webhook notifications
• System tray support
• Auto-recovery system
• Pause/Resume functionality
• Dual layout system (F2 to toggle)
• Text recognition for drops (OCR)
• Auto zoom control

Click OK to close the installer."""

        messagebox.showinfo("� Installation Compliete", message)
        self.close_application()
            
    def close_application(self):
        """Close the application"""
        self.root.quit()
        self.root.destroy()
        
    def run(self):
        """Start the GUI application"""
        self.root.mainloop()

if __name__ == "__main__":
    app = InstallerGUI()
    app.run()