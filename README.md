H-probe (Ver. 1.1)
==================


Overview
--------

H-probe is an online active probing tool for estimating traffic correlations from end-to-end measurements. H-probe does not rely on a receiver as it uses ICMP echo packets. It uses libpcap to capture returning ICMP echo replies. From the timing information H-probe is able to estimate the correlation (covariance) of the cross traffic sharing the end-to-end path with the probing traffic. For Internet aggregate traffic it is known [Leland et al. '94] that it is long range dependent (LRD) with Hurst parameter H. The Hurst parameter can be estimated from the covariance slope that is given by 2H-2. H-probe also implements the aggregate variance method known from [Taqqu et al. '95], which is more robust than the covariance, for estimating H. 

H-probe uses sampling methodology that is described in
"[Estimating traffic correlations from sampling and active network probing](http://ieeexplore.ieee.org/xpl/abstractReferences.jsp?tp=&arnumber=6663503)", by A. Rizk, Z. Bozakov and M. Fidler. IFIP Networking Conference 2013, pp.1,9, 22-24 May 2013

A technical report "H-Probe: Estimating Traffic Correlations from Sampling and Active Network Probing" is available at [arXiv](http://arxiv.org/abs/1208.2870).

H-Probe injects ICMP echo request probes from the sender to the target and captures the corresponding round trip times (RTT) using libpcap. Using the RTTs H-probe estimates the traffic correlations on the end-to-end path. Details of the algorithm are given the paper mentioned above.



Requirements
------------

1. Linux operating system 
2. root privileges to use libpcap for packet capture
3. python version 2.6 or 2.7 including the following required python packages: pypcap, numpy, libdnet, dpkt. Additionally the following optional python packages will be used if installed: affinity (pypi), progressbar. To use the live plotting functionality gnuplot is must also be installed. 

In Debian based distributions you should be able to install all necessary packages using:

    sudo apt-get install python-pypcap python-dumbnet python-numpy 
    sudo apt-get install python-dev python-setuptools python-progressbar 
    sudo apt-get install gnuplot 
    
    sudo easy_install affinity

The software has been extensively tested under Linux (specifically Ubuntu 12.04 using python 2.6.5). The software has not been tested on Windows and OS X - feedback is appreciated.
    

Installation
------------

You can obtain the latest version of the software from GitHub using:

    git clone https://github.com/bozakov/H-probe.git
    
You can also download and uncompress a zip archive with the most recent source files: 
    
    wget https://github.com/bozakov/H-probe/zipball/master
    gunzip bozakov-H-probe*.zip

After changing to the extracted directory you can immediately start using H-probe: 

    sudo ./h-probe www.nasa.gov

This will start an online estimation run which will display and periodically update a plot of the aggregate variance of the network path from your host to www.nasa.gov. Alternately, you can run a headless session and save all measurement results into a "dumpfile" which  can be loaded and parsed at any time using the `--dump` option.

    sudo ./h-probe www.nasa.gov --dump 

The command line options are given below
    
    ./h-probe [options] host [savefile]

    Options:
      --version             show program's version number and exit
      -h, --help            show this help message and exit
      -n PNUM, --probe-num=PNUM
                            total number of probes (default: 100000)
      -d DELTA, --delta=DELTA
                            min. time in seconds between probes (default: 1e-3)
      -r RATE, --rate=RATE  mean probing intensity between 0 and 1 (default: 0.1)
      -s PLEN, --psize=PLEN
                            total probe packet size in bytes (default: 64)
      -L L, --lag=L         maximum lag in seconds (default: 10.0 s)
      -M M, --agg-level=M   min/max aggregation range in seconds for aggregate
                            variance method (default: [0.1, 100.0] s)
      --in-slots            maximum lag and the aggregation levels are given in
                            slots rather than absolute time
      -t MIN_RTT, --min-rtt=MIN_RTT
                            specify the minimum RTT used to detect a busy beriod
      --no-plot             disable visualization (default: False)
      --fps=FPS             frames per second for plotting (default: 1.0)
      --aggvar              estimate aggregate variance (default)
      --xcov                estimate path covariance
      --hist                generate a histogram of the RTTs
      --dump                dump the captured RTTs to a file for post-processing
      --load=LOADDUMP       load a dump of captured RTTs
      --tag=TAG             optional tag appended to save filename (default: )
      --verbose             print additional info


In order to ensure accurate timestamping and send times, H-probe launches multiple python processes which run on separate CPUs/cores (the modules are main, rcvloop, sendloop and the parser). The CPU affinity of each process may be manually specified in the special file affinity.map in the h-probe directory.



Output
------

1.  Covariance method (`--xcov` option): calculates and plots the covariance versus the time lag in seconds on a log-log scale. For LRD traffic the covariance decays as \tau^{2H-2}. This results into a slope on a log-log scale as 2H-2.

2.  Aggregate variance method (`--aggvar` option): generates a plot depicting the aggregate variance versus the aggregation level M. On a log-log scale the aggregate variance decays with M as a straight line with a slope of 2H-2. This is the default estimation method.

3.  After a predefined number of probes has been collected (`-n` option) the measurement terminates and the current plot (either covariance or aggregate variance) is saved under the following name:

        [savefile]_<tag>_[method].eps

    
    or, if no savefile was specified:
    
        [host]_[date]_[time]_<tag>_[method].eps
        
 * [host] is the target host name
 * [date] is the current date (YYYYMMDD)
 * [time] is the measurement completion time (HHMM)
 * <tag>  is an optional user defined tag (`--tag` option)
 * [method] is the estimation method: av for aggregate variance, xc for covariance plot

  
    Additionally the estimate raw data is saved as a .dat file which can be imported and analyzed in other tools. The file name format is identical to the EPS file but has a .dat extension. The file contains a new line for each received probe with the format `YY [XX]` where:
    
    * YY    is the y-coordinate value (i.e. aggregated variance, or covariance)
    * [XX]  is the (optional) x-coordinate value (i.e. aggregation level or lag)
    

4.  H-probe can save the measurement results into a dump file for subsequent analysis using the '--dump' option. The default dump file is saved as:

         [savefile]_<tag>_[method].dump
    
    or, if no savefile was specified:
    
         [host]_[date]_[tag]_[time].dump
    
    The dumpfile contains a single line for each measured RTT using a
    three column, white space delimited format `AA BB CCCCC`

   * AA     is the integer probe sequence number
   * BB     is the integer slot number of the probe (each slot is Delta wide)
   * CCCCC  is the measured RTT in seconds


Contact
-------

<zb@ikt.uni-hannover.de>

<amr.rizk@ikt.uni-hannover.de>

You can find the project page [here](http://www.ikt.uni-hannover.de/h-probe).

License
-------

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; see the file COPYING.  If not, write to
the Free Software Foundation, Inc., 59 Temple Place - Suite 330,
Boston, MA 02111-1307, USA.













