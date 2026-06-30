# Resilience Lab

## Objetivo

Avaliar a resiliência de uma aplicação distribuída utilizando Kubernetes e Chaos Mesh.

## Arquitetura

* Frontend/API Gateway
* Order Service
* PostgreSQL

## Tecnologias

* Python
* FastAPI
* PostgreSQL
* Docker
* Kubernetes
* Chaos Mesh
* Prometheus
* Grafana

## Serviços

### Order Service

Endpoints disponíveis:

* GET /health
* GET /orders
* GET /orders/{id}
* POST /orders

## Banco de Dados

O serviço de pedidos utiliza PostgreSQL para persistência de dados.

Tabela principal:

* orders

Campos:

* id
* description
