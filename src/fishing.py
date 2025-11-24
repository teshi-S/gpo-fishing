import threading
import time
import mss
import numpy as np
import win32api
import win32con
import keyboard

class FishingBot:
    def __init__(self, app):
        self.app = app
        self.recovery_in_progress = False
        self.watchdog_active = False
        self.watchdog_thread = None
        self.last_loop_heartbeat = time.time()
        self.force_stop_flag = False
    
    def check_recovery_needed(self):
        """Simple recovery check - detects stuck states"""
        if not self.app.recovery_enabled or not self.app.main_loop_active or self.recovery_in_progress:
            return False
            
        current_time = time.time()
        
        # Check every 15 seconds
        if current_time - self.app.last_smart_check < 15.0:
            return False
            
        self.app.last_smart_check = current_time
        
        # Check if current state has been running too long
        state_duration = current_time - self.app.state_start_time
        max_duration = self.app.max_state_duration.get(self.app.current_state, 60.0)
        
        # Shorter timeout for idle state
        if self.app.current_state == "idle" and state_duration > 30.0:
            max_duration = 30.0
        
        if state_duration > max_duration:
            self.app.log(f'🚨 State "{self.app.current_state}" stuck for {state_duration:.0f}s (max: {max_duration}s)', "error")
            return True
            
        # Check for complete freeze
        time_since_activity = current_time - self.app.last_activity_time
        if time_since_activity > 90:
            self.app.log(f'⚠️ Complete freeze detected - no activity for {time_since_activity:.0f}s', "error")
            return True
            
        return False
    
    def start_watchdog(self):
        """Start aggressive watchdog that monitors from OUTSIDE the main loop"""
        if self.watchdog_active:
            return
            
        self.watchdog_active = True
        self.last_loop_heartbeat = time.time()
        self.watchdog_thread = threading.Thread(target=self._watchdog_monitor, daemon=True)
        self.watchdog_thread.start()
        self.app.log('🐕 Watchdog started - monitoring for stuck states', "verbose")
    
    def stop_watchdog(self):
        """Stop the watchdog"""
        self.watchdog_active = False
        if self.watchdog_thread and self.watchdog_thread.is_alive():
            self.watchdog_thread.join(timeout=2.0)
    
    def _watchdog_monitor(self):
        """AGGRESSIVE watchdog that runs OUTSIDE main loop to catch stuck states"""
        while self.watchdog_active and self.app.main_loop_active:
            try:
                current_time = time.time()
                
                # Check heartbeat from main loop
                heartbeat_age = current_time - self.last_loop_heartbeat
                
                # AGGRESSIVE: Check every 5 seconds, trigger if no heartbeat for 20 seconds
                if heartbeat_age > 20.0:
                    self.app.log(f'🚨 WATCHDOG TRIGGERED: No heartbeat for {heartbeat_age:.0f}s - FORCE RECOVERY', "error")
                    self._force_recovery()
                    break
                
                # Also check traditional stuck states
                if self.check_recovery_needed():
                    self.app.log('🚨 WATCHDOG: Stuck state detected - FORCE RECOVERY', "error")
                    self._force_recovery()
                    break
                
                time.sleep(5.0)  # Check every 5 seconds
                
            except Exception as e:
                self.app.log(f'⚠️ Watchdog error: {e}', "error")
                time.sleep(5.0)
        
        self.app.log('🐕 Watchdog stopped', "verbose")
    
    def update_heartbeat(self):
        """Update heartbeat from main loop"""
        self.last_loop_heartbeat = time.time()
    
    def _force_recovery(self):
        """NUCLEAR OPTION: Force recovery when system is truly stuck"""
        if self.recovery_in_progress:
            return
            
        current_time = time.time()
        
        # Recovery limit
        if self.app.recovery_count >= 3:
            self.app.log(f'🛑 RECOVERY LIMIT REACHED: {self.app.recovery_count} attempts failed. STOPPING EVERYTHING.', "error")
            self.app.main_loop_active = False
            self.watchdog_active = False
            return
        
        self.recovery_in_progress = True
        self.app.recovery_count += 1
        self.app.last_recovery_time = current_time
        
        self.app.log(f'💥 FORCE RECOVERY #{self.app.recovery_count}/3 - NUKING EVERYTHING', "error")
        
        # Send webhook
        if hasattr(self.app, 'webhook_manager'):
            recovery_info = {
                "recovery_number": self.app.recovery_count,
                "stuck_state": self.app.current_state,
                "timestamp": current_time,
                "recovery_type": "FORCE_RECOVERY"
            }
            self.app.webhook_manager.send_recovery(recovery_info)
        
        # FORCE stop everything
        self.force_stop_flag = True
        self.app.main_loop_active = False
        
        # Release mouse IMMEDIATELY
        try:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self.app.is_clicking = False
        except:
            pass
        
        # Reset ALL state
        self.app.last_activity_time = current_time
        self.app.last_fish_time = current_time
        self.app.set_recovery_state("idle", {"action": "force_recovery_reset"})
        
        # AGGRESSIVE thread cleanup - don't wait nicely
        self.app.log('💥 FORCE KILLING main loop thread...', "verbose")
        time.sleep(1.0)  # Brief pause for force_stop_flag to take effect
        
        # Try to join thread, but don't wait forever
        try:
            if hasattr(self.app, 'main_loop_thread') and self.app.main_loop_thread and self.app.main_loop_thread.is_alive():
                self.app.main_loop_thread.join(timeout=3.0)
                if self.app.main_loop_thread.is_alive():
                    self.app.log('⚠️ Thread refused to die - continuing anyway', "error")
        except:
            pass
        
        # RESTART FROM SCRATCH
        if self.app.recovery_count < 3:
            self.app.log('💥 RESTARTING FROM SCRATCH...', "important")
            
            # Reset flags
            self.force_stop_flag = False
            self.last_loop_heartbeat = time.time()
            
            # Start fresh
            self.app.main_loop_active = True
            self.app.main_loop_thread = threading.Thread(target=self.run_main_loop, daemon=True)
            self.app.main_loop_thread.start()
            
            self.app.log('✅ FORCE RECOVERY COMPLETE - Fresh start initiated', "important")
        
        self.recovery_in_progress = False
    
    def perform_recovery(self):
        """Legacy recovery method - now just calls force recovery"""
        self._force_recovery()
    
    def cast_line(self):
        """Cast fishing line"""
        self.app.cast_line()
    
    def check_and_purchase(self):
        """Check if auto-purchase is needed"""
        if getattr(self.app, 'auto_purchase_var', None) and self.app.auto_purchase_var.get():
            self.app.purchase_counter += 1
            loops_needed = int(getattr(self.app, 'loops_per_purchase', 1)) if getattr(self.app, 'loops_per_purchase', None) is not None else 1
            print(f'🔄 Purchase counter: {self.app.purchase_counter}/{loops_needed}')
            if self.app.purchase_counter >= max(1, loops_needed):
                try:
                    self.perform_auto_purchase()
                    self.app.purchase_counter = 0
                except Exception as e:
                    print(f'❌ AUTO-PURCHASE ERROR: {e}')
    
    def perform_auto_purchase(self):
        """Perform auto-purchase sequence"""
        pts = self.app.point_coords
        if not pts or not pts.get(1) or not pts.get(2) or not pts.get(3) or not pts.get(4):
            print('Auto purchase aborted: points not fully set (need points 1-4).')
            return
        
        if not self.app.main_loop_active:
            print('Auto purchase aborted: main loop stopped.')
            return
        
        amount = str(self.app.auto_purchase_amount)
        
        # Purchase sequence with state tracking
        self.app.set_recovery_state("menu_opening", {"action": "pressing_e_key"})
        keyboard.press_and_release('e')
        time.sleep(self.app.purchase_delay_after_key)
        
        if not self.app.main_loop_active:
            return
        
        self.app.set_recovery_state("clicking", {"action": "click_point_1"})
        self._click_at(pts[1])
        time.sleep(self.app.purchase_click_delay)
        
        if not self.app.main_loop_active:
            return
        
        self.app.set_recovery_state("clicking", {"action": "click_point_2"})
        self._click_at(pts[2])
        time.sleep(self.app.purchase_click_delay)
        
        if not self.app.main_loop_active:
            return
        
        self.app.set_recovery_state("typing", {"action": "typing_amount"})
        keyboard.write(amount)
        time.sleep(self.app.purchase_after_type_delay)
        
        if not self.app.main_loop_active:
            return
        
        # Continue purchase sequence
        self._click_at(pts[1])
        time.sleep(self.app.purchase_click_delay)
        
        if not self.app.main_loop_active:
            return
        
        self._click_at(pts[3])
        time.sleep(self.app.purchase_click_delay)
        
        if not self.app.main_loop_active:
            return
        
        self._click_at(pts[2])
        time.sleep(self.app.purchase_click_delay)
        
        if not self.app.main_loop_active:
            return
        
        self._right_click_at(pts[4])
        time.sleep(self.app.purchase_click_delay)
        
        if hasattr(self.app, 'webhook_manager'):
            self.app.webhook_manager.send_purchase(amount)
        print()
    
    def _click_at(self, coords):
        """Click at coordinates"""
        try:
            x, y = (int(coords[0]), int(coords[1]))
            win32api.SetCursorPos((x, y))
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        except Exception as e:
            print(f'Error clicking at {coords}: {e}')
    
    def _right_click_at(self, coords):
        """Right click at coordinates"""
        try:
            x, y = (int(coords[0]), int(coords[1]))
            win32api.SetCursorPos((x, y))
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
        except Exception as e:
            print(f'Error right-clicking at {coords}: {e}')
    
    def run_main_loop(self):
        """Main fishing loop with aggressive monitoring"""
        print('🎣 Main loop started with watchdog protection')
        target_color = (85, 170, 255)
        dark_color = (25, 25, 25)
        white_color = (255, 255, 255)
        
        # Start watchdog if not already running
        if not self.watchdog_active:
            self.start_watchdog()
        
        # Reset recovery count on fresh start
        if not self.recovery_in_progress:
            self.app.recovery_count = 0
        
        try:
            with mss.mss() as sct:
                # Auto-purchase at start if enabled
                if getattr(self.app, 'auto_purchase_var', None) and self.app.auto_purchase_var.get():
                    self.app.set_recovery_state("purchasing", {"sequence": "auto_purchase"})
                    self.perform_auto_purchase()
                
                # Main fishing loop
                while self.app.main_loop_active and not self.force_stop_flag:
                    # Update heartbeat for watchdog
                    self.update_heartbeat()
                    
                    try:
                        # Cast line
                        self.app.set_recovery_state("casting", {"action": "initial_cast"})
                        self.cast_line()
                        cast_time = time.time()
                        
                        # Enter detection phase
                        self.app.set_recovery_state("fishing", {"action": "blue_bar_detection"})
                        detected = False
                        was_detecting = False
                        print('Scanning for blue fishing bar...')
                        
                        detection_start_time = time.time()
                        while self.app.main_loop_active and not self.force_stop_flag:
                            # Update heartbeat frequently during detection
                            self.update_heartbeat()
                            
                            # Timeout check
                            current_time = time.time()
                            if current_time - detection_start_time > self.app.scan_timeout + 10:
                                print(f'Detection timeout after {self.app.scan_timeout + 10}s, recasting...')
                                break
                            
                            # Get screenshot
                            x = self.app.overlay_area['x']
                            y = self.app.overlay_area['y']
                            width = self.app.overlay_area['width']
                            height = self.app.overlay_area['height']
                            monitor = {'left': x, 'top': y, 'width': width, 'height': height}
                            screenshot = sct.grab(monitor)
                            img = np.array(screenshot)
                            
                            # Look for blue bar (target color)
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
                            
                            if found_first:
                                detected = True
                            else:
                                # No blue bar found
                                if not detected and time.time() - cast_time > self.app.scan_timeout:
                                    print(f'Cast timeout after {self.app.scan_timeout}s, recasting...')
                                    break
                                
                                if was_detecting:
                                    print('Fish caught! Processing...')
                                    time.sleep(self.app.wait_after_loss)
                                    was_detecting = False
                                    self.check_and_purchase()
                                    break
                                
                                time.sleep(0.1)
                                continue
                            
                            # Find right edge of blue bar
                            point2_x = None
                            row_idx = point1_y - y
                            for col_idx in range(width - 1, -1, -1):
                                b, g, r = img[row_idx, col_idx, 0:3]
                                if r == target_color[0] and g == target_color[1] and b == target_color[2]:
                                    point2_x = x + col_idx
                                    break
                            
                            if point2_x is None:
                                time.sleep(0.1)
                                continue
                            
                            # Get the fishing bar area
                            temp_area_x = point1_x
                            temp_area_width = point2_x - point1_x + 1
                            temp_monitor = {'left': temp_area_x, 'top': y, 'width': temp_area_width, 'height': height}
                            temp_screenshot = sct.grab(temp_monitor)
                            temp_img = np.array(temp_screenshot)
                            
                            # Find top and bottom of dark area
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
                                time.sleep(0.1)
                                continue
                            
                            # Get the real fishing area
                            self.app.real_area = {'x': temp_area_x, 'y': top_y, 'width': temp_area_width, 'height': bottom_y - top_y + 1}
                            real_x = self.app.real_area['x']
                            real_y = self.app.real_area['y']
                            real_width = self.app.real_area['width']
                            real_height = self.app.real_area['height']
                            real_monitor = {'left': real_x, 'top': real_y, 'width': real_width, 'height': real_height}
                            real_screenshot = sct.grab(real_monitor)
                            real_img = np.array(real_screenshot)
                            
                            # Find white indicator
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
                            
                            # Find dark sections (fish position)
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
                            
                            # Control the fishing
                            if dark_sections and white_top_y is not None:
                                if not was_detecting:
                                    self.app.increment_fish_counter()
                                    self.app.set_recovery_state("idle")
                                was_detecting = True
                                
                                # Calculate error and control
                                for section in dark_sections:
                                    section['size'] = section['end'] - section['start'] + 1
                                largest_section = max(dark_sections, key=lambda s: s['size'])
                                
                                raw_error = largest_section['middle'] - white_top_y
                                normalized_error = raw_error / real_height if real_height > 0 else raw_error
                                derivative = normalized_error - self.app.previous_error
                                self.app.previous_error = normalized_error
                                pd_output = self.app.kp * normalized_error + self.app.kd * derivative
                                
                                print(f'Error: {raw_error}px, PD: {pd_output:.2f}')
                                
                                # Control mouse
                                if pd_output > 0:
                                    if not self.app.is_clicking:
                                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                                        self.app.is_clicking = True
                                else:
                                    if self.app.is_clicking:
                                        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                                        self.app.is_clicking = False
                            
                            time.sleep(0.1)
                        
                        self.app.set_recovery_state("idle", {"action": "detection_complete"})
                        
                    except Exception as e:
                        print(f'🚨 Main loop error: {e}')
                        self.app.log(f'Main loop error: {e}', "error")
                        if not self.force_stop_flag:
                            time.sleep(1.0)
                        else:
                            break  # Exit immediately on force stop
        
        except Exception as e:
            self.app.log(f'🚨 Critical main loop error: {e}', "error")
        
        finally:
            # ALWAYS clean up
            print('🛑 Main loop stopped - cleaning up')
            
            # Stop watchdog
            self.stop_watchdog()
            
            # Clean up mouse state
            if self.app.is_clicking:
                try:
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
                    self.app.is_clicking = False
                except:
                    pass