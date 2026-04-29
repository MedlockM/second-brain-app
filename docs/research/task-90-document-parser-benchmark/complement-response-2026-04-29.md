# Complement Response: Cost Optimization Strategies for Document Parsing

This complement addresses the owner's request for strategies to optimize parsing costs based on document type (DOCX, PPTX, native PDF, scanned PDF, PNG scans, etc.) to avoid routing all files to expensive OCR-capable parsers when not necessary.

## Executive Summary

**Key insight**: Cost optimization strategies differ significantly by tool architecture:

1. **Native multi-tier APIs** (AWS Textract, Azure Document Intelligence, Unstructured.io) offer explicit API-level routing between cheap (text extraction) and expensive (OCR + layout analysis) tiers
2. **Unified parsers** (LlamaParse, Marker, Docling) handle routing internally with opaque or minimal cost differentiation
3. **Lightweight local tools** (PyMuPDF) require manual pre-screening via heuristic-based text detection

**Recommended approach**: Implement a **two-stage routing architecture** with pre-processing detection + tiered parser selection.

---

## Cost Optimization Strategies by Solution

### Strategy 1: Explicit API Tier Selection (AWS Textract, Azure, Unstructured.io)

These platforms provide separate API endpoints or strategy parameters with clear cost tiers. The application controls which features to invoke.

#### AWS Textract

**Three pricing tiers**:

| Tier | API | Cost per 1,000 pages | Use case |
|------|-----|----------------------|----------|
| Detect Document Text | `DetectDocumentText` | $1.50 | Text-only extraction (no OCR emphasis, simple PDFs) |
| Analyze - Tables | `AnalyzeDocument` (Tables) | $15 | OCR + table extraction |
| Analyze - Forms | `AnalyzeDocument` (Forms) | $50 | OCR + form field extraction |

**Routing strategy**:

1. **File type detection**: Use MIME type and file extension to categorize uploads
   - DOCX, PPTX, XLSX → Not supported by Textract (requires conversion or different parser)
   - Native PDFs → Attempt `DetectDocumentText` first
   - Image files (PNG, JPG, TIFF) → Requires OCR, route to `AnalyzeDocument`

2. **PDF content detection**: Before invoking Textract, use PyMuPDF to detect if PDF contains extractable text
   ```python
   import fitz  # PyMuPDF
   
   def requires_ocr(pdf_path):
       doc = fitz.open(pdf_path)
       page = doc[0]
       text = page.get_text()
       # Heuristic: if first page has < 50 chars, likely scanned
       return len(text.strip()) < 50
   ```
   - If `requires_ocr() == False` → `DetectDocumentText` ($1.50/1k pages)
   - If `requires_ocr() == True` → `AnalyzeDocument` with Tables ($15/1k pages)

3. **Feature-based routing**: Only invoke `AnalyzeDocument` with Forms ($50/1k) if user explicitly requests form field extraction

**Cost savings example** (1,000 mixed documents/month):
- Without routing: All docs → `AnalyzeDocument Forms` = $100/month
- With routing: 70% native PDFs → `DetectDocumentText` ($1.05) + 30% scanned → `AnalyzeDocument Tables` ($4.50) = **$5.55/month (94% savings)**

**Limitations**:
- No native Office format support (DOCX, XLSX, PPTX must be converted to PDF first)
- Requires pre-processing step to detect document type

**Source**: https://aws.amazon.com/textract/pricing

---

#### Azure Document Intelligence

**Two primary tiers**:

| Tier | API | Cost per 1,000 pages | Use case |
|------|-----|----------------------|----------|
| Read API | `prebuilt-read` | $1.50-3 | Basic OCR, text extraction |
| Layout API | `prebuilt-layout` | $10-30 | Advanced layout analysis, tables, structure |

**Routing strategy**:

1. **Format-based routing**:
   - Office files (DOCX, XLSX, PPTX, HTML) → Always `Read API` (native support in v4.0)
   - Simple PDFs (text-only, no tables) → `Read API`
   - Complex PDFs (tables, forms, multi-column layouts) → `Layout API`

2. **Progressive fallback**:
   - Start with `Read API` for all PDFs
   - If downstream LLM pipeline reports low-quality extraction (e.g., table data corrupted) → Retry with `Layout API`
   - Cache the "complexity classification" per document hash to avoid future retries

3. **Searchable PDF output**: Both APIs support generating searchable PDFs with embedded text (no extra cost in v4.0), useful for archival + search

**Cost savings example** (1,000 mixed documents/month):
- Without routing: All docs → `Layout API` = $30/month
- With routing: 60% simple docs → `Read API` ($1.80) + 40% complex → `Layout API` ($12) = **$13.80/month (54% savings)**

**Advantages**:
- Native Office format support (no conversion needed)
- Clear API separation for cost control
- Searchable PDF output included

**Source**: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/

---

#### Unstructured.io

**Four strategy modes** (open source + SaaS):

| Strategy | Processing method | Cost (compute/time) | Use case |
|----------|------------------|---------------------|----------|
| `fast` | pdfminer text extraction | Lowest | Native PDFs with extractable text |
| `ocr_only` | Tesseract OCR → text partition | Medium | Scanned PDFs, images |
| `hi_res` | detectron2_onnx layout analysis | Highest | Complex layouts, table extraction |
| `auto` | Intelligent selection based on content | Variable | General-purpose (analyzes doc first) |

**Routing strategy**:

1. **File type heuristics**:
   - DOCX, PPTX, XLSX → `fast` (native text extraction via python-docx, python-pptx, openpyxl)
   - Native PDFs → `fast` (unless tables required → `hi_res`)
   - PNG/JPG/TIFF files → `ocr_only` or `hi_res` (depending on layout complexity)
   - Scanned PDFs → `ocr_only` or `hi_res`

2. **Table detection requirement**:
   - If user upload scenario requires table extraction (e.g., spreadsheets, financial reports) → `hi_res` (only strategy that extracts tables from PDFs per documentation)
   - Otherwise → `fast` or `ocr_only`

3. **Auto-strategy delegation**: Use `strategy="auto"` as default; the library automatically selects:
   - `hi_res` if tables needed
   - `fast` if text extractable
   - `ocr_only` if image-based
   
   **Trade-off**: Less control but avoids manual decision logic

**Cost model for SaaS** ($0.03/page flat rate):
- Cost differentiation comes from **processing time**, not pricing tier
- `fast` processes faster → lower infrastructure cost per document
- `hi_res` processes slower → higher infrastructure cost per document

**Cost savings approach**: Not directly monetary (flat per-page rate), but **latency optimization**:
- Route simple docs to `fast` → 2-5 seconds per doc
- Route complex docs to `hi_res` → 10-30 seconds per doc
- Reduces user wait time and infrastructure load

**Advantages**:
- Clear strategy parameter for explicit control
- `auto` mode for hands-off optimization
- Self-hosted option (open source) allows per-instance cost control

**Source**: https://docs.unstructured.io/open-source/core-functionality/partitioning

---

### Strategy 2: Unified Parser with Internal Optimization (LlamaParse, Marker, Docling)

These tools present a single interface but may consume different resources internally based on document complexity.

#### LlamaParse

**Credit system** (1,000 credits = $1.25):

- **Basic parsing**: "as low as 1 credit/page"
- **Advanced parsing**: Higher credits for "layout-aware agentic parsing with LLMs or VLMs"

**Routing strategy**:

1. **Tier parameter**: LlamaParse offers a `tier` parameter (e.g., `tier="agentic"`) to control processing intensity
   - Lower tiers → Fewer credits per page
   - Higher tiers → More credits per page, better accuracy

2. **Document pre-classification**: Implement a lightweight classifier upstream:
   ```python
   def classify_document_complexity(file_path):
       # Check file type
       if file_path.endswith(('.docx', '.pptx', '.xlsx')):
           return 'simple'  # Office docs have native text
       
       # For PDFs, check text extractability
       if is_text_based_pdf(file_path):
           return 'simple'
       else:
           return 'complex'  # Requires OCR
   
   # Route to appropriate tier
   if complexity == 'simple':
       result = parser.load_data(file, tier="basic")
   else:
       result = parser.load_data(file, tier="agentic")
   ```

3. **Test-then-configure approach**: LlamaParse docs recommend testing new document types with different settings before configuring pipelines
   - Run a sample batch through multiple tiers
   - Evaluate accuracy vs. cost
   - Hard-code optimal tier per document class

**Limitations**:
- Credit consumption not transparent (no published credit costs per document type)
- Requires experimentation to determine optimal tier

**Cost savings estimate** (assuming 2x credit difference between tiers):
- Without routing: All docs at high tier = 2 credits/page × 2,000 pages = 4,000 credits = $5/month
- With routing: 70% low tier (1 credit) + 30% high tier (2 credits) = 2,600 credits = **$3.25/month (35% savings)**

**Source**: https://llamaindex.ai/pricing

---

#### Marker (self-hosted)

**Processing modes**:

- **Default**: Heuristic detection of text vs. image content, applies OCR only when needed
- **Force OCR**: `--force_ocr` flag forces OCR on entire document
- **Strip existing OCR**: `--strip_existing_ocr` removes embedded OCR and re-processes

**Routing strategy**:

1. **Let Marker auto-detect** (default behavior):
   - Marker internally checks if PDF has extractable text
   - If yes → Direct text extraction
   - If no → OCR via built-in models

2. **No explicit cost differentiation**: Marker is self-hosted, so compute cost is amortized across all documents
   - Text extraction is faster (~0.1s/page)
   - OCR processing is slower (~3-5s/page with GPU)

3. **Throughput optimization**: Use batch processing with multi-GPU workers to maximize throughput
   ```bash
   # Process 1,000 docs with 4 GPUs, 15 workers
   NUM_DEVICES=4 NUM_WORKERS=15 marker_chunk_convert input_dir output_dir
   ```
   - Achieves ~122 pages/second on H100 GPU
   - No need to pre-sort documents by complexity

**Cost model**: Compute cost is **constant per page** (GPU hours), not per feature
- Optimization focus: **Minimize total processing time** via parallelization, not document routing

**When to route**:
- If operating in mixed CPU/GPU environment:
  - Route simple PDFs → CPU workers (free compute)
  - Route scanned PDFs → GPU workers (paid compute)

**Source**: https://github.com/VikParuchuri/marker

---

#### Docling (self-hosted)

**Similar to Marker**: Internal detection, no explicit routing API

- Supports "extensive OCR for scanned PDFs and images"
- Uses VLM (Visual Language Model) for complex documents
- No documented strategy parameters like Unstructured.io

**Routing strategy**: Same as Marker (auto-detection or batch all documents)

**Source**: https://github.com/DS4SD/docling

---

### Strategy 3: Lightweight Pre-Screening + Fallback (PyMuPDF + Premium Parser)

Use PyMuPDF as a **routing oracle** before invoking expensive parsers.

#### Architecture

```
User Upload
    ↓
PyMuPDF Text Extraction Attempt
    ↓
┌───────────────┴────────────────┐
│                                │
Text Detected (>50 chars)     No Text / Minimal Text
Simple Document                Scanned Document
│                                │
↓                                ↓
PyMuPDF Markdown Output      LlamaParse / Textract OCR
(Zero API cost)              (API cost: $0.001-0.05/page)
│                                │
└────────────────┬───────────────┘
                 ↓
         LLM Pipeline
```

#### Implementation Pattern

```python
import fitz  # PyMuPDF

def route_document(file_path):
    """
    Pre-screen document to determine optimal parser.
    """
    # Step 1: Determine file type
    file_type = get_file_type(file_path)
    
    if file_type in ['docx', 'pptx', 'xlsx']:
        # Office docs: always use premium parser (native support)
        return 'premium_parser'
    
    if file_type == 'pdf':
        # Step 2: Check if PDF has extractable text
        doc = fitz.open(file_path)
        
        # Sample first 3 pages
        sample_pages = min(3, len(doc))
        total_chars = 0
        
        for i in range(sample_pages):
            page = doc[i]
            text = page.get_text()
            total_chars += len(text.strip())
        
        avg_chars_per_page = total_chars / sample_pages
        
        # Heuristic thresholds
        if avg_chars_per_page > 100:
            # Native PDF with text
            return 'pymupdf'
        elif avg_chars_per_page > 20:
            # Sparse text, may need OCR
            return 'premium_parser_light'  # Use cheaper tier
        else:
            # Scanned PDF, definitely needs OCR
            return 'premium_parser_ocr'
    
    if file_type in ['png', 'jpg', 'tiff']:
        # Image files: always need OCR
        return 'premium_parser_ocr'
    
    # Default fallback
    return 'premium_parser'

def parse_with_routing(file_path):
    parser_type = route_document(file_path)
    
    if parser_type == 'pymupdf':
        # Free local processing
        doc = fitz.open(file_path)
        markdown = ""
        for page in doc:
            markdown += page.get_text("markdown")
        return markdown
    
    elif parser_type == 'premium_parser_light':
        # Use cheaper API tier (e.g., AWS Textract DetectDocumentText)
        return call_textract_basic(file_path)
    
    elif parser_type == 'premium_parser_ocr':
        # Use full OCR tier (e.g., LlamaParse, Textract AnalyzeDocument)
        return call_llamaparse(file_path)
    
    else:
        # Default to premium parser
        return call_premium_parser(file_path)
```

#### Cost Savings Analysis

**Scenario**: 1,000 documents/month, mixed types

| Document Type | % of Total | Without Routing | With Routing | Savings |
|--------------|-----------|----------------|-------------|---------|
| Native PDFs (simple) | 50% | LlamaParse: $1.25 | PyMuPDF: $0 | $1.25 |
| Scanned PDFs | 30% | LlamaParse: $0.75 | LlamaParse: $0.75 | $0 |
| Office docs | 20% | LlamaParse: $0.50 | LlamaParse: $0.50 | $0 |
| **Total** | **100%** | **$2.50** | **$1.25** | **50% savings** |

**Assumptions**:
- LlamaParse: 2 credits/page avg, 2 pages/doc avg = 4 credits/doc = $0.005/doc
- PyMuPDF: $0/doc (open source, local compute negligible)

---

## Recommended Multi-Tier Architecture

Based on the research, here's the optimal architecture for media-summarizer:

### Tier 0: File Type Classification (Upstream Guard)

```python
def classify_upload(file_path):
    extension = get_extension(file_path)
    
    # Office documents: always extractable text
    if extension in ['.docx', '.pptx', '.xlsx']:
        return 'office', 'simple'
    
    # Images: always require OCR
    if extension in ['.png', '.jpg', '.jpeg', '.tiff', '.heif']:
        return 'image', 'complex'
    
    # PDFs: require content inspection
    if extension == '.pdf':
        complexity = detect_pdf_complexity(file_path)
        return 'pdf', complexity
    
    # HTML: extractable text
    if extension in ['.html', '.htm']:
        return 'html', 'simple'
    
    return 'unknown', 'complex'  # Default to complex
```

### Tier 1: Complexity Detection (PDF-Specific)

```python
def detect_pdf_complexity(pdf_path):
    """
    Determine if PDF is text-based or scanned.
    Returns: 'simple' | 'moderate' | 'complex'
    """
    doc = fitz.open(pdf_path)
    
    # Sample analysis
    sample_size = min(3, len(doc))
    text_density = []
    has_images = False
    
    for i in range(sample_size):
        page = doc[i]
        
        # Check text content
        text = page.get_text()
        char_count = len(text.strip())
        
        # Check for embedded images
        images = page.get_images()
        if images:
            has_images = True
        
        # Calculate text density (chars per pixel area)
        page_area = page.rect.width * page.rect.height
        density = char_count / page_area if page_area > 0 else 0
        text_density.append(density)
    
    avg_density = sum(text_density) / len(text_density)
    
    # Classification thresholds (tunable)
    if avg_density > 0.01:  # Dense text
        return 'simple'
    elif avg_density > 0.001:  # Sparse text
        return 'moderate'
    else:  # Minimal/no text
        return 'complex'
```

### Tier 2: Parser Routing

```python
def route_to_parser(file_type, complexity):
    """
    Select optimal parser based on document characteristics.
    """
    routing_table = {
        ('office', 'simple'): 'llamaparse_basic',
        ('pdf', 'simple'): 'pymupdf',
        ('pdf', 'moderate'): 'llamaparse_basic',
        ('pdf', 'complex'): 'llamaparse_advanced',
        ('image', 'complex'): 'llamaparse_advanced',
        ('html', 'simple'): 'local_html_parser',
    }
    
    key = (file_type, complexity)
    return routing_table.get(key, 'llamaparse_advanced')  # Default fallback
```

### Cost Impact Projection

**Baseline** (no routing, all docs → LlamaParse advanced):
- 1,000 docs/month × 2 pages/doc × 2 credits/page = 4,000 credits = **$5/month**

**With routing**:
- 30% simple PDFs → PyMuPDF (0 credits) = 0 credits
- 20% office docs → LlamaParse basic (1 credit/page) = 400 credits
- 30% moderate PDFs → LlamaParse basic (1 credit/page) = 600 credits
- 20% scanned/complex → LlamaParse advanced (2 credits/page) = 800 credits
- **Total**: 1,800 credits = **$2.25/month (55% savings)**

---

## Tool-Specific Optimization Strategies Summary

| Tool | Native Routing Support | Strategy | Cost Optimization Potential |
|------|----------------------|----------|---------------------------|
| **AWS Textract** | ✅ Yes (API tiers) | Use `DetectDocumentText` for native PDFs, `AnalyzeDocument` for scans | **90%+ savings** (10x price difference) |
| **Azure Doc Intelligence** | ✅ Yes (API tiers) | Use `Read API` for simple docs, `Layout API` for complex layouts | **50%+ savings** (3-10x price difference) |
| **Unstructured.io** | ✅ Yes (strategy param) | Use `strategy="fast"` for native PDFs, `"hi_res"` for scanned + tables | **Latency optimization** (not direct cost, flat $0.03/page) |
| **LlamaParse** | ⚠️ Partial (tier param) | Use lower tier for simple docs, test to determine optimal tier | **30-50% savings** (requires experimentation) |
| **Marker (self-host)** | ❌ No (auto-detect) | Let Marker handle internally, optimize via batch parallelization | **Throughput optimization** (not cost per doc) |
| **Docling (self-host)** | ❌ No (auto-detect) | Same as Marker, auto-detection internal | **Throughput optimization** (not cost per doc) |
| **PyMuPDF** | ✅ Yes (pre-screening) | Use as routing oracle, extract simple PDFs locally | **100% savings on simple PDFs** (zero API cost) |

---

## Recommendations for media-summarizer

### Phase 1: Immediate Cost Optimization (Current LlamaParse + PyMuPDF Stack)

1. **Implement PyMuPDF pre-screening**:
   - Before sending PDFs to LlamaParse, attempt text extraction with PyMuPDF
   - If successful (>100 chars/page threshold), use PyMuPDF output
   - If failed, send to LlamaParse
   - **Expected savings**: 30-50% of LlamaParse credits

2. **Add file type routing**:
   - DOCX, PPTX, XLSX → LlamaParse (native support)
   - Simple PDFs → PyMuPDF first, fallback to LlamaParse if poor quality
   - Scanned PDFs, images → LlamaParse directly
   - **Expected savings**: Additional 20-30% via reduced LlamaParse calls

3. **Cache complexity classifications**:
   - Store document hash + complexity classification in database
   - Reuse classification if same document uploaded again (e.g., user re-uploads)

### Phase 2: Advanced Optimization (If LlamaParse Costs Exceed Budget)

4. **Evaluate Unstructured.io as alternative**:
   - At $0.03/page flat rate vs. LlamaParse variable credits
   - If volume exceeds 10k docs/month, Unstructured.io may be cheaper
   - Benefit: Explicit `strategy` parameter for fine-grained control

5. **Consider Azure Document Intelligence**:
   - If Office format support (DOCX, XLSX, PPTX) is critical
   - Use `Read API` ($1.50-3/1k pages) for 70%+ of documents
   - Reserve `Layout API` ($10-30/1k pages) for complex layouts only
   - **Expected savings**: 50-70% vs. uniform high-tier pricing

6. **Hybrid multi-parser architecture**:
   - Simple docs → PyMuPDF (free)
   - Office docs → Azure Read API ($0.003/page)
   - Complex scans → LlamaParse (variable, ~$0.002-0.005/page)
   - **Expected savings**: 60-80% via best-tool-per-doc routing

### Phase 3: Scale Optimization (If Volume Exceeds 50k Docs/Month)

7. **Evaluate self-hosted Marker or Docling**:
   - At $200/month GPU compute, breakeven vs. SaaS at ~40k pages/month
   - No per-page cost, only infrastructure
   - Benefit: Full control over processing pipeline

8. **Implement document complexity ML classifier**:
   - Train lightweight image classifier to predict "requires OCR" probability
   - Features: file size, embedded fonts count, image layer detection
   - Route based on confidence score (e.g., >0.8 → skip OCR)

---

## Actionable Next Steps

1. **Immediate (Week 1)**:
   - Add PyMuPDF pre-screening to current pipeline
   - Measure credit consumption before/after on 100-doc sample
   - Validate PyMuPDF output quality vs. LlamaParse for simple PDFs

2. **Short-term (Month 1)**:
   - Implement file type + complexity routing table
   - A/B test output quality: PyMuPDF vs. LlamaParse on native PDFs
   - Define quality threshold (e.g., "if downstream LLM summary scores <0.7, retry with LlamaParse")

3. **Long-term (Quarter 1)**:
   - Monitor cost per document type in analytics dashboard
   - If LlamaParse exceeds $50/month, evaluate Azure or Unstructured.io migration
   - If volume hits 10k docs/month, run cost-benefit analysis for self-hosted Marker

---

## Additional Considerations

### Quality vs. Cost Trade-offs

- **PyMuPDF**: Fast + free, but basic table extraction (may lose structure)
- **LlamaParse basic tier**: Good for simple docs, may miss complex table relationships
- **LlamaParse advanced tier**: Best quality, highest cost

**Mitigation**: Implement **progressive retry logic**:
1. Start with cheapest parser (PyMuPDF or basic tier)
2. If downstream LLM detects poor quality (e.g., flashcard generation fails due to corrupted table data), automatically retry with higher tier
3. Cache retry decisions to avoid future misclassifications

### Handling Edge Cases

1. **PDF with both text and scanned images**:
   - PyMuPDF will extract text layers but miss scanned images
   - Solution: If text extraction succeeds but page count < expected, route to OCR parser

2. **Password-protected PDFs**:
   - All parsers require unlocked PDFs
   - Solution: Reject at upload validation step, prompt user to remove password

3. **Very large files (>100 pages)**:
   - Some parsers (PyMuPDF) handle efficiently
   - Others (LlamaParse) may consume excessive credits
   - Solution: Implement page-based cost estimate before processing, warn user if cost exceeds threshold

### Performance Monitoring

Track these metrics per parser:

```python
{
    "parser": "pymupdf|llamaparse_basic|llamaparse_advanced",
    "document_type": "pdf_simple|pdf_complex|office|image",
    "pages": 10,
    "processing_time_ms": 1234,
    "api_cost_usd": 0.005,
    "quality_score": 0.85,  # From LLM evaluation
    "retry_count": 0
}
```

Use this data to:
- Refine routing heuristics (e.g., adjust text density threshold)
- Identify cost anomalies (e.g., unexpected high credit consumption)
- A/B test parser alternatives

---

## Sources

1. **AWS Textract pricing**: https://aws.amazon.com/textract/pricing
2. **Azure Document Intelligence**: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/
3. **Unstructured.io partition strategies**: https://docs.unstructured.io/open-source/core-functionality/partitioning
4. **LlamaParse pricing**: https://llamaindex.ai/pricing
5. **Marker documentation**: https://github.com/VikParuchuri/marker
6. **Docling documentation**: https://github.com/DS4SD/docling
7. **PyMuPDF documentation**: https://github.com/pymupdf/PyMuPDF
8. **pypdf text extraction**: https://pypdf.readthedocs.io/en/stable/user/extract-text.html
