#!/usr/bin/env python

# Copyright JS Foundation and other contributors, http://js.foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import jerry_client_ws
from cmd import Cmd
from pprint import pprint
import math
import select
import socket
import struct
import sys
import argparse
import logging
import os
import time


class DebuggerPrompt(Cmd):

    def __init__(self, debugger):
        Cmd.__init__(self)
        self.debugger = debugger
        self.stop = False
        self.quit = False
        self.cont = True
        self.non_interactive = False
        self.dsp = 0
        self.display = 0
        self.show = 0

    def precmd(self, line):
        self.stop = False
        self.cont = False
        if self.non_interactive:
            print("%s" % line)
        return line

    def postcmd(self, stop, line):
        return self.stop


    def do_quit(self, _):
        """ Exit JerryScript debugger """
        self.debugger.quit()
        self.quit = True
        self.stop = True

    def do_display(self, args):
        """ Toggle source code display after breakpoints """
        if args:
            line_num = self.src_check_args(args)
            if line_num >= 0:
                self.display = line_num
            else:
                return
        else:
            print("Non-negative integer number expected, 0 turns off this function")
            return
        if self.dsp > 0:
            self.debugger.stop()
        self.cont = False

    def do_break(self, args):
        """ Insert breakpoints on the given lines or functions """
        if args == "":
            print("Error: Breakpoint index expected")
        elif ':' in args:
            try:
                args_second = int(args.split(':', 1)[1])
                if args_second < 0:
                    print("Error: Positive breakpoint index expected")
                else:
                    sbreak = self.debugger.set_break(args)
            except ValueError as val_errno:
                print("Error: Positive breakpoint index expected: %s" % val_errno)
        else:
            sbreak = self.debugger.set_break(args)
        if sbreak is not None:
            print(sbreak)

    do_b = do_break

    def do_list(self, _):
        """ Lists the available breakpoints """
        if self.debugger.active_breakpoint_list:
            print("=== %sActive breakpoints %s ===" % (self.debugger.green_bg, self.debugger.nocolor))
            for breakpoint in self.debugger.active_breakpoint_list.values():
                print(" %d: %s" % (breakpoint.active_index, breakpoint))

        if self.debugger.pending_breakpoint_list:
            print("=== %sPending breakpoints%s ===" % (self.debugger.yellow_bg, self.debugger.nocolor))
            for breakpoint in self.debugger.pending_breakpoint_list.values():
                print(" %d: %s (pending)" % (breakpoint.index, breakpoint))

        if not self.debugger.active_breakpoint_list and not self.debugger.pending_breakpoint_list:
            print("No breakpoints")

    def do_delete(self, args):
        """ Delete the given breakpoint, use 'delete all|active|pending' to clear all the given breakpoints """
        if not args:
            print("Error: Breakpoint index expected")
            print("Delete the given breakpoint, use 'delete all|active|pending' to clear all the given breakpoints ")
        elif args in ['all','pending','active']:
            result = self.debugger.delete(args)
            if len(result) > 0:
                print(result)
        else:
            try:
                breakpoint_index = int(args),
                result = self.debugger.delete(args)
            except ValueError as val_errno:
                result = "Error: Integer number expected, %s" % (val_errno)

    def do_next(self, args):
        """ Next breakpoint in the same context """
        if args != '':
            while int(args) != 0:
                result = self.debugger.next(1)
                if '\3' in result:
                    result = result.replace('\3','')
                print(result)
                time.sleep(0.1)
                if self.display > 0:
                    print_source(self.debugger, self.display, self.debugger.src_offset)
                #    self.display = 0
                #if self.dsp == 1:
                #    print_source(self.debugger, self.debugger.display, self.debugger.src_offset)
                args = int(args) - 1
        else:
            result = self.debugger.next(1)
            if '\3' in result:
                result = result.replace('\3','')
            print(result)
            time.sleep(0.3)
            if self.display > 0:
                print_source(self.debugger, self.display, self.debugger.src_offset)
            #    self.display = 0
            #if self.dsp == 1:
            #    print_source(self.debugger, self.debugger.display, self.debugger.src_offset)
        self.cont = False
    do_n = do_next

    def do_step(self, _):
        """ Next breakpoint, step into functions """
        result = self.debugger.step()
        if '\3' in result:
            result = result.replace('\3','')
        print(result)
        if self.display > 0:
            print_source(self.debugger, self.display, self.debugger.src_offset)
        #    self.display = 0
        #if self.dsp == 1:
        #    print_source(self.debugger,self.debugger.display,0)
        self.cont = False
    do_s = do_step

    def do_backtrace(self, args):
        """ Get backtrace data from debugger """
        print(self.debugger.backtrace(args))
        self.show = 1
        self.stop = True

    do_bt = do_backtrace

    def do_src(self, args):
        """ Get current source code """
        if args:
            line_num = self.src_check_args(args)
            if line_num >= 0:
                print_source(self.debugger, line_num, 0)
            elif line_num == 0:
                print_source(self.debugger, self.debugger.default_viewrange, 0)
            else:
                return

    do_source = do_src

    def do_scroll(self, _):
        """ Scroll the source up or down """
        while True:
            key = sys.stdin.readline()
            if key == 'w\n':
                self._scroll_direction("up")
            elif key == 's\n':
                self._scroll_direction("down")
            elif key == 'q\n':
                break
            else:
                print("Invalid key")

    def _scroll_direction(self, direction):
        """ Helper function for do_scroll """
        self.debugger.src_offset_diff = int(max(math.floor(self.debugger.display / 3), 1))
        if direction == "up":
            self.debugger.src_offset -= self.debugger.src_offset_diff
            print_source(self.debugger, self.debugger.display, self.debugger.src_offset)
        else:
            self.debugger.src_offset += self.debugger.src_offset_diff
            print_source(self.debugger, self.debugger.display, self.debugger.src_offset)

    def do_continue(self, _):
        """ Continue execution """
        result = self.debugger.get_continue()
        if result is None:
            self.quit = True
            self.stop = True
        elif '\3' in result:
            result = result.replace('\3','')
            if len(result) > 0:
                print(result)
            self.quit = True
            self.stop = True
        else:
            print(result)
            self.stop = True
            self.cont = False
        
        #if not self.non_interactive:
        #    print("Press enter to stop JavaScript execution.")
        if self.display > 0:
            print_source(self.debugger, self.display, self.debugger.src_offset)
            #self.display = 0
        #if self.dsp == 1:
        #    print_source(self.debugger, self.debugger.display, self.debugger.src_offset)

    do_c = do_continue

    def do_finish(self, _):
        """ Continue running until the current function returns """
        result = self.debugger.finish()
        if '\3' in result:
            result = result.replace('\3','')
        print(result)
        if self.dsp == 1:
            print_source(self.debugger, self.debugger.display, self.debugger.src_offset)
        self.cont = True

    do_f = do_finish

    def do_dump(self, args):
        """ Dump all of the debugger data """
        if args:
            print("Error: No argument expected")
        else:
            pprint(self.debugger.function_list)

    def do_eval(self, args):
        """ Evaluate JavaScript source code """
        print(self.debugger.eval(args))

    do_e = do_eval

    def do_memstats(self, _):
        """ Memory statistics """
        print(self.debugger.memstats())

    do_ms = do_memstats

    def do_abort(self, args):
        """ Throw an exception """
        abort = self.debugger.abort(args)

        self.stop = True
        self.quit = True
        if '\3' in abort:
            abort = abort.replace('\3','')
        if len(abort) == 0:
            if self.dsp == 1:
                print_source(self.debugger, self.debugger.display, self.debugger.src_offset)
        else:
            print(abort)
            self.quit = True
            self.stop = True

    def do_throw(self, args):
        """ Throw an exception """
        throw = self.debugger.throw(args)
        if '\3' in throw:
            throw = throw.replace('\3','')
        print(throw)
        if 'err:' in throw:
            self.quit = True
            self.stop = True
        
        if self.dsp == 1:
            print_source(self.debugger, self.debugger.display, self.debugger.src_offset)
            #self.debugger.stop()

    def do_exception(self, args):
        """ Config the exception handler module """
        print(self.debugger.exception(args))

    def src_check_args(self, args):
        try:
            line_num = int(args)
            if line_num < 0:
                print("Error: Non-negative integer number expected")
                return -1

            return line_num
        except ValueError as val_errno:
            print("Error: Non-negative integer number expected: %s" % (val_errno))
            return -1

def print_source(debugger, line_num, offset):
    last_bp = debugger.last_breakpoint_hit
    if not last_bp:
        return

    lines = last_bp.function.source
    if last_bp.function.source_name:
        print("Source: %s" % (last_bp.function.source_name))

    if line_num == 0:
        start = 0
        end = len(last_bp.function.source)
    else:
        start = max(last_bp.line - line_num, 0)
        end = min(last_bp.line + line_num - 1, len(last_bp.function.source))
        if offset:
            if start + offset < 0:
                debugger.src_offset += debugger.src_offset_diff
                offset += debugger.src_offset_diff
            elif end + offset > len(last_bp.function.source):
                debugger.src_offset -= debugger.src_offset_diff
                offset -= debugger.src_offset_diff

            start = max(start + offset, 0)
            end = min(end + offset, len(last_bp.function.source))

    for i in range(start, end):
        if i == last_bp.line - 1:
            print("%s%4d%s %s>%s %s" % (debugger.green, i + 1, debugger.nocolor, debugger.red, \
                                        debugger.nocolor, lines[i]))
        else:
            print("%s%4d%s   %s" % (debugger.green, i + 1, debugger.nocolor, lines[i]))


def main():
    args = jerry_client_ws.arguments_parse()

    debugger = jerry_client_ws.JerryDebugger(args.address)
    #db = jerry_client_ws.init_debugger(debugger)

    non_interactive = args.non_interactive

    logging.debug("Connected to JerryScript on %d port", debugger.port)

    prompt = DebuggerPrompt(debugger)
    prompt.prompt = "(jerry-debugger) "
    prompt.non_interactive = non_interactive

    if args.color:
        debugger.set_colors()

    if args.display:
        prompt.dsp = 1
        debugger.display = args.display
        prompt.do_display(args.display)
        prompt.cont = False
    else: 
        prompt.dsp = 0
        if not args.client_source:
            print(prompt.debugger.show_display(0))
        prompt.cont = False

    if args.exception is not None:
        prompt.do_exception(str(args.exception))

    if args.client_source is not None:
        if args.client_source != []:
            clsrc = prompt.debugger.store_client_sources(args.client_source)
            if '\3' in clsrc:
                clsrc = clsrc.replace('\3','')
            print(clsrc)
            #print(prompt.debugger.store_client_sources(args.client_source))

    while True:
        if not non_interactive and prompt.cont:
            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.readline()
                prompt.cont = False
                prompt.debugger.stop()
                if args.display:
                    print_source(prompt.debugger, prompt.display, 0)
                continue
        else:
            if args.display and prompt.show == 0:
                print_source(prompt.debugger, prompt.display, 0)
            prompt.cmdloop()

        if prompt.quit:
            break


if __name__ == "__main__":
    try:
        main()
    except socket.error as error_msg:
        ERRNO = error_msg.errno
        MSG = str(error_msg)
        if ERRNO == 111:
            sys.exit("Failed to connect to the JerryScript debugger.")
        elif ERRNO == 32 or ERRNO == 104:
            sys.exit("Connection closed.")
        else:
            sys.exit("Failed to connect to the JerryScript debugger.\nError: %s" % (MSG))