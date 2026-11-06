import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path


POLICIES_DIRECTORY = (
    Path(__file__).resolve().parents[3]
    / "knowledge"
    / "policies"
)

SECTION_PATTERN = re.compile(
    r"^## (?P<section_id>[A-Z]+-\d+) — (?P<title>.+)$",
    re.MULTILINE,
)

MAX_SECTION_CHARACTERS = 4000


class EmptyPolicyCorpus(ValueError):
    """No documents available, distinct from malformed or stale documents."""


@dataclass(frozen=True)
class PolicyChunk:
    chunk_id: str
    document_id: str
    document_title: str
    version: str
    effective_from: date
    section_id: str
    section_title: str
    text: str
    source_file: str


def read_metadata(header: str, label: str) -> str:
    match = re.search(
        rf"^{re.escape(label)}:\s*(.+)$",
        header,
        re.MULTILINE,
    )

    if match is None:
        raise ValueError(f"Metadado obrigatório ausente: {label}.")

    return match.group(1).strip()


def parse_policy(markdown: str, source_file: str) -> list[PolicyChunk]:
    markdown = markdown.lstrip("\ufeff").replace("\r\n", "\n")
    sections = list(SECTION_PATTERN.finditer(markdown))

    if not sections:
        raise ValueError(
            f"{source_file}: nenhuma seção de política foi encontrada."
        )

    header = markdown[:sections[0].start()]
    title_match = re.search(r"^# (.+)$", header, re.MULTILINE)

    if title_match is None:
        raise ValueError(f"{source_file}: título do documento ausente.")

    document_title = title_match.group(1).strip()
    document_id = read_metadata(header, "Documento")
    version = read_metadata(header, "Versão")
    effective_from = date.fromisoformat(
        read_metadata(header, "Vigência inicial")
    )

    chunks = []
    seen_sections = set()

    for index, section in enumerate(sections):
        section_id = section.group("section_id")
        section_title = section.group("title").strip()

        if section_id in seen_sections:
            raise ValueError(
                f"{source_file}: seção repetida: {section_id}."
            )

        seen_sections.add(section_id)

        end = (
            sections[index + 1].start()
            if index + 1 < len(sections)
            else len(markdown)
        )

        text = markdown[section.end():end].strip()

        if not text:
            raise ValueError(
                f"{source_file}: seção vazia: {section_id}."
            )

        if len(text) > MAX_SECTION_CHARACTERS:
            raise ValueError(
                f"{source_file}: seção {section_id} excede "
                f"{MAX_SECTION_CHARACTERS} caracteres."
            )

        identity = json.dumps(
            {
                "document_id": document_id,
                "document_title": document_title,
                "version": version,
                "effective_from": effective_from.isoformat(),
                "section_id": section_id,
                "section_title": section_title,
                "text": text,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

        chunk_id = hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()

        chunks.append(
            PolicyChunk(
                chunk_id=chunk_id,
                document_id=document_id,
                document_title=document_title,
                version=version,
                effective_from=effective_from,
                section_id=section_id,
                section_title=section_title,
                text=text,
                source_file=source_file,
            )
        )

    return chunks


def load_policy_chunks(
    directory: Path = POLICIES_DIRECTORY,
) -> list[PolicyChunk]:
    paths = sorted(directory.glob("*.md"))

    if not paths:
        raise EmptyPolicyCorpus(
            f"Nenhum documento Markdown encontrado em {directory}."
        )

    chunks = []
    seen_documents = set()

    for path in paths:
        document_chunks = parse_policy(
            path.read_text(encoding="utf-8"),
            source_file=path.name,
        )

        first = document_chunks[0]
        document_key = (first.document_id, first.version)

        if document_key in seen_documents:
            raise ValueError(
                "Documento e versão repetidos: "
                f"{first.document_id}, versão {first.version}."
            )

        seen_documents.add(document_key)
        chunks.extend(document_chunks)

    return chunks


def main() -> None:
    chunks = load_policy_chunks()

    print(f"Trechos carregados: {len(chunks)}")

    for chunk in chunks:
        print(
            f"{chunk.document_id} | "
            f"v{chunk.version} | "
            f"{chunk.section_id} | "
            f"{chunk.section_title}"
        )

    print("\nPrimeiro trecho completo:")
    print(
        json.dumps(
            asdict(chunks[0]),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
