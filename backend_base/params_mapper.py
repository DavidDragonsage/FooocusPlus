import os

class ComfyTaskParams:
    def __init__(self, params):
        self.params = params
        self.workflow = ''

    fooo2node = {
        'seed': 'KSampler:main_sampler:seed;KSampler:KSampler:seed;TiledKSampler:main_sampler:seed;KolorsSampler:main_sampler:seed;RandomNoise:noise_seed:noise_seed;easy seed:sync_seed:seed',
        'steps': 'KSampler:main_sampler:steps;KSampler:KSampler:steps;TiledKSampler:main_sampler:steps;KolorsSampler:main_sampler:steps;BasicScheduler:scheduler_select:steps',
        'cfg_scale': 'KSampler:main_sampler:cfg;KSampler:KSampler:cfg;TiledKSampler:main_sampler:cfg;KolorsSampler:main_sampler:cfg;CLIPTextEncodeFlux:prompt:guidance',
        'sampler': 'KSampler:main_sampler:sampler_name;KSampler:KSampler:sampler_name;TiledKSampler:main_sampler:sampler_name;KSamplerSelect:sampler_select:sampler_name',
        'scheduler': 'KSampler:main_sampler:scheduler;KSampler:KSampler:scheduler;TiledKSampler:main_sampler:scheduler;KolorsSampler:main_sampler:scheduler;BasicScheduler:scheduler_select:scheduler',
        'denoise': 'KSampler:main_sampler:denoise;KSampler:KSampler:denoise;TiledKSampler:main_sampler:denoise;KolorsSampler:main_sampler:denoise_strength;BasicScheduler:scheduler_select:denoise',
        'tiling': 'TiledKSampler:main_sampler:tiling;SeamlessTile:seamless_tile:tiling;CircularVAEDecode:vae_tiled:tiling',
        'tiled_offset_x': 'OffsetImage:offset_image:x_percent',
        'tiled_offset_y': 'OffsetImage:offset_image:y_percent',
        'base_model': 'CheckpointLoaderSimple:base_model:ckpt_name;CheckpointLoaderSimple:Load Checkpoint:ckpt_name;CheckpointLoaderSimple:CheckpointLoaderSimple:ckpt_name;UNETLoader:base_model:unet_name;UnetLoaderGGUF:base_model:unet_name',
        'base_model_dtype': 'UNETLoader:base_model:weight_dtype',
        'merge_model': 'UNETLoader:merge_model:unet_name',
        'model_merge_ratio': 'ModelMergeSimple:model_merge_ratio:ratio',

        'lora_speedup': 'LoraLoaderModelOnly:lora_speedup:lora_name;LoraLoader:lora_speedup:lora_name',
        'lora_speedup_strength': 'LoraLoaderModelOnly:lora_speedup:strength_model;LoraLoader:lora_speedup:strength_model;LoraLoader:lora_speedup:strength_clip',

        'lora_1': 'LoraLoaderModelOnly:lora_1:lora_name;LoraLoader:lora_1:lora_name;LoraLoaderModelOnly:lora_speedup:lora_name;LoraLoader:lora_speedup:lora_name',
        'lora_1_strength': 'LoraLoaderModelOnly:lora_1:strength_model;LoraLoader:lora_1:strength_model;LoraLoader:lora_1:strength_clip;LoraLoaderModelOnly:lora_speedup:strength_model;LoraLoader:lora_speedup:strength_model;LoraLoader:lora_speedup:strength_clip',

        'lora_2': 'LoraLoaderModelOnly:lora_2:lora_name;LoraLoader:lora_2:lora_name',
        'lora_2_strength': 'LoraLoaderModelOnly:lora_2:strength_model;LoraLoader:lora_2:strength_model;LoraLoader:lora_2:strength_clip',

        'lora_3': 'LoraLoaderModelOnly:lora_3:lora_name;LoraLoader:lora_3:lora_name',
        'lora_3_strength': 'LoraLoaderModelOnly:lora_3:strength_model;LoraLoader:lora_3:strength_model;LoraLoader:lora_3:strength_clip',

        'lora_4': 'LoraLoaderModelOnly:lora_4:lora_name;LoraLoader:lora_4:lora_name',
        'lora_4_strength': 'LoraLoaderModelOnly:lora_4:strength_model;LoraLoader:lora_4:strength_model;LoraLoader:lora_4:strength_clip',

        'lora_5': 'LoraLoaderModelOnly:lora_5:lora_name;LoraLoader:lora_5:lora_name',
        'lora_5_strength': 'LoraLoaderModelOnly:lora_5:strength_model;LoraLoader:lora_5:strength_model;LoraLoader:lora_5:strength_clip',

        'lora_6': 'LoraLoaderModelOnly:lora_6:lora_name;LoraLoader:lora_6:lora_name',
        'lora_6_strength': 'LoraLoaderModelOnly:lora_6:strength_model;LoraLoader:lora_6:strength_model;LoraLoader:lora_6:strength_clip',

        'width': 'EmptyLatentImage:aspect_ratios_size:width;EmptyLatentImage:Empty Latent Image:width;EmptySD3LatentImage:aspect_ratios_size:width;ImageResize+:resize_input_image:width;KolorsSampler:main_sampler:width;easy int:aspect_ratios_width:value',
        'height': 'EmptyLatentImage:aspect_ratios_size:height;EmptyLatentImage:Empty Latent Image:height;EmptySD3LatentImage:aspect_ratios_size:height;ImageResize+:resize_input_image:height;KolorsSampler:main_sampler:height;easy int:aspect_ratios_height:value',

        'prompt': 'CLIPTextEncode:prompt:text;CLIPTextEncode:CLIP Text Encode (Positive):text;ZImageTextEncoder:prompt:user_prompt;MZ_ChatGLM3_V2:prompt:text;KolorsTextEncode:prompt_negative_prompt:prompt;CLIPTextEncodeFlux:prompt:t5xxl;CLIPTextEncodeFlux:prompt:clip_l',

        'negative_prompt': 'CLIPTextEncode:negative_prompt:text;CLIPTextEncode:CLIP Text Encode (Negative):text;ZImageTextEncoderSimple:negative_prompt:user_prompt;MZ_ChatGLM3_V2:negative_prompt:text;KolorsTextEncode:prompt_negative_prompt:negative_prompt',

        'clip_model': 'DualCLIPLoader:clip_model:clip_name1;DualCLIPLoaderGGUF:clip_model:clip_name1;CLIPLoaderGGUF:clip_model:clip_name;CLIPLoader:clip_model:clip_name;TripleCLIPLoader:clip_model:clip_name3',

        'llms_model': 'MZ_ChatGLM3Loader:llms_model:chatglm3_checkpoint;DownloadAndLoadChatGLM3:llms_model:precision',
        'input_image': 'LoadImage:input_image:image',
        'layer_diffuse_injection': 'LayeredDiffusionApply:layer_diffuse_apply:config',
        'sd_version': 'LayeredDiffusionDecode:layer_diffuse_decode:sd_version;LayeredDiffusionDecodeRGBA:layer_diffuse_decode_rgba:sd_version',
        'layer_diffuse_cond': 'LayeredDiffusionCondApply:layer_diffuse_cond_apply:config',
        'light_source_text_switch': 'easy imageSwitch:ic_light_source_text_switch:boolean',
        'light_source_shape_switch': 'easy imageSwitch:ic_light_source_shape_switch:boolean',
        'light_source_text': 'LightSource:ic_light_source_text:light_position',
        'light_apply': 'LoadAndApplyICLightUnet:ic_light_apply:model_path',
        'light_detail_transfer': 'DetailTransfer:ic_light_detail_transfer:mode',
        'light_source_start_color': 'CreateGradientFromCoords:ic_light_source_color:start_color',
        'light_source_end_color': 'CreateGradientFromCoords:ic_light_source_color:end_color',
        'light_editor_path': 'SplineEditor:ic_light_editor:points_store'
    }


    def set_mapping_rule(self, maps):
        self.fooo2node.update(maps)

    def update_params(self, new_parms):
        self.params.update(new_parms)

    def delete_params(self, keys):
        for k in keys:
            if k in self.params:
                del self.params[k]

    def convert2comfy(self, workflow):
        #print(f'params:{self.params}')
        self.workflow = workflow
        for (pk1,v) in self.params.items():
            if pk1 in self.fooo2node:
                nk = self.fooo2node[pk1]
                self.replace_key(nk,v)
        return self.workflow


    def replace_key(self,nk,v):
        lines = nk.split(';')
        for line in lines:
            parts = line.strip().split(':')
            class_type = parts[0].strip()
            meta_title = parts[1].strip()
            inputs = parts[2].strip()

            # Slash-Proofing: Normalize slashes to match the host OS for all model files
            if isinstance(v, str) and any(ext in v.lower() for ext in ['.safetensors', '.gguf', '.ckpt', '.bin', '.pt']):
                v = v.replace('/', os.sep).replace('\\', os.sep)

            for n in self.workflow.keys():
                if self.workflow[n]["class_type"]==class_type and self.workflow[n]["_meta"]["title"]==meta_title:
                    if '|' in inputs:
                        keys = inputs.split('|')
                        vs = v.strip().split('|')
                        for i in range(len(keys)):
                            self.workflow[n]["inputs"][keys[i]] = vs[i]
                    else:
                        self.workflow[n]["inputs"][inputs] = v
        return
