# Copyright 2014 IKT Leibniz Universitaet Hannover
# GPL2
# Zdravko Bozakov (zb@ikt.uni-hannover.de)

import array
import dpkt
import logging
import socket
import struct
import sys
import time

import hphelper

try:
    import dnet               # OSX: brew install libdnet --with-python
                              # note: dnet.ip_cksum_add has a bug on OSX Mavericks
except ImportError:
    try:
        import dumbnet as dnet        # different name under debian systems
    except ImportError:
        print __name__ + ": please make sure the following packages are installed:"
        print "\tpython-dnet"

try:
    from numpy import random as prnd
    import numpy as np
    import pcap               # python-pypcap
except ImportError:
    print "!! please make sure all the following packages are installed:"
    print "\tpython-pypcap"
    print "\tpython-numpy"
    exit(1)

# pcap versions with different methods for injecting packets exist            
if hasattr(pcap.pcap, 'inject'):
    # ubuntu (python-pcap)
    PCAP_INJECT = True
else:
    # use pcap.sendpacket instead
    PCAP_INJECT = False

try:
  import setproctitle
  setproctitle.setproctitle('h-probe')
except:
  pass # Ignore errors, since this is only cosmetic


options = hphelper.options
from hphelper import DEBUG, INFO, ERROR, set_affinity 


IP_HDR_LEN    = 20
ETHER_HDR_LEN = 14
ICMP_HDR_LEN  = 8

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



def dummyloop(ns):
    # notify receiver that we are ready to send
    ns.SND_READY=True
    # block until receiver says it is ready
    while not ns.RCV_READY:
        time.sleep(0.1)

    DEBUG('READY', __name__)


################################################################################
def sendloop(ns, busy_loop=False):

    geotimes = options.delta*slottimes

    set_affinity('sendloop') 

    time_time  = time.time          # faster: http://wiki.python.org/moin/PythonSpeed/PerformanceTips
    time_sleep = time.sleep

 
    if ns.cnum:
        pnum = ns.cnum
    else:
        pnum = options.pnum
        INFO('expected run time', '~%.2f s (mean inter-probe time %.2e s)' % (geotimes[-1], options.delta/options.rate))
        if geotimes[-1]/60/60>4:
            WARN('WARNING', 'stationarity may not hold!')



    # notify receiver that we are ready to send and block until
    # receiver process says it is ready
    ns.SND_READY=True
    while not ns.RCV_READY:
        time.sleep(0.1)

    DEBUG('READY', __name__)


    payload_rest = '8'*PKT_ARRAY_APPEND
    try:
        t_start = time_time()
        geotimes += t_start
        pkt = ''.join([pkts[0],payload_rest])
        
        if busy_loop==True:
            for i in xrange(1,pnum):
                sendpacket(pkt)
                pkt = ''.join([pkts[i],payload_rest])    # append payload 
                while (time_time() < geotimes[i]):
                    pass
        else:                                       
            for i in xrange(1,pnum):
                sendpacket(pkt)
                pkt = ''.join([pkts[i],payload_rest])            # append payload 
                time_sleep(np.max((geotimes[i]-time_time(),0.0)))  # reduce the load at the expence of accuracy    
        sendpacket(pkt)                                 # send the last prepared packet

    except KeyboardInterrupt:
        pass

    t_total = time_time() - t_start

    print '\a',  
    #s.close()                 # close socket
    DEBUG("sender runtime:\t %.8f s" % (t_total))


##############################################################################
# pre-generate probes on import


def gen_probes_raw():
    """ Pre-generate raw Ethernet packets and store these in the 
    array pkts.
    """
    from dpkt.ethernet import Ethernet
    from dpkt.ip import IP
    from dpkt.icmp import ICMP
    
    eth_info = dnet.intf().get_dst(options.net_info['ip_dst'])
    options.net_info['l2_src'] = eth_info['link_addr'].eth
    gw = dnet.route().get(options.net_info['ip_dst'])
    if gw:
        options.net_info['l2_dst'] = dnet.arp().get(gw).eth
    else:   # destination is in the same subnet
        options.net_info['l2_dst'] = dnet.arp().get(options.net_info['ip_dst']).eth


    try:
        icmp_data = ICMP(type=8, data=ICMP.Echo(seq=0, id=0,data = 'H'*(options.plen-ICMP_HDR_LEN-IP_HDR_LEN)))
        ip_data = IP(src=options.net_info['ip_src'].ip, dst=options.net_info['ip_dst'].ip, p=1, data=icmp_data)
        ip_data.len += len(ip_data.data)

        p0 = Ethernet(src=options.net_info['l2_src'], dst=options.net_info['l2_dst'], data=ip_data)
        str_p = str(p0)

        hdr = str_p[:ETHER_HDR_LEN+IP_HDR_LEN]
        pkt = str_p[ETHER_HDR_LEN+IP_HDR_LEN:]
        psize = options.plen + ETHER_HDR_LEN

        # packet and format 
        p = [ hdr, 
              pkt[:2], 
              struct.pack('<H', (0)),                           # p[2] = ICMP checksum
              pkt[4:16], 
              struct.pack('!L', (0) % 0xFFFFFFFF),              # p[4] = sequence number (4 bytes)
              struct.pack('!L', (0) % 0xFFFFFFFF),              # p[5] = slot number (4 bytes)
              pkt[16+4+4:]]                                     # payload

        ck = checksum(''.join(p[1:])) & 0xFFFF                  # calculate initial ICMP cksum
        p[2] = struct.pack('H', (ck))                           # update ICMP cksum

        M_ = sum(struct.unpack('HHHH',''.join(p[4:6])))
        j = 0
        for i in xrange(options.pnum):
            j=long(slottimes[i])
            p[4] = struct.pack('!L', (i) % 0xFFFFFFFF)          # increment 4 byte seq ID in ICMP payload
            p[5] = struct.pack('!L', (j) % 0xFFFFFFFF)          # increment 4 byte slot ID in ICMP payload
            M = sum(struct.unpack('HHHH', ''.join(p[4:6])))
            ck = ck + M_ - M

            p[2] = struct.pack('H', (ck) % 0xFFFF)               # update ICMP cksum
            pkts[i] = ''.join(p)[:PKT_ARRAY_WIDTH]                  # only store first 100 packet bytes 

            M_=M

    except (MemoryError, ValueError):
        ERROR("Not enough memory!",2)
    except KeyboardInterrupt:
        print 'terminated by user.'
        raise SystemExit(-1)

    print 'done.'
    try:
        po = pcap.pcap(options.net_info['eth'])
        return po
    except Exception as e:
        print e




import code

if __name__=='__main__':
    print 'TESTING SENDER'

    options.pnum = 1000
    options.rate = 0.1
    options.plen = 64
    options.delta = 1e-3
    options.DST = '192.168.1.1'

    eth_info = dnet.intf().get_dst(dnet.addr(options.DST))

    net_info = {}
    net_info['eth'] = eth_info['name']
    net_info['ip_src'] = dnet.addr(eth_info['addr'].ip)
    net_info['ip_dst'] = dnet.addr(options.DST, dnet.ADDR_TYPE_IP)

    options.net_info = net_info

#    class ns: pass
#    ns.cnum = None
#    ns.RCV_READY = True
#    sendloop(ns, busy_loop=False)



PKT_ARRAY_WIDTH   = 100                  # number of packet bytes to store in pkts array
PKT_ARRAY_APPEND  = max((options.plen + ETHER_HDR_LEN) - PKT_ARRAY_WIDTH,0) # need to append this number of bytes to the payload while sending



def sendpacket(pkt_str):
    # pcap versions with different methods for injecting packets exist
    if PCAP_INJECT==True:
        s.inject(pkt_str, len(pkt_str))
    elif PCAP_INJECT==False:
        s.sendpacket(pkt_str)


if not options.loaddump:
    print 'pre-generating %i ICMP probes...' % (options.pnum), 
    sys.stdout.flush()

    # store send times as an slot index
    slottimes = np.cumsum(np.random.geometric(options.rate, size=options.pnum)).astype(int)

    # pre-generate all ICMP packets in an numpy array so we do not
    # have to waste time at runtime
    pkts = np.empty(options.pnum, dtype=np.dtype((str, PKT_ARRAY_WIDTH)))

    probe_socket = gen_probes_raw()
    s = probe_socket

