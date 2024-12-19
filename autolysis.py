import os
import sys
import pandas as pd
import seaborn as sns
import matplotlib
matplotlib.use('Agg')  # Use a non-interactive backend
import matplotlib.pyplot as plt
import requests
import argparse
import json
from pathlib import Path

def load_and_describe_data(filename):
    """Load the CSV and generate a summary description."""
    try:
        data = pd.read_csv(filename, encoding="utf-8")
    except UnicodeDecodeError:
        try:
            data = pd.read_csv(filename, encoding="latin1")
        except Exception as e:
            print(f"Error loading file: {e}")
            sys.exit(1)

    # Convert unsupported data types to strings for JSON serialization
    description = {
        "shape": data.shape,
        "columns": {col: str(dtype) for col, dtype in data.dtypes.items()},
        "missing_values": data.isnull().sum().to_dict(),
        "summary_statistics": data.describe(include='all').to_dict()
    }
    return data, description

def query_llm(prompt, token):
    """Send a prompt to the AI Proxy LLM and return its response."""
    url = "https://aiproxy.sanand.workers.dev/openai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    except requests.exceptions.RequestException as e:
        print(f"Error querying LLM: {e}")
        sys.exit(1)

def generate_analysis_prompt(description):
    """Generate a dynamic prompt for the LLM based on data description."""
    return f"""
    I have a dataset with the following characteristics:
    {json.dumps(description, indent=2)}

    Please provide insights, suggested analyses, and visualizations to explore the data. Include code suggestions if needed.
    """

def plot_correlation_matrix(data, filename):
    """Plot and save a correlation matrix heatmap."""
    corr_matrix = data.corr(numeric_only=True)
    plt.figure(figsize=(10, 8))
    sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", fmt=".2f", cbar=True)
    plt.title("Correlation Matrix")
    plt.savefig(filename)
    plt.close()

def plot_missing_values(data, filename):
    """Plot and save missing values as a heatmap."""
    plt.figure(figsize=(10, 6))
    sns.heatmap(data.isnull(), cbar=False, cmap="viridis")
    plt.title("Missing Values Heatmap")
    plt.savefig(filename)
    plt.close()

def generate_readme(data_summary, analysis_results, images, token):
    """Generate a README.md file using the LLM."""
    prompt = f"""
    Summarize the following dataset and analysis into a report:

    Dataset Description:
    {json.dumps(data_summary, indent=2)}

    Analysis Results:
    {analysis_results}

    The report should describe:
    1. The data received.
    2. The analysis conducted.
    3. Insights discovered.
    4. Implications or suggestions based on the findings.

    Include the following images in the report:
    {images}
    """
    return query_llm(prompt, token)


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Automated Data Analysis and Storytelling")
    parser.add_argument("filename", help="Input CSV filename")
    args = parser.parse_args()

    # Load environment variable for API token
    token = os.environ["AIPROXY_TOKEN"]
    if not token:
        print("Error: AIPROXY_TOKEN environment variable is not set.")
        sys.exit(1)


    # Load and describe data
    print("Loading and describing the dataset...")
    data, description = load_and_describe_data(args.filename)
    print("Dataset loaded successfully.")

    # Query LLM for analysis suggestions
    print("Querying the LLM for analysis suggestions...")
    analysis_prompt = generate_analysis_prompt(description)
    analysis_results = query_llm(analysis_prompt, token)
    print("Analysis suggestions received.")

    # Generate visualizations
    print("Creating visualizations...")
    dataset_name = Path(args.filename).stem
    output_dir = Path(dataset_name)
    output_dir.mkdir(exist_ok=True)

    correlation_img = output_dir / "correlation_matrix.png"
    missing_values_img = output_dir / "missing_values.png"

    if not data.empty:
        plot_correlation_matrix(data, correlation_img)
        plot_missing_values(data, missing_values_img)

    # Generate README.md
    print("Generating README.md...")
    images = f"- Correlation Matrix: {correlation_img}\n- Missing Values Heatmap: {missing_values_img}"
    readme_content = generate_readme(description, analysis_results, images, token)
    with open(output_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)

    print(f"README.md and visualizations created successfully in {output_dir}.")


main()
