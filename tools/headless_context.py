"""Creates an offscreen OpenGL context so the engine can be exercised without a screen.

The machine this repo is developed on has no GPU, so Mesa's llvmpipe software
renderer does the work. That is actually the right thing to test against: llvmpipe
reports GL 4.5 with no GL_ARB_bindless_texture, which is the same restriction the
Intel UHD 730 the engine targets has. If something compiles and draws here, it will
compile and draw there.

Run anything that uses this under a virtual X server:

    xvfb-run -a python3 your_script.py
"""
import os

os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
os.environ.setdefault("MESA_GL_VERSION_OVERRIDE", "4.5")
os.environ.setdefault("MESA_GLSL_VERSION_OVERRIDE", "450")

import glfw


def make_context(width: int = 640, height: int = 480, visible: bool = False, title: str = "headless"):
    """Returns a GLFW window with a 4.3 core context current on it.

    4.3 is what the engine's shaders target, and asking for exactly that keeps this
    working on drivers that top out below 4.6."""
    if not glfw.init():
        raise RuntimeError("Failed to initialize GLFW")
    glfw.window_hint(glfw.VISIBLE, glfw.TRUE if visible else glfw.FALSE)
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)
    window = glfw.create_window(width, height, title, None, None)
    if not window:
        glfw.terminate()
        raise RuntimeError("Failed to create an offscreen window")
    glfw.make_context_current(window)
    return window


def describe_context():
    from OpenGL.GL import (glGetString, glGetIntegerv, glGetStringi, GL_VERSION, GL_RENDERER,
                           GL_SHADING_LANGUAGE_VERSION, GL_EXTENSIONS, GL_NUM_EXTENSIONS,
                           GL_MAX_TEXTURE_IMAGE_UNITS)
    extension_count = glGetIntegerv(GL_NUM_EXTENSIONS)
    extensions = {glGetStringi(GL_EXTENSIONS, i).decode() for i in range(extension_count)}
    return {
        "version": glGetString(GL_VERSION).decode(),
        "renderer": glGetString(GL_RENDERER).decode(),
        "glsl": glGetString(GL_SHADING_LANGUAGE_VERSION).decode(),
        "max_texture_image_units": int(glGetIntegerv(GL_MAX_TEXTURE_IMAGE_UNITS)),
        "has_bindless": "GL_ARB_bindless_texture" in extensions,
    }


def save_framebuffer(path: str, width: int, height: int, framebuffer: int = 0):
    """Reads the given framebuffer back into a PNG, flipped the right way up."""
    from OpenGL.GL import (glBindFramebuffer, glReadPixels, glPixelStorei, GL_FRAMEBUFFER,
                           GL_RGBA, GL_UNSIGNED_BYTE, GL_PACK_ALIGNMENT)
    import numpy as np
    from PIL import Image

    glBindFramebuffer(GL_FRAMEBUFFER, framebuffer)
    glPixelStorei(GL_PACK_ALIGNMENT, 1)
    raw = glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE)
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)
    Image.fromarray(pixels[::-1]).save(path)
    return path
