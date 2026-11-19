# Benzara E-Commerce AI Agent 

A Python pipeline for processing an e-commerce Excel workbook. It generates product content from vendor-provided facts,  researches competitor listings, creates lifestyle-image variations, and analyses the sales sheet. 


## 1. What the pipeline does

1. Reads the first two worksheets in the input Excel workbook:
   - Worksheet 1: vendor/product data
   - Worksheet 2: sales data
2. Cleans the input data and generates product content using a local Ollama model. If Ollama is unavailable or returns invalid JSON, the content agent uses a conservative extractive fallback based on supplied vendor facts.
3. Searches for competitor product candidates using Tavily.
4. Generates lifestyle image variations using Cloudflare Workers AI.
5. Analyses sales data.
6. Exports results to the output directory.


## 2. Project structure

```text
working_ai_agent/
├── agents/             # Content, competitor, image and sales agents
├── input/              # Sample input workbook
├── output/             # Generated reports (created/filled at runtime)
├── pipelines/          # Pipeline orchestration
├── processing/         # Excel reading, cleaning, validation and sales logic
├── tests/              # Unit tests
├── utils/              # Ollama client and logging
├── .env.example        
├── .gitignore
├── config.py
├── main.py
├── requirements.txt
└── README.md
```

## 3. Requirements

- Python 3.10 or newer (Python 3.11 is recommended)
- pip
- Internet access for optional Tavily research and Cloudflare image generation
- Ollama installed and running locally for LLM-based content generation; otherwise the extractive fallback is used

## 4. Install

### Windows (Command Prompt)

```cmd
git clone https://github.com/YOUR_USERNAME/working_ai_agent.git
cd working_ai_agent

python -m venv .venv
.venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

### macOS / Linux

```bash
git clone https://github.com/YOUR_USERNAME/working_ai_agent.git
cd working_ai_agent

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 5. Configure environment variables

Create a local `.env` file by copying `.env.example`.

Windows:
```cmd
copy .env.example .env
```

macOS / Linux:
```bash
cp .env.example .env
```

Edit `.env` and add credentials

| Variable | Purpose |
|---|---|
| `OLLAMA_BASE_URL` | Local Ollama server URL |
| `OLLAMA_MODEL` | Installed Ollama model name |
| `OLLAMA_TIMEOUT` | LLM request timeout in seconds |
| `TAVILY_API_KEY` | Tavily key for competitor research |
| `ENABLE_COMPETITOR_RESEARCH` | Set `true` to enable competitor research |
| `COMPETITOR_LIMIT` | Maximum vendor products sent for competitor research |
| `TAVILY_MAX_RESULTS` | Maximum search results requested per product (agent caps candidate rows) |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account ID for image generation |
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token for Workers AI |
| `CLOUDFLARE_IMAGE_MODEL` | Cloudflare image model identifier |
| `CLOUDFLARE_IMAGE_TIMEOUT` | Image request timeout in seconds |
| `ENABLE_IMAGE_GENERATION ` | Make it `true`|
| `IMAGE_LIMIT` | Maximum vendor products processed for images |
| `OUTPUT_DIR` | Default output directory |
| `LOG_LEVEL` | Logging level, e.g. `INFO` |


### Ollama setup

Install Ollama, start the Ollama service, then download the model configured in `.env`. For the default model:

```bash
ollama pull llama3:latest
ollama list
```

The model must be available locally before running if you want LLM-generated product copy. If Ollama is unavailable, the application attempts a fact-based fallback.


## 6. Run the pipeline

Using the included sample workbook:

```bash
python main.py --input "input/test_data.xlsx"
```

Specify a different output directory:

```bash
python main.py --input "input/test_data.xlsx" --output "output"
```

Use an absolute path when the workbook is elsewhere:

```cmd
python main.py --input "C:\path\to\your\test_data.xlsx" --output "output"
```

The workbook must contain at least two worksheets. The first is treated as vendor/product data and the second as sales data. Column names should follow the supplied sample workbook's structure.

## 7. Outputs

The pipeline writes the following files to the output directory:

- `product_content.xlsx` — generated product titles, descriptions, features and validation notes
- `competitor_analysis.xlsx` — competitor research candidates and available source evidence 
- `image_generation_status.xlsx` — generated, skipped or failed image status
- `sales_analysis.xlsx` — sales summary, status counts, top/low items, monthly sales and insights
- `top_items.xlsx` and `low_items.xlsx` — sales item extracts
- `final_report.xlsx` — consolidated workbook with separate product, competitor and sales sheets
- `execution_summary.json` — run counts, sheet names, errors and sales summary
- `generated_images/` — generated PNG files 


## 8. Run tests

```bash
python -m pytest -q
```


## 9.  Troubleshooting

- **Ollama unavailable:** make sure the Ollama service is running and the model named in `.env` is installed. The content agent may use its fallback if it cannot use Ollama.
- **Tavily errors:** check the API key, network access and provider quota. 
- **Cloudflare errors:** check the account ID, API token permissions, model availability and usage limits. 
- **Input workbook error:** confirm the file exists and has at least two worksheets in the expected order.


