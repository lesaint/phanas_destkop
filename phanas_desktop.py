#!/usr/bin/env python3

import argparse
import getpass

import phanas.file_utils
import phanas.logging
from phanas.credentials import InputProvider


class CliInputProvider(InputProvider):
    def get_password(self, prompt: str) -> str | None:
        return getpass.getpass(prompt=prompt)

def main():
    phanas.logging.configure_logging()

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-g",
        "--generate-sudoers",
        help="generate sudoers commands for current linux and nas user",
        action="store_true",
    )
    parser.add_argument(
        "-k", "--keepass-sync", help="run keepass synchronization", action="store_true"
    )
    parser.add_argument(
        "-b", "--backup", help="call backup script", action="store_true"
    )
    parser.add_argument(
        "-n", "--nascopy", help="call NAS copy script", action="store_true"
    )
    parser.add_argument("-ng", "--no-gui", help="do not use a GUI", action="store_true")
    parser.add_argument(
        "-m", "--automount", help="mount NAS drives (Linux only)", action="store_true"
    )
    args = parser.parse_args()

    config = phanas.file_utils.read_config_file()
    if args.generate_sudoers:
        import phanas.sudoers as sudoers

        print(sudoers.generate())
    elif args.keepass_sync:
        import phanas.keepass as keepass

        keepass.run(config, input_provider=CliInputProvider())
    elif args.backup:
        import phanas.backup as backup

        backup.run(config)
    elif args.nascopy:
        import phanas.nascopy as nascopy

        nascopy.run(config)
    elif args.automount:
        from phanas.automount import AutoMount

        AutoMount().run()
    elif args.no_gui:
        from phanas.phanas_desktop import PhanasDesktop, Output, PROGRAM_NAME
        import logging

        logger = logging.getLogger("*********")
        logger.info("%s started", PROGRAM_NAME)

        phanasDesktop = PhanasDesktop(config, logger)
        phanasDesktop.do_things(input_provider=CliInputProvider(), output=Output())
    else:
        import phanas.login_gui as login_gui

        login_gui.run(config)


if __name__ == "__main__":
    main()
