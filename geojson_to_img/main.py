import json
import math
import requests
import os

from .point import Point
from .bounds import Bounds

from wand.image import Image
from wand.drawing import Drawing
from wand.display import display
from wand.color import Color
import numpy as np

import logging
log = logging.getLogger(__name__)

class Render:
    def __init__(self, geojson, width=1024, height=1024):
        self.minxtile = 0
        self.minytile = 0

        self.number_of_rows = 0
        self.number_of_cols = 0

        self.rendering_zoom = 13
        self.tile_provider = "OSM"
        self.square_rendering = False
        self.center = 0
        self.stroke_width = 3

        self.render_width = int(width)
        self.render_height = int(height)

        self.width_in_pixel = 0
        self.height_in_pixel = 0

        self.bounds = ""
        self.rendering_bounds = ""

        self.tile_cache_path = "./cache"
        self.cache_path = ""

        self.img = ""

        self.debug = False

        self.render_quality = 90

        self.geojson = json.loads(geojson)

        self.prepare()

    def init_cache(self):
        self.cache_path = self.get_cache_path()

        if not os.path.isdir(self.cache_path):
            os.makedirs(self.cache_path)

    def get_cache_path(self):
        return "%s/%s/%s" % (
            self.tile_cache_path,
            self.tile_provider,
            self.rendering_zoom,
        )

    def get_tile(self, tile):
        tile_path = "%s/%s/%s.png" % (self.cache_path, tile[0], tile[1])

        if not os.path.exists(tile_path):

            tile_dir = os.path.dirname(tile_path)

            if not os.path.isdir(tile_dir):
                os.makedirs(tile_dir)

            url = self.get_tile_url(tile)
            response = requests.get(url)
            f = open(tile_path, "wb+")
            f.write(response.content)

        f = open(tile_path, "rb")
        return f

    def prepare(self):
        self.get_bounds()
        self.define_zoom_level()
        self.get_rendering_bounds()
        self.init_cache()

    def process(self):
        tiles = self.get_tiles_for_bounds()
        self.generate_background(tiles)
        return self.generate_track()

    def define_zoom_level(self):
        """
        Define the best zoom level giving the specified size
        for the image. Starting from the higher zoom level (18)
        then decrementing to get the best level.
        """

        self.rendering_zoom = 18
        self.get_size_from_bounds_and_zoom_level()

        while (
            self.width_in_pixel > self.render_width
            or self.height_in_pixel > self.render_height
        ) and self.rendering_zoom > 1:
            self.rendering_zoom = self.rendering_zoom - 1
            self.get_size_from_bounds_and_zoom_level()
            log.debug("define_zoom_level w: %s, h: %s, z: %s" % (
                self.width_in_pixel,
                self.height_in_pixel,
                self.rendering_zoom,
            ))

    def get_bounds(self):

        my_max = np.max(self.geojson["coordinates"], axis=0)
        max_lon = my_max[0]
        max_lat = my_max[1]

        my_min = np.min(self.geojson["coordinates"], axis=0)
        min_lon = my_min[0]
        min_lat = my_min[1]

        self.bounds = Bounds(min_lon, max_lon, min_lat, max_lat)

    def get_rendering_bounds(self):

        center_lat = (self.bounds.se.lat + self.bounds.nw.lat) / 2.0
        center_lon = (self.bounds.se.lon + self.bounds.nw.lon) / 2.0
        center = Point(center_lon, center_lat)
        center.project(self.rendering_zoom)
        self.center = center

        top_left_x = center.x - (self.render_width / 2.0)
        top_left_y = center.y - (self.render_height / 2.0)
        top_left = Point.from_xy(top_left_x, top_left_y)
        top_left.unproject(self.rendering_zoom)

        bottom_x = center.x + (self.render_width / 2.0)
        bottom_y = center.y + (self.render_height / 2.0)
        bottom_right = Point.from_xy(bottom_x, bottom_y)
        bottom_right.unproject(self.rendering_zoom)

        self.rendering_bounds = Bounds(
            top_left.lon, bottom_right.lon, bottom_right.lat, top_left.lat
        )

        log.debug(self.rendering_bounds)

    def get_size_from_bounds_and_zoom_level(self):

        # top left point
        top_left = Point(self.bounds.nw.lon, self.bounds.nw.lat)
        top_left.project(self.rendering_zoom)

        # top right point
        top_right = Point(self.bounds.se.lon, self.bounds.nw.lat)
        top_right.project(self.rendering_zoom)

        # calculate width in px
        width = math.fabs(top_left.x - top_right.x)

        # bottom left point
        bottom_left = Point(self.bounds.nw.lon, self.bounds.se.lat)
        bottom_left.project(self.rendering_zoom)

        # calculte height in px
        height = math.fabs(top_left.y - bottom_left.y)

        self.width_in_pixel = width
        self.height_in_pixel = height

    def get_tiles_for_bounds(self):
        """
        Returns a matrix of tile corresponding to the bounds
        """
        self.rendering_bounds.nw.project(self.rendering_zoom)
        self.rendering_bounds.se.project(self.rendering_zoom)

        nw_tile_x, nw_tile_y = self.rendering_bounds.nw.get_tile()
        se_tile_x, se_tile_y = self.rendering_bounds.se.get_tile()

        x = [int(nw_tile_x), int(se_tile_x)]
        x.sort()
        y = [int(nw_tile_y), int(se_tile_y)]
        y.sort()

        # Create the range of the tiles
        tile_x_range = list(range(x[0], x[1] + 1))
        tile_y_range = list(range(y[0], y[1] + 1))

        self.number_of_cols = len(tile_x_range)
        self.number_of_rows = len(tile_y_range)
        self.minxtile = tile_x_range[0]
        self.minytile = tile_y_range[0]

        i = 0

        # Create a Matrix of tiles
        matrix = [
            [0 for x in range(self.number_of_cols)] for y in range(self.number_of_rows)
        ]

        # Loop over the rows (y tiles)
        for y_tile in tile_y_range:
            j = 0
            # Loop over the columns (x tiles)
            for x_tile in tile_x_range:
                matrix[i][j] = [x_tile, y_tile]
                # increment the columns
                j += 1
            # increment lines
            i += 1

        return matrix

    def generate_background(self, tiles):
        """
        Displays the tiles on the background
        """

        self.img = Image(
            width=self.number_of_cols * 256, height=self.number_of_rows * 256
        )

        current_row = 0

        for row in tiles:
            current_col = 0
            for tile in row:
                response = self.get_tile(tile)
                try:
                    with Image(file=response) as tile_img:
                        draw = Drawing()
                        draw.composite(
                            operator="modulus_add",
                            left=current_col * 256,
                            top=current_row * 256,
                            width=tile_img.width,
                            height=tile_img.height,
                            image=tile_img,
                        )
                        draw(self.img)
                finally:
                    response.close()

                current_col += 1

            current_row += 1

    def get_tile_url(self, tile):
        """
        Returns the url for a specified tile
        """
        return "https://tile.openstreetmap.org/%s/%s/%s.png" % (
            self.rendering_zoom,
            tile[0],
            tile[1],
        )

    def generate_track(self):

        draw = Drawing()
        draw.stroke_width = 2
        draw.stroke_color = Color("red")
        draw.fill_color = Color("transparent")

        points = []

        # Loop over the coordinates to create a list of tuples
        for coords in self.geojson["coordinates"]:
            pt = Point(coords[0], coords[1])
            pt.project(self.rendering_zoom)
            x, y = pt.get_xy()
            x = round(x - (self.minxtile * 256))
            y = round(y - (self.minytile * 256))
            points.append((x, y))

        # draw the polyline
        draw.polyline(points)

        # apply to the image
        draw(self.img)

        # self.rendering_bounds.nw.project(self.rendering_zoom)
        x = int(self.rendering_bounds.nw.tile_x - self.minxtile)
        y = int(self.rendering_bounds.nw.tile_y - self.minytile)

        self.crop(x, y)
        self.img.format = "jpeg"
        # self.img.save(filename='image.jpg')
        return self.img.make_blob("jpeg")

    def crop(self, x, y):
        x = self.rendering_bounds.nw.x - (self.minxtile * 256)
        y = self.rendering_bounds.nw.y - (self.minytile * 256)
        self.img.crop(
            int(x), int(y), width=self.render_width, height=self.render_height
        )
