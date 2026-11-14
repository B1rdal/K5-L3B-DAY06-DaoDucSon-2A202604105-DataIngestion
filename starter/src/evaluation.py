"""Strict, reproducible evidence retrieval metrics; no inferred human labels."""
from collections import defaultdict
from typing import Any
import unicodedata


def normalized(text: str) -> str:
    """Ignore Unicode composition and layout whitespace, retaining wording."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def gold_records(question: dict[str, Any]) -> list[dict[str, Any]]:
    records = [{key: question[key] for key in
                ("gold_source_id", "gold_page", "evidence_quote")}]
    records.extend(question.get("alternative_evidence", []))
    return records


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    """A hit requires one chunk containing a complete registered evidence quote.

    The chunk must have the gold document ID and an accepted physical PDF page.
    Alternatives are explicit gold records, never guessed from retrieval scores.
    This strict automatic metric can miss paraphrased-but-equivalent evidence;
    manual grounding/coherence assessments remain separate.
    """
    evidence = gold_records(question)
    assessed = []
    for rank, hit in enumerate(hits[:3], start=1):
        matches = []
        for index, gold in enumerate(evidence):
            pages = gold["gold_page"]
            pages = pages if isinstance(pages, list) else [pages]
            quote = normalized(gold["evidence_quote"])
            if (quote and hit["document_id"] == gold["gold_source_id"]
                    and hit["page"] in pages and quote in normalized(hit["text"])):
                matches.append(index)
        assessed.append({**hit, "rank": rank, "evidence_hit": bool(matches),
                         "matching_gold_records": matches})
    return {
        "question_id": question["id"], "split": question["split"],
        "question": question["question"], "expected_answer": question["expected_answer"],
        "gold_evidence": evidence, "requested_filter": question.get("filter") or {},
        "hits": assessed, "hit_at_1": bool(assessed and assessed[0]["evidence_hit"]),
        "evidence_hit_at_3": any(hit["evidence_hit"] for hit in assessed),
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Report numerators and denominators separately for each strategy/split."""
    groups = defaultdict(list)
    seen = set()
    for trace in traces:
        identity = (trace["strategy"], trace["split"], trace["question_id"])
        if identity in seen:
            raise ValueError(f"Duplicate evaluation trace: {identity}")
        seen.add(identity)
        groups[identity[:2]].append(trace)
    metrics = []
    for (strategy, split), items in sorted(groups.items()):
        count = len(items)
        hit1 = sum(item["hit_at_1"] for item in items)
        hit3 = sum(item["evidence_hit_at_3"] for item in items)
        filtered = [item for item in items if item["requested_filter"]]
        compliant = sum(bool(item["hits"]) and all(
            all(hit.get(key, hit["metadata"].get(key)) == value
                for key, value in item["requested_filter"].items())
            for hit in item["hits"]
        ) for item in filtered)
        metrics.append({
            "strategy": strategy, "split": split, "questions": count,
            "hit_at_1_count": hit1, "hit_at_1": hit1 / count,
            "evidence_hit_at_3_count": hit3, "evidence_hit_at_3": hit3 / count,
            "filter_questions": len(filtered), "filter_compliant_count": compliant,
            "filter_compliance": compliant / len(filtered) if filtered else None,
        })
    return {"metrics": metrics,
            "metric_definition": "Correct document/page plus complete gold quote in one chunk; Unicode NFC and whitespace normalized. No semantic-equivalence adjudication."}
