.PHONY: dev setup

ifneq (,$(wildcard .env))
  include .env
  export
endif

setup:
	docker compose up -d

dev:
	poetry run python -m kuma_ingress_watcher.controller
