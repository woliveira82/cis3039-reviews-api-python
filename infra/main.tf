# Provisions the test environment for the Reviews API: a serverless Cosmos DB
# account with its database and container, and a Python 3.14 Function App on
# Flex Consumption. Linux Consumption does not support Python 3.13+, so this uses
# Flex Consumption instead of `az functionapp create --consumption-plan-location`.
# Terraform creates the infrastructure only; seed and publish afterwards with:
#
#   func azure functionapp publish reviews-test-<YOUR ID>-func
#
# Usage:
#   terraform -chdir=infra init
#   terraform -chdir=infra apply
#
# The state stores the Cosmos and storage keys, so keep *.tfstate out of Git.

locals {
  subscription_id = "316bb7db-3c11-4533-9127-e7a6610a2c98"
  location        = "uksouth"

  resource_group_name       = "reviews-test-<YOUR ID>-rg"
  storage_account_name      = "reviewstest<YOUR ID>funcstore"
  deployment_container_name = "app-package"
  service_plan_name         = "reviews-test-<YOUR ID>-plan"
  function_app_name         = "reviews-test-<YOUR ID>-func"

  python_version         = "3.14"
  instance_memory_in_mb  = 2048
  maximum_instance_count = 40

  cosmos_account_name        = "reviews-test-<YOUR ID>-cosmos"
  cosmos_database_id         = "reviews-db"
  cosmos_container_id        = "reviews"
  cosmos_partition_key_paths = ["/id"]
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

# az cosmosdb create --kind GlobalDocumentDB --capabilities EnableServerless
#   --default-consistency-level Session
#   --locations regionName=uksouth failoverPriority=0 isZoneRedundant=False
resource "azurerm_cosmosdb_account" "cosmos" {
  name                = local.cosmos_account_name
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  # The app authenticates with the account key, so key auth must stay enabled.
  local_authentication_enabled = true

  capabilities {
    name = "EnableServerless"
  }

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.rg.location
    failover_priority = 0
    zone_redundant    = false
  }
}

# az cosmosdb sql database create
resource "azurerm_cosmosdb_sql_database" "reviews" {
  name                = local.cosmos_database_id
  resource_group_name = azurerm_resource_group.rg.name
  account_name        = azurerm_cosmosdb_account.cosmos.name
}

# az cosmosdb sql container create --partition-key-path '/id'
resource "azurerm_cosmosdb_sql_container" "reviews" {
  name                = local.cosmos_container_id
  resource_group_name = azurerm_resource_group.rg.name
  account_name        = azurerm_cosmosdb_account.cosmos.name
  database_name       = azurerm_cosmosdb_sql_database.reviews.name
  partition_key_paths = local.cosmos_partition_key_paths
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

  # az functionapp config appsettings set, wired to the account created above.
  app_settings = {
    COSMOS_ENDPOINT     = azurerm_cosmosdb_account.cosmos.endpoint
    COSMOS_DATABASE_ID  = azurerm_cosmosdb_sql_database.reviews.name
    COSMOS_CONTAINER_ID = azurerm_cosmosdb_sql_container.reviews.name
    COSMOS_KEY          = azurerm_cosmosdb_account.cosmos.primary_key
  }
}

output "cosmos_endpoint" {
  value = azurerm_cosmosdb_account.cosmos.endpoint
}

# Read with: export COSMOS_KEY="$(terraform -chdir=infra output -raw cosmos_key)"
output "cosmos_key" {
  value     = azurerm_cosmosdb_account.cosmos.primary_key
  sensitive = true
}

output "function_app_name" {
  value = azurerm_function_app_flex_consumption.func.name
}

output "reviews_url" {
  value = "https://${azurerm_function_app_flex_consumption.func.default_hostname}/api/reviews"
}
