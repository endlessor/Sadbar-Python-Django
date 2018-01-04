#! /bin/sh

NOW=`date +"%Y%m%d%H%M"`
pg_dump  -Fc "postgresql://{{ database.user }}:{{ database.password }}@127.0.0.1/{{ database.name }}" -f {{ project.root }}/backup/sandbar_$NOW.pg
