#!/bin/bash
test "$1" = "--fail" && exit 1
test "$1" = "--out" && echo "$2"
exit 0
