"""A primitive Windows style desktop, built on the engine in this repo.

What it exercises, end to end:

  * the text module's MSDF glyph pipeline, drawing the pregenerated atlases in
    Fonts/Already_Loaded_Fonts, including its typewriter reveal modes
  * the UI module's bevelled widgets: draggable windows, buttons, a taskbar with a
    Start menu and a clock, desktop icons
  * bound texture units rather than GL_ARB_bindless_texture, so it runs on Mesa
    drivers such as the Intel UHD Graphics this was written for

Run it normally:

    python3 windows_desktop_demo.py

Or offscreen, on a machine with no display, which is how it gets verified:

    xvfb-run -a python3 windows_desktop_demo.py --frames 60 --screenshot desktop.png

A note on which fonts appear here. Of the fifteen atlases in the repo, fourteen
render correctly. "Menu" is left out because its glyph plane bounds are about three
times its advances, so its letters pile on top of each other: that atlas needs
regenerating, and no amount of engine code fixes it.
"""

import argparse
import sys

from Modular_Overly_Disorienting_Engine import *

# ---------------------------------------------------------------------------
# The desktop is described from the top left, the way a window manager would lay
# it out, and converted to the engine's bottom left origin on the way in.
# ---------------------------------------------------------------------------
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 720

DESKTOP_TEAL = (0.0, 0.5, 0.5, 1.0)
TEXT_BLACK = (0.0, 0.0, 0.0, 1.0)
TEXT_WHITE = (1.0, 1.0, 1.0, 1.0)

UI_FONT = ("Arial", False, False)
# Decorative atlases the demo shows off. Each entry is the font's cache name and the
# .ttf inside Fonts/Font_Zip_Archives that produced it.
EXTRA_FONTS = [
    ("Lexiconius", "lexiconius.ttf"),
    ("London-20", "london-20.ttf"),
    ("Tiberian", "tiberian.ttf"),
    ("Herzog", "herzog.ttf"),
]


def from_top(y_from_top, height=0.0):
    """Turns a top-down y into the bottom-up y the engine wants."""
    return SCREEN_HEIGHT - y_from_top - height


def sample_for_font(font_key, preferred=("Handgloves 123", "HANDGLOVES 123", "HANDGLOVES")):
    """Picks a specimen string the font can actually draw.

       Most of these atlases are display faces that ship caps only, or no digits, so
       asking for lowercase would silently render nothing for those characters."""
    data = TextHandler.fonts.get(font_key)
    if data is None:
        return ""
    available = set(data["glyphs"])
    for candidate in preferred:
        if all(ord(character) in available for character in candidate):
            return candidate
    drawable = "".join(chr(code) for code in sorted(available) if 33 <= code < 127)
    return drawable[:14]


class Desktop:
    """Owns the window, the camera, the shaders and every widget on screen."""

    def __init__(self, width=SCREEN_WIDTH, height=SCREEN_HEIGHT, visible=True):
        self.width = width
        self.height = height
        self.open_windows = []

        settings = StartupSettings()
        settings.window_startup.starting_resolution_x = width
        settings.window_startup.starting_resolution_y = height
        settings.window_startup.starting_name = "Modular Overly Disorienting Engine - Desktop"
        settings.window_startup.clear_color = DESKTOP_TEAL
        if not visible:
            settings.window_startup.set_flag(VISIBLE, FALSE)

        self.window = Window(settings)
        self.window.select()

        self.mouse = Mouse(MouseLayout())
        self.keyboard = Keyboard(KeyboardLayout())
        self.mouse.default_window = self.window
        self.keyboard.default_window = self.window
        self.window.set_input(self.mouse, self.keyboard)

        # load_engine brings up the texture, light and text handlers, so every shader
        # and every atlas has to be created after this point.
        load_engine(self.window)

        self.ui_shader = CompleteShader(VertexShader.ui_rect_shader, FragmentShader.ui_rect_shader)
        self.text_shader = CompleteShader(VertexShader.ui_text_shader, FragmentShader.text_shader)

        output = OutputStartupSettings()
        output.resolution_x, output.resolution_y = width, height
        self.camera = Camera(specific_output_settings=output)
        self.window.set_main_camera(self.camera)

        # The rects go down first and the glyphs on top, which is purely a matter of
        # the order the shaders were added to the camera.
        self.camera.add_shaders(self.ui_shader, PASS_UI)
        self.camera.add_shaders(self.text_shader, PASS_TEXT_UI)

        for name, zip_name in EXTRA_FONTS:
            TextHandler.load_font(name, False, False, zip_name)

        UIHandler._load_ui_handler()
        UIHandler.set_viewport_size(width, height)

        perspective = glm.ortho(0.0, float(width), 0.0, float(height))
        # Captions live on their own text layer, paired with the rect layer. Both are
        # attached to their shader so neither pass draws the other's layers.
        self.text_layer = TextLayer(perspective, reserved_characters=4096)
        self.ui_layer = UILayer(perspective, capacity=256, text_layer=self.text_layer)
        self.camera.add_layers_to_shaders(self.text_shader, self.text_layer)
        self.camera.add_layers_to_shaders(self.ui_shader, self.ui_layer)

        self.mouse.add_action_to_layouts(UIHandler.handle_mouse_press, MOUSE_BUTTON_LEFT, PRESS)
        self.mouse.add_action_to_layouts(UIHandler.handle_mouse_release, MOUSE_BUTTON_LEFT, RELEASE)
        self.mouse.add_action_to_layouts(UIHandler.handle_mouse_move, None, MOUSE_MOVE)
        self.keyboard.add_action_to_layouts(self.window.close, KEY_ESCAPE, PRESS)

        self._build_desktop()

    # -- desktop furniture ---------------------------------------------------
    def _build_desktop(self):
        self.taskbar = UITaskbar(self.ui_layer, float(self.width),
                                 on_start_click=lambda: self.start_menu.toggle())
        self.start_menu = UIStartMenu(self.ui_layer, 3.0, TASKBAR_HEIGHT, width=190.0)
        self.start_menu.add_entry("Notepad", self.open_notepad)
        self.start_menu.add_entry("Font Viewer", self.open_font_viewer)
        self.start_menu.add_entry("Typewriter", self.open_typewriter)
        self.start_menu.add_entry("About", self.open_about)

        UIDesktopIcon(self.ui_layer, 30.0, from_top(60.0, ICON_DEFAULT_SIZE), "Notepad",
                      on_activate=self.open_notepad)
        UIDesktopIcon(self.ui_layer, 30.0, from_top(150.0, ICON_DEFAULT_SIZE), "Fonts",
                      on_activate=self.open_font_viewer)
        UIDesktopIcon(self.ui_layer, 30.0, from_top(240.0, ICON_DEFAULT_SIZE), "Readme",
                      on_activate=self.open_about)

        self.open_notepad()
        self.open_font_viewer()
        self.open_typewriter()

    def _new_window(self, x_from_left, y_from_top, width, height, title):
        window = UIWindow(self.ui_layer, float(x_from_left), from_top(y_from_top, height),
                          float(width), float(height), title=title,
                          on_close=self._forget_window)
        self.taskbar.add_window(window)
        self.open_windows.append(window)
        return window

    def _forget_window(self, closed_window):
        if closed_window in self.open_windows:
            self.open_windows.remove(closed_window)

    def _client_paragraph(self, window, x, y_from_client_top, wrap_width=-1):
        """A paragraph positioned inside a window's client area.

           Captions that belong to a widget go through UILabel, but body text wants
           wrapping and reveal modes, so it talks to the text module directly."""
        client = window.client_area
        base_x, base_y = client.get_absolute_position()
        paragraph = self.text_layer.add_new_paragraph()
        paragraph.set_position(base_x + x, base_y + client.height - y_from_client_top, 0.0)
        if wrap_width > 0:
            paragraph.set_bounds(width=wrap_width)
        return paragraph

    # -- the "applications" --------------------------------------------------
    def open_notepad(self):
        window = self._new_window(250, 70, 430, 250, "Untitled - Notepad")
        paragraph = self._client_paragraph(window, 8.0, 20.0, wrap_width=405.0)
        paragraph.add_sentence(
            "This text is drawn by the engine's own MSDF text module. Every glyph is one "
            "instance of a single quad, and all of them come from one atlas sampled "
            "through a bound texture unit.",
            font_key=UI_FONT, size=14.0, r=0.0, g=0.0, b=0.0,
            mode=MODE_INSTANT_TEXT, delay_mode=DELAY_NONE)
        # A second sentence in the same paragraph carries on from where the first one
        # stopped, so this one continues the flow instead of overlapping it.
        paragraph.add_sentence(
            "\n\nThe paragraph has a width, so those lines wrapped on their own. This "
            "sentence is a different colour to show that a paragraph can mix styles.",
            font_key=UI_FONT, size=14.0, r=0.1, g=0.1, b=0.55,
            mode=MODE_INSTANT_TEXT, delay_mode=DELAY_NONE)
        UIButton(self.ui_layer, 330.0, 8.0, 80.0, 24.0, caption="Close",
                 parent=window.client_area, on_click=window.close, raise_target=window)
        return window

    def open_font_viewer(self):
        window = self._new_window(430, 360, 520, 280, "Font Viewer")
        heading = self._client_paragraph(window, 8.0, 18.0)
        heading.add_sentence("Atlases loaded from Fonts/Already_Loaded_Fonts:",
                            font_key=UI_FONT, size=13.0, r=0.0, g=0.0, b=0.0,
                            mode=MODE_INSTANT_TEXT, delay_mode=DELAY_NONE)
        y = 48.0
        for name, _zip_name in EXTRA_FONTS:
            key = (name, False, False)
            if key not in TextHandler.fonts:
                continue
            label = self._client_paragraph(window, 8.0, y)
            label.add_sentence(f"{name}:", font_key=UI_FONT, size=12.0,
                               r=0.25, g=0.25, b=0.25,
                               mode=MODE_INSTANT_TEXT, delay_mode=DELAY_NONE)
            sample = self._client_paragraph(window, 130.0, y)
            sample.add_sentence(sample_for_font(key), font_key=key, size=24.0,
                                r=0.0, g=0.0, b=0.0,
                                mode=MODE_INSTANT_TEXT, delay_mode=DELAY_NONE)
            y += 52.0
        return window

    def open_typewriter(self):
        window = self._new_window(90, 400, 300, 200, "Typewriter")
        # Both sentences share one paragraph: that is what lets the second one wait for
        # the first, since DELAY_WAIT_FOR_SENTENCE with no target means "the sentence
        # before me in this paragraph".
        paragraph = self._client_paragraph(window, 8.0, 22.0, wrap_width=275.0)
        paragraph.add_sentence("Revealed one letter at a time. ",
                               font_key=UI_FONT, size=14.0, r=0.0, g=0.0, b=0.0,
                               mode=MODE_PER_LETTER, interval_in_seconds=0.05,
                               delay_mode=DELAY_NONE)
        paragraph.add_sentence("Then this one arrives a whole word at a time.",
                               font_key=UI_FONT, size=14.0, r=0.5, g=0.0, b=0.0,
                               mode=MODE_PER_WORD, interval_in_seconds=0.15,
                               delay_mode=DELAY_WAIT_FOR_SENTENCE)
        return window

    def open_about(self):
        window = self._new_window(520, 120, 400, 210, "About")
        title = self._client_paragraph(window, 12.0, 30.0)
        title.add_sentence("MODEn", font_key=("London-20", False, False), size=34.0,
                           r=0.1, g=0.1, b=0.4, mode=MODE_INSTANT_TEXT, delay_mode=DELAY_NONE)
        body = self._client_paragraph(window, 12.0, 70.0, wrap_width=370.0)
        body.add_sentence(
            "Modular Overly Disorienting Engine. Runs on an OpenGL 4.3 core context "
            "and no longer needs GL_ARB_bindless_texture, so Mesa drivers are fine.",
            font_key=UI_FONT, size=13.0, r=0.0, g=0.0, b=0.0,
            mode=MODE_INSTANT_TEXT, delay_mode=DELAY_NONE)
        UIButton(self.ui_layer, 300.0, 8.0, 80.0, 24.0, caption="OK",
                 parent=window.client_area, on_click=window.close, raise_target=window)
        return window

    # -- frame loop ----------------------------------------------------------
    def update(self, dt):
        UIHandler._update(dt)

    def capture(self, path):
        """Renders one frame and reads it straight back out.

           Deliberately does not rely on whatever is in the window's buffers after the
           main loop's last swap: on an offscreen window the front buffer holds nothing
           useful, which shows up as a blank white PNG. Drawing a fresh frame and
           reading the back buffer before any swap is the same picture, deterministically."""
        from OpenGL.GL import (glBindFramebuffer, glClear, glClearColor, glViewport,
                               glReadBuffer, glPixelStorei, glReadPixels, glEnable,
                               GL_FRAMEBUFFER, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
                               GL_BACK, GL_PACK_ALIGNMENT, GL_RGBA, GL_UNSIGNED_BYTE,
                               GL_DEPTH_TEST)
        import numpy as np
        from PIL import Image

        self.window.select()
        glEnable(GL_DEPTH_TEST)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glViewport(0, 0, self.width, self.height)
        glClearColor(*DESKTOP_TEAL)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.camera.render(False)

        glReadBuffer(GL_BACK)
        glPixelStorei(GL_PACK_ALIGNMENT, 1)
        raw = glReadPixels(0, 0, self.width, self.height, GL_RGBA, GL_UNSIGNED_BYTE)
        pixels = np.frombuffer(raw, dtype=np.uint8).reshape(self.height, self.width, 4)
        Image.fromarray(pixels[::-1]).save(path)
        return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="A primitive Windows style desktop built on MODEn.")
    parser.add_argument("--frames", type=int, default=None,
                        help="run this many frames and exit, instead of waiting for the window to close")
    parser.add_argument("--screenshot", metavar="PATH", default=None,
                        help="save the last frame to a PNG (implies --frames if not given)")
    parser.add_argument("--screenshot-every", type=int, default=None, metavar="N",
                        help="also save a PNG every N frames, numbered, next to --screenshot")
    parser.add_argument("--hidden", action="store_true",
                        help="do not show the window; for running offscreen")
    args = parser.parse_args(argv)

    frames = args.frames
    if args.screenshot and frames is None:
        frames = 45

    desktop = Desktop(visible=not args.hidden)

    saved = []

    def after_frame(frame_number, _dt):
        if args.screenshot_every and frame_number % args.screenshot_every == 0:
            stem = args.screenshot.rsplit(".", 1)[0] if args.screenshot else "desktop"
            saved.append(desktop.capture(f"{stem}_{frame_number:03d}.png"))

    activate_main_loop(desktop.update, max_frames=frames,
                       per_frame_callback=after_frame if args.screenshot_every else None)

    if args.screenshot:
        saved.append(desktop.capture(args.screenshot))
    for path in saved:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
