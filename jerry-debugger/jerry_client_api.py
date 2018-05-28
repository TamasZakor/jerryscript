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

from jerry_client_ws import *
import socket
import struct
import sys
import argparse
import logging
import os

def main():
    args = arguments_parse()

    debugger = JerryDebugger(args.address)

    if args.color:
        debugger.set_colors()

    non_interactive = args.non_interactive

    logging.debug("Connected to JerryScript on %d port", debugger.port)

    prompt = DebuggerPrompt(debugger)
    prompt.non_interactive = non_interactive

    data = ''
    data2 = ''
    next = 0
  
    while True:
        data2 = debugger.get_message(False)
        if data2 == b'':
            continue

        if not data2:
            break

        buffer_type = ord(data2[2])
        if buffer_type in [JERRY_DEBUGGER_PARSE_ERROR,
                                        JERRY_DEBUGGER_BYTE_CODE_CP,
                                        JERRY_DEBUGGER_PARSE_FUNCTION,
                                        JERRY_DEBUGGER_BREAKPOINT_LIST,
                                        JERRY_DEBUGGER_SOURCE_CODE,
                                        JERRY_DEBUGGER_SOURCE_CODE_END,
                                        JERRY_DEBUGGER_SOURCE_CODE_NAME,
                                        JERRY_DEBUGGER_SOURCE_CODE_NAME_END,
                                        JERRY_DEBUGGER_FUNCTION_NAME,
                                        JERRY_DEBUGGER_FUNCTION_NAME_END]:
                            parse_source(debugger, data2)
                            break

    if args.display:
        debugger.display = args.display
        debugger.Next(debugger, data, '1')

    if args.exception is not None:
        prompt.do_exception(str(args.exception))

    if args.client_source is not None:
        prompt.store_client_sources(args.client_source)
    

    while True:
        #if not non_interactive:
        #    if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
        #        sys.stdin.readline()
        #        prompt.cont = False
        #        debugger.send_command(JERRY_DEBUGGER_STOP)
        
        pr = raw_input("(jerry-debugger) ")

        if pr in ['quit','q']:
            debugger.quit('Quit')
            break

        elif pr in ['finish']:
            debugger.finish('finish')
            break

        elif pr in ['display']:
            if debugger.display == 0:
                debugger.display = 10
                debugger.display(debugger, debugger.display)
                debugger.display = 0
            else:
                debugger.display(debugger, debugger.display)

        elif pr in ('break','b'):
            debugger.set_break(debugger, '0')

        elif pr in ('backtrace','bt'):
            debugger.backtrace(debugger,'')

        elif pr in ['list']:
            debugger.list(debugger)

        elif pr in ['delete']:
            print(""" Delete the given breakpoint, use 'delete all|active|pending' to clear all the given breakpoints """)
        
        elif pr in ['eval','e']:    
            print(""" Evaluate JavaScript source code """)

        elif pr in ['step','s']:    
            debugger.step(debugger, 's')

        elif pr in ['source','src']:    
            debugger.src(debugger, '')

        elif pr in ['scroll']:
            debugger.scroll(debugger,'')

        elif pr in ['throw']:
            debugger.throw(debugger, 'throw')

        elif pr in ['exception']:
            debugger.exception(debugger, '')

        elif ' ' in pr:
            args_one = pr.split(' ')[0]
            args_second = pr.split(' ')[1]
            if args_one in ['delete']:
                debugger.delete(debugger,args_second)
                debugger.List(debugger)

            if args_one in ['eval','e']:
                debugger.eval(debugger,args_second)

            if args_one in ['backtrace','bt']:
                debugger.backtrace(debugger,args_second)

            if args_one in ['source','src']:
                debugger.src(debugger,args_second)

            if args_one in ['exception']:
                debugger.exception(debugger,args_second)

        elif ':' in pr:
            args_one = pr.split(':')[0]
            args_second = pr.split(':')[1]

            if args_one in ['display']:
                if args_second == 0:
                    args.display = 10
                    debugger.display(debugger, args.display)
                else:
                    debugger.display(debugger, args_second)

            elif args_one in ['break','b']:
                debugger.Break(debugger, args_second)

        elif pr in ['memstats', 'ms']:
            memstat = debugger.memstats()
            print(memstat)

        elif pr in ['c', 'continue']:
            debugger.display(debugger, args.display)
            debugger.get_continue('continue')

        elif pr in ['dump']:
            debugger.dump(debugger)

        elif pr in ['next', 'n']:
            debugger.next(debugger, data, '1')

        elif pr in ['help', 'h']:
            print('   b           c          display       ms         n     q      finish')
            print('   break:num   continue   display:num   memstats   next  quit')
            
        else:
            print('** Unknown command')

        '''
        data = debugger.get_message(False)

        if data == b'':
            continue

        if not data:  # Break the while loop if there is no more data.
            break

        buffer_type = ord(data[2])
        buffer_size = ord(data[1]) - 1

        print(buffer_type)

        logging.debug("Main buffer type: %d, message size: %d", buffer_type, buffer_size)
        #print("Main buffer type: %d, message size: %d" % (buffer_type, buffer_size))
        if buffer_type in [JERRY_DEBUGGER_PARSE_ERROR,
                           JERRY_DEBUGGER_BYTE_CODE_CP,
                           JERRY_DEBUGGER_PARSE_FUNCTION,
                           JERRY_DEBUGGER_BREAKPOINT_LIST,
                           JERRY_DEBUGGER_SOURCE_CODE,
                           JERRY_DEBUGGER_SOURCE_CODE_END,
                           JERRY_DEBUGGER_SOURCE_CODE_NAME,
                           JERRY_DEBUGGER_SOURCE_CODE_NAME_END,
                           JERRY_DEBUGGER_FUNCTION_NAME,
                           JERRY_DEBUGGER_FUNCTION_NAME_END]:
            parse_source(debugger, data)

        elif buffer_type == JERRY_DEBUGGER_WAITING_AFTER_PARSE:
            debugger.send_command(JERRY_DEBUGGER_PARSER_RESUME)

        elif buffer_type == JERRY_DEBUGGER_RELEASE_BYTE_CODE_CP:
            release_function(debugger, data)

        elif buffer_type in [JERRY_DEBUGGER_BREAKPOINT_HIT, JERRY_DEBUGGER_EXCEPTION_HIT]:
            breakpoint_data = struct.unpack(debugger.byte_order + debugger.cp_format + debugger.idx_format, data[3:])

            breakpoint = get_breakpoint(debugger, breakpoint_data)
            debugger.last_breakpoint_hit = breakpoint[0]

            if buffer_type == JERRY_DEBUGGER_EXCEPTION_HIT:
                print("Exception throw detected (to disable automatic stop type exception 0)")
                if exception_string:
                    print("Exception hint: %s" % (exception_string))
                    exception_string = ""

            if breakpoint[1]:
                breakpoint_info = "at"
            else:
                breakpoint_info = "around"

            if breakpoint[0].active_index >= 0:
                breakpoint_info += " breakpoint:%s%d%s" % (debugger.red, breakpoint[0].active_index, debugger.nocolor)

            print("Stopped %s %s" % (breakpoint_info, breakpoint[0]))
            if debugger.display:
                print_source(prompt.debugger, debugger.display, 0)

            if debugger.repeats_remain:
                prompt.do_next(debugger.repeats_remain)
                time.sleep(0.1)
            else:
                pr = raw_input("(jerry-debugger) ")
                #prompt.cmdloop()

        #elif buffer_type in ['quit','q']:
        #    debugger.Quit('Quit')
        #    break

        elif buffer_type == JERRY_DEBUGGER_EXCEPTION_STR:
            exception_string += data[3:]

        elif buffer_type == JERRY_DEBUGGER_EXCEPTION_STR_END:
            exception_string += data[3:]

        elif buffer_type in [JERRY_DEBUGGER_BACKTRACE, JERRY_DEBUGGER_BACKTRACE_END]:
            frame_index = 0

            while True:
                buffer_pos = 3
                while buffer_size > 0:
                    breakpoint_data = struct.unpack(debugger.byte_order + debugger.cp_format + debugger.idx_format,
                                                    data[buffer_pos: buffer_pos + debugger.cp_size + 4])

                    breakpoint = get_breakpoint(debugger, breakpoint_data)

                    print("Frame %d: %s" % (frame_index, breakpoint[0]))

                    frame_index += 1
                    buffer_pos += 6
                    buffer_size -= 6

                if buffer_type == JERRY_DEBUGGER_BACKTRACE_END:
                    break

                data = debugger.get_message(True)
                buffer_type = ord(data[2])
                buffer_size = ord(data[1]) - 1

                if buffer_type not in [JERRY_DEBUGGER_BACKTRACE,
                                       JERRY_DEBUGGER_BACKTRACE_END]:
                    raise Exception("Backtrace data expected")

            #prompt.cmdloop()
            pr = raw_input("(jerry-debugger) ")


        elif buffer_type in [JERRY_DEBUGGER_EVAL_RESULT,
                             JERRY_DEBUGGER_EVAL_RESULT_END,
                             JERRY_DEBUGGER_OUTPUT_RESULT,
                             JERRY_DEBUGGER_OUTPUT_RESULT_END]:
            message = b""
            msg_type = buffer_type
            while True:
                if buffer_type in [JERRY_DEBUGGER_EVAL_RESULT_END,
                                   JERRY_DEBUGGER_OUTPUT_RESULT_END]:
                    subtype = ord(data[-1])
                    message += data[3:-1]
                    break
                else:
                    message += data[3:]

                data = debugger.get_message(True)
                buffer_type = ord(data[2])
                buffer_size = ord(data[1]) - 1
                # Checks if the next frame would be an invalid data frame.
                # If it is not the message type, or the end type of it, an exception is thrown.
                if buffer_type not in [msg_type, msg_type + 1]:
                    raise Exception("Invalid data caught")

            # Subtypes of output
            if buffer_type == JERRY_DEBUGGER_OUTPUT_RESULT_END:
                message = message.rstrip('\n')
                if subtype in [JERRY_DEBUGGER_OUTPUT_OK,
                               JERRY_DEBUGGER_OUTPUT_DEBUG]:
                    print("%sout: %s%s" % (debugger.blue, debugger.nocolor, message))
                elif subtype == JERRY_DEBUGGER_OUTPUT_WARNING:
                    print("%swarning: %s%s" % (debugger.yellow, debugger.nocolor, message))
                elif subtype == JERRY_DEBUGGER_OUTPUT_ERROR:
                    print("%serr: %s%s" % (debugger.red, debugger.nocolor, message))
                elif subtype == JERRY_DEBUGGER_OUTPUT_TRACE:
                    print("%strace: %s%s" % (debugger.blue, debugger.nocolor, message))

            # Subtypes of eval
            elif buffer_type == JERRY_DEBUGGER_EVAL_RESULT_END:
                if subtype == JERRY_DEBUGGER_EVAL_ERROR:
                    print("Uncaught exception: %s" % (message))
                else:
                    print(message)

                #prompt.cmdloop()
                pr = raw_input("(jerry-debugger) ")

        #elif pr in ['memstats']:
            #buffer_type == JERRY_DEBUGGER_MEMSTATS_RECEIVE:

        #    memory_stats = struct.unpack(debugger.byte_order + debugger.idx_format *5,
        #                                 data[3: 3 + 4 *5])

        #    print("Allocated bytes: %d" % (memory_stats[0]))
        #    print("Byte code bytes: %d" % (memory_stats[1]))
        #    print("String bytes: %d" % (memory_stats[2]))
        #    print("Object bytes: %d" % (memory_stats[3]))
        #    print("Property bytes: %d" % (memory_stats[4]))

            #prompt.cmdloop()
        #    pr = raw_input("(jerry-debugger) ")

        elif buffer_type == JERRY_DEBUGGER_WAIT_FOR_SOURCE:
            prompt.send_client_source()


        else:
            raise Exception("Unknown message")
        '''

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