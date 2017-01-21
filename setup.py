from setuptools import setup

setup(name='geojson_to_img',
      version='0.1.0',
      description='Render a geojson linestring as an image',
      url='https://github.com/alexjomin/geojson-to-img',
      author='Alexandre Jomin',
      license='MIT',
      packages=['geojson_to_img'],
	  install_requires=[
          'wand','numpy','requests'
      ],
      zip_safe=False)