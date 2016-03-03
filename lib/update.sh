#!/bin/bash

src=../../sst92/sst-data
dst=sst-data

mkdir -p $dst
for f in $src/*.p $src/*License*; do
    cp -av $f $dst
done
