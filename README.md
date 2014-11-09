enocean module programmer for raspberry pi board

Allows to programm programm-code and optional configuration-data into a
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
