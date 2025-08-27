import os
from pathlib import Path
from modules.launch_util import verify_installed_version
import modules.user_structure as US


def load_translator(arg_language, arg_user_dir):
    print()
    print('[Translator Support] Verifying the prompt translation function:')
    if verify_installed_version('argostranslate', '1.9.6', False):
        verify_installed_version('ctranslate2', '4.0', False)
        verify_installed_version('spacy', '3.8.7', False)
        print(' The Argos Translate library is available')

        from_code = arg_language
        to_code = "en"

        # Download and install Argos Translate language package
        import argostranslate.package
        import argostranslate.translate

        translator_dir = Path(arg_user_dir/'translator_packs').resolve()
        if not US.make_dir(translator_dir):
            print(f'[Translator Support] Could not initialize the {translator_dir} directory')
            return
        return # the package install code is not working yet

        package_dir = Path(translator_dir/'packages').resolve()
        if not US.make_dir(package_dir):
            print(f'[Translator Support] Could not initialize the {package_dir} directory')
            return


        os.environ["ARGOS_TRANSLATE_PACKAGE_DIR"] = str(package_dir)
        os.environ["ARGOS_PACKAGES_DIR"] = str(package_dir)

        # Download and install Argos Translate language package
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
            print(f"Installing package for {from_code} to {to_code}...")
            argostranslate.package.install_from_path(package_to_install.download())
            print("Package installed successfully")
        else:
            print(f"No package found for translating from '{from_code}' to '{to_code}'")

    return