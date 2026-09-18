
from Modular_Overly_Disorienting_Engine import *
import math

settings=StartupSettings()
window_one = Window(settings)
window_one.select()
# window_two=Window(copy_resources_from_window_id=window_one.id)



window_one.set_size(1000,1000)
# window_one.clear_color = (0.075, 0.18, 0.553, 1.0)

mouse_layout=MouseLayout()
keyboard_layout=KeyboardLayout()
mouse = Mouse(mouse_layout)
keyboard = Keyboard(keyboard_layout)
mouse.default_window=window_one #TODO add set method
keyboard.default_window=window_one
window_one.set_input(mouse,keyboard)
camera_shader_for_rendering=CompleteShader(VertexShader.default_3d_rendering,FragmentShader.default_3d_rendering)
lamp_shader=CompleteShader(VertexShader.light_cube,FragmentShader.light_cube)
world_text_shader_for_camera=CompleteShader(VertexShader.world_text_shader,FragmentShader.text_shader)
ui_text_shader_for_camera=CompleteShader(VertexShader.ui_text_shader,FragmentShader.text_shader)
output_settings=OutputStartupSettings()
output_settings.resolution_x,output_settings.resolution_y=1000,1000
load_engine(window_one)
camera = Camera(optional_mouse=mouse,specific_output_settings=output_settings)
window_one.set_main_camera(camera)
camera.yaw_sensitivity,camera.pitch_sensitivity,camera.roll_sensitivity=0.5,0.5,0.5
fullbright_shader=CompleteShader(VertexShader.fullbright_light_ignore,FragmentShader.fullbright_light_ignore)
camera.set_main_shader(fullbright_shader)
camera.add_shaders(lamp_shader,PASS_EXTRA)

camera.add_shaders(ui_text_shader_for_camera,PASS_TEXT_UI)

output_settings2=OutputStartupSettings()
output_settings2.resolution_x,output_settings.resolution_y=1000,1000


test_scene=Scene()



camera2test = Camera(specific_output_settings=output_settings)
camera2test.set_position(*(camera2test.get_position()-camera.get_front_direction(False)*2))
camera2test.set_main_shader(camera_shader_for_rendering)
camera2test.add_shaders(lamp_shader,PASS_EXTRA)
box_texture_index = TextureHandler.get_textures("box.png")
box_specular_texture= TextureHandler.get_textures("box_specular.png")
# camera2test.add_shaders(world_text_shader_for_camera,TEXT_PASS)
cube=Model(autoadd_to_main_scene=False,autorender=False)
cube.add_attribute(2)
cube.add_attribute(1,int)
cube.add_attribute(3)
cube.add_attribute(1,int)

vertices_to_add = [
    # FRONT Pos (Z+)       Texel (U,V)   Tex1          Normals (X,Y,Z)      Tex2 (Specular)
    -0.5, -0.5,  0.5,      0.0,  0.0,    box_texture_index,  0.0,  0.0,  1.0,  box_specular_texture,
    -0.5,  0.5,  0.5,      0.0,  1.0,    box_texture_index,  0.0,  1.0,  1.0,  box_specular_texture, # Note: Fixed Normal Y to match Z+ face
     0.5,  0.5,  0.5,      1.0,  1.0,    box_texture_index,  0.0,  0.0,  1.0,  box_specular_texture,
     0.5, -0.5,  0.5,      1.0,  0.0,    box_texture_index,  0.0,  0.0,  1.0,  box_specular_texture,

    # RIGHT Pos (X+)       Texel (U,V)   Tex1          Normals (X,Y,Z)      Tex2 (Specular)
     0.5, -0.5,  0.5,      0.0,  0.0,    camera2test.output.texture,  1.0,  0.0,  0.0,  camera2test.output.texture,
     0.5, -0.5, -0.5,      1.0,  0.0,    camera2test.output.texture,  1.0,  0.0,  0.0,  camera2test.output.texture,
     0.5,  0.5, -0.5,      1.0,  1.0,    camera2test.output.texture,  1.0,  0.0,  0.0,  camera2test.output.texture,
     0.5,  0.5,  0.5,      0.0,  1.0,    camera2test.output.texture,  1.0,  0.0,  0.0,  camera2test.output.texture,

    # BACK Pos (Z-)        Texel (U,V)   Tex1          Normals (X,Y,Z)      Tex2 (Specular)
     0.5, -0.5, -0.5,      0.0,  0.0,    box_texture_index,  0.0,  0.0, -1.0,  box_specular_texture,
     0.5,  0.5, -0.5,      0.0,  1.0,    box_texture_index,  0.0,  0.0, -1.0,  box_specular_texture,
    -0.5,  0.5, -0.5,      1.0,  1.0,    box_texture_index,  0.0,  0.0, -1.0,  box_specular_texture,
    -0.5, -0.5, -0.5,      1.0,  0.0,    box_texture_index,  0.0,  0.0, -1.0,  box_specular_texture,

    # LEFT Pos (X-)        Texel (U,V)   Tex1          Normals (X,Y,Z)      Tex2 (Specular)
    -0.5, -0.5, -0.5,      0.0,  0.0,    box_texture_index, -1.0,  0.0,  0.0,  box_specular_texture,
    -0.5, -0.5,  0.5,      1.0,  0.0,    box_texture_index, -1.0,  0.0,  0.0,  box_specular_texture,
    -0.5,  0.5,  0.5,      1.0,  1.0,    box_texture_index, -1.0,  0.0,  0.0,  box_specular_texture,
    -0.5,  0.5, -0.5,      0.0,  1.0,    box_texture_index, -1.0,  0.0,  0.0,  box_specular_texture,

    # TOP Pos (Y+)         Texel (U,V)   Tex1          Normals (X,Y,Z)      Tex2 (Specular)
    -0.5,  0.5,  0.5,      0.0,  0.0,    box_texture_index,  0.0,  1.0,  0.0,  box_specular_texture,
     0.5,  0.5,  0.5,      1.0,  0.0,    box_texture_index,  0.0,  1.0,  0.0,  box_specular_texture,
     0.5,  0.5, -0.5,      1.0,  1.0,    box_texture_index,  0.0,  1.0,  0.0,  box_specular_texture,
    -0.5,  0.5, -0.5,      0.0,  1.0,    box_texture_index,  0.0,  1.0,  0.0,  box_specular_texture,

    # BOTTOM Pos (Y-)      Texel (U,V)   Tex1          Normals (X,Y,Z)      Tex2 (Specular)
    -0.5, -0.5, -0.5,      0.0,  0.0,    box_texture_index,  0.0, -1.0,  0.0,  box_specular_texture,
     0.5, -0.5, -0.5,      1.0,  0.0,    box_texture_index,  0.0, -1.0,  0.0,  box_specular_texture,
     0.5, -0.5,  0.5,      1.0,  1.0,    box_texture_index,  0.0, -1.0,  0.0,  box_specular_texture,
    -0.5, -0.5,  0.5,      0.0,  1.0,    box_texture_index,  0.0, -1.0,  0.0,  box_specular_texture,
]


cube.add_vertices(vertices_to_add)
cube.connect_vertices([0,1,2,0,2,3])
cube.connect_vertices([4, 5, 6, 4, 6, 7])
cube.connect_vertices([8, 9, 10, 8, 10, 11])
cube.connect_vertices([12, 13, 14, 12, 14, 15])
cube.connect_vertices([16, 17, 18, 16, 18, 19])
cube.connect_vertices([20, 21, 22, 20, 22, 23])


cube.set_position(z=-3)
vertices_to_add2 = [
    # FRONT face (Z+)
    -0.5, -0.5,  0.5,
    -0.5,  0.5,  0.5,
     0.5,  0.5,  0.5,
     0.5, -0.5,  0.5,

    # RIGHT face (X+)
     0.5, -0.5,  0.5,
     0.5, -0.5, -0.5,
     0.5,  0.5, -0.5,
     0.5,  0.5,  0.5,

    # BACK face (Z-)
     0.5, -0.5, -0.5,
     0.5,  0.5, -0.5,
    -0.5,  0.5, -0.5,
    -0.5, -0.5, -0.5,

    # LEFT face (X-)
    -0.5, -0.5, -0.5,
    -0.5, -0.5,  0.5,
    -0.5,  0.5,  0.5,
    -0.5,  0.5, -0.5,

    # TOP face (Y+)
    -0.5,  0.5,  0.5,
     0.5,  0.5,  0.5,
     0.5,  0.5, -0.5,
    -0.5,  0.5, -0.5,

    # BOTTOM face (Y-)
    -0.5, -0.5, -0.5,
     0.5, -0.5, -0.5,
     0.5, -0.5,  0.5,
    -0.5, -0.5,  0.5,
]
cube2 = Model(autoadd_to_main_scene=False,autorender=False)
cube2.add_vertices(vertices_to_add2)
cube2.connect_vertices([0,1,2,0,2,3])
cube2.connect_vertices([4, 5, 6, 4, 6, 7])
cube2.connect_vertices([8, 9, 10, 8, 10, 11])
cube2.connect_vertices([12, 13, 14, 12, 14, 15])
cube2.connect_vertices([16, 17, 18, 16, 18, 19])
cube2.connect_vertices([20, 21, 22, 20, 22, 23])
cube2.set_scale(0.1,0.1,0.1)


cube3 = Model(autoadd_to_main_scene=False,autorender=False)
cube3.add_vertices(vertices_to_add2)
cube3.connect_vertices([0,1,2,0,2,3])
cube3.connect_vertices([4, 5, 6, 4, 6, 7])
cube3.connect_vertices([8, 9, 10, 8, 10, 11])
cube3.connect_vertices([12, 13, 14, 12, 14, 15])
cube3.connect_vertices([16, 17, 18, 16, 18, 19])
cube3.connect_vertices([20, 21, 22, 20, 22, 23])
cube3.set_scale(0.1,0.1,0.1)
cube3.set_position(1.5,1.5,-1.5)




window_one.add_extra_cameras(camera2test) #fuck you, me



camera.add_models_to_shaders(fullbright_shader,cube)
camera.add_models_to_shaders(lamp_shader,[cube2,cube3])
camera2test.add_models_to_shaders(camera_shader_for_rendering,[cube])
camera2test.add_models_to_shaders(lamp_shader,[cube2,cube3])#TODO remove
def debug():
    print(camera_shader_for_rendering.wanted_uniforms)
    print(cube.get_all_uniform_names())



cam_speed=0
test_light=Light(0,diffuse=[0.0,0.0,0.0])

test_light2=Light(0,[1.5,1.5,-1.5],diffuse=[1.0,0.0,0.0])

test_scene.add_to_scene(camera)
test_scene.add_to_scene(cube)
test_scene.add_to_scene([cube2,cube3])
test_scene.add_to_scene(camera2test)
test_scene.add_to_scene(test_light)
test_scene.add_to_scene(test_light2)

delt=0
def nothing(dt):
    global cam_speed
    global delt
    delt=dt
    cube2.set_position(math.cos(get_time()),1,math.sin(get_time())-3)
    test_light.set_position(*cube2.get_position())






def forward():
    camera.change_position(*delt*4*camera.get_front_direction())
def backward():
    camera.change_position(*delt*-4*camera.get_front_direction())
def right():
    camera.change_position(*delt*4*camera.get_right_direction())
def left():
    camera.change_position(*delt*-4*camera.get_right_direction())
def leave():
    window_one.close("nothing")

def bup():
    # Blue Up
    global delt
    if test_light.diffuse[2] < 1.0:

        test_light.diffuse[2] += delt
        test_light.specular[2] = test_light.diffuse[2] # Keep specular in sync
        test_light.ambient[2] = test_light.diffuse[2] * 0.2 # Keep ambient low
def bdo():
    # Blue Down
    global delt
    if test_light.diffuse[2] > 0.0:
        test_light.diffuse[2] -= delt
        test_light.specular[2] = test_light.diffuse[2]
        test_light.ambient[2] = test_light.diffuse[2] * 0.2
def gup():
    # Green Up
    global delt
    if test_light.diffuse[1] < 1.0:
        test_light.diffuse[1] += delt
        test_light.specular[1] = test_light.diffuse[1]
        test_light.ambient[1] = test_light.diffuse[1] * 0.2
def gdo():
    # Green Down
    global delt
    if test_light.diffuse[1] > 0.0:
        test_light.diffuse[1] -= delt
        test_light.specular[1] = test_light.diffuse[1]
        test_light.ambient[1] = test_light.diffuse[1] * 0.2
def rup():
    # Red Up
    if test_light.diffuse[0] < 1.0:
        test_light.diffuse[0] += delt
        test_light.specular[0] = test_light.diffuse[0]
        test_light.ambient[0] = test_light.diffuse[0] * 0.2
def rdo():
    # Red Down
    if test_light.diffuse[0] > 0.0:
        test_light.diffuse[0] -= delt
        test_light.specular[0] = test_light.diffuse[0]
        test_light.ambient[0] = test_light.diffuse[0] * 0.2
def getlcol():
    return test_light.diffuse
def getlpos():
    return cube2.get_position()
def getcpos():
    return camera.get_position()
def tlo():
    test_light2.on=False
def swapcams1():
    window_one.set_main_camera(camera)
def swapcams2():
    window_one.set_main_camera(camera2test)

camera.set_uniforms("viewPos",getcpos)



def word_delete():
    pass
    # ui_text_layer.delete_text_from_paragraph(ui_sentence,"new",ALL_INSTANCES_WORD,INSTANT_TEXT)


TextHandler.load_font("Menu",False,False,"menu-font-pixelated.ttf")
TextHandler.load_font("Decay",False,False,"decay-take-2.ttf")
world_text_layer = TextLayer(camera.get_perspective_matrix)
ui_text_layer = TextLayer(glm.ortho(0.0, window_one.get_size()[0], 0.0, window_one.get_size()[1]))
ui_paragraph=ui_text_layer.add_new_paragraph()

test_sentence=ui_paragraph.add_sentence("This is a test sentence. ",mode=MODE_INSTANT_TEXT,delay_mode=DELAY_NONE)

# test_sentence.add_text("This is another ")
# test_sentence.add_text("test",r=1.0,g=0.0,b=0.0)
# test_sentence.add_text(" oracion.")


# test_sentence.
# ui_sentence = ui_text_layer.add_new_paragraph("This doth be UI.\nPoggers 4",0,900, font_bold_italic_tuple=("Arial",False,False),font_size=64,max_paragraph_length=800,mode=PER_WORD,interval=0.1,)
#
# world_sentence = world_text_layer.add_new_paragraph("Sentences work yay 1 2 3 last_word_of_first_sentence.\nPoggers 4",x=0, y=1, z=-3,font_size=1,mode=PER_WORD,interval=0.1,yaw=6,pitch=-30,blue=1.0,green=0.0,red=0.0,use_centre_pivot=False)

cube.set_uniforms("shininess", 8.0,"material")
cube2.set_uniforms("light_color",getlcol)
cube3.set_uniforms("light_color",(1.0,0.0,0.0))



camera.set_rotation(55,325,0)
camera.set_position(2.5,2.0,-1.25)
camera2test.set_rotation(55,325,0)
camera2test.set_position(2.5,2.0,-1.25)
cube2.add_children(cube3)
#TODO ADD CLUSTERED SHADING OPTION FOR LIGHTING. WILL BE VERY GOOD




keyboard.add_action_to_layouts(swapcams1,KEY_N,PRESS)
keyboard.add_action_to_layouts(swapcams2,KEY_M,PRESS)

keyboard.add_action_to_layouts(bup,KEY_KP_9,HOLD)
keyboard.add_action_to_layouts(bdo,KEY_KP_6,HOLD)
keyboard.add_action_to_layouts(gup, KEY_KP_8, HOLD)
keyboard.add_action_to_layouts(gdo, KEY_KP_5, HOLD)
keyboard.add_action_to_layouts(rup, KEY_KP_7, HOLD)
keyboard.add_action_to_layouts(rdo, KEY_KP_4, HOLD)
keyboard.add_action_to_layouts(tlo,KEY_T,PRESS)
keyboard.add_action_to_layouts(forward,KEY_W,HOLD)
keyboard.add_action_to_layouts(backward,KEY_S,HOLD)
keyboard.add_action_to_layouts(right,KEY_A,HOLD)
keyboard.add_action_to_layouts(left,KEY_D,HOLD)
keyboard.add_action_to_layouts(leave,KEY_F)
keyboard.add_action_to_layouts(debug)
keyboard.add_action_to_layouts(word_delete,KEY_B)


# print(ui_text_layer.paragraphs)
activate_main_loop(nothing)




#TODO FIX THE STUPID LIGHTING ISSUE THAT MAKES THINGS DARKER WHEN FIRST TURNING ON THE COLOR OF THE LIGHT

#TODO ISSUES
#TODO Improve models and meshes and the way that they are drawn, so that they can be instanced and batch rendered

#TODO
# set_input_mode(self.id, CURSOR, CURSOR_HIDDEN)
# that´s for hiding mouse^
# glfwSetFramebufferSizeCallback(window id, function that resets the viewport when resized);
# Phong shader

#TODO You´ll figure it out. You made it this far, you can make it farther.
#TODO I leave it all to you, future me. Apologies for the bad code and I hope you can make it better