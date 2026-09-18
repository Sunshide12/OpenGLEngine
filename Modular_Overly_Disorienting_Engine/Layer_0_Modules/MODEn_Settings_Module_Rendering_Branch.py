from glfw import *
import inspect
import sys



# D:\Python\My_Python_Projects\venv\Scripts\pip.exe install #something something


USE_OWN="own"
RECOMPUTE="recompute"
class StartupSettings:
    enable_purpose_text = True
    enable_default_setup = False
    enable_debug_text=False
    def __init__(self):
        self.window_startup=WindowStartupSettings()
        self.camera_startup=CameraStartupSettings()
class WindowStartupSettings:
    valid_flags = [
        RED_BITS,
        GREEN_BITS,
        BLUE_BITS,
        ALPHA_BITS,
        DEPTH_BITS,
        STENCIL_BITS,
        ACCUM_RED_BITS,
        ACCUM_GREEN_BITS,
        ACCUM_BLUE_BITS,
        ACCUM_ALPHA_BITS,
        AUX_BUFFERS,
        SAMPLES,
        SRGB_CAPABLE,
        STEREO,
        DOUBLEBUFFER,
        RESIZABLE,
        VISIBLE,
        DECORATED,
        FOCUSED,
        AUTO_ICONIFY,
        FLOATING,
        MAXIMIZED,
        CENTER_CURSOR,
        TRANSPARENT_FRAMEBUFFER,
        FOCUS_ON_SHOW,
        SCALE_TO_MONITOR,
        CONTEXT_VERSION_MAJOR,
        CONTEXT_VERSION_MINOR,
    ]
    def __init__(self):
        self.starting_resolution_x = 500
        self.starting_resolution_y = 500
        self.starting_name = "Modular Overly Disorienting Engine"
        self.starting_purpose="Default placeholder text for a window's purpose. For modding and debugging purposes, it is recommended to change."
        self.starting_position_x = 0
        self.starting_position_y = 0
        self.copy_resources_from = None
        self.start_fullscreen = None
        self.clear_color=(0.0,0.0,0.0,1.0)
        self.render_directly_to_window=True
        self.starting_creation_flags = {RED_BITS:8,
                                        GREEN_BITS:8,
                                        BLUE_BITS:8,
                                        ALPHA_BITS:8,
                                        DEPTH_BITS:24,
                                        VISIBLE:TRUE,
                                        DOUBLEBUFFER:TRUE,
                                        CONTEXT_VERSION_MAJOR:4,
                                        CONTEXT_VERSION_MINOR:6,
        }
        self._standardized_startup_truth_constants=[
            0<=self.starting_resolution_x,
            0<=self.starting_resolution_y,
            0<=self.starting_position_x,
            0<=self.starting_position_y,
            len(self.clear_color)==4,
            isinstance(self.starting_name,str),
            isinstance(self.starting_purpose, str),
            isinstance(self.clear_color,tuple),
            isinstance(self.render_directly_to_window, bool),
            all(key in WindowStartupSettings.valid_flags for key in self.starting_creation_flags.keys())
        ]
    def set_flag(self,flag,value):
        self.starting_creation_flags[flag]=value
    def remove_flag(self,flag):
        self.starting_creation_flags.pop(flag)

    def is_valid(self):
        for equality in self._standardized_startup_truth_constants:
            if not equality:
                print(f'A window setting truth constant, seems to be untrue. Hence, the program will keep terminating until the issue is solved by the programmer')
                sys.exit()


        #You can use these as flags
        #     NAME                          DESCRIPTION                               VALUE
        # RED_BITS				    Bits for red channel	                        8
        # GREEN_BITS				Bits for green channel	                        8
        # BLUE_BITS				    Bits for blue channel	                        8
        # ALPHA_BITS				Bits for alpha channel	                        8
        # DEPTH_BITS				Bits for depth buffer	                        24
        # STENCIL_BITS			    Bits for stencil buffer                     	8
        # ACCUM_RED_BITS			Bits for accumulation buffer (red)	    Usually 0
        # ACCUM_GREEN_BITS			Bits for accumulation buffer (green)	Usually 0
        # ACCUM_BLUE_BITS			Bits for accumulation buffer (blue)	    Usually 0
        # ACCUM_ALPHA_BITS			Bits for accumulation buffer (alpha)	Usually 0
        # AUX_BUFFERS			    Number of auxiliary buffers	                    0
        # SAMPLES				    Number of samples for multisampling (MSAA)	    0, 4, 8
        # SRGB_CAPABLE			    Enable sRGB (color correction for human eye) framebuffer    TRUE/FALSE
        # STEREO				    Enable stereo(VR) rendering	            TRUE/FALSE
        # DOUBLEBUFFER			    Enable double buffering	                TRUE/FALSE

        # RESIZABLE	                Can the window be resized?	            TRUE/FALSE
        # VISIBLE	                Show the window after creation	        TRUE/FALSE
        # DECORATED	                Include title bar and borders	        TRUE/FALSE
        # FOCUSED	                Focus window on creation	            TRUE/FALSE
        # AUTO_ICONIFY	            Auto-minimize fullscreen on focus loss	TRUE/FALSE
        # FLOATING	                Always on top?	                        TRUE/FALSE
        # MAXIMIZED	                Start window maximized	                TRUE/FALSE
        # CENTER_CURSOR	            Center cursor on window creation	    TRUE/FALSE
        # TRANSPARENT_FRAMEBUFFER	Transparent window background	        TRUE/FALSE
        # FOCUS_ON_SHOW	            Focus window when shown	                TRUE/FALSE
        # SCALE_TO_MONITOR	        Auto-scale window on high-DPI displays	TRUE/FALSE
class OutputStartupSettings:
    def __init__(self):
        self.resolution_x=500
        self.resolution_y=500
        self.add_depth_buffer=True
        self.add_stencil_buffer=False
class CameraStartupSettings:

    def __init__(self):
        self.yaw_limit_down = 0
        self.yaw_limit_up = 360
        self.pitch_limit_down = 0
        self.pitch_limit_up = 360
        self.roll_limit_down = 0
        self.roll_limit_up = 360
        self.field_of_view_y_axis = 60
        self.field_of_view_x_axis = RECOMPUTE
        self.near_plane = 0.1
        self.far_plane = 100
        self.turning_unit = 10
        self.rotation_order=((0.0,0.0,1.0),(1.0,0.0,0.0),(0.0,1.0,0.0))
        self.invert_mouse_vertical=False
        self.invert_mouse_horizontal=True
        self.use_default_rendering_shader=True
        self.make_renderer = True
        self._standardized_startup_truth_constants = [
            0 <=self.yaw_limit_down<self.yaw_limit_up <= 360,
            0 <= self.pitch_limit_down < self.pitch_limit_up <= 360,
            0 <= self.roll_limit_down < self.roll_limit_up <= 360,
            self.field_of_view_y_axis==RECOMPUTE and self.field_of_view_x_axis != RECOMPUTE or 0 < self.field_of_view_y_axis < 181,
            self.field_of_view_x_axis==RECOMPUTE and self.field_of_view_y_axis != RECOMPUTE or 0 < self.field_of_view_x_axis < 181,
            0 < self.near_plane,
            0< self.far_plane,
            isinstance(self.rotation_order,tuple),
            isinstance(self.rotation_order[0],tuple),
            isinstance(self.rotation_order[1], tuple),
            isinstance(self.rotation_order[2], tuple),
            isinstance(self.invert_mouse_vertical,bool),
            isinstance(self.invert_mouse_horizontal,bool),
            isinstance(self.use_default_rendering_shader, bool),
            isinstance(self.make_renderer, bool),
            all(isinstance(unimportant_name, int) for unimportant_name in [1])
        ]
        self.startup_output_settings=OutputStartupSettings()


    def is_valid(self):
        for equality in self._standardized_startup_truth_constants:
            if not equality:
                print(f'A camera setting truth constant, seems to be untrue. Hence, the program will keep terminating until the issue is solved by the programmer')
                sys.exit()
active_default_settings=StartupSettings()

def purpose_text(purpose):
    if StartupSettings.enable_purpose_text:
        print(f"{inspect.getmodule(inspect.stack()[1].frame).__name__}     <-{purpose}")

purpose_text("The base of everything, has the (default) values from which all other modules begin ")


