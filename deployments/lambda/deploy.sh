#!/bin/bash
# Deploy MCP Gateway to AWS Lambda

set -e

echo "Building Lambda deployment package..."

# Install dependencies with platform and Python version for Lambda compatibility
pip install -r requirements.txt \
    --platform manylinux2014_x86_64 \
    --python-version 3.11 \
    --only-binary=:all: \
    -t ./package/

# Copy source code
cp -r src ./package/
cp -r deployments ./package/

# Create deployment package
cd package
zip -r ../lambda-deployment.zip . -x "*.pyc" "*__pycache__*"
cd ..

# Clean up
rm -rf package

echo "Deployment package created: lambda-deployment.zip"
echo ""
echo "To deploy, run:"
echo "  sam deploy --template-file deployments/lambda/template.yaml --guided"
echo ""
echo "Or use AWS CLI:"
echo "  aws lambda update-function-code --function-name mcp-gateway-lambda --zip-file fileb://lambda-deployment.zip"
