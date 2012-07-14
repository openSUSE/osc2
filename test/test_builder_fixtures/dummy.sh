#!/bin/bash
test "$1" = "--fail" && exit 1
test "$1" = "--out" && echo "$2"
test "$1" = "foo.spec" && echo "$1"
exit 0
