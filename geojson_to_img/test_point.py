import math

p = Point(50.1345, 40.00123)
p.project(12)
print p.x, p.y

u = Point.from_xy(p.x, p.y)
print "tile %s %s" % (u.tile_x, u.tile_y)
u.unproject(12)
print u.lon, u.lat
