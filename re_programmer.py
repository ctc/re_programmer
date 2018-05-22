#!/usr/bin/python
# copyright (c) 2014 Ingo Flaschberger
# enocean raspberry programmer

import RPi.GPIO as GPIO
import spidev
import time
import pickle
from intelhex import IntelHex
import re
import sys
import os
import argparse
import textwrap

# config parameters
PORT_RESET = 7 # GPIO4
PORT_READY = 11 # GPI17
PORT_PMODE = 13 # GPI27
SAVE_PATH = 'data'
SPI_MAX_SPEED = 2000000

CMD_RD_SW_VERSION = 0x4B
CMD_RD_FLASH_PAGE = 0x69
CMD_WR_PRG_AREA = 0x6E
CMD_WR_FLASH_PAGE = 0x6A
CMD_WR_FLASH_BYTE = 0x6C
CMD_WR_BIST = 0x71
CMD_RD_PRG_AREA = 0x6D
ANSW_INF_OK = 0x58

PAGE_INFO = 128
PAGE_CONF = 127
SIZE_INFO = 1
SIZE_CONF = 1

spi = 0
text = ''

def Main():

    parser = argparse.ArgumentParser( description='Enocean module programmer for Raspberry Pi.', formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument( '-c', '--conf', dest='conf_file', action='store', default='', help='configuration file in intel hex format')
    parser.add_argument( '-p', '--prog', dest='prog_file', action='store', default='', help='program file in intel hex format') 
    parser.add_argument( '-f', '--force', dest='force', action='store_const', default=False, const=True, help='force local stored config')
    parser.add_argument( '-l', '--lock', dest='lock', action='store_const', default=False, const=True, help='set codeprotection')
    parser.add_argument( '-v', '--version', action= 'version', version= textwrap.dedent("%(prog)s 1.2\ncopyright 2014 Ingo Flaschberger"))
    args = parser.parse_args()

    try:
        os.system( '/sbin/modprobe spi-bcm2708 -q')
    except:
        os.system( '/sbin/modprobe spi-bcm2835')

    if( not os.path.isdir( SAVE_PATH)):
        os.system( 'mkdir ' + SAVE_PATH)

    print( "Info:")
    if( args.prog_file != ''):
        print( "\tFlash program file: " + args.prog_file)
    if( args.conf_file != ''):
        print( "\tFlash config file: " + args.prog_file)
    if( args.prog_file == '' and args.conf_file == ''):
        print( "\tRead config from module only")

    try:
        Init()
        Connect()
        info = ReadInfo()
        old_conf = ReadConfig( info['id'], args.force)
        
        if( args.prog_file != '' or args.conf_file != ''):
            if( args.conf_file == ''):
                new_conf = old_conf
            else:
                new_conf = MergeConfig( old_conf, args.conf_file)
            program_size = GetProgSize( new_conf)
            if( args.prog_file != ''):
                new_program = ReadProgram( args.prog_file)
                WriteProgArea( new_program, program_size)
            else:
                new_program = None
            WriteConfigArea( new_conf, True if (args.prog_file != '') else False)
            ExecuteBist()
            Verify( new_conf, new_program, program_size)
            if( args.lock == True):
                CodeProtect()
                VerifyCodeProtect()
    finally:
        End()

def Init():
    GPIO.setmode(GPIO.BOARD)

def End():
    global spi
    Enable( 0)
    Reset( 0)
    if( spi != 0):
        spi.close()
    time.sleep( 0.001)
    Reset( 1)
    time.sleep( 0.001)
    Reset( 0)
    GPIO.cleanup()

def Enable( state):
    GPIO.setup( PORT_PMODE, GPIO.OUT)
    GPIO.output( PORT_PMODE, state)

def Reset( state):
    GPIO.setup( PORT_RESET, GPIO.OUT)
    GPIO.output( PORT_RESET, state)

def Ready():
    GPIO.setup( PORT_READY, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    return GPIO.input( PORT_READY)


def List2Hex( data, delimiter = ' '):
    hex = delimiter.join('%02X' % d for d in data)
    return hex

def GetSWVersion():
    data = [ 0xA5, 0x5A, 0xA5, CMD_RD_SW_VERSION, 0x00, 0x00, 0x00, 0x00]
    data[7] = CalcChecksum( data)
    Send( data)
    data = Receive( 8)

    if( data[7] != CalcChecksum( data)):
        raise Exception( "GetSWVersion: wrong chksum: should: " + List2Hex( [data[7]]) + " is: " + List2Hex( [CalcChecksum( data)]))

    if( data[0] != 0xa5 or data[1] != 0x5a or data[2] != 0xa5 or data[3] != 0x8c):
        raise Exception( "GetSWVersion: wrong answer")
           
    print( "\tdetected bootloader version: " + str( data[4]) + "." + str( data[5]) + "." + str( data[6]))
    
def ReverseBits(byte):
    byte = ((byte & 0xF0) >> 4) | ((byte & 0x0F) << 4)
    byte = ((byte & 0xCC) >> 2) | ((byte & 0x33) << 2)
    byte = ((byte & 0xAA) >> 1) | ((byte & 0x55) << 1)
    return byte

def Send( buffer):
    global spi

    text_clear()
    count = 0
    n = 4
    for i in range(0, len( buffer), n):
        count += 4
        if( count % 1024 == 0):
            text_reprint( "\tWrote: " + str( count/1024) + " KB\n")
    
        send = list( buffer[i:i+n])
        #print( 'send' + str(i) + ': ' + List2Hex( send))
        
        if( Ready() != 1):
            WaitTillReady( 500)
        
        spi.xfer2( send)
        time.sleep( 0.00002)

def WaitTillReady( max):
    
    for x in range(0, max):
        if( Ready() != 1):
            time.sleep( 0.001)
        else:
            return
    raise Exception( "Enocean Module not ready")

def Receive( size):
    global spi

    text_clear()
    count = 0    
    n = 4
    receive = []
    for  i in range(0, size, n):
        count += 4
        if( count % 1024 == 0):
            text_reprint( "\tRead: " + str( count/1024) + " KB\n")
            
        if( Ready() != 1):
            WaitTillReady( 500)

        recv =  spi.xfer2( [ 0, 0, 0, 0])
        receive += recv
    return receive

def CalcChecksum( buffer):
    chksum = 0
    for i in range(2, 7):
         chksum += buffer[i]
         #print( "calc: " + List2Hex( [buffer[i]]) + "\n")
    return chksum % 256

def ReadFlashPage( start, size):
    global spi

    data = [ 0xA5, 0x5A, 0xA5, CMD_RD_FLASH_PAGE, start, 0x00, 0x00, 0x00]
    data[7] = CalcChecksum( data)
    Send( data)
    data = Receive( 8)
    InfoOk( data, 'ReadFlashPage')
    data = Receive( size * 256);
    return data

def Connect():
    global spi

    print( "Connect to module")
    Enable( 1)
    Reset( 1)
    spi = spidev.SpiDev()
    spi.open(0,0)
    spi.max_speed_hz = SPI_MAX_SPEED
    time.sleep( 0.001)
    Reset( 0);
    time.sleep( 0.001)
    if( Ready() != 1):
        raise Exception( "Failed to detect Enocean Module or not ready")
    Enable( 0);
    GetSWVersion()

def ReadInfo():

    print( "Read info area")
    info = ReadFlashPage( PAGE_INFO, SIZE_INFO)
    lot = info[2:7]
    print( "\tlot:\t" + chr(lot[0]) + chr(lot[1]) + chr(lot[2]) + chr(lot[3]) + ('%02X' %  lot[4]))
    id = info[64:68]
    print( "\tid:\t" + List2Hex( id, ''))
    _lock = info[255]
    if( _lock == 0x7F):
        lock = True
        print( "\tlock:\tyes")
    else:
        lock = False
        print( "\tlock:\tno")
    return  { 'lot': lot, 'id': id, 'lock': lock}

def ReadConfig( id = '', force_backup = False, clear_code_protect = True):

    print( "Read config area")
    if( force_backup == True):
        try:
            conf_hex = IntelHex( SAVE_PATH + '/' + List2Hex( id, '') + '_cfg.hex')
            if( len( conf_hex.tobinarray()) != 256):
                raise Exception( "ReadConfig: wrong config file size: " + SAVE_PATH + '/' + List2Hex( id, '') + '_cfg.hex')
            print( "\tloaded config from backup:")
            DecodeConfig( conf_hex, '\t\t')
        except:
            raise Exception( "ReadConfig: no backup config found")
        print( "\tDone")
        return conf_hex

    conf = ReadFlashPage( PAGE_CONF, SIZE_CONF)
    if( clear_code_protect == True):
        conf[1] = 0xFF; # disable code-protect

    hex = {}
    conf_hex = IntelHex( hex)
    i = 0
    empty = True
    for c in conf:
        conf_hex[i] = c
        i+=1
        if( c != 0xFF):
            empty = False

    if( id != ''):
        if( empty == True):
            try:
                print( "\tEmpty config area, read config from backup: " + SAVE_PATH + '/' + List2Hex( id, '') + '_cfg.hex')
                conf_hex = IntelHex( SAVE_PATH + '/' + List2Hex( id, '') + '_cfg.hex')
                if( len( conf_hex.tobinarray()) != 256):
                    raise Exception( "ReadConfig: wrong config file size: " + SAVE_PATH + '/' + List2Hex( id, '') + '_cfg.hex')
                print( "\tloaded config from backup:")
                DecodeConfig( conf_hex, '\t\t')
            except:
                raise Exception( "ReadConfig: empty chip and no backup config found")
        else:
            conf_hex.tofile( SAVE_PATH + '/' + List2Hex( id, '') + '_cfg.hex', format='hex')
            print( "\tloaded config from module:")
            DecodeConfig( conf_hex, '\t\t')
            print( "\t\tdumped config to: " + SAVE_PATH + '/' + List2Hex( id, '') + '_cfg.hex')
    
    print( "\tDone")
    return conf_hex

def DecodeConfig( conf_hex, prefix = ''):
    conf = conf_hex.tobinarray()
    api = conf[4:8]
    print( prefix + "API version:\t\t" + str( api[0]) + '.' +  str( api[1]) + '.' +  str( api[2]) + '.' +  str( api[3]))
    app = conf[8:12]
    print( prefix + "App version:\t\t" + str( app[0]) + '.' +  str( app[1]) + '.' +  str( app[2]) + '.' +  str( app[3]))
    desc = str(bytearray(conf[12:28])).split("\0")[0]
    print( prefix + "App description:\t" + desc)

def MergeConfig( old_conf, new_conf_file):
    print( "Merge config:")
    new_conf = IntelHex( new_conf_file)
    old_conf.merge( new_conf, overlap='replace')
    print( "\tnew config:")
    DecodeConfig( old_conf, prefix = '\t\t')
    return old_conf

def GetProgSize( conf):
    return conf[0]

def InfoOk( data, caller):
    if( data[7] != CalcChecksum( data)):
        raise Exception( caller + ": wrong chksum: should: " + List2Hex( [data[7]]) + " is: " + List2Hex( [CalcChecksum( data)]))

    if( data[0] != 0xa5 or data[1] != 0x5a or data[2] != 0xa5 or data[3] != ANSW_INF_OK):
        raise Exception( caller + ": wrong answer")

def ReadProgram( prog_file):
    prog_hex = IntelHex( prog_file)
    
    if( len( prog_hex.tobinarray()) % 256 != 0):
        raise Exception( "ReadProgram: wrong program file size: " + prog_file)
    return prog_hex

def WriteProgArea( prog_hex, size):

    print( "Write program area to module")
    
    prog = prog_hex.tobinarray()
    
    if( len( prog) != size*256):
        raise Exception( "WriteProgArea: wrong program size")
    
    # erase
    data = [ 0xA5, 0x5A, 0xA5, CMD_WR_PRG_AREA, size, 0x00, 0x00, 0x00]
    data[7] = CalcChecksum( data)
    Send( data)
    data = Receive( 8)
    InfoOk( data, 'WriteProgArea')
    # program
    Send( prog)
    data = Receive( 8)
    InfoOk( data, 'WriteProgArea')
    print( "\tDone")

def WriteFlashPage( start, write):
    
     data = [ 0xA5, 0x5A, 0xA5, CMD_WR_FLASH_PAGE, start, 0x00, 0x00, 0x00]
     data[7] = CalcChecksum( data)
     Send( data)
     data = Receive( 8)
     InfoOk( data, 'WriteFlashPage')
     Send( write)
     data = Receive( 8)
     InfoOk( data, 'WriteFlashPage')

def WriteConfigArea( new_conf_hex, update_prog_size):

    print( "Write config area to module")
    new_conf = new_conf_hex.tobinarray()
    WriteFlashPage( PAGE_CONF, new_conf)
    
    if( update_prog_size): 
        # 1st 4 bytes are only byte access
        WriteFlashByte( PAGE_CONF * 256 + 0, new_conf[0])
        WriteFlashByte( PAGE_CONF * 256 + 1, new_conf[1])
        WriteFlashByte( PAGE_CONF * 256 + 2, new_conf[2])
        WriteFlashByte( PAGE_CONF * 256 + 3, new_conf[3])
    
    print( "\tDone")

def WriteFlashByte( address, write):
    
    data = [ 0xA5, 0x5A, 0xA5, CMD_WR_FLASH_BYTE, int( address / 256), int( address % 256), write, 0x00]
    data[7] = CalcChecksum( data)
    Send( data)
    data = Receive( 8)
    InfoOk( data, 'WriteFlashPage')

def WriteProgSize( size):
    print( "Write program size")
    WriteFlashByte( PAGE_CONF * 256 + 0, size)
    print( "\tDone")

def ExecuteBist():
    print( "Run builtin selftest")
    data = [ 0xA5, 0x5A, 0xA5, CMD_WR_BIST, 0x00, 0x00, 0x00, 0x00]
    data[7] = CalcChecksum( data)
    Send( data)
    data = Receive( 8)
    InfoOk( data, 'WriteFlashPage')
    if( data[4] != 0x00):
         raise Exception( "ExecuteBist: failed")
    print( "\tDone")

def Verify( new_conf_hex, new_prog_hex, program_size):
       
    print( "Verify config area")
    read_conf = ReadFlashPage( PAGE_CONF, SIZE_CONF)
    new_conf = new_conf_hex.tobinarray()
    i = 0
    for c in new_conf:
        if( c != read_conf[i]):
            raise Exception( "Verify: config area mismatch at: " + ("%X" % i))
        i += 1
    print( "\tDone")
    
    if( new_prog_hex != None):
        print( "Verify program area")
        data = [ 0xA5, 0x5A, 0xA5, CMD_RD_PRG_AREA, program_size, 0x00, 0x00, 0x00]
        data[7] = CalcChecksum( data)
        Send( data)
        data = Receive( 8)
        InfoOk( data, 'WriteFlashPage')
        read_prog = Receive( program_size * 256)
        new_prog = new_prog_hex.tobinarray()
        i = 0
        for p in new_prog:
            if( p != read_prog[i]):
                raise Exception( "Verify: program area mismatch at: " + ("%X" % i))
            i += 1
        print( "\tDone")
    
def CodeProtect():
    print( "Set codeprotect bit")
    WriteFlashByte( PAGE_CONF * 256 + 1, 0x00)
    print( "\tDone")

def VerifyCodeProtect():
    
    print( "Verify codeprotect bit")
    read_conf = ReadFlashPage( PAGE_CONF, SIZE_CONF)
    if( read_conf[1] != 0x00):
        raise Exception( "VerifyCodeProtect: codeprotection is not set")
    print( "\tDone")

def text_clear():
    global text
    text = ''

def text_moveup( lines):
    for _ in range(lines):
        sys.stdout.write("\x1b[A")

def text_reprint( _text):
    global text
    # Clear previous text by overwritig non-spaces with spaces
    text_moveup( text.count("\n"))
    sys.stdout.write(re.sub(r"[^\s]", " ", text))
    # Print new text
    lines = min( text.count("\n"), _text.count("\n"))
    text_moveup(lines)
    sys.stdout.write( _text)
    sys.stdout.flush()
    text = _text

# run
Main()
