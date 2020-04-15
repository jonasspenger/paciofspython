#!/bin/bash
################################################################################
# info
################################################################################
# uses: iozone http://www.iozone.org/, install: brew install iozone (macOS)

################################################################################
# setup environment
################################################################################
trap "kill 0" EXIT
cd `dirname $0`
set -e  # exit when any command fails

################################################################################
# run test
################################################################################
# reset test directory
rm -rf .testiozone
mkdir .testiozone
cd .testiozone

echo paciofslocal
mkdir vol1
mkdir mnt1
timeout 1m python3 ../../../paciofs/paciofslocal.py --mountpoint mnt1 --volume vol1 --logginglevel ERROR &
sleep 15
pushd mnt1
iozone -a | tee ../test.paciofslocal.log
popd
umount mnt1

echo passthroughfs
mkdir vol2
mkdir mnt2
timeout 1m python3 ../../../paciofs/passthrough.py vol2 mnt2 &
sleep 15
pushd mnt2
iozone -a | tee ../test.passthrough.log
popd
umount mnt2

echo localfs
mkdir vol3
pushd vol3
iozone -a | tee ../test.localfs.log
popd

exit
