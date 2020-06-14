# from https://stackoverflow.com/a/31867043

import sys
import os
import inspect

print("Python " + sys.version)
print()

print(__file__ )                                       # main.py
print(sys.argv[0])                                     # main.py
print(inspect.stack()[0][1])                           # lib/bar.py
print(sys.path[0])                                     # C:\filepaths
print()

print(os.path.realpath(__file__))                      # C:\filepaths\main.py
print(os.path.abspath(__file__))                       # C:\filepaths\main.py
print(os.path.basename(__file__))                      # main.py
print(os.path.basename(os.path.realpath(sys.argv[0]))) # main.py
print()

print(sys.path[0])                                     # C:\filepaths
print(os.path.abspath(os.path.split(sys.argv[0])[0]))  # C:\filepaths
print(os.path.dirname(os.path.abspath(__file__)))      # C:\filepaths
print(os.path.dirname(os.path.realpath(sys.argv[0])))  # C:\filepaths
print(os.path.dirname(__file__))                       # (empty string)
print()

print(inspect.getfile(inspect.currentframe()))         # lib/bar.py

print(os.path.abspath(inspect.getfile(inspect.currentframe()))) # C:\filepaths\lib\bar.py
print(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))) # C:\filepaths\lib
print()

print(os.path.abspath(inspect.stack()[0][1]))          # C:\filepaths\lib\bar.py
print(os.path.dirname(os.path.abspath(inspect.stack()[0][1])))  # C:\filepaths\lib
print()