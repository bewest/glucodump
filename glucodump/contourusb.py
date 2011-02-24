#
# Copyright (C) 2011 Anders Hammarquist <iko@iko.pp.se>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"Communication with Bayer Contour USB meter"

import usbcomm
import re

class BayerCOMM(object):
    "Framing for Bayer meters"

    framere = re.compile('\x02(?P<check>(?P<recno>[0-7])(?P<text>[^\x0d]*)'
                         '\x0d(?P<end>[\x03\x17]))'
                         '(?P<checksum>[0-9A-F][0-9A-F])\x0d\x0a')

    mode_data = object()
    mode_precommand = object()
    mode_command = object()

    def __init__(self, dev):
        self.dev = dev
        self.currecno = 1
        self.state = None

    def checksum(self, text):
        return hex(sum(ord(c) for c in text) % 256)[-2:].upper()

    def checkframe(self, frame):
        match = self.framere.match(frame)
        if not match:
            return None # invalid frame
        if int(match.group('recno')) != self.currecno:
            return None

        checksum = self.checksum(match.group('check'))
        if checksum != match.group('checksum'):
            return None

        self.currecno = (self.currecno + 1) % 8

        return match.group('text')
        
    def sync(self):
        """
        Sync with meter and yield received data frames
        """
        tometer = '\x04'
        while True:
            self.state = self.mode_data
            self.dev.write(tometer)
            data = self.dev.read()
            if data[-1] == '\x05':
                # got an <ENQ>, send <ACK>
                tometer = '\x06'
                continue
            if data[-1] == '\x04':
                # got an <EOT>, done
                self.state = self.mode_precommand
                break
            stx = data.find('\x02')
            if stx != -1:
                # got <STX>, parse frame
                result = self.checkframe(data[stx:])
                if result:
                    tometer = '\x06'
                    yield result
                else:
                    tometer = '\x15' # Couldn't parse, <NAK>

    def ensurecommand(self):
        if self.state == self.mode_command:
            return

        if self.state in (None, self.mode_data):
            while True:
                self.dev.write('\x15') # send <NAK>
                data = self.dev.read()
                if data[-1] == '\x04':
                    # got <EOT>, meter ready
                    self.state = self.mode_precommand
                    break

        if self.state == self.mode_precommand:
            while True:
                self.dev.write('\x05') # send <ENQ>
                data = self.dev.read()
                if data[-1] == '\x06':
                    self.state = self.mode_command
                    return # Got ack, now in command mode


    def command(self, data):
        """Send a command to the meter

        Enter remote command mode if needed
        """
        self.ensurecommand()

        self.dev.write(data)
        data = self.dev.read()
        if data[-1] != '\x06':
            return None
        return data[:-1]
