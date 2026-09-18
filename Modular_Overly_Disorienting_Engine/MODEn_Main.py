import glfw
from OpenGL.GL import *
from Modular_Overly_Disorienting_Engine.Layer_0_Modules import *
from Modular_Overly_Disorienting_Engine.Layer_1_Modules import *
from Modular_Overly_Disorienting_Engine.Layer_2_Modules import *
from Modular_Overly_Disorienting_Engine.Layer_3_Modules import *
from Modular_Overly_Disorienting_Engine.Layer_4_Modules import *
import ctypes


#TODO fix imports and add purpose text to everything
#TODO Improve models and meshes and the way that they are drawn, so that they can be instanced and batch rendered
#TODO FIX THE STUPID LIGHTING ISSUE THAT MAKES THINGS DARKER WHEN FIRST TURNING ON THE COLOR OF THE LIGHT
#TODO ALSO make lights per scene not global
#TODO find a way to call layer.optimize_layer every so often automatically
#TODO just... just go over the text module man. be brave and get there dude....

purpose_text("Ties all of the previous layers together and offers the main unmodified loop")
purpose_text("Currently running version 0.9")

# Main loop


def load_engine(any_window=None):
    if any_window is not None:
        any_window.select()
        print("Remember to set a camera as main to every window you have after loading engine, otherwise the program will crash")
        TextureHandler._load_texture_handler()
        LightHandler._load_light_handler()
        TextHandler._load_text_handler()
    else:
        raise Exception("You have not given any window to the load_engine function")



def activate_main_loop(loop_addition):

    glEnable(GL_DEPTH_TEST)

    while Window.active_windows:

        glfw.poll_events()

        # The clock has to be advanced before anything consumes it. This used to read
        # TimeHandler.delta_time before _update_dt() had run, so every reveal timer and
        # every scene update was a frame behind, and on the very first frame they were
        # handed a delta of zero.
        global_dt=TimeHandler._update_dt()
        TextHandler._update(global_dt)
        SceneHandler.update_scenes(global_dt)

        for window in Window.active_windows[:]:  # shallow copy to allow safe removal
            if glfw.window_should_close(window.id):
                window.close()
                continue
            else:
                window.select()
                window.run_active_input_actions()
                window._rendering_loop()


        loop_addition(global_dt)

    # Every window has been closed, so the loop is over and GLFW can let go of the
    # platform resources it grabbed. This used to sit at module level, which meant
    # that merely importing the engine tore down GLFW: the only reason anything
    # worked was that the package __init__ happened to call glfw.init() again
    # immediately afterwards. Creating a context before the import would break it.
    glfw.terminate()