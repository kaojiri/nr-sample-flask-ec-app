#!/bin/bash
set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
AWS_REGION=${AWS_REGION:-ap-northeast-1}
PROJECT_NAME="flask-ec-app"

echo -e "${GREEN}=== Flask EC App Deployment Script ===${NC}"

# Check if required tools are installed
command -v aws >/dev/null 2>&1 || { echo -e "${RED}AWS CLI is required but not installed.${NC}" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo -e "${RED}Docker is required but not installed.${NC}" >&2; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo -e "${RED}kubectl is required but not installed.${NC}" >&2; exit 1; }

# Get ECR repository URL from Terraform output
echo -e "${YELLOW}Getting ECR repository URL...${NC}"
cd terraform
ECR_REPO=$(terraform output -raw ecr_repository_url)
CLUSTER_NAME=$(terraform output -raw eks_cluster_name)
cd ..

echo -e "${GREEN}ECR Repository: ${ECR_REPO}${NC}"
echo -e "${GREEN}EKS Cluster: ${CLUSTER_NAME}${NC}"

# Login to ECR
echo -e "${YELLOW}Logging in to ECR...${NC}"
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_REPO}

# Build Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
docker build -t ${PROJECT_NAME}:latest .

# Tag and push to ECR
echo -e "${YELLOW}Tagging and pushing to ECR...${NC}"
docker tag ${PROJECT_NAME}:latest ${ECR_REPO}:latest
docker tag ${PROJECT_NAME}:latest ${ECR_REPO}:$(git rev-parse --short HEAD 2>/dev/null || echo "manual")
docker push ${ECR_REPO}:latest
docker push ${ECR_REPO}:$(git rev-parse --short HEAD 2>/dev/null || echo "manual")

# Configure kubectl
echo -e "${YELLOW}Configuring kubectl...${NC}"
aws eks update-kubeconfig --region ${AWS_REGION} --name ${CLUSTER_NAME}

# Update Kubernetes manifests with ECR repository URL
echo -e "${YELLOW}Updating Kubernetes manifests...${NC}"
find k8s/ -name "*.yaml" -type f -exec sed -i.bak "s|<YOUR_ECR_REPO_URL>|${ECR_REPO}|g" {} \;

# Apply Kubernetes manifests
echo -e "${YELLOW}Applying Kubernetes manifests...${NC}"
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml

# Run database migration
echo -e "${YELLOW}Running database migration...${NC}"
kubectl apply -f k8s/migration-job.yaml

# Wait for deployment
echo -e "${YELLOW}Waiting for deployment to be ready...${NC}"
kubectl wait --for=condition=available --timeout=300s deployment/flask-ec-app -n flask-ec-app

# Get service URL
echo -e "${GREEN}Deployment completed!${NC}"
echo -e "${YELLOW}Getting service URL...${NC}"
kubectl get svc flask-ec-app-service -n flask-ec-app

echo -e "${GREEN}=== Deployment Complete ===${NC}"
