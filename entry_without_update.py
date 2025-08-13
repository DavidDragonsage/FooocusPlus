import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.append(str(ROOT))
os.chdir(ROOT)
print(f'ROOT {ROOT}')

print('Loading FooocusPlus without updating...')

from launch import *
