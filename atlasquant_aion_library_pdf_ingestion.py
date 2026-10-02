"""AION Library PDF Ingestion V1.

Local-only PDF adapter for AION Library Foundation + Index. It extracts text with
pypdf, computes deterministic checksums, applies bounded chunking and transparent
keyword classification. It never calls OCR, network, external models or providers.
"""
from __future__ import annotations

from io import BytesIO
from hashlib import sha256
from typing import Any, Mapping, Sequence
import re
import unicodedata

from pypdf import PdfReader

from atlasquant_aion_library_foundation import ingest_document, review_document
from atlasquant_aion_library_index import empty_library_index, index_document

SCHEMA="ATLASQUANT_AION_LIBRARY_PDF_INGESTION_V1"
MAX_PDF_BYTES=25*1024*1024
MAX_PAGES=500
MAX_EXTRACTED_CHARS=1_500_000
CHUNK_CHARS=1400
CHUNK_OVERLAP=180
MAX_CHUNKS=1200

TOPIC_RULES={
    "MACROECONOMIA":("inflacao","cpi","pce","payroll","nfp","desemprego","pib","gdp","juros","fed","fomc","bce","ecb"),
    "FOREX":("forex","dxy","usd","eur","gbp","jpy","cad","aud","nzd","chf","cambio","moeda"),
    "ICT_SMC":("fvg","order block","bos","breaker","liquidity","liquidez","ict","smc","amd","judas swing"),
    "RISCO":("risco","drawdown","stop loss","stop","exposicao","alavancagem","volatilidade"),
    "NEGOCIOS":("cliente","crm","vendas","marketing","receita","margem","funil","negocio"),
    "INVESTIMENTOS":("renda fixa","acoes","fii","fundo imobiliario","portfolio","carteira","dividendos"),
}
def _clean(value:Any,limit:int=5000)->str:
    return " ".join(str(value or "").replace("\x00","").split())[:limit]

def _fold(value:Any)->str:
    raw=unicodedata.normalize("NFKD",str(value or ""))
    return "".join(ch for ch in raw if not unicodedata.combining(ch)).casefold()

def _sha256(data:bytes)->str:
    return sha256(data).hexdigest()

def classify_topics(text:Any)->dict[str,Any]:
    folded=_fold(text)
    scores=[]
    for topic,terms in TOPIC_RULES.items():
        matched=[term for term in terms if term in folded]
        if matched:
            scores.append({"topic":topic,"score":len(matched),"matched_terms":matched})
    scores.sort(key=lambda x:(-x["score"],x["topic"]))
    return {
        "schema":SCHEMA,
        "topics":scores,
        "primary_topic":scores[0]["topic"] if scores else "UNCLASSIFIED",
        "classification_method":"DETERMINISTIC_KEYWORD_RULES",
        "model_called":False,
        "provider_called":False,
        "executes_action":False,
    }

def chunk_text(text:Any,*,chunk_chars:int=CHUNK_CHARS,overlap:int=CHUNK_OVERLAP)->list[str]:
    normalized=_clean(text,MAX_EXTRACTED_CHARS)
    if not normalized:
        return []
    size=max(400,min(int(chunk_chars),4000))
    ov=max(0,min(int(overlap),size//3))
    chunks=[]
    start=0
    while start<len(normalized) and len(chunks)<MAX_CHUNKS:
        end=min(len(normalized),start+size)
        piece=normalized[start:end].strip()
        if piece:
            chunks.append(piece)
        if end>=len(normalized):
            break
        start=max(start+1,end-ov)
    return chunks
def extract_pdf(pdf_bytes:bytes)->dict[str,Any]:
    if not isinstance(pdf_bytes,(bytes,bytearray)):
        return {"schema":SCHEMA,"status":"BLOCKED","blockers":["PDF_BYTES_REQUIRED"],"pages":[]}
    raw=bytes(pdf_bytes)
    if not raw:
        return {"schema":SCHEMA,"status":"BLOCKED","blockers":["PDF_EMPTY"],"pages":[]}
    if len(raw)>MAX_PDF_BYTES:
        return {"schema":SCHEMA,"status":"BLOCKED","blockers":["PDF_TOO_LARGE"],"pages":[]}
    if not raw.startswith(b"%PDF-"):
        return {"schema":SCHEMA,"status":"BLOCKED","blockers":["PDF_SIGNATURE_INVALID"],"pages":[]}
    try:
        reader=PdfReader(BytesIO(raw),strict=False)
    except Exception as exc:
        return {
            "schema":SCHEMA,"status":"BLOCKED","blockers":["PDF_PARSE_ERROR"],
            "error_type":type(exc).__name__,"pages":[],
        }
    if len(reader.pages)>MAX_PAGES:
        return {"schema":SCHEMA,"status":"BLOCKED","blockers":["PDF_PAGE_LIMIT"],"pages":[]}
    pages=[]
    total=0
    failures=0
    for idx,page in enumerate(reader.pages,start=1):
        try:
            text=_clean(page.extract_text() or "",MAX_EXTRACTED_CHARS-total)
        except Exception:
            text=""
            failures+=1
        if text:
            total+=len(text)
            pages.append({"page":idx,"text":text})
        if total>=MAX_EXTRACTED_CHARS:
            break
    status="EXTRACTED" if pages else "REVIEW_REQUIRED"
    blockers=[] if pages else ["NO_EXTRACTABLE_TEXT"]
    return {
        "schema":SCHEMA,
        "status":status,
        "blockers":blockers,
        "page_count":len(reader.pages),
        "extracted_pages":len(pages),
        "extraction_failures":failures,
        "pages":pages,
        "checksum":"sha256:"+_sha256(raw),
        "bytes":len(raw),
        "ocr_executed":False,
        "provider_called":False,
        "web_research_executed":False,
        "executes_action":False,
    }
def stage_pdf_document(
    *,
    pdf_bytes:bytes,
    filename:Any,
    tenant_id:Any,
    workspace_id:Any,
    trusted_context:Mapping[str,Any]|None,
    title:Any="",
    author:Any="",
    publisher:Any="",
    published_at:Any="",
    document_version:Any="1",
    rights_status:Any="UNKNOWN",
)->dict[str,Any]:
    ctx=dict(trusted_context or {})
    tenant=_clean(tenant_id,120)
    workspace=_clean(workspace_id,120)
    blockers=[]
    if tenant!=_clean(ctx.get("tenant_id"),120) or workspace!=_clean(ctx.get("workspace_id"),120):
        blockers.append("SCOPE_MISMATCH")
    name=_clean(filename,260)
    if not name.lower().endswith(".pdf"):
        blockers.append("PDF_EXTENSION_REQUIRED")
    extraction=extract_pdf(pdf_bytes)
    if extraction.get("status")!="EXTRACTED":
        blockers.extend(extraction.get("blockers") or [])
    if blockers:
        return {
            "schema":SCHEMA,"status":"BLOCKED","blockers":list(dict.fromkeys(blockers)),
            "extraction":extraction,"external_persisted":False,"memory_promoted":False,
            "execution_authorized":False,"external_action_executed":False,
        }
    full_text="\\n".join(str(x.get("text") or "") for x in extraction["pages"])
    topics=classify_topics(full_text)
    summary=_clean(full_text,4000)
    staged=ingest_document(
        tenant_id=tenant,
        workspace_id=workspace,
        title=_clean(title,400) or name,
        source_reference="upload://"+name,
        checksum=extraction["checksum"],
        source_type="INTERNAL_DOCUMENT",
        author=author,
        publisher=publisher,
        published_at=published_at,
        document_version=document_version,
        rights_status=rights_status,
        summary=summary,
        evidence_refs=[extraction["checksum"]],
    )
    record=dict(staged.get("record") or {})
    record["pdf_metadata"]={
        "filename":name,
        "bytes":extraction["bytes"],
        "page_count":extraction["page_count"],
        "extracted_pages":extraction["extracted_pages"],
        "ocr_executed":False,
    }
    record["topic_classification"]=topics
    return {
        "schema":SCHEMA,
        "status":staged.get("status"),
        "record":record,
        "extraction":{k:v for k,v in extraction.items() if k!="pages"},
        "passages":chunk_text(full_text),
        "topic_classification":topics,
        "requires_review":True,
        "requires_checkpoint_save":staged.get("requires_checkpoint_save") is True,
        "external_persisted":False,
        "memory_promoted":False,
        "execution_authorized":False,
        "external_action_executed":False,
    }
def review_and_index_pdf(
    *,
    staged:Mapping[str,Any],
    trusted_context:Mapping[str,Any]|None,
    evidence_refs:Sequence[Any]|None=None,
    index:Mapping[str,Any]|None=None,
)->dict[str,Any]:
    """Explicit admin review followed by local index staging."""
    item=dict(staged or {})
    row=dict(item.get("record") or {})
    if item.get("status")!="STAGED" or not row:
        return {
            "schema":SCHEMA,"status":"BLOCKED","blockers":["PDF_NOT_STAGED"],
            "external_persisted":False,"memory_promoted":False,
            "execution_authorized":False,
        }
    refs=list(evidence_refs or row.get("evidence_refs") or [])
    reviewed=review_document(
        row,
        trusted_context=trusted_context,
        decision="VALIDATED",
        evidence_refs=refs,
        reason="PDF_REVIEW_APPROVED",
    )
    if reviewed.get("status")!="STAGED":
        return {
            "schema":SCHEMA,"status":"BLOCKED",
            "blockers":reviewed.get("blockers") or ["DOCUMENT_REVIEW_BLOCKED"],
            "review":reviewed,
            "external_persisted":False,"memory_promoted":False,
            "execution_authorized":False,
        }
    indexed=index_document(
        index or empty_library_index(),
        reviewed["record"],
        passages=item.get("passages") or [],
        trusted_context=trusted_context,
    )
    return {
        "schema":SCHEMA,
        "status":"INDEXED" if indexed.get("status")=="INDEXED" else "BLOCKED",
        "reviewed_record":reviewed.get("record"),
        "index":indexed.get("index"),
        "indexed_passages":indexed.get("indexed_passages",0),
        "topic_classification":item.get("topic_classification") or {},
        "external_persisted":False,
        "memory_promoted":False,
        "execution_authorized":False,
        "external_action_executed":False,
    }

__all__=[
    "SCHEMA","MAX_PDF_BYTES","MAX_PAGES","MAX_EXTRACTED_CHARS","TOPIC_RULES",
    "classify_topics","chunk_text","extract_pdf","stage_pdf_document","review_and_index_pdf",
]
