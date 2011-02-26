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

"test contour usb interface"

import StringIO
from .. import contourusb

class FakeMeter(object):
    def __init__(self, read=[], write=None):
        self._read = read
        if write is None:
            write = []
        self._write = write

    def read(self):
        return self._read.pop(0)

    def write(self, data):
        self._write.append(data)

class TestBayerCOMM(object):
    def test_simple(self):
        f = StringIO.StringIO()
        bc = contourusb.BayerCOMM(f)
        assert bc

    def test_sync(self):
        expected = 'H|\\^&||-7880|Bayer7150^1.05\\0.00^7150-SAM2193|||||||P|1|200305121635'

        # As documented, the meter shoud come back with an <ENQ>, possibly
        # preceeded by an <EOT> when send data in the initial phase

        f = FakeMeter(read=['\x04\x05','\x021H|\\^&||-7880|Bayer7150^1.05\\0.00^7150-SAM2193|||||||P|1|200305121635\x0d\x17AE\x0d\x0a', '\x04'])
        bc = contourusb.BayerCOMM(f)
        results = list(bc.sync())
        assert results == [expected]
        assert f._write == ['\x04', '\x06', '\x06']

        # The meter actually sends the header prior to the <EOT>
        # Should we care?
        expected = 'H|\\^&||uvmjq4|Bayer7390^01.20\\01.04\\04.02.19^7390-1163170'\
            '^7396-|A=1^C=63^G=1^I=0200^R=0^S=1^U=1^V=10600^X=07007007009' \
            '9180135180248^Y=360126090050099050300089^Z=1|209||||||1|2011' \
            '02142249'
        dataread = \
            '\x04\x021H|\\^&||uvmjq4|Bayer7390^01.20\\01.04\\04.02.19^7390-1163170'\
            '^7396-|A=1^C=63^G=1^I=0200^R=0^S=1^U=1^V=10600^X=07007007009' \
            '9180135180248^Y=360126090050099050300089^Z=1|209||||||1|2011' \
            '02142249\x0d\x17\x36\x35\x0d\x0a\x05'

        f = FakeMeter(read=[dataread, dataread[1:-1], '\x04'])
        bc = contourusb.BayerCOMM(f)        
        results = list(bc.sync())
        assert results == [expected]
        assert f._write == ['\x04', '\x06', '\x06']

    def test_multiread(self):
        dataread = [ '\x04\x05', 
                     '\x021G\r\x179C\r\n',
                     '\x022F\r\x179C\r\n',
                     '\x023E\r\x179C\r\n',
                     '\x024D\r\x179C\r\n',
                     '\x025C\r\x179C\r\n',
                     '\x026B\r\x179C\r\n',
                     '\x027A\r\x179C\r\n',
                     '\x020H\r\x179C\r\n',
                     '\x021G\r\x179C\r\n',
                     '\x022F\r\x179C\r\n',
                     '\x04'
                     ]

        f = FakeMeter(read=dataread)
        bc = contourusb.BayerCOMM(f)        
        results = list(bc.sync())
        assert len(results) == 10

    def test_state(self):
        dataread = [ '\x04\x05', 
                     '\x021G\r\x179C\r\n',
                     '\x022F\r\x179C\r\n',
                     '\x04'
                     ]

        f = FakeMeter(read=dataread)
        bc = contourusb.BayerCOMM(f)        

        assert bc.state == None
        for x in bc.sync():
            assert bc.state == bc.mode_data

        assert bc.state == bc.mode_precommand

    def test_ensurecommand(self):
        f = FakeMeter(read=['\x04', '\x06'])
        bc = contourusb.BayerCOMM(f)
        assert bc.state == None
        bc.ensurecommand()
        assert bc.state == bc.mode_command
        assert f._write == ['\x15', '\x05']

        bc.ensurecommand()
        assert bc.state == bc.mode_command
        assert f._write == ['\x15', '\x05']

        f = FakeMeter(read=['\x04', '\x06'])
        bc = contourusb.BayerCOMM(f)
        assert bc.state == None
        bc.state = bc.mode_precommand
        bc.ensurecommand()
        assert bc.state == bc.mode_command
        assert f._write == ['\x05', '\x05']

        
    def test_command(self):
        f = FakeMeter(read=['\x04', '\x06', 'D|0|\r\n\x06'])
        bc = contourusb.BayerCOMM(f)
        bc.state = bc.mode_command

        res = bc.command('R|')
        assert res is None # Didn't get <ACK>

        res = bc.command('W|')
        assert isinstance(res, str)
        assert len(res) == 0

        res = bc.command('M|')
        assert res == 'D|0|\r\n'
        
class TestContourUSB(object):
    def test_H(self):
        data = 'H|\\^&||uvmjq4|Bayer7390^01.20\\01.04\\04.02.19^7390-1163170'\
            '^7396-|A=1^C=63^G=1^I=0200^R=0^S=1^U=1^V=10600^X=07007007009' \
            '9180135180248^Y=360126090050099050300089^Z=1|209||||||1|2011' \
            '02142249'

        cu = contourusb.ContourUSB()
        cu.record(data)

        assert cu.field_sep == '|'
        assert cu.repeat_sep == '\\'
        assert cu.comp_sep == '^'
        assert cu.escape_sep == '&'

        assert cu.password == 'uvmjq4'
        assert cu.meter_product == 'Bayer7390'
        assert cu.meter_version == [ '01.20', '01.04', '04.02.19' ]
        assert cu.meter_serial == '7390-1163170'
        assert cu.meter_sku == '7396-'

        assert cu.device_info == { 'A': '1', 'C': '63', 'G': '1', 'I': '0200',
                                   'R': '0', 'S': '1', 'U': '1', 'V': '10600',
                                   'X': '070070070099180135180248',
                                   'Y': '360126090050099050300089', 'Z': '1'
                                   }
        assert cu.result_count == 209
        assert cu.processing_id == ''
        assert cu.spec_version == '1'
        assert cu.header_datetime == '201102142249'
                                   
