# ZeroTrace Enterprise Deployment Runbook

This guide instructs Enterprise SecOps and Platform Engineers on deploying ZeroTrace into sovereign, air-gapped Kubernetes environments (AWS EKS, GCP GKE, Azure AKS, or On-Premise).

---

## 1. Prerequisites

- Kubernetes cluster v1.26+
- Helm v3.10+
- PostgreSQL 16 with `pgvector` extension
- Redis 7+
- S3-compatible Object Storage (AWS S3, MinIO, or Google Cloud Storage)

---

## 2. Quick Deploy with Helm

### Step 1: Add or Clone Repository
```bash
git clone https://github.com/moiz-on-git/ZeroTrace.git
cd ZeroTrace/deploy/helm/zerotrace
```

### Step 2: Configure Environment Values
Create a custom `values.prod.yaml`:
```yaml
global:
  environment: production
  imageRegistry: ghcr.io/moiz-on-git

orchestrator:
  replicaCount: 3
  env:
    ZT_ENV: production
    ZT_ANCHOR_PROVIDER: shiprite
    ZT_DATABASE_URL: "postgresql+asyncpg://user:password@postgres-service:5432/zt_prod"
    ZT_REDIS_URL: "redis://:password@redis-service:6379/1"

dataPlane:
  replicaCount: 2
  env:
    ZT_POSTGRES_URL: "postgresql://user:password@postgres-service:5432/zt_rag"
    ZT_S3_BUCKET: "enterprise-lakehouse-bucket"
    AWS_REGION: "ap-south-1"

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: privacy.company.com
      paths:
        - path: /
          pathType: Prefix
          service: web
    - host: api-privacy.company.com
      paths:
        - path: /
          pathType: Prefix
          service: orchestrator
```

### Step 3: Deploy Helm Chart
```bash
helm upgrade --install zerotrace . \
  -n zerotrace --create-namespace \
  -f values.prod.yaml
```

---

## 3. Verifying Pod Security & Network Policies

ZeroTrace strictly isolates the Data Plane from public ingress via Kubernetes `NetworkPolicy`:
```bash
# Verify all pods are running non-root with dropped capabilities
kubectl get pods -n zerotrace -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.securityContext}{"\n"}{end}'

# Verify data isolation policy
kubectl describe networkpolicy zerotrace-data-isolation -n zerotrace
```

---

## 4. Disaster Recovery & Sovereign Key Management

- **Legal Ed25519 Keys**: Keys are injected via Kubernetes Secrets or HashiCorp Vault sidecar.
- **HMAC Pepper Secrets**: Rotated using envelope encryption via AWS KMS or GCP Cloud KMS.
