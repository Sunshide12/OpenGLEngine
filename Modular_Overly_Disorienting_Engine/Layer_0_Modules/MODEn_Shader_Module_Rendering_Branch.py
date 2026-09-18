from Modular_Overly_Disorienting_Engine.Layer_0_Modules import purpose_text, TextureHandler
from OpenGL.GL import *
from pyglm import glm
import numpy as np
import re

purpose_text(
    "Handles the creation, manipulation and linking of shaders. Also contains the source code for built-in shaders")

# Paterns for recognizing what shaders needs/outputs what
attribute_pattern = re.compile(r'layout\s*\(\s*location\s*=\s*(\d+)\s*\)\s*in\s+(\w+)\s+(\w+)\s*;')
uniform_pattern = re.compile(r'uniform\s+(\w+)\s+(\w+)\s*;')
out_pattern = re.compile(r'out\s+(\w+)\s+(\w+)\s*;')
struct_pattern = re.compile(
    r'struct\s+(\w+)\s*\{([^}]*)\};',
    re.DOTALL
)

member_pattern = re.compile(
    r'\s*(\w+)\s+(\w+)\s*;'
)


def parse_structs(shader_code: str):
    structs = {}

    for struct_name, body in struct_pattern.findall(shader_code):
        members = member_pattern.findall(body)
        structs[struct_name] = members

    return structs


def get_shader_data(shader_code: str, get_only_names=True):
    attributes = attribute_pattern.findall(shader_code)
    uniforms = uniform_pattern.findall(shader_code)
    outputs = out_pattern.findall(shader_code)

    structs = parse_structs(shader_code)

    needed_attributes = []
    needed_uniforms = []
    given_outputs = []

    # Attributes
    for location, dtype, name in attributes:
        if get_only_names:
            needed_attributes.append(name)
        else:
            needed_attributes.append([location, dtype, name])

    # Uniforms (EXPAND STRUCTS)
    for dtype, name in uniforms:
        if dtype in structs:
            # Expand struct members
            for member_type, member_name in structs[dtype]:
                full_name = f"{name}.{member_name}"
                if get_only_names:
                    needed_uniforms.append(full_name)
                else:
                    needed_uniforms.append(["uniform", member_type, full_name])
        else:
            if get_only_names:
                needed_uniforms.append(name)
            else:
                needed_uniforms.append(["uniform", dtype, name])

    # Outputs
    for dtype, name in outputs:
        given_outputs.append([dtype, name])

    return needed_attributes, needed_uniforms, given_outputs

    # for dtype, name in uniforms:
    #     if get_only_names:
    #         needed_uniforms.append(name)
    #     else:
    #         needed_uniforms.append(["uninform", dtype, name])
    # for dtype, name in outputs:
    #     given_outputs.append([dtype, name])
    # return needed_attributes,needed_uniforms,given_outputs


def help_shader(shader_code: str):
    return get_shader_data(shader_code)
class VertexShader:
    #TODO pass window size to this in order to make text perfectly scaling
    # ALSO, MAYBE AGG GLMEMORYBARRIER TO MAKE SURE RENDERING WORKS MID POSITION CHANGE
    world_text_shader = """#version 430 core
#extension GL_ARB_bindless_texture : require

layout(location = 0) in vec3 aPos;

struct CharData {
    // --- Integers (3 slots / 12 bytes) ---
    uint h_low;             // 0
    uint h_high;            // 1
    uint use_center_pivot;  // 2

    // --- Floats (29 slots / 116 bytes) ---
    float gx, gy, gw, gh;   // 3, 4, 5, 6
    float u, v, uw, vh;     // 7, 8, 9, 10
    float reveal_id;        // 11
    float word_id;          // 12
    float abs_z;            // 13
    float pitch, yaw, roll; // 14, 15, 16
    float r, g, b, a;       // 17, 18, 19, 20
    float pcx, pcy, pcz;    // 21, 22, 23
    
    float padding[8];       // 24, 25, 26, 27, 28, 29, 30, 31 (The fillers)
};

layout(std430, binding = 2) buffer TextBuffer {
    CharData characters[];
};

uniform mat4 text_perspective;
uniform mat4 view_matrix;
uniform int u_buffer_offset;

out vec2 TexCoords;
out vec4 vColor;
flat out uvec2 FontHandle;

mat3 getRotationMatrix(vec3 degrees) {
    vec3 rad = radians(degrees);
    vec3 s = sin(rad);
    vec3 c = cos(rad);
    // Correct Column-Major rotation matrices
    mat3 rotX = mat3(1, 0, 0, 0, c.x, s.x, 0, -s.x, c.x);
    mat3 rotY = mat3(c.y, 0, -s.y, 0, 1, 0, s.y, 0, c.y);
    mat3 rotZ = mat3(c.z, s.z, 0, -s.z, c.z, 0, 0, 0, 1);
    return rotZ * rotY * rotX;
}

void main() {
    uint index = gl_InstanceID + u_buffer_offset;
    CharData data = characters[index];

    vec2 rect_pos = vec2(data.gx, data.gy);
    vec2 rect_size = vec2(data.gw, data.gh);
    
    // Calculate world position
    vec3 vertex_world_home = vec3(rect_pos + (aPos.xy * rect_size), data.abs_z);
    vec3 local_center = vec3(rect_pos + (rect_size * 0.5), data.abs_z);
    vec3 para_center = vec3(data.pcx, data.pcy, data.pcz);

    vec3 pivot = (data.use_center_pivot == 1) ? para_center : local_center;

    mat3 rotMat = getRotationMatrix(vec3(data.pitch, data.yaw, data.roll));
    vec3 final_pos = pivot + (rotMat * (vertex_world_home - pivot));

    gl_Position = text_perspective * view_matrix * vec4(final_pos, 1.0);

    TexCoords = aPos.xy * vec2(data.uw, data.vh) + vec2(data.u, data.v);
    FontHandle = uvec2(data.h_low, data.h_high);
    vColor = vec4(data.r, data.g, data.b, data.a);
}
    """
    ui_text_shader = """
#version 430 core
#extension GL_ARB_bindless_texture : require

layout(location = 0) in vec3 aPos;

struct CharData {
    // --- Integers (3 slots / 12 bytes) ---
    uint h_low;             // 0
    uint h_high;            // 1
    uint use_center_pivot;  // 2

    // --- Floats (29 slots / 116 bytes) ---
    float gx, gy, gw, gh;   // 3, 4, 5, 6
    float u, v, uw, vh;     // 7, 8, 9, 10
    float reveal_id;        // 11
    float word_id;          // 12
    float abs_z;            // 13
    float pitch, yaw, roll; // 14, 15, 16
    float r, g, b, a;       // 17, 18, 19, 20
    float pcx, pcy, pcz;    // 21, 22, 23
    
    float padding[8];       // 24, 25, 26, 27, 28, 29, 30, 31 (The fillers)
};

layout(std430, binding = 2) buffer TextBuffer {
    CharData characters[];
};

uniform mat4 text_perspective; // Usually an Orthographic projection for UI
uniform int u_buffer_offset;

out vec2 TexCoords;
out vec4 vColor;
flat out uvec2 FontHandle;

mat3 getRotationMatrix(vec3 degrees) {
    vec3 rad = radians(degrees);
    vec3 s = sin(rad);
    vec3 c = cos(rad);
    // Column-major matrices
    mat3 rotX = mat3(1, 0, 0, 0, c.x, s.x, 0, -s.x, c.x);
    mat3 rotY = mat3(c.y, 0, -s.y, 0, 1, 0, s.y, 0, c.y);
    mat3 rotZ = mat3(c.z, s.z, 0, -s.z, c.z, 0, 0, 0, 1);
    return rotZ * rotY * rotX;
}

void main() {
    uint index = gl_InstanceID + u_buffer_offset;
    CharData data = characters[index];

    vec2 rect_pos = vec2(data.gx, data.gy);
    vec2 rect_size = vec2(data.gw, data.gh);
    
    // 1. Calculate vertex position in UI space
    // We use aPos.xy to scale the unit quad to the character size
    vec3 vertex_pos = vec3(rect_pos + (aPos.xy * rect_size), 0.0);
    
    // 2. Define Pivots
    vec3 local_center = vec3(rect_pos + (rect_size * 0.5), 0.0);
    vec3 para_center = vec3(data.pcx, data.pcy, 0.0);
    vec3 pivot = (data.use_center_pivot == 1) ? para_center : local_center;

    // 3. Apply Rotation
    mat3 rotMat = getRotationMatrix(vec3(data.pitch, data.yaw, data.roll));
    vec3 rotated_offset = rotMat * (vertex_pos - pivot);
    vec2 final_ui_pos = pivot.xy + rotated_offset.xy;

    // 4. Depth Handling
    // If your Ortho matrix is 0 to 1, this works. 
    // If it's -1 to 1, you might need: -1.0 + (data.abs_z * 0.01)
    float ui_z = data.abs_z * 0.01; 

    gl_Position = text_perspective * vec4(final_ui_pos, ui_z, 1.0);

    // 5. Outputs
    TexCoords = aPos.xy * vec2(data.uw, data.vh) + vec2(data.u, data.v);
    FontHandle = uvec2(data.h_low, data.h_high);
    vColor = vec4(data.r, data.g, data.b, data.a); // Added this back!
}
    """
    default_3d_rendering = """#version 460 core

// --- ATTRIBUTES ---
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec2 aTexCoord;
layout(location = 2) in uint aTexIndex;
layout(location = 3) in vec3 aNormals;
layout(location = 4) in uint aSpecIndex;

// --- OUTPUTS TO FRAGMENT SHADER ---
out vec2 vTexCoord;
out vec3 vFragPos;
out vec3 vNormal;
flat out uint vTexIndex; 
flat out uint vSpecIndex;

// --- UNIFORMS ---
uniform mat4 model_matrix;
uniform mat4 view_matrix;
uniform mat4 perspective_matrix;
uniform mat3 normal_matrix; // Recalculated once per model in Python

void main() {
    // 1. Calculate World Position
    vec4 worldPos = model_matrix * vec4(aPos, 1.0);

    // 2. Project to Screen
    gl_Position = perspective_matrix * view_matrix * worldPos;

    // 3. Pass data to Fragment Shader
    vFragPos = worldPos.xyz;
    vTexCoord = aTexCoord;
    vTexIndex = aTexIndex;   
    vSpecIndex = aSpecIndex;

    // 4. Transform Normals to World Space
    // Using the pre-calculated mat3 ensures lighting works on stretched/skewed objects
    vNormal = normalize(normal_matrix * aNormals);  
}""" #TODO normals suck ass to manually define, find a way to autocalculate
    fullbright_light_ignore = """
#version 460 core

// --- ATTRIBUTES (Kept identical to avoid Python attribute errors) ---
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec2 aTexCoord;
layout(location = 2) in uint aTexIndex;
layout(location = 3) in vec3 aNormals; 
layout(location = 4) in uint aSpecIndex;

// --- OUTPUTS ---
out vec2 vTexCoord;
flat out uint vTexIndex; 

// --- UNIFORMS ---
uniform mat4 model_matrix;
uniform mat4 view_matrix;
uniform mat4 perspective_matrix;

void main() {
    // 1. Standard transformation
    gl_Position = perspective_matrix * view_matrix * model_matrix * vec4(aPos, 1.0);

    // 2. Pass only texture data
    vTexCoord = aTexCoord;
    vTexIndex = aTexIndex;
}
"""
    bindless_prot = """
            #version 460 core
#extension GL_ARB_bindless_texture : require

// Vertex attributes
layout(location = 0) in vec3 aPos;       // position
layout(location = 2) in vec2 aTexCoord; // texture coordinates
layout(location = 3) in uint aTexIndex; // flat index into SSBO

// Outputs to fragment shader
out vec2 vTexCoord;
flat out uint vTexIndex;

// Transformation matrices
uniform mat4 model_matrix;
uniform mat4 view_matrix;
uniform mat4 perspective_matrix;

void main() {
    gl_Position = perspective_matrix * view_matrix * model_matrix * vec4(aPos, 1.0);

    // Pass through the actual texture coordinates and index
    vTexCoord = aTexCoord;
    vTexIndex = aTexIndex;
}
    """
    bindless_test = """
                #version 460 core
    #extension GL_ARB_bindless_texture : require

    // Vertex attributes
    layout(location = 0) in vec3 aPos;       // position
    layout(location = 2) in vec2 aTexCoord; // texture coordinates
    layout(location = 3) in uint aTexIndex; // flat index into SSBO

    // Outputs to fragment shader
    out vec2 vTexCoord;
    flat out uint vTexIndex;

    // Transformation matrices
    uniform mat4 model_matrix;
    uniform mat4 view_matrix;
    uniform mat4 perspective_matrix;

    void main() {
        gl_Position = perspective_matrix * view_matrix * model_matrix * vec4(aPos, 1.0);

        // Pass through the actual texture coordinates and index
        vTexCoord = aTexCoord;
        vTexIndex = aTexIndex;
    }
        """
    _window_renderer = """
       #version 330 core

layout (location = 0) in vec3 window_position;
layout (location = 1) in vec2 camera_output_texture_position;

out vec2 texture_coordinates;

void main()
{
    texture_coordinates = camera_output_texture_position;
    gl_Position = vec4(window_position, 1.0);
}
    """
    lighting_self = """#version 330 core
    layout (location = 0) in vec3 aPos;
    layout (location = 1) in vec3 aNormal;
    layout(location=2) in vec2 aTexCoords;
    out vec2 TexCoords;
    out vec3 FragPos;
    out vec3 Normal;

    uniform mat4 model_matrix;
    uniform mat4 view_matrix;
    uniform mat4 perspective_matrix;

    void main()
    {
        FragPos = vec3(model_matrix * vec4(aPos, 1.0));
        Normal = mat3(transpose(inverse(model_matrix))) * aNormal;  
        TexCoords = aTexCoords;

        gl_Position = perspective_matrix * view_matrix * vec4(FragPos, 1.0);
    }

    """
    lighting_phong = """#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec3 aNormal;

out vec3 FragPos;
out vec3 Normal;

uniform mat4 model_matrix;
uniform mat4 view_matrix;
uniform mat4 perspective_matrix;

void main()
{
    FragPos = vec3(model_matrix * vec4(aPos, 1.0));
    Normal = mat3(transpose(inverse(model_matrix))) * aNormal;  

    gl_Position = perspective_matrix * view_matrix * vec4(FragPos, 1.0);
}

"""
    light_cube = """#version 330 core
    layout (location = 0) in vec3 aPos;

    uniform mat4 model_matrix;
    uniform mat4 view_matrix;
    uniform mat4 perspective_matrix;

    void main()
    {
    	gl_Position = perspective_matrix * view_matrix * model_matrix * vec4(aPos, 1.0);
    }
    	"""


class FragmentShader:
    text_shader="""
#version 430 core
#extension GL_ARB_bindless_texture : require

in vec2 TexCoords;
in vec4 vColor; // This comes from your data.r, g, b, a
flat in uvec2 FontHandle;

out vec4 FragColor;

float median(float r, float g, float b) {
    return max(min(r, g), min(max(r, g), b));
}

void main() {
    sampler2D msdf_atlas = sampler2D(FontHandle);
    vec3 msd = texture(msdf_atlas, TexCoords).rgb;
    
    // MSDF shape calculation
    float sd = median(msd.r, msd.g, msd.b);
    float screenPxRange = 2.0; 
    float screenPxDistance = screenPxRange * (sd - 0.5);
    float opacity = clamp(screenPxDistance + 0.5, 0.0, 1.0);

    // Apply the text color!
    // We multiply the color's RGB by the MSDF opacity, 
    // and combine the color's Alpha with the MSDF opacity.
    FragColor = vec4(vColor.rgb, vColor.a * opacity);
}
"""

    default_3d_rendering = """#version 460 core
#extension GL_ARB_bindless_texture : require

struct Light {
    vec4 position_on;     // [x, y, z, on_flag]
    vec4 direction_type;  // [x, y, z, type]
    vec4 attenuation;     // [constant, linear, quadratic, radius]
    vec4 spotAngles;      // [cutOff, outerCutOff, 0, 0]
    vec4 ambient;         // [r, g, b, 0]
    vec4 diffuse;         // [r, g, b, 0]
    vec4 specular;        // [r, g, b, 0]
};

// --- UNIFORMS & SSBOs ---
layout(std430, binding = 0) buffer TexHandles { uvec2 handles[]; };
layout(std430, binding = 1) buffer LightBuffer { Light lights[]; };

uniform int numLights;
uniform vec3 viewPos;
struct Material { float shininess; };
uniform Material material;

// --- INPUTS ---
flat in uint vTexIndex; 
flat in uint vSpecIndex; 
in vec2 vTexCoord;
in vec3 vNormal;
in vec3 vFragPos;

out vec4 FragColor;

vec3 CalcLight(Light l, vec3 normal, vec3 viewDir, vec3 texColor, vec3 specMap) {
    // 1. Skip if light is off
    if (l.position_on.w < 0.5) return vec3(0.0);

    int type = int(l.direction_type.w);
    vec3 lightDir;
    float attenuation = 1.0;
    float intensity = 1.0;

    // 2. Direction and Attenuation
    if (type == 2) { // Global Directional
        lightDir = normalize(-l.direction_type.xyz);
    } else {         // Point (0) or Spot (1)
        vec3 lPos = l.position_on.xyz;
        lightDir = normalize(lPos - vFragPos);
        float d = length(lPos - vFragPos);
        attenuation = 1.0 / (l.attenuation.x + l.attenuation.y * d + l.attenuation.z * (d * d));

        if (type == 1) { // Spotlight
            float theta = dot(lightDir, normalize(-l.direction_type.xyz)); 
            float epsilon = l.spotAngles.x - l.spotAngles.y;
            intensity = clamp((theta - l.spotAngles.y) / epsilon, 0.0, 1.0);
        }
    }

    // 3. Diffuse Factor (N dot L)
    float diff_factor = max(dot(normal, lightDir), 0.0);

    // 4. Ambient
    vec3 amb = l.ambient.rgb * texColor;

    // 5. Diffuse
    vec3 diff = l.diffuse.rgb * diff_factor * texColor;

    // 6. Specular (Fixed to disappear when light is black or behind)
    vec3 reflectDir = reflect(-lightDir, normal);
    float spec_pow = pow(max(dot(viewDir, reflectDir), 0.0), material.shininess);

    // Logic: Specular only exists if light is hitting the front (diff_factor > 0)
    // and if the light actually has a diffuse color (prevents ghost metal shine)
    float lightBrightness = max(max(l.diffuse.r, l.diffuse.g), l.diffuse.b);
    vec3 spec = (diff_factor > 0.0) ? (l.specular.rgb * spec_pow * specMap * lightBrightness) : vec3(0.0);

    return (amb + diff + spec) * attenuation * intensity;
}

void main() {
    sampler2D diffuseTex = sampler2D(handles[vTexIndex]);
    sampler2D specularTex = sampler2D(handles[vSpecIndex]);

    vec3 texColor = texture(diffuseTex, vTexCoord).rgb;
    vec3 specMap = texture(specularTex, vTexCoord).rgb;
    vec3 norm = normalize(vNormal);
    vec3 viewDir = normalize(viewPos - vFragPos);

    vec3 result = vec3(0.0);
    for(int i = 0; i < numLights; i++) {
        result += CalcLight(lights[i], norm, viewDir, texColor, specMap);
    }

    FragColor = vec4(result, 1.0);
}"""
    fullbright_light_ignore = """#version 460 core
#extension GL_ARB_bindless_texture : require

// --- UNIFORMS & SSBOs ---
// Keeping the texture handle buffer
layout(std430, binding = 0) buffer TexHandles { uvec2 handles[]; };

// --- INPUTS ---
// Keep all inputs from your existing vertex shader to avoid layout mismatches
flat in uint vTexIndex; 
flat in uint vSpecIndex; 
in vec2 vTexCoord;
in vec3 vNormal;
in vec3 vFragPos;

out vec4 FragColor;

void main() {
    // 1. Convert the handle to a sampler
    sampler2D diffuseTex = sampler2D(handles[vTexIndex]);

    // 2. Sample the FULL color (RGBA)
    vec4 texColor = texture(diffuseTex, vTexCoord);

    // 3. Output the sampled alpha instead of a hardcoded 1.0
    FragColor = texColor;
}
"""

    bindless_prot = """
    #version 460 core
    #extension GL_ARB_bindless_texture : require

    // Removed GL_ARB_gpu_shader_int64 as it is not supported on your hardware
    flat in uint vTexIndex;
    in vec2 vTexCoord;
    out vec4 fragColor;

    layout(std430, binding = 0) buffer TexHandles {
    uvec2 handles[]; 
};

    void main() {

        // The bindless extension allows constructing a sampler directly from a uvec2
        sampler2D tex = sampler2D(handles[vTexIndex]);
        fragColor = texture(tex, vTexCoord);
    }"""
    bindless_test = """
        #version 460 core
        #extension GL_ARB_bindless_texture : require

        // Removed GL_ARB_gpu_shader_int64 as it is not supported on your hardware
        flat in uint vTexIndex;
        in vec2 vTexCoord;
        out vec4 fragColor;

        layout(std430, binding = 0) buffer TexHandles {
        uvec2 handles[]; 
    };

        void main() {

            // The bindless extension allows constructing a sampler directly from a uvec2
            sampler2D tex = sampler2D(handles[vTexIndex]);
            fragColor = texture(tex, vTexCoord);
        }"""
    _window_renderer = """
        #version 330 core

in vec2 texture_coordinates;
in vec2 TexCoords;
out vec4 FragColor;

uniform sampler2D camera_output;

void main()
{
    FragColor = texture(camera_output, texture_coordinates);
}
    """
    lighting_self = """#version 330 core
    out vec4 FragColor;
    in vec3 FragPos;  
    in vec3 Normal;  
    in vec2 TexCoords;

    struct Material_struct {
        sampler2D diffuse;
        vec3 specular_color;
        float shininess;
    }; 

    struct Light_struct {
        vec3 position;
        vec3 ambient_color;
        vec3 diffuse_color;
        vec3 specular_color;
    };

    uniform vec3 viewPos;
    uniform Material_struct material;
    uniform Light_struct light;


    void main()
    {
        // ambient
        vec3 ambient = light.ambient_color * texture(material.diffuse, TexCoords).rgb;

        // diffuse 
        vec3 norm = normalize(Normal);
        vec3 lightDir = normalize(light.position - FragPos);
        float diff = max(dot(norm, lightDir), 0.0);
        vec3 diffuse = light.diffuse_color * diff *  texture(material.diffuse, TexCoords).rgb;  



        // specular
        vec3 viewDir = normalize(viewPos - FragPos);
        vec3 reflectDir = reflect(-lightDir, norm);  
        float spec = pow(max(dot(viewDir, reflectDir), 0.0), material.shininess);
        vec3 specular = light.specular_color * (spec * material.specular_color);  

        vec3 result = ambient + diffuse + specular;
        FragColor = vec4(result, 1.0);
    }   """
    lighting_phong = """#version 330 core
out vec4 FragColor;
in vec3 FragPos;  
in vec3 Normal; 

struct Material_struct {
    vec3 main_color;
    vec3 ambient_color;
    vec3 diffuse_color;
    vec3 specular_color;    
    float shininess;
}; 

struct Light_struct {
    vec3 position;
    vec3 ambient_color;
    vec3 diffuse_color;
    vec3 specular_color;
};

uniform vec3 viewPos;
uniform Material_struct material;
uniform Light_struct light;


void main()
{
    // ambient
    vec3 ambient = light.ambient_color * material.ambient_color;

    // diffuse 
    vec3 norm = normalize(Normal);
    vec3 lightDir = normalize(light.position - FragPos);
    float diff = max(dot(norm, lightDir), 0.0);
    vec3 diffuse = light.diffuse_color * (diff * material.diffuse_color);

    // specular
    vec3 viewDir = normalize(viewPos - FragPos);
    vec3 reflectDir = reflect(-lightDir, norm);  
    float spec = pow(max(dot(viewDir, reflectDir), 0.0), material.shininess);
    vec3 specular = light.specular_color * (spec * material.specular_color);  

    vec3 result = ambient + diffuse + specular;
    FragColor = vec4(result, 1.0);
}   """
    light_cube = """#version 330 core
out vec4 FragColor;
uniform vec3 light_color;
void main()
{
    FragColor = vec4(light_color,1.0); // set all 4 vector values to 1.0;
}"""


valid_shader_types = [GL_VERTEX_SHADER, GL_FRAGMENT_SHADER, GL_GEOMETRY_SHADER, GL_TESS_CONTROL_SHADER,
                      GL_TESS_EVALUATION_SHADER, GL_COMPUTE_SHADER, VertexShader, FragmentShader]


class CompleteShader:
    def __init__(self, uncompiled_vertex_shader, uncompiled_fragment_shader):
        self.program = None
        self._uniforms = {}  # Stores current values
        self._uniform_locations = {}  # Location cache for performance
        v_code = uncompiled_vertex_shader
        f_code = uncompiled_fragment_shader
        if v_code and f_code:
            self._compile_and_attach_shaders(v_code, f_code)
        v_data = get_shader_data(v_code)
        f_data = get_shader_data(f_code)
        self.wanted_uniforms = v_data[1] + f_data[1]
        self._cache_locations()

    def _compile_and_attach_shaders(self, v_code, f_code):
        v_shader = self._compile_shader(v_code, GL_VERTEX_SHADER)
        f_shader = self._compile_shader(f_code, GL_FRAGMENT_SHADER)

        program = glCreateProgram()
        glAttachShader(program, v_shader)
        glAttachShader(program, f_shader)
        glLinkProgram(program)

        if not glGetProgramiv(program, GL_LINK_STATUS):
            raise RuntimeError(f"Linker Error: {glGetProgramInfoLog(program).decode()}")

        self.program = program
        glDeleteShader(v_shader)
        glDeleteShader(f_shader)

    def _compile_shader(self, code, s_type):
        shader = glCreateShader(s_type)
        glShaderSource(shader, code)
        glCompileShader(shader)
        if not glGetShaderiv(shader, GL_COMPILE_STATUS):
            raise RuntimeError(f"Compile Error ({s_type}): {glGetShaderInfoLog(shader).decode()}")
        return shader

    def _cache_locations(self):
        for name in self.wanted_uniforms:
            loc = glGetUniformLocation(self.program, name)
            if loc != -1:
                self._uniform_locations[name] = loc

    def use(self):
        glUseProgram(self.program)
        if hasattr(TextureHandler, 'texture_shader_storage_buffer'):
            glBindBufferBase(GL_SHADER_STORAGE_BUFFER, 0, TextureHandler.texture_shader_storage_buffer)

    def set_uniform(self, names, values):
        if not isinstance(names, list): names = [names]
        if not isinstance(values, list): values = [values]

        for name, value in zip(names, values):
            self._uniforms[name] = value
            self._apply_uniform(name, value)

    def _apply_uniform(self, name, value):

        location = self._uniform_locations.get(name)
        if location is None:
            location = glGetUniformLocation(self.program, name)
            self._uniform_locations[name] = location

        if location == -1: return

        if callable(value): value = value()
        if isinstance(value, glm.mat4):
            glUniformMatrix4fv(location, 1, GL_TRUE, np.array(value, dtype=np.float32))
        elif isinstance(value, glm.vec3):
            glUniform3f(location, *value)
        elif isinstance(value, (float, np.float32)):
            glUniform1f(location, value)
        elif isinstance(value, (int, bool)):
            glUniform1i(location, int(value))
        elif isinstance(value, glm.vec4):
            glUniform4f(location, *value)
        elif isinstance(value, glm.mat3):
            glUniformMatrix3fv(location, 1, GL_TRUE, np.array(value, dtype=np.float32))
        elif isinstance(value, (tuple, list)):
            self._apply_tuple_uniform(location, value)
        elif isinstance(value, np.ndarray):
            self._apply_ndarray_uniform(location, value)
        elif isinstance(value, glm.vec2):
            glUniform2f(location, *value)

    def _apply_tuple_uniform(self, location, value):
        l = len(value)
        if l == 3:
            glUniform3f(location, *value)
        elif l == 2:
            glUniform2f(location, *value)
        elif l == 4:
            glUniform4f(location, *value)
        elif l == 16:
            glUniformMatrix4fv(location, 1, GL_TRUE, np.array(value, dtype=np.float32))

    def _apply_ndarray_uniform(self, location, value):
        if value.ndim == 2:
            glUniformMatrix4fv(location, 1, GL_TRUE, value.astype(np.float32))
        else:
            s = value.size
            if s == 3:
                glUniform3f(location, *value)
            elif s == 2:
                glUniform2f(location, *value)
            elif s == 4:
                glUniform4f(location, *value)

    def delete(self):
        if self.program:
            glDeleteProgram(self.program)
            self.program = None

class UniformHelper:
    def __init__(self):
        self.uniforms_available = {}

    def _get_all_uniform_names(self, struct=None):
        if struct is None:
            return list(self.uniforms_available.keys())
        return [k for k in self.uniforms_available.keys() if f"{struct}." in k]
    def _set_uniforms(self, names, uniforms, struct=None):
        if not isinstance(names, list): names = [names]
        if not isinstance(uniforms, list): uniforms = [uniforms]
        prefix = f"{struct}." if struct else ""
        for name, val in zip(names, uniforms):
            self.uniforms_available[f"{prefix}{name}"] = val

    def _get_uniforms(self, names):
        if not isinstance(names, list): names = [names]
        found_names = []
        found_unifs = []
        for name in names:
            if name in self.uniforms_available:
                found_names.append(name)
                found_unifs.append(self.uniforms_available[name])
        return found_names, found_unifs

    def _use_same_helper_as(self, other):
        if isinstance(other, UniformHelper):
            self.uniforms_available = other.uniforms_available
        else:
            self.uniforms_available = other.uniform_helper.uniforms_available


