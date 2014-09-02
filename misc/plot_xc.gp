# plot auto covariance
# set the .dat file in you shell, e.g.: 
# export HP_DAT=/users/bozakov/www.nasa.gov_20120814_0909__from_dump_xc.dat

FILE=system("echo $HP_DAT") 

set datafile commentschars "#%"
set log xy
set datafile missing 'nan'
set grid
unset key
set format y "%.0e"
plot FILE


