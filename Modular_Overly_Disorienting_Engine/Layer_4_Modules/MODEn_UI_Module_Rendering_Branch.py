"""Retro Windows-95-style UI widget toolkit.

Architecture is the structural twin of the text module
(`MODEn_Text_Module_Rendering_Branch.py`): a `UIHandler` owns one big SSBO,
`UILayer`s own slices of it, widgets pack their data into a CPU-side
bytearray with `struct.pack_into`, and the whole slice is pushed to the GPU
with a single `glBufferSubData` per dirty range. One instanced unit quad is
drawn per layer (`glDrawElementsInstanced(..., layer.get_rect_count())`).

Coordinate space
-----------------
All UI coordinates are in UI PIXELS with the origin at the BOTTOM-LEFT of the
target framebuffer and y increasing UPWARD. This matches
`glm.ortho(0.0, width, 0.0, height)`, exactly how `TextLayer`'s perspective
matrices are built elsewhere in the engine.

GLFW (and therefore the Input module's mouse callbacks) reports the cursor
with y measured DOWN from the TOP of the window. Win95-style layouts are also
naturally laid out from the top down. Use the module-level `screen_to_ui`
helper (or `UIHandler.handle_mouse_*`, which already does this) to convert:

    ui_x, ui_y = screen_to_ui(screen_x, screen_y, viewport_height)

Rect struct / SSBO layout
--------------------------
Binding point 3 is reserved for this module's rect buffer (0 = texture slot
table, 1 = lights, 2 = text characters). Each rect is a fixed 96-byte record
made ENTIRELY of scalar float/uint members (no vec2/vec3/vec4 fields), which
means std430 packs it with zero implicit padding -- the same trick the text
module's `CharData` struct uses -- so the Python struct.pack_into layout
below lines up byte-for-byte with the GLSL `UIRect` struct in
`VertexShader.ui_rect_shader` / `FragmentShader.ui_rect_shader`.

Field order (`_UI_STRUCT_FORMAT = '<6f2I16f'`, 96 bytes total):

    0  pos_x            float   UI-space x of the rect's bottom-left corner
    1  pos_y            float   UI-space y of the rect's bottom-left corner
    2  width            float
    3  height           float
    4  z                float   draw-order metadata (see note below)
    5  bevel_thickness  float   pixels; 0 disables the bevel entirely
    6  tex_slot         uint    0xFFFFFFFF (UI_NO_TEXTURE_SLOT) = flat colour
    7  flags            uint    bit0 raised, bit1 sunken, bit2 clip-to-parent
    8  face_r           float   \
    9  face_g           float    | face colour (also the icon tint when textured)
    10 face_b           float    |
    11 face_a           float   /
    12 hi_r             float   \
    13 hi_g             float    | highlight-edge colour (top/left on a raised bevel)
    14 hi_b             float    |
    15 hi_a             float   /
    16 sh_r             float   \
    17 sh_g             float    | shadow-edge colour (bottom/right on a raised bevel)
    18 sh_b             float    |
    19 sh_a             float   /
    20 u0               float   \
    21 v0               float    | UV origin + UV size, same (u, v, uw, vh)
    22 u1               float    | convention as the text shader
    23 v1               float   /

Note on `z` / draw order: the UI render pass runs with depth testing
disabled (overlapping translucent widgets need to blend, not occlude), so
`z` currently has NO effect on what draws on top of what. Front-to-back
stacking is instead achieved by draw order: within one `glDrawElementsInstanced`
call, instance N is rasterized (and blended) after instance N-1, so a widget
"on top" is simply one whose rect lives at a higher index in the layer's
buffer. `UIWidget.raise_to_front()` implements "bring to front" by freeing a
widget's (and its children's) rect indices and re-allocating fresh ones past
the layer's current high-water mark. `z` is still carried all the way to the
vertex shader (as a tiny nudge to `gl_Position.z`) in case a depth-tested UI
pass is ever added later.

Text integration
------------------
Widget captions (`UILabel`, and the caption text owned by `UIButton`,
`UIWindow`'s title, etc.) do not draw their own text -- they are thin
wrappers around the existing text module's public API:
`TextLayer.add_new_paragraph()` and `Paragraph.add_sentence(...)`. Pair a
`UILayer` with a `TextLayer` by passing `text_layer=` to `UILayer(...)` (or
call `ui_layer.set_text_layer(text_layer)` afterwards); every `UILabel`
created on that `UILayer` uses `ui_layer.text_layer` to create its paragraph,
so captions share the same orthographic projection as their rects.

IMPORTANT / KNOWN LIMITATION: the text module is being finished in parallel
with this file. As of this writing `Paragraph._process_packets` (its
internal glyph -> GPU packing step) is a no-op stub, so captions created
through `UILabel` will not yet produce visible glyphs even though the calls
below succeed. Everything here is written strictly against the text module's
public, non-underscored surface (`TextLayer(...)`, `add_new_paragraph()`,
`add_sentence(...)`, and the plain `x`/`y`/`z`/`a` attributes `Sentence`
exposes for positioning) and wrapped in defensive try/except blocks, so
captions should start rendering with no changes needed here once that
pipeline is completed by its owner.

Minimal usage
--------------
    UIHandler._load_ui_handler()
    perspective = glm.ortho(0.0, width, 0.0, height)
    text_layer = TextLayer(perspective)          # optional, for captions
    ui_layer = UILayer(perspective, text_layer=text_layer)

    window = UIWindow(ui_layer, 40, 40, 240, 160, title="My App")
    button = UIButton(ui_layer, 10, 10, 80, 24, caption="OK", parent=window.client_area,
                       on_click=lambda: print("clicked"))
    taskbar = UITaskbar(ui_layer, width)
    taskbar.add_window(window)

    # per frame:
    UIHandler._update(dt)   # ticks widgets (e.g. the taskbar clock) and uploads dirty rects
"""

import ctypes
import struct
import time as _time
from OpenGL.GL import *

from Modular_Overly_Disorienting_Engine.Layer_0_Modules import purpose_text, TextureHandler, UniformHelper, USE_OWN
from Modular_Overly_Disorienting_Engine.Layer_1_Modules.MODEn_Model_Module_Rendering_Branch import Model
from Modular_Overly_Disorienting_Engine.Layer_2_Modules.MODEn_Text_Module_Rendering_Branch import (
    TextHandler, TextLayer, MODE_INSTANT_TEXT, DELAY_NONE, FONT_KEY_DEFAULT,
)

purpose_text("A retro Windows-95-style widget toolkit: bevelled windows, buttons, a taskbar, "
             "a start menu and desktop icons, all backed by one instanced-quad SSBO per layer.")

# --------------------------------------------------------------------------
# Struct / buffer constants
# --------------------------------------------------------------------------
_UI_STRUCT_FORMAT = '<6f2I16f'
_UI_STRUCT_SIZE = struct.calcsize(_UI_STRUCT_FORMAT)  # 96 bytes; see module docstring for field order
_UI_TEX_SLOT_BYTE_OFFSET = 6 * 4  # byte offset of the 'tex_slot' field within one packed rect

UI_NO_TEXTURE_SLOT = 0xFFFFFFFF

FLAG_BEVEL_NONE = 0
FLAG_BEVEL_RAISED = 1 << 0
FLAG_BEVEL_SUNKEN = 1 << 1
FLAG_CLIP_TO_PARENT = 1 << 2  # accepted by widgets and packed into the buffer; the shader does not
                              # yet enforce clipping against a parent's bounds (see report / TODO below)

# The ortho projection uniform every UI shader must declare under this exact name.
UI_PERSPECTIVE_UNIFORM_NAME = "ui_perspective"

# Classic Windows 95 3D-face palette (0..1 floats).
UI_FACE_DEFAULT = (0.75, 0.75, 0.75, 1.0)        # 192,192,192 "3D Face"
UI_HIGHLIGHT_DEFAULT = (1.0, 1.0, 1.0, 1.0)      # 255,255,255 "3D Highlight"
UI_SHADOW_DEFAULT = (0.5, 0.5, 0.5, 1.0)         # 128,128,128 "3D Shadow"
UI_TITLEBAR_ACTIVE = (0.0, 0.0, 0.5, 1.0)        # 0,0,128     "Active Title"
UI_TITLEBAR_TEXT = (1.0, 1.0, 1.0, 1.0)

# Caption defaults. A text size is an em size in the layer's units, and a UI layer is
# built on an orthographic matrix measured in pixels, so these are pixel sizes. The
# text module's own default of 0.05 is meant for world-space text and would come out
# microscopic on a UI layer.
UI_DEFAULT_FONT_KEY = FONT_KEY_DEFAULT
UI_DEFAULT_FONT_SIZE = 13.0

TITLE_BAR_HEIGHT = 20.0
TITLE_BAR_MARGIN = 2.0
CLOSE_BUTTON_SIZE = 16.0
TASKBAR_HEIGHT = 30.0
CLOCK_PANEL_WIDTH = 70.0
DOUBLE_CLICK_INTERVAL = 0.4  # seconds
ICON_DEFAULT_SIZE = 32.0


def lighten_color(rgba, amount=0.5):
    r, g, b, a = rgba
    return (r + (1.0 - r) * amount, g + (1.0 - g) * amount, b + (1.0 - b) * amount, a)


def darken_color(rgba, amount=0.5):
    r, g, b, a = rgba
    return (r * (1.0 - amount), g * (1.0 - amount), b * (1.0 - amount), a)


def screen_to_ui(screen_x, screen_y, viewport_height):
    """Converts a top-left-origin, y-down "screen" coordinate (GLFW's mouse
       convention, and the natural way to describe a Win95-style layout) into
       this module's bottom-left-origin, y-up UI space."""
    return screen_x, viewport_height - screen_y


def caption_width(text, font_key=None, size=None):
    """Measured width of a caption, kerning included."""
    return TextHandler.measure_text(text, font_key or UI_DEFAULT_FONT_KEY,
                                    UI_DEFAULT_FONT_SIZE if size is None else size)


def caption_baseline(height, font_key=None, size=None):
    """Baseline that centres a caption's cap height inside a widget of the given
       height. A sentence's y is its first baseline, not its bottom edge, so this
       has to come off the font's ascender rather than being a fraction of the
       widget height."""
    ascender = TextHandler.get_ascender(font_key or UI_DEFAULT_FONT_KEY,
                                        UI_DEFAULT_FONT_SIZE if size is None else size)
    return max(1.0, (height - ascender) * 0.5)


def _current_clock_string():
    return _time.strftime("%H:%M:%S")


# --------------------------------------------------------------------------
# UIHandler
# --------------------------------------------------------------------------
class UIHandler:
    """Static owner of the shared rect SSBO (mirrors TextHandler)."""

    initialized = False
    UI_BUFFER_BINDING = 3  # binding 0 = texture slots, 1 = lights, 2 = text characters
    ui_shader_storage_buffer = 0
    _max_rects = 4096
    ui_layers = []
    _GLOBAL_UI_QUAD = None

    # Mouse-dispatch state
    _viewport_heights = {}   # window_id -> height; the None key is the fallback/default window
    _captured_widget = None  # the widget that received the last press, until release
    _is_button_down = False

    @staticmethod
    def _load_ui_handler():
        if not UIHandler.initialized:
            UIHandler.ui_shader_storage_buffer = glGenBuffers(1)
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, UIHandler.ui_shader_storage_buffer)
            glBufferData(GL_SHADER_STORAGE_BUFFER, UIHandler._max_rects * _UI_STRUCT_SIZE, None, GL_DYNAMIC_DRAW)
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, UIHandler.UI_BUFFER_BINDING, UIHandler.ui_shader_storage_buffer)

            # Only used for this module's own standalone rendering/tests. The real render
            # pass reuses TextHandler._GLOBAL_TEXT_QUAD's VAO instead (same vertex layout:
            # a single vec3 aPos unit quad spanning 0..1), so either quad works interchangeably.
            UIHandler._GLOBAL_UI_QUAD = Model(None, False, False)
            vertices = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 0.0]
            UIHandler._GLOBAL_UI_QUAD.add_vertices(vertices)
            UIHandler._GLOBAL_UI_QUAD.connect_vertices([0, 1, 2, 2, 3, 0])

            UIHandler.initialized = True
            glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)

    @staticmethod
    def _ensure_capacity(total_rects_needed):
        while total_rects_needed > UIHandler._max_rects:
            UIHandler._double_capacity()

    @staticmethod
    def _double_capacity():
        """Grows the shared SSBO in place, preserving every existing layer's data.
           Layer offsets never move, so this is always safe regardless of how
           many layers exist."""
        old_bytes = UIHandler._max_rects * _UI_STRUCT_SIZE
        new_max = UIHandler._max_rects * 2
        new_bytes = new_max * _UI_STRUCT_SIZE

        new_ssbo = glGenBuffers(1)
        glBindBuffer(GL_COPY_WRITE_BUFFER, new_ssbo)
        glBufferData(GL_COPY_WRITE_BUFFER, new_bytes, None, GL_DYNAMIC_DRAW)
        if UIHandler.ui_shader_storage_buffer:
            glBindBuffer(GL_COPY_READ_BUFFER, UIHandler.ui_shader_storage_buffer)
            glCopyBufferSubData(GL_COPY_READ_BUFFER, GL_COPY_WRITE_BUFFER, 0, 0, old_bytes)
            glBindBuffer(GL_COPY_READ_BUFFER, 0)
        glBindBuffer(GL_COPY_WRITE_BUFFER, 0)

        if UIHandler.ui_shader_storage_buffer:
            glDeleteBuffers(1, [UIHandler.ui_shader_storage_buffer])
        UIHandler.ui_shader_storage_buffer = new_ssbo
        glBindBufferBase(GL_SHADER_STORAGE_BUFFER, UIHandler.UI_BUFFER_BINDING, new_ssbo)
        UIHandler._max_rects = new_max

    @staticmethod
    def _update(dt):
        for layer in UIHandler.ui_layers:
            layer._update_layer(dt)

    # ---- viewport bookkeeping, for the GLFW-y-flip in the mouse handlers below ----
    @staticmethod
    def _window_key(window_id):
        """A dictionary key for a GLFW window.

           The window handle the input module passes along is a ctypes pointer, and
           those are not hashable, so using one as a dict key raised TypeError the
           moment a real mouse event arrived. Its address is stable for the window's
           lifetime and hashes fine."""
        if window_id is None:
            return None
        try:
            return ctypes.cast(window_id, ctypes.c_void_p).value
        except (ctypes.ArgumentError, TypeError):
            try:
                hash(window_id)
            except TypeError:
                return id(window_id)
            return window_id

    @staticmethod
    def set_viewport_size(width, height, window_id=None):
        UIHandler._viewport_heights[UIHandler._window_key(window_id)] = height
        # Also record it as the fallback, so a handler that is handed a window this
        # was never called for still gets a sane height instead of zero.
        UIHandler._viewport_heights.setdefault(None, height)

    @staticmethod
    def _height_for(window_id):
        key = UIHandler._window_key(window_id)
        if key in UIHandler._viewport_heights:
            return UIHandler._viewport_heights[key]
        return UIHandler._viewport_heights.get(None, 0)

    # ---- hit-testing across every layer ----
    @staticmethod
    def _pick_widget(x, y):
        """Topmost hit widget across every layer: later layers, and later
           (higher z-order) widgets/children within a layer, win."""
        for layer in reversed(UIHandler.ui_layers):
            for widget in reversed(layer.top_level_widgets):
                hit = widget.hit_test_topmost(x, y)
                if hit is not None:
                    return hit
        return None

    # ---- registerable straight onto a Mouse's MouseLayout ----
    @staticmethod
    def handle_mouse_press(mouse_x, mouse_y, window_id=None):
        height = UIHandler._height_for(window_id)
        ux, uy = screen_to_ui(mouse_x, mouse_y, height)
        widget = UIHandler._pick_widget(ux, uy)
        UIHandler._captured_widget = widget
        UIHandler._is_button_down = True
        if widget is not None:
            widget.on_press(ux, uy)

    @staticmethod
    def handle_mouse_release(mouse_x, mouse_y, window_id=None):
        height = UIHandler._height_for(window_id)
        ux, uy = screen_to_ui(mouse_x, mouse_y, height)
        UIHandler._is_button_down = False
        widget = UIHandler._captured_widget
        UIHandler._captured_widget = None
        if widget is not None:
            widget.on_release(ux, uy)

    @staticmethod
    def handle_mouse_move(mouse_x, mouse_y, window_id=None, delta_x=None, delta_y=None):
        height = UIHandler._height_for(window_id)
        ux, uy = screen_to_ui(mouse_x, mouse_y, height)
        # y is flipped, so a downward screen delta must flip sign to stay consistent
        # with "up is positive" in UI space.
        dux = delta_x if delta_x is not None else 0.0
        duy = -delta_y if delta_y is not None else 0.0
        if UIHandler._is_button_down and UIHandler._captured_widget is not None:
            UIHandler._captured_widget.on_move(ux, uy, dux, duy)


# --------------------------------------------------------------------------
# UILayer
# --------------------------------------------------------------------------
class UILayer:
    """Owns a contiguous slice of UIHandler's shared rect SSBO plus the CPU-side
       mirror of that slice. Mirrors TextLayer's structure and responsibilities."""

    _total_reserved_rects = 0
    DEFAULT_CAPACITY = 128

    def __init__(self, perspective_matrix, capacity=DEFAULT_CAPACITY, text_layer=None):
        self.layer_index = len(UIHandler.ui_layers)
        self.buffer_offset = UILayer._total_reserved_rects
        self.capacity = capacity
        UILayer._total_reserved_rects += capacity
        UIHandler._ensure_capacity(UILayer._total_reserved_rects)

        self.cpu_buffer = bytearray(self.capacity * _UI_STRUCT_SIZE)
        self._rect_count = 0        # high-water mark of used indices; 0 when empty
        self._free_indices = []
        self._dirty_range = None    # [start, end) local indices pending a glBufferSubData, or None
        self._tickable = []

        self.top_level_widgets = []
        self.text_layer = text_layer

        UIHandler.ui_layers.append(self)

        self._uniform_helper = UniformHelper()
        self._uniform_helper._set_uniforms(UI_PERSPECTIVE_UNIFORM_NAME, perspective_matrix)

    def set_text_layer(self, text_layer):
        """Pairs (or re-pairs) this layer with a TextLayer so UILabels created
           on it use that TextLayer's paragraphs for captions."""
        self.text_layer = text_layer

    # ---- contract the renderer is written against ----
    def get_rect_count(self):
        return self._rect_count

    def get_used_texture_slots(self):
        slots = set()
        for i in range(self._rect_count):
            tex_slot = struct.unpack_from('<I', self.cpu_buffer, i * _UI_STRUCT_SIZE + _UI_TEX_SLOT_BYTE_OFFSET)[0]
            if tex_slot != UI_NO_TEXTURE_SLOT:
                slots.add(tex_slot)
        return list(slots)

    def get_uniforms(self, names):
        return self._uniform_helper._get_uniforms(names)

    def set_ui_perspective_matrix(self, matrix):
        self._uniform_helper._set_uniforms(UI_PERSPECTIVE_UNIFORM_NAME, matrix)

    def rebuild(self):
        """Uploads whatever range of rects has changed since the last call."""
        if self._dirty_range is None:
            return
        start, end = self._dirty_range
        self._dirty_range = None
        start = max(0, start)
        end = min(self._rect_count, end)
        if end <= start:
            return
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, UIHandler.ui_shader_storage_buffer)
        byte_offset = (self.buffer_offset + start) * _UI_STRUCT_SIZE
        raw = bytes(self.cpu_buffer[start * _UI_STRUCT_SIZE:end * _UI_STRUCT_SIZE])
        glBufferSubData(GL_SHADER_STORAGE_BUFFER, byte_offset, len(raw), raw)
        glBindBuffer(GL_SHADER_STORAGE_BUFFER, 0)

    # ---- rect (de)allocation ----
    def allocate_rect(self, force_new=False):
        """Reserves a rect slot and returns its LOCAL index (0-based within this
           layer; the renderer adds `buffer_offset`). `force_new=True` skips the
           free list and always returns a fresh, strictly-higher index -- used by
           raise_to_front() to push a widget's draw order past everything else."""
        if not force_new and self._free_indices:
            return self._free_indices.pop()
        if self._rect_count >= self.capacity:
            self._grow(max(self.capacity * 2, self._rect_count + 1))
        idx = self._rect_count
        self._rect_count += 1
        return idx

    def free_rect(self, local_index):
        struct.pack_into(_UI_STRUCT_FORMAT, self.cpu_buffer, local_index * _UI_STRUCT_SIZE,
                          0.0, 0.0, 0.0, 0.0, 0.0, 0.0, UI_NO_TEXTURE_SLOT, 0,
                          *([0.0] * 16))
        self._mark_dirty(local_index, local_index + 1)
        if local_index == self._rect_count - 1:
            # Freed the trailing rect: shrink the high-water mark immediately
            # (and cascade through any previously-freed rects this exposes)
            # so a fully torn-down layer correctly reports 0 rects again.
            self._rect_count -= 1
            while self._rect_count > 0 and (self._rect_count - 1) in self._free_indices:
                self._free_indices.remove(self._rect_count - 1)
                self._rect_count -= 1
        else:
            self._free_indices.append(local_index)

    def write_rect(self, local_index, x, y, width, height, z, bevel, tex_slot, flags,
                   face_r, face_g, face_b, face_a,
                   hi_r, hi_g, hi_b, hi_a,
                   sh_r, sh_g, sh_b, sh_a,
                   u0, v0, u1, v1):
        struct.pack_into(_UI_STRUCT_FORMAT, self.cpu_buffer, local_index * _UI_STRUCT_SIZE,
                          x, y, width, height, z, bevel,
                          int(tex_slot) & 0xFFFFFFFF, int(flags) & 0xFFFFFFFF,
                          face_r, face_g, face_b, face_a,
                          hi_r, hi_g, hi_b, hi_a,
                          sh_r, sh_g, sh_b, sh_a,
                          u0, v0, u1, v1)
        self._mark_dirty(local_index, local_index + 1)

    def _mark_dirty(self, start, end):
        if self._dirty_range is None:
            self._dirty_range = [start, end]
        else:
            self._dirty_range[0] = min(self._dirty_range[0], start)
            self._dirty_range[1] = max(self._dirty_range[1], end)

    def _grow(self, new_capacity):
        # Safe only when nothing has been reserved after this layer in the global
        # buffer yet -- otherwise growing in place would overwrite the next
        # layer's region. (The text module has the identical limitation.)
        is_last_layer = (self.buffer_offset + self.capacity) == UILayer._total_reserved_rects
        if not is_last_layer:
            raise RuntimeError(
                "UILayer exhausted its reserved rect capacity and is not the most "
                "recently created UILayer, so it cannot grow in place without "
                "overwriting another layer's region of the shared SSBO. Construct "
                "this UILayer with a larger 'capacity' argument up front."
            )
        added = new_capacity - self.capacity
        UILayer._total_reserved_rects += added
        UIHandler._ensure_capacity(UILayer._total_reserved_rects)
        new_buffer = bytearray(new_capacity * _UI_STRUCT_SIZE)
        new_buffer[:len(self.cpu_buffer)] = self.cpu_buffer
        self.cpu_buffer = new_buffer
        self.capacity = new_capacity

    # ---- per-frame ticking (e.g. the taskbar clock) ----
    def register_tickable(self, obj):
        self._tickable.append(obj)

    def unregister_tickable(self, obj):
        if obj in self._tickable:
            self._tickable.remove(obj)

    def _update_layer(self, dt):
        for obj in self._tickable:
            obj.update(dt)
        self.rebuild()


# --------------------------------------------------------------------------
# UIWidget
# --------------------------------------------------------------------------
class UIWidget:
    """Base widget: an optional rect in a UILayer's slice of the shared SSBO,
       plus position/size/visibility/parent-child bookkeeping, hit-testing and
       the press/release/move input hooks every widget can override."""

    def __init__(self, layer, x=0.0, y=0.0, width=10.0, height=10.0, z=0.0, parent=None,
                 face=UI_FACE_DEFAULT, highlight=UI_HIGHLIGHT_DEFAULT, shadow=UI_SHADOW_DEFAULT,
                 bevel=0.0, bevel_mode=FLAG_BEVEL_NONE, tex_slot=UI_NO_TEXTURE_SLOT, uv=(0.0, 0.0, 1.0, 1.0),
                 visible=True, has_own_rect=True, clip_to_parent=False, raise_target=None):
        self.layer = layer
        self.x = float(x)
        self.y = float(y)
        self.width = float(width)
        self.height = float(height)
        self.z = float(z)
        self.face = list(face)
        self.highlight = list(highlight)
        self.shadow = list(shadow)
        self.bevel = float(bevel)
        self.bevel_mode = bevel_mode
        self.tex_slot = tex_slot
        self.uv = tuple(uv)
        self.visible = visible
        self.clip_to_parent = clip_to_parent
        # A widget whose press should also bring some OTHER widget (usually its
        # owning window) to the front -- e.g. a window's title bar or client area.
        self.raise_target = raise_target

        self.parent = parent
        self.children = []

        self._rect_index = layer.allocate_rect() if has_own_rect else None

        if parent is not None:
            parent.children.append(self)
        else:
            layer.top_level_widgets.append(self)

        self._rebuild()

    # ---- tree / geometry ----
    def is_effectively_visible(self):
        if not self.visible:
            return False
        if self.parent is not None:
            return self.parent.is_effectively_visible()
        return True

    def get_absolute_position(self):
        if self.parent is not None:
            pax, pay = self.parent.get_absolute_position()
            return pax + self.x, pay + self.y
        return self.x, self.y

    def hit_test(self, x, y):
        """Point-in-rect test in absolute UI space. Always false while hidden."""
        if not self.visible:
            return False
        ax, ay = self.get_absolute_position()
        return (ax <= x <= ax + self.width) and (ay <= y <= ay + self.height)

    def hit_test_topmost(self, x, y):
        """Returns the topmost (self or descendant) widget hit at (x, y),
           respecting child z-order (later children are on top), or None."""
        if not self.visible:
            return None
        for child in reversed(self.children):
            hit = child.hit_test_topmost(x, y)
            if hit is not None:
                return hit
        return self if self.hit_test(x, y) else None

    def set_position(self, x, y):
        self.x = float(x)
        self.y = float(y)
        self._rebuild_recursive()

    def set_size(self, width, height):
        self.width = float(width)
        self.height = float(height)
        self._rebuild()

    def set_visible(self, visible):
        self.visible = visible
        self._rebuild_recursive()

    def _rebuild_recursive(self):
        self._rebuild()
        for child in self.children:
            child._rebuild_recursive()

    # ---- GPU rect sync ----
    def _rebuild(self):
        if self._rect_index is None:
            return
        ax, ay = self.get_absolute_position()
        visible = self.is_effectively_visible()
        w = self.width if visible else 0.0
        h = self.height if visible else 0.0
        face = self.face if visible else (0.0, 0.0, 0.0, 0.0)
        flags = self.bevel_mode | (FLAG_CLIP_TO_PARENT if self.clip_to_parent else 0)
        self.layer.write_rect(
            self._rect_index, ax, ay, w, h, self.z, self.bevel,
            self.tex_slot, flags,
            face[0], face[1], face[2], face[3],
            self.highlight[0], self.highlight[1], self.highlight[2], self.highlight[3],
            self.shadow[0], self.shadow[1], self.shadow[2], self.shadow[3],
            self.uv[0], self.uv[1], self.uv[2], self.uv[3],
        )

    # ---- z-order ----
    def raise_to_front(self):
        """Moves this widget to the end of its sibling list and re-allocates
           its (and its descendants') rects past the layer's current
           high-water mark, so they draw last -- i.e. on top -- next frame."""
        owner_list = self.parent.children if self.parent is not None else self.layer.top_level_widgets
        if self in owner_list:
            owner_list.remove(self)
            owner_list.append(self)
        self._reallocate_to_front()

    def _reallocate_to_front(self):
        if self._rect_index is not None:
            self.layer.free_rect(self._rect_index)
            self._rect_index = self.layer.allocate_rect(force_new=True)
        for child in self.children:
            child._reallocate_to_front()
        self._rebuild()

    # ---- lifecycle ----
    def destroy(self):
        for child in list(self.children):
            child.destroy()
        self.children.clear()
        if self._rect_index is not None:
            self.layer.free_rect(self._rect_index)
            self._rect_index = None
        if self.parent is not None:
            if self in self.parent.children:
                self.parent.children.remove(self)
        else:
            if self in self.layer.top_level_widgets:
                self.layer.top_level_widgets.remove(self)

    # ---- input hooks; override in subclasses ----
    def on_press(self, x, y):
        if self.raise_target is not None:
            self.raise_target.raise_to_front()

    def on_release(self, x, y):
        pass

    def on_move(self, x, y, dx, dy):
        pass


# --------------------------------------------------------------------------
# UILabel
# --------------------------------------------------------------------------
class UILabel(UIWidget):
    """A text caption positioned in UI space. Owns no rect of its own; it is a
       thin wrapper around the paired TextLayer's paragraph/sentence API (see
       the "Text integration" section of the module docstring for the current
       limitation around glyph packing not being finished yet)."""

    def __init__(self, layer, x, y, text="", font_key=None, size=None, color=(0.0, 0.0, 0.0, 1.0),
                 parent=None, z=0.0):
        self._paragraph = None
        self._sentence = None
        self.font_key = font_key if font_key is not None else UI_DEFAULT_FONT_KEY
        self.size = UI_DEFAULT_FONT_SIZE if size is None else size
        self.color = list(color)
        self.text_layer = layer.text_layer
        super().__init__(layer, x, y, width=0.0, height=0.0, z=z, parent=parent, has_own_rect=False)
        self._text = ""
        if self.text_layer is not None:
            try:
                self._paragraph = self.text_layer.add_new_paragraph()
            except Exception as exc:
                print(f"UILabel: could not create a paragraph on the paired TextLayer ({exc}); "
                      f"caption '{text}' will not render.")
        if text:
            self.set_text(text)

    def set_text(self, text):
        self._text = text
        if self._paragraph is None:
            return
        try:
            # A label owns exactly one sentence, so replacing its text means clearing
            # the paragraph rather than appending another sentence to it.
            if self._sentence is not None:
                self._sentence.set_text(text, font_key=self.font_key, size=self.size,
                                        r=self.color[0], g=self.color[1], b=self.color[2],
                                        a=self.color[3], mode=MODE_INSTANT_TEXT)
            else:
                self._sentence = self._paragraph.add_sentence(
                    text, font_key=self.font_key, size=self.size,
                    r=self.color[0], g=self.color[1], b=self.color[2], a=self.color[3],
                    mode=MODE_INSTANT_TEXT, delay_mode=DELAY_NONE)
            self._apply_position()
        except Exception as exc:
            # Defensive: the text module is WIP and its call signature may still shift.
            print(f"UILabel.set_text: text module call failed defensively ({exc})")

    def _apply_position(self):
        if self._sentence is None:
            return
        ax, ay = self.get_absolute_position()
        try:
            # Go through set_position rather than assigning x/y, because the glyphs are
            # already packed in the GPU buffer with their absolute positions baked in:
            # writing the attribute alone would move the sentence on the CPU only, and
            # a dragged window's title would stay behind.
            self._sentence.set_position(ax, ay, self.z)
        except Exception:
            pass

    def _apply_visibility(self):
        if self._sentence is None:
            return
        target_alpha = self.color[3] if self.is_effectively_visible() else 0.0
        try:
            # Same reasoning as the position: alpha lives in the packed struct, so it
            # has to be set through the call that patches the buffer.
            self._sentence.set_colour(a=target_alpha)
        except Exception:
            pass

    def _rebuild(self):
        # No rect of our own: keep the underlying sentence's position/visibility
        # in sync instead.
        self._apply_position()
        self._apply_visibility()

    def destroy(self):
        """Takes the caption's glyphs down with the widget.

           A label's pixels live in the text layer's buffer, not in a rect, so the base
           class's rect bookkeeping does not touch them. Without this, closing a window
           left its title and its buttons' captions painted on the desktop."""
        if self._paragraph is not None and self.text_layer is not None:
            try:
                self.text_layer.remove_paragraph(self._paragraph)
            except Exception as exc:
                print(f"UILabel.destroy: could not release the caption's paragraph ({exc})")
            self._paragraph = None
            self._sentence = None
        super().destroy()


# --------------------------------------------------------------------------
# UIButton
# --------------------------------------------------------------------------
class UIButton(UIWidget):
    """A bevelled push button: raised normally, sunken while pressed, fires
       `on_click` on release if the cursor is still over it."""

    def __init__(self, layer, x, y, width, height, caption="", z=0.0, parent=None,
                 face=UI_FACE_DEFAULT, on_click=None, text_color=(0.0, 0.0, 0.0, 1.0),
                 raise_target=None):
        super().__init__(layer, x, y, width, height, z=z, parent=parent,
                          face=face, highlight=UI_HIGHLIGHT_DEFAULT, shadow=UI_SHADOW_DEFAULT,
                          bevel=2.0, bevel_mode=FLAG_BEVEL_RAISED, raise_target=raise_target)
        self.on_click = on_click
        self._pressed = False
        self.label = None
        if caption:
            label_x = max(2.0, (width - caption_width(caption)) * 0.5)
            self.label = UILabel(layer, label_x, caption_baseline(height), caption,
                                 parent=self, color=text_color)

    def on_press(self, x, y):
        super().on_press(x, y)
        self._pressed = True
        self.bevel_mode = FLAG_BEVEL_SUNKEN
        self._rebuild()

    def on_release(self, x, y):
        was_pressed = self._pressed
        self._pressed = False
        self.bevel_mode = FLAG_BEVEL_RAISED
        self._rebuild()
        if was_pressed and self.hit_test(x, y) and callable(self.on_click):
            self.on_click()


def size_to_px(size):
    """Kept for compatibility. A text size already is a pixel em size on a UI layer,
       so this is the identity; use caption_width for anything that needs a real
       measurement."""
    return size


# --------------------------------------------------------------------------
# UIWindow
# --------------------------------------------------------------------------
class _TitleBar(UIWidget):
    """Internal: the draggable strip of a UIWindow. Kept as its own widget
       (rather than special-casing UIWindow's own hit_test) so the close
       button, which is a sibling-ish child sitting on top of it, naturally
       takes priority during hit-testing."""

    def __init__(self, window, layer, x, y, width, height, **kwargs):
        self.window = window
        kwargs.setdefault("raise_target", window)
        super().__init__(layer, x, y, width, height, parent=window, **kwargs)

    def on_press(self, x, y):
        super().on_press(x, y)
        self.window._dragging = True
        self.window._drag_offset = (x - self.window.x, y - self.window.y)

    def on_move(self, x, y, dx, dy):
        if self.window._dragging:
            self.window.set_position(x - self.window._drag_offset[0], y - self.window._drag_offset[1])

    def on_release(self, x, y):
        self.window._dragging = False


class UIWindow(UIWidget):
    """A bevelled frame with a draggable title bar (caption + close button)
       and an optional sunken client area. Raises itself to the front of its
       layer whenever any part of it is pressed."""

    def __init__(self, layer, x, y, width, height, title="Window", z=0.0,
                 has_client_area=True, on_close=None):
        super().__init__(layer, x, y, width, height, z=z, parent=None,
                          face=UI_FACE_DEFAULT, highlight=UI_HIGHLIGHT_DEFAULT, shadow=UI_SHADOW_DEFAULT,
                          bevel=2.0, bevel_mode=FLAG_BEVEL_RAISED)
        self.title = title
        self.on_close = on_close
        self._dragging = False
        self._drag_offset = (0.0, 0.0)

        title_bar_width = width - 2 * TITLE_BAR_MARGIN
        title_bar_y = height - TITLE_BAR_HEIGHT - TITLE_BAR_MARGIN
        self.title_bar = _TitleBar(self, layer, TITLE_BAR_MARGIN, title_bar_y, title_bar_width, TITLE_BAR_HEIGHT,
                                    face=UI_TITLEBAR_ACTIVE, highlight=UI_TITLEBAR_ACTIVE, shadow=UI_TITLEBAR_ACTIVE,
                                    bevel=0.0, bevel_mode=FLAG_BEVEL_NONE)

        self.title_label = UILabel(layer, 4.0, caption_baseline(TITLE_BAR_HEIGHT), title,
                                    parent=self.title_bar, color=UI_TITLEBAR_TEXT)

        close_x = title_bar_width - CLOSE_BUTTON_SIZE - 3.0
        close_y = (TITLE_BAR_HEIGHT - CLOSE_BUTTON_SIZE) * 0.5
        self.close_button = UIButton(layer, close_x, close_y, CLOSE_BUTTON_SIZE, CLOSE_BUTTON_SIZE,
                                      caption="X", parent=self.title_bar, on_click=self.close,
                                      raise_target=self)

        self.client_area = None
        if has_client_area:
            client_height = max(0.0, title_bar_y - TITLE_BAR_MARGIN)
            self.client_area = UIWidget(layer, TITLE_BAR_MARGIN, TITLE_BAR_MARGIN,
                                         width - 2 * TITLE_BAR_MARGIN, client_height,
                                         parent=self, raise_target=self,
                                         face=UI_FACE_DEFAULT, highlight=UI_HIGHLIGHT_DEFAULT, shadow=UI_SHADOW_DEFAULT,
                                         bevel=2.0, bevel_mode=FLAG_BEVEL_SUNKEN)

    def on_press(self, x, y):
        # Any press on the plain frame (not already claimed by a child) raises the window.
        self.raise_to_front()

    def close(self):
        self.destroy()
        if callable(self.on_close):
            self.on_close(self)


# --------------------------------------------------------------------------
# UITaskbar
# --------------------------------------------------------------------------
class UITaskbar(UIWidget):
    """A strip along the bottom of the screen: a Start button, one button per
       tracked open window, and a sunken clock panel on the right."""

    def __init__(self, layer, screen_width, z=100.0, on_start_click=None):
        super().__init__(layer, 0.0, 0.0, screen_width, TASKBAR_HEIGHT, z=z, parent=None,
                          face=UI_FACE_DEFAULT, highlight=UI_HIGHLIGHT_DEFAULT, shadow=UI_SHADOW_DEFAULT,
                          bevel=2.0, bevel_mode=FLAG_BEVEL_RAISED)
        layer.register_tickable(self)
        self._clock_timer = 0.0

        self.start_button = UIButton(layer, 3.0, 3.0, 60.0, TASKBAR_HEIGHT - 6.0, caption="Start",
                                      parent=self, on_click=on_start_click)

        clock_x = screen_width - CLOCK_PANEL_WIDTH - 3.0
        self.clock_panel = UIWidget(layer, clock_x, 3.0, CLOCK_PANEL_WIDTH, TASKBAR_HEIGHT - 6.0,
                                     parent=self, face=UI_FACE_DEFAULT, highlight=UI_HIGHLIGHT_DEFAULT,
                                     shadow=UI_SHADOW_DEFAULT, bevel=2.0, bevel_mode=FLAG_BEVEL_SUNKEN)
        clock_text = _current_clock_string()
        self.clock_label = UILabel(layer,
                                   max(2.0, (CLOCK_PANEL_WIDTH - caption_width(clock_text)) * 0.5),
                                   caption_baseline(TASKBAR_HEIGHT - 6.0), clock_text,
                                   parent=self.clock_panel)

        self._window_buttons = {}
        self._next_window_button_x = 70.0

    def update(self, dt):
        self._clock_timer += dt
        if self._clock_timer >= 1.0:
            self._clock_timer = 0.0
            self.clock_label.set_text(_current_clock_string())

    def add_window(self, window):
        """Creates a taskbar button that raises `window`, and automatically
           removes that button when the window closes."""
        button_width = 120.0
        button = UIButton(self.layer, self._next_window_button_x, 3.0, button_width, TASKBAR_HEIGHT - 6.0,
                           caption=window.title, parent=self, on_click=window.raise_to_front)
        self._next_window_button_x += button_width + 2.0
        self._window_buttons[window] = button

        previous_on_close = window.on_close

        def _wrapped_close(closed_window, _previous=previous_on_close):
            self._remove_window_button(closed_window)
            if callable(_previous):
                _previous(closed_window)

        window.on_close = _wrapped_close

    def _remove_window_button(self, window):
        button = self._window_buttons.pop(window, None)
        if button is not None:
            button.destroy()


# --------------------------------------------------------------------------
# UIStartMenu
# --------------------------------------------------------------------------
class UIStartMenu(UIWidget):
    """A vertical list of clickable entries, toggled by (typically) a
       taskbar's Start button. Hidden by default."""

    ENTRY_HEIGHT = 22.0

    def __init__(self, layer, x, y, width=160.0, z=110.0):
        super().__init__(layer, x, y, width, UIStartMenu.ENTRY_HEIGHT, z=z, parent=None,
                          face=UI_FACE_DEFAULT, highlight=UI_HIGHLIGHT_DEFAULT, shadow=UI_SHADOW_DEFAULT,
                          bevel=2.0, bevel_mode=FLAG_BEVEL_RAISED, visible=False)
        self._entries = []

    def add_entry(self, label, callback):
        entry = UIButton(self.layer, 2.0, 0.0, self.width - 4.0, UIStartMenu.ENTRY_HEIGHT - 2.0,
                          caption=label, parent=self, on_click=self._wrap_entry_callback(callback))
        self._entries.append(entry)
        self._resize_to_entries()
        self._reposition_entries()
        return entry

    def _wrap_entry_callback(self, callback):
        def _runner():
            if callable(callback):
                callback()
            self.hide()
        return _runner

    def _resize_to_entries(self):
        self.height = max(UIStartMenu.ENTRY_HEIGHT, len(self._entries) * UIStartMenu.ENTRY_HEIGHT)
        self._rebuild()

    def _reposition_entries(self):
        for index, entry in enumerate(self._entries):
            entry_y = self.height - (index + 1) * UIStartMenu.ENTRY_HEIGHT
            entry.set_position(2.0, entry_y + 1.0)

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def show(self):
        self.set_visible(True)
        self.raise_to_front()

    def hide(self):
        self.set_visible(False)


# --------------------------------------------------------------------------
# UIDesktopIcon
# --------------------------------------------------------------------------
class UIDesktopIcon(UIWidget):
    """A small icon + label on the desktop. Selectable (press toggles
       selection, shown as a sunken outline); double-click invokes
       `on_activate`."""

    def __init__(self, layer, x, y, label="Icon", tex_slot=UI_NO_TEXTURE_SLOT, size=ICON_DEFAULT_SIZE,
                 on_activate=None, z=1.0):
        icon_face = (1.0, 1.0, 1.0, 1.0) if tex_slot != UI_NO_TEXTURE_SLOT else UI_FACE_DEFAULT
        super().__init__(layer, x, y, size, size, z=z, parent=None,
                          face=icon_face, highlight=UI_HIGHLIGHT_DEFAULT, shadow=UI_SHADOW_DEFAULT,
                          bevel=2.0, bevel_mode=FLAG_BEVEL_NONE, tex_slot=tex_slot)
        self.on_activate = on_activate
        self.selected = False
        self._last_press_time = -1.0
        # Centre the caption under the icon; the label's x is relative to the icon.
        self.label = UILabel(layer, (size - caption_width(label)) * 0.5, -16.0, label, parent=self)

    def set_selected(self, selected):
        self.selected = selected
        self.bevel_mode = FLAG_BEVEL_SUNKEN if selected else FLAG_BEVEL_NONE
        self._rebuild()

    def on_press(self, x, y):
        super().on_press(x, y)
        now = _time.time()
        is_double_click = self._last_press_time >= 0.0 and (now - self._last_press_time) <= DOUBLE_CLICK_INTERVAL
        self._last_press_time = now
        self.set_selected(True)
        if is_double_click and callable(self.on_activate):
            self.on_activate()
