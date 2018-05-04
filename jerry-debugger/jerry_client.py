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
        
        JDconnect().connect
        #display(JDconnect().connect).show
        while True:
            display(JDconnect().connect).show()
            pr = raw_input("(jerry-debugger) ")
            com = Commands(pr)
            if com == -1:
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