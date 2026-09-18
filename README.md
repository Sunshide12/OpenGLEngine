# Modular Overly Disorienting Engine

A Python/OpenGL rendering engine (`Modular_Overly_Disorienting_Engine`), driven through
GLFW, PyOpenGL, pyglm, Pillow and NumPy.

## Requirements

- Ubuntu 22.04 (or similar Linux with X11 and Mesa).
- Python 3.11+ (the repo's committed `__pycache__` files were built against 3.11, 3.13
  and 3.14; any of those, or a nearby version, will do — nothing in the source uses
  version-specific syntax beyond `match`/structural typing, which needs Python 3.10+).
- An OpenGL 4.3 core-profile context. The bundled shaders are written as
  `#version 430 core`, and the window is created requesting a 4.3 core, forward-compatible
  context (see `WindowStartupSettings.starting_creation_flags` in
  `Modular_Overly_Disorienting_Engine/Layer_0_Modules/MODEn_Settings_Module_Rendering_Branch.py`).
  This runs on Mesa's `iris` driver (e.g. Intel UHD Graphics 730) and on Mesa's `llvmpipe`
  software renderer alike.
- **The engine no longer requires `GL_ARB_bindless_texture`.** It used to target bindless
  texture handles, which many Mesa drivers (including `iris` and `llvmpipe`) do not expose.
  Textures are now identified by a "slot" integer that shaders resolve through a
  slot-to-texture-unit table (see `TextureHandler` in
  `Modular_Overly_Disorienting_Engine/Layer_0_Modules/MODEn_Texture_Module_Rendering_Branch.py`),
  bound to real texture units at draw time.

## System packages (Ubuntu 22.04)

The `glfw` PyPI wheel bundles its own copy of the GLFW shared library, so `libglfw3` does
not need to be installed separately. You still need the underlying GL/X11 runtime
libraries that GLFW and Mesa link against:

```bash
sudo apt update
sudo apt install -y \
    libgl1 libglx0 libegl1 \
    libx11-6 libxrandr2 libxinerama1 libxcursor1 libxi6 libxext6 \
    mesa-utils
```

(`mesa-utils` is optional — it provides `glxinfo`, useful for confirming the driver and
OpenGL version Mesa reports on the target machine.)

## Python setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

There is no packaged entry point yet; the engine is imported as a library and driven by
a script that builds a window, camera and scene.

### `engine testing.py`

`engine testing.py` (in the repo root) is the existing example of wiring the engine
together — creating a window, a camera, shaders, a scene and a textured cube. It is
being developed in parallel with this cleanup, so its exact shape is not documented
here; read the script itself for the current example. Run it with:

```bash
python3 "engine testing.py"
```

On a machine with no display attached, run it (or any other engine script) under a
virtual X server, e.g. `xvfb-run -a python3 "engine testing.py"`.
