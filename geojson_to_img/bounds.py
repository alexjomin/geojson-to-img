from point import Point

class Bounds:
    	def __init__(self, min_lon, max_lon, min_lat, max_lat):
		self.nw = Point(min_lon, max_lat)
		self.se = Point(max_lon, min_lat)

	def __str__(self):
		return "nw: [%f,%f] - se: [%f,%f]" % (self.nw.lon, self.nw.lat, self.se.lon, self.se.lat)
