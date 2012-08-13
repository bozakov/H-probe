H-probe (Ver. 1.0)
====================

Outline
========



Overview
=========

H-probe is an online active probing tool for estimating traffic correlations from end-to-end measurements. H-probe does not rely on a receiver as it uses ICMP echo packets. It uses libpcap to capture returning ICMP echo replies. From the timing information H-probe is able to estimate the correlation (covariance) of the cross traffic sharing the end-to-end path with the probing traffic. For Internet aggregate traffic it is known [Leland et al. '94] that it is long range dependent (LRD) with Hurst parameter H. The Hurst parameter can be estimated from the covariance slope that is given by 2H-2. H-probe also implements the aggregate variance method known from [Taqqu et al. '95], which is more robust than the covariance, for estimating H. 

H-probe uses sampling methodology that is described in
"H-Probe: Estimating Traffic Correlations from Sampling and Active Network Probing", by A. Rizk, Z. Bozakov and M. Fidler. The paper is available at: XXX


H-Probe injects ICMP echo request probes from the sender to the target and captures the corresponding round trip times (RTT) using libpcap. Using the RTTs H-probe estimates the traffic correlations on the end-to-end path. Details of the algorithm are given the paper mentioned above.



Requirements
============

1) UNIX based operating system 
2) root privileges to use libpcap to capture incoming packets
3) python version 2.6 or 2.7 including the following required python packages: pypcap, numpy, scapy. Additionally the following optional python packages can be installed: affinity (pypi), progressbar. To use the plotting functionality gnuplot is required. 

In Debian based distributions you should be able to install all necessary packages using:

	sudo apt-get install python-pypcap python-numpy python-scapy
	sudo apt-get install python-dev python-setuptools gnuplot python-progressbar 
	sudo apt-get install gnuplot 
	
	sudo easy_install affinity

The software has been extensively tested under Linux (specifically Ubuntu 12.04 using python 2.6.5). The software has not been tested on Windows and OS X - feedback is appreciated.
	

Installation
============

After downloading the software you can extract it using
$> gunzip example.zip

After the software is extracted you can run it immediately using
$> ./h-probe host

You can run the software using
$> ./h-probe [options] host [savefile]

H-probe can save measurement results into "dumpfiles" that can be loaded and parsed at any time using the '--dump' option.


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
                        variance method (default: [0.10000000000000001, 100.0]
                        s)
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


Output
======

1) Covariance plot: The plot depicts the covariance versus the time lag in seconds on a log-log scale. For LRD traffic the covariance decays as \tau^{2H-2}. This results into a slope on a log-log scale as 2H-2.

2) Aggregate variance plot [default]: The plot depicts the aggregate variance versus the aggregation level M. On a log-log scale the aggregate variance decays with M as a straight line with a slope of 2H-2.

3) The plot (either covariance or aggregate variance plot) is saved under the following name:

	[host]_[date]_[time]_[tag]_[method].eps

[host]    is the target host name
[date]    is the current date
[time]    is the measurement completion time
[tag]     is an optional user defined tag (--tag option)
[method]  is the estimation method: av for aggregate variance, xc for covariance plot

Additionally the plot is saved as a .dat file which can be imported and analyzed in other tools. The plot file is named:

	[host]_[date]_[time]_[tag]_[method].dat

The plot file contains a new line for each received prode with the following format:

YY [XX]

YY	is the y-coordinate value (i.e. aggregated variance, or covariance)
[XX]	is the (optional) x-coordinate value (i.e. aggregation level or lag)


4) Dump file: H-probe can save the measurement results into a dump file for subsequent analysis. The default dump file is named as:
 	[host]_[date]_[tag]_[time].dump

The dumpfile contains the measured RTTs in the following format:

AA BB CCCCC

AA 	is the probe sequence number
BB 	is the slot number of the probe (each slot is Delta wide)
CCCCC	is the measured RTT


Contact
========

zb@ikt.uni-hannover.de



License
========

This software is licensed under the GPL2.














