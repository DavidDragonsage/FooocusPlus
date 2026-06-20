@echo off
:: Please copy this file to the FooocusPlus directory to run it
:: FooocusPlus will run using CUDA 13 but the
:: NVIDIA video driver must be up-to-date for this to work
.\python_embedded\python.exe -s FooocusPlusAI\entry_with_update.py --gpu-type cu130 --language en %*
pause
