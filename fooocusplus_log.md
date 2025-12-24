# 1.0.9 Add/Remove to/from Favourites, Batch Generation, Image Editor, Image Grids, Image Recovery, New Styles & UI Popup Messages

* introduced Add/Remove Current Preset to/from Favorites
  * for new users, the Favorites are: Default, Cheyenne18,
  * Flux1Krea_8GGUF, HyperFlux1S8 and HyperFlux5
  * these Favorites can be added with the Restore Favorites button
* the Flux preset categories now less abbreviated:
  * Flux1Dev, Flux1Krea, Flux1Schnell and HyperFlux1D
  * both HyperFlux Schnell presets are now in the Flux1Schnell category
* introduced Image Recovery to restore images lost in a crash or deletion
  * temporary images are removed during the generative cycle, not at launch
* introduced Batch Generate to the new Batch Control accordion in Settings
* Batch Generate is supported by a Batch Count slider, varying from 1 to 25
  * Batch Generate restarts image generation the specified number of times
  * it is ideal for creating multiple Image Grids
  * Batch Generate also works as an Image Quantity multiplier
* the Generate Image Grid feature is upgraded to save grids to Outputs
  * grids are optimized to avoid the creation of partial rows
  * aspect ratio awareness is used to make the grids as square as possible
  * grid size is controlled by Image Quantity and limited to 16 images
  * the grid may be viewed in the Catalog but not in the log file
  * the Generate Image Grid control is located in the Batch Control accordion
* under the Main Prompt box, introduced the Features option to hold:
  * IC-Light and Edit, the new image editor
  * unlike Input Image, these functions are always available
* Edit is composed of five optional dropdowns:
  * Adjustments include Brightness, Contrast, Hue, Saturation & Sharpness
  * Transformations can resize, flip and crop the image
  * Transparency options create a transparent image or an invisible background
  * Composite images can be created by positioning overlays on a base
  * Effects include Blurs, Edge Enhance, Posterize & Solarize
  * all image functions preserve image metadata, if any
* Prompt Array processing now correctly removes leading & trailing spaces
* changed the Prompt Array separator from the comma to the vertical bar,
  * adjustable in config.txt with the "prompt_array_separator" parameter
* introduced new Info and Warning UI popups to support these features:
  * Batch Generate, Image Grid, Make New Preset, Model Downloads,
  * Recover Images, Refresh All Files and Version Updates, etc.
* an audio Notification can occur at the end of a generative batch
  * this option is set by "Enable Audio Notification", under Extras
  * also set by "audio_notification": true in config.txt
  * by default, notification uses the original Fooocus mp3 sound clip
  * UserDir/master_audio contains 11 alternative notification files
  * any mp3 placed in UserDir/user_audio will be chosen at random
  * also the "Refresh All Files" button makes a new random selection
* for Welcome images, user png images now override the built-in jpgs
  * the logo, white and black pngs are found in UserDir/control_images
* the Advanced tab Image Control accordion now contains these functions:
  * Recover Images, Image Format, Save Metadata to Images, Metadata Scheme,
  * Disable Image Log, Show Newest Images First, Disable Preview,
  * Black Out NSFW & Save Only the Final Enhanced Image
* regenerating images from the log, image metadata or gallery work correctly
  * the Current Preset field is updated correctly
  * Apply Metadata and Load Parameters now work correctly with Flux models
* moved all args_parser command line argument coding to args_manager
  * deleted args_parser.py, options.py and latent_visualization.py
* corrected args.directml coding so that it properly sets the device ID
* deleted the arguments that were unused, redundant or compromised security:
  * --cache-path, --debug-mode, --disable-analytics,
  * --disable-enhance-output-sorting, --disable-header-check,
  * --disable-image-log, --disable-server-log, --enable-auto-describe-image,
  * --external-working-path, --is-windows-embedded-python, --listen,
  * --location, --multi-user, --port, --share, --preview-option, --webroot,
  * --web-upload-size (some of these were removed in previous versions)
* now args.disable_comfyd completely prevents the use of Comfy
* config.default_comfy_active_checkbox or the UI control toggles Comfy use
  * the config.default_comfyd_active_checkbox is gone: incorrect default
* moved all config defaults to modules.config from enhanced.all_parameters
  * deleted enhanced.all_parameters.py
* "Make New Preset" can now correctly replace the Default preset
  * improved the button's appearance, it is now similar to "Image Recovery"
* there is now the option to "Save the Current Aspect Ratio" in the new preset
* startup preset batch files now set all parameters correctly
  * introduced the Flux1Krea8 and SD1.5_RealVis startup batch files
  * replaced the Juggernaut & HyperFlux presets with Juggernaut8 & HyperFlux5
* the Custom startup batch file and the Custom preset have been removed
* added the Rossetti Steampunk, Science Fiction and World styles
* added 36 new TaffyCarl (Carl Bratcher) styles(!) and updated the Stylesheet
* fixed the Styles menu so that it properly displays acronyms & initials
* there is now a console note that UserDir/wildcards is the working directory
* moved four functions from webui to modules.ui_util to reduce module bloat:
  * sort_enhance_images(), generate_clicked()
  * inpaint_mode_change(), enhance_inpaint_mode_change()
* added two new functions to modules.ui_util:
  * init_batch_counter(), update_batch_counter()
* resolved a bug with the Preset Bar checkbox not working
* reduced the tab width (Settings, Styles, etc.) to accommodate languages
* simplified the "up-to-date" console message, removing the coded part
* program name & version now appears in the bottom left corner of the canvas
* System Information now displays the Gradio version
  * removed the Gradio footer as it was conveying no useful information
* Tech Note: "special" enhanced.toolbox CSS moved to standard style.css file
* Hotfix0: none<br/><br/>


# 1.0.8 Prompt Translation

* installs any of 40 language packs available from Argos Translate
* prompt translation is automatic or may be manually selected from the UI
* most messages in the console window are interpreted in the selected language
* most dynamic status messages shown in the UI are also interpreted
* Wildcard names and a controlled amount of Wildcard Contents are interpreted
* the number of interpreted lines is set in Extras and in config.txt
* in the UI, the number of Wildcards per page is increased from 28 to 35
* the "Refresh All Files" button now adds new Wildcards to the display
* the Translate feature may be disabled from an Extras option or in config.txt
* removed Translators 5.8.9 from requirements file and the Python library
* the French language UI is now complete
* samples of all available styles are shown in the Styles Documentation link
* this link has a nudity warning, due to 6 NSFW images out of a total of 1104
* due to the NSFW content, this link is removed if "black_out_nsfw" is enabled
* moved the "Mask Erode or Dilate" control from Expert Mode to Inpaint/Outpaint
* "Mask Erode or Dilate" is available only if "Enable Advanced Masking" is checked
* removed the "allow_custom_value" option from the Sampler and Scheduler controls
* "zh" is the language detector for Simplified Chinese but "cn" is accepted<br/>
* Hotfix6: Gradio information moved from footer to System Information
  * prepared enhanced.version module for FooocusPlus 1.0.9
* Hotfix5: introduced error control on FreeU values during Save Preset
* Hotfix4: the Stylesheet is reformatted and supports all FooocusPlus styles
  * replaced the nude and questionable images; removed the nudity warning
  * also improved the messaging when using an obsolete Python library
* Hotfix3: restored the proper detection of Windows and python_embedded
  * this change enable the python_embedded version to be reported correctly
  * updated language information in the FooocusPlus readme file
* Hotfix2: removed unnecessary console message to restart to finish updating
  * added console message if fallback to "karras" occurs and updates common
* Hotfix1: added console message to restart to finish updating
  * in sample_hijack.py, falls back to "karras" if scheduler error<br/><br/>


# 1.0.7 Flux1 Krea & Enhancements

* introduced three presets: Flux1Krea, Flux1Krea_5GGUF and Flux1Krea_8GGUF
* these presets are located in the new Flux1Krea Preset Category
* added the Spanish language user interface
* a version information link is now available below System Identification, in Extras
* introduced Hotfix identification, displaying a fourth digit in the version string
* Linux users now use the appropriate Xformers version. No change for Windows users
* debugged and updated support for AMD graphics card users
* added HF-Mirror support for Chinese users, in the two Chinese batch files
* to reduce image distortion, the main canvas is now set for a minimum height of 300px
* updated python_embedded version to 1.06 (current users are already updated)<br/>
* Hotfix20: added a diagnostic to test a user problem with LoRA loading
* Hotfix19: a disabled Preset Bar no longer reappears when changing presets
* Hotfix18: added three point error control for Scheduler values
* Hotfix17: using the --output-path startup argument no longer causes an error
* Hotfix16: fixed a bug in Windows detection that affected Linux users
* Hotfix15: fixed a bug with loading Xformers - improved verify_installed_version()
* Hotfix14: introduced the CheyenneAlt preset in the Illustrative category
  * also updated the English UK language file & cleaned up the startup code
* Hotfix13: improved error handling for PyGit2 verification
* Hotfix12: PyGit2 is now verified before updating FooocusPlus
* Hotfix11: added Insightface wheel for Linux and macOS
* Hotfix10: Inpainting help popup uses correct text in English & Spanish
* Hotfix9: added the Flux1Krea_FP8 preset
  * users can add or amend languages with the UserDir/user_language directory
  * hotfix numbers can now exceed 9
* Hotfix8: removed the Flux1Krea preset due to unreliability
  * the Spanish language user interface (UI) is now complete
  * fixed a bug with Inpainting that in some cases prevented use of the Inpainting model
* Hotfix7: fixed a "NoneType" error with Inpainting, initialized Argos Translate
* Hotfix6: fixed another "assert" bug with Inpainting
* Hotfix5: UI now supports full translation
* Hotfix4: fixed a bug with some Performance options causing an error
* Hotfix3: removed the assert statements from Inpainting: it uses error control instead
  * added the Elsewhere preset to the General Category, a backup for the Default preset
  * this is to encourage the creation of a user created Default to suit individual needs
  * removed the "test" Random Prompt Topic and rationalized the random prompt names
* Hotfix2: fix the version numbering problem
* Hotfix1: fix startup update problem<br/><br/>


# 1.0.6 Bug Fixes & UI Refinements

* removed the following components that are not suitable for production code:
  * launch_support.build_launcher() and launch_with_commit.py
  * run_FooocusPlus_commit.bat & run_FooocusPlus_dev.bat (auto-delete)
* introduced the "--gpu-type" command line argument
* run_FooocusPlus_cu124.bat demonstrates gpu_type = "cu124"
* restored run_FooocusPlus_FR.bat for French language support
* corrected the Flux1S preset to use the "flux_base" task_method
* the base model list "flux_base2_gguf" method now includes "schnell" in the filter
* created Hyperflux Schnell models, represented by the HyperFlux1S5 & HyperFlux1S8 presets
* HyperFlux1S5 is in the Flux1S category and HyperFlux1S8 is in the HyperFlux category
* added a "Tiny Pack" for 4GB VRAM users and a "Schnell Pack" to the Hugging Face archives
* moved the Cheyenne preset to the General category and renamed it Cheyenne18
* introduced the Custom preset into the Favorite category, set for Custom Performance
* the Custom preset also specifies a 16*9 aspect ratio and an image quantity of 10
* the Custom preset is supported by run_Custom.bat in the batch_startups directory
* when switching aspect ratio templates, Default toggles to Custom instead of Cheyenne
* when switching presets, the positive and negative prompts are preserved
* if available, positive and negative prompts specified in presets are utilized
* the Negative Prompt field is now just below the Preset selectors so that is always visible
* the main prompt automatically extends to accomodate long prompts, like original Fooocus
* the extended prompt field makes editing more practical and reduces errors
* similarly, image quantity settings are preserved during preset switching
* and image quantity values specified in a preset are used, if available
* restored the function of the Sampler and Scheduler dropdowns
* fixed an intermittent error with the Scheduler Name during image generation
* overwriting the aspect ratio width and height values no longer produces a console error
* introduced the Juggernaut8 and Juggernaut9 presets
* renamed the existing Juggernaut preset to "JuggernautXI"
* added the Rossetti Painting, Rossetti Drawing and Rossetti Sketch styles
* restored the correct operation of LoRAs in Flux presets
* restored the operation of preset aspect ratios
* if an aspect ratio height value is missing, it will be rebuilt
* increased the width of the Base Model and Refiner dropdowns
* the Refiner dropdown is invisible in Comfy modes such as Flux (instead of non-interactive)
* increased the width of the LoRA selector dropdowns and grouped each LoRA separately
* "Output Format" is renamed "Image Format" and moved to the Advanced tab
* the Metadata settings are moved from Expert Mode and grouped with Image Format
* the old Fooocus Documentation link has been removed from the Advanced tab
* new Forum (Pure Fooocus) and Wiki links are grouped with the Image Log link
* adjusted the Guidance Scale (CFG) slider from a 0.001 to a 0.1 step increment
* adjusted the Image Sharpness slider from a 0.001 to a 0.1 step increment
* if a directory is not accessible, the program no longer tries to rename it ".corrupted"
* in support of UK users, all presets referring to CivitAI links now refer to the FooocusPlus repo<br/>
* Hotfix5: removed the non-destructive error condition when using Describe
* Hotfix4: improved legacy graphics card support
* Hotfix3: "Refresh All Files" correctly adds new LoRAs and does not cause an error
* Hotfix2: Linux is finally functional: dependency errors and non-compliant coding were resolved
* Hotfix1: restored the visibility of the Stop & Skip buttons during generation<br/><br/>


# 1.0.5 Bug Fixes & Enhancements

* fixed a bug that prevented installation of FooocusPlus to a subfolder
* FooocusPlus may now be installed to a subfolder, regardless of the parent folder's name
* restructured config.txt for more consistency, reliability and operating system compatibility
* several config.txt options now fit their UI equivalents, e.g. "Image Quantity" not "Image Number"
* config.txt now uses pathlib Path to itemize model folders
* the user must delete config.txt and config_modification_tutorial.txt to activate the changes
* the UI now has a "Custom" Performance option which defaults to 15 steps
* "Custom" is adjustable in config.txt with custom_performance_steps, from 1 to 200 steps
* the Refiner dropdown no longer lists Flux models
* the "Refiner Switch At" settings are no longer ignored
* restored IC-Light operation
* fixed an obscure bug with preset switching when recreating a specific image
* restored Save Preset operation and made the Save Preset functions Linux compatible
* added the female_hair, male_hair and hair (unisex) wildcards
* updated pytorch-lightning and lightning-fabric from version 2.5.1 to 2.5.2
* removed a misleading and incorrect error message during first time installation
* now using a "fooocusplus" temporary folder to avoid possible conflicts with mainline Fooocus
* removed the Kolors presets because they are not working: Kolors support will return in the future
* all batch startup files now contain a note about copying them to the FooocusPlus directory
* removed the HF Mirror argument from the Chinese batch files, it was causing an error
* fixed a bug with Clip Skip that affected some users
* xformers installation now uses verify_installed_version() rather than Torchruntime<br/><br/>


# 1.0.4 Bug Fix for Incorrect Model Paths & Installation Corruption by AMD Support

* resolves the bug with incorrect secondary paths to the models folders
* the user must delete config.txt and config_modification_tutorial.txt for this fix to take effect
* once the config text files are deleted then FooocusPlusAI\UserDir is automatically removed
* directml support for AMD video cards is deleted if not required
* the presence of directml files in the Python libraries was sabotaging NVIDIA installations
* in the GUI, "Forced Overwrite of Sampling Step" is grouped with Performance Options
* to reduce clutter, the Performance Options are now available from an accordion<br/><br/>


# 1.0.3 Critical Bug Fixes & NVIDIA 50xx Support

* introduced full support for NVIDIA 50xx video cards
* now using Torchruntime 1.18.1, Torch 2.7.1 and Xformers 0.0.30
* full Torch information is now listed in the console, including the CUDA variant
* the bug with Aspect Ratio selection has been resolved
* the Random Preset Category selector now works reliably
* a slight slot machine effect may occur during the randomization process
* when switching between Preset Categories, a new preset is selected at random
* there is now a HyperFlux Preset Category, bringing the total to 12 categories
* the occasional hangups in Flux mode no longer occur
* checks for required library files are now done at the start of the launch
* the checks allow for requirements to be exceeded if marked with a ">="
* the library files have been cleaned up and several items have been updated
* these library updates will automatically install during launch
* these changes are also available in the python_embedded archive at Hugging Face
* the image seed options are now accessed through the Image Seed Control accordion<br/><br/>


# 1.0.2 LowVRAM Support

* LowVRAM Preset mode activates if VRAM<6GB
* also, LowVRAM Preset mode is set by config.txt "default_low_vram_presets": true
* in this mode, the default category is LowVRAM and the preset is 4GB_Default
* the 4GB_Default preset now uses Segmind-Vega in normal mode
* the VegaRT preset operates Segming-Vega in "Real Time" mode
* Styles can now be configured in UserDir, like Presets and Topics<br/><br/>


# 1.0.1 Maintenance Update

* pytorch-lightning now loads correctly
* resolved the "Fooocus' is not a valid MetadataScheme" error
* the user structure module now sets up the UserDir folders in a Linux compatible way
* fixed a bug that was partially installing python_embedded within the program directory
* this phantom python_embedded folder is automatically deleted if present
* from 1.0.0, Flux models are installed in either the "FluxDev" or "FluxSchnell" folders
* if an obsolete "Flux" folder is found and it is empty, it is automatically deleted<br/><br/>


# 1.0.0 Welcome to FooocusPlus 1.0.0!

* removed the irrelevant Fooocus and Simple version information. FooocusPlus does not synchronize with either of them
* removed legacy upstream references and moved the master subfolders to a new masters parent folder
* like mainline Fooocus, there are now two metadata schemes: "Fooocus" and "A1111". The confusing "Simple" label is gone
* if an image is stored with A1111 metadata, the Apply Metadata button is disabled instead of creating an error
* added Torch, CUDA and xformers data to System Information, under the Extras tab
* fixed a bug that prevented reinstallation of Torch if its folder was not found
* the various master folders are now subfolders of the new "masters" folder
* by default, all presets except for SD1.5 now use a 0*0 aspect ratio, meaning that it does not have any effect
* but as before, if a valid aspect ratio is set in a preset it overrides the current UI setting
* as presets are changed, by default the UI setting for aspect ratio does not change
* there are now four sets of aspect ratios defined in config.txt, the Standard, Shortlist, SD1.5, and PixArt templates
* the default settings for these templates are used for initial values but they do not override setting changes in the UI
* by default FooocusPlus starts with the Shortlist template, a Standard template that is simplified to only 15 values
* this default can be changed using the "enable_shortlist_aspect_ratios" config.txt setting
* the UI can toggled between Shortlist and Standard templates with the "Use the Aspect Ratio Shortlist" checkbox
* the SD1.5 presets change the aspect ratio display to the SD1.5 template
* when PixArt Sigma is introduced, a preset will select the PixArt template
* when switching between presets the UI attempts to keep the currently selected aspect ratio, and width and height too
* introduced and tested the "experimental" SDXL 1280*1280 aspect ratio, available from the Standard template
* introduced both Preset Categories and Presets dropdowns under the Settings tab
* the Preset Categories are: Alternative, Fantasy, Favorite, Flux1D, Flux1S, General, Illustrative, LowVRAM, Pony, Realistic & SD1.5
* the Category structure is duplicated to the User Directory. Changes in this directory will update the working preset folder
* the Categories are actually folders. If a preset file is located in a folder it will show up in that category
* presets can be stored in more than one category (folder) if desired
* the Make New Preset button, under the Extras tab, saves the current settings to a new preset, stored in the User Directory structure
* if the new preset is given the same name as a built-in one it will override it
* if the Random category is selected a random preset is chosen
* all presets may be displayed at once if the All category is selected
* the Current Preset is now listed just below the Generate button
* if Favorites is checked (the default) the favorite presets are shown in a horizontal menu bar located above the main canvas
* the current preset is now stored in the log
* FooocusPlus starts with the Default preset, unless low VRAM is detected in which case it starts with 4GB_Default
* the VRAM 4GB_Default preset can also be set by the config.txt "default_low_vram_presets" option
* added a config.txt option and checkbox to "Show Newest Images First" in the log. If this is off the newest images are last
* the Flux base models are recategorized into the FluxDev and FluxSchnell folders
* fixed a strange bug in which the "Specific Seed" value was being trashed when changing presets
* fixed bugs with SuperPrompter, Wildcard Panel, Sampler selector, Refiner switch and metadata processing
* subject to testing, this version provisionally supports NVIDIA 50xx video cards
* temporarily removed several Wildcard files that need improvement<br/><br/>


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
* added the Flux AntiBlur.safetensors & Hyper-FLUX.1-dev-8steps-lora.safetensors to the Starter Pack LoRAs<br/><br/>


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
* resolved the bug: "SaveImageWebsocket.IS_CHANGED() missing 1 required positional argument: 's'"<br/><br/>


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
* in Beta8, disabled all further updating to reduce the possibility of corruption by FooocusPlus 1.0.0<br/><br/>


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
* balanced entry_with_update.py to include only the best features from Fooocus & SimpleSDXL2<br/><br/>


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
* the file structure of FooocusPlus is now self-contained, containing all models within FooocusPlusAI<br/><br/>


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
* the FooocusPlus version number is now tied to this log rather than being hard coded<br/><br/>


# 0.9.0

* (2024-12-24) Forked FooocusPlus from SimpleSDXL2
* modified en.json language file to regularize capitalization, etc.
* introduced en_uk.json to support European English
* installed corrected version of watercolor_2 & mandala_art styles
* installed pony_real style in the new FooocusPlus style json
