#!/usr/bin/env python

from delfick_app import App

class Main(App):
    def execute(self, args, extra_args, cli_args, logging_handler):
        print("Sync with amzon!")

main = Main.main
if __name__ == "__main__":
    main()
