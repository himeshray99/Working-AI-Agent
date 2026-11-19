import argparse
from pathlib import Path
from pipelines.orchestrator import run_pipeline
from config import OUTPUT_DIR

def main():
    parser = argparse.ArgumentParser(description="Local-first AI e-commerce agent")
    parser.add_argument("--input", required=True, help="Path to test_data.xlsx")
    parser.add_argument("--output", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    result = run_pipeline(Path(args.input), Path(args.output))
    print("\nPipeline finished.")
    print(f"Products: {result.get('vendor_count', 0)}")
    print(f"Content records: {result.get('content_count', 0)}")
    print(f"Competitor records: {result.get('competitor_count', 0)}")
    print(f"Images generated: {result.get('images_generated', 0)}")
    print(f"Sales lines analysed: {result.get('sales_lines', 0)}")
    print(f"Output: {Path(args.output).resolve()}")

if __name__ == "__main__":
    main()
