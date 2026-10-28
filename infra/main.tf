# Provisions the test Function App for the Reviews API (Python 3.14, Flex
# Consumption). Linux Consumption does not support Python 3.13+, so this uses
# Flex Consumption instead of `az functionapp create --consumption-plan-location`.
# Terraform creates the infrastructure only; publish the code afterwards with:
#
#   func azure functionapp publish reviews-test-ab47-func
#
# Usage:
#   export TF_VAR_cosmos_key="$TEST_COSMOS_KEY"
#   terraform -chdir=infra init
#   terraform -chdir=infra apply

locals {
  subscription_id = "316bb7db-3c11-4533-9127-e7a6610a2c98"
  location        = "uksouth"

  resource_group_name       = "reviews-test-ab47-rg"
  storage_account_name      = "reviewstestab47funcstore"
  deployment_container_name = "app-package"
  service_plan_name         = "reviews-test-ab47-plan"
  function_app_name         = "reviews-test-ab47-func"

  python_version         = "3.14"
  instance_memory_in_mb  = 2048
  maximum_instance_count = 40

  cosmos_endpoint     = "https://reviews-test-ab47-cosmos.documents.azure.com:443/"
  cosmos_database_id  = "reviews-db"
  cosmos_container_id = "reviews"
}

# The account key is the only secret, so it is supplied at apply time instead
# of being committed: export TF_VAR_cosmos_key="$TEST_COSMOS_KEY".
variable "cosmos_key" {
  description = "Primary key of the test Cosmos DB account."
  type        = string
  sensitive   = true
}

terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = local.subscription_id
}

resource "azurerm_resource_group" "rg" {
  name     = local.resource_group_name
  location = local.location
}

# az storage account create --sku Standard_LRS
resource "azurerm_storage_account" "func" {
  name                     = local.storage_account_name
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  min_tls_version          = "TLS1_2"
}

# Flex Consumption deploys the app package to a blob container.
resource "azurerm_storage_container" "deployments" {
  name                  = local.deployment_container_name
  storage_account_id    = azurerm_storage_account.func.id
  container_access_type = "private"
}

resource "azurerm_service_plan" "plan" {
  name                = local.service_plan_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  os_type             = "Linux"
  sku_name            = "FC1"
}

# az functionapp create, with Python instead of Node. Flex Consumption rejects
# FUNCTIONS_WORKER_RUNTIME and FUNCTIONS_EXTENSION_VERSION as app settings; the
# runtime comes from runtime_name/runtime_version instead.
resource "azurerm_function_app_flex_consumption" "func" {
  name                = local.function_app_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  service_plan_id     = azurerm_service_plan.plan.id

  storage_container_type      = "blobContainer"
  storage_container_endpoint  = "${azurerm_storage_account.func.primary_blob_endpoint}${azurerm_storage_container.deployments.name}"
  storage_authentication_type = "StorageAccountConnectionString"
  storage_access_key          = azurerm_storage_account.func.primary_access_key

  runtime_name           = "python"
  runtime_version        = local.python_version
  instance_memory_in_mb  = local.instance_memory_in_mb
  maximum_instance_count = local.maximum_instance_count

  https_only = true

  site_config {}

  # az functionapp config appsettings set
  app_settings = {
    COSMOS_ENDPOINT     = local.cosmos_endpoint
    COSMOS_DATABASE_ID  = local.cosmos_database_id
    COSMOS_CONTAINER_ID = local.cosmos_container_id
    COSMOS_KEY          = var.cosmos_key
  }
}

output "function_app_name" {
  value = azurerm_function_app_flex_consumption.func.name
}

output "reviews_url" {
  value = "https://${azurerm_function_app_flex_consumption.func.default_hostname}/api/reviews"
}
