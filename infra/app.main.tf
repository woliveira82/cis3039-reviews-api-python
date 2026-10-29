###############################################################################
# Reviews SPA — TEST environment (Azure Storage static website)
#
# Terraform equivalent of README "Publish manually to Azure Storage". Each
# resource has the original `az` / `npm` command commented above it for
# comparison.
#
# The SPA never talks to Cosmos DB: the browser only calls the Reviews API
# (src/infra/http-review-service.ts). The test resource group, Cosmos DB and
# Python Function App are owned by cis3039-reviews-api-python/infra/main.tf;
# apply that first. This file reads its outputs from the local state file.
#
#   terraform -chdir=terraform init
#   terraform -chdir=terraform apply -var="uid=ab47"
#
# Prerequisites: `az login`, Node/npm, and `npm ci` already run in this repo.
###############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

# az login
# az account set --subscription 'YOUR_SUBSCRIPTION_ID'
provider "azurerm" {
  features {}
  # Null falls back to ARM_SUBSCRIPTION_ID / the `az account show` subscription.
  subscription_id = var.subscription_id
}

# -----------------------------------------------------------------------------
# Variables
# -----------------------------------------------------------------------------

variable "subscription_id" {
  description = "Azure subscription id. Null uses ARM_SUBSCRIPTION_ID or the az CLI default."
  type        = string
  default     = null
}

variable "uid" {
  description = "Short unique id used in every resource name (e.g. ab47)."
  type        = string
  default     = "ab47"

  validation {
    # Storage account names: 3-24 lowercase letters/digits ("reviewstest" + uid + "spa").
    condition     = can(regex("^[a-z0-9]{1,10}$", var.uid))
    error_message = "uid must be 1-10 lowercase letters/digits (storage account name limit)."
  }
}

variable "api_state_path" {
  description = "Local state file of the Python API's Terraform (cis3039-reviews-api-python/infra)."
  type        = string
  default     = "../../cis3039-reviews-api-python/infra/terraform.tfstate"
}

# -----------------------------------------------------------------------------
# Naming and inputs from the API deployment
# -----------------------------------------------------------------------------

# Replaces the manual D6 step:
# az functionapp show \
#   --name 'YOUR_TEST_FUNCTION_APP' \
#   --resource-group 'reviews-test-YOUR_UID-rg' \
#   --query defaultHostName --output tsv
data "terraform_remote_state" "api" {
  backend = "local"
  config = {
    path = abspath("${path.module}/${var.api_state_path}")
  }
}

locals {
  rg_name              = "reviews-test-${var.uid}-rg"
  spa_storage_name     = "reviewstest${var.uid}spa"
  test_function_app    = data.terraform_remote_state.api.outputs.function_app_name
  reviews_api_base_url = trimsuffix(data.terraform_remote_state.api.outputs.reviews_url, "/reviews")

  app_root = abspath("${path.module}/..")

  # Rebuild and re-upload when sources or build settings change.
  spa_source_hash = sha1(join("", concat(
    [for f in sort(fileset("${local.app_root}/src", "**")) : filesha1("${local.app_root}/src/${f}")],
    [for f in ["index.html", "package-lock.json", "vite.config.ts"] : filesha1("${local.app_root}/${f}")],
  )))
}

# -----------------------------------------------------------------------------
# 1. Existing test resource group (created with the API)
# -----------------------------------------------------------------------------

# az group show --name "$TEST_RESOURCE_GROUP" --output json
data "azurerm_resource_group" "test" {
  name = local.rg_name
}

# -----------------------------------------------------------------------------
# 1. Separate SPA storage account
# -----------------------------------------------------------------------------

# az storage account check-name --name "$SPA_STORAGE_ACCOUNT" --output json
#
# az storage account create \
#   --name "$SPA_STORAGE_ACCOUNT" \
#   --resource-group "$TEST_RESOURCE_GROUP" \
#   --location "$SPA_REGION" \
#   --sku Standard_LRS \
#   --kind StorageV2
resource "azurerm_storage_account" "spa" {
  name                     = local.spa_storage_name
  resource_group_name      = data.azurerm_resource_group.test.name
  location                 = data.azurerm_resource_group.test.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"

  tags = { environment = "test" }
}

# -----------------------------------------------------------------------------
# 2. Enable static website hosting
# -----------------------------------------------------------------------------

# az storage blob service-properties update \
#   --account-name "$SPA_STORAGE_ACCOUNT" \
#   --static-website true \
#   --index-document index.html
resource "azurerm_storage_account_static_website" "spa" {
  storage_account_id = azurerm_storage_account.spa.id
  index_document     = "index.html"
}

locals {
  # SITE_URL=$(az storage account show ... --query primaryEndpoints.web --output tsv)
  # SITE_ORIGIN="${SITE_URL%/}"
  site_origin = trimsuffix(azurerm_storage_account.spa.primary_web_endpoint, "/")
}

# -----------------------------------------------------------------------------
# 3. Build against the test API and publish
# -----------------------------------------------------------------------------

# .env:
#   VITE_REVIEWS_SERVICE=http
#   VITE_USE_SEED_DATA=false
#   VITE_REVIEWS_BASE_URL=https://YOUR_ACTUAL_TEST_HOSTNAME/api
#
# npm run build
#
# az storage blob upload-batch \
#   --account-name "$SPA_STORAGE_ACCOUNT" \
#   --source ./dist \
#   --destination '$web' \
#   --overwrite true
#
# Vite gives shell variables priority over .env, so the settings are passed as
# environment variables and .env does not need editing. dist/ is produced during
# apply, so the upload uses the CLI rather than azurerm_storage_blob.
resource "terraform_data" "publish" {
  triggers_replace = [
    azurerm_storage_account_static_website.spa.id,
    local.reviews_api_base_url,
    local.spa_source_hash,
  ]

  provisioner "local-exec" {
    working_dir = local.app_root
    command     = "npm run build && az storage blob upload-batch --account-name ${azurerm_storage_account.spa.name} --source ./dist --destination '$web' --overwrite true"

    environment = {
      VITE_REVIEWS_SERVICE  = "http"
      VITE_USE_SEED_DATA    = "false"
      VITE_REVIEWS_BASE_URL = local.reviews_api_base_url
    }
  }
}

# -----------------------------------------------------------------------------
# 4. Allow the website origin on the test Function App
# -----------------------------------------------------------------------------

# az functionapp cors add \
#   --name "$TEST_FUNCTION_APP" \
#   --resource-group "$API_RESOURCE_GROUP" \
#   --allowed-origins "$SITE_ORIGIN"
#
# The Function App belongs to the API's Terraform, so CORS is added with the
# CLI here instead of redefining that resource.
resource "terraform_data" "cors" {
  triggers_replace = [local.test_function_app, local.site_origin]

  provisioner "local-exec" {
    command = "az functionapp cors add --name ${local.test_function_app} --resource-group ${data.azurerm_resource_group.test.name} --allowed-origins ${local.site_origin}"
  }
}

# -----------------------------------------------------------------------------
# Verify (manual): open site_url, check GET /api/reviews in Network returns the
# seeded test data, then POST a review and confirm it survives a refresh.
# -----------------------------------------------------------------------------

output "site_url" {
  value = azurerm_storage_account.spa.primary_web_endpoint
}

output "reviews_api_base_url" {
  description = "VITE_REVIEWS_BASE_URL baked into the build."
  value       = local.reviews_api_base_url
}
