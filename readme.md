
![2025-05-27_23-38-45_3956](https://github.com/user-attachments/assets/5a128dc4-ecae-44ad-a360-4cde04ada4ff)

# FooocusPlus – AI Art Made Simple

FooocusPlus is a community-developed AI image generation application that makes creating stunning works of art easier than ever. FooocusPlus runs offline on your computer and is completely free! Now you can have your very own Stable Diffusion or Midjourney that helps turn your creative ideas into beautiful images without any technical skills.

## Features

- Generate stunning images with meticulously prepared presets – just describe your new masterpiece and watch it come to life
- Get inspiration for your art – choose from an extensive list of styles, or use our integrated AI assistant to help you write the perfect prompt
- Enhance existing images using AI – banish Photoshop editing with advanced image modification tools, or even use an existing picture as inspiration for a new creation!
- Bring the power of community home – use LoRA models from websites like Civitai to add new concepts to your images
- Full control at your fingertips – simple one-click access to advanced generation options, letting you use custom settings like a pro without ever leaving our friendly user interface
- Multilingual – full support for English, French, and Simplified Chinese out of the box
- Private – runs on your computer and does not send information about your identity or AI art generation to third parties without your consent

## Supported Models

FooocusPlus gives you access to a diversity of AI image generation base models, including:

- Stable Diffusion XL (SDXL) and a large number of SDXL variants
- Pony Diffusion XL
- Flux from Black Forest Labs
- Hunyuan-DiT
- Kwai Kolors (temporarily disabled)
- Playground 2.5
- Segmind-Vega
- Stable Diffusion 1.5 (SD1.5)
- Stable Diffusion 3.5 (temporarily disabled)

If you’re new to AI art, don’t worry! Our built-in presets will give you one-click access to all of those exciting AI image generation models without any prior knowledge required. Favorite presets are located in a bar at the top of the FooocusPlus main canvas, and the whole preset collection is available from two dropdown menus located under the Settings tab. You'll be able to choose your own favorite model in no time.

## System Requirements

To run FooocusPlus, you will need a computer with a graphics card capable of running advanced AI software, including at least:

- 6GB of video RAM (8GB recommended for SDXL base models, 12GB for Flux)
- 16GB of system RAM (32GB recommended for SDXL, 48GB for Flux)
- 50GB of hard drive space

While some graphics cards with 4GB of video RAM (VRAM) will work - some of them even supporting Flux - image generation may be slow or erratic. Some 4GB VRAM cards may not support image generation at all.

For those systems that are capable of generating FooocusPlus images with only 4GB of VRAM, we include a unique default base model that is small and fast. In addition, FooocusPlus supports Stable Diffusion 1.5 (SD1.5), which should run in most 4GB VRAM cards.

FooocusPlus supports NVIDIA graphics cards on Windows and Linux, macOS on Silicon, and many AMD graphics cards on Linux. We also support using AMD graphics cards on Windows at a reduced speed, and provide limited support for macOS on Intel.

Torchruntime is integrated into FooocusPlus. Please check their [compatibility tables](https://github.com/easydiffusion/torchruntime/blob/main/README.md#compatibility-table) for more details on hardware and software support.

## Installing FooocusPlus

For Linux users, please use the [Installation Script for Linux](https://github.com/DavidDragonsage/FooocusPlus/wiki/Installation-Script-for-Linux) in the FooocusPlus Wiki.

For Windows users, this [Installation Procedure](https://github.com/DavidDragonsage/FooocusPlus/wiki/Installation-Procedure-for-Windows) is also available in the Wiki, complete with images.

If you were using a pre-release or Beta version of FooocusPlus, please be sure to delete or at least rename it first, it is not compatible with the release version. Ideally FooocusPlus should be installed in the root of a high speed internal drive such an NVMe solid state drive (SSD). However it will work fine on standard SATA hard drive, just a bit more slowly. First, download the following archives:

- The _latest_ version of [7-Zip](https://7-zip.org/). The installation may fail if the version is not current.
- The [FooocusPlus](https://huggingface.co/DavidDragonsage/FooocusPlus/resolve/main/FooocusPlus.7z) program archive.
- If you are using Windows, the [Python library](https://huggingface.co/DavidDragonsage/FooocusPlus/resolve/main/python_embedded.7z) files.
- The FooocusPlus [Support Pack](https://huggingface.co/DavidDragonsage/FooocusPlus/resolve/main/SupportPack.7z) The Support Pack is optional but will save you a lot of time later
- The FooocusPlus [Tiny Pack](https://huggingface.co/DavidDragonsage/FooocusPlus/resolve/main/TinyPack.7z). The Tiny Pack is designed for those with graphics cards that have less than 6GB of video RAM (VRAM). The Tiny Pack is completely optional. If not installed now, its files will be downloaded later if needed by a preset.
- The FooocusPlus [Schnell Pack](https://huggingface.co/DavidDragonsage/FooocusPlus/resolve/main/SchnellPack.7z). Another completely optional pack, it contains four basic Flux1 Schnell models. Schnell models provide high speed - 4 sampling steps per image generation - with reasonably good quality.
<br/><br/>
1. After your downloads are complete, first install 7-Zip.

2. Next, extract the _program archive_ to create a FooocusPlus folder in the root of the drive, E:\ for example. The FooocusPlus folder will contain the FooocusPlusAI folder, the UserDir folder and two batch files.

3. Next, extract the _python_embedded_ library archive into the FooocusPlus folder.

4. Next, extract the _Support Pack_ to the FooocusPlus folder. These files will be added to the UserDir\models subfolder.

5. If you decided to download the _Tiny Pack_ or _Schnell Pack_, extract them to the FooocusPlus folder. Their contents will be added to the UserDir\models subfolder.

6. Now double-click on the _run_FooocusPlus.bat_ file to load FooocusPlus for the first time. It will download some additional components automatically on the first run.

## Language Support

Language and optional preset startup files are available in the FooocusPlus\UserDir\batch_startups folder. _Please copy whatever you need to the FooocusPlus folder before using them._ These are the current language startups:

- Chinese, Simplified: 常规启动.bat and 不更新启动.bat (no update)
- English, UK: run_FooocusPlus_UK.bat
- French: run_FooocusPlus_française.bat
- Spanish: run_FooocusPlus_español.bat

## Getting Help

Have a question or concern? Visit the Discussions page here at GitHub or join our friendly community at the Facebook [Pure Fooocus](https://www.facebook.com/groups/fooocus) group. If you think you have found a bug or want to suggest a missing feature, visit the GitHub Issues page to file a report so that we can investigate.

## Licensing

FooocusPlus is free to download and use, and the FooocusPlus developers will never request money or identifiable information from you in order to access or run the software. We do not accept donations or sponsorships, but instead welcome positive feedback, encouragement, and GitHub stars.

FooocusPlus is published under the GPL-3.0 license, and your use of the software is conditional on your acceptance of both the terms of the GPL-3.0 and the additional terms contained in this section. In particular, you acknowledge that some AI image generation models included in FooocusPlus are licensed for non-commercial community use only, and you agree to purchase all necessary licenses from the relevant developers prior to commercially distributing artwork generated with these models.

You also agree that you will not use FooocusPlus to:

- Violate the laws of your country, state, or locality
- Exploit minors or create child exploitation content
- Create non-consensual or illegal pornographic content
- Create material that may be used to harm or harass others
- Violate the license agreements of included software packages or AI models

## Credits

FooocusPlus is Copyright &copy; 2024-2025 David Sage and contributors.

This software was made possible by integrating open-source technologies from projects including:

- Fooocus by illyasviel and mashb1t
- ComfyUI by comfyanonymous and the Comfy-Org team
- SimpleSDXL2 by metercai
- diffusers by the huggingface team
- torchruntime by cmdr2 and the easydiffusion team
- OneButtonPrompt by AIrjen, via SimpleSDXL2 and RuinedFooocus
- Superprompter by sammcj
- Stable Diffusion 1.5 (SD1.5) support by Irmagon (Thomas Gaud)
- the members of the Pure Fooocus Facebook group for their encouragement, enthusiasm and careful Beta testing

![2025-05-23_20-21-10_1729](https://github.com/user-attachments/assets/b6217150-7f09-4641-b976-7dab9de4826c)
