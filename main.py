import json
import math
import requests
import os
from urllib2 import urlopen


from point import Point

from wand.image import Image
from wand.drawing import Drawing
from wand.display import display
from wand.color import Color
import numpy as np

class Bounds:
	def __init__(self, min_lon, max_lon, min_lat, max_lat):
		self.nw = Point(min_lon, max_lat)
		self.se = Point(max_lon, min_lat)

	def __str__(self):
		return "nw: [%f,%f] - se: [%f,%f]" % (self.nw.lon, self.nw.lat, self.se.lon, self.se.lat)

class Render:
	def __init__(self):
		self.minxtile = 0
		self.minytile = 0

		self.number_of_rows = 0
		self.number_of_cols = 0

		self.rendering_zoom = 13
		self.tile_provider = 'OCM'
		self.square_rendering = False
		self.center = 0
		self.stroke_width = 3

		self.render_width = 1024
		self.render_height = 1024

		self.width_in_pixel = 0
		self.height_in_pixel = 0

		self.bounds = ''
		self.render_bounds = ''

		self.tile_cache_path = './cache'
		self.cache_path = ''

		self.img = ''

		self.debug = False

		self.render_quality = 90

		self.geojson = json.loads('{"type":"LineString","coordinates":[[5.412748,43.360318,258],[5.413958,43.366102,283],[5.412584,43.369715,302],[5.414469,43.370355,306],[5.413189,43.374368,335],[5.411554,43.375172,337],[5.413816,43.376519,356],[5.415824,43.380505,391],[5.416427,43.380085,393],[5.418586,43.38248,422],[5.420246,43.380303,447],[5.420494,43.383029,473],[5.422048,43.383886,489],[5.419287,43.385022,512],[5.419748,43.386111,523],[5.426246,43.384748,563],[5.427167,43.384946,565],[5.427374,43.386208,565],[5.429949,43.385184,568],[5.436618,43.388492,595],[5.437642,43.390197,614],[5.437807,43.393985,586],[5.439188,43.395814,624],[5.446777,43.397953,580],[5.450796,43.397511,572],[5.451464,43.395866,548],[5.450699,43.394891,550],[5.451553,43.393449,543],[5.454467,43.392593,534],[5.456006,43.391128,521],[5.455855,43.388559,521],[5.457382,43.385755,465],[5.456907,43.383438,431],[5.452229,43.385048,362],[5.448221,43.390924,400],[5.450078,43.38691,410],[5.449974,43.384266,414],[5.447448,43.384282,406],[5.445593,43.385385,407],[5.445908,43.383649,407],[5.443885,43.383301,405],[5.443694,43.381986,403],[5.441981,43.381899,401],[5.441585,43.381178,399],[5.439699,43.382995,391],[5.43815,43.38114,386],[5.436753,43.381281,384],[5.436337,43.379139,378],[5.43464,43.3793,374],[5.43288,43.378096,372],[5.430634,43.37923,393],[5.429847,43.380653,409],[5.428224,43.379003,422],[5.425607,43.380881,434],[5.423399,43.379416,436],[5.420329,43.380282,445],[5.420417,43.382886,469],[5.422077,43.383882,488],[5.419289,43.385033,508],[5.419745,43.386119,519],[5.426144,43.384786,559],[5.427193,43.385022,563],[5.427412,43.386262,561],[5.429191,43.385055,570],[5.431623,43.385971,563],[5.431737,43.384077,519],[5.433638,43.381662,461],[5.432576,43.381078,449],[5.431049,43.382019,436],[5.428138,43.378908,423],[5.428898,43.375145,368],[5.432677,43.3711,303],[5.42319,43.365812,248],[5.421966,43.366624,246],[5.421758,43.368688,259],[5.419097,43.364757,268],[5.417933,43.36567,245],[5.417683,43.363217,255],[5.413205,43.362457,260],[5.412824,43.360192,252]]}')

	def init_cache(self):
		self.cache_path = self.get_cache_path()

		if not os.path.isdir(self.cache_path):
			os.makedirs(self.cache_path)

	def get_cache_path(self):
		return "%s/%s/%s" % (self.tile_cache_path, self.tile_provider, self.rendering_zoom)

	def get_tile(self, tile):
		tile_path = "%s/%s/%s.png" % (self.cache_path, tile[0], tile[1])

		if not os.path.exists(tile_path) :

			tile_dir = os.path.dirname(tile_path)

			if not os.path.isdir(tile_dir):
				os.makedirs(os.path.dirname(tile_dir))

			url = self.get_tile_url(tile)
			response = urlopen(url)
			url = self.get_tile_url(tile)
			f = open(tile_path, 'w+')
			f.write(response.read())

		f = open(tile_path, 'r')
		return f


	def prepare(self):
		self.get_bounds()
		self.define_zoom_level()
		self.init_cache()
		tiles = self.get_tiles_for_bounds()
		self.generate_background(tiles)
		self.generate_track()

	def define_zoom_level(self) :
		"""
		Define the best zoom level giving the specified size
		for the image. Starting from the higher zoom level (18)
		then decrementing to get the best level.
		"""

		self.rendering_zoom = 18
		self.get_size_from_bounds_and_zoom_level()

		while (self.width_in_pixel > self.render_width or self.height_in_pixel > self.render_height) and self.rendering_zoom > 1 :
			self.rendering_zoom = self.rendering_zoom - 1
			self.get_size_from_bounds_and_zoom_level()
			print "define_zoom_level w: %s, h: %s, z: %s" % (self.width_in_pixel, self.height_in_pixel, self.rendering_zoom)


	def get_bounds(self):

		max = np.max(self.geojson['coordinates'], axis=0)
		max_lon = max[0]
		max_lat = max[1]
		max_ele = max[2]

		min = np.min(self.geojson['coordinates'], axis=0)
		min_lon = min[0]
		min_lat = min[1]
		min_ele = min[2]

		self.bounds = Bounds(min_lon, max_lon, min_lat, max_lat)

	def get_size_from_bounds_and_zoom_level(self):

		# top left point
		top_left = Point(self.bounds.nw.lon, self.bounds.nw.lat)
		top_left.project(self.rendering_zoom)

		# top right point
		top_right = Point(self.bounds.se.lon, self.bounds.nw.lat)
		top_right.project(self.rendering_zoom)

		# calculate width in px
		width = math.fabs(top_left.x-top_right.x)

		# bottom left point
		bottom_left = Point(self.bounds.nw.lon, self.bounds.se.lat)
		bottom_left.project(self.rendering_zoom)

		# calculte height in px
		height = math.fabs(top_left.y-bottom_left.y)

		self.width_in_pixel = width
		self.height_in_pixel = height

	def get_tiles_for_bounds(self):
		self.bounds.nw.project(self.rendering_zoom)
		self.bounds.se.project(self.rendering_zoom)

		nw_tile_x, nw_tile_y = self.bounds.nw.get_tile()
		se_tile_x, se_tile_y = self.bounds.se.get_tile()

		x = [int(nw_tile_x), int(se_tile_x)]
		x.sort()
		y = [int(nw_tile_y), int(se_tile_y)]
		y.sort()

		# Create the range of the tiles
		tile_x_range = range(x[0], x[1]+1)
		tile_y_range = range(y[0], y[1]+1)

		self.number_of_cols = len(tile_x_range)
		self.number_of_rows = len(tile_y_range)
		self.minxtile = tile_x_range[0]
		self.minytile = tile_y_range[0]

		i = 0

		# Create a Matrix of tiles
		matrix = [[0 for x in range(self.number_of_cols)] for y in range(self.number_of_rows)]

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

	def generate_background(self, tiles) :
		"""

		"""
		self.img = Image(width=self.number_of_cols*256, height=self.number_of_rows*256)

		current_row = 0

		for row in tiles :
			current_col = 0
			for tile in row:
				response = self.get_tile(tile)
				try:
					with Image(file=response) as tile_img:
						draw = Drawing()
						draw.composite(operator='add', left=current_col*256, top=current_row*256, width=tile_img.width, height=tile_img.height, image=tile_img)
						draw(self.img)
				finally:
					response.close()

				current_col += 1

			current_row += 1

	def get_tile_url(self, tile) :
		"""
			Returns the url for a specified tile
		"""
		return "http://tile.openstreetmap.org/%s/%s/%s.png" % (self.rendering_zoom, tile[0], tile[1])

	def generate_track(self) :

		draw = Drawing()
		draw.stroke_width = 2
		draw.stroke_color = Color('red')
		draw.fill_color = Color('transparent')

		points = []

		# Loop over the coordinates to create a list of tuples
		for coords in self.geojson['coordinates'] :
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

		self.img.format = 'jpeg'
		self.img.save(filename='image.jpg')

r = Render()
r.prepare()