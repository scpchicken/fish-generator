.PHONY: test run build

test:
	python3 test.py

build:
	python3 fishgen.py rando.c

run:
	python3 fishgen.py rando.c
	python3 fish.py rando.z