# Pdf-outliner


## Overview


**Pdf-outliner** is a Python-based solution for extracting structured outlines (headings, titles, and sections) from PDF documents and exporting them as JSON files. It uses advanced text filtering and merging logic to handle complex PDFs, including those with hidden text, tables, and artifacts. The solution is containerized with Docker for easy deployment and reproducibility.


---


## Features


- **Automatic Heading Extraction**: Detects headings using font size, position, and text analysis.
- **Table Detection**: Ignores text inside tables to avoid false headings.
- **Header/Footer Filtering**: Removes repetitive page elements.
- **Robust Merging**: Combines fragmented text spans into complete headings.
- **Debug Mode**: Detailed logging for troubleshooting extraction issues.
- **JSON Output**: Structured output for downstream processing.


---


## Folder Structure


```
Pdf-outliner/
├── Dockerfile           # Container configuration
├── LICENSE              # MIT License
├── README.md            # This documentation
├── sample_outline.json  # Example output
├── sample.pdf           # Example input PDF
├── tx.py                # Main extraction script
└── venv/                # (optional) Python virtual environment
```


---


## Usage


### 1. Local Python


Install dependencies:
```bash
pip install pymupdf
```


Run the extractor:
```bash
python tx.py
```
You will be prompted for the PDF file path and output JSON file path. If left blank, it defaults to `sample.pdf` and `sample_outline.json`.


### 2. Docker


Build the Docker image:
```bash
docker build --platform linux/amd64 -t pdf-outliner .
```


Run the container:
```bash
docker run --rm -v $(pwd):/app pdf-outliner
```
This will process `sample.pdf` and generate `sample_outline.json` in the same directory.


---


## Output Format


The output JSON will look like:


```json
{
 "title": "Document Title",
 "outline": [
   {
     "level": "H1",
     "text": "Section Heading",
     "page": 1
   },
   ...
 ]
}
```


---


## Implementation Details


- **Libraries Used**: [PyMuPDF](https://github.com/pymupdf/PyMuPDF) for PDF parsing.
- **Algorithm**:
 - Extracts all text spans with font and position metadata.
 - Merges horizontally contiguous spans on the same line.
 - Filters out invisible, suspicious, or repetitive text.
 - Assigns heading levels based on font size hierarchy.
 - Ignores text inside detected tables.
 - Outputs a clean, deduplicated outline.


---


## Performance & Constraints


- Designed for fast processing (sub-10 seconds for typical PDFs).
- No internet access required at runtime.
- Works on AMD64 CPUs (Linux).
- All dependencies are open source.


---


## License


MIT License. See [LICENSE](LICENSE) for details.


---


## Troubleshooting


- If headings are fragmented or missing, enable debug mode when prompted to see detailed extraction logs.
- For complex PDFs, check the output JSON and debug logs for clues about filtering or merging issues.


---


## Credits


Developed by Saksham Mishra and Shaman Ranjan for the Adobe India Hackathon 2025.


---






