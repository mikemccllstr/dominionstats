#!/bin/bash

if [ $# -ne 1 ]
then
    echo Usage: multi_scrape.sh [goko logdir]
    echo Example: multi_scrape.sh 20130513
    exit -1
fi

BASE_ARCHIVE=http://archive-dominionlogs.goko.com/$1/
BASE_RECENT=http://dominionlogs.goko.com/$1/

wget --spider $BASE_RECENT && BASE=$BASE_RECENT
wget --spider $BASE_ARCHIVE && BASE=$BASE_ARCHIVE
THREADS=20

wget --header='Accept-Encoding: gzip' $BASE -O- | zcat | perl -lne 'print "$1" if /href="(.*?txt)"/' > _all

if [ `cat _all | wc -l` -gt 0 ]
then
    cat _all | split -l 100 - _index.
    ls _index.* | xargs -n 1 -P $THREADS wget --base=$BASE --header='Accept-Encoding: gzip' --quiet -i
    rm _index.*
    echo "Done downloading"
fi

ls > _old
ls _* >> _old
cat _all _old | sort | uniq -u > _new

if [ `cat _new | wc -l` -gt 0 ]
then
    cat _new | split -l 100 - _index.
    ls _index.* | xargs -n 1 -P $THREADS wget --base=$BASE --header='Accept-Encoding: gzip' --quiet -i
    rm _index.*
    echo "Done doublechecking"
fi

for x in `cat _all`
do
    mv $x $x.gz
    gunzip $x.gz
done

tar cjf $1.all.tar.bz2 -T _all


for x in `cat _all` 
do
    rm $x
done

rm _all
rm _old
rm _new

