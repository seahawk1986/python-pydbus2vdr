from distutils.core import setup
setup(name='pydbus2vdr',
      version='0.0.8',
      description='A module to communicate with vdr-plugin-dbus2vdr using pydbus',
      author='Alexander Grothe',
      author_email='seahawk1986@gmx.de',
      url='https://github.com/seahawk1986/python-pydbus2vdr',
      py_modules=['pydbus2vdr'],
      requires=['pydbus(>=0.6.0)'],
      )
