# MAIA EKS Deployment Runbook

> Registro completo de la infraestructura desplegada. Permite recuperar el estado
> exacto del sistema desde cero o diagnosticar problemas rápidamente.
>
> **Script automático**: `scripts/full-deploy.ps1`

---

## Datos Fijos del Entorno

| Variable | Valor |
|---|---|
| AWS Account ID | `360879159958` |
| Region | `us-east-1` |
| EKS Cluster | `maia-dev-eks` |
| ECR Repo | `360879159958.dkr.ecr.us-east-1.amazonaws.com/maia-dev-ecr` |
| S3 Bucket | `maia-dev-artifacts-37e567a4` |
| ALB DNS (activo) | `maia-alb-1736872550.us-east-1.elb.amazonaws.com` |
| ALB DNS (viejo terraform, vacío) | `maia-dev-alb-821977149.us-east-1.elb.amazonaws.com` |
| VPC ID | `vpc-0bcabca7a1b69957f` |
| OIDC Provider ID | `54979A0F10FE2CBBAFF3C75200C89DE3` |
| EKS Node Role | `maia-dev-eks-node-role` |
| ALB Controller Role | `AmazonEKSLoadBalancerControllerRole` |
| ALB Controller Policy | `AWSLoadBalancerControllerIAMPolicy` (v3.3.0) |
| Namespace K8s | `maia` |

### Subnets públicas (para el Ingress)
| Subnet ID | AZ |
|---|---|
| `subnet-013c940ec293be0b2` | us-east-1a |
| `subnet-0c6d8636fbd1d67f6` | us-east-1b |
| `subnet-03b7a3532ca0a076f` | us-east-1c |
| `subnet-091b9d3496c56d794` | us-east-1d |
| `subnet-0a7b441bf832e3df5` | us-east-1e |
| `subnet-0080f72a65e4458de` | us-east-1f |

### IAM Users con acceso a EKS Console
- `arn:aws:iam::360879159958:user/terraform-user` → `system:masters`
- `arn:aws:iam::360879159958:user/MAIA-scoliosis-user` → `system:masters`

---

## Modelos en S3

| Modelo | S3 Key |
|---|---|
| Binary Curve CNN | `experiments/v02A/pipeline_model/01_binary_curve_cnn/last_binary_curve_model.pt` |
| Student Patch CNN | `experiments/v02A/pipeline_model/02_student_1ch_4heads/student_1ch_multihead_ALL_FINETUNES_CHECKOUTS_20260520_004121_current_loaded_full_checkpoint.pt` |

---

## Estado de los Pods (referencia)

```
NAMESPACE    NAME                                           READY   STATUS    RESTARTS
maia         backend-xxx                                    1/1     Running   0
maia         frontend-xxx                                   1/1     Running   0
maia         kafka-xxx                                      1/1     Running   0-1
maia         listener-xxx                                   1/1     Running   0
maia         mongo-xxx                                      1/1     Running   0
kube-system  aws-load-balancer-controller-xxx (x2)         1/1     Running   0
```

---

## Pasos de Despliegue Completo (desde cero)

### Paso 0 — Prerrequisitos locales

```powershell
# Herramientas requeridas:
# - AWS CLI v2 (configurado con terraform-user credentials)
# - kubectl
# - helm
# - docker (Desktop corriendo)
# - terraform

aws configure  # usar credenciales de terraform-user
aws sts get-caller-identity  # verificar cuenta 360879159958
```

### Paso 1 — Terraform (infraestructura base)

```powershell
cd "C:\Users\Tavo\MAIA_TESIS\MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA\infra\terraform"

# Copiar y editar tfvars si no existe
Copy-Item terraform.tfvars.example terraform.tfvars

terraform init
terraform apply -auto-approve
```

Outputs que se usan después:
- `eks_cluster_name` → `maia-dev-eks`
- `ecr_repository_url` → `360879159958.dkr.ecr.us-east-1.amazonaws.com/maia-dev-ecr`
- `s3_bucket_name` → `maia-dev-artifacts-37e567a4`

### Paso 2 — Kubeconfig

```powershell
aws eks update-kubeconfig --region us-east-1 --name maia-dev-eks
kubectl get nodes  # debe mostrar 2 nodos Ready
```

### Paso 3 — Fix IMDS hop limit (CRÍTICO para acceso S3 desde pods)

Sin este paso, boto3 dentro de los contenedores no puede obtener credenciales del node role.

```powershell
# Obtener instance IDs de los nodos EKS
$nodes = aws ec2 describe-instances `
  --filters "Name=tag:eks:cluster-name,Values=maia-dev-eks" `
  --query "Reservations[*].Instances[*].InstanceId" `
  --output text

foreach ($id in ($nodes -split '\s+' | Where-Object { $_ })) {
    Write-Host "Updating IMDS hop limit for $id..."
    aws ec2 modify-instance-metadata-options `
      --instance-id $id `
      --http-put-response-hop-limit 2 `
      --http-endpoint enabled
}
```

> **Nota**: Al añadir nuevos nodos (escalado), repetir este paso para los nuevos.

### Paso 4 — IAM: S3 ReadOnly para el node role

```powershell
aws iam attach-role-policy `
  --role-name maia-dev-eks-node-role `
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess
```

### Paso 5 — IAM: ALB Controller Role + Policy

```powershell
$ACCOUNT_ID = "360879159958"
$OIDC_ID    = "54979A0F10FE2CBBAFF3C75200C89DE3"
$OIDC_PROVIDER = "oidc.eks.us-east-1.amazonaws.com/id/$OIDC_ID"

# Descargar política v3.3.0 (incluye DescribeListenerAttributes)
Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v3.3.0/docs/install/iam_policy.json" `
  -OutFile "$env:TEMP\alb-iam-policy.json"

aws iam create-policy `
  --policy-name AWSLoadBalancerControllerIAMPolicy `
  --policy-document "file://$env:TEMP\alb-iam-policy.json"

# Trust policy para IRSA del ALB controller
$trust = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Federated":"arn:aws:iam::' + $ACCOUNT_ID + ':oidc-provider/' + $OIDC_PROVIDER + '"},"Action":"sts:AssumeRoleWithWebIdentity","Condition":{"StringEquals":{"' + $OIDC_PROVIDER + ':sub":"system:serviceaccount:kube-system:aws-load-balancer-controller","' + $OIDC_PROVIDER + ':aud":"sts.amazonaws.com"}}}]}'
$trust | Out-File -Encoding ascii "$env:TEMP\alb-trust.json"

aws iam create-role `
  --role-name AmazonEKSLoadBalancerControllerRole `
  --assume-role-policy-document "file://$env:TEMP\alb-trust.json"

aws iam attach-role-policy `
  --role-name AmazonEKSLoadBalancerControllerRole `
  --policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy"
```

### Paso 6 — Instalar AWS Load Balancer Controller (Helm)

```powershell
$VPC_ID = "vpc-0bcabca7a1b69957f"

helm repo add eks https://aws.github.io/eks-charts
helm repo update eks

helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller `
  -n kube-system `
  --set clusterName=maia-dev-eks `
  "--set=serviceAccount.annotations.eks\.amazonaws\.com/role-arn=arn:aws:iam::360879159958:role/AmazonEKSLoadBalancerControllerRole" `
  --set region=us-east-1 `
  --set vpcId=$VPC_ID `
  --wait --timeout=180s

kubectl get pods -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
# Esperado: 2 pods 1/1 Running
```

> **IMPORTANTE**: Si falla con "VPC ID from instance metadata" → asegurarse de pasar `--set vpcId=...`
> Si falla con "DescribeListenerAttributes" → bajar política v2.6.0 y subir v3.3.0 (Paso 5)

### Paso 7 — Build y Push de imagen backend

```powershell
$ECR = "360879159958.dkr.ecr.us-east-1.amazonaws.com/maia-dev-ecr"

aws ecr get-login-password --region us-east-1 | `
  docker login --username AWS --password-stdin 360879159958.dkr.ecr.us-east-1.amazonaws.com

# Si docker login da "Error saving credentials: not implemented":
# es un warning cosmético, el login sí funciona, continuar.

docker build -t "${ECR}:backend-dev" `
  "C:\Users\Tavo\MAIA_TESIS\MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA\back"

docker push "${ECR}:backend-dev"
```

### Paso 8 — Desplegar manifests K8s

```powershell
cd "C:\Users\Tavo\MAIA_TESIS\MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA"

kubectl apply -k k8s/eks/
kubectl apply -f k8s/eks/ingress.yaml   # Ingress no está en kustomization

kubectl get pods -n maia
kubectl get ingress -n maia
# ADDRESS del ingress tarda ~2 min en aparecer (ALB provisionando)
```

### Paso 9 — aws-auth: acceso a consola EKS

```powershell
$patchFile = "$env:TEMP\aws-auth-patch.yaml"
@"
data:
  mapUsers: |
    - userarn: arn:aws:iam::360879159958:user/terraform-user
      username: terraform-user
      groups:
      - system:masters
    - userarn: arn:aws:iam::360879159958:user/MAIA-scoliosis-user
      username: MAIA-scoliosis-user
      groups:
      - system:masters
"@ | Out-File -Encoding utf8 $patchFile

kubectl patch configmap aws-auth -n kube-system --type merge --patch-file $patchFile
```

### Paso 10 — Verificar despliegue

```powershell
$ALB = "maia-alb-1736872550.us-east-1.elb.amazonaws.com"

# Health check
curl.exe "http://$ALB/api/v1/health"
# Esperado: {"status":"ok"}

# Test pipeline (primera vez descarga modelos de S3 ~1-2 min)
$IMG = "C:\Users\Tavo\MAIA_TESIS\MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA\front\src\imports\Front_Escoliosis.png"
curl.exe -X POST "http://$ALB/api/v1/pipeline/run" -F "file=@$IMG" -F "full_assets=||"
```

---

## Acceso local a MongoDB y Kafka (port-forward)

```powershell
# MongoDB Compass → conectar a mongodb://localhost:27017
kubectl port-forward -n maia svc/mongo 27017:27017

# Kafka client → bootstrap: localhost:9092
kubectl port-forward -n maia svc/kafka 9092:9092
```

---

## Rollout de nueva imagen backend

```powershell
# Después de cambiar código en back/
docker build -t "360879159958.dkr.ecr.us-east-1.amazonaws.com/maia-dev-ecr:backend-dev" `
  "C:\Users\Tavo\MAIA_TESIS\MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA\back"
docker push "360879159958.dkr.ecr.us-east-1.amazonaws.com/maia-dev-ecr:backend-dev"
kubectl rollout restart deployment/backend deployment/listener -n maia
kubectl rollout status deployment/backend -n maia --timeout=120s
```

---

## Diagnóstico rápido

```powershell
# Estado general
kubectl get pods -n maia
kubectl get nodes

# Logs backend (últimas 50 líneas)
kubectl logs -n maia deployment/backend --tail=50

# Logs listener
kubectl logs -n maia deployment/listener --tail=30

# Eventos del Ingress (ALB)
kubectl describe ingress maia-alb-ingress -n maia | Select-String "Events" -Context 0,20

# Verificar credenciales S3 desde el pod
kubectl exec -n maia deployment/backend -- python -c "import boto3; boto3.client('s3').list_buckets(); print('S3 OK')"

# IMDS hop limit actual de los nodos
aws ec2 describe-instances `
  --filters "Name=tag:eks:cluster-name,Values=maia-dev-eks" `
  --query "Reservations[*].Instances[*].{ID:InstanceId,HopLimit:MetadataOptions.HttpPutResponseHopLimit}" `
  --output table
```

---

## Problemas conocidos y soluciones

| Error | Causa | Solución |
|---|---|---|
| `NoCredentialsError: Unable to locate credentials` | IMDS hop limit = 1 | Paso 3: `modify-instance-metadata-options --http-put-response-hop-limit 2` |
| `AccessDenied: DescribeListenerAttributes` | IAM policy ALB v2.6.0 | Paso 5: bajar y re-crear policy con JSON de v3.3.0 |
| `failed to fetch VPC ID from instance metadata` | ALB Controller sin VPC explícita | `helm ... --set vpcId=vpc-0bcabca7a1b69957f` |
| `Error saving credentials: not implemented` | Docker credential store | Warning cosmético, ignorar — el login sí funciona |
| `pending-install` en helm list | Helm timeout con helm release bloqueada | `helm uninstall aws-load-balancer-controller -n kube-system` y reinstalar |
| `ModuleNotFoundError: No module named 'pandas'` | Faltaba en requirements.txt | Agregar `pandas==2.2.3` y rebuild imagen |
| `No PodTemplates / you don't have permission` en consola EKS | Usuario IAM no en aws-auth | Paso 9: patch aws-auth ConfigMap |

---

## Pendientes

- [ ] Frontend real (build de `front/` → ECR tag `frontend-dev`)
- [ ] Test completo del pipeline de inferencia (modelo descargado desde S3 + resultado)
- [ ] Destruir ALB viejo de Terraform: `terraform destroy -target=aws_lb.maia_alb`
- [ ] Agregar `pandas==2.2.3` a `back/requirements.txt` y hacer push de nueva imagen

---

## Variables de entorno del Backend (k8s/eks/backend.yaml)

```yaml
APP_ENV: production
APP_HOST: 0.0.0.0
APP_PORT: "8000"
AWS_REGION: us-east-1
AWS_S3_BUCKET: maia-dev-artifacts-37e567a4
MONGO_URI: mongodb://mongo:27017
MONGO_DB: app_db
REDIS_URI: redis://redis:6379/0
KAFKA_BOOTSTRAP_SERVERS: kafka:9092
PIPELINE_INSTANCE_MODE: "true"
PIPELINE_WRITE_METRICS_TO_MONGO: "true"
PIPELINE_PUBLISH_EVENTS_TO_KAFKA: "true"
PIPELINE_BINARY_CURVE_MODEL_PATH: experiments/v02A/pipeline_model/01_binary_curve_cnn/last_binary_curve_model.pt
PIPELINE_STUDENT_PATCH_MODEL_PATH: experiments/v02A/pipeline_model/02_student_1ch_4heads/student_1ch_multihead_ALL_FINETUNES_CHECKOUTS_20260520_004121_current_loaded_full_checkpoint.pt
PIPELINE_MODELS_LOCAL_DIR: /tmp/pipeline_models
```
