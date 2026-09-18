from Modular_Overly_Disorienting_Engine import Camera
from Modular_Overly_Disorienting_Engine.Layer_0_Modules import *
from typing import List

purpose_text("Handles Opening a screen, setting up its flags and basic window manipulation")


class Window:
    active_windows: List["Window"] = []
    def __init__(self, starting_settings: StartupSettings | WindowStartupSettings=active_default_settings,
                 auto_initialization: bool = True, keyboard: Keyboard = None,
                 mouse: Mouse = None,copy_resources_from_window_id:int=None):
        self.id = None
        if isinstance(starting_settings, StartupSettings):
            starting_settings = starting_settings.window_startup
        elif isinstance(starting_settings, WindowStartupSettings):
            starting_settings = starting_settings
        else:
            raise TypeError(f"Expected Settings or WindowSettings, got {type(starting_settings)}")
        starting_settings.is_valid()
        self.clear_color=starting_settings.clear_color
        self.starting_name_for_errors=starting_settings.starting_name
        self.last_clear_color=None
        self._main_camera=None
        self.depth_buffer_clear_value=1.0
        self.clear_func_value=GL_LESS
        self._other_linked_cameras=[]
        self._active_mouse_layout = None
        self._active_keyboard_layout = None
        if auto_initialization:
            self.make_functional(starting_settings, keyboard, mouse,copy_resources_from_window_id)
        self.aspect_ratio = starting_settings.starting_resolution_x/starting_settings.starting_resolution_y
    def make_functional(self, settings: WindowStartupSettings ,
                        keyboard: Keyboard = None, mouse: Mouse = None,copy_resources_from_window_id:int|None=None):
        if self.id is None:
            default_window_hints()
            for hint, value in settings.starting_creation_flags.items():
                window_hint(hint, value)
            if copy_resources_from_window_id is None:
                self.id = create_window(settings.starting_resolution_x,
                                        settings.starting_resolution_y,
                                        settings.starting_name,
                                        settings.start_fullscreen,
                                        settings.copy_resources_from)
            if copy_resources_from_window_id is not None:
                self.id = create_window(settings.starting_resolution_x,
                                        settings.starting_resolution_y,
                                        settings.starting_name,
                                        settings.start_fullscreen,
                                        copy_resources_from_window_id)
            set_window_pos(self.id, settings.starting_position_x, settings.starting_position_y)
            set_window_close_callback(self.id, self.close)
            Window.active_windows.append(self)
            if keyboard:
                self.set_active_keyboard_or_layout(keyboard)
            if mouse:
                self.set_active_mouse_or_layout(mouse)
    def set_input(self,mouse_or_layout:Mouse|MouseLayout,keyboard_or_layout:Keyboard|KeyboardLayout):
        self.set_active_mouse_or_layout(mouse_or_layout)
        self.set_active_keyboard_or_layout(keyboard_or_layout)

    def set_active_keyboard_or_layout(self, keyboard_or_layout: Keyboard|KeyboardLayout):
        if isinstance(keyboard_or_layout,Keyboard):
            layout=keyboard_or_layout.get_active_layout()
        else:
            layout=keyboard_or_layout
        self._active_keyboard_layout = layout
        set_key_callback(self.id, layout._callback_function)

    def set_active_mouse_or_layout(self, mouse_or_layout: Mouse|MouseLayout):
        if isinstance(mouse_or_layout,Mouse):
            layout=mouse_or_layout.get_active_layout()
        else:
            layout=mouse_or_layout
        self._active_mouse_layout = layout
        set_mouse_button_callback(self.id, layout._click_function)
        set_cursor_pos_callback(self.id, layout._move_function)
        set_scroll_callback(self.id, layout._scroll_function)
        set_cursor_enter_callback(self.id, layout._enter_function)
    def run_active_input_actions(self):
        if self._active_keyboard_layout:
            for action in self._active_keyboard_layout.get_held_actions():
                action()
        if self._active_mouse_layout:
            for action in self._active_mouse_layout.get_held_actions():
                action()
    def select(self):
        make_context_current(self.id)

    def set_main_camera(self, camera:Camera):
        self._main_camera=camera
        if self._main_camera.near_plane<self._main_camera.far_plane:
            self.depth_buffer_clear_value=1.0
            self.clear_func_value=GL_LESS
        else:
            self.depth_buffer_clear_value = 0.0
            self.clear_func_value = GL_GREATER
            glClipControl(GL_LOWER_LEFT, GL_ZERO_TO_ONE)
    def add_extra_cameras(self,cameras:list|Camera):
        if type(cameras) !=list:
            cameras=[cameras]
        if cameras not in self._other_linked_cameras:
            self._other_linked_cameras.extend(cameras)
    def _rendering_loop(self):
        glClearDepth(self.depth_buffer_clear_value)
        glDepthFunc(self.clear_func_value)
        if self.last_clear_color != self.clear_color:
            glClearColor(*self.clear_color)
            self.last_clear_color = self.clear_color
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        for camera in self._other_linked_cameras:
            camera.render(True)
        glMemoryBarrier(GL_TEXTURE_FETCH_BARRIER_BIT | GL_FRAMEBUFFER_BARRIER_BIT)
        if self._main_camera is None:
            raise RuntimeError(
                f"The window '{self.starting_name_for_errors}' is being rendered but has no main camera. "
                f"Call window.set_main_camera(camera) after load_engine().")
        self._main_camera.render(False)
        swap_buffers(self.id)
        # glViewport(0, 0, *self.get_dimensions())
    def close(self, useless_id=USE_OWN):
        if self in Window.active_windows:
            Window.active_windows.remove(self)
        destroy_window(self.id)
        self.id = None
    def hide(self):
        hide_window(self.id)
    def show(self):
        show_window(self.id)
    def minimize(self):
        iconify_window(self.id)
    def unminimize(self):
        restore_window(self.id)
    def pop_to_front(self):
        focus_window(self.id)
    def fullscreen(self):
        set_window_monitor(self.id, get_primary_monitor(), 0, 0, get_video_mode(get_primary_monitor()).width,
                           get_video_mode(get_primary_monitor()).height,
                           get_video_mode(get_primary_monitor()).refresh_rate)
    def update_aspect_ratio(self,x,y):
        self.aspect_ratio=x/y


    #TODO define a "on resize" that updates the aspect ratio




    def get_size(self):
        return get_window_size(self.id)
    def set_size(self,x:int=USE_OWN,y:int=USE_OWN, move_right_side_instead=False):
        current_size_x, current_size_y = self.get_size()
        if x == USE_OWN:
            x = current_size_x
        if y == USE_OWN:
            y = current_size_y
        set_window_size(self.id,x,y)
        self.update_aspect_ratio(x,y)

        if move_right_side_instead:
            self.set_position(self.get_position()[0] - (x - current_size_x))
        return x, y
    def change_size(self,x:int=0,y:int=0,move_right_side_instead=False):

        current_size_x, current_size_y = self.get_size()
        self.set_size(current_size_x+x,current_size_y+y)
        if move_right_side_instead:
            self.set_position(self.get_position()[0]-x)

    def get_position(self):
        return get_window_pos(self.id)
    def set_position(self,x:int=USE_OWN,y:int=USE_OWN):
        current_pos_x,current_pos_y=self.get_position()
        if x == USE_OWN:
            x=current_pos_x
        if y == USE_OWN:
            y=current_pos_y
        set_window_pos(self.id,x,y)
    def change_positions(self,x:int=0,y:int=0):
        current_pos_x, current_pos_y = self.get_position()
        set_window_pos(self.id, current_pos_x+x, current_pos_y+y)
    def should_close(self):
        if self.id is None:
            return True
        else:
            return False


# default_window_hints()	Reset all window hints to their defaults
#
# window_hint(hint, value)	Set a GLFW hint (e.g. color/depth bits, resizable, etc.)
#
# create_window(w, h, title, monitor, share)	Create window and OpenGL/Vulkan context
#
# destroy_window(window)	Destroy the window and its context
#
# window_should_close(window)	Check if close flag is set for the window
#
# set_window_should_close(window, value)	Set the window’s close flag
#
# set_window_title(window, title)	Change window title at runtime
#
# get_window_pos(window)	Get current window position (x, y)
#
# set_window_pos(window, x, y)	Move window to a specified position
#
# get_window_size(window)	Get window client area size
#
# set_window_size(window, w, h)	Resize window client area
#
# get_framebuffer_size(window)	Get framebuffer pixel size (for high‑DPI support)
#
# get_window_frame_size(window)	Get outer frame border sizes
#
# iconify_window(window)	Minimize (iconify) the window
#
# restore_window(window)	Restore from minimized state
#
# show_window(window)	Make the window visible
#
# hide_window(window)	Hide the window
#
# get_window_attrib(window, attrib)	Query runtime window attributes (e.g. RESIZABLE)
#
# set_window_user_pointer(window, ptr)	Store custom Python data associated with window
#
# get_window_user_pointer(window)	Retrieve stored pointer object
#
# set_window_pos_callback(window, cb)	Callback when window moves
#
# set_window_size_callback(window, cb)	Callback when resized
#
# set_window_close_callback(window, cb)	Callback on close request (e.g. X button)
#
# set_window_refresh_callback(window, cb)	Called when window needs redraw
#
# set_window_focus_callback(window, cb)	Called when window gains/loses focus
#
# set_window_iconify_callback(window, cb)	Called when window is minimized/restored
#
# set_framebuffer_size_callback(window, cb)	Callback on framebuffer resize (HDPI-aware)
#
# poll_events()	Poll pending events (input, window changes, etc.)
#
# wait_events()	Sleep until at least one event occurs
#
# wait_events_timeout(timeout)	Sleep with timeout waiting for events
#
# post_empty_event()	Wake up thread waiting on events
#
# swap_buffers(window)	Present your rendered frame (double buffering)
