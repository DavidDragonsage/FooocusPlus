import os
import sys
from common import ROOT
from enhanced.translator import interpret

path_root = ROOT

def init_module(file_path):
    module_root = os.path.dirname(file_path)
    sys.path.append(module_root)
    module_name = os.path.relpath(module_root, os.path.dirname(os.path.abspath(__file__)))
    if module_name == "OneButtonPrompt":
        interpret(f'[{module_name}] Initializing the Random Prompt custom module')
    else:
        interpret(f'[{module_name}] Initializing the {module_name} custom module')
    return module_name, module_root
