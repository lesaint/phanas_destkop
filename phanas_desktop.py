#!/usr/bin/env python3

import argparse
import phanas.automount as automount
import phanas.sudoers as sudoers

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", "--generate-sudoers", help="generate sudoers commands for current linux and nas user", action="store_true")
    args = parser.parse_args()
    if args.generate_sudoers:
        print(sudoers.generate())
    else:
        automount.run_gui() 

if __name__ == '__main__':
   main()
