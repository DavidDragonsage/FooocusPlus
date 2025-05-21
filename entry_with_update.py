import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(ROOT)
os.chdir(ROOT)

print('Loading FooocusPlus without updating...')

from launch import *
