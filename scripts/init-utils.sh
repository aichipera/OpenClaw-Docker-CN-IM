#!/bin/bash
# Shared utility functions for OpenClaw init scripts

log_section() {
    echo "=== $1 ==="
}

is_root() {
    [ "$(id -u)" -eq 0 ]
}
