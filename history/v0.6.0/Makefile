.PHONY: test run docker-build

test:
	PYTHONPATH=. python3 -m unittest discover -s tests -v

run:
	./run_local.sh

docker-build:
	docker build -t impacto-local:0.3 .
