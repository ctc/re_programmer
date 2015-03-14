<pre>
usage: re_programmer.py [-h] [-c CONF_FILE] [-p PROG_FILE] [-f] [-l] [-v]

Enocean module programmer for Raspberry Pi.

optional arguments:
  -h, --help            show this help message and exit
  -c CONF_FILE, --conf CONF_FILE
                        configuration file in intel hex format
  -p PROG_FILE, --prog PROG_FILE
                        program file in intel hex format
  -f, --force           force local stored config
  -l, --lock            set codeprotection
  -v, --version         show program's version number and exit


Allows to program program-code and optional configuration-data into a
enocean module.
Configuration-data is backuped into 'data' directory.

rasperry b(+) pinout:
 6 GND
 7 RESET
11 ADIO7
13 PROG_EN
19 WSDADIO2
21 RSDAIO3
23 SCLKDIO1
24 SCSEDIO0

because of high spi frequencies recommended flat cable layout:
GND
RESET
GND
ADIO7
GND
PROG_EN
GND
WSDADIO2
GND
RSDAIO3
GND
SCLKDIO1
GND
SCSEDIO0
GND
</pre>
