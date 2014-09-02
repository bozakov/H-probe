FDIR='../examples/';
files=dir([ FDIR '*.dump']);

% lags
L=1000

hs=[];
xcs=[];
ds={};

for n = 1:length(files)
    clear t
    x=1:L;
    col = [.7, mod(n,8)/8, .3];

    files(n).name
    ds{n} = load([FDIR files(n).name]);
    d = ds{n};
    fprintf('out of order probes: %d\n', sum(diff(d(:,2))<0))

    d3=d(:,3);
    d3=d3-mean(d3); c='g.';
    d3=d3>0; 

    % sample process
    a=full(sparse(d(:,2)+1,ones,ones));

    % observation process
    t=full(sparse(d(:,2)+1,ones,d3));
    # limit the size of the trace so that MATLAB does not run out of memory
    TEND=min(10e6,length(t));

    t(a~=0) = t(a~=0) - mean(t(a~=0));
    clear a;

    xc=xcov(t(1:end),L,'unbiased'); xc=xc(L+2:end);

    %%% PLOT %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    % omit negative values
    IDX=xc>0;
    X = x(IDX);  Y = xc(IDX);

    figure(19999); hold on; grid on;
    plot(log10(X),log10(Y),c,'color',col)

    P = polyfit(log10(X),log10(Y)',1); h = (2+P(1))/2
    hs(end+1) = h;

end


figure(3)
plot(hs,'r')
