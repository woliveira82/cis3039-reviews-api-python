# Week 5 Reviews API

A Python Azure Functions API for the CIS3039 Week 5 deployment and
configuration work. It stores Reviews in Azure Cosmos DB for NoSQL, exposes
anonymous GET and POST endpoints, and includes a repeatable upsert seed command.

This guide supplements the guided Week 5 worksheet. It covers local setup, the
Part C configuration exercise, separate development and test databases, manual
Azure deployment, verification, redeployment and safe cleanup. Supplementary
checks below do not add required lab steps or replace the worksheet's evidence.

Week 5 moves from local development with cloud persistence to a deployed
browser–API–database test environment. `dev` is a logical environment: here it
combines a local API with dedicated Azure development Cosmos resources. `test`
has deployed components with separate data and configuration. Resource groups
organise resources and their lifecycle; endpoints, credentials and application
configuration determine which data each process accesses.

This is a practice copy, separate from your assessment implementation. The
assessment requirements, deadlines, criteria and deliverables remain unchanged.

## API and code structure

The API exposes these routes:

| Method | Route | Successful response |
| --- | --- | --- |
| `GET` | `/api/reviews` | `200` with `{ reviews, totalCount }` |
| `POST` | `/api/reviews` | `201` with `{ review }` |

POST bodies use this shape:

```json
{
  "rating": 5,
  "title": "Excellent",
  "comment": "A useful review."
}
```

The repository keeps domain, application, infrastructure and transport code
separate:

| Path | Responsibility |
| --- | --- |
| `function_app.py` | Azure Functions entry point that registers the HTTP blueprints |
| `src/domain/` | Review model and repository port |
| `src/app/` | Add/list use cases |
| `src/infra/` | Fake and Cosmos repository adapters |
| `src/config/composition_root.py` | Cosmos configuration and dependency assembly |
| `src/functions/` | Azure Functions HTTP handlers |
| `scripts/` | No-cloud demos, settings loader, seed runner and seed data |

The Cosmos container uses `/id` as its partition key. Seed reruns upsert the five
supplied IDs and retain unrelated records.

### Boundary and repository contracts

Successful HTTP envelopes are endpoint-specific rather than universal. POST
returns `{ review }`; GET returns `{ reviews, totalCount }`, where `totalCount`
is the number of reviews returned by that read. Each review contains `id`,
`rating`, `title`, `comment` and an ISO-string `createdAt`. The domain retains
`created_at` as a timezone-aware `datetime`; conversion happens explicitly at the
HTTP and Cosmos boundaries.

Malformed requests and domain validation failures return HTTP 400 with
`{ issues: [{ field, message }] }`. Unexpected configuration, generator, clock,
repository, stored-data or response-mapping failures return a generic HTTP 500
without exposing internal details.

Within the application, creation and add operations return frozen dataclass
results discriminated by `success`: successful results carry `data`, while
expected validation failures carry `issues`. Listing returns a result with
`success=True` and `data`. Operational failures raise exceptions instead of
being presented as validation results.

Both `FakeReviewRepo` and `CosmosReviewRepo` implement the same `ReviewRepo`
protocol: async `get_by_id()` returns a review or `None`, `list()` returns a
sequence, and `save()` performs an unconditional upsert and returns the
persisted entity. That returned entity can differ from the submitted entity, so
`add_review()` returns the value from `save()`. Reviews are frozen dataclasses,
so the fake can share them safely; the Cosmos adapter validates data returned by
the SDK.

## Development environment

Install VS Code, a working container runtime and the VS Code Dev Containers
extension. Use the same history-preserving private-copy route as Week 4.
Clone the maintained example and open it in VS Code:

```sh
git clone https://github.com/tpdavison/cis3039-reviews-api.git
cd cis3039-reviews-api
code .
```

Choose **Dev Containers: Reopen in Container**. Create an empty **private**
repository in your GitHub account, without a README, licence or `.gitignore`.
In the container terminal, replace `YOUR_GITHUB_USERNAME` and point `origin` at
that repository, inspect both remote URLs, then push the existing history:

```sh
git remote set-url origin https://github.com/YOUR_GITHUB_USERNAME/cis3039-reviews-api.git
git remote -v
git branch --show-current
git push -u origin main
```

Confirm the branch is `main` and the remote is your private repository before
pushing. The current student links target the maintained repository's `main`.
Keep the cloned history; do not initialise a new history or create a public fork.

Run all remaining Bash commands from the API repository root inside the Dev
Container, including when using Windows as the host computer.

The declared environment uses:

- `ghcr.io/tpdavison/devops-labs:2026-latest`
- Python `3.14` (pinned in `.python-version`)
- [uv](https://docs.astral.sh/uv/) for dependency and environment management
- Azure Functions runtime/Core Tools `4.x`

Install uv in the container if it is missing, then run `uv sync`. The container image tag is intentionally floating, so inspect the
installed versions when diagnosing a later difference.

```sh
uv --version
uv run python --version
func --version
az version
uv sync --locked
```

`uv sync --locked` creates `.venv/` from the committed `uv.lock` and fails if the
lockfile is out of date with `pyproject.toml`. Do not replace it with an
unlocked install as evidence that the repository works. No automated test suite
is supplied.

Python needs no build step. Prefix commands with `uv run` so they use the
project's `.venv/`; for example `uv run func start` runs the local Function host
with the project interpreter, and `uv run ruff check .` lints the code.

Manage dependencies with uv rather than editing files by hand:

```sh
uv add PACKAGE            # runtime dependency
uv add --dev PACKAGE      # development-only tool
uv export --no-dev --no-hashes --no-emit-project -o requirements.txt
```

Azure builds the deployed app from `requirements.txt`, so regenerate it with the
`uv export` command above after every dependency change and commit it with
`pyproject.toml` and `uv.lock`.

## Configuration model and Part C constraint

The starting repository deliberately keeps three non-secret values hard-coded
in `src/config/composition_root.py`:

- the Cosmos account endpoint;
- the database ID (`reviews-db`);
- the container ID (`reviews`).

Only `COSMOS_KEY` is initially read from `os.environ`. This is deliberate:
externalising the other three values is the Part C student exercise. Do not
replace the starting code with a completed solution before doing that exercise.

The final configuration contract uses exactly these names:

- `COSMOS_ENDPOINT`
- `COSMOS_DATABASE_ID`
- `COSMOS_CONTAINER_ID`
- `COSMOS_KEY`

`local.settings.example.json` is a tracked, non-secret template. Real
`*.settings.json` files are ignored by Git and by Function deployment.

### How settings reach the process

Environment-based application configuration is consumed through `os.environ`;
the three starting constants remain the Part C exception described above.
Three mechanisms supply those environment variables:

- Core Tools loads `Values` from `local.settings.json` for the local Functions host.
- Standalone scripts call the generic settings loader before doing any work.
- Azure Function App application settings supply deployed environment variables.

The loader (`scripts/load_settings.py`) is not imported into HTTP handlers. The
seed script runs it first, passing its optional command-line argument:

```sh
uv run python -m scripts.seed_review_repo [ENVIRONMENT]
```

Run scripts as modules (`-m`) from the repository root so `src` and `scripts`
import as packages.

The supplied loader is course infrastructure; students should not need to edit
it. Its file selection is:

| Command | Selected input |
| --- | --- |
| `uv run python -m scripts.seed_review_repo` | Only `local.settings.json`, if present; otherwise shell values |
| `uv run python -m scripts.seed_review_repo test` | Requires only `test.settings.json`; missing file is an error |
| `uv run python -m scripts.seed_review_repo shell` | Deliberately loads no settings file |

Additional loader rules:

- a missing default `local.settings.json` preserves shell-only variables;
- a missing explicitly named settings file fails instead of falling back;
- file values override variables inherited from the shell;
- collision warnings disclose variable names, never values;
- malformed JSON and unsafe environment names fail clearly.

`shell` is reserved for shell-only mode and cannot be used as an environment
file name. Named files can be intentionally incomplete: variables absent from
their `Values` object remain inherited from the shell, so always inspect the
non-secret target printed before seeding.

Overrides affect only the Python process, not the invoking shell. The loader
loads at most one file; it does not discover Azure resources, retrieve keys or
validate Cosmos-specific settings.

Because file values take precedence, the non-secret template deliberately omits
`COSMOS_KEY`. Keep account keys in the shell rather than adding an empty or real
key to a copied settings file. An empty key entry would override a valid shell
key. File selection does not prove that every effective value belongs to test:
a partial file can mix its values with inherited shell configuration.

The loader's optional default file applies only to standalone scripts. For local
Functions runs, provide `local.settings.json` with the template's
`FUNCTIONS_WORKER_RUNTIME=python`. Before Part C, create a minimal host settings
file as shown below; after Part C, copy and edit the full template.

## Run the no-cloud demonstrations

Two deterministic scripts demonstrate the domain and application contracts
without settings files, Cosmos DB or the Functions host:

```sh
uv run python -m scripts.demo_domain
uv run python -m scripts.demo_reviews
```

The domain demo shows a valid review and readable issues from an invalid review.
The application demo uses fixed ID and clock dependencies with `FakeReviewRepo`.
It makes the entity returned by `save()` visible, then demonstrates listing,
missing-item behaviour and that returned reviews cannot be mutated.

## Select the Azure subscription and region

The following sections manually create billable Azure resources. Run commands
individually, inspect their results, and stop if a subscription, region, name or
existing resource does not match your intended environment.

The Cosmos operations used here are core Azure CLI commands. The
`cosmosdb-preview` extension is not required.

Replace every `YOUR_...` placeholder in a command before running it. Use your
own short lowercase-letter-and-digit identifier for `YOUR_UID`, and use an
Azure region permitted by your subscription for `YOUR_REGION` (for example,
`uksouth`).

```sh
az cosmosdb create --help
az cosmosdb sql database create --help
az cosmosdb sql container create --help
az login
az account list \
  --query "[].{subscriptionName:name,subscriptionId:id,isDefault:isDefault}" \
  --output table
```

Select and verify the correct subscription:

```sh
az account set --subscription YOUR_SUBSCRIPTION_ID
az account show \
  --query '{subscriptionName:name,subscriptionId:id}' \
  --output table
```

The table queries give columns explicit display names. Azure CLI's table
formatter can omit properties named `id`, `type` or `etag`; aliases such as
`subscriptionId` and `resourceType` keep those values visible.

Inspect available locations, Cosmos DB provider support and inherited policy:

```sh
az account list-locations \
  --query '[].{region:name,displayName:displayName}' --output table
az provider show --namespace Microsoft.DocumentDB \
  --query '{registrationState:registrationState,regions:resourceTypes[?resourceType==`databaseAccounts`].locations}' \
  --output json
az policy assignment list --scope '/subscriptions/YOUR_SUBSCRIPTION_ID' \
  --disable-scope-strict-match true --output json
```

A region appearing in `list-locations` does not prove that subscription policy
permits Cosmos DB there. The examples use `uksouth`. If it is unavailable,
agree another supported region and use it consistently. Ask the subscription
administrator or tutor for help rather than bypassing policy or provider
registration.

The commands use `reviews-db` as the database ID and `reviews` as the container
ID. Development resources use the `reviews-dev-YOUR_UID-...` pattern and test
resources use `reviews-test-YOUR_UID-...`.

Cosmos account names are globally unique, contain 3–44 lowercase letters,
numbers or hyphens, and start with a lowercase letter or number.

## Cost and capacity warning

Serverless Cosmos DB charges for consumed request units and retained storage.
The development and test accounts are independently billable environments.
Serverless consumes subscription credit and is not eligible for the Cosmos DB
[lifetime free-tier discount](https://learn.microsoft.com/en-us/azure/cosmos-db/free-tier).
Function execution, its required storage account and any automatically created
monitoring resources can also incur charges.

Do not add `--throughput` or `--max-throughput` to the database or container
commands below. `EnableServerless` establishes the intended capacity model when
each account is created. An existing provisioned-throughput account does not
become serverless merely because database/container creation succeeds.

Serverless accounts are single-region and do not provide the predictable
throughput model of provisioned capacity. Review Microsoft's
[serverless overview](https://learn.microsoft.com/en-us/azure/cosmos-db/serverless)
and [capacity-mode comparison](https://learn.microsoft.com/en-us/azure/cosmos-db/throughput-serverless)
before provisioning.

## Provision the development Cosmos environment

Create the dedicated development resource group, serverless account, database
and container:

```sh
az group create \
  --name reviews-dev-YOUR_UID-rg \
  --location YOUR_REGION \
  --output none

az cosmosdb create \
  --resource-group reviews-dev-YOUR_UID-rg \
  --name reviews-dev-YOUR_UID-cosmos \
  --kind GlobalDocumentDB \
  --locations regionName=YOUR_REGION failoverPriority=0 isZoneRedundant=False \
  --capabilities EnableServerless \
  --default-consistency-level Session \
  --output none

az cosmosdb sql database create \
  --resource-group reviews-dev-YOUR_UID-rg \
  --account-name reviews-dev-YOUR_UID-cosmos \
  --name reviews-db \
  --output none

az cosmosdb sql container create \
  --resource-group reviews-dev-YOUR_UID-rg \
  --account-name reviews-dev-YOUR_UID-cosmos \
  --database-name reviews-db \
  --name reviews \
  --partition-key-path '/id' \
  --output none
```

Verify capacity, location, endpoint, key authentication and partition design:

```sh
az cosmosdb show \
  --resource-group reviews-dev-YOUR_UID-rg \
  --name reviews-dev-YOUR_UID-cosmos \
  --query '{endpoint:documentEndpoint,capabilities:capabilities[].name,locations:locations[].locationName,keyAuthDisabled:disableLocalAuth}' \
  --output json

az cosmosdb sql container show \
  --resource-group reviews-dev-YOUR_UID-rg \
  --account-name reviews-dev-YOUR_UID-cosmos \
  --database-name reviews-db \
  --name reviews \
  --query '{id:resource.id,partitionKey:resource.partitionKey.paths}' \
  --output json
```

Confirm `EnableServerless`, the selected region, key authentication not disabled,
and `/id`. Stop and resolve any mismatch before continuing.

Display the non-secret endpoint, then retrieve the development key into the
environment without displaying it. Copy the endpoint output for the
configuration steps below:

```sh
az cosmosdb show \
  --resource-group reviews-dev-YOUR_UID-rg \
  --name reviews-dev-YOUR_UID-cosmos \
  --query documentEndpoint --output tsv

export COSMOS_KEY="$(az cosmosdb keys list \
  --resource-group reviews-dev-YOUR_UID-rg \
  --name reviews-dev-YOUR_UID-cosmos \
  --type keys \
  --query primaryMasterKey --output tsv)"
```

Do not print the key, enable shell tracing during retrieval, or put it in source
control. Your signed-in identity must have permission to list account keys.

The shell now holds the development account key. An `export` applies to the
current shell session and processes started from it. Repeat the appropriate
key-retrieval command in a new terminal, on another computer or after recreating
the container; do not assume the key is available there.

## Confirm the starting configuration behaviour

Before Part C, edit only the three hard-coded non-secret values in
`src/config/composition_root.py` so they identify the development account you just
created. The database and container defaults already match the commands above;
replace the demonstration endpoint with the endpoint printed by the preceding
`az cosmosdb show` command.

The preceding key-retrieval command exports the key under the one name the
starting code already reads. Seed the development database:

```sh
uv run python -m scripts.seed_review_repo
```

The seed command prints the endpoint, database and container before writing. It
never prints the key. Confirm the displayed target is the development account.
This output is diagnostic, not an interactive confirmation prompt: writes begin
immediately. It sequentially upserts IDs `1`–`5`; reruns replace those items and
retain unrelated records. A failure can leave earlier writes saved.

Before the first local host run, create this ignored host settings file. It
selects the Python worker without completing the three-value Part C exercise:

```sh
cat > local.settings.json <<'JSON'
{
  "IsEncrypted": false,
  "Values": {
    "FUNCTIONS_WORKER_RUNTIME": "python"
  }
}
JSON
```

Start the local Function host in the terminal that exported the key:

```sh
uv run func start
```

In a separate request terminal, verify GET. The POST below is a supplementary
API check:

```sh
curl -i http://localhost:7071/api/reviews

curl -i -X POST \
  -H 'Content-Type: application/json' \
  -d '{"rating":5,"title":"Local check","comment":"Created through the API."}' \
  http://localhost:7071/api/reviews
```

Expect HTTP 200 from GET, and HTTP 201 if you try a valid supplementary POST.
Stop the host with Ctrl+C. A storage health warning can appear because this HTTP-only example does
not configure local Azure Storage. Its HTTP triggers do not require Azurite for
this exercise; the template supplies the Python worker selection and omits
`AzureWebJobsStorage`. A warning is not evidence of storage-trigger readiness.
Adding storage bindings would need their own storage configuration. The deployed
Function App still requires its separate hosting Storage account.

## Complete the Part C externalisation exercise

Now change `COSMOS_OPTIONS` in `src/config/composition_root.py` so the endpoint,
database ID and container ID come from the three corresponding environment
variables. Keep `COSMOS_KEY` environment-based. The completed composition root
must:

- use the four exact names listed earlier;
- reject every missing or blank required value clearly;
- keep `get_cosmos_target()` consistent with the configuration used by the repository,
  returning only the non-secret endpoint/database/container;
- never include the key in summaries or errors;
- retain lazy repository construction and the existing architectural boundary:
  importing the module must not require settings or create a Cosmos client.

Do not move Cosmos knowledge into `scripts/load_settings.py`, the repository
adapter or the HTTP handlers. The starting repository intentionally does not
contain the completed code for this exercise.

Values read with `os.environ.get()` have type `str | None`: a variable might
not exist. Validate missing or blank values before returning a definite string
for the Cosmos options. A validation helper can return a string or raise a safe
error; a working fallback is not required. Avoid default arguments that
silently choose an endpoint, database or container and hide missing configuration.
A type annotation or `typing.cast` does not validate a value. Read and validate configuration
when dependencies or the target summary are requested, preserving lazy assembly.

Before supplying the target settings, complete the required missing-configuration
checkpoint. Retain the minimal B4 `local.settings.json` above, containing only
the Python worker selection in `Values`. In the original dev-key terminal, keep
`COSMOS_KEY` exported and remove any inherited target variables:

```sh
unset COSMOS_ENDPOINT COSMOS_DATABASE_ID COSMOS_CONTAINER_ID
uv run func start
```

Lazy assembly may allow the host to start and discover functions. Actually repeat
the GET from the separate request terminal before adding settings:

```sh
curl -i http://localhost:7071/api/reviews
```

Expect generic HTTP 500 and a safe `dependency-construction` failure-stage log.
Host startup alone does not prove successful configuration; do not expect a
detailed public configuration error or guaranteed startup failure. If GET still
succeeds, inspect your code edit and inherited settings. Record the status and
safe failure stage, then stop the host with Ctrl+C.

Now copy the non-secret template over the minimal local settings file:

```sh
cp local.settings.example.json local.settings.json
```

Edit the copied file and replace `YOUR_UID` with the real development account
identifier, or replace the complete endpoint with the endpoint printed by the
development `az cosmosdb show` command. Keep `COSMOS_DATABASE_ID=reviews-db`
and `COSMOS_CONTAINER_ID=reviews`. The JSON template intentionally has no
`COSMOS_KEY` entry.

With the development key still exported in its original shell, seed and start
again:

```sh
uv run python -m scripts.seed_review_repo
uv run func start
```

Confirm the seed target is dev and repeat the GET from the separate request
terminal to verify the same development records. This demonstrates that both
entry points use the externalised configuration. Leave the dev host running in
its original dev-key shell during Part D; do not replace that shell's key with
the test key.

Record the development review IDs and titles (including any supplementary local
POST) so you can compare them after test seeding and deployment.

## Provision and configure the test Cosmos environment

The test environment must be separate from development. Keep the dev host running
in its original dev-key shell. Open another API-container terminal for test
provisioning, seeding, settings and deployment. In this test terminal, repeat the
subscription selection and verification above and use the same permitted region.
Exports do not propagate between terminals or alter already-running processes.
Reuse the agreed IDs, but create the dedicated `reviews-test-...` group and account:

```sh
az group create \
  --name reviews-test-YOUR_UID-rg \
  --location YOUR_REGION \
  --output none

az cosmosdb create \
  --resource-group reviews-test-YOUR_UID-rg \
  --name reviews-test-YOUR_UID-cosmos \
  --kind GlobalDocumentDB \
  --locations regionName=YOUR_REGION failoverPriority=0 isZoneRedundant=False \
  --capabilities EnableServerless \
  --default-consistency-level Session \
  --output none

az cosmosdb sql database create \
  --resource-group reviews-test-YOUR_UID-rg \
  --account-name reviews-test-YOUR_UID-cosmos \
  --name reviews-db \
  --output none

az cosmosdb sql container create \
  --resource-group reviews-test-YOUR_UID-rg \
  --account-name reviews-test-YOUR_UID-cosmos \
  --database-name reviews-db \
  --name reviews \
  --partition-key-path '/id' \
  --output none
```

Verify it independently:

```sh
az cosmosdb show \
  --resource-group reviews-test-YOUR_UID-rg \
  --name reviews-test-YOUR_UID-cosmos \
  --query '{endpoint:documentEndpoint,capabilities:capabilities[].name,locations:locations[].locationName,keyAuthDisabled:disableLocalAuth}' \
  --output json

az cosmosdb sql container show \
  --resource-group reviews-test-YOUR_UID-rg \
  --account-name reviews-test-YOUR_UID-cosmos \
  --database-name reviews-db \
  --name reviews \
  --query '{id:resource.id,partitionKey:resource.partitionKey.paths}' \
  --output json

az cosmosdb show \
  --resource-group reviews-test-YOUR_UID-rg \
  --name reviews-test-YOUR_UID-cosmos \
  --query documentEndpoint --output tsv

export COSMOS_KEY="$(az cosmosdb keys list \
  --resource-group reviews-test-YOUR_UID-rg \
  --name reviews-test-YOUR_UID-cosmos \
  --type keys \
  --query primaryMasterKey --output tsv)"
```

This separate test shell now holds the test account key. Keep it active through
test seeding, Function App configuration and deployment verification. Continue
local requests against the dev host in its original shell. If dev needs restarting
in a new or reused terminal, follow [Return to local development](#return-to-local-development).

Create an ignored test settings file from the same non-secret template and edit
its endpoint to the test value. Retain `reviews-db` and `reviews` as the database
and container IDs, and leave `COSMOS_KEY` absent so it comes from the shell:

```sh
cp local.settings.example.json test.settings.json
```

After completing Part C, seed only the test target:

```sh
uv run python -m scripts.seed_review_repo test
```

Check the printed target carefully. It must show the test endpoint and must not
show the development endpoint; the database/container must be `reviews-db` and
`reviews`. Confirm IDs `1`–`5` in the test Cosmos account's **Data Explorer in the
Azure Portal**, then compare development data with your recorded IDs and confirm
it is unchanged. Do not reseed test after the verification title edit below.
`uv run python -m scripts.seed_review_repo test` requires `test.settings.json`, never loads
`local.settings.json`, and leaves the test key active in the shell.

## Create the test Function App

Deploy only after completing Part C and verifying the test seed target. The
following creates a Flex Consumption Function App using Azure Functions runtime
4 and Python 3.14. Python 3.14 matches this repository's `.python-version`; Linux
Consumption does not support Python 3.13 or later, so this app uses Flex
Consumption. Check that your region offers it:

```sh
az functionapp list-flexconsumption-runtimes \
  --location YOUR_REGION --runtime python --output table
```

[`infra/main.tf`](infra/main.tf) provisions the same resources (and the Cosmos
application settings below) with Terraform as an alternative to these commands:

```sh
export TF_VAR_cosmos_key="$COSMOS_KEY"   # the test account key
terraform -chdir=infra init
terraform -chdir=infra apply
```

Function App hostnames and storage-account names are globally unique. The
hosting Storage account is distinct from either Cosmos account. Its name must
contain only lowercase letters and digits and be 3–24 characters. Adjust the names if Azure reports that they are unavailable, and
record the final values. Replace `YOUR_TEST_STORAGE_ACCOUNT` with such a name;
the uppercase placeholder is not itself a valid storage-account name.

```sh
az storage account check-name \
  --name YOUR_TEST_STORAGE_ACCOUNT \
  --query '{available:nameAvailable,reason:reason,message:message}' \
  --output json

az storage account create \
  --name YOUR_TEST_STORAGE_ACCOUNT \
  --resource-group reviews-test-YOUR_UID-rg \
  --location YOUR_REGION \
  --sku Standard_LRS \
  --kind StorageV2 \
  --output none

az functionapp create \
  --name reviews-test-YOUR_UID-func \
  --resource-group reviews-test-YOUR_UID-rg \
  --storage-account YOUR_TEST_STORAGE_ACCOUNT \
  --flex-consumption-location YOUR_REGION \
  --runtime python \
  --runtime-version 3.14 \
  --https-only true \
  --output none
```

Verify the explicit runtime before deployment:

```sh
az functionapp show \
  --name reviews-test-YOUR_UID-func \
  --resource-group reviews-test-YOUR_UID-rg \
  --query 'properties.functionAppConfig.runtime' \
  --output json

az functionapp show \
  --name reviews-test-YOUR_UID-func \
  --resource-group reviews-test-YOUR_UID-rg \
  --query httpsOnly \
  --output tsv
```

Expect runtime `python` version `3.14` and HTTPS enabled.

## Configure Azure application settings

Local settings files configure local processes; they are excluded from deployment
and do not configure the Function App in Azure. Azure needs its own application
settings, which become environment variables for the deployed process. Replace
`YOUR_TEST_COSMOS_ENDPOINT` with the endpoint printed for the test account. In the
test terminal, pass the test values and suppress command output so the key is not
printed:

**The shell's `COSMOS_KEY` must belong to the test Cosmos account.** Endpoint,
database, container and key must describe the same test target. Reacquire the
test key immediately before applying settings, even if you retrieved it earlier.
If retrieval fails or the key is empty, stop; do not apply settings.

```sh
export COSMOS_KEY="$(az cosmosdb keys list \
  --resource-group reviews-test-YOUR_UID-rg \
  --name reviews-test-YOUR_UID-cosmos \
  --type keys \
  --query primaryMasterKey --output tsv)"

test -n "${COSMOS_KEY:-}" && \
az functionapp config appsettings set \
  --name reviews-test-YOUR_UID-func \
  --resource-group reviews-test-YOUR_UID-rg \
  --settings \
    COSMOS_ENDPOINT='YOUR_TEST_COSMOS_ENDPOINT' \
    COSMOS_DATABASE_ID='reviews-db' \
    COSMOS_CONTAINER_ID='reviews' \
    COSMOS_KEY="$COSMOS_KEY" \
  --output none
```

Flex Consumption sets the runtime and extension version from the app's
configuration and rejects `FUNCTIONS_WORKER_RUNTIME` and
`FUNCTIONS_EXTENSION_VERSION` as application settings, so they are not set here.

Changing application settings restarts the app. List the names, then inspect only
the explicitly whitelisted non-secret target values:

```sh
az functionapp config appsettings list \
  --name reviews-test-YOUR_UID-func \
  --resource-group reviews-test-YOUR_UID-rg \
  --query '[].name' --output table

for setting in COSMOS_ENDPOINT COSMOS_DATABASE_ID COSMOS_CONTAINER_ID; do
  az functionapp config appsettings list \
    --name reviews-test-YOUR_UID-func \
    --resource-group reviews-test-YOUR_UID-rg \
    --query "[?name=='$setting'].{settingName:name,value:value}" --output table
done
```

Check all five relevant names: `AzureWebJobsStorage`, `COSMOS_ENDPOINT`,
`COSMOS_DATABASE_ID`, `COSMOS_CONTAINER_ID` and `COSMOS_KEY`. Check the actual
test account endpoint, database `reviews-db` and container `reviews`. Never
display credentials or an unfiltered settings response. Names alone do not prove
values or database connectivity; the deployed GET below checks connectivity.

## Build and deploy manually

Azure application settings configure how the deployed service runs; they do not
upload its code. This repository uses a remote build: Core Tools uploads the
source and Azure installs the packages listed in `requirements.txt`. In the test
terminal, check that the lockfile and `requirements.txt` are current, confirm the
functions are discoverable, and publish. Azure runs that code with the test
settings applied above. Publish only after every preceding command succeeds:

```sh
uv sync --locked
uv export --no-dev --no-hashes --no-emit-project -o requirements.txt
git diff --exit-code requirements.txt
uv run python -c "import function_app"
func azure functionapp publish reviews-test-YOUR_UID-func
```

`.funcignore` excludes local settings, the virtual environment, uv project files,
seed utilities and development-only tooling. The deployed app is discovered from
`function_app.py`, which registers the blueprints in `src/functions/`.

Do not use `--publish-local-settings`: test settings have already been applied
explicitly, and local development configuration must not be copied to Azure.

## Verify the deployed API

In the test terminal, retrieve the deployed app's actual hostname:

```sh
az functionapp show \
  --name reviews-test-YOUR_UID-func \
  --resource-group reviews-test-YOUR_UID-rg \
  --query defaultHostName --output tsv
```

Stop if retrieval fails or returns empty. Copy the returned hostname into a
separate request below, replacing `YOUR_RETURNED_HOSTNAME`. The URL combines the
scheme `https://`, the returned hostname and the route `/api/reviews`. Do not
construct the hostname by appending `.azurewebsites.net` to the app name.

```sh
curl -i https://YOUR_RETURNED_HOSTNAME/api/reviews
```

Expect HTTP 200 with `{ reviews, totalCount }` containing the seeded test IDs
`1`–`5`. Record the actual hostname for SPA integration and inspect the same URL
in a browser or Postman too. Complete the required D6 evidence:

1. In the **Azure Portal**, open the test Cosmos account's **Data Explorer**,
   database `reviews-db`, container `reviews`.
2. Edit only review `1`'s title to a recognisable valid test-only value such as
   `Test only YOUR_UID`, using your UID. Save it, leaving the ID, rating, comment
   and timestamp unchanged. Do not reseed afterwards.
3. Repeat the deployed GET and confirm that title appears. Repeat local dev GET
   against the host still running in its original dev-key shell and confirm the
   dev data is unchanged from your recorded baseline:

```sh
curl -i https://YOUR_RETURNED_HOSTNAME/api/reviews

curl -i http://localhost:7071/api/reviews
```

Seeded test IDs, the test-only title and unchanged local dev data are the required
connectivity and isolation evidence. A direct POST check is supplementary. If you
perform it, use the same returned hostname in both requests:

```sh
curl -i -X POST \
  -H 'Content-Type: application/json' \
  -d '{"rating":4,"title":"Deployment check","comment":"Created in the test environment."}' \
  https://YOUR_RETURNED_HOSTNAME/api/reviews

curl -i https://YOUR_RETURNED_HOSTNAME/api/reviews
```

For this supplementary check, expect 201 then 200. Confirm the posted item appears
only in the test Cosmos account, and compare development data with your recorded
baseline to confirm it is unchanged. The endpoints are deliberately anonymous for
this teaching API.

This verifies the API directly. Browser access from a separately hosted SPA can
also require Function App CORS configuration; that is an integration concern,
separate from authentication. CORS does not protect these anonymous endpoints
from direct clients such as `curl`. Keep Cosmos credentials in the API and
follow the Week 5 SPA guide for browser integration and SPA configuration
validation.

## Redeploy after a code change

Application settings persist across ordinary code deployments. Rebuild and
publish again:

```sh
uv sync --locked
uv export --no-dev --no-hashes --no-emit-project -o requirements.txt
git diff --exit-code requirements.txt
uv run python -c "import function_app"
func azure functionapp publish reviews-test-YOUR_UID-func
```

Repeat the deployed GET using the returned hostname and confirm unchanged dev
data after every deployment; repeat POST only as a supplementary check. Reapply
application settings only when their intended values change, and verify the
runtime again if the Function App platform configuration changes.

## Return to local development

During the guided route, dev remains running in its original dev-key shell; keep
using it for local requests. If the host has stopped or you are returning to local
work in a new or reused terminal, retrieve the development key there before
starting the host:

```sh
export COSMOS_KEY="$(az cosmosdb keys list \
  --resource-group reviews-dev-YOUR_UID-rg \
  --name reviews-dev-YOUR_UID-cosmos \
  --type keys \
  --query primaryMasterKey --output tsv)"
```

Confirm `local.settings.json` still identifies the development account endpoint,
database `reviews-db` and container `reviews`, with no `COSMOS_KEY` entry. The
shell now holds the development key; `uv run python -m scripts.seed_review_repo`
selects the local file and `uv run func start` runs against development after
Part C. Seed only if you intend to
replace the five sample records. Start the host in that terminal and verify the
local endpoint again:

```sh
uv run func start
```

In another terminal:

```sh
curl -i http://localhost:7071/api/reviews
```

Expect HTTP 200 and compare the returned development IDs and titles with your
saved baseline. The test-only title and any supplementary test POST must be absent;
your development reviews must be unchanged. Repeat the local POST check if needed.

If you later seed test or reapply test application settings, retrieve the test
key again using the commands in those sections. Selecting `test.settings.json`
does not retrieve a key or change the invoking shell.

## Safe cleanup

Stopping the local host or Function App does not delete Cosmos data or eliminate
retained-storage charges. Keep environments only while they are needed for the
lab and integrated rehearsal.

Before deleting anything, confirm the subscription, group identity and every
resource in the group:

```sh
az account show \
  --query '{subscriptionName:name,subscriptionId:id}' \
  --output table

az group show \
  --name reviews-test-YOUR_UID-rg \
  --query '{resourceGroupName:name,resourceGroupId:id,location:location}' \
  --output table

az resource list \
  --resource-group reviews-test-YOUR_UID-rg \
  --query '[].{resourceName:name,resourceType:type}' \
  --output table
```

Deletion permanently removes the Function App, its storage/monitoring resources,
the test Cosmos account and all test data in that group. Continue only if it is
your dedicated disposable test group and contains no assessment, shared or
unrelated or unfinished resources. Retain those deliberately. If anything is
unexpected, do not delete the group.

Run the command without `--yes` and read its confirmation prompt before
accepting:

```sh
az group delete --name reviews-test-YOUR_UID-rg
```

When deletion finishes, verify removal:

```sh
az group exists --name reviews-test-YOUR_UID-rg
```

Expect `false`. Inspect and delete the development group separately only when
development work is also complete:

```sh
az group show \
  --name reviews-dev-YOUR_UID-rg \
  --query '{resourceGroupName:name,resourceGroupId:id,location:location}' \
  --output table

az resource list \
  --resource-group reviews-dev-YOUR_UID-rg \
  --query '[].{resourceName:name,resourceType:type}' \
  --output table

az group delete --name reviews-dev-YOUR_UID-rg
az group exists --name reviews-dev-YOUR_UID-rg
```

Keep the repository and your notes; cleanup concerns cloud resources, not the
local or GitHub project.

## Command summary

| Command | Purpose | Azure required? |
| --- | --- | --- |
| `uv sync --locked` | Create `.venv/` from the locked dependencies | No; package download access is required |
| `uv add PACKAGE` / `uv add --dev PACKAGE` | Add a runtime or development dependency | No; package download access is required |
| `uv export --no-dev --no-hashes --no-emit-project -o requirements.txt` | Regenerate the deployment requirements | No |
| `uv run ruff check .` / `uv run ruff format .` | Lint and format the code | No |
| `uv run python -m scripts.demo_domain` | Demonstrate domain creation and validation | No |
| `uv run python -m scripts.demo_reviews` | Demonstrate fake-backed add/list use cases | No |
| `uv run python -m scripts.seed_review_repo` | Upsert samples using `local.settings.json` if present, otherwise shell variables | Configured development Cosmos target |
| `uv run python -m scripts.seed_review_repo test` | Require only `test.settings.json`, plus shell variables for omitted values; retrieve the test key first | Configured test Cosmos target after Part C |
| `uv run python -m scripts.seed_review_repo shell` | Upsert samples using shell variables without loading a file | Configured Cosmos target |
| `uv run func start` | Run the local Function host with the project interpreter | Cosmos required for successful requests |
| `func azure functionapp publish ...` | Deploy the API with a remote build from `requirements.txt` | Existing Function App and Azure login |

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `uv sync --locked` fails | Record the uv and Python versions, retain the lockfile and use the supported container. If `pyproject.toml` changed, run `uv lock` and commit the result. |
| `ModuleNotFoundError` for `src` or `scripts` | Run scripts from the repository root as modules (`python -m scripts.NAME`), not as file paths. |
| Missing `COSMOS_KEY` | Export the appropriate account key in the terminal starting the process; repeat in each new shell/computer/container. |
| Missing named settings file | Create `<name>.settings.json`, or deliberately select `shell` mode. |
| Wrong seed target | Read the printed endpoint/database/container; named seeding never falls back to local settings. |
| Key rejected | Confirm that the key and endpoint belong to the same account and key auth is enabled. Reacquire the test key in the separate test terminal before applying test app settings. Restart dev only in a dev-key shell with local settings targeting dev. |
| Database/container not found | Check the configured IDs and `/id` partition design against Azure verification output. |
| No functions discovered | Run `uv run python -c "import function_app"` to surface import errors, start the host with `uv run` so it uses `.venv/`, and confirm `requirements.txt` is current before deploying. |
| Local host configuration missing | Create the minimal pre-Part C `local.settings.json`, or copy and edit the template after Part C; retain `FUNCTIONS_WORKER_RUNTIME=python`. The standalone loader's optional file rule does not configure Core Tools. |
| Local host warns about storage | For this HTTP-only exercise, verify the actual GET response; POST is supplementary. Azurite is not required. Storage-trigger readiness is a separate concern. |
| Part C missing-configuration checkpoint | Keep the minimal B4 host file, unset the three target variables in the dev-key shell, start and actually GET. Expect generic 500 and a safe `dependency-construction` stage before copying the template. |
| Deployment returns 500 | Check the five setting names, whitelisted non-secret target values, runtime `python` `3.14`, test target existence and safe Function logs. A `dependency-construction` stage suggests configuration; a `use-case-execution` stage can include connectivity or stored-data failure. The public 500 intentionally omits details. Never dump secrets or the unfiltered settings response. |
| Region provisioning fails | Recheck the subscription, provider registration, inherited policy and serverless availability. |

Current command syntax is based on the official
[Azure Cosmos DB CLI reference](https://learn.microsoft.com/en-us/cli/azure/cosmosdb?view=azure-cli-latest),
[Function App CLI reference](https://learn.microsoft.com/en-us/cli/azure/functionapp?view=azure-cli-latest),
[Azure Functions Python reference](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python),
[application-settings guidance](https://learn.microsoft.com/en-us/azure/azure-functions/functions-how-to-use-azure-function-app-settings?tabs=azurecli)
and [uv documentation](https://docs.astral.sh/uv/).
