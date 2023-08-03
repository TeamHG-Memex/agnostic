

build-container:
	docker build -t agnostic-tests tests/docker

require-docker-account:
	@test -z "${DOCKER_ACCOUNT}" && echo "[ERROR] Must export DOCKER_ACCOUNT" && exit 1 || echo "[INFO] DOCKER_ACCOUNT is '${DOCKER_ACCOUNT}'"

push-container: require-docker-account
	docker tag agnostic-tests ${DOCKER_ACCOUNT}/agnostic-tests:latest
	docker push ${DOCKER_ACCOUNT}/agnostic-tests:latest

integration-test: build-container
