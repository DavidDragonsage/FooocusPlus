import os
import re
import json
import math
import gradio as gr
import common
import args_manager as args
from enhanced.translator import interpret
from modules.util import get_files_from_folder
from modules.config import path_wildcards

wildcards_max_bfs_depth = 64
wildcards = {}
wildcards_list = {}
wildcards_translation = {}
wildcards_words_translation = {}
wildcards_template = {}
wildcards_weight_range = {}

array_regex = re.compile(r'\[([\w\(\)\.\s,;:-]+)\]')
array_regex1 = re.compile(r'\[([\w\(\)\s,;.:\"-]+)\]')
tag_regex0 = re.compile(r'([\s\w\(\);-]+)')
tag_regex1 = re.compile(r'([\s\w\(\),-]+)')
tag_regex2 = re.compile(r'__([\w-]+)__')
tag_regex3 = re.compile(r'__([\w-]+)__:([\d]+)')
tag_regex4 = re.compile(r'__([\w-]+)__:([RLrl]){1}([\d]*)')
tag_regex5 = re.compile(r'__([\w-]+)__:([RLrl]){1}([\d]*):([\d]+)')
tag_regex6 = re.compile(r'__([\w-]+)__:([\d]+):([\d]+)')
wildcard_regex = re.compile(r'-([\w-]+)-')


def set_wildcard_path_list(name, list_value):
    global wildcards_list
    if name in wildcards_list.keys():
        if list_value not in wildcards_list[name]:
            wildcards_list[name].append(list_value)
    else:
        wildcards_list.update({name: [list_value]})
    return


def get_wildcards_samples(path="root"):
    global wildcards, wildcards_list, wildcards_translation, wildcards_template, wildcards_weight_range, wildcard_regex
    wildcards_list_all = sorted([f[:-4] for f in get_files_from_folder(path_wildcards, ['.txt'], None, variation=True)])
    for wildcard in wildcards_list_all:
        words = open(os.path.join(path_wildcards, f'{wildcard}.txt'), encoding='utf-8').read().splitlines()
        words = [x.split('?')[0] for x in words if x != '' and not wildcard_regex.findall(x)]
        templates = [x for x in words if '|' in x]  #  word|template|weight_range
        for line in templates:
            parts = line.split("|")
            word = parts[0]
            template = parts[1]
            weight_range = ''
            if len(parts)>2:
                weight_range = parts[2]
            if word is None or word == '':
                wildcards_template.update({wildcard: template})
                if len(weight_range.strip())>0:
                    wildcards_weight_range.update({wildcard: weight_range})
            else:
                wildcards_template({f'{wildcard}/{word}': template})
                if len(weight_range.strip())>0:
                    wildcards_weight_range.update({f'{wildcard}/{word}': weight_range})
        words = [x.split("|")[0] for x in words]
        wildcards.update({wildcard: words})
        wildcard_path = wildcard.split("/")
        if len(wildcard_path)==1:
            set_wildcard_path_list("root", wildcard_path[0])
        elif len(wildcard_path)==2:
            set_wildcard_path_list(wildcard_path[0], wildcard_path[1])
        elif len(wildcard_path)==3:
            set_wildcard_path_list(f'{wildcard_path[0]}/{wildcard_path[1]}', wildcard_path[2])
            set_wildcard_path_list(wildcard_path[0], wildcard_path[1])
        else:
            interpret('[Wildcards] The level of wildcards is too deep:', path_wildcards)
    if wildcards_list_all:
        interpret(f'[Wildcards] Refresh and Load {len(wildcards_list_all)}/{len(wildcards.keys())} wildcards: {", ".join(wildcards_list_all)}.')
        print()
    return [[interpret(x, '', True)] for x in wildcards_list[path]]


def get_words_of_wildcard_samples(wildcard="root"):
    global wildcards, wildcards_list, wildcards_words_translation
    if wildcard == "root":
        wildcard = wildcards_list[wildcard][0]
    if args.args.language == 'en' or args.args.language == 'en_uk':
        words = [[x] for x in wildcards[wildcard]]
    else:
        # keep response time reasonable:
        if len(wildcards[wildcard]) > common.wildcard_lines_to_interpret:
            words = [[x] for x in wildcards[wildcard]]
        else:
            if len(wildcards[wildcard]) > 5:
                interpret(f'Interpreting {len(wildcards[wildcard])} wildcard words...')
            words = [[interpret(x, '', True)] for x in wildcards[wildcard]]
    return words


def get_words_with_wildcard(wildcard, rng, method='R', number=1, start_at=1):
    global wildcards
    if wildcard is None or wildcard=='':
        words = []
    else:
        words = wildcards[wildcard]
    words_result = []
    number0 = number
    if method=='L' or method=='l':
        if number == 0:
            words_result = words
        else:
            if number < 0:
                number = 1
            start = start_at - 1
            if number > len(words):
                number = len(words)
            if (start + number)>len(words):
                words_result = words[start:] + words[:start + number - len(words)]
            else:
                words_result = words[start:start + number]
    else:
        if number < 1:
            number = 1
        if number > len(words):
            number = len(words)
        nums = 1 if start_at<=1 else start_at
        for i in range(number):
            words_each = rng.sample(words, nums)
            words_result.append(words_each[0] if nums==1 else f'({" ".join(words_each)})')
    words_result = [replace_wildcard(txt, rng) for txt in words_result]
    interpret(f'[Wildcards] Get words from wildcard:__{wildcard}__, method:{method}, number:{number}, start_at:{start_at}, result:{words_result}')
    return words_result


def replace_wildcard(text, rng):
    global wildcards_max_bfs_depth, tag_regex2, wildcards
    parts = tag_regex2.findall(text)
    i = 1
    while parts:
        for wildcard in parts:
            text = text.replace(f'__{wildcard}__', rng.choice(wildcards[wildcard]), 1)
        parts = tag_regex2.findall(text)
        i += 1
        if i > wildcards_max_bfs_depth:
            break
    return text


def get_words(arrays, totalMult, index):
    if(len(arrays) == 1):
        word = arrays[0][index]
        return [word]
    else:
        words = arrays[0]
        word = words[index % len(words)]
        index -= index % len(words)
        index /= len(words)
        index = math.floor(index)
        return [word] + get_words(arrays[1:], math.floor(totalMult/len(words)), index)


def add_wildcards_and_array_to_prompt(wildcard, prompt, state_params):
    global wildcards, wildcards_list
    wildcard = wildcards_list['root'][wildcard]
    state_params.update({"wildcard_in_wildcards": wildcard})
    if len(prompt)>0:
        if prompt[-1]=='_':
            state_params["array_wildcards_mode"] = '_'
            if len(prompt)==1 or len(prompt)>2 and prompt[-2]!='_':
                prompt = prompt[:-1]

    new_tag = f'__{wildcard}__'
    prompt = f'{prompt.strip()} {new_tag}'
    content_label = interpret(f'{wildcard}:', '', True)
    return gr.update(value=prompt), gr.Dataset.update(label=content_label, samples=get_words_of_wildcard_samples(wildcard)), gr.update(open=True)
    return

def add_word_to_prompt(wildcard, index, prompt):
    global wildcards, wildcards_list
    wildcard = wildcards_list['root'][wildcard]
    words = wildcards[wildcard]
    word = words[index]
    prompt = prompt.strip()
    for tag in [f'[__{wildcard}__]', f'__{wildcard}__']:
        if prompt.endswith(tag):
            prompt = prompt[:-1*len(tag)]
            break
    prompt = f'{prompt.strip()} {word}'
    return gr.update(value=prompt)
