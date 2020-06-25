#!/usr/bin/env python3

import argparse
import phanas.file_utils

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", "--generate-sudoers", help="generate sudoers commands for current linux and nas user", action="store_true")
    parser.add_argument("-k", "--keepass-sync", help="run keepass synchronization", action="store_true")
    args = parser.parse_args()

    config = phanas.file_utils.read_config_file()

    if args.generate_sudoers:
        import phanas.sudoers as sudoers
        print(sudoers.generate())
    elif args.keepass_sync:
        import phanas.keepass as keepass
        keepass.run(config)
    else:
        import phanas.login_gui as login_gui
        login_gui.run(config) 

if __name__ == '__main__':
    main()
