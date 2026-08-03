.PHONY: build run test

build:
	python3 fishgen.py rando.c

run:
	python3 fishgen.py rando.c
	python3 fish.py rando.z

test:
	python3 test.py