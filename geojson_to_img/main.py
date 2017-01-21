import json
import math
import requests
import os
from urllib2 import urlopen

from point import Point
from bounds import Bounds

from wand.image import Image
from wand.drawing import Drawing
from wand.display import display
from wand.color import Color
import numpy as np

class Render:
	def __init__(self, geojson):
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
		self.rendering_bounds = ''

		self.tile_cache_path = './cache'
		self.cache_path = ''

		self.img = ''

		self.debug = False

		self.render_quality = 90

		self.geojson = json.loads(geojson)

		self.prepare()

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
				os.makedirs(tile_dir)

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
		self.get_rendering_bounds()
		self.init_cache()

	def process(self):
		tiles = self.get_tiles_for_bounds()
		self.generate_background(tiles)
		return self.generate_track()

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

		self.rendering_bounds = Bounds(top_left.lon, bottom_right.lon, bottom_right.lat, top_left.lat)

		print self.rendering_bounds

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
			Displays the tiles on the background
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

		# self.rendering_bounds.nw.project(self.rendering_zoom)
		x = int(self.rendering_bounds.nw.tile_x - self.minxtile)
		y = int(self.rendering_bounds.nw.tile_y - self.minytile)

		self.crop(x, y)
		self.img.format = 'jpeg'
		# self.img.save(filename='image.jpg')
		return self.img.make_blob('jpeg')

	def crop(self, x, y):
		x = self.rendering_bounds.nw.x - (self.minxtile * 256)
		y = self.rendering_bounds.nw.y - (self.minytile * 256)
		self.img.crop(int(x), int(y), width=self.render_width, height=self.render_height)


geojson = '{"type":"LineString","coordinates":[[2.257921,48.585854,87.14],[2.258616,48.58588,87.14],[2.258009,48.587399,75.6],[2.255933,48.586365,77.52],[2.252881,48.586563,67.429688],[2.254731,48.584026,91.462524],[2.249013,48.58165,91.46],[2.250155,48.580166,95.788452],[2.250155,48.578194,97.23],[2.246867,48.57233,93.39],[2.246716,48.567307,93.385132],[2.247187,48.565968,92.42395],[2.24976,48.565639,93.39],[2.249126,48.562473,90.98],[2.252468,48.562332,88.098022],[2.261554,48.559189,89.54],[2.259115,48.554718,88.1],[2.258657,48.551525,86.66],[2.256686,48.547268,92.904541],[2.266251,48.544479,96.269287],[2.264871,48.5355,171.25],[2.253407,48.529675,155.870972],[2.256207,48.526997,136.16],[2.256166,48.526051,122.22],[2.260633,48.5242,82.81],[2.255459,48.520794,84.252686],[2.257162,48.520794,78.965454],[2.260557,48.517807,60.700317],[2.261719,48.518017,58.77771],[2.262251,48.517235,56.86],[2.26144,48.515873,54.451782],[2.262167,48.514187,69.83],[2.26533,48.514366,71.27],[2.267144,48.512749,107.805054],[2.264759,48.511009,129.92],[2.262028,48.510929,130.395996],[2.26254,48.510517,131.84],[2.262011,48.509945,130.4],[2.266171,48.506454,143.37],[2.268641,48.506084,142.89],[2.270881,48.503971,135.2],[2.274603,48.502544,100.595093],[2.284443,48.500984,95.79],[2.288828,48.499462,111.650269],[2.295648,48.49894,129.92],[2.295706,48.496822,129.434692],[2.300065,48.495159,146.257812],[2.298924,48.49194,124.147339],[2.296733,48.48975,125.589355],[2.294994,48.486404,137.13],[2.304065,48.489689,92.9],[2.309546,48.489311,92.9],[2.310527,48.491096,103],[2.313882,48.493557,119.34082],[2.315551,48.492172,123.67],[2.316283,48.489834,86.66],[2.318676,48.487129,75.60083],[2.320129,48.477085,71.755493],[2.316758,48.467232,52.53],[2.317126,48.464993,56.855103],[2.315828,48.46191,53.49],[2.309203,48.460445,82.330078],[2.303312,48.461594,82.330078],[2.303064,48.459511,109.727661],[2.302087,48.45834,106.84],[2.302731,48.45805,113.572998],[2.298962,48.455456,90.02063],[2.296376,48.452381,114.53],[2.292456,48.452435,109.727661],[2.29379,48.463356,142.41],[2.292526,48.464176,130.876709],[2.290077,48.464119,96.75],[2.285306,48.465878,76.56],[2.283852,48.467323,81.85],[2.281919,48.464127,76.08],[2.279932,48.463715,78.965454],[2.278615,48.46516,93.87],[2.27993,48.467308,77.52],[2.273735,48.468674,88.578735],[2.268601,48.468681,76.562134],[2.2659,48.467693,114.53418],[2.263837,48.468624,110.69],[2.263698,48.4701,138.09],[2.264757,48.471115,127.99],[2.26143,48.471588,146.257812],[2.261098,48.476135,127.03],[2.258926,48.479031,133.28],[2.249369,48.481361,113.09],[2.249262,48.483421,152.025757],[2.251955,48.490585,136.16394],[2.247646,48.491322,145.78],[2.245923,48.494232,141.45],[2.239716,48.495827,139.05],[2.236134,48.49485,108.285645],[2.22991,48.496372,66.95],[2.224106,48.495995,74.16],[2.223347,48.502495,65.03],[2.223939,48.504204,65.026367],[2.228047,48.509121,71.27],[2.231046,48.510242,65.99],[2.230958,48.514389,69.35],[2.228606,48.515476,72.72],[2.228993,48.516239,76.081421],[2.233336,48.515743,81.368774],[2.238067,48.516453,78.484741],[2.23988,48.518234,115.5],[2.238927,48.518494,122.71],[2.238696,48.519497,127.51],[2.243661,48.519737,124.63],[2.246068,48.520531,134.72],[2.245085,48.521606,146.738403],[2.251415,48.522869,137.125244],[2.249337,48.524574,154.91],[2.232823,48.528511,136.16],[2.233722,48.530617,136.16],[2.231045,48.531933,137.125244],[2.23351,48.535587,143.85],[2.233901,48.542492,106.36],[2.232919,48.54422,98.19],[2.237401,48.560692,85.69458],[2.239318,48.561951,83.771973],[2.244595,48.562588,84.733398],[2.24438,48.564308,85.69],[2.245322,48.565311,85.69458],[2.245424,48.567204,88.098022],[2.246701,48.567493,87.62],[2.246742,48.571846,89.539917],[2.247499,48.573772,85.69],[2.25386,48.573986,85.21],[2.255018,48.578632,87.62],[2.256348,48.580574,83.771973],[2.261783,48.581196,81.849365],[2.259968,48.584412,83.291382],[2.258076,48.585873,80.407471]]}'
r = Render(geojson)
i = r.process()

with open('out.jpg', 'wb+') as f:
	f.write(i)