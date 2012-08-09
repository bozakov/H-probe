# plot auto covariance
set datafile commentschars "#%"
set log xy
set datafile missing 'nan'
set grid
unset key
set format y "%.0e"

plot 'examples/trace.dat'


