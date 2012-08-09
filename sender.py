# Copyright 2012 IKT Leibniz Universitaet Hannover
# GPL2
# Zdravko Bozakov (zb@ikt.uni-hannover.de)

import time
import logging

import hphelper
from hphelper import err, set_affinity 

logging.getLogger("scapy.runtime").setLevel(logging.ERROR)

try:
    from numpy import random as prnd
    from numpy import *

    import pcap               # python-pypcap
    from scapy.all import *
except ImportError:
    print "!! please make sure the following packages are installed:"
    print "\tpython-pypcap"
    print "\tpython-numpy"
    print "\tpython-scapy"
    exit(1)


options = hphelper.options



def checksum(packet):
    """Generates a checksum of a (ICMP) packet. Based on ping.c on
    FreeBSD"""

    #from https://subversion.grenouille.com/svn/pygrenouille/developers/tictactoc/trunk/libs/ping.py

    if len(packet) & 1:                 # any data?
        packet = packet + '\0'          # make null
    words = array.array('h', packet)    # make a signed short array of packet
    sum = 0

    for word in words:
        sum = sum + (word & 0xffff)     # bitwise AND
    hi = sum >> 16                      # bitwise right-shift
    lo = sum & 0xffff                   # bitwise AND
    sum = hi + lo
    sum = sum + (sum >> 16)

    return (~sum) & 0xffff              # bitwise invert + AND



def dummyloop(ns, slottimes):
    # notify receiver that we are ready to send
    ns.SND_READY=True
    # block until receiver says it is ready
    while not ns.RCV_READY:
        time.sleep(0.1)

    if options.DEBUG: print 'READY: ' + __name__


################################################################################
def sendloop(ns, slottimes):
    addr = (options.eth, 0x0800)
    geotimes = options.delta*slottimes

    set_affinity('sendloop')

    timetime = time.time          # faster: http://wiki.python.org/moin/PythonSpeed/PerformanceTips
 
    if ns.cnum:
        pnum = ns.cnum
    else:
        pnum = options.pnum
        print 'expected run time:\t ~%f s (mean inter packet time %.3e s)' % (geotimes[-1], options.delta/options.rate)

    try:
        s = socket.socket(socket.PF_PACKET, socket.SOCK_RAW)  # create the raw-socket
        s.bind(addr)                                          # ether type for IP e.g. ('eth1', 0x0800)
        s.setblocking(False)                                  # False = disable blocking
    except socket.error:
        err("could not create raw socket, root privileges are required!")


    # notify receiver that we are ready to send
    ns.SND_READY=True
    # block until receiver says it is ready
    while not ns.RCV_READY:
        time.sleep(0.1)

    if options.DEBUG: print 'READY: ' + __name__


    payload = '8'*payload_len

    try:
        t_start = timetime()
        geotimes += t_start

        pkt = ''.join([pkts[0],payload])

        for i in xrange(1,pnum):
            #hexdump(pkts[i])
            #Ether(pkts[i]).show2()

            s.send(pkt)
            pkt = ''.join([pkts[i],payload])


            while ((timetime() ) < geotimes[i]):
                #time.sleep(delta/4) # REVERT TODO
                pass

    except KeyboardInterrupt:
        pass

    t_total = timetime() - t_start
    if options.DEBUG:
        print "sender runtime:\t %.8f s" % (t_total)
    else:
        print '\a',           # bell

    s.close()                 # close socket


##############################################################################
# pre-generate probes on import

IP_HDR_LEN    = 20
ETHER_HDR_LEN = 14
ICMP_HDR_LEN  = 8
ARRAY_PLEN    = 100                  # number of packet bytes to store in pkts array
ARRAY_PAYLOAD = max((options.plen + ETHER_HDR_LEN) - ARRAY_PLEN,0) # need to append this number of bytes to the payload while sending
IPDST = options.IPDST


# pre-generate all ICMP packets in an numpy array so we do not have to
# waste time at runtime
pkts = empty(options.pnum, dtype=dtype((str, ARRAY_PLEN)))

try:
    p = Ether()/IP(dst=IPDST)/ICMP(type=8, seq=0, chksum=0)/Raw('8'*(options.plen-ICMP_HDR_LEN-IP_HDR_LEN))     # 8 Byte ICMP header + 20 Byte IP header
    try:
        strp = str(p)
    except socket.error:
        err("scapy needs root privileges!")
    print 'generating ICMP packets...'

    hdr = strp[:ETHER_HDR_LEN+IP_HDR_LEN]
    pkt = strp[ETHER_HDR_LEN+IP_HDR_LEN:]
    psize = options.plen + ETHER_HDR_LEN


    p = [ hdr, pkt[:2], struct.pack('<H', (0)), pkt[4:16], struct.pack('!L', (0) % 0xFFFFFFFF), pkt[20:]]     # insert 4 byte ID into ICMP payload

    ck = checksum(''.join(p[1:]))                           # calculate initial ICMP cksum

    for i in xrange(options.pnum):
        p[4] = struct.pack('!L', (i) % 0xFFFFFFFF)          # increment 4 byte ID in ICMP payload
        p[2] = struct.pack('<H', (ck))                      # update ICMP cksum

        pkts[i] = ''.join(p)[:ARRAY_PLEN]                   # only store first 100 packet bytes in the array
        ck = (ck-256) % 0xFFFF                              # increment ICMP cksum: see RFC 1141


except (MemoryError, ValueError):
    err("Not enough memory!",2)
except KeyboardInterrupt:
    print 'terminated by user.'
    raise SystemExit(-1)

print 'finished generating packets'

payload_len = ARRAY_PAYLOAD

