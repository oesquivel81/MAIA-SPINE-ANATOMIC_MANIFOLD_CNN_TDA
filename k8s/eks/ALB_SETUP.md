# Configuración de ALB para EKS

## Requisitos previos

1. **EKS Cluster**: Debe estar creado y operativo (se crea con Terraform)
2. **OIDC Provider**: Necesario para IAM roles for service accounts (IRSA)
3. **AWS Load Balancer Controller**: Debe estar instalado en el cluster

## Instalación del AWS Load Balancer Controller

### Paso 1: Crear OIDC Provider (una vez)

```bash
# Obtener el OIDC ID del cluster
CLUSTER_NAME="maia-eks"
OIDC_ID=$(aws eks describe-cluster --name $CLUSTER_NAME --query "cluster.identity.oidc.issuer" --output text | cut -d '/' -f 5)

# Crear OIDC Provider (solo si no existe)
aws iam create-open-id-connect-provider \
    --url "https://oidc.eks.us-east-1.amazonaws.com/id/$OIDC_ID" \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 1b511abead59c6ce207077c0ef0285eea7d6491fa6 || echo "OIDC Provider ya existe"
```

### Paso 2: Crear IAM Role para el Load Balancer Controller

```bash
# Descargar política
curl https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.6.0/docs/install/iam_policy.json -o iam-policy.json

# Crear IAM Policy
aws iam create-policy \
    --policy-name AWSLoadBalancerControllerIAMPolicy \
    --policy-document file://iam-policy.json \
    2>/dev/null || echo "Policy ya existe"

# Crear IAM Role
CLUSTER_NAME="maia-eks"
OIDC_ID=$(aws eks describe-cluster --name $CLUSTER_NAME --query "cluster.identity.oidc.issuer" --output text | cut -d '/' -f 5)

aws iam create-role \
    --role-name AmazonEKSLoadBalancerControllerRole \
    --assume-role-policy-document "{
      \"Version\": \"2012-10-17\",
      \"Statement\": [
        {
          \"Effect\": \"Allow\",
          \"Principal\": {
            \"Federated\": \"arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/$OIDC_ID\"
          },
          \"Action\": \"sts:AssumeRoleWithWebIdentity\",
          \"Condition\": {
            \"StringEquals\": {
              \"oidc.eks.us-east-1.amazonaws.com/id/$OIDC_ID:sub\": \"system:serviceaccount:kube-system:aws-load-balancer-controller\"
            }
          }
        }
      ]
    }" \
    2>/dev/null || echo "Role ya existe"

# Adjuntar política al role
aws iam attach-role-policy \
    --role-name AmazonEKSLoadBalancerControllerRole \
    --policy-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/AWSLoadBalancerControllerIAMPolicy \
    2>/dev/null || echo "Policy ya adjunta"
```

### Paso 3: Instalar el Load Balancer Controller con Helm

```bash
# Agregar Helm repository
helm repo add eks https://aws.github.io/eks-charts
helm repo update

# Instalar el controlador
CLUSTER_NAME="maia-eks"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
    -n kube-system \
    --set clusterName=$CLUSTER_NAME \
    --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"="arn:aws:iam::$ACCOUNT_ID:role/AmazonEKSLoadBalancerControllerRole"
```

## Crear el Ingress con ALB

Después de instalar el Load Balancer Controller, aplicar la Ingress:

```bash
kubectl apply -f k8s/eks/ingress.yaml
```

Esperar a que se cree el ALB:

```bash
kubectl get ingress -n maia -w
```

Cuando esté listo, verás la URL del ALB en la columna `ADDRESS`.

## Verificar el ALB

```bash
# Ver detalles del Ingress
kubectl describe ingress maia-alb-ingress -n maia

# Ver los target groups y health
aws elbv2 describe-target-health --target-group-arn <arn-del-target-group>
```

## Rutas disponibles

Una vez que el ALB esté en funcionamiento:

- **Frontend**: `http://<ALB-DNS>/`
- **Backend API**: `http://<ALB-DNS>/api/v1/...`
- **Health Check**: `http://<ALB-DNS>/api/v1/health`

## Infraestructura Terraform

El archivo `infra/terraform/alb.tf` crea:

- Security Group para el ALB
- Application Load Balancer
- Target Groups (uno para backend, uno para frontend)
- Listener HTTP
- Listener Rules para ruteo basado en path

Outputs disponibles después de `terraform apply`:

```bash
terraform output alb_dns_name      # DNS del ALB
terraform output alb_url           # URL completa
terraform output alb_arn           # ARN del ALB
```

## Notas importantes

1. El ALB se crea en EKS mode (`count = local.use_eks ? 1 : 0`)
2. Las subnets públicas se filtran automáticamente por AZ soportadas
3. Health check apunta a `/api/v1/health` del backend
4. El Ingress usa pathType `Prefix` para flexibilidad en rutas
5. El target type es `ip` (estándar para EKS)

## Troubleshooting

### El ALB Controller no se instala

```bash
# Verificar si el controller está corriendo
kubectl get deployment -n kube-system aws-load-balancer-controller

# Ver logs
kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller
```

### El Ingress no tiene ADDRESS

```bash
# Verificar eventos
kubectl describe ingress maia-alb-ingress -n maia

# Ver reconciliation logs
kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller | grep ingress
```

### Targets unhealthy

```bash
# Verificar que los servicios están en ejecución
kubectl get svc -n maia
kubectl get pods -n maia

# Revisar logs del backend
kubectl logs -n maia -l app=backend
```
