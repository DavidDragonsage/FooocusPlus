# 1.0.0

* removed the irrelevant Fooocus and Simple version information. FooocusPlus does not synchronize to either of them

# 0.9.8 Dev

* initialized the UserDir folder: its location defaults to the repo's parent
* UserDir contains the models, master & user presets, startup batch, startup & control images, and wildcards folders
* the UserDir also contains config.txt and config_modification_tutorial.txt, torch_base.txt, and the Random Prompt master and user topic folders
* config.txt now contains all the settings listed in config_modification_tutorial.txt, making changes much easier
* startup_batch now holds all the optional batch files, besides the default run_FooocusPlus.bat
* master_presets is a copy of the same folder in the repo, for user reference only
* user_presets is designed for custom modifications of the master presets and presets saved within the UI
* during runtime, presets are loaded from the scratchpad presets folder within the repo, which is dynamically stocked
  from master_presets and then overwritten with the contents of user_presets
* this system enables any master preset to be superceded by a user preset, reducing potential preset bloat
* accessed from the Extras tab, the Make New Preset button enables creation of a preset based on the current parameters
* removed "auto" model support in presets, a confusing & unnecessary "feature"
* "Read Wildcards in Order" is now grouped with the wildcard dropdowns and called "Generate Wildcards in Order"
* renamed "Random" to "Random Seed" and "Fixed Seed" to "Specific Seed" (it is not really fixed because it still increments)
* moved "Disable Seed Increment" to just above "Specific Seed" and renamed it "Freeze Seed"
* introduced "Seed Increment Skip" for large random increments, called "Extra Variation", placed directly below "Random Seed"
* all four seed options now have descriptive help messages
* all UI references to OneButtonPrompt are now called "Random Prompt" and its "Presets" are called "Topics"
* removed more offensive text from Random Prompt, resolving some problems with Waifu's and Husbando's operation
* cleaned up the files and coding related to Random Prompt that caused the creation of ghost directories in the repo.
* removed superfluous Random Prompt and SuperPrompt controls in the Extras section
* the Random Prompt Topics dropdown menu is now alpha-sorted
* the newly labeled "Create a New Topic" option now operates a dropdown Save Topic group with improved formatting and help
* the same system used for user preset control also applies to user topics, allowing for easy addition and removal of topics
* the Superprompter folder is now correctly rebuilt if it is deleted
* corrected the path for the full SD3.0 medium base model, with accessories
* python_embedded version control now only applies to Windows platforms because other platforms do not use python_embedded
* updated many more Python libraries and removed Torch and its five related dependencies from the library
* Torch and its dependencies are now dynamically installed according to the user's operating system and hardware
* this dynamic system uses Torchruntime and the Torch version is recorded in torch_base.txt in UserDir
* added the Flux_BlackColor_SaMay.safetensors & FluxDFaeTasticDetails.safetensors to the built-in LoRAs
* added the Flux AntiBlur.safetensors & Hyper-FLUX.1-dev-8steps-lora.safetensors to the Starter Pack LoRAs


# 0.9.7 Dev

* this release restores all mainline Fooocus functions
  including prompt and wildcard operation
* enabled automatic updating for the development (dev) branch
* if VRAM<6GB the UI now defaults to the VegaRT model
* console warnings of unreliability occur if VRAM<6GB
* if VRAM<4GB then the use of large models is locked out (Comfy lockout)
* Smart Memory is now enabled by default if VRAM=>12GB
* added video card information and Smart Memory status to the UI ("System Information")
* added error control for file downloads
* removed offensive language from the One Button Prompt texts
* the SuperPrompter is now functional
* fully integrated the upscale or vary (UOV) sliders into normal operation
* the Vary (Subtle) and Vary (Strong) radio buttons no longer exist,
  instead their values are indicated in the info. text below the vary slider
* upscale and vary descriptions are now more friendly and helpful  
* set the widths for the Random Prompt and Generate columns to 75 pixels
* except for Describe and Meta, the Input Image tabs are restored to the Fooocus standard
* the number of pages in the image catalogue now defaults to a maximum of 100 instead of 65
* system message updates now only report on FooocusPlus changes
* the Brush Colour selector is integrated into the Inpainting pane
* Inpainting descriptions are now more friendly and helpful
* the Advanced and Enable Advanced Masking checkboxes now default to disabled
* the Gradio startup messages are FooocusPlus specific and do not refer to sharing
* a checkbox in the Describe pane now switches the auto-describe feature on or off
* two wildcard files have been added and some of the existing wildcards are improved
* the welcome logic has been improved and placed in its own module
* if skip_jpg is present all downloaded welcome JPGs are ignored
* if skip.png is also present, the welcome image is the default black screen
* welcome images are stored in enhanced\welcome_images instead of enhanced\attached
* the control images (skip.jpg and skip.png) are stored in enhanced\control_images
* "python_embeded" is renamed "python_embedded": changed all internal references
* updated many Python libraries and fixed the Onnx Graphsurgeon bug
* python_embedded now includes version control: if the version is incorrect then program loading stops
* resolved the bug: "SaveImageWebsocket.IS_CHANGED() missing 1 required positional argument: 's'"


# 0.9.6 Beta7

* introduced support for 4GB SDXL compatible models
* system defaults to a 4GB version of SAI SDXL if VRAM<6GB
* improved FooocusPlus version messaging: updates are specifically identified
* special base model and LoRA subfolders (e.g. "\Flux") are automatically created
* "Disable Seed Increment" now works (this was an inherited bug)
* wildcards are now always random, even when the seed is frozen (another inherited bug)
* "Read Wildcards in Order" has been restored
* whatever JPGs are stored in enhanced/attached/ will be randomly displayed as welcome images
* removed all __pycache__ and .pyc files from the FooocusPlus repository
* in Beta2, updated the presets and Flux file selector to better support Flux models
* in Beta2, restored the "Extreme" performance setting & increased the limit on displayed presets to 30
* in Beta3, added support for Stable Diffusion 1.5 (SD1.5) base models
* in Beta4, Flux presets now support the clip model parameter, allowing for lower resource use presets
* in Beta5, the Flux1D_GGUF & Flux1D_8GGUF presets now support the HyperFlux & AntiBlur LoRAs
* in Beta5, HyperFlux16 now uses flux-hyp16-Q8_0.gguf instead of Q5, and supports FaeTastic & AntiBlur LoRAs
* in Beta5, the two 4GB presets now correctly download the specified base models
* in Beta6, added clip_model error control to comfy_task and added clip_model parameter to Flux1S_GGUF
* in Beta7, corrected a bug with "Refresh All Files" and also gave it a realistically sized button


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

