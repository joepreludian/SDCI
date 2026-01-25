.PHONY: clean setup build_publish_pypi

clean:
	rm -Rf dist/*

setup:
	pip install pipx
	pipx install uv

build: clean
	uv build

publish: build
	uv publish

docker-build: build
	docker compose build sdci-base

docker-testing: docker-build
	docker compose run --rm sdci-client
	docker compose down
