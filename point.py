import math

class Point:
	"""
		https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames
	"""

	def __init__(self, lon, lat):
		self.lon = lon
		self.lat = lat
		self.x = 0
		self.y = 0
		self.tile_x = 0
		self.tile_y = 0

	@staticmethod
	def from_xy(cls, x, y):
		p = cls()
		p.x = x
		p.y = y
		return p

	def project(self, zoom_level):
		n = math.pow(2, zoom_level)

		self.tile_x = (self.lon + 180) / 360 * n

		lat_rad = math.radians(self.lat)
		self.tile_y = (1.0 - (math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi)) / 2 * n

		self.x = self.tile_x * 256
		self.y = self.tile_y * 256

	def unproject(self, zoom_level):
		n = math.pow(2, zoom_level)
  		self.lon = self.tile_x / n * 360.0 - 180.0
  		lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * self.tile_y / n)))
  		self.lat = math.degrees(lat_rad)

	def get_tile(self):
		return self.tile_x, self.tile_y

	def get_xy(self):
		return self.x, self.y

	def get_ll(self):
		return self.lon, self.lat

p = Point(50.1345, 40.00123)
p.project(12)
print p.x , p.y
p.unproject(12)
print p.lon, p.lat
