#!/usr/bin/env python

# Copyright (c) 2019 Computer Vision Center (CVC) at the Universitat Autonoma de
# Barcelona (UAB).
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

# Allows visualising a 2D map generated by vehicles.

"""
Welcome to CARLA No Rendering Mode Visualizer
    H           : Hero Mode
    ESC         : quit
"""

# ==============================================================================
# -- find carla module ---------------------------------------------------------
# ==============================================================================

import glob
import os
import sys

try:
    sys.path.append(glob.glob('**/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass

# ==============================================================================
# -- imports -------------------------------------------------------------------
# ==============================================================================
import carla

import argparse
import logging
import weakref
import math
import random

try:
    import pygame
    from pygame import gfxdraw
    from pygame.locals import K_a
    from pygame.locals import K_h
    from pygame.locals import K_i
    from pygame.locals import K_DOWN
    from pygame.locals import K_LEFT
    from pygame.locals import K_RIGHT
    from pygame.locals import K_UP
    from pygame.locals import K_ESCAPE
except ImportError:
    raise RuntimeError('cannot import pygame, make sure pygame package is installed')


# ==============================================================================
# -- Constants -----------------------------------------------------------------
# ==============================================================================

# Colors
COLOR_RED = pygame.Color(255, 0, 0)
COLOR_BLUE = pygame.Color(0, 0, 255)
COLOR_GREEN = pygame.Color(0, 255, 0)
COLOR_YELLOW = pygame.Color(255, 255, 0)
COLOR_MAGENTA = pygame.Color(255, 0, 255)
COLOR_CYAN = pygame.Color(0, 255, 255)
COLOR_WHITE = pygame.Color(255, 255, 255)
COLOR_BLACK = pygame.Color(0, 0, 0)
COLOR_GREY = pygame.Color(127, 127, 127)
COLOR_LIGHT_GREY = pygame.Color(200, 200, 200)
COLOR_DARK_GREY = pygame.Color(50, 50, 50)
COLOR_ORANGE = pygame.Color(255, 127, 0)

# Legend names
LEGEND_NAME = 'LEGEND'
VEHICLE_NAME = 'Vehicle'
TRAFFIC_LIGHT_NAME = 'Traffic Light'
SPEED_LIMIT_NAME = 'Speed Limit'
WALKER_NAME = 'Walker'

# Module Defines
MODULE_WORLD = 'WORLD'
MODULE_HUD = 'HUD'
MODULE_INPUT = 'INPUT'
MODULE_RENDER = 'RENDER'

# ==============================================================================
# -- TransformHelper -----------------------------------------------------------
# ==============================================================================


class TransformHelper(object):

    def __init__(self, min_map_point, max_map_point, map_size):
        self.min_map_point = min_map_point
        self.max_map_point = max_map_point
        self.map_size = map_size

    def convert_world_to_screen_point(self, point):
        return (int(float(point[0] - self.min_map_point[0]) / float((self.max_map_point[0] - self.min_map_point[0])) * self.map_size),
                int(float(point[1] - self.min_map_point[1]) / float((self.max_map_point[1] - self.min_map_point[1])) * self.map_size))

    def convert_world_to_screen_size(self, size):
        return (int(size[0] / float((self.max_map_point[0] - self.min_map_point[0])) * self.map_size),
                int(size[1] / float((self.max_map_point[1] - self.min_map_point[1])) * self.map_size))


# ==============================================================================
# -- Vehicle ----------------------------------------------------------------------
# ==============================================================================

class Vehicle(object):

    def __init__(self, actor, color, map_transform_helper):
        self.actor = actor
        self.color = color
        self.map_transform_helper = map_transform_helper

        # Compute bounding box points
        bb_extent = self.actor.bounding_box.extent

        original_size = [bb_extent.x * 2.0, bb_extent.y * 2.0]

        converted_size = map_transform_helper.convert_world_to_screen_size(original_size)

        arrow_width = 2

        self.color = color
        self.surface_size = (max(converted_size[0], 1), max(converted_size[1], 1))
        arrow_size = max(self.surface_size[0] / 2, 1)

        self.surface = pygame.Surface((self.surface_size[0], self.surface_size[1]), pygame.SRCALPHA)
        self.surface.set_colorkey(COLOR_BLACK)

        pygame.draw.polygon(self.surface, color, [(0,0), (self.surface_size[0],0), (self.surface_size[0], self.surface_size[1]),(0, self.surface_size[1])] )
        render_module = module_manager.get_module(MODULE_RENDER)

        center = (self.surface_size[0]/2, self.surface_size[1] / 2)
        arrow_tip = (self.surface_size[0], self.surface_size[1] / 2)
        arrow_half = self.surface_size[1] / 2 + arrow_tip[0] / 2

        render_module.drawLine(self.surface, COLOR_BLUE, False, [center, arrow_tip], arrow_width)
        render_module.drawLine(self.surface, COLOR_BLUE, False, [arrow_tip, (arrow_half-1, 0)], arrow_width)
        render_module.drawLine(self.surface, COLOR_BLUE, False, [arrow_tip, (arrow_half-1, self.surface_size[1])], arrow_width)

    def render(self, display):
        actor_location=self.actor.get_location()

        x, y=self.map_transform_helper.convert_world_to_screen_point((actor_location.x, actor_location.y))

        rotate_surface=pygame.transform.rotate(self.surface, -self.actor.get_transform().rotation.yaw)

        display.blit(rotate_surface, (x, y))


class TrafficLight(object):
    def __init__(self, actor, radius, map_transform_helper):
        self.actor=actor

        actor_location=actor.get_location()
        self.x, self.y=map_transform_helper.convert_world_to_screen_point((actor_location.x, actor_location.y))

        self.color=COLOR_BLACK
        if 'traffic_light' in actor.type_id:
            if actor.state == carla.libcarla.TrafficLightState.Green:
                color=COLOR_GREEN
            elif actor.state == carla.libcarla.TrafficLightState.Yellow:
                color=COLOR_YELLOW
            elif actor.state == carla.libcarla.TrafficLightState.Red:
                color=COLOR_RED

        self.surface=pygame.Surface((radius * 2, radius * 2))
        pygame.draw.circle(self.surface, color, (radius, radius), radius)

    def render(self, display):
        display.blit(self.surface, (self.x, self.y))


class SpeedLimit(object):
    def __init__(self, actor, radius, map_transform_helper):
        self.actor=actor

        actor_location=actor.get_location()
        self.x, self.y=map_transform_helper.convert_world_to_screen_point((actor_location.x, actor_location.y))

        self.color=COLOR_BLUE
        self.surface=pygame.Surface((radius * 2, radius * 2))
        pygame.draw.circle(self.surface, self.color, (radius, radius), radius)

    def render(self, display):
        display.blit(self.surface, (self.x, self.y))


class Walker(object):
    def __init__(self, actor, radius, map_transform_helper):
        self.actor=actor

        actor_location=actor.get_location()
        self.x, self.y=map_transform_helper.convert_world_to_screen_point((actor_location.x, actor_location.y))

        self.color=COLOR_WHITE
        self.surface=pygame.Surface((radius * 2, radius * 2))
        pygame.draw.circle(self.surface, self.color, (radius, radius), radius)

    def render(self, display):
        display.blit(self.surface, (self.x, self.y))


class RenderShape(object):
    @staticmethod
    def render_vehicles(render_module, surface, list_actors, color, map_transform_helper):
        for actor in list_actors:
            vehicle_render=Vehicle(actor, color, map_transform_helper)
            vehicle_render.render(surface)

    @staticmethod
    def render_traffic_lights(render_module, surface, list_actors, color, radius, map_transform_helper):
        for actor in list_actors:
            traffic_light_render=TrafficLight(actor, radius, map_transform_helper)
            traffic_light_render.render(surface)

    @staticmethod
    def render_walkers(render_module, surface, list_actors, color, radius, map_transform_helper):
        for actor in list_actors:
            walker_render=Walker(actor, radius, map_transform_helper)
            walker_render.render(surface)

    @staticmethod
    def render_speed_limits(render_module, surface, list_actors, color, radius, map_transform_helper):
        for actor in list_actors:
            speed_limit_render=SpeedLimit(actor, radius, map_transform_helper)
            speed_limit_render.render(surface)

# ==============================================================================
# -- ModuleManager -------------------------------------------------------------
# ==============================================================================


class ModuleManager(object):
    def __init__(self):
        self.modules=[]

    def register_module(self, module):
        self.modules.append(module)

    def clear_modules(self):
        del self.modules[:]

    def tick(self, clock):
        # Update all the modules
        for module in self.modules:
            module.tick(clock)

    def render(self, display):
        display.fill((0, 0, 0))
        for module in self.modules:
            module.render(display)

    def get_module(self, name):
        for module in self.modules:
            if module.name == name:
                return module

    def start_modules(self):
        for module in self.modules:
            module.start()


# ==============================================================================
# -- ModuleRender -------------------------------------------------------------
# ==============================================================================
class ModuleRender(object):
    def __init__(self, name, antialiasing):
        self.name=name
        self.antialiasing=antialiasing

    def start(self):
        pass

    def render(self, display):
        pass

    def tick(self, clock):

        text_antialiasing=''
        if self.antialiasing:
            text_antialiasing='ON'
        else:
            text_antialiasing='OFF'

        module_info_text=[
            'Anti-aliasing:           % 3s' % text_antialiasing,
        ]
        module_hud = module_manager.get_module(MODULE_HUD)
        module_hud.add_info(self.name, module_info_text)

    def drawLineList(self, surface, color, closed, list_lines, width):
        for line in list_lines:
            if not self.antialiasing:
                self.drawLine(surface, color, closed, line, width)
            else:
                self.drawLineAA(surface, color, closed, line, width)

    def drawLine(self, surface, color, closed, line, width):
        if not self.antialiasing:
            self._drawLine(surface, color, closed, line, width)
        else:
            self._drawLineAA(surface, color, closed, line, width)

    def drawLineWithBorder(self, surface, color, closed, line, width, border, color_border):
        if not self.antialiasing:
            self._drawLine(surface, color_border, closed, line, width + border)
            self._drawLine(surface, color, closed, line, width)
        else:
            self._drawLineAA(surface, color_border, closed, line, width + border)
            self._drawLineAA(surface, color, closed, line, width)

    def _drawLine(self, surface, color, closed, line, width):
        pygame.draw.lines(surface, color, closed, line, width)

    def _drawLineAA(self, surface, color, closed, line, width):
        p0 = line[0]
        p1 = line[1]

        center_line_x = (p0[0]+p1[0])/2
        center_line_y = (p0[1]+p1[1])/2
        center_line = [center_line_x, center_line_y]

        length = 10  # Line size
        half_length = length / 2.

        half_width = width / 2.

        angle = math.atan2(p0[1] - p1[1], p0[0] - p1[0])
        sin_angle = math.sin(angle)
        cos_angle = math.cos(angle)

        half_length_cos_angle = (half_length) * cos_angle
        half_length_sin_angle = (half_length) * sin_angle
        half_width_cos_angle = (half_width) * cos_angle
        half_width_sin_angle = (half_width) * sin_angle

        UL = (center_line[0] + half_length_cos_angle - half_width_sin_angle,
              center_line[1] + half_width_cos_angle + half_length_sin_angle)
        UR=(center_line[0] - half_length_cos_angle - half_width_sin_angle,
              center_line[1] + half_width_cos_angle - half_length_sin_angle)
        BL=(center_line[0] + half_length_cos_angle + half_width_sin_angle,
              center_line[1] - half_width_cos_angle + half_length_sin_angle)
        BR=(center_line[0] - half_length_cos_angle + half_width_sin_angle,
              center_line[1] - half_width_cos_angle - half_length_sin_angle)

        pygame.gfxdraw.aapolygon(surface, (UL, UR, BR, BL), color)
        pygame.gfxdraw.filled_polygon(surface, (UL, UR, BR, BL), color)

    def drawCircle(self, surface, x, y, radius, color):
        if not self.antialiasing:
            self._drawCircle(surface, x, y, radius, color)
        else:
            self._drawCircleAA(surface, x, y, radius, color)

    def _drawCircle(self, surface, x, y, radius, color):
        pygame.draw.circle(surface, color, (x, y), radius)

    def _drawCircleAA(self, surface, x, y, radius, color):
        pygame.gfxdraw.aacircle(surface, x, y, radius, color)
        pygame.gfxdraw.filled_circle(surface, x, y, radius, color)

# ==============================================================================
# -- HUD -----------------------------------------------------------------------
# ==============================================================================


class Legend(object):
    def __init__(self, list_keys, header_font, font):
        self.header_surface=header_font.render(LEGEND_NAME, True, COLOR_LIGHT_GREY)

        self.legend_surfaces=[]
        self.surface_size=25

        for key in list_keys:
            color_surface=pygame.Surface((self.surface_size, self.surface_size))
            color_surface.fill(key[0])

            font_surface=font.render(key[1], True, COLOR_LIGHT_GREY)

            self.legend_surfaces.append((color_surface, font_surface))

    def render(self, display):

        h_offset=20
        v_offset=200 + 25 + 10
        h_space=10

        display.blit(self.header_surface, (8 + 100 / 2, v_offset))

        for surface in self.legend_surfaces:
            v_offset=v_offset + surface[0].get_height() + 10
            display.blit(surface[0], (h_offset, v_offset))
            display.blit(surface[1], (surface[0].get_width() + h_offset + h_space, v_offset + 5))


class ModuleHUD (object):

    def __init__(self, name, width, height):
        self.name=name
        self._init_hud_params()
        self._init_data_params(width, height)

    def start(self):
        pass

    def _init_hud_params(self):
        font=pygame.font.Font(pygame.font.get_default_font(), 20)
        fonts=[x for x in pygame.font.get_fonts() if 'mono' in x]
        default_font='ubuntumono'
        mono=default_font if default_font in fonts else fonts[0]
        mono=pygame.font.match_font(mono)
        self._font_mono=pygame.font.Font(mono, 14)
        self._header_font=pygame.font.SysFont('Arial', 14)

    def _init_data_params(self, height, width):
        self.dim=(height, width)
        self._show_info=True
        self._info_text={}
        self.legend=Legend(((COLOR_MAGENTA, VEHICLE_NAME),
                              (COLOR_BLUE, SPEED_LIMIT_NAME),
                              (COLOR_WHITE, WALKER_NAME)),
                             self._header_font,
                             self._font_mono)

    def tick(self, clock):
        if not self._show_info:
            return

    def add_info(self, module_name, info):
        self._info_text[module_name]=info

    def renderActorId(self, display, list_actors, transform_helper, translation_offset):
        if self._show_info:
            v_offset=4
            for actor in list_actors:
                location=actor.get_location()
                x, y=transform_helper.convert_world_to_screen_point((location.x, location.y - v_offset))

                color_surface=pygame.Surface((len(str(actor.id)) * 8, 14))
                color_surface.set_alpha(150)
                color_surface.fill(COLOR_BLACK)

                display.blit(color_surface, (x + translation_offset[0], y + translation_offset[1]))
                font_surface=self._font_mono.render(str(actor.id), True, COLOR_LIGHT_GREY)
                font_surface.set_colorkey(COLOR_BLACK)
                display.blit(font_surface, (x + translation_offset[0], y + translation_offset[1]))

    def render(self, display):
        if self._show_info:
            info_surface=pygame.Surface((240, self.dim[1]))
            info_surface.set_alpha(100)
            display.blit(info_surface, (0, 0))
            v_offset=4
            bar_h_offset=100
            bar_width=106
            i=0
            for module_name, module_info in self._info_text.items():
                surface=self._header_font.render(module_name, True, COLOR_LIGHT_GREY)
                display.blit(surface, (8 + bar_width / 2, 18 * i + v_offset))
                i += 1
                for item in module_info:
                    if v_offset + 18 > self.dim[1]:
                        break
                    if isinstance(item, list):
                        if len(item) > 1:
                            points=[(x + 8, v_offset + 8 + (1.0 - y) * 30) for x, y in enumerate(item)]
                            pygame.draw.lines(display, (255, 136, 0), False, points, 2)
                        item=None
                        v_offset += 18
                    elif isinstance(item, tuple):
                        if isinstance(item[1], bool):
                            rect=pygame.Rect((bar_h_offset, v_offset + 8), (6, 6))
                            pygame.draw.rect(display, COLOR_WHITE, rect, 0 if item[1] else 1)
                        else:
                            rect_border=pygame.Rect((bar_h_offset, v_offset + 8), (bar_width, 6))
                            pygame.draw.rect(display, COLOR_WHITE, rect_border, 1)
                            f=(item[1] - item[2]) / (item[3] - item[2])
                            if item[2] < 0.0:
                                rect=pygame.Rect((bar_h_offset + f * (bar_width - 6), v_offset + 8), (6, 6))
                            else:
                                rect=pygame.Rect((bar_h_offset, v_offset + 8), (f * bar_width, 6))
                            pygame.draw.rect(display, COLOR_WHITE, rect)
                        item=item[0]
                    if item:  # At this point has to be a str.
                        surface=self._font_mono.render(item, True, COLOR_WHITE)
                        display.blit(surface, (8, 18 * i + v_offset))
                    v_offset += 18
            self.legend.render(display)

# ==============================================================================
# -- World ---------------------------------------------------------------------
# ==============================================================================


class ModuleWorld(object):

    def __init__(self, name, host, port, timeout):
        self.name=name
        self.host=host
        self.port=port
        self.timeout=timeout
        self.server_fps=0
        self.server_clock=pygame.time.Clock()

    def _get_data_from_carla(self, host, port, timeout):
        try:
            client=carla.Client(host, port)
            client.set_timeout(timeout)

            world=client.get_world()
            town_map=world.get_map()
            actors=world.get_actors()
            return (world, town_map, actors)

        except Exception as ex:
            logging.error(ex)
            exit_game()

    def _create_world_surfaces(self):
        self.map_surface=pygame.Surface((self.surface_size, self.surface_size))

        self.vehicles_surface=pygame.Surface((self.surface_size, self.surface_size))
        self.vehicles_surface.set_colorkey((0, 0, 0))

        self.traffic_light_surface=pygame.Surface((self.surface_size, self.surface_size))
        self.traffic_light_surface.set_colorkey((0, 0, 0))

        self.speed_limits_surface=pygame.Surface((self.surface_size, self.surface_size))
        self.speed_limits_surface.set_colorkey((0, 0, 0))

        self.walkers_surface=pygame.Surface((self.surface_size, self.surface_size))
        self.walkers_surface.set_colorkey((0, 0, 0))

    def _compute_map_bounding_box(self, map_waypoints):

        x_min=float('inf')
        y_min=float('inf')
        x_max=0
        y_max=0

        for waypoint in map_waypoints:
            x_max=max(x_max, waypoint.transform.location.x)
            x_min=min(x_min, waypoint.transform.location.x)

            y_max=max(y_max, waypoint.transform.location.y)
            y_min=min(y_min, waypoint.transform.location.y)

        return (x_min, y_min, x_max, y_max)

    def start(self):
        self.world, self.town_map, self.actors=self._get_data_from_carla(self.host, self.port, self.timeout)

        # Store necessary modules
        self.hud_module=module_manager.get_module(MODULE_HUD)
        self.module_input=module_manager.get_module(MODULE_INPUT)

        self.surface_size=min(self.hud_module.dim[0], self.hud_module.dim[1])

        self._create_world_surfaces()

        # Generate waypoints
        waypoint_length=2.0
        map_waypoints=self.town_map.generate_waypoints(waypoint_length)

        # compute bounding boxes
        self.x_min, self.y_min, self.x_max, self.y_max=self._compute_map_bounding_box(map_waypoints)

        # Feed map bounding box and surface size to transform helper
        self.transform_helper=TransformHelper((self.x_min, self.y_min), (self.x_max, self.y_max), self.surface_size)

        # Retrieve data from waypoints orientation, width and length and do conversions into another list
        self.normalized_point_list = []
        self.intersection_waypoints = []
        for waypoint in map_waypoints:

            # Width of road
            width=self.transform_helper.convert_world_to_screen_size((waypoint.lane_width, waypoint.lane_width))[0]

            direction=(1, 0)
            yaw=math.radians(waypoint.transform.rotation.yaw)
            # Waypoint front
            wf=(direction[0] * math.cos(yaw) - direction[1] * math.sin(yaw),
                  direction[0] * math.sin(yaw) + direction[1] * math.cos(yaw))

            wp_0 = (waypoint.transform.location.x, waypoint.transform.location.y)
            wp_1 = (wp_0[0] + wf[0] * waypoint_length, wp_0[1] + wf[1] * waypoint_length)

            # Convert waypoints to screen space
            wp_0_screen = self.transform_helper.convert_world_to_screen_point(wp_0)
            wp_1_screen = self.transform_helper.convert_world_to_screen_point(wp_1)


            # Orientation of road
            color=COLOR_BLACK
            if waypoint.is_intersection:
                self.intersection_waypoints.append(((wp_0_screen, wp_1_screen), COLOR_DARK_GREY, width))
            else:
                self.normalized_point_list.append(((wp_0_screen, wp_1_screen), COLOR_DARK_GREY, width))

        # Module render
        self.render_module = module_manager.get_module(MODULE_RENDER)
        self.map_rendered = False

        # Hero actor
        self.filter_radius = 50
        self.hero_actor = None

        weak_self = weakref.ref(self)
        self.world.on_tick(lambda timestamp: ModuleWorld.on_world_tick(weak_self, timestamp))

    def select_random_hero(self):
        self.hero_actor = random.choice([actor for actor in self.actors if 'vehicle' in actor.type_id])

    def tick(self, clock):
        self.update_hud_info(clock)

    def update_hud_info(self, clock):
        hero_mode_text = []
        if self.hero_actor is not None:
            vehicle_name, vehicle_brand, vehicle_model = self.hero_actor.type_id.split('.')
            type_id_text = vehicle_brand + ' ' + vehicle_model

            hero_speed = self.hero_actor.get_velocity()
            hero_speed_text = math.sqrt(hero_speed.x ** 2 + hero_speed.y ** 2 + hero_speed.z ** 2)
            hero_mode_text = [
                'Hero Mode:               ON',
                'Hero ID:               %4d' % self.hero_actor.id,
                'Hero Type ID:%12s' % type_id_text,
                'Hero speed:          %3d km/h' % hero_speed_text
            ]
        else:
            hero_mode_text = ['Hero Mode:               OFF']

        module_info_text = [
            'Server:  % 16d FPS' % self.server_fps,
            'Client:  % 16d FPS' % clock.get_fps()
        ]

        module_info_text = module_info_text + hero_mode_text
        module_hud = module_manager.get_module(MODULE_HUD)
        module_hud.add_info(self.name, module_info_text)

    @staticmethod
    def on_world_tick(weak_self, timestamp):
        self = weak_self()
        if not self:
            return

        self.server_clock.tick()
        self.server_fps = self.server_clock.get_fps()

    def render_map(self, display):
        self.map_surface.fill(COLOR_GREY)
        for point in self.normalized_point_list:
            self.render_module.drawLineWithBorder(self.map_surface,
                                                  point[1],
                                                  False,
                                                  point[0],
                                                  point[2],
                                                  3,
                                                  COLOR_WHITE)

        for point in self.intersection_waypoints:
            self.render_module.drawLine(self.map_surface,
                                        point[1],
                                        False,
                                        point[0],
                                        point[2])

    def render_hero_actor(self, display, hero_actor, color, radius, translation_offset):

        hero_radius = self.filter_radius / float((self.x_max - self.x_min)) * self.surface_size
        hero_diameter = hero_radius * 2.0

        self.hero_actor_surface = pygame.Surface((hero_diameter, hero_diameter))
        self.hero_actor_surface.set_colorkey((0, 0, 0))
        self.hero_actor_surface.set_alpha(100)

        hero_actor_location = hero_actor.get_location()
        x, y = self.transform_helper.convert_world_to_screen_point((hero_actor_location.x, hero_actor_location.y))

        # Create surface with alpha for circle radius

        self.render_module.drawCircle(self.hero_actor_surface, int(hero_radius),
                                      int(hero_radius), int(hero_radius), COLOR_ORANGE)

        display.blit(self.hero_actor_surface, (x - int(hero_radius) + translation_offset[0],
                                               y - int(hero_radius) + translation_offset[1]))

    def is_actor_inside_hero_radius(self, actor):
        return math.sqrt((actor.get_location().x-self.hero_actor.get_location().x)**2
                + (actor.get_location().y - self.hero_actor.get_location().y)**2) <= self.filter_radius

    def _splitActors(self, actors):
        vehicles = []
        traffic_lights = []
        speed_limits = []
        walkers = []

        for actor in actors:
            if 'vehicle' in actor.type_id:
                vehicles.append(actor)
            elif 'traffic_light' in actor.type_id:
                traffic_lights.append(actor)
            elif 'speed_limit' in actor.type_id:
                speed_limits.append(actor)
            elif 'walker' in actor.type_id:
                walkers.append(actor)

        return (vehicles, traffic_lights, speed_limits, walkers)

    def render(self, display):

        if not self.map_rendered:
            self.render_map(display)
            self.map_rendered = True

        self.vehicles_surface.fill(COLOR_BLACK)
        self.traffic_light_surface.fill(COLOR_BLACK)
        self.speed_limits_surface.fill(COLOR_BLACK)
        self.walkers_surface.fill(COLOR_BLACK)

        vehicles, traffic_lights, speed_limits, walkers = self._splitActors(self.actors)

        if self.hero_actor is not None:
            vehicles = [vehicle for vehicle in vehicles if self.is_actor_inside_hero_radius(vehicle)]

            traffic_lights = [traffic_light for traffic_light in traffic_lights
                              if self.is_actor_inside_hero_radius(traffic_light)]

            speed_limits = [speed_limit for speed_limit in speed_limits
                            if self.is_actor_inside_hero_radius(speed_limit)]

        RenderShape.render_vehicles(self.render_module, self.vehicles_surface,
                                    vehicles, COLOR_MAGENTA, self.transform_helper)
        RenderShape.render_traffic_lights(self.render_module, self.traffic_light_surface, traffic_lights,
                                          COLOR_BLACK, 3, self.transform_helper)
        RenderShape.render_speed_limits(self.render_module, self.speed_limits_surface, speed_limits,
                                        COLOR_BLUE, 3, self.transform_helper)

        RenderShape.render_walkers(self.render_module, self.walkers_surface, walkers,
                                   COLOR_WHITE, 3, self.transform_helper)

        # Scale surfaces
        # scale_factor = (int(self.surface_size * module_input.wheel_offset[0]),
        #                 int(self.surface_size * module_input.wheel_offset[1]))
        # self.map_surface = pygame.transform.smoothscale(self.map_surface, scale_factor)
        # self.vehicles_surface = pygame.transform.smoothscale(self.vehicles_surface, scale_factor)
        # self.traffic_light_surface = pygame.transform.smoothscale(self.traffic_light_surface, scale_factor)
        # self.speed_limits_surface = pygame.transform.smoothscale(self.speed_limits_surface, scale_factor)

        # Translation offset
        if self.hero_actor is None:
            translation_offset = ((display.get_width() - self.surface_size)/2 +
                                  self.module_input.mouse_offset[0], self.module_input.mouse_offset[1])
        else:
            hero_location = (self.hero_actor.get_location().x, self.hero_actor.get_location().y)
            hero_location_screen = self.transform_helper.convert_world_to_screen_point(hero_location)
            translation_offset = ( -hero_location_screen[0] + display.get_width() / 2,
                                   (- hero_location_screen[1] + display.get_height() / 2) )

        # Blit surfaces
        display.blit(self.map_surface, translation_offset)
        display.blit(self.vehicles_surface, translation_offset)
        display.blit(self.traffic_light_surface, translation_offset)
        display.blit(self.speed_limits_surface, translation_offset)
        display.blit(self.walkers_surface, translation_offset)
        actor_id_surface = self.hud_module.renderActorId(display, vehicles, self.transform_helper, translation_offset)

        if self.hero_actor is not None:
            selected_hero_actor = [vehicle for vehicle in vehicles if vehicle.id == self.hero_actor.id]
            self.render_hero_actor(display, selected_hero_actor[0], COLOR_RED, 5, translation_offset)

        del vehicles[:]
        del traffic_lights[:]
        del speed_limits[:]
        del walkers[:]

# ==============================================================================
# -- Input -----------------------------------------------------------
# ==============================================================================


class ModuleInput(object):
    def __init__(self, name):
        self.name = name
        self.mouse_pos = (0, 0)
        self.mouse_offset = [0.0, 0.0]
        self.wheel_offset = [1.0, 1.0]
        self.wheel_amount = 0.1

    def start(self):
        pass

    def render(self, display):
        pass

    def tick(self, clock):
        self.parse_input()

    def _parse_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                exit_game()
            elif event.type == pygame.KEYUP:
                if event.key == K_ESCAPE:
                    exit_game()
                if event.key == K_a:
                    module_render = module_manager.get_module(MODULE_RENDER)
                    module_render.antialiasing = not module_render.antialiasing
                if event.key == K_h:
                    module_world = module_manager.get_module(MODULE_WORLD)
                    if module_world.hero_actor is None:
                        module_world.select_random_hero()
                    else:
                        module_world.hero_actor = None
                if event.key == K_i:
                    module_hud = module_manager.get_module(MODULE_HUD)
                    module_hud._show_info = not module_hud._show_info

            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.mouse_pos = pygame.mouse.get_pos()
                if event.button == 4:
                    self.wheel_offset[0] += self.wheel_amount
                    self.wheel_offset[1] += self.wheel_amount

                if event.button == 5:
                    self.wheel_offset[0] -= self.wheel_amount
                    self.wheel_offset[1] -= self.wheel_amount
                    if self.wheel_offset[0] <= 0.1:
                        self.wheel_offset[0] = 0.1
                    if self.wheel_offset[1] <= 0.1:
                        self.wheel_offset[1] = 0.1

    def _parse_keys(self):
        keys = pygame.key.get_pressed()
        # if keys[pygame.K_LEFT]:
        # Do something

    def _parse_mouse(self):
        if pygame.mouse.get_pressed()[0]:
            x, y = pygame.mouse.get_pos()
            self.mouse_offset[0] = self.mouse_offset[0] + x - self.mouse_pos[0]
            self.mouse_offset[1] += y - self.mouse_pos[1]
            self.mouse_pos = (x, y)

    def parse_input(self):
        self._parse_events()
        self._parse_keys()
        self._parse_mouse()


# ==============================================================================
# -- Global Objects ------------------------------------------------------------
# ==============================================================================
module_manager = ModuleManager()


# ==============================================================================
# -- Game Loop ---------------------------------------------------------------
# ==============================================================================


def game_loop(args):
    # Init Pygame
    pygame.init()
    display = pygame.display.set_mode(
        (args.width, args.height),
        pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption(args.description)

    # Init modules
    input_module = ModuleInput(MODULE_INPUT)
    hud_module = ModuleHUD(MODULE_HUD, args.width, args.height)
    world_module = ModuleWorld(MODULE_WORLD, args.host, args.port, 2.0)
    render_module = ModuleRender(MODULE_RENDER, bool(args.antialiasing == 'True'))

    # Register Modules
    module_manager.register_module(input_module)
    module_manager.register_module(render_module)
    module_manager.register_module(world_module)
    module_manager.register_module(hud_module)

    module_manager.start_modules()

    clock = pygame.time.Clock()
    while True:
        clock.tick_busy_loop(60)

        module_manager.tick(clock)
        module_manager.render(display)

        pygame.display.flip()


def exit_game():
    module_manager.clear_modules()
    pygame.quit()
    sys.exit()

# ==============================================================================
# -- Main --------------------------------------------------------------------
# ==============================================================================


def main():
    # Parse arguments
    argparser = argparse.ArgumentParser(
        description='CARLA No Rendering Mode Visualizer')
    argparser.add_argument(
        '-v', '--verbose',
        action='store_true',
        dest='debug',
        help='print debug information')
    argparser.add_argument(
        '--host',
        metavar='H',
        default='127.0.0.1',
        help='IP of the host server (default: 127.0.0.1)'
    )
    argparser.add_argument(
        '-p', '--port',
        metavar='P',
        default=2000,
        type=int,
        help='TCP port to listen to (default: 2000)')
    argparser.add_argument(
        '--res',
        metavar='WIDTHxHEIGHT',
        default='1280x720',
        help='window resolution (default: 1280x720)')

    argparser.add_argument(
        '--antialiasing',
        metavar='antialiasing',
        default=True,
        help='antialiasing (default: True)')
    args = argparser.parse_args()
    args.description = argparser.description
    args.width, args.height = [int(x) for x in args.res.split('x')]

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

    logging.info('listening to server %s:%s', args.host, args.port)
    print(__doc__)

    try:
        game_loop(args)
    except KeyboardInterrupt:
        print('\nCancelled by user. Bye!')


if __name__ == '__main__':
    main()
