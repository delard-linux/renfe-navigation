# Renfe Navigation API

FastAPI service exposing a GET endpoint that uses Playwright to fetch available trains from Renfe given origin, destination, and outbound/return dates.

## Project Structure

```
renfe-navigation/
├── app/
│   ├── main.py                        # FastAPI app and endpoints
│   ├── parser.py                      # Independent HTML parser
│   ├── renfe.py                       # Compatibility wrapper (re-exports)
│   ├── renfe_common.py                # Shared utilities and models
│   ├── search_trains_service.py       # Direct API search service
│   ├── search_trains_flow_service.py  # Homepage flow service
│   └── resources/
│       └── estaciones.json            # Station catalog
├── tests/
│   ├── conftest.py                      # pytest configuration
│   ├── test_fixed_parser_train_lists.py # HTML parser tests
│   ├── test_api_endpoint.py             # API endpoint tests
│   └── fixtures/
│       ├── train_list_sample.html       # Test data
│       └── renfe_response_sample.html   # Sample HTML response
├── tests_playwright/
│   ├── conftest.py          # Configuration for debug mode (headless=False)
│   └── test_search_flow.py  # E2E flow tests
├── pytest.ini               # pytest configuration
├── pyproject.toml           # Poetry configuration
├── poetry.lock              # Dependency lock file
├── Makefile                 # Useful commands
└── README.md
```

## Setup

```bash
# 1) Install Poetry at user level (if you don't have it)
curl -sSL https://install.python-poetry.org | python3 -

# Verify that poetry is available (in user PATH)
poetry --version

# (Optional) View project virtual environment path if already created
# This helps confirm which interpreter Make/Poetry will use
poetry env info --path

# 2) Install project dependencies with Poetry
poetry install

# 3) Install Playwright browsers within project environment
poetry run playwright install
```

### System dependencies for Playwright (if an error appears)

If you see a message like:

```
╔══════════════════════════════════════════════════════╗
║ Host system is missing dependencies to run browsers. ║
║ Please install them with the following command:      ║
║                                                      ║
║     sudo playwright install-deps                     ║
```

Run the system dependency installation command pointing to the project environment's Python (adjust the path to your `.venv` if it differs):

```bash
sudo ~/renfe-navigation/.venv/bin/python3 -m playwright install-deps
```

Notes:
- This step is for the operating system and normally requires `sudo`. It's not integrated into the Makefile to avoid accidentally running commands with elevated privileges.
- After installing system dependencies, make sure to reinstall browsers if necessary: `poetry run playwright install`.

### Playwright installation verification

To verify that Playwright has downloaded the browsers, check the user cache:

```bash
ls -la ~/.cache/ms-playwright || true
```

You should see folders with downloaded browsers.

## Architecture

The project follows a modular architecture with separated services:

### Core Modules

- **`app/main.py`**: FastAPI application with REST endpoints
- **`app/parser.py`**: Independent HTML parser for train data
- **`app/renfe_common.py`**: Shared utilities, models, and helper functions
  - `TrainModel`, `FareOption`: Pydantic models
  - Station catalog functions
  - Response saving and parsing utilities
- **`app/search_trains_service.py`**: Direct API search service
  - Sends POST request to Renfe's internal API
  - Faster, no UI interaction
- **`app/search_trains_flow_service.py`**: Complete homepage flow service
  - Navigates from Renfe homepage
  - Handles cookies, form filling, date picker
  - Full UI interaction via Playwright
- **`app/renfe.py`**: Compatibility wrapper
  - Re-exports all services for backward compatibility
  - Legacy code continues to work

### Service Selection

**Use `/trains` (search_trains_service) when:**
- You need fast results
- Direct API access is sufficient
- No UI interaction required

**Use `/trains-flow` (search_trains_flow_service) when:**
- Testing the complete user flow
- Verifying UI elements work
- Debugging form interactions

## Quick Usage

```bash
# Start the server (always using Make for simplicity)
make run
```

```bash
# Run all tests (unit and E2E)
make test
```

```bash
# Playwright tests visible (non-headless browser)
make test-playwright
```

## Endpoints

### GET /trains
Performs a direct train search using Renfe's internal API.

- GET /trains?origin=OURENSE&destination=MADRID&date_out=2025-10-14&date_return=2025-11-05&adults=1

Dates must be in ISO format YYYY-MM-DD.

### GET /trains-flow
Performs the complete flow from Renfe's homepage, filling the form and clicking search.

- GET /trains-flow?origin=OURENSE&destination=MADRID&date_out=2025-10-14&date_return=2025-11-05&adults=1

Dates must be in ISO format YYYY-MM-DD.

**Note:** This endpoint automatically saves the HTML response in the `responses/` directory with the format `[AAMMDD_HH24MISS]_[Status code]_buscarTrenFlow.do.log`.

### Response Structure

Each train includes:
- `train_id`: Unique train identifier
- `service_type`: Service type (AVE, AVLO, ALVIA, etc.)
- `departure_time`, `arrival_time`: Schedules
- `duration`: Journey duration
- `price_from`: Minimum price from
- `fares[]`: Array of available fares with:
  - `name`: Fare name (Básico, Elige, Prémium, etc.)
  - `price`: Fare price
  - `code`: Fare code
  - `tp_enlace`: Link code
  - `features[]`: List of included features
- `badges[]`: Special labels (Lowest price, Fastest)
- `accessible`: H seat available
- `eco_friendly`: Zero emissions

### Response Logging

Each search automatically saves Renfe's HTML response in the `responses/` directory with the format:

```
[AAMMDD_HHMMSS]_[StatusCode]_buscarTren.do.log
```

Example: `251007_143022_200_buscarTren.do.log`

## Testing with curl

The scraper uses Renfe's direct API: `https://venta.renfe.com/vol/buscarTren.do?Idioma=es&Pais=ES`

Stations are automatically resolved from `app/resources/estaciones.json`.

### Example 1: Ourense -> Madrid (round trip)
```bash
curl -s "http://localhost:8000/trains?origin=OURENSE&destination=MADRID&date_out=2025-10-14&date_return=2025-11-05&adults=1" | jq
```

### Example 2: Barcelona -> Madrid (one way)
```bash
curl -s "http://localhost:8000/trains?origin=BARCELONA&destination=MADRID&date_out=2025-10-20&adults=2" | jq
```

### Example 3: Madrid -> Sevilla (round trip)
```bash
curl -s "http://localhost:8000/trains?origin=MADRID&destination=SEVILLA&date_out=2025-11-01&date_return=2025-11-03&adults=1" | jq
```

### Example 4: Valencia -> Alicante (one way, 4 passengers)
```bash
curl -s "http://localhost:8000/trains?origin=VALENCIA&destination=ALICANTE&date_out=2025-10-25&adults=4" | jq
```

### Example 5: Bilbao -> San Sebastián (round trip)
```bash
curl -s "http://localhost:8000/trains?origin=BILBAO&destination=SAN%20SEBASTIAN&date_out=2025-11-10&date_return=2025-11-12&adults=2" | jq
```

**Note:** You can use station names as they appear in `estaciones.json`. The system will automatically search for matches.

### Examples with /trains-flow

These examples use the complete flow from Renfe's homepage:

#### Example 6: Ourense -> Madrid (round trip) using complete flow
```bash
curl -s "http://localhost:8000/trains-flow?origin=OURENSE&destination=MADRID&date_out=2025-10-14&date_return=2025-11-05&adults=1"
```

#### Example 7: Barcelona -> Madrid (one way) using complete flow
```bash
curl -s "http://localhost:8000/trains-flow?origin=BARCELONA&destination=MADRID&date_out=2025-10-20&adults=2"
```

**Note:** The `/trains-flow` endpoints generate response files in `responses/` with the format `[AAMMDD_HH24MISS]_[Status code]_buscarTrenFlow.do.log`.

## Testing

The project uses **pytest** for unit and integration tests.

### Unit and Integration Tests (tests/)

These tests verify parsing logic and endpoints without interacting with a real browser.

#### Run all tests:

```bash
pytest
# or
make test
```

#### With more detail:

```bash
pytest -v
# or
make test-verbose
```

#### Run specific tests:

```bash
# Only parser tests
pytest tests/test_fixed_parser_train_lists.py -v

# A specific test
pytest tests/test_fixed_parser_train_lists.py::test_parse_train_list_html_extracts_fares -v

# Tests with detailed output (useful for debugging)
pytest tests/test_fixed_parser_train_lists.py::test_parse_train_list_html_display_results -v -s
```

### End-to-End Tests with Playwright (tests_playwright/)

**These tests run the browser VISIBLE by default** so you can see how the real flow executes.

#### Run all E2E tests:

```bash
make test-playwright
# or
pytest tests_playwright/ -v -s
```

#### Run a single E2E test:

```bash
make test-playwright-one
# or
pytest tests_playwright/test_search_flow.py::test_search_trains_flow_ourense_madrid -v -s
```

#### Playwright configuration:

Playwright tests can be configured with environment variables:

```bash
# Run in headless mode (no visible browser)
PLAYWRIGHT_HEADLESS=true pytest tests_playwright/ -v

# Slow down actions for better visualization (milliseconds)
PLAYWRIGHT_SLOWMO=1000 pytest tests_playwright/ -v -s

# Record test videos
PLAYWRIGHT_VIDEO=true pytest tests_playwright/ -v

# Change viewport
PLAYWRIGHT_WIDTH=1920 PLAYWRIGHT_HEIGHT=1080 pytest tests_playwright/ -v -s
```

### Test Coverage

The project uses `pytest-cov` to analyze code coverage. There are several ways to view coverage:

```bash
# View coverage in terminal with uncovered lines
make test-cov

# Generate interactive HTML report
make test-html  # Opens htmlcov/index.html

# Re-run only failed tests
make test-failed
```

#### Current coverage status:

| Module | Coverage | Description |
|--------|----------|-------------|
| `app/parser.py` | 90% | Independent and tested HTML parser |
| `app/main.py` | 87% | FastAPI endpoint with integration tests |
| `app/renfe.py` | 24% | Playwright scraper (needs more tests) |

Tests focus on:
- ✓ Correct HTML parsing of trains
- ✓ Train and fare data structure
- ✓ FastAPI endpoint integration
- ✓ Required parameter validation

### Available tests

#### `test_fixed_parser_train_lists.py`

Tests for Renfe HTML parser (`app/parser.py`) with fixed fixture data:

- ✓ Correctly parses train structure
- ✓ Extracts basic information (schedules, duration, prices)
- ✓ Extracts multiple fares with features
- ✓ Extracts badges and labels
- ✓ Identifies accessibility and eco features
- ✓ Recognizes different service types
- ✓ Correctly serializes to JSON

Tests use real data fixtures in `tests/fixtures/train_list_sample.html`

#### `test_api_endpoint.py`

Tests for FastAPI endpoint (`/trains`) using real response fixtures:

- ✓ Verifies endpoint response structure
- ✓ Validates number of parsed trains
- ✓ Checks train data structure
- ✓ Tests endpoint with return date
- ✓ Validates required parameters

Tests use mocks and fixtures in `tests/fixtures/renfe_response_sample.html`

### Independent parser

The parser (`app/parser.py`) with the `parse_train_list_html()` function is independent and can be used to parse Renfe HTML without needing Playwright. It's agnostic of whether it's outbound or return.

### Cleanup

To clean temporary files and caches:

```bash
make clean  # Cleans __pycache__, .pytest_cache, htmlcov, etc.
```