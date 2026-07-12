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
| `network-chaos.yaml` | NetworkChaos | Falha de Rede | Latência de 2000ms por 60s (round-trip compõe além do timeout de 3s) |
| `pod-chaos.yaml` | PodChaos | Falha de Instância | `pod-kill` de uma réplica (`mode: one`) |
| `stress-chaos.yaml` | StressChaos | Falha de Recurso | CPU 2 workers a 100% por 120s |

---

## A. Dependências — instalar uma vez na máquina

Softwares que precisam existir no host **antes de qualquer coisa**. Instala uma
vez; sobrevivem a reboots e a recriações do cluster.

| Dependência | Para que serve | Verificar |
|---|---|---|
| **Docker** | Driver do minikube | `docker version` |
| **minikube** | Cluster Kubernetes local | `minikube version` |
| **kubectl** | Cliente do Kubernetes | `kubectl version --client` |
| **Helm** | Instala o Chaos Mesh | `helm version` |

Registre o repositório Helm do Chaos Mesh (uma vez só):

```bash
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update
```

---

## B. Preparação do ambiente — uma vez por cluster

Comandos de configuração que **persistem enquanto o cluster existir**. Só precisa
repetir se você apagar o cluster (`minikube delete`) e criar de novo.

**1. Subir o cluster** (runtime `containerd`; o driver docker com Docker 29+ é
incompatível com o chaos-daemon):

```bash
minikube start --driver=docker --container-runtime=containerd --cpus=4 --memory=6g
minikube addons enable metrics-server
```

**2. Instalar o Chaos Mesh** (1 réplica do controller basta para o laboratório):

```bash
helm install chaos-mesh chaos-mesh/chaos-mesh -n chaos-mesh --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock \
  --set controllerManager.replicaCount=1 \
  --version 2.6.3
```

**3. Subir a aplicação e a observabilidade** (Prometheus + Grafana em `../k8s/`):

```bash
kubectl apply -f ../k8s/            # deployments, services, hpa da aplicação
kubectl apply -f ../k8s/prometheus.yaml
kubectl apply -f ../k8s/grafana.yaml
```

---

## C. Antes de cada sessão de teste — toda vez

Passos rápidos que **não persistem** e precisam ser refeitos a cada vez que você
liga a máquina / retoma os testes.

**1. Módulos de kernel do NetworkChaos** (necessários só para o experimento de
rede; o driver docker compartilha o kernel do host, e `modprobe` manual **não
sobrevive a reboot**):

```bash
sudo modprobe sch_netem ip_set ip_set_hash_net ip_set_hash_ip xt_set
lsmod | grep -E 'sch_netem|ip_set|xt_set'          # confirma que carregaram
```

> Se a máquina não foi reiniciada desde a última sessão, eles já estão na memória
> e este passo pode ser pulado. Para carregar automaticamente em todo boot, veja
> "Tornar os módulos permanentes" no fim do documento.

**2. Se o cluster foi desligado** (`minikube stop` ou a máquina reiniciou), religue
sem recriar — tudo do bloco B continua lá:

```bash
minikube start                                     # reusa o cluster existente
```

**3. Verificar que está tudo de pé:**

```bash
kubectl get pods                                   # app, prometheus, grafana Running
kubectl get pods -n chaos-mesh                     # chaos-mesh Running
kubectl get crd | grep chaos-mesh.org              # networkchaos/podchaos/stresschaos
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

- **Estado Estável:** painel **Latência p95** em ~10ms; o frontend responde de
  imediato (HTTP 200); requisição pod-a-pod ao `order-service` em ~0.01s.
- **Hipótese:** cada perna do atraso (2s) fica abaixo do timeout de 3s do
  `frontend/client.py`, mas o efeito se **compõe** a cada round-trip (handshake +
  requisição + resposta ≈ 4× → ~8s no cliente), ultrapassando o timeout em toda
  requisição. O frontend degrada de forma graciosa (retry esgota → circuit breaker
  abre → mensagem de indisponível) sem quebrar a interface e sem duplicar pedidos.
- **Configuração do Ataque:** `delay latency=2000ms jitter=100ms`, `mode=all`,
  `duration=60s`.

**Demonstração visual:**

1. Deixe à vista o painel **Latência p95** e o frontend no navegador (F12 → Network).
2. Injete o ataque (sempre delete-e-aplique para forçar injeção nova):
   ```bash
   kubectl delete -f network-chaos.yaml --ignore-not-found
   kubectl apply  -f network-chaos.yaml
   ```
3. Observe o painel **Latência p95** subir de ~10ms para ~8s. No navegador,
   recarregue a página: aparece o texto vermelho **"Serviço temporariamente
   indisponível"** (o atraso composto estoura o timeout de 3s).

**Verificação por terminal** (mede a latência client-side, ainda maior que o p95
server-side):

```bash
kubectl describe networkchaos network-delay-order-service | grep -A6 "Status:"   # AllInjected: True
kubectl exec deploy/frontend -- python -c "import time,requests; t=time.time(); requests.get('http://order-service:8001/orders'); print(round(time.time()-t,3),'s')"
```

O comando demora ~8s — o atraso de 2s se compõe a cada round-trip, bem acima do
timeout de 3s que o frontend se recusa a esperar.

- **Resultado Observado:** p95 sobe para ~2s; o frontend degrada com mensagem de
  indisponível, sem quebrar a interface e sem criar/duplicar pedidos.
- **Ações Corretivas:** timeout de 3s + retry (tenacity) + circuit breaker
  (pybreaker) no `frontend/client.py`; e **chave de idempotência** (`idempotency_key`)
  para que o retry de escrita não gere pedidos duplicados (`frontend/client.py` +
  `order-service`).

```bash
kubectl delete -f network-chaos.yaml --ignore-not-found
```

---

## 2. PodChaos — Falha de Instância

- **Estado Estável:** painel **Réplicas ativas** = 2.
- **Hipótese:** ao matar **uma** das réplicas, a outra continua atendendo
  (redundância), então **não há impacto para o usuário**; o Kubernetes recria a
  réplica morta (self-healing) e o serviço volta a 2 réplicas sozinho.
- **Configuração do Ataque:** `action=pod-kill`, `mode=one`.

> `pod-kill` é instantâneo e o Kubernetes recria o pod em poucos segundos — janela
> menor que o intervalo de coleta (5s), que o gráfico não registraria. Um
> `initContainer` `slow-start` (`sleep 25`) no Deployment do `order-service`
> (`k8s/order-service.yaml`) simula um warm-up lento: o pod é recriado na hora, mas
> só passa a servir na `:8001` após ~25s — alargando a janela o suficiente para a
> queda de 2 → 1 aparecer no painel. A volta a 2 continua sendo **self-healing real**
> (pod novo, `AGE` resetado).

> Deixe o **gerador de carga** rodando (seção "Acesso às telas") para comprovar que o
> serviço continua respondendo durante todo o ataque.

**Demonstração visual:**

1. No Grafana, deixe à vista o painel **Réplicas ativas**.
2. Injete o ataque (sempre delete-e-aplique para forçar injeção nova):
   ```bash
   kubectl delete -f pod-chaos.yaml --ignore-not-found
   kubectl apply  -f pod-chaos.yaml
   ```
3. Observe **Réplicas ativas** cair de 2 para **1** e permanecer assim por ~25s (o
   warm-up do pod recriado), voltando a 2 sozinha.
4. No navegador: recarregue a página durante a janela — ela **continua funcionando
   normalmente** (a réplica sobrevivente atende; o retry cobre qualquer requisição
   que tenha caído no pod morto). É a prova de disponibilidade por redundância.

**Verificação por terminal:**

```bash
kubectl describe podchaos pod-kill-order-service | grep -A6 "Status:"   # AllInjected: True
kubectl get pods -l app=order-service -w    # um pod com AGE resetado (self-healing)
```

- **Resultado Observado:** uma réplica é morta e recriada; painel cai de 2 para 1 por
  ~25s, **sem indisponibilidade** (a outra réplica segue atendendo); recuperação
  automática a 2 ao fim do warm-up. Print do painel **Réplicas ativas**.
- **Ações Corretivas:** `replicas: 2` (redundância) + auto-recuperação do Kubernetes
  (self-healing); o retry no `frontend/client.py` absorve as requisições que
  atingiram o pod morto durante a transição.

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

