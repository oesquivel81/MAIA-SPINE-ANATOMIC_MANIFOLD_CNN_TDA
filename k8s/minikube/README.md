# Minikube stack: frontend + backend + redis + mongo

## Requisitos

- Docker Desktop iniciado
- kubectl instalado
- Minikube instalado

## Iniciar cluster

En PowerShell:

```powershell
& "C:\Program Files\Kubernetes\Minikube\minikube.exe" start --driver=docker --cpus=2 --memory=2200 --kubernetes-version=stable
```

## Construir y cargar imagen del backend

```powershell
cd C:\Users\octav\OneDrive\Documents\Proyecto_Grado_MAIA\MAIA-SPINE-ANATOMIC_MANIFOLD_CNN_TDA
docker build -t maia-back:dev -f back/Dockerfile back
& "C:\Program Files\Kubernetes\Minikube\minikube.exe" image load maia-back:dev
```

## Desplegar recursos Kubernetes

```powershell
kubectl apply -k k8s/minikube
kubectl get pods -n maia
kubectl get svc -n maia
```

## Acceso a servicios en Windows (driver Docker)

Abre una terminal por servicio y dejala abierta:

```powershell
& "C:\Program Files\Kubernetes\Minikube\minikube.exe" service backend -n maia --url
& "C:\Program Files\Kubernetes\Minikube\minikube.exe" service frontend -n maia --url
```

Notas:
- Las URLs son tipo `http://127.0.0.1:<puerto>`
- Si cierras esa terminal, el tunel se cierra

## Validaciones rapidas

```powershell
# Backend
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:<puerto_backend>/api/v1/health"

# Frontend
Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:<puerto_frontend>"
```

## Limpiar

```powershell
kubectl delete -k k8s/minikube
& "C:\Program Files\Kubernetes\Minikube\minikube.exe" stop
```

## Nota del frontend

Actualmente `front/` solo tiene un README, por eso el despliegue usa un frontend temporal con NGINX.
Cuando tengas app real (React/Next/Vite), se reemplaza el deployment `frontend.yaml`.
