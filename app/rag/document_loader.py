"""
Sehat Saathi - Document Loader for RAG Knowledge Base
======================================================
Loads and chunks WHO/MoHFW health documents from the knowledge_base directory.
Supports: .txt, .pdf, .md files
"""
import logging
import os
from pathlib import Path
from typing import List

from langchain_community.document_loaders import TextLoader, PyPDFLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

logger = logging.getLogger(__name__)

# Chunk configuration tuned for medical documents
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64


def load_documents(docs_path: str) -> List[Document]:
    """
    Load all documents from the knowledge base directory.
    Supports .txt, .md, and .pdf files.

    Args:
        docs_path: Path to the directory containing knowledge base documents.

    Returns:
        List of LangChain Document objects.
    """
    docs_dir = Path(docs_path)
    if not docs_dir.exists():
        logger.warning("Knowledge base directory not found: %s", docs_path)
        docs_dir.mkdir(parents=True, exist_ok=True)
        _create_seed_documents(docs_dir)

    all_docs: List[Document] = []

    # Load text and markdown files
    for ext in ["*.txt", "*.md"]:
        for file_path in docs_dir.glob(ext):
            try:
                loader = TextLoader(str(file_path), encoding="utf-8")
                docs = loader.load()
                for doc in docs:
                    doc.metadata["source"] = file_path.name
                    doc.metadata["file_type"] = ext.lstrip("*.")
                all_docs.extend(docs)
                logger.info("Loaded %d chunks from %s", len(docs), file_path.name)
            except Exception as e:
                logger.error("Failed to load %s: %s", file_path, e)

    # Load PDF files
    for file_path in docs_dir.glob("*.pdf"):
        try:
            loader = PyPDFLoader(str(file_path))
            docs = loader.load()
            for doc in docs:
                doc.metadata["source"] = file_path.name
                doc.metadata["file_type"] = "pdf"
            all_docs.extend(docs)
            logger.info("Loaded %d pages from PDF: %s", len(docs), file_path.name)
        except Exception as e:
            logger.error("Failed to load PDF %s: %s", file_path, e)

    logger.info("Total documents loaded: %d", len(all_docs))
    return all_docs


def chunk_documents(documents: List[Document]) -> List[Document]:
    """
    Split documents into chunks suitable for embedding and retrieval.

    Args:
        documents: Raw loaded documents.

    Returns:
        Chunked list of Document objects.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    chunks = splitter.split_documents(documents)
    logger.info(
        "Chunked %d documents into %d chunks (size=%d, overlap=%d)",
        len(documents), len(chunks), CHUNK_SIZE, CHUNK_OVERLAP,
    )
    return chunks


def _create_seed_documents(docs_dir: Path) -> None:
    """
    Create minimal seed health documents if the knowledge base is empty.
    These serve as fallback content for RAG when no external docs are provided.
    """
    seed_docs = {
        "who_general_health_guidelines.txt": WHO_SEED_CONTENT,
        "india_immunization_schedule.txt": IMMUNIZATION_SEED_CONTENT,
        "preventive_care_mohfw.txt": PREVENTIVE_CARE_SEED_CONTENT,
    }
    for filename, content in seed_docs.items():
        (docs_dir / filename).write_text(content, encoding="utf-8")
    logger.info("Created %d seed documents in %s", len(seed_docs), docs_dir)


WHO_SEED_CONTENT = """
WHO General Health Guidelines - Sehat Saathi Knowledge Base
Source: World Health Organization (WHO)

FEVER MANAGEMENT:
A fever is a body temperature above 38°C (100.4°F). Most fevers in adults are caused by
viral infections and resolve on their own within 3-5 days. As per WHO guidelines:
- Low-grade fever (37.5-38.5°C): Rest, fluids, monitor temperature
- Moderate fever (38.5-39.5°C): Consult a health worker if persistent > 2 days
- High fever (>39.5°C): Seek medical care promptly
- ANY fever in children under 3 months: Seek immediate medical attention
- Fever with stiff neck, rash, or severe headache: Seek emergency care

DIARRHEA MANAGEMENT:
Diarrhea is the passage of 3 or more loose or liquid stools per day.
As per WHO guidelines:
- Oral Rehydration Solution (ORS) is the primary treatment for diarrhea
- ORS recipe: 1 liter clean water + 6 teaspoons sugar + 0.5 teaspoon salt
- Continue breastfeeding for infants during diarrhea
- Signs of severe dehydration: sunken eyes, dry mouth, not urinating, lethargy
- Bloody diarrhea requires immediate medical attention

RESPIRATORY INFECTIONS:
Common cold and upper respiratory infections are usually viral and self-limiting.
- Rest and hydration are the primary treatments
- Antibiotics are NOT effective against viral infections
- Danger signs: breathing difficulty, chest pain, high fever > 39°C, unable to drink

MALARIA PREVENTION:
As per WHO malaria guidelines:
- Sleep under insecticide-treated bed nets (ITN)
- Use indoor residual spraying (IRS) if available
- Fever with chills and shivering in malaria-endemic areas: get tested immediately
- Prompt diagnosis and treatment is critical — delay can be fatal

TUBERCULOSIS (TB):
As per WHO TB guidelines:
- TB symptoms: persistent cough > 2 weeks, blood in sputum, night sweats, weight loss
- TB is curable with a complete course of antibiotics (6 months)
- Free TB diagnosis and treatment is available at all government health centres
- Do NOT stop treatment early — incomplete treatment causes drug-resistant TB

SAFE WATER AND SANITATION:
- Drink only boiled or treated water
- Wash hands with soap before eating and after using toilet
- Safe disposal of human waste prevents cholera, typhoid, hepatitis A
""".strip()

IMMUNIZATION_SEED_CONTENT = """
India National Immunization Schedule - MoHFW
Source: Ministry of Health and Family Welfare, Government of India

UNIVERSAL IMMUNIZATION PROGRAMME (UIP):
All vaccines under UIP are FREE at government health facilities.

At Birth: BCG, OPV-0, Hepatitis B birth dose
6 Weeks: OPV-1, Pentavalent-1, Rotavirus-1, fIPV-1
10 Weeks: OPV-2, Pentavalent-2, Rotavirus-2
14 Weeks: OPV-3, Pentavalent-3, Rotavirus-3, fIPV-2
9 Months: MR-1 (Measles-Rubella), Vitamin A, JE-1 (endemic districts)
15 Months: MR-2, DPT Booster-1, OPV Booster, Vitamin A-2
5 Years: DPT Booster-2
10 Years: Td (Tetanus-diphtheria)
15-16 Years: Td Booster

PREGNANT WOMEN VACCINATION:
TT-1: Early pregnancy (as early as possible)
TT-2: 4 weeks after TT-1
TT Booster: If received 2 TT doses in a previous pregnancy within 3 years

VITAMIN A SUPPLEMENTATION:
9 months: 1 lakh IU
Every 6 months until 5 years: 2 lakh IU
Prevents childhood blindness and reduces child mortality

WHERE TO GET VACCINATED:
- Sub-centre, PHC, CHC — fixed vaccination days (Tuesday/Friday in most states)
- Anganwadi Centres
- District Hospitals
""".strip()

PREVENTIVE_CARE_SEED_CONTENT = """
Preventive Healthcare Guidelines - MoHFW India
Source: Ministry of Health and Family Welfare, National Health Mission

MATERNAL HEALTH:
Antenatal Care (ANC) — All services FREE at government facilities:
- Register at PHC as early as possible in pregnancy (ideally before 12 weeks)
- Minimum 4 ANC visits recommended (WHO recommends 8)
- Essential tests: Blood pressure, hemoglobin, blood group, urine, HIV, blood sugar
- Iron-Folic Acid (IFA) tablets: Take throughout pregnancy and 3 months post-delivery
- Institutional delivery: Give birth at a health facility for safety
- Janani Suraksha Yojana (JSY): Cash incentive for institutional delivery
- Pradhan Mantri Matru Vandana Yojana (PMMVY): ₹5000 for first child

CHILD HEALTH:
- Breastfeeding: Exclusive breastfeeding for first 6 months
- Complementary feeding: Start at 6 months while continuing breastfeeding
- Growth monitoring: Weigh baby monthly at Anganwadi for first 2 years
- Vitamin A supplementation: Every 6 months from 9 months to 5 years

REPRODUCTIVE HEALTH:
- Family planning services: FREE at all PHCs (contraceptives, counselling)
- ASHA workers provide free contraceptives at the village level

NUTRITION:
- Anaemia prevention: Take IFA tablets as prescribed
- Mid-Day Meal programme: Ensures nutrition for school children
- ICDS (Anganwadi): Supplementary nutrition for children under 6 and pregnant women

NATIONAL HEALTH PROGRAMMES:
- Ayushman Bharat PMJAY: Health insurance up to ₹5 lakh per family per year
- TB-Free India: Free diagnosis and treatment for tuberculosis
- National Vector Borne Disease Control Programme: Malaria, dengue prevention
- National Programme for Prevention of Cancer, Diabetes, CVD: Free screening
""".strip()
