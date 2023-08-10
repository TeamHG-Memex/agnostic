

require-docker-account:
	@test -z "${DOCKER_ACCOUNT}" && \
		echo "[ERROR] Must export DOCKER_ACCOUNT" && \
		exit 1 || \
		echo "[INFO] DOCKER_ACCOUNT is '${DOCKER_ACCOUNT}'"

build-container: require-docker-account
	docker build -t agnostic-tests tests/docker
	docker tag agnostic-tests ${DOCKER_ACCOUNT}/agnostic-tests:latest

push-container: require-docker-account
	docker push ${DOCKER_ACCOUNT}/agnostic-tests:latest

stop-container:
	docker stop agnostic-tests || true
	docker rm agnostic-tests || true

start-container: require-docker-account stop-container
	docker run -d -v ${PWD}:/opt/agnostic --name agnostic-tests \
		${DOCKER_ACCOUNT}/agnostic-tests:latest

container-shell:
	docker exec -it -w /opt/agnostic agnostic-tests bash

integration-test: require-docker-account start-container
	@echo "Sleeping 10 seconds so databases can start up"
	@sleep 10
	docker exec -it -w /opt/agnostic agnostic-tests pytest --cov=agnostic tests/
	$(MAKE) stop-container
