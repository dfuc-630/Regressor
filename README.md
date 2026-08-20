# Regressor

> Một phương pháp xây dựng **long-term memory** và **documentation-as-database** cho AI coding agent — để mỗi task sau luôn đứng trên vai mọi task trước.

---

## Mục lục

1. [Regressor là gì?](#regressor-là-gì)
2. [Triết lý nền: Docs-as-Database](#triết-lý-nền-docs-as-database)
3. [Kiến trúc tổng quan](#kiến-trúc-tổng-quan)
4. [Tech Stack](#tech-stack)
5. [Thứ tự tra cứu & Nguồn sự thật](#thứ-tự-tra-cứu--nguồn-sự-thật)
6. [Quy trình vận hành (3 Phase)](#quy-trình-vận-hành-3-phase)
7. [Hệ thống Docs-as-Database chi tiết](#hệ-thống-docs-as-database-chi-tiết)
8. [Python Compiler Pipeline](#python-compiler-pipeline)
9. [Skill `docs-create`](#skill-docs-create)
10. [GitNexus — Code Intelligence](#gitnexus--code-intelligence)
11. [Serena — Semantic Code Toolkit](#serena--semantic-code-toolkit)
12. [Superpowers — Kỷ luật quy trình](#superpowers--kỷ-luật-quy-trình)
13. [MCP Servers kết nối](#mcp-servers-kết-nối)
14. [Cây thư mục tham chiếu](#cây-thư-mục-tham-chiếu)
15. [Nguyên tắc vàng](#nguyên-tắc-vàng)
16. [Cheat sheet lệnh](#cheat-sheet-lệnh)

---

## Regressor là gì?

Regressor là phương pháp xây dựng một **hệ tri thức sâu (long-term memory)** kết hợp với một **hệ thống docs chặt chẽ**, gộp lại nhiều giải pháp hiệu quả và đã được chứng minh, để cung cấp **full context** cho AI agent trước khi agent thực hiện bất kỳ task software engineering nào — thiết kế, code, debug, viết docs, hay lập plan.

Cái tên lấy cảm hứng từ hình tượng nhân vật chính trong manga/manhwa/manhua có khả năng **hồi quy (regression)**: mỗi vòng lặp, nhân vật quay lại nhưng vẫn giữ trong mình toàn bộ kiến thức quan trọng và cốt lõi đã từng tích lũy ở những vòng trước. Áp dụng vào SE: mỗi khi agent bắt đầu một task mới, nó **không xuất phát từ số 0** — nó tra lại "trí nhớ" đã được xây dựng qua toàn bộ các task trước đó: business logic, kiến trúc, quyết định thiết kế, ràng buộc, lịch sử thay đổi.

Nguyên lý cốt lõi: **dùng càng lâu, hệ thống càng đồ sộ.** Mỗi feature được document, mỗi quyết định được ghi lại, mỗi lần compile là một lần nạp thêm tri thức vào graph. Context không co lại theo từng conversation — nó **tích lũy** theo thời gian và khép thành một vòng tuần hoàn phát triển:

> làm task → tri thức được ghi lại → graph dày thêm → agent hiểu sâu hơn → task sau làm nhanh & đúng hơn → lại tiếp tục ghi lại...

## Triết lý nền: Docs-as-Database

Khác với docs truyền thống (văn xuôi tự do, dễ trôi khỏi thực tế code), Regressor coi **docs là dữ liệu có cấu trúc, compile được**, giống code:

- Mỗi file docs phải tuân theo khuôn dạng cố định (YAML frontmatter + cú pháp tag `[ID] {meta} nội dung`).
- Docs được **parse → validate → compile** bằng một Python compiler thật, không phải chỉ đọc bằng mắt.
- Sau khi validate sạch, docs được **ingest thành node/relationship trong Neo4j** — biến văn bản thành một đồ thị tri thức có thể query.
- Nếu docs sai cú pháp, thiếu ID, hoặc tham chiếu đến ID không tồn tại → compiler chặn lại, không cho ingest.

Nhờ vậy, Neo4j Knowledge Graph luôn là **nguồn sự thật (source of truth)** đáng tin cậy cho business logic — không phải một tài liệu Confluence có thể lỗi thời mà không ai biết.

## Kiến trúc tổng quan

```text
 ┌──────────────────────────────────────────────────────────────────────┐
 │                    TASK MỚI (design / code / debug / plan)            │
 └───────────────────────────────────┬────────────────────────────────────┘
                                      ▼
        ┌────────────────────────────────────────────────────┐
        │  PHASE 1 — Context Gathering                          │
        │  ① Neo4j Knowledge Graph        (Priority 1)          │
        │  ② Serena  +  GitNexus          (Priority 2 & 3,      │
        │     chạy song song)                                   │
        └────────────────────────┬─────────────────────────────┘
                                  ▼
        ┌────────────────────────────────────────────────────┐
        │  PHASE 2 — Docs-as-Database  (skill `docs-create`)    │
        │  scaffold.py → viết 9 file → compile --dry-run        │
        │  → neo4j_ingestor (MERGE vào Neo4j)                   │
        └────────────────────────┬─────────────────────────────┘
                                  ▼
        ┌────────────────────────────────────────────────────┐
        │  PHASE 3 — Implement & Verify                         │
        │  code đúng theo docs → detect_changes() → commit      │
        └────────────────────────┬─────────────────────────────┘
                                  │
                                  ▼
                Neo4j Knowledge Graph dày thêm một lớp tri thức
                                  │
                 ╰────────────── vòng lặp cho task kế tiếp ─────────────╮
                                                                        │
                 ◄──────────────────────────────────────────────────────╯
```

Bốn khối công cụ đứng sau ba phase này là **Neo4j**, **hệ docs 9-file + compiler Python**, **GitNexus & Serena**, và **Superpowers**.

## Tech Stack

| Thành phần | Vai trò trong Regressor |
|---|---|
| **Neo4j** | Đồ thị tri thức (Knowledge Graph) — lưu Feature/System, Requirement, BusinessRule, Component, Decision,... dưới dạng node/relationship, query được bằng Cypher. |
| **Docs-as-Database** | Hệ thống docs độc quyền: 9 file chuẩn hóa cho mỗi feature/system, có luồng sinh khung (scaffold), validate/verify, và ingest — tất cả qua Python script trong `graph/compiler/`. |
| **GitNexus** | Code intelligence: symbol graph, execution flow, impact analysis (blast radius), rename an toàn theo call graph, phát hiện thay đổi trước khi commit. |
| **Serena** | Semantic code toolkit qua LSP: tìm symbol, tìm nơi gọi, đọc/sửa code chính xác ở cấp AST thay vì text thô. |
| **Superpowers** | Bộ skill quy trình (process skills) bắt buộc phải kiểm tra trước mọi hành động: brainstorming, writing-plans, TDD, systematic-debugging,... đảm bảo kỷ luật kỹ thuật. |
| **`docs-create` skill** | Skill riêng ép buộc quy trình 3-Phase Safe Change & Documentation Workflow, nối toàn bộ các mảnh trên thành một pipeline duy nhất. |

## Thứ tự tra cứu & Nguồn sự thật

Trước **mọi** task (design/coding/debug/docs/plan), thứ tự tra cứu bắt buộc là:

1. **Neo4j Knowledge Graph** — business rule, requirement, impact analysis, blast radius.
2. **Serena + GitNexus** (chạy song song) — implementation thật, execution flow, side effect.
3. Chỉ khi hai bước trên không đủ mới mở file cụ thể, rồi mới `grep`/`rg`/`find`/`ls`.

Nếu thông tin còn thiếu: **tiếp tục tra cứu, không đoán/không bịa.**

Phân cấp nguồn sự thật:

| Ưu tiên | Nguồn | Trả lời cho câu hỏi |
|---|---|---|
| 1 | **Neo4j Knowledge Graph** | Business intent, rule, kiến trúc |
| 2 | **Serena + GitNexus** | Implementation kỹ thuật & execution thật |
| 3 | **Raw docs (`/docs/`)** | Dữ liệu nguồn nạp cho graph |

Nếu ba nguồn mâu thuẫn nhau: code có thể đã lỗi thời, hoặc graph cần cập nhật — **dừng lại và hỏi user**, không tự quyết.

## Quy trình vận hành (3 Phase)

### Phase 1 — Context Gathering

Trước khi đề xuất hoặc sửa bất kỳ dòng code nào, agent phải có đủ:

- Requirement & business rule liên quan (từ Neo4j).
- Blast radius / impact analysis (từ Neo4j + GitNexus `impact()`).
- Symbol & component bị ảnh hưởng (từ Neo4j + Serena `find_symbol`).
- Execution flow, nếu logic phức tạp (từ GitNexus `context()`).

### Phase 2 — Tạo/Cập nhật Docs

Khi cần tạo hoặc sửa docs kiến trúc/feature, **bắt buộc** đi qua skill `docs-create` (chi tiết ở mục 9) — không viết tay, không tự soạn markdown:

1. `scaffold.py` sinh khung 9 file.
2. Điền nội dung theo cú pháp tag bắt buộc.
3. `compile.py --dry-run` để validate.
4. `compile.py --neo4j-uri ...` để ingest chính thức.

### Phase 3 — Implement & Verify

- Code phải khớp với docs vừa viết — docs không được mâu thuẫn với code.
- Chạy `detect_changes()` của GitNexus trước khi commit, so sánh với `master` khi cần regression review.
- Cảnh báo user nếu impact analysis trả về mức rủi ro HIGH/CRITICAL.
- Commit docs và code **cùng nhau**.

Kết thúc Phase 3, Neo4j đã dày thêm một lớp tri thức mới — task tiếp theo sẽ bắt đầu từ Phase 1 với một graph giàu hơn. Đó chính là vòng lặp "hồi quy" của Regressor.

## Hệ thống Docs-as-Database chi tiết

### Hai domain

Docs sống nghiêm ngặt trong hai domain:

- **`docs/features/`** — tài liệu ở mức feature.
- **`docs/systems/`** — tài liệu ở mức system/component hạ tầng.

Mỗi topic (feature/system) có các folder version đánh số tăng dần (`00000-init`, `00001`, `00002`...). Folder version cao nhất là **active version** duy nhất.

### 9 file chuẩn

Mỗi version folder chỉ được chứa đúng 9 file này (không hơn, không kém):

| # | File | doc_type | ID Prefix | Nội dung | Giới hạn dòng |
|---|---|---|---|---|---|
| 1 | `01-requirements.md` | Requirements | `REQ-` | Yêu cầu nghiệp vụ/chức năng | 200 · **bắt buộc** |
| 2 | `02-business-rules.md` | BusinessRules | `RULE-` | Luật nghiệp vụ dạng WHEN / THEN / REASON | 200 |
| 3 | `03-data-models.md` | DataModels | `ENTITY-`, `FIELD-` | Entity & field của database | không giới hạn |
| 4 | `04-api-contracts.md` | APIContracts | `API-` | Endpoint, params, response, errors | không giới hạn |
| 5 | `05-components.md` | Components | `COMP-` | Component code, map tới symbol thật qua `MAPS_TO_SYMBOL` | không giới hạn · **bắt buộc** |
| 6 | `06-decisions.md` | Decisions | `DEC-` | ADR: CONTEXT / DECISION / CONSEQUENCES | không giới hạn |
| 7 | `07-dependencies.md` | Dependencies | `DEP-` | Liên kết FROM → TO giữa component/system/external/kafka | không giới hạn |
| 8 | `08-plan.md` | Plan | `TASK-` | Checklist implement, trạng thái TODO/DONE | 200 · **bắt buộc** |
| 9 | `09-glossary.md` | Glossary | `TERM-` | Định nghĩa thuật ngữ domain | 100 |

Ba file **bắt buộc** phải luôn tồn tại trong mọi version: `01-requirements.md`, `05-components.md`, `08-plan.md` — compiler sẽ cảnh báo nếu thiếu.

### YAML Frontmatter

Mọi file `.md` bắt đầu bằng một block YAML — đây là cách compiler liên kết các file với nhau:

```yaml
---
domain: Feature|System
topic: <ten-topic-kebab-case>
version: "00000-init"
doc_type: Requirements|BusinessRules|DataModels|APIContracts|Components|Decisions|Dependencies|Plan|Glossary
depends_on: []
gitnexus_processes: []
last_updated: 2026-08-20
author: <ten-agent-hoac-user>
---
```

`depends_on` nối topic này với topic khác trong graph; `gitnexus_processes` map docs tới execution flow thật của GitNexus.

### Cú pháp tag có cấu trúc

Nội dung bên trong mỗi file dùng cú pháp tag xác định để compiler đọc được: `[NODE-ID] {key: value} Mô tả ngắn`, các sub-field thụt lề bên dưới.

```markdown
[RULE-01] {priority: high, status: active} Late payment penalty rule
  - WHEN: Payment is received after the due date
  - THEN: Apply 2% penalty on outstanding amount
  - REASON: Enforce timely payment compliance
```

```markdown
[COMP-01] {type: service} MaintenanceFeeCalculator
  - IMPLEMENTS: [REQ-01], [REQ-02]
  - MAPS_TO_SYMBOL: src/calculator.py
```

ID phải **duy nhất trong topic**, không được trùng, không được tự đặt prefix mới ngoài `REQ-`, `RULE-`, `ENTITY-`, `FIELD-`, `API-`, `COMP-`, `DEC-`, `DEP-`, `TASK-`, `TERM-`.

### Versioning

- Tối đa **5 version** cho mỗi topic (`00000-init` → `00004`).
- Lần thay đổi thứ 6 phải trigger `10000-reset` — một version gộp lại toàn bộ state, không cần đọc các version cũ để hiểu.
- Với version incremental (`00001+`): **chỉ viết phần thay đổi**, thêm mục "What Changed", và tham chiếu rõ baseline cũ — không copy lại toàn bộ.
- Nghiêm cấm tạo folder đánh dấu kiểu `CURRENT`/`latest`/`active` — active version luôn được xác định bằng số cao nhất.

## Python Compiler Pipeline

Toàn bộ pipeline nằm ở `graph/compiler/`, docs được coi là code và đi qua 4 bước xử lý tuần tự:

| File | Vai trò |
|---|---|
| `scaffold.py` | Sinh 9 file chuẩn (kèm YAML frontmatter + ví dụ cú pháp) cho một topic mới. Không cho tự tạo file tay. |
| `parser.py` + `models.py` | Đọc toàn bộ `/docs`, parse thành `ParsedCorpus` → `ParsedTopic` → `ParsedDocument` (dataclass cho Requirement, BusinessRule, Entity, Component, Decision, Dependency, Task, Term...). |
| `validators.py` | Kiểm tra frontmatter đầy đủ, ID không trùng trong topic, không có reference gãy (trỏ tới ID không tồn tại), đủ file bắt buộc, đúng giới hạn dòng. Lỗi (`ERROR`) sẽ chặn ingest; cảnh báo (`WARNING`) thì không. |
| `neo4j_ingestor.py` | Đẩy corpus đã validate vào Neo4j bằng Cypher `MERGE` **idempotent**, dùng driver `neo4j` chính thức trực tiếp — không qua LLM. Mặc định xóa sạch graph rồi build lại (`clear_first=True`), dùng `--no-clear` để giữ dữ liệu cũ. |
| `compile.py` | CLI orchestrator: parse → validate → (`--dry-run` thì dừng) → ingest vào Neo4j. |

### Node labels trong Neo4j

`Feature`, `System`, `Version`, `Requirement`, `BusinessRule`, `Entity`, `Field`, `Endpoint`, `Component`, `Decision`, `Dependency`, `Task`, `Term`, `Symbol`, `External` — mỗi label đều có index trên `id` để query nhanh.

### Relationship chính

| Quan hệ | Ý nghĩa |
|---|---|
| `HAS_VERSION` | Feature/System → Version |
| `DEFINES` | Version → mọi node nội dung (Requirement, Rule, Entity, Component,...) |
| `DEPENDS_ON` | Requirement→Requirement, BusinessRule→BusinessRule, Task→Task |
| `DEPENDS_ON_TOPIC` | Version → topic khác (liên kết cross-feature/system) |
| `APPLIES_TO` | BusinessRule → Requirement |
| `MAPS_TO_SYMBOL` | Entity/Endpoint/Component → Symbol code thật (cầu nối docs ↔ code) |
| `IMPLEMENTS` | Component/Task → Requirement/Endpoint |
| `FALLBACK_TO` | Component → Component dự phòng |
| `AFFECTS` / `SUPERSEDES` | Decision → Component / Decision cũ |
| `FROM` / `TO` | Dependency → Component, System, External, hoặc Kafka |
| `COVERS` | Task → BusinessRule |
| `USED_BY` | Term → bất kỳ node nào dùng thuật ngữ đó |

Đây chính là "bộ nhớ dài hạn" mà Regressor tra cứu ở Phase 1 của mọi task.

## Skill `docs-create`

Nằm ở `.claude/skills/docs-create/`, gồm 3 file: `SKILL.md` (quy trình), `templates.md` (mẫu nhanh), `checklist.md` (checklist QA). Đi cùng là rule bắt buộc `docs/rules/feature-system-docs.md` (`alwaysApply: true`) — nguồn quy định format tuyệt đối.

Quy trình 4 bước **strict**, không cho làm tắt:

1. **Scaffold bắt buộc** — `python3 -m graph.compiler.scaffold --domain feature --topic <ten> --version <ver>`, tuyệt đối không tự tạo 9 file bằng tay.
2. **Viết docs** — đọc kỹ `docs/rules/feature-system-docs.md`, điền dữ liệu bằng cú pháp `[ID] {meta}`, xác định version (max 5, tới lần 6 thì `10000-reset`).
3. **Compile & Validate** — `python3 -m graph.compiler.compile --docs-dir ./docs --dry-run`, sửa hết lỗi link gãy/ID trùng.
4. **Ingest vào Neo4j** — chạy lại compile không có `--dry-run` để đẩy graph tri thức mới lên.

Nguyên tắc quan trọng đi kèm: Neo4j graph là nguồn sự thật tối cao cho business logic; **không được bịa rule** — nếu graph thiếu thông tin, phải hỏi user; docs không bao giờ được mâu thuẫn với code.

## GitNexus — Code Intelligence

Repo này được GitNexus index dưới tên **maintain-fee-service** (2925 symbols, 4400 relationships, 64 execution flows). Vai trò: hiểu code, đánh giá impact, điều hướng an toàn — thay thế cho việc đọc/lần code bằng mắt hoặc grep mù.

**Công cụ chính:** `impact` (blast radius trước khi sửa), `context` (toàn bộ ngữ cảnh của 1 symbol: caller/callee/execution flow), `query` (tìm execution flow theo concept, thay cho grep), `detect_changes` (kiểm tra thay đổi trước khi commit, so sánh với `master`), `rename` (đổi tên hiểu call graph, an toàn hơn find-replace), cùng `api_impact`, `cypher`, `route_map`, `shape_check`, `tool_map`, `group_list`/`group_sync`, `list_repos`.

**Luật bắt buộc** (được GitNexus tự chèn vào cả `CLAUDE.md` và `AGENTS.md`):

- Luôn `impact()` trước khi sửa bất kỳ function/class/method.
- Luôn `detect_changes()` trước khi commit.
- Luôn cảnh báo user nếu risk ở mức HIGH/CRITICAL.
- Không bao giờ rename bằng find-and-replace thô.
- Index bị cũ? Chạy `node .gitnexus/run.cjs analyze` (hoặc `npx gitnexus analyze`).

6 skill vận hành nằm ở `.claude/skills/gitnexus/`: `gitnexus-exploring`, `gitnexus-impact-analysis`, `gitnexus-debugging`, `gitnexus-refactoring`, `gitnexus-guide`, `gitnexus-cli` (cộng `gitnexus-pr-review` ở tầng plugin) — mỗi skill ứng với một loại câu hỏi (kiến trúc, blast radius, debug, refactor, tra cứu API, index/CLI).

## Serena — Semantic Code Toolkit

Serena là lớp thao tác code ở cấp **AST/LSP** thay vì text thô: `find_symbol`, `find_referencing_symbols`, `find_implementations`, `find_declaration`, `get_symbols_overview`, `search_for_pattern` để đọc; `replace_symbol_body`, `insert_before_symbol`, `insert_after_symbol`, `rename_symbol`, `safe_delete_symbol` để sửa chính xác đúng symbol, không side-effect ngoài ý muốn.

Serena còn có một lớp memory riêng, nhẹ hơn Neo4j nhiều: `write_memory`/`read_memory`/`list_memories` lưu tại `.serena/memories/` — đóng vai trò "sổ tay" liên tục giữa các session của riêng project đó, khác với Neo4j là "thư viện tri thức" đầy đủ cấu trúc và query được bằng Cypher.

Quy tắc bắt buộc: gọi `initial_instructions` (Serena Instructions Manual) trước khi bắt đầu bất kỳ coding task nào.

## Superpowers — Kỷ luật quy trình

Superpowers là bộ **process skill** — khác với các skill kiến thức, nó ép buộc **cách agent hành xử** trước khi làm bất cứ điều gì. Skill gốc `using-superpowers` bắt agent phải kiểm tra "có skill nào áp dụng không" trước cả câu hỏi làm rõ đầu tiên.

Các process skill cốt lõi:

| Skill | Dùng khi |
|---|---|
| `brainstorming` | Trước mọi creative work — tạo feature, thêm behavior mới |
| `writing-plans` | Có spec/requirement cho task nhiều bước, trước khi đụng code |
| `executing-plans` | Thực thi một plan đã viết, có checkpoint review |
| `subagent-driven-development` | Thực thi plan với các task độc lập trong cùng session |
| `dispatching-parallel-agents` | ≥2 task độc lập, không chia sẻ state |
| `systematic-debugging` | Gặp bug/test fail/hành vi lạ, trước khi đề xuất fix |
| `test-driven-development` | Trước khi viết implementation code |
| `using-git-worktrees` | Cần workspace cách ly cho feature work |
| `requesting-code-review` / `receiving-code-review` | Hoàn thành task lớn / nhận feedback review |
| `verification-before-completion` | Trước khi claim "đã xong/đã fix/đã pass" |
| `finishing-a-development-branch` | Implementation xong, tất cả test pass |
| `writing-skills` | Tạo hoặc chỉnh sửa skill mới |

Superpowers không chỉ tồn tại trên lý thuyết — trong repo này, output của `brainstorming` và `writing-plans` được lưu thật tại `docs/superpowers/specs/` và `docs/superpowers/plans/` (ví dụ: `2026-05-15-advanced-price-caching-design.md`, `2026-05-08-vulnerability-remediation.md`). Đây là **vùng nháp** — nơi ý tưởng được brainstorm và plan được viết ra trước khi implement.

Điểm nối quan trọng với Docs-as-Database: spec/plan trong `docs/superpowers/` là tri thức **tạm thời, đang hình thành**; một khi đã implement và chốt, nó được **kết tinh lại** thành 9 file chính thức qua `docs-create`, rồi compile + ingest vào Neo4j để trở thành tri thức **vĩnh viễn**. Superpowers giữ kỷ luật trong lúc làm; Docs-as-Database + Neo4j giữ lại thành quả sau khi làm xong.

## MCP Servers kết nối

Cấu hình tại `.mcp.json`:

| Server | Lệnh khởi động | Vai trò |
|---|---|---|
| `serena` | `serena start-mcp-server --project-from-cwd` | Semantic code toolkit (AST/LSP) |
| `gitnexus` | `gitnexus mcp` | Code intelligence, impact analysis, execution flow |
| `neo4j` | `python -m neo4j_mcp_server` | Đọc/viết trực tiếp Cypher vào Knowledge Graph |

## Cây thư mục tham chiếu

```text
.
├── CLAUDE.md / AGENTS.md            # luật bắt buộc cho AI agent (discovery order, gitnexus rules)
├── .claude/skills/
│   ├── docs-create/                 # skill ép buộc quy trình doc (SKILL.md, templates.md, checklist.md)
│   └── gitnexus/                    # exploring / impact-analysis / debugging / refactoring / guide / cli
├── docs/
│   ├── index.md                     # mục lục toàn bộ feature & system đã document
│   ├── explain/                     # bản tóm tắt nhanh, đối chiếu code qua GitNexus + Serena
│   ├── features/<topic>/<version>/01..09-*.md
│   ├── systems/<topic>/<version>/01..09-*.md
│   ├── rules/feature-system-docs.md # luật format bắt buộc (alwaysApply: true)
│   └── superpowers/
│       ├── specs/                   # output của skill brainstorming
│       └── plans/                   # output của skill writing-plans
├── graph/
│   ├── compiler/                    # scaffold.py, parser.py, models.py, validators.py,
│   │                                 # neo4j_ingestor.py, compile.py
│   ├── scripts/                     # init_graph.py, ingest_docs.py,...
│   └── graph_client.py
└── .serena/memories/                 # bộ nhớ nhẹ theo project của Serena
```

## Nguyên tắc vàng

**Luôn làm:**

- Tra Neo4j trước, Serena + GitNexus song song sau — theo đúng thứ tự ưu tiên.
- `impact()` trước khi sửa bất kỳ symbol nào; `detect_changes()` trước khi commit.
- Dùng `scaffold.py` để sinh docs — không viết tay 9 file.
- `compile --dry-run` để validate sạch trước khi ingest thật.
- Giữ docs khớp 100% với code đã implement.
- Cảnh báo user khi risk ở mức HIGH/CRITICAL.

**Không bao giờ:**

- Bịa business rule khi graph thiếu — phải hỏi user, không đoán.
- Tạo file ngoài 9 file chuẩn, hoặc folder `CURRENT`/`latest`/`active`.
- Tự đặt prefix ID mới ngoài danh sách đã quy định.
- Rename symbol bằng find-and-replace thô.
- Commit khi chưa `detect_changes()` hoặc khi compile chưa pass sạch lỗi.

## Cheat sheet lệnh

```bash
# Cập nhật lại index GitNexus khi code đã đổi nhiều
node .gitnexus/run.cjs analyze

# Sinh khung 9 file docs cho 1 feature mới
python3 -m graph.compiler.scaffold --domain feature --topic <ten-feature> --version 00000-init

# Sinh khung cho 1 system
python3 -m graph.compiler.scaffold --domain system --topic <ten-system> --version 00000-init

# Validate docs (không ghi Neo4j)
python3 -m graph.compiler.compile --docs-dir ./docs --dry-run

# Ingest chính thức lên Neo4j
python3 -m graph.compiler.compile --docs-dir ./docs --neo4j-uri bolt://localhost:7687
```

---

Regressor không phải một công cụ đơn lẻ — nó là **cách các công cụ này được nối lại thành một vòng lặp**: mỗi task đi qua vòng lặp một lần, và graph tri thức không bao giờ nhỏ lại.
