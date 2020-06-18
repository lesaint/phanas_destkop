#!/usr/bin/env python3

import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", "--generate-sudoers", help="generate sudoers commands for current linux and nas user", action="store_true")
    parser.add_argument("-k", "--keepass-sync", help="run keepass synchronization", action="store_true")
    args = parser.parse_args()
    if args.generate_sudoers:
        import phanas.sudoers as sudoers
        print(sudoers.generate())
    elif args.keepass_sync:
        import phanas.keepass as keepass
        keepass.run()
    else:
        import phanas.automount as automount
        automount.run_gui() 

if __name__ == '__main__':
    main()
