# Experimentos de Caos (Chaos Mesh)

Roteiro de execução e teste dos 3 experimentos obrigatórios (requisito 2.2 da
especificação). Cada seção segue a matriz do relatório: **Estado Estável →
Hipótese → Configuração do Ataque → Resultado Observado → Ações Corretivas**.

A demonstração é feita em duas camadas complementares:

- **Visual** (prioritária): dashboard do Grafana reagindo ao vivo + interface web
  do frontend. É o material para o vídeo/defesa (item 3.3) e para os prints do
  relatório.
- **Terminal** (verificação): comandos `kubectl` que comprovam numericamente o
  mesmo efeito, úteis quando o gráfico é sutil.

Todos os experimentos têm como alvo os pods do `order-service`
(`labelSelectors: app: order-service`, namespace `default`).

## Manifestos

| Arquivo | Tipo | Categoria (spec 2.2) | Efeito |
|---|---|---|---|
| `network-chaos.yaml` | NetworkChaos | Falha de Rede | Latência de 1000ms por 60s |
| `pod-chaos.yaml` | PodChaos | Falha de Instância | `pod-kill` de uma réplica |
| `stress-chaos.yaml` | StressChaos | Falha de Recurso | CPU 2 workers a 100% por 120s |

---

## Pré-requisitos do ambiente

Cluster com runtime **containerd** (o driver docker com Docker 29+ é incompatível
com o chaos-daemon) e recursos suficientes:

```bash
minikube start --driver=docker --container-runtime=containerd --cpus=4 --memory=6g
minikube addons enable metrics-server
```

Módulos de kernel para o NetworkChaos (o driver docker compartilha o kernel do
host):

```bash
sudo modprobe sch_netem ip_set ip_set_hash_net ip_set_hash_ip xt_set
```

Chaos Mesh (1 réplica do controller já basta para o laboratório):

```bash
helm install chaos-mesh chaos-mesh/chaos-mesh -n chaos-mesh --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock \
  --set controllerManager.replicaCount=1 \
  --version 2.6.3
```

Observabilidade (Prometheus + Grafana) — manifestos em `../k8s/`:

```bash
kubectl apply -f ../k8s/prometheus.yaml
kubectl apply -f ../k8s/grafana.yaml
```

Verificação geral:

```bash
kubectl get pods                                   # app, prometheus, grafana Running
kubectl get pods -n chaos-mesh                     # chaos-mesh Running
kubectl get crd | grep chaos-mesh.org             # networkchaos/podchaos/stresschaos
```

---

## Acesso às telas (deixe abertos durante os testes)

**Grafana — dashboard "Resilience Lab" (tela principal):**

```bash
kubectl port-forward svc/grafana 3000:3000
# http://localhost:3000  (admin/admin) -> dashboard "Resilience Lab"
```

Painéis disponíveis:

| Painel | Prova qual experimento |
|---|---|
| Latência p95 | NetworkChaos |
| Taxa de requisições (req/s) | atividade/carga |
| Taxa de erros 5xx | PodChaos |
| CPU por pod | StressChaos |
| Réplicas ativas | PodChaos e StressChaos (HPA) |

**Frontend — interface web:**

```bash
minikube service frontend --url          # abra a URL no navegador (F12 -> Network)
```

**Gerador de carga** (para os painéis terem tráfego e o ataque ocorrer "durante
requisição ativa"). Rode em um terminal e deixe rodando:

```bash
kubectl port-forward svc/order-service 8001:8001    # terminal dedicado
# em outro terminal:
while true; do curl -s -o /dev/null http://localhost:8001/orders; sleep 0.2; done
```

---

## 1. NetworkChaos — Falha de Rede

- **Estado Estável:** latência p95 no painel do Grafana em ~10ms; requisição
  pod-a-pod em ~0.01s.
- **Hipótese:** a latência de 1000ms deixa o serviço lento, mas o timeout de 3s e
  o retry do frontend mantêm as respostas (HTTP 200); não há queda.
- **Configuração do Ataque:** `delay latency=1000ms jitter=100ms`, `duration=60s`.

**Demonstração visual:**

1. No Grafana, deixe o painel **Latência p95** à vista.
2. Injete o ataque (sempre delete-e-aplique para forçar injeção nova):
   ```bash
   kubectl delete -f network-chaos.yaml --ignore-not-found
   kubectl apply  -f network-chaos.yaml
   ```
3. Observe o painel **Latência p95** disparar de ~10ms para segundos.
4. No navegador, recarregue a página (F5): com F12 → Network, o tempo de carga
   sobe visivelmente. (Para o efeito dramático de "serviço indisponível" na tela,
   use `latency: "5000ms"`, acima do timeout de 3s → aparece o texto vermelho.)

**Verificação por terminal:**

```bash
kubectl describe networkchaos network-delay-order-service | grep -A6 "Status:"   # AllInjected: True
kubectl exec deploy/frontend -- python -c "import time,requests; t=time.time(); requests.get('http://order-service:8001/orders'); print(round(time.time()-t,3),'s')"
```

- **Resultado Observado:** latência p95 salta para alguns segundos, mantendo HTTP
  200. Print do painel antes/durante.
- **Ações Corretivas:** timeout de 3s + retry (tenacity) + circuit breaker
  (pybreaker) no `frontend/client.py`.

```bash
kubectl delete -f network-chaos.yaml
```

---

## 2. PodChaos — Falha de Instância

- **Estado Estável:** painel **Réplicas ativas** = 2; **Taxa de erros 5xx** = 0.
- **Hipótese:** ao matar 1 réplica, o Service redireciona para a réplica viva e o
  Deployment recria o pod; disponibilidade mantida (impacto quase invisível).
- **Configuração do Ataque:** `action=pod-kill`, `mode=one`, `gracePeriod=0`.

**Demonstração visual:**

1. No Grafana, deixe à vista os painéis **Réplicas ativas** e **Taxa de erros 5xx**.
2. Injete o ataque (sempre delete-e-aplique para forçar injeção nova):
   ```bash
   kubectl delete -f pod-chaos.yaml --ignore-not-found
   kubectl apply  -f pod-chaos.yaml
   ```
3. Observe **Réplicas ativas** cair para 1 e voltar a 2 em segundos (o pod é
   recriado). A **Taxa de requisições** segue fluindo — o serviço não parou.
4. No navegador: recarregue a página — ela continua respondendo normalmente
   (prova da redundância). Para mostrar impacto visível na tela, edite
   `pod-chaos.yaml` com `mode: all` (mata as 2 réplicas) → aparece o texto
   vermelho de indisponibilidade até o Kubernetes recriar os pods.

**Verificação por terminal:**

```bash
kubectl get pods -l app=order-service -w    # pod Terminating -> novo Running
```

- **Resultado Observado:** um pod morre e outro nasce em poucos segundos;
  disponibilidade mantida com `mode: one`. Print do painel **Réplicas ativas**.
- **Ações Corretivas:** `replicas: 2` no Deployment + recriação automática do
  Kubernetes.

```bash
kubectl delete -f pod-chaos.yaml
```

---

## 3. StressChaos — Falha de Recurso

- **Estado Estável:** painel **CPU por pod** ~1-2m; **Réplicas ativas** = 2.
- **Hipótese:** ao saturar a CPU, o HorizontalPodAutoscaler escala de 2 até 5
  réplicas.
- **Configuração do Ataque:** `stressors.cpu: workers=2 load=100`, `duration=120s`.

**Demonstração visual:**

1. No Grafana, deixe à vista os painéis **CPU por pod** e **Réplicas ativas**.
2. Injete o ataque (sempre delete-e-aplique para forçar injeção nova):
   ```bash
   kubectl delete -f stress-chaos.yaml --ignore-not-found
   kubectl apply  -f stress-chaos.yaml
   ```
3. Observe **CPU por pod** subir ao limite (~500m) e, em ~1-2 min, **Réplicas
   ativas** subir de 2 → 5 (o HPA escalando). Novas linhas de CPU aparecem no
   painel conforme os pods nascem.
4. Após o ataque (120s), a CPU cai e o HPA reduz de volta para 2 (cooldown).

**Verificação por terminal:**

```bash
kubectl describe stresschaos stress-cpu-order-service | grep -A6 "Status:"   # AllInjected: True
kubectl top pods -l app=order-service      # CPU ~500m
kubectl get hpa -w                          # REPLICAS 2 -> 5
```

- **Resultado Observado:** CPU sobe de ~1m para ~500m; HPA passa de 2% para ~500%
  e escala 2 → 5 réplicas. Print dos painéis **CPU por pod** e **Réplicas ativas**.
- **Ações Corretivas:** `HorizontalPodAutoscaler` (2–5 réplicas, alvo 60% CPU) +
  `resources.requests/limits` no Deployment. Requer `metrics-server` ativo.

```bash
kubectl delete -f stress-chaos.yaml
```

---

## Limpeza geral

```bash
kubectl delete networkchaos,podchaos,stresschaos --all --ignore-not-found
kubectl get pods -l app=order-service     # estabiliza em 2 réplicas
```

Se a remoção travar em um finalizer:

```bash
kubectl patch <kind> <nome> --type=merge -p '{"metadata":{"finalizers":[]}}'
```

## Dicas de demonstração

- O `duration` curto dos manifestos (60s/120s) expira no meio da demo; para gravar
  com folga, aumente para `300s` temporariamente.
- Layout de vídeo sugerido: metade da tela com o Grafana (dashboard "Resilience
  Lab"), metade com o navegador do frontend; injete o caso e as duas telas reagem
  ao mesmo tempo.
- Meça a latência do NetworkChaos por dentro do cluster (`kubectl exec`), nunca via
  `port-forward` do host — o port-forward mascara o atraso.
