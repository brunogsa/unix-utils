#!/bin/bash
# Picks a greeting.

pick() {
  case "$1" in
    a) echo "first" ;;
    b) echo "second" ;;
    *) echo "other" ;;
  esac
}

pick "$1"
