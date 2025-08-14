#!/usr/bin/env python
# -*- coding: utf-8 -*-

from imgui.integrations.glfw import GlfwRenderer
from OpenGL.GL import *
from OpenGL.arrays import vbo
import glm
import glfw
import imgui
import sys
import imgui_menu
import mesh
from tkinter import filedialog
import numpy
import logging
import shader

logging.basicConfig(level=logging.INFO)
window = None


class Application:
    loaded_model = None
    view_mode = "DEFAULT"
    background_color = [0.3, 0.3, 0.3]
    model_color = [1.0, 1.0, 1.0]

    @staticmethod
    def change_model(path):
        Application.loaded_model.delete_buffers()
        Application.loaded_model = mesh.Mesh(path)

    @staticmethod
    def request_change_model():
        file_path = Application.open_file()
        if file_path:
            Application.change_model(file_path)

    @staticmethod
    def open_file():
        # open 'extensions.txt' file and read all extensions
        with open("extensions.txt", "r") as file:
            extensions_str = file.read()

        extensions = [("Assimp Assets", extensions_str), ("All Files", ".*")]
        file_path = filedialog.askopenfilename(title="Open Model File", filetypes=extensions)
        return file_path

    @staticmethod
    def quit_application():
        glfw.set_window_should_close(window, True)


def log_gl_debug_message(*args, **kwargs):
    logging.log(logging.INFO, 'args = {0}, kwargs = {1}'.format(args, kwargs))


def gen_global_vbo():
    guid = glGenBuffers(1)
    glBindBuffer(GL_UNIFORM_BUFFER, guid)
    glBufferData(GL_UNIFORM_BUFFER, 128, None, GL_STATIC_DRAW)
    glBindBuffer(GL_UNIFORM_BUFFER, 0)
    glBindBufferBase(GL_UNIFORM_BUFFER, 0, guid)
    return guid


def create_axis_model():
    model_axis = mesh.Mesh()
    model_axis.vertices = [
        0, 0, 0, 10, 0, 0,
        0, 0, 0, 0, 10, 0,
        0, 0, 0, 0, 0, 10
    ]
    model_axis.colors = [
        1, 0, 0, 1, 0, 0,
        0, 1, 0, 0, 1, 0,
        0, 0, 1, 0, 0, 1
    ]
    model_axis.uvs = [0] * 12
    model_axis.normals = [0] * 18
    model_axis.indices = [0, 1, 2, 3, 4, 5]

    # Add grids
    for i in range(0, 21):
        x = i - 10
        model_axis.vertices.extend([-10, 0, x, 10, 0, x, x, 0, -10, x, 0, 10])
        model_axis.colors.extend([0.4, 0.4, 0.4] * 4)
        model_axis.normals.extend([0] * 12)
        model_axis.uvs.extend([0] * 8)
        model_axis.indices.extend([6 + i * 4, 7 + i * 4, 8 + i * 4, 9 + i * 4])

    model_axis.gen_buffer()
    return model_axis


def main():
    global window
    window = impl_glfw_init()
    imgui.create_context()
    impl = GlfwRenderer(window)
    imgui_menu.init_menu()

    glDebugMessageCallback(GLDEBUGPROC(log_gl_debug_message), None)
    Application.loaded_model = mesh.Mesh("Resources/suzanne.obj")

    model_axis = create_axis_model()

    shaders = dict()
    shaders["DEFAULT"] = shader.Shader("Resources/vertex_default.glsl", "Resources/fragment_default.glsl")
    shaders["NORMAL"] = shader.Shader("Resources/vertex_normal.glsl", "Resources/fragment.glsl")
    shaders["UV"] = shader.Shader("Resources/vertex_uv.glsl", "Resources/fragment.glsl")
    shaders["AXIS"] = shader.Shader("Resources/vertex_axis.glsl", "Resources/fragment.glsl")

    for shader_program in shaders.values():
        shader_program.load_shaders()

    guid = gen_global_vbo()

    glEnable(GL_MULTISAMPLE)
    glEnable(GL_DEPTH_TEST)

    mouse_pos_current = (0, 0)
    mouse_pos_last = (0, 0)
    mouse_pos_drag = (0, 0)
    mouse_scroll_integral = 0
    current_scale = 1.0

    while not glfw.window_should_close(window):
        glfw.poll_events()
        impl.process_inputs()

        io = imgui.get_io()
        mouse_pos_last = mouse_pos_current
        mouse_pos_current = io.mouse_pos.x, io.mouse_pos.y

        # can drag model if mouse isn't captured by imgui, .
        if not io.want_capture_mouse:
            if io.mouse_down[0]:
                mouse_pos_drag = (
                    mouse_pos_drag[0] + mouse_pos_current[0] - mouse_pos_last[0],
                    mouse_pos_drag[1] + mouse_pos_current[1] - mouse_pos_last[1])
            mouse_scroll_integral += io.mouse_wheel
            mouse_scroll_integral = max(-10, min(10, mouse_scroll_integral))

        screen_size = io.display_size
        aspect_ratio = screen_size.x / screen_size.y if screen_size.y != 0.0 else 1.0

        glClearColor(*Application.background_color, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glViewport(0, 0, int(screen_size.x), int(screen_size.y))

        imgui_menu.draw_menu(Application)

        loaded_model = Application.loaded_model
        scale_factor = 0.5 + mouse_scroll_integral * 0.05
        target_scale = scale_factor / loaded_model.radius
        current_scale = glm.lerp(current_scale, target_scale, 0.1)

        world_matrix = glm.scale(glm.mat4(1), glm.vec3(current_scale))
        world_matrix = glm.rotate(world_matrix, mouse_pos_drag[1] * 0.01, glm.vec3(1, 0, 0))
        world_matrix = glm.rotate(world_matrix, mouse_pos_drag[0] * 0.01, glm.vec3(0, 1, 0))
        world_matrix = glm.translate(world_matrix, -glm.vec3(loaded_model.center))

        view_matrix = glm.lookAt(glm.vec3(0, 1, 1), glm.vec3(0, 0, 0), glm.vec3(0, 1, 0))
        projection_matrix = glm.perspective(glm.radians(45), aspect_ratio, 0.1, 100.0)

        # update global uniform buffer
        glBindBuffer(GL_UNIFORM_BUFFER, guid)
        glBufferSubData(GL_UNIFORM_BUFFER, 0, 64, glm.value_ptr(view_matrix))
        glBufferSubData(GL_UNIFORM_BUFFER, 64, 64, glm.value_ptr(projection_matrix))
        glBindBuffer(GL_UNIFORM_BUFFER, 0)

        glPolygonMode(GL_FRONT_AND_BACK, GL_LINE if Application.view_mode == "WIREFRAME" else GL_FILL)

        shader_program = shaders["DEFAULT"]
        shader_program_axis = shaders["AXIS"]
        if Application.view_mode == "NORMAL":
            shader_program = shaders["NORMAL"]
        elif Application.view_mode == "UV":
            shader_program = shaders["UV"]

        glUseProgram(shader_program.active_shader)

        model_location = glGetUniformLocation(shader_program.active_shader, "model_Transform")
        glUniformMatrix4fv(model_location, 1, GL_FALSE, glm.value_ptr(world_matrix))

        model_location = glGetUniformLocation(shader_program.active_shader, "model_Color")
        glUniform3f(model_location, *Application.model_color)

        glBindVertexArray(loaded_model.vao)
        glDrawElements(GL_TRIANGLES, len(loaded_model.indices), GL_UNSIGNED_INT, None)

        glUseProgram(shader_program_axis.active_shader)

        model_location = glGetUniformLocation(shader_program_axis.active_shader, "model_Transform")
        glUniformMatrix4fv(model_location, 1, GL_FALSE, glm.value_ptr(world_matrix))

        glBindVertexArray(model_axis.vao)
        glDrawElements(GL_LINES, len(model_axis.indices), GL_UNSIGNED_INT, None)

        imgui.render()
        impl.render(imgui.get_draw_data())

        glfw.swap_buffers(window)

    impl.shutdown()
    glfw.terminate()


def impl_glfw_init():
    width, height = 1280, 720
    window_name = "VistAsset 3D"

    if not glfw.init():
        logging.error("Could not initialize OpenGL context")
        sys.exit(1)

    # OS X supports only forward-compatible core profiles from 3.2
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, GL_TRUE)

    # Enable Multi-Sample Anti-Aliasing
    glfw.window_hint(glfw.SAMPLES, 8)

    # Create a windowed mode window and its OpenGL context
    window = glfw.create_window(int(width), int(height), window_name, None, None)
    glfw.make_context_current(window)

    if not window:
        glfw.terminate()
        logging.error("Could not initialize Window")
        sys.exit(1)

    return window


if __name__ == "__main__":
    main()