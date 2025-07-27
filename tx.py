import fitz  # PyMuPDF
import json
import os
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional
import re

class HeaderFooterDetector:
    """Detects and filters out headers and footers that repeat across pages."""
    
    def __init__(self):
        self.potential_headers = defaultdict(list)
        self.potential_footers = defaultdict(list)
        self.confirmed_headers = set()
        self.confirmed_footers = set()
    
    def add_page_text(self, page_spans: List[Dict], page_num: int, page_height: float):
        top_threshold = page_height * 0.1
        bottom_threshold = page_height * 0.9
        
        for span in page_spans:
            y_center = (span['bbox'][1] + span['bbox'][3]) / 2
            text = span['text'].strip()
            if len(text) > 100:
                continue
                
            if y_center <= top_threshold:
                self.potential_headers[text].append(page_num)
            elif y_center >= bottom_threshold:
                self.potential_footers[text].append(page_num)
    
    def analyze_repeating_elements(self, total_pages: int):
        min_repetitions = max(2, total_pages // 3)
        
        for text, page_nums in self.potential_headers.items():
            if len(page_nums) >= min_repetitions:
                self.confirmed_headers.add(text)
        
        for text, page_nums in self.potential_footers.items():
            if len(page_nums) >= min_repetitions:
                self.confirmed_footers.add(text)
        
        footer_patterns = [
            r'page \d+',
            r'\d+ of \d+',
            r'©',
            r'copyright',
            r'version \d+',
            r'\d{4}',
        ]
        
        for text, page_nums in self.potential_footers.items():
            text_lower = text.lower()
            for pattern in footer_patterns:
                if re.search(pattern, text_lower) and len(page_nums) >= 2:
                    self.confirmed_footers.add(text)
                    break
    
    def is_header_or_footer(self, text: str) -> bool:
        text = text.strip()
        if text in self.confirmed_headers or text in self.confirmed_footers:
            return True
        for header_text in self.confirmed_headers:
            if self._is_similar_text(text, header_text):
                return True
        for footer_text in self.confirmed_footers:
            if self._is_similar_text(text, footer_text):
                return True
        
        text_lower = text.lower()
        common_patterns = [
            r'page \d+',
            r'\d+ of \d+',
            r'chapter \d+',
            r'section \d+',
            r'©.*\d{4}',
            r'copyright.*\d{4}',
            r'version \d+',
            r'^[.\s]+$',
        ]
        
        for pattern in common_patterns:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
    def _is_similar_text(self, text1: str, text2: str) -> bool:
        normalized1 = re.sub(r'\d+', 'X', text1.lower().strip())
        normalized2 = re.sub(r'\d+', 'X', text2.lower().strip())
        return normalized1 == normalized2 and len(normalized1) > 3

class SimplePDFOutlineExtractor:
    def __init__(self, debug_mode=False):
        self.header_footer_detector = HeaderFooterDetector()
        self.debug_mode = debug_mode
        self.debug_info = {
            'all_spans': [],
            'filtered_spans': [],
            'rejected_spans': []
        }
    
    def extract_builtin_toc(self, doc) -> List[Dict]:
        toc = doc.get_toc()
        outline = []
        for item in toc:
            level, title, page = item
            heading_level = f"H{min(level, 3)}"
            outline.append({"level": heading_level, "text": title.strip(), "page": page})
        return outline

    def is_text_visible_and_valid(self, span: Dict, page_text: str, page_num: int) -> Tuple[bool, str]:
        """Enhanced filtering with detailed rejection reasons."""
        text = span["text"].strip()
        rejection_reason = ""
        
        # Check if text is too small (likely hidden)
        if span.get("font_size", 0) < 4:  # Increased from 3 to 4
            rejection_reason = f"Font size too small: {span.get('font_size', 0)}"
            return False, rejection_reason
        
        # Check if text is outside reasonable page bounds
        bbox = span.get("bbox", (0, 0, 0, 0))
        if bbox[0] < 0 or bbox[1] < 0:  # Negative coordinates
            rejection_reason = f"Negative coordinates: {bbox}"
            return False, rejection_reason
        if bbox[2] - bbox[0] < 5 or bbox[3] - bbox[1] < 3:  # Too small dimensions
            rejection_reason = f"Too small dimensions: {bbox}"
            return False, rejection_reason
        
        # Check for very light/transparent text (often hidden)
        if span.get("color", 0) > 0.95:  # Very light color (close to white)
            rejection_reason = f"Very light text color: {span.get('color', 0)}"
            return False, rejection_reason
        
        # More strict validation against page text
        normalized_text = re.sub(r'\s+', ' ', text.lower().strip())
        normalized_page_text = re.sub(r'\s+', ' ', page_text.lower())
        
        # If the text is longer than 10 characters and not found in page text, it's suspicious
        if len(normalized_text) > 10:
            if normalized_text not in normalized_page_text:
                # Check if most words from the text appear
                words = [w for w in normalized_text.split() if len(w) > 2]
                if words:
                    found_words = sum(1 for word in words if word in normalized_page_text)
                    word_match_ratio = found_words / len(words)
                    if word_match_ratio < 0.7:  # Increased threshold from 0.5 to 0.7
                        rejection_reason = f"Low word match ratio: {word_match_ratio:.2f} for text: '{text[:50]}...'"
                        return False, rejection_reason
        
        # Check for suspicious patterns that indicate hidden/generated text
        suspicious_patterns = [
            (r'^[a-zA-Z]\s[a-zA-Z]\s[a-zA-Z]', "Single letters with spaces"),
            (r'^\s*[^\w\s]*\s*$', "Only special characters"),
            (r'^.{1,2}$', "Very short text (1-2 characters)"),
            (r'^[A-Z]{2,}\s*$', "All caps short text"),  # New pattern
            (r'^\d+\s*$', "Numbers only"),  # New pattern
        ]
        
        for pattern, description in suspicious_patterns:
            if re.match(pattern, text):
                rejection_reason = f"Suspicious pattern ({description}): '{text}'"
                return False, rejection_reason
        
        return True, ""

    def extract_spans_with_metadata(self, page):
        spans = []
        data = page.get_text("dict")
        page_height = page.rect.height
        page_num = page.number + 1
        
        # Get plain text for comparison
        plain_text = page.get_text()
        
        if self.debug_mode:
            print(f"\n--- DEBUG: Processing Page {page_num} ---")
            print(f"Plain text preview: {plain_text[:200]}...")
        
        for block in data.get("blocks", []):
            if "lines" not in block:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text or len(text) < 2:
                        continue
                    
                    span_data = {
                        "text": text,
                        "font_size": span.get("size", 0),
                        "page": page_num,
                        "bbox": span.get("bbox", (0, 0, 0, 0)),
                        "font": span.get("font", ""),
                        "flags": span.get("flags", 0),
                        "color": span.get("color", 0),
                        "page_height": page_height
                    }
                    
                    if self.debug_mode:
                        self.debug_info['all_spans'].append(span_data.copy())
                    
                    # Apply enhanced filtering
                    is_valid, rejection_reason = self.is_text_visible_and_valid(span_data, plain_text, page_num)
                    if is_valid:
                        spans.append(span_data)
                        if self.debug_mode:
                            self.debug_info['filtered_spans'].append(span_data.copy())
                    else:
                        if self.debug_mode:
                            span_data['rejection_reason'] = rejection_reason
                            self.debug_info['rejected_spans'].append(span_data.copy())
        
        return spans

    def normalize_text(self, text: str) -> str:
        return ' '.join(text.split())

    def is_likely_heading(self, span: Dict) -> bool:
        text = span["text"].strip()
        if len(text) < 3 or len(text) > 150 or text.count('.') > 10:
            return False
        if self.header_footer_detector.is_header_or_footer(text):
            return False
        
        # Enhanced skip patterns
        skip_patterns = [
            r'^\d+$',
            r'^[.\s]+$',
            r'www\.',
            r'http',
            r'@',
            r'^[^a-zA-Z]*$',  # Only non-alphabetic characters
            r'^\w{1,2}$',     # Very short words
            r'^[A-Z]\s*$',    # Single capital letter
        ]
        for pattern in skip_patterns:
            if re.search(pattern, text.lower()):
                return False
        return True

    def assign_levels_by_font_size(self, spans: List[Dict], title_text: str = "") -> Dict[str, List[Dict]]:
        filtered_spans = [span for span in spans if self.is_likely_heading(span)]
        if not filtered_spans:
            return {'Title': [], 'H1': [], 'H2': [], 'H3': []}

        # Remove title text from heading assignment
        if title_text:
            filtered_spans = [span for span in filtered_spans if self.normalize_text(span['text']) != title_text]

        if not filtered_spans:
            return {'Title': [], 'H1': [], 'H2': [], 'H3': []}

        font_sizes = sorted(set(span['font_size'] for span in filtered_spans), reverse=True)
        level_map = {}
        
        # Now assign H1, H2, H3 to the remaining font sizes (after excluding title)
        if len(font_sizes) > 0:
            level_map[font_sizes[0]] = 'H1'
        if len(font_sizes) > 1:
            level_map[font_sizes[1]] = 'H2'
        if len(font_sizes) > 2:
            level_map[font_sizes[2]] = 'H3'

        levels = {'Title': [], 'H1': [], 'H2': [], 'H3': []}
        seen_texts = set()
        for span in filtered_spans:
            level = level_map.get(span['font_size'])
            if not level:
                continue
            normalized_text = self.normalize_text(span['text'])
            if normalized_text and normalized_text not in seen_texts:
                seen_texts.add(normalized_text)
                span_copy = span.copy()
                span_copy['text'] = normalized_text
                levels[level].append(span_copy)
        return levels

    def group_headings_by_page(self, outline: List[Dict]) -> Dict[int, List[Dict]]:
        page_headings = defaultdict(list)
        for heading in outline:
            page_num = heading['page']
            page_headings[page_num].append(heading)
        for page_num in page_headings:
            page_headings[page_num].sort(key=lambda x: x.get('original_order', 0))
        return dict(page_headings)

    def print_debug_info(self):
        """Print detailed debug information about text extraction."""
        if not self.debug_mode:
            return
            
        print(f"\n=== DEBUG INFORMATION ===")
        print(f"Total spans found: {len(self.debug_info['all_spans'])}")
        print(f"Valid spans after filtering: {len(self.debug_info['filtered_spans'])}")
        print(f"Rejected spans: {len(self.debug_info['rejected_spans'])}")
        
        print(f"\n--- REJECTED SPANS ---")
        for span in self.debug_info['rejected_spans']:
            print(f"Page {span['page']}: '{span['text'][:50]}...' - {span.get('rejection_reason', 'Unknown')}")
        
        print(f"\n--- VALID SPANS (potential headings) ---")
        for span in self.debug_info['filtered_spans']:
            if len(span['text']) > 10 and span['font_size'] > 10:  # Likely headings
                print(f"Page {span['page']}: '{span['text']}' (Font: {span['font_size']}, Bbox: {span['bbox']})")

    def process_pdf_simple(self, input_path: str, output_path: str):
        doc = fitz.open(input_path)
        
        print(f"Processing PDF: {input_path}")
        print(f"Total pages: {len(doc)}")
        
        builtin_toc = self.extract_builtin_toc(doc)
        if builtin_toc:
            title = os.path.splitext(os.path.basename(input_path))[0]
            simple_outline = [{"level": h["level"], "text": h["text"], "page": h["page"]} for h in builtin_toc]
            result = {
                "title": title,
                "outline": simple_outline
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"Outline written to {output_path}")
            print(f"Title: {title}")
            print(f"Found {len(builtin_toc)} headings using built-in TOC")
            print("\nComplete Outline:")
            for heading in simple_outline:
                print(f"  {heading['level']}: {heading['text']} (Page {heading['page']})")
            doc.close()
            return

        all_spans = []
        for page in doc:
            spans = self.extract_spans_with_metadata(page)
            all_spans.extend(spans)
            self.header_footer_detector.add_page_text(spans, page.number + 1, page.rect.height)

        self.header_footer_detector.analyze_repeating_elements(len(doc))
        
        if self.debug_mode:
            self.print_debug_info()
        
        if not all_spans:
            print(f"No valid text found in {input_path}")
            doc.close()
            return

        for i, span in enumerate(all_spans):
            span['original_order'] = i

        # First, determine the title
        title = ""
        page1_spans = [s for s in all_spans if s['page'] == 1 and self.is_likely_heading(s)]
        if page1_spans:
            largest = max(page1_spans, key=lambda s: s['font_size'])
            title = self.normalize_text(largest['text'])
        if not title:
            title = os.path.splitext(os.path.basename(input_path))[0]

        # Then assign levels, excluding the title text
        level_groups = self.assign_levels_by_font_size(all_spans, title)
        outline = []
        for level in ['H1', 'H2', 'H3']:
            for span in level_groups[level]:
                outline.append({
                    "level": level,
                    "text": span['text'],
                    "page": span['page'],
                    "font_size": span['font_size'],
                    "original_order": span['original_order']
                })
        outline.sort(key=lambda x: x['original_order'])
        
        # Create simple outline format
        simple_outline = [{"level": h["level"], "text": h["text"], "page": h["page"]} for h in outline]

        result = {
            "title": title,
            "outline": simple_outline
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"Outline written to {output_path}")
        print(f"Title: {title}")
        print(f"Found {len(outline)} headings using font size analysis")
        print("\nComplete Outline:")
        for heading in simple_outline:
            print(f"  {heading['level']}: {heading['text']} (Page {heading['page']})")

        # Debug: Show what text was filtered out
        print(f"\nSummary:")
        print(f"- Total spans found before filtering: {len([s for s in all_spans if len(s['text'].strip()) > 2])}")
        print(f"- Headings found after filtering: {len(outline)}")
        print(f"- Pages processed: {len(doc)}")

        doc.close()

def main():
    print("=== Enhanced PDF Outline Extractor with Advanced Filtering & Debug ===")
    print("Features:")
    print("- Advanced filtering of hidden/invisible text")
    print("- Removal of PDF artifacts and suspicious text")
    print("- Cross-validation with plain text extraction")
    print("- Built-in TOC support with fallback to font analysis")
    print("- Debug mode for troubleshooting")
    print()
    
    input_file = input("Enter PDF file path (or press Enter for 'sample.pdf'): ").strip()
    if not input_file:
        input_file = 'sample.pdf'
        
    output_file = input("Enter output JSON file path (or press Enter for auto-generated): ").strip()
    if not output_file:
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = f'{base_name}_outline.json'
        
    debug_mode = input("Enable debug mode? (y/n, default n): ").strip().lower() == 'y'
    
    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found!")
        return
        
    extractor = SimplePDFOutlineExtractor(debug_mode=debug_mode)
    try:
        extractor.process_pdf_simple(input_file, output_file)
        print(f"\nSuccess! Check '{output_file}' for the results.")
    except Exception as e:
        print(f"Error processing PDF: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()