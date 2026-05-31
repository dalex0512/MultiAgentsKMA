"""
Luồng điền biểu mẫu theo hội thoại — hỏi từng trường, xuất file đã điền (không sửa file gốc).
"""

import json
import logging
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from config import DOCS_ROOT, LLM_MODEL, OPENAI_API_KEY
from agents.catalog_service import load_catalog, search_forms
from agents.form_document import extract_form_text, fill_form_copy
from agents.student_profile import (
    FormField,
    StudentProfile,
    apply_profile_to_fields,
    canonical_key_for_field,
    format_profile_confirm_block,
    merge_answers_into_profile,
    parse_correction,
    resolve_correction_key,
    CANONICAL_LABELS,
)

log = logging.getLogger(__name__)

openai_client = OpenAI(api_key=OPENAI_API_KEY)

BIEU_MAU_DIR = Path(DOCS_ROOT) / "bieu_mau"
FILLED_ROOT = Path(__file__).parent.parent / "data" / "filled_forms"

FILL_START_RE = re.compile(
    r"(điền|dien|làm\s+đơn|lam\s+don|giúp\s+tôi\s+điền|giup\s+toi\s+dien|"
    r"điền\s+(thông\s+tin|giúp|ho\s+đơn)|dien\s+thong\s+tin|fill\s+form|điền\s+đơn)",
    re.I,
)
CANCEL_RE = re.compile(r"^(hủy|huỷ|thôi|bỏ\s+qua|cancel|dừng)\b", re.I)
CONFIRM_YES_RE = re.compile(
    r"^(đúng|dung|xác\s*nhận|xac\s*nhan|ok|chính\s*xác|chinh\s*xac|"
    r"tiếp\s*tục|tiep\s*tuc|đồng\s*ý|dong\s*y)\s*\.?$",
    re.I,
)
REJECT_PROFILE_RE = re.compile(
    r"(nhập\s+lại|nhap\s+lai|không\s+dùng|khong\s+dung|điền\s+lại|dien\s+lai|bỏ\s+qua)",
    re.I,
)
BATCH_REQUEST_RE = re.compile(
    r"(một\s+lượt|mot\s+luot|1\s+lượt|1\s+luot|hỏi\s+hết|hoi\s+het|"
    r"trả\s+lời\s+một\s+lượt|tra\s+loi\s+mot\s+luot|gửi\s+một\s+lượt)",
    re.I,
)
FILENAME_RE = re.compile(r"[\w\-]+\.(docx?|DOCX?)", re.I)

BATCH_HINT = (
    "\n\n_Bạn có thể trả lời **từng mục**, hoặc gõ **một lượt** để xem danh sách câu hỏi "
    "rồi gửi **mỗi dòng một câu trả lời** (theo đúng thứ tự)._"
)


def _slug(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return t

FIELD_EXTRACT_PROMPT = """\
Phân tích nội dung mẫu đơn/biểu mẫu sau và liệt kê các trường cần sinh viên TỰ ĐIỀN
(không gồm phần đã in sẵn như tên trường, quốc hiệu, chữ ký).

Trả về JSON thuần (không markdown), dạng:
{{"fields": [
  {{"key": "ho_ten", "label": "Họ và tên sinh viên", "question": "Họ và tên đầy đủ của bạn?"}},
  ...
]}}

Quy tắc:
- 5–18 trường quan trọng nhất, label khớp chữ trên mẫu (để máy điền đúng chỗ).
- key: snake_case tiếng Việt không dấu.
- Bỏ trường chỉ dành cho cơ quan ký duyệt (Giám đốc, ngày ký trống chung...).
- question: câu hỏi ngắn, lịch sự, tiếng Việt.

Tên mẫu: {display_name}
---
{text}
"""


@dataclass
class FormFillState:
    status:        str = "idle"          # idle | confirm_profile | collecting | done
    filename:      str = ""
    display_name:  str = ""
    fields:        list[FormField] = field(default_factory=list)
    answers:       dict[str, str] = field(default_factory=dict)
    current_index: int = 0
    download_id:   str = ""
    download_url:  str = ""
    output_name:   str = ""
    prefilled_from_profile: bool = False
    fields_to_ask: list[FormField] = field(default_factory=list)  # subset cần hỏi
    batch_mode: bool = False


# file_id -> absolute path (chỉ file trong FILLED_ROOT)
_download_registry: dict[str, Path] = {}


def get_filled_file_path(download_id: str) -> Path | None:
    p = _download_registry.get(download_id)
    if p and p.is_file() and FILLED_ROOT in p.resolve().parents:
        return p
    # fallback: scan session folder
    for f in FILLED_ROOT.rglob("*"):
        if f.is_file() and download_id in f.name:
            return f
    return None


def _resolve_filename(question: str, history: list[dict]) -> str | None:
    m = FILENAME_RE.search(question)
    if m:
        return m.group(0)

    blob = question.lower()
    for fname in load_catalog():
        if fname.lower() in blob:
            return fname

    forms = search_forms(question, limit=1)
    if forms and len(question.split()) >= 2:
        return forms[0]["filename"]

    for msg in reversed(history or []):
        c = msg.get("content", "")
        m = FILENAME_RE.search(c)
        if m:
            return m.group(0)
        cat = load_catalog()
        for fname, meta in cat.items():
            if fname in c or meta.get("display_name", "") in c:
                return fname
    return None


def _extract_fields_llm(text: str, display_name: str) -> list[FormField]:
    try:
        resp = openai_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{
                "role": "user",
                "content": FIELD_EXTRACT_PROMPT.format(
                    display_name=display_name,
                    text=text[:6000],
                ),
            }],
            max_tokens=1200,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        items = data.get("fields", data if isinstance(data, list) else [])
        out: list[FormField] = []
        for it in items:
            key = (it.get("key") or "").strip()
            label = (it.get("label") or "").strip()
            if not key or not label:
                continue
            out.append(FormField(
                key=key,
                label=label,
                question=(it.get("question") or f"Vui lòng cho biết {label.lower()}.").strip(),
            ))
        if out:
            return out[:18]
    except Exception as e:
        log.warning(f"[form_fill] LLM field extract failed: {e}")

    return _extract_fields_heuristic(text)


def _extract_fields_heuristic(text: str) -> list[FormField]:
    fields: list[FormField] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) > 120:
            continue
        m = re.match(r"^(.{3,60}?)[\s]*[:：]\s*[\t_…\.\s]*$", line)
        if not m:
            m = re.match(r"^(.{3,55}?):\s*$", line)
        if m:
            label = m.group(1).strip()
            if any(x in label.lower() for x in ("giám đốc", "ký tên", "tl.", "mẫu số")):
                continue
            key = re.sub(r"[^a-z0-9]+", "_", _slug(label))
            key = re.sub(r"_+", "_", key).strip("_") or f"field_{len(fields)}"
            if label in seen:
                continue
            seen.add(label)
            fields.append(FormField(
                key=key,
                label=label,
                question=f"Vui lòng cho biết {label.lower()}.",
            ))
    return fields[:16]


def _generate_filled_file(
    session_id: str,
    filename: str,
    fields: list[FormField],
    answers: dict[str, str],
) -> tuple[str, str, str]:
    template = BIEU_MAU_DIR / filename
    if not template.is_file():
        raise FileNotFoundError(filename)

    token = f"{session_id[:8]}_{uuid.uuid4().hex[:10]}"
    out_dir = FILLED_ROOT / token
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = template.stem
    ext = template.suffix
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_name = f"{stem}_da_dien_{ts}{ext}"
    output = out_dir / out_name

    labels = {f.key: f.label for f in fields}
    fill_form_copy(template, output, labels, answers)

    download_id = token
    _download_registry[download_id] = output.resolve()
    url = f"/forms/filled/{download_id}/{out_name}"
    return download_id, url, out_name


def _format_progress(state: FormFillState) -> str:
    total = len(state.fields_to_ask) or len(state.fields)
    done = sum(1 for f in (state.fields_to_ask or state.fields) if state.answers.get(f.key))
    return f"({done}/{total} trường cần điền)"


def _fields_pending(state: FormFillState) -> list[FormField]:
    if state.fields_to_ask:
        return state.fields_to_ask
    return state.fields


def _current_field(state: FormFillState) -> FormField | None:
    pending = _fields_pending(state)
    if state.current_index < len(pending):
        return pending[state.current_index]
    return None


def _remaining_fields(state: FormFillState) -> list[FormField]:
    pending = _fields_pending(state)
    return pending[state.current_index:]


def _format_batch_questions(state: FormFillState) -> str:
    remaining = _remaining_fields(state)
    lines = [
        f"**{i}/{len(remaining)}.** {f.question}"
        for i, f in enumerate(remaining, 1)
    ]
    return "\n".join(lines)


def _split_batch_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


class FormFillService:
    """Xử lý hội thoại điền đơn; gắn vào SessionState.form_fill."""

    def wants_fill(self, question: str, state: FormFillState | None) -> bool:
        if state and state.status in ("collecting", "confirm_profile"):
            return True
        return bool(FILL_START_RE.search(question))

    def handle(
        self,
        question: str,
        history: list[dict],
        session_id: str,
        state: FormFillState | None,
        *,
        last_form_filename: str = "",
        student_profile: StudentProfile | None = None,
    ) -> tuple[str, FormFillState | None, dict | None, StudentProfile | None]:
        """
        Returns (answer, new_state, extra_event).
        extra_event may include form_download_url for UI.
        """
        q = question.strip()
        state = state or FormFillState()
        profile = student_profile or StudentProfile()

        if CANCEL_RE.search(q) and state.status in ("collecting", "confirm_profile"):
            return (
                "Đã hủy quy trình điền đơn. Bạn có thể hỏi tiếp về biểu mẫu khác.",
                FormFillState(),
                None,
                profile,
            )

        if state.status == "confirm_profile":
            return self._handle_profile_confirm(q, session_id, state, profile)

        if state.status == "collecting":
            if BATCH_REQUEST_RE.search(q):
                state.batch_mode = True
                remaining = _remaining_fields(state)
                if not remaining:
                    return self._finalize(session_id, state, profile)
                return (
                    f"Vui lòng trả lời **{len(remaining)}** dòng (mỗi dòng một mục, theo thứ tự):\n\n"
                    f"{_format_batch_questions(state)}",
                    state,
                    None,
                    profile,
                )
            ans = self._collect_answer(q, session_id, state, profile)
            return (*ans, profile)

        if not FILL_START_RE.search(q):
            return "", state, None, profile

        if last_form_filename and not state.filename:
            state.filename = last_form_filename

        return self._start_fill(q, history, session_id, state, profile)

    def _start_fill(
        self,
        question: str,
        history: list[dict],
        session_id: str,
        state: FormFillState,
        profile: StudentProfile,
    ) -> tuple[str, FormFillState, dict | None, StudentProfile]:
        if state.status == "done":
            state = FormFillState(filename=state.filename)

        fname = state.filename or _resolve_filename(question, history)
        if not fname:
            forms = search_forms(question, limit=5)
            if not forms:
                return (
                    "Để điền đơn giúp bạn, vui lòng nêu rõ tên biểu mẫu "
                    "(ví dụ: *Giấy xác nhận sinh viên*) hoặc gửi lại sau khi chọn file mẫu.",
                    state,
                    None,
                    profile,
                )
            lines = "\n".join(
                f"- **{f['display_name']}** (`{f['filename']}`)"
                for f in forms
            )
            return (
                f"Bạn muốn điền biểu mẫu nào?\n\n{lines}\n\n"
                "Hãy trả lời tên đơn hoặc gõ **điền giúp tôi** kèm tên đơn.",
                state,
                None,
                profile,
            )

        catalog = load_catalog()
        meta = catalog.get(fname, {})
        display = meta.get("display_name", fname)
        path = BIEU_MAU_DIR / fname
        if not path.is_file():
            return (f"Không tìm thấy file mẫu `{fname}` trên hệ thống.", state, None, profile)

        try:
            text = extract_form_text(path)
        except Exception as e:
            log.error(f"[form_fill] extract {fname}: {e}")
            return (
                "Không đọc được nội dung mẫu đơn. Vui lòng thử biểu mẫu .docx hoặc liên hệ Phòng Đào tạo.",
                state,
                None,
                profile,
            )

        fields = _extract_fields_llm(text, display)
        if not fields:
            return (
                "Không xác định được các ô cần điền trong mẫu này. "
                "Bạn có thể tải mẫu gốc và điền tay.",
                state,
                None,
                profile,
            )

        prefill, need_ask = apply_profile_to_fields(profile, fields)
        new_state = FormFillState(
            status="collecting",
            filename=fname,
            display_name=display,
            fields=fields,
            answers=dict(prefill),
            fields_to_ask=need_ask if need_ask else list(fields),
            current_index=0,
            prefilled_from_profile=bool(prefill) and profile.forms_filled > 0,
        )

        extra = {"form_filename": fname, "form_display_name": display}

        if prefill and profile.forms_filled > 0:
            new_state.status = "confirm_profile"
            rows: list[tuple[str, str, str]] = []
            for f in fields:
                if f.key not in prefill:
                    continue
                canon = canonical_key_for_field(f)
                disp = CANONICAL_LABELS.get(canon, f.label) if canon else f.label
                rows.append((f.key, disp, prefill[f.key]))
            block = format_profile_confirm_block(rows)
            n_ask = len(need_ask)
            ask_note = (
                f"Sau khi xác nhận, tôi sẽ hỏi thêm **{n_ask}** mục chỉ có ở đơn này."
                if n_ask else "Sau khi xác nhận, tôi sẽ tạo file đơn ngay."
            )
            return (
                f"Đã chọn mẫu **{display}**.\n\n"
                "Thông tin dưới đây lấy từ **đơn bạn vừa điền trong phiên chat này** "
                "(chỉ tái sử dụng khi nhãn trường khớp với mẫu):\n\n"
                f"{block}\n\n"
                f"{ask_note}\n\n"
                "Gõ **đúng** hoặc **xác nhận** để tiếp tục. "
                "Gõ **nhập lại** để điền lại tất cả. "
                "Sửa một mục: `họ tên: Nguyễn Văn B`."
                f"{BATCH_HINT}",
                new_state,
                extra,
                profile,
            )

        pending = _fields_pending(new_state)
        if not pending:
            return self._finalize(session_id, new_state, profile)

        f0 = pending[0]
        skipped = len(fields) - len(pending)
        skip_note = (
            f" Đã điền sẵn {skipped} mục từ phiên trước."
            if skipped and profile.forms_filled > 0 else ""
        )
        if len(pending) >= 4:
            new_state.batch_mode = True
            return (
                f"Đã chọn mẫu **{display}**.{skip_note}\n\n"
                f"Cần điền {_format_progress(new_state)}. "
                f"Gõ **một lượt** để xem danh sách, rồi gửi **mỗi dòng một câu trả lời** "
                f"(theo thứ tự), hoặc trả lời từng mục.\n\n"
                f"{_format_batch_questions(new_state)}"
                f"{BATCH_HINT}",
                new_state,
                extra,
                profile,
            )

        return (
            f"Đã chọn mẫu **{display}**.{skip_note}\n\n"
            f"Tôi sẽ hỏi lần lượt {_format_progress(new_state)}. "
            f"Gõ **hủy** để dừng.\n\n"
            f"**1/{len(pending)}.** {f0.question}"
            f"{BATCH_HINT}",
            new_state,
            extra,
            profile,
        )

    def _handle_profile_confirm(
        self,
        text: str,
        session_id: str,
        state: FormFillState,
        profile: StudentProfile,
    ) -> tuple[str, FormFillState, dict | None, StudentProfile]:
        if REJECT_PROFILE_RE.search(text):
            state.answers = {}
            state.fields_to_ask = list(state.fields)
            state.current_index = 0
            state.status = "collecting"
            state.prefilled_from_profile = False
            f0 = state.fields[0]
            return (
                "Đã xóa thông tin tạm. Vui lòng điền lại từ đầu.\n\n"
                f"**1/{len(state.fields)}.** {f0.question}",
                state,
                None,
                profile,
            )

        corr = parse_correction(text)
        if corr:
            frag, val = corr
            ck = resolve_correction_key(frag)
            if ck:
                profile.values[ck] = val
            for f in state.fields:
                if ck and canonical_key_for_field(f) == ck:
                    state.answers[f.key] = val
                elif frag.lower() in f.label.lower() or _slug(frag) in _slug(f.label):
                    state.answers[f.key] = val
                    profile.label_aliases[_slug(f.label)] = val
            return self._profile_confirm_message(state, profile)

        if CONFIRM_YES_RE.search(text):
            state.status = "collecting"
            pending = _fields_pending(state)
            unanswered = [f for f in pending if not state.answers.get(f.key, "").strip()]
            state.fields_to_ask = unanswered
            state.current_index = 0
            if not unanswered:
                return self._finalize(session_id, state, profile)
            f0 = unanswered[0]
            if len(unanswered) >= 4:
                state.batch_mode = True
                return (
                    "Đã xác nhận thông tin đã lưu.\n\n"
                    f"Còn **{len(unanswered)}** mục. Gửi **một lượt** (mỗi dòng một câu trả lời) "
                    f"hoặc trả lời từng mục.\n\n"
                    f"{_format_batch_questions(state)}",
                    state,
                    None,
                    profile,
                )
            return (
                "Đã xác nhận thông tin đã lưu.\n\n"
                f"**1/{len(unanswered)}.** {f0.question}"
                f"{BATCH_HINT}",
                state,
                None,
                profile,
            )

        return (
            self._profile_confirm_message(state, profile)[0]
            + "\n\n(Vui lòng gõ **đúng**, **nhập lại**, hoặc sửa dạng `họ tên: ...`)",
            state,
            None,
            profile,
        )

    def _profile_confirm_message(
        self,
        state: FormFillState,
        profile: StudentProfile,
    ) -> tuple[str, FormFillState, dict | None, StudentProfile]:
        rows: list[tuple[str, str, str]] = []
        for f in state.fields:
            v = state.answers.get(f.key, "").strip()
            if not v:
                continue
            canon = canonical_key_for_field(f)
            disp = CANONICAL_LABELS.get(canon, f.label) if canon else f.label
            rows.append((f.key, disp, v))
        block = format_profile_confirm_block(rows)
        return (
            f"Thông tin hiện dùng cho đơn **{state.display_name}**:\n\n{block}",
            state,
            None,
            profile,
        )

    def _apply_field_answer(
        self,
        field: FormField,
        val: str,
        state: FormFillState,
        profile: StudentProfile,
    ) -> None:
        state.answers[field.key] = val
        canon = canonical_key_for_field(field)
        if canon:
            profile.values[canon] = val
        profile.label_aliases[_slug(field.label)] = val

    def _collect_batch(
        self,
        answer_text: str,
        session_id: str,
        state: FormFillState,
        profile: StudentProfile,
    ) -> tuple[str, FormFillState, dict | None]:
        lines = _split_batch_lines(answer_text)
        remaining = _remaining_fields(state)

        if not remaining:
            return self._finalize(session_id, state, profile)[:3]

        if len(lines) < 2:
            return self._collect_answer(answer_text, session_id, state, profile)

        if len(lines) != len(remaining):
            return (
                f"Bạn gửi **{len(lines)}** dòng, nhưng còn **{len(remaining)}** mục cần điền.\n\n"
                f"{_format_batch_questions(state)}\n\n"
                "Vui lòng gửi lại đúng **mỗi dòng một câu trả lời**, theo thứ tự trên.",
                state,
                None,
            )

        for field, val in zip(remaining, lines):
            if not val:
                return (
                    f"Dòng trống tại mục **{field.label}**. Vui lòng gửi lại đủ {len(remaining)} dòng.",
                    state,
                    None,
                )
            self._apply_field_answer(field, val, state, profile)

        state.current_index = len(_fields_pending(state))
        return self._finalize(session_id, state, profile)[:3]

    def _collect_answer(
        self,
        answer_text: str,
        session_id: str,
        state: FormFillState,
        profile: StudentProfile,
    ) -> tuple[str, FormFillState, dict | None]:
        lines = _split_batch_lines(answer_text)
        remaining = _remaining_fields(state)
        if len(lines) >= 2 and len(lines) == len(remaining):
            return self._collect_batch(answer_text, session_id, state, profile)

        pending = _fields_pending(state)
        idx = state.current_index
        if idx >= len(pending):
            return self._finalize(session_id, state, profile)[:3]

        field = pending[idx]
        val = answer_text.strip()
        if not val:
            return (
                f"Vui lòng nhập thông tin cho: **{field.label}**\n\n{field.question}",
                state,
                None,
            )

        self._apply_field_answer(field, val, state, profile)
        state.current_index = idx + 1

        if state.current_index >= len(pending):
            return self._finalize(session_id, state, profile)[:3]

        next_f = pending[state.current_index]
        n = state.current_index + 1
        total = len(pending)
        return (
            f"Đã ghi nhận.\n\n**{n}/{total}.** {next_f.question}",
            state,
            None,
        )

    def _finalize(
        self,
        session_id: str,
        state: FormFillState,
        profile: StudentProfile,
    ) -> tuple[str, FormFillState, dict | None, StudentProfile]:
        try:
            download_id, url, out_name = _generate_filled_file(
                session_id,
                state.filename,
                state.fields,
                state.answers,
            )
        except Exception as e:
            log.error(f"[form_fill] generate failed: {e}")
            return (
                "Đã thu thập đủ thông tin nhưng không tạo được file điền sẵn. "
                "Vui lòng thử lại sau.",
                FormFillState(status="idle"),
                None,
                profile,
            )

        merge_answers_into_profile(profile, state.fields, state.answers)

        state.status = "done"
        state.download_id = download_id
        state.download_url = url
        state.output_name = out_name

        summary = "\n".join(
            f"- {f.label}: {state.answers.get(f.key, '')}"
            for f in state.fields
            if state.answers.get(f.key)
        )

        reuse_hint = ""
        if profile.forms_filled >= 1:
            reuse_hint = (
                "\n\n_Khi điền đơn tiếp theo trong cùng phiên chat, "
                "thông tin trùng (họ tên, MSSV, …) sẽ được gợi ý lại — "
                "bạn xác nhận **đúng** trước khi tạo file._"
            )

        return (
            f"### Đã điền xong\n"
            f"Mẫu: **{state.display_name}**\n\n"
            f"**[Tải file đã điền]({url})** — bản sao, không thay đổi file gốc.\n\n"
            f"#### Tóm tắt thông tin\n"
            f"{summary}\n\n"
            "Vui lòng mở file và **đối chiếu từng mục** trước khi nộp."
            f"{reuse_hint}",
            state,
            {
                "form_download_url": url,
                "form_download_name": out_name,
                "form_download_id": download_id,
            },
            profile,
        )


form_fill_service = FormFillService()
