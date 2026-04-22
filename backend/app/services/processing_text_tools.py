import re


def split_long_sentences(
    text: str,
    threshold: int,
    *,
    clause_joiner: str = "。",
    min_clauses: int = 3,
) -> str:
    chunks = re.split(r"([。！？!?])", text)
    rebuilt: list[str] = []
    for index in range(0, len(chunks), 2):
        sentence = chunks[index].strip()
        punct = chunks[index + 1] if index + 1 < len(chunks) else ""
        comma_count = sentence.count("，")
        if len(sentence) > threshold and comma_count >= min_clauses:
            parts = [part.strip() for part in sentence.split("，") if part.strip()]
            if len(parts) <= min_clauses:
                rebuilt.append(sentence + punct)
                continue
            current: list[str] = []
            current_len = 0
            groups: list[str] = []
            for part in parts:
                if current and current_len + len(part) > threshold:
                    groups.append("，".join(current))
                    current = [part]
                    current_len = len(part)
                else:
                    current.append(part)
                    current_len += len(part)
            if current:
                groups.append("，".join(current))
            rebuilt.append(clause_joiner.join(groups) + punct)
        else:
            rebuilt.append(sentence + punct)
    return "".join(rebuilt).strip()


def split_sentences(text: str) -> list[tuple[str, str]]:
    chunks = re.split(r"([。！？!?；;])", str(text or ""))
    sentences: list[tuple[str, str]] = []
    for index in range(0, len(chunks), 2):
        sentence = chunks[index].strip()
        punct = chunks[index + 1] if index + 1 < len(chunks) else ""
        if sentence:
            sentences.append((sentence, punct or "。"))
    return sentences


def merge_short_sentences(text: str, *, max_sentence_length: int = 22, merge_limit: int = 4) -> str:
    sentences = split_sentences(text)
    if len(sentences) < 3:
        return str(text or "").strip()

    rebuilt: list[str] = []
    buffer: list[str] = []
    merged_groups = 0
    for sentence, punct in sentences:
        if len(sentence) <= max_sentence_length and merged_groups < merge_limit:
            buffer.append(sentence)
            if len("".join(buffer)) >= max_sentence_length + 8:
                rebuilt.append("，".join(buffer) + punct)
                buffer = []
                merged_groups += 1
            continue

        if buffer:
            rebuilt.append("，".join(buffer) + "。")
            buffer = []
            merged_groups += 1
        rebuilt.append(sentence + punct)

    if buffer:
        rebuilt.append("，".join(buffer) + "。")
    return "".join(rebuilt).strip()


def soften_connective_prefixes(
    text: str,
    *,
    prefixes: tuple[str, ...] = ("同时，", "此外，", "进一步看，", "在此基础上，", "由此可见，"),
    keep_first: int = 1,
) -> str:
    sentences = split_sentences(text)
    if len(sentences) < 2:
        return str(text or "").strip()

    rebuilt: list[str] = []
    prefix_hits = 0
    for sentence, punct in sentences:
        current = sentence
        for prefix in prefixes:
            if current.startswith(prefix):
                prefix_hits += 1
                if prefix_hits > keep_first:
                    current = current[len(prefix) :].lstrip()
                break
        rebuilt.append(current + punct)
    return "".join(rebuilt).strip()


def rewrite_parallel_targets(
    text: str,
    *,
    max_changes: int = 1,
    prefer_compact: bool = False,
) -> str:
    output = str(text or "")
    patterns = (
        (
            r"需要([^。！？；;，,]{3,20})，并保持([^。！？；;，,]{3,22})",
            (r"既要\1，也要保持\2", r"一方面要\1，另一方面还要保持\2"),
        ),
        (
            r"需要([^。！？；;，,]{3,20})，同时兼顾([^。！？；;，,]{3,22})",
            (r"既要\1，也要兼顾\2", r"在推进\1的同时，还要兼顾\2"),
        ),
        (
            r"将([^。！？；;，,]{2,16})与([^。！？；;，,]{2,16})结合，能够([^。！？；;，,]{3,24})，并形成([^。！？；;，,]{3,24})",
            (
                r"通过把\1与\2衔接起来，不仅可以\3，也有助于形成\4",
                r"\1与\2衔接后，既能\3，也能推动\4形成",
            ),
        ),
        (
            r"通过([^。！？；;，,]{2,18})，能够([^。！？；;，,]{3,24})，并([^。！？；;，,]{3,24})",
            (
                r"借助\1，既可以\2，也能\3",
                r"在\1的基础上，既能\2，也能\3",
            ),
        ),
    )
    changes = 0
    for pattern, replacements in patterns:
        if changes >= max_changes:
            break
        ordered = replacements if not prefer_compact else tuple(reversed(replacements))
        for replacement in ordered:
            next_output, count = re.subn(pattern, replacement, output, count=1)
            if count and next_output != output:
                output = next_output
                changes += 1
                break
    return output


def rewrite_causal_chains(
    text: str,
    *,
    max_changes: int = 1,
    prefer_compact: bool = False,
) -> str:
    output = str(text or "")
    patterns = (
        (
            r"研究表明，([^。！？；;，,]{4,22})，因此([^。！？；;，,]{4,24})",
            (r"研究结果显示，由于\1，因而\2", r"从研究结果看，\1，这也使得\2"),
        ),
        (
            r"由于([^。！？；;，,]{4,22})，([^。！？；;，,]{4,24})",
            (r"在\1的背景下，\2", r"\1这一条件，使得\2"),
        ),
        (
            r"为了([^。！？；;，,]{3,18})，需要([^。！？；;，,]{3,20})",
            (r"若要\1，就需要\2", r"围绕\1这一目标，需要\2"),
        ),
        (
            r"围绕([^。！？；;，,]{3,18})展开分析",
            (r"分析围绕\1展开", r"相关分析围绕\1展开"),
        ),
    )
    changes = 0
    for pattern, replacements in patterns:
        if changes >= max_changes:
            break
        ordered = replacements if not prefer_compact else tuple(reversed(replacements))
        for replacement in ordered:
            next_output, count = re.subn(pattern, replacement, output, count=1)
            if count and next_output != output:
                output = next_output
                changes += 1
                break
    return output


def rewrite_academic_frames(
    text: str,
    *,
    max_changes: int = 2,
    prefer_compact: bool = False,
) -> str:
    output = str(text or "")
    patterns = (
        (
            r"本文以([^。！？；;，,]{3,24})为([^。！？；;，,]{2,18})，围绕([^。！？；;，,]{4,28})，探讨([^。！？；;，,]{4,32})",
            (
                r"围绕\4，本文把\1作为\2，并围绕\3展开讨论",
                r"本文将\1视为\2，把\4作为重点，并围绕\3展开分析",
            ),
        ),
        (
            r"本文立足([^。！？；;，,]{3,24})，系统探讨([^。！？；;，,]{4,30})，梳理([^。！？；;，,]{4,28})，以期([^。！？；;，,]{3,24})",
            (
                r"立足\1，文章把\2作为主线，并对\3进行梳理，希望\4",
                r"以\1为立足点，本文围绕\2展开论述，同时梳理\3，以便\4",
            ),
        ),
        (
            r"采用([^。！？；;，,]{3,20})与([^。！？；;，,]{3,20})，发现在([^。！？；;，,]{3,24})下，([^。！？；;，,]{4,30})",
            (
                r"通过\1与\2相结合可以看到，在\3下，\4",
                r"借助\1和\2的结合，研究发现，在\3下，\4",
            ),
        ),
        (
            r"从([^。！？；;，,]{4,28})三个维度，探讨([^。！？；;，,]{4,32})",
            (
                r"针对\2，可从\1三个维度展开讨论",
                r"\2的讨论可以从\1三个维度展开",
            ),
        ),
        (
            r"以([^。！？；;，,]{3,22})为切入，系统论证([^。！？；;，,]{4,30})，梳理([^。！？；;，,]{4,28})，并([^。！？；;，,]{4,28})",
            (
                r"以\1作为切入点后，文章系统论证\2，同时梳理\3，并\4",
                r"围绕\1这一切入点，本文对\2进行系统论证，同时梳理\3，并\4",
            ),
        ),
    )
    changes = 0
    for pattern, replacements in patterns:
        if changes >= max_changes:
            break
        ordered = replacements if not prefer_compact else tuple(reversed(replacements))
        for replacement in ordered:
            next_output, count = re.subn(pattern, replacement, output, count=1)
            if count and next_output != output:
                output = next_output
                changes += 1
                break
    return output


def reorder_comma_clauses(
    text: str,
    *,
    max_changes: int = 1,
    min_clause_len: int = 4,
) -> str:
    content = str(text or "")
    sentences = split_sentences(content)
    if not sentences:
        return content.strip()
    rebuilt: list[str] = []
    changes = 0
    for sentence, punct in sentences:
        current = sentence
        if changes < max_changes and current.count("，") >= 2:
            parts = [part.strip() for part in current.split("，") if part.strip()]
            if len(parts) >= 3 and len(parts[0]) >= min_clause_len and len(parts[1]) >= min_clause_len:
                reordered = [parts[1], parts[0], *parts[2:]]
                candidate = "，".join(reordered)
                if candidate != current:
                    current = candidate
                    changes += 1
        rebuilt.append(f"{current}{punct}")
    return "".join(rebuilt).strip()
