"""Convert taxonomy rules and approved examples into knowledge documents."""

import json
from pathlib import Path

from creativebench.knowledge.models import (
    KnowledgeDocument,
    KnowledgeDocumentType,
)
from creativebench.models import AnnotationSource, AnnotationStatus, PromptRecord

DIMENSION_NAMES = {
    "genres": "文体",
    "intents": "创作意图",
    "roles": "角色方式",
    "risks": "安全风险",
}


def _load_taxonomy(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data.get("dimensions"), dict):
        raise ValueError("taxonomy 缺少 dimensions")
    return data


def _load_approved_examples(path: Path) -> list[PromptRecord]:
    records: list[PromptRecord] = []
    with path.open(encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = PromptRecord.model_validate_json(line)
            except ValueError as error:
                raise ValueError(f"样例第 {line_number} 行无效：{error}") from error
            if (
                record.annotation.status is AnnotationStatus.APPROVED
                and record.annotation.source is AnnotationSource.HUMAN
            ):
                records.append(record)
    return records


def _build_label_documents(taxonomy: dict) -> list[KnowledgeDocument]:
    documents: list[KnowledgeDocument] = []
    version = str(taxonomy.get("version", "unknown"))

    for dimension, entries in taxonomy["dimensions"].items():
        if dimension not in DIMENSION_NAMES or not isinstance(entries, list):
            raise ValueError(f"不支持的 taxonomy 维度：{dimension}")
        for entry in entries:
            confused = "、".join(entry.get("confusable_with", [])) or "无"
            content = "\n".join(
                [
                    f"标签维度：{DIMENSION_NAMES[dimension]}",
                    f"标签代码：{entry['code']}",
                    f"标签名称：{entry['name']}",
                    f"定义：{entry['definition']}",
                    f"适用条件：{entry['include_when']}",
                    f"排除条件：{entry['exclude_when']}",
                    f"易混淆标签：{confused}",
                ]
            )
            documents.append(
                KnowledgeDocument(
                    id=f"label:{dimension}:{entry['code']}",
                    content=content,
                    doc_type=KnowledgeDocumentType.LABEL_DEFINITION,
                    metadata={
                        "taxonomy_version": version,
                        "dimension": dimension,
                        "dimension_name": DIMENSION_NAMES[dimension],
                        "label_code": entry["code"],
                        "label_name": entry["name"],
                    },
                )
            )
    return documents


def _build_example_documents(
    records: list[PromptRecord],
    label_names: dict[str, str],
) -> list[KnowledgeDocument]:
    documents: list[KnowledgeDocument] = []
    for record in records:
        labels = {
            "genres": [item.value for item in record.labels.genres],
            "intents": [item.value for item in record.labels.intents],
            "roles": [item.value for item in record.labels.roles],
            "risks": [item.value for item in record.labels.risks],
        }

        def display(codes: list[str]) -> str:
            return "、".join(label_names.get(code, code) for code in codes) or "无"

        content = "\n".join(
            [
                "已审核 Prompt 标注样例",
                f"Prompt：{record.prompt_text}",
                f"样本范围：{record.scope.value}",
                f"文体标签：{display(labels['genres'])}",
                f"创作意图：{display(labels['intents'])}",
                f"角色方式：{display(labels['roles'])}",
                f"安全风险：{display(labels['risks'])}",
                f"人工判断依据：{record.annotation.rationale}",
            ]
        )
        documents.append(
            KnowledgeDocument(
                id=f"example:{record.id}",
                content=content,
                doc_type=KnowledgeDocumentType.APPROVED_EXAMPLE,
                metadata={
                    "prompt_id": record.id,
                    "scope": record.scope.value,
                    "genres": labels["genres"],
                    "intents": labels["intents"],
                    "roles": labels["roles"],
                    "risks": labels["risks"],
                    "annotation_source": record.annotation.source.value,
                },
            )
        )
    return documents


def build_knowledge_documents(
    taxonomy_path: Path,
    examples_path: Path,
) -> list[KnowledgeDocument]:
    """Build deterministic documents from the two checked-in knowledge sources."""

    taxonomy = _load_taxonomy(taxonomy_path)
    label_names = {
        entry["code"]: entry["name"]
        for entries in taxonomy["dimensions"].values()
        for entry in entries
    }
    documents = _build_label_documents(taxonomy)
    documents.extend(
        _build_example_documents(
            _load_approved_examples(examples_path),
            label_names,
        )
    )

    ids = [document.id for document in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("知识文档 ID 重复")
    return documents


def write_knowledge_jsonl(documents: list[KnowledgeDocument], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for document in documents:
            file.write(document.model_dump_json())
            file.write("\n")
