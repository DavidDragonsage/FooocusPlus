import os
import logging
from pathlib import Path
from modules.launch_util import verify_installed_version
import args_manager as args
import common
import modules.user_structure as US

full_file = True # identifies if language file is complete
english_from_language = ''
english_to_language = ''
language_from_english = ''
language_to_english = ''
language_name = ''


def interpret(txt_translate, txt_no_translate = '', silent = False):
    # for console messages only, not for the UI
    # always translates from English to the selected language
    if not args.args.language.startswith('en') and txt_translate:
        import argostranslate.translate
        txt_translate = txt_translate.replace('_',' ')
        logging.getLogger("stanza").disabled = True
        try:    # workaround for occasional "Access is denied" errors
            txt_translate = argostranslate.translate.translate(txt_translate, "en", args.args.language)
        except:
            pass
    txt_translate = (txt_translate + " " + str(txt_no_translate)).strip()
    if not silent:
        print(txt_translate)
    return txt_translate


def translate(txt_translate, auto=False):
    # auto = txt_translate entered by code, not from UI Translate button
    # do not translate English or pre-translated text that starts with a space)
    global english_from_language, english_to_language, language_from_english, language_to_english
    if not args.args.language.startswith('en') and txt_translate and common.prompt_translator:
        if txt_translate.startswith(' ') and auto:
            return txt_translate
        import argostranslate.translate
        print()
        logging.getLogger("stanza").disabled = True
        if txt_translate.startswith(' '):
            print(f'{language_from_english}: "{txt_translate}"')
            txt_translate = argostranslate.translate.translate(txt_translate, "en", args.args.language)
            print()
            print(f'{english_to_language}: "{txt_translate}"')
        else:
            print(f'{english_from_language}: "{txt_translate}"')
            txt_translate = argostranslate.translate.translate(txt_translate, args.args.language, "en")
            if auto == False:
               txt_translate = ' ' + txt_translate # space indicates text that is already translated
            print()
            print(f'{language_to_english}: "{txt_translate}"')
        print()
    return txt_translate


def find_language_file(arg_code, fallback = False):
    global full_file
    localization_path = Path('language')
    full_file = True
    full_path = None
    if isinstance(arg_code, str):
        filename = arg_code + '.json'
        full_path = Path(localization_path/filename)

        # adjust for incomplete language files
        # that are flagged with an initial "_":
        if not full_path.is_file():
            temp_code = '_' + arg_code + '.json'
            full_path = Path(localization_path/temp_code)
            full_file = False

        if fallback:
            # if no language file, revert to English master:
            if not full_path.is_file():
                arg_code = 'en_master'
                full_path = Path(localization_path/'en_master.json')
            # if no master language file, revert to US English:
            if not full_path.is_file():
                arg_code = 'en'
                full_path = Path(localization_path/'en.json')
    return full_path, arg_code


def check_localization(arg_code):
    global language_name
    full_path, arg_code = find_language_file(arg_code)
    if not full_path.is_file():
        print()
        interpret(f'The FooocusPlus user interface does not support: {language_name}')
    elif not full_file:
        print()
        interpret(f'The FooocusPlus user interface has incomplete support for: {language_name}')
    else:
        return

    interpret('We are looking for a volunteer interpreter!')
    if arg_code == 'zh':  # "Wiki" sends the Chinese translator ballistic!
        interpret('Please check this FooocusPlus article:')
    else:
        interpret('Please check this FooocusPlus Wiki article:')
    print(' https://github.com/DavidDragonsage/FooocusPlus/wiki/Language-Localization-File-Editing')
    interpret('Contact us at the Discussion page:')
    print(' https://github.com/DavidDragonsage/FooocusPlus/discussions')
    interpret('or at the Facebook group:')
    print(' https://www.facebook.com/groups/fooocus')
    interpret(' if you are able to help out.')
    print()

    return


def make_translation_msgs(package_to_install):
    global english_from_language, english_to_language, language_from_english, language_to_english, language_name
    str_language = str(package_to_install).split()
    language_name = str_language[-1]
    english_from_language = interpret('Translate from', language_name, True)
    english_to_language = interpret('Translate to', language_name, True)
    language_from_english = interpret('Translate from English', '', True)
    language_to_english = interpret('Translate to English', '', True)
    return

def load_translator_pack(from_code, to_code):
    # Download and install Argos Translate language package
    import argostranslate.package
    import argostranslate.translate
    argostranslate.package.update_package_index()
    available_packages = argostranslate.package.get_available_packages()
    package_to_install = next(
        filter(
            lambda x: x.from_code == from_code and x.to_code == to_code, available_packages
        ),
        None  # Return None if no matching package is found
    )

    # If the package is found, download and install it
    if package_to_install:
        print()
        print(f"Activating the package for {package_to_install}...")
        argostranslate.package.install_from_path(package_to_install.download())
        install_msg = f'The {package_to_install} package is now available'
        # Translate
        if from_code == 'en':
            translated_msg = argostranslate.translate.translate(install_msg, from_code, to_code)
            make_translation_msgs(package_to_install)
        else:
            translated_msg = argostranslate.translate.translate(install_msg, to_code, from_code)
        print(translated_msg)
    else:
        args.args.language = 'en' # revert to English for non-supported languages
        print(f"No package found for translating from '{from_code}' to '{to_code}'")
    return


def load_translator():
    print()
    print('[Translator] Verifying the prompt translation function:')
    if verify_installed_version('argostranslate', '1.9.6', False):
        verify_installed_version('ctranslate2', '4.0', False)
        verify_installed_version('spacy', '3.8.7', False)
        print(' Loading the Argos Translate library')

        # hide warnings: "Language %s package %s expects mwt, which has been added"
        #logging.getLogger("stanza").setLevel(logging.ERROR) # no effect
        logging.getLogger("stanza").disabled = True

        # Download and install an Argos Translate language package
        if args.args.language == 'cn':
            args.args.language = 'zh' # use language code instead of country code
        load_translator_pack("en", args.args.language)
        load_translator_pack(args.args.language, "en")
        check_localization(args.args.language)
    return
