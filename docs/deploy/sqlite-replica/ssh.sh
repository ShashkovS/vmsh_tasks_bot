#!/bin/sh
exec /usr/bin/ssh -F /etc/vmsh-sqlite-replica/ssh_config "$@"
