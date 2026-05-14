#!/bin/bash

# Script para instalar AWS Load Balancer Controller en EKS
# Uso: ./install-alb-controller.sh <cluster-name> [region]

set -e

CLUSTER_NAME="${1:-maia-eks}"
REGION="${2:-us-east-1}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "🔧 Instalando AWS Load Balancer Controller"
echo "   Cluster: $CLUSTER_NAME"
echo "   Region: $REGION"
echo "   Account: $ACCOUNT_ID"
echo ""

# Paso 1: Crear OIDC Provider
echo "📝 Paso 1: Creando OIDC Provider..."
OIDC_ID=$(aws eks describe-cluster --name $CLUSTER_NAME --region $REGION --query "cluster.identity.oidc.issuer" --output text | cut -d '/' -f 5)
OIDC_PROVIDER="oidc.eks.${REGION}.amazonaws.com/id/${OIDC_ID}"

aws iam create-open-id-connect-provider \
    --url "https://${OIDC_PROVIDER%/id/*}" \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 1b511abead59c6ce207077c0ef0285eea7d6491fa6 \
    --region $REGION 2>/dev/null && echo "✓ OIDC Provider creado" || echo "✓ OIDC Provider ya existe"

# Paso 2: Descargar política IAM
echo ""
echo "📝 Paso 2: Descargando política IAM..."
curl -s https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.6.0/docs/install/iam_policy.json -o /tmp/iam-policy.json
echo "✓ Política descargada"

# Paso 3: Crear IAM Policy
echo ""
echo "📝 Paso 3: Creando IAM Policy..."
aws iam create-policy \
    --policy-name AWSLoadBalancerControllerIAMPolicy \
    --policy-document file:///tmp/iam-policy.json \
    --region $REGION 2>/dev/null && echo "✓ IAM Policy creada" || echo "✓ IAM Policy ya existe"

# Paso 4: Crear IAM Role
echo ""
echo "📝 Paso 4: Creando IAM Role..."

TRUST_POLICY=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/${OIDC_PROVIDER}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "${OIDC_PROVIDER}:sub": "system:serviceaccount:kube-system:aws-load-balancer-controller"
        }
      }
    }
  ]
}
EOF
)

aws iam create-role \
    --role-name AmazonEKSLoadBalancerControllerRole \
    --assume-role-policy-document "$TRUST_POLICY" \
    --region $REGION 2>/dev/null && echo "✓ IAM Role creado" || echo "✓ IAM Role ya existe"

# Paso 5: Adjuntar política
echo ""
echo "📝 Paso 5: Adjuntando política IAM..."
aws iam attach-role-policy \
    --role-name AmazonEKSLoadBalancerControllerRole \
    --policy-arn "arn:aws:iam::${ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy" \
    --region $REGION 2>/dev/null && echo "✓ Política adjunta" || echo "✓ Política ya adjunta"

# Paso 6: Instalar con Helm
echo ""
echo "📝 Paso 6: Instalando con Helm..."
helm repo add eks https://aws.github.io/eks-charts
helm repo update

kubectl config use-context "arn:aws:eks:${REGION}:${ACCOUNT_ID}:cluster/${CLUSTER_NAME}" 2>/dev/null || \
    aws eks update-kubeconfig --name $CLUSTER_NAME --region $REGION

helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
    -n kube-system \
    --set clusterName=$CLUSTER_NAME \
    --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"="arn:aws:iam::${ACCOUNT_ID}:role/AmazonEKSLoadBalancerControllerRole" \
    --wait

echo "✓ Helm chart instalado"

# Verificación final
echo ""
echo "📝 Verificando instalación..."
kubectl rollout status deployment/aws-load-balancer-controller -n kube-system --timeout=180s
echo ""
echo "✅ AWS Load Balancer Controller instalado exitosamente"
echo ""
echo "🚀 Próximos pasos:"
echo "   1. Aplicar el Ingress: kubectl apply -f k8s/eks/ingress.yaml"
echo "   2. Verificar: kubectl get ingress -n maia -w"
echo "   3. Esperar a que obtenga ADDRESS (DNS del ALB)"
