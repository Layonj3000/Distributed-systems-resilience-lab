# 🧪 Resilience Lab

Aplicação distribuída para estudo de resiliência com Kubernetes e Chaos Mesh.

## 🏗️ Arquitetura

```
Frontend (porta 30080) → Order Service (porta 8001) → PostgreSQL (porta 5432)
```

| Componente    | Tecnologia       | Réplicas |
|---------------|------------------|----------|
| Frontend      | FastAPI + Jinja2 | 2        |
| Order Service | FastAPI          | 2 (HPA)  |
| PostgreSQL    | PostgreSQL 17    | 1        |
| Prometheus    | prom/prometheus  | 1        |
| Grafana       | grafana/grafana  | 1        |

## 📋 Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/)
- [Minikube](https://minikube.sigs.k8s.io/docs/start/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Helm](https://helm.sh/docs/intro/install/)

## 🐳 Execução local (Docker Compose)

Útil para desenvolvimento rápido, sem Kubernetes.

```bash
docker compose up --build
```

Acesse em: http://localhost:8000

## ☸️ Execução no Kubernetes (Minikube)

### 1. Iniciar o Minikube

O runtime `containerd` é **obrigatório** — o driver docker com Docker 29+ é
incompatível com o chaos-daemon do Chaos Mesh.

```bash
minikube start --driver=docker --container-runtime=containerd --cpus=4 --memory=6g
minikube addons enable metrics-server
```

### 2. Build das imagens

Com o runtime `containerd`, use `minikube image build` (o `minikube docker-env` **não**
funciona nesse runtime):

```bash
minikube image build -t distributed-systems-resilience-lab-frontend:latest ./frontend
minikube image build -t distributed-systems-resilience-lab-order-service:latest ./order-service
```

### 3. Deploy da aplicação

```bash
kubectl apply -f k8s/postgres.yaml
kubectl apply -f k8s/order-service.yaml
kubectl apply -f k8s/order-service-hpa.yaml
kubectl apply -f k8s/frontend.yaml
```

### 4. Deploy da observabilidade

```bash
kubectl apply -f k8s/prometheus.yaml
kubectl apply -f k8s/grafana.yaml
```

### 5. Verificar os pods

```bash
kubectl get pods
```

⚠️ Aguarde todos os pods estarem com status `Running`. Os pods do `order-service`
levam ~25s a mais para iniciar por causa do `initContainer` de warm-up (usado para
tornar a queda de réplicas do PodChaos visível no Grafana).

### 6. Acessar os serviços

```bash
# Frontend
minikube service frontend

# Grafana (usuário: admin / senha: admin)
minikube service grafana
```

## 🔄 Atualizar após mudanças no código

```bash
minikube image build -t distributed-systems-resilience-lab-frontend:latest ./frontend
minikube image build -t distributed-systems-resilience-lab-order-service:latest ./order-service

kubectl rollout restart deployment/frontend
kubectl rollout restart deployment/order-service
```

## ⚙️ Instalar o Chaos Mesh

```bash
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update

helm install chaos-mesh chaos-mesh/chaos-mesh \
  --namespace chaos-mesh \
  --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock \
  --set controllerManager.replicaCount=1 \
  --version 2.6.3
```

Verificar instalação:

```bash
kubectl get pods -n chaos-mesh
```

## 🧪 Experimentos de Caos

> **Antes do NetworkChaos** — carregue os módulos de kernel do netem no host (o driver
> docker compartilha o kernel; `modprobe` não sobrevive a reboot, refaça a cada sessão):
>
> ```bash
> sudo modprobe sch_netem ip_set ip_set_hash_net ip_set_hash_ip xt_set
> ```
>
> Roteiro detalhado de cada experimento (matriz do relatório) em [`chaos/README.md`](chaos/README.md).

### 1. Falha de Rede — latência de 2000ms no Order Service

```bash
kubectl apply -f chaos/network-chaos.yaml
```

### 2. Falha de Instância — kill de uma réplica do Order Service (`mode: one`)

```bash
kubectl apply -f chaos/pod-chaos.yaml
```

### 3. Falha de Recurso — sobrecarga de CPU no Order Service

```bash
kubectl apply -f chaos/stress-chaos.yaml
```

### Remover experimentos

```bash
kubectl delete -f chaos/network-chaos.yaml
kubectl delete -f chaos/pod-chaos.yaml
kubectl delete -f chaos/stress-chaos.yaml
```

## 🛡️ Mecanismos de Tolerância a Falhas

| Mecanismo      | Onde             | Configuração                          |
|----------------|------------------|---------------------------------------|
| Circuit Breaker | Frontend        | 5 falhas → abre por 30s               |
| Retry          | Frontend         | 3 tentativas com intervalo de 1s      |
| Idempotência   | Frontend + Order Service | chave única por pedido; o retry de escrita não duplica |
| Timeout        | Frontend         | 3s por requisição                     |
| Réplicas       | Frontend / Order Service | 2 réplicas cada               |
| HPA            | Order Service    | 2–5 réplicas, escala em 60% de CPU    |

## 🔬 Observabilidade

| Serviço    | URL local                  | Credenciais     |
|------------|----------------------------|-----------------|
| Prometheus | `minikube service prometheus` | —            |
| Grafana    | `minikube service grafana`    | admin / admin |

O dashboard **Resilience Lab** é provisionado automaticamente no Grafana com os painéis:

- Latência p95 do Order Service
- Taxa de requisições (req/s)
- CPU por pod
- Réplicas ativas

## 📁 Estrutura do Projeto

```
.
├── chaos/                  # Manifestos do Chaos Mesh
│   ├── network-chaos.yaml
│   ├── pod-chaos.yaml
│   └── stress-chaos.yaml
├── frontend/               # Serviço de frontend
│   ├── templates/
│   ├── app.py
│   ├── client.py
│   ├── config.py
│   └── Dockerfile
├── order-service/          # Serviço de pedidos
│   ├── app.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   └── Dockerfile
├── k8s/                    # Manifestos do Kubernetes
│   ├── frontend.yaml
│   ├── order-service.yaml
│   ├── order-service-hpa.yaml
│   ├── postgres.yaml
│   ├── prometheus.yaml
│   └── grafana.yaml
└── docker-compose.yml      # Execução local
```
## 👨‍💻 Autores 
<div>
  <table style="margin: 0 auto;">
    <tr>
      <td><a href="https://github.com/DavidPotentini"><img loading="lazy" src="https://avatars.githubusercontent.com/u/106561154?v=4" width="115"><br><sub>David Potentini</sub></a></td>
      <td><a href="https://github.com/Layonj300"><img loading="lazy" src="https://avatars.githubusercontent.com/u/106559843?v=4" width="115"><br><sub>Layon Reis</sub></a></td>
    </tr>
  </table>
</div>