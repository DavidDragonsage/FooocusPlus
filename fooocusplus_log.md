# 0.9.7 Dev

* enabled automatic updating from the development (dev) branch
* removed offensive language from the One Button Prompt texts
* fully integrated the upscale or vary (UOV) sliders into normal operation
* the Vary (Subtle) and Vary (Strong) radio buttons no longer exist,
  instead their values are indicated in the info. text below the vary slider
* upscale and vary descriptions are now more friendly and helpful  
* set the widths for the Random Prompt and Generate columns to 75 pixels
* except for Describe and Meta, the Input Image tabs are restored to the Fooocus standard
* system message updates now only report on FooocusPlus changes
* the Brush Colour selector is integrated into the Inpainting pane
* Inpainting descriptions are now more friendly and helpful
* the Advanced and Enable Advanced Masking checkboxes now default to disabled
* the Gradio startup messages are FooocusPlus specific and do not refer to sharing
* a checkbox in the Describe pane now switches the auto-describe feature on or off
* two wildcard files have been added and some of the existing wildcards are improved
* the welcome logic is improved, if skip_jpg is present all downloaded welcome JPGs are ignored
* if skip.png is also present, the welcome image is the default black screen
* welcome images are stored in enhanced\welcome_images instead of enhanced\attached
* the control images (skip.jpg and skip.png) are stored in enhanced\control_images


# 0.9.6

* introduced support for 4GB SDXL compatible models
* system defaults to a 4GB version of SAI SDXL if VRAM<6GB
* improved FooocusPlus version messaging: updates are specifically identified
* special base model and LoRA subfolders (e.g. "\Flux") are automatically created
* "Disable Seed Increment" now works (this was an inherited bug)
* wildcards are now always random, even when the seed is frozen (another inherited bug)
* "Read Wildcards in Order" has been restored
* whatever JPGs are stored in enhanced/attached/ will be randomly displayed as welcome images
* removed all __pycache__ and .pyc files from the FooocusPlus repository


# 0.9.5

* rebuilt the .git folder for inclusion in PureFooocus release versions
* fixed the bug with inconsistent "default" preset capitalization
* confirmed that Hunyuan-DiT (HyDiT) is working
* rebuilt a new Kolors zip archive and unploaded it to the Hugging Face repo.
* recoded comfy_task.py to support this new archive and tested the three Kolors presets
* slightly improved the three Kolors presets and named them more logically
* disabled the topbar preset tooltips and iFrame Instruction pane in all languages
* removed the presets html and samples folder and reduced the image folder to just one image
* simplified the Javascript tooltip code down to just a return statement
* balanced entry_with_update.py to include only the best features from Fooocus & SimpleSDXL2


# 0.9.4

* the GroundingDINO and RemBG security issues are now resolved
* Gradio analytics are now permanently disabled (no more calling home)
* Gradio share is disabled for security reasons
* the UI is temporily coded to only display topbar preset menu selection
* in preparation for a categorized dropdown preset menu, all presets now contain a "preset category"
  parameter. Once the preset dropdown is working the topbar preset menu will be removed
* the default base model is changed from JuggernautXL XI to Elsewhere XL which works better as a general
  purpose model
* Comfy lockout now occurs when VRAM<6GB instead of VRAM<4GB
* when wildcards are inserted into the prompts they are no longer surrounded by square brackets
* the ROOT constant and two pseudo globals are now located in common.py
* fixed a mainline Fooocus bug in which the Metadata Scheme could not be chosen when Metadata was enabled
* by default, the Outputs folder is now located in the FooocusPlus folder
* when the Translator is disabled, the Random Prompt and SuperPrompt buttons are reformatted
* FooocusPlus is now an independent fork, no longer dependent on SimpleSDXL2 or mainline Fooocus
* the file structure of FooocusPlus is now self-contained, containing all models within FooocusPlusAI


# 0.9.1 to 0.9.3

* Resolved all security issues except those associated with GroundingDINO and RemBG,
  this involved a lot of recoding and it was the major work accomplished in these versions
* sub-optimal overrides (such as disabling Smart Memory) to support VRAM sharing have been removed
* coding has been made more streamlined and standardized
* image parameters, including the prompt, can now be changed while waiting for image generation
* the preset dropdown selector from mainline Fooocus has been restored
* work is ongoing to switch between the topbar and dropdown preset selectors
* console messages now have more clarity
* simple images with the words "Pure Fooocus" replace the distracting startup images on the main canvas
* the Fooocus metadata option has been restored and the Simple metadata option has been removed
* the mixed language preset tooltips, the Chinese only preset frame under the Settings tab, the
  Translator button and Translation Methods selector are all removed unless the command line
   argument "--language cn" (i.e. Chinese language) is present
* the "Big Model" translation method is removed since it did not work in SimpleSDXL2 or in FooocusPlus
* the UI Language selector is removed since it was redundant and only partially functional
* the system information displayed at the bottom of the Extras (formerly Enhanced) pane has been improved
* preliminary work on supporting Stable Diffusion 3.5 has been initiated
* the FooocusPlus version number is now tied to this log rather than being hard coded


# 0.9.0

* (2024-12-24) Forked FooocusPlus from SimpleSDXL2
* modified en.json language file to regularize capitalization, etc.
* introduced en_uk.json to support European English
* installed corrected version of watercolor_2 & mandala_art styles
* installed pony_real style in the new FooocusPlus style json

