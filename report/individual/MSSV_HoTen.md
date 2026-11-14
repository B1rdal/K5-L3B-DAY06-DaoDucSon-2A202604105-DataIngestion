# Báo cáo cá nhân — Day 6: Data Ingestion Engineering

**Ngày lập báo cáo:** 14/11/2026 (Asia/Saigon).

**Chủ đề:** Xây dựng và đánh giá kho truy xuất bằng chứng từ một tài liệu truyện tiếng Anh bằng PostgreSQL + pgvector.

| Thông tin | Giá trị |
|---|---|
| Họ và tên | Chưa được cung cấp |
| MSSV | Chưa được cung cấp |
| Lớp | Chưa được xác nhận |
| Remote origin hiện tại | [B1rdal/K5-L3B-Day06-DataIngestionEngineering](https://github.com/B1rdal/K5-L3B-Day06-DataIngestionEngineering) |
| Commit chốt bài | Chưa chốt; mã nguồn và artifacts còn thay đổi trong working tree |

> Phần kỹ thuật dưới đây sử dụng kết quả đã chạy và artifacts đã lưu. Bộ câu hỏi và các nhãn định tính được hỗ trợ bởi Codex AI; chưa có xác minh độc lập của người học. Quyền xử lý/chia sẻ corpus, manifest cuối cùng và thông tin học viên vẫn cần hoàn thiện trước khi nộp. Chưa xác nhận khả năng truy cập repo của người chấm và chưa thực hiện nộp link.

## Dữ liệu và pipeline

### Chủ đề, nguồn/quyền, số trang và quy tắc tính trang

Corpus là **Roshidere, Volume 10 — Glucose Translations**, một bản fan translation tiếng Anh. File được người dùng cung cấp tại:

```text
F:\FDownload\MainDownload\Roshidere, Vol. 10 - Glucose Translations.pdf
```

Đây là đường dẫn bản sao local, không phải bằng chứng về quyền sử dụng hoặc URL tải có giấy phép. Phần đầu PDF ghi thông tin nhóm dịch và các hạn chế liên quan đến chia sẻ/in lại. **Chưa xác minh được quyền xử lý và tái phân phối cho phạm vi bài lab; không ghi corpus là public domain hoặc được cấp phép mở.** Dữ liệu và trích đoạn cần được giữ local cho đến khi quyền chia sẻ được làm rõ. Nếu không được phép nộp dữ liệu gốc/trace chứa nội dung, cần bổ sung manifest và cách truy cập/tái tạo cùng minh chứng được phép chia sẻ theo hướng dẫn lớp.

- PDF có **270 trang vật lý**. Trích xuất thu được văn bản trên **261 trang**, **9 trang không có text trích xuất** (trang 1–7, 11 và 12), và **0 lỗi trích xuất**.
- Corpus làm việc giữ **227 trang có văn bản** thuộc prologue, chương 1–10, epilogue và bonus story. Số này là kết quả của quy tắc chọn trang; **chưa thay thế việc duyệt cuối cùng toàn bộ trang nội dung hữu ích**.
- Chỉ giữ các phần truyện trong cấu hình. Loại phần đầu, mục lục, afterword, ghi chú cuối của nhóm dịch, trang chỉ có footer/không có chữ và các trang riêng bắt đầu bằng dấu chú thích của nhóm dịch.
- Xóa đúng footer dạng `Glucose Translations <số trang>`. Không nhân bản trang để đạt số lượng; vẫn giữ nguyên số trang PDF gốc sau khi lọc.
- Không dùng một ngưỡng độ dài để tự coi mọi trang là nội dung hợp lệ. Một số trang ngắn vẫn có lời thoại/nội dung hữu ích; một số trang có text chỉ là phần phụ.
- Quy tắc và quyết định từng trang nằm trong [page_selection.json](../../starter/results/roshidere/page_selection.json). Manifest nguồn/quyền cuối cùng `data/manifest.*` chưa được tạo/chốt.

| Phần | Số trang văn bản trong corpus làm việc |
|---|---:|
| prologue | 4 |
| chapter_1 | 20 |
| chapter_2 | 14 |
| chapter_3 | 19 |
| chapter_4 | 31 |
| chapter_5 | 24 |
| chapter_6 | 21 |
| chapter_7 | 23 |
| chapter_8 | 26 |
| chapter_9 | 19 |
| chapter_10 | 16 |
| epilogue | 4 |
| bonus_story | 6 |

SHA-256 của PDF: `dd48d3ff9c189bf4987e985e0b356edd5ea18b75fb010c92d3bb5b4c49b50fcf`.

### Chuẩn hóa, lỗi và giới hạn

Pipeline đã hiện thực:

```text
PDF → trích xuất từng trang → chuẩn hóa → chọn corpus/gắn metadata
    → chia chunk → embedding local → lưu PostgreSQL + pgvector
    → truy xuất top-3 → benchmark → audit bằng chứng
```

`ingestion.py` dùng pypdf ở chế độ layout, chuẩn hóa Unicode NFC, xuống dòng và khoảng trắng nhưng giữ ranh giới dòng/đoạn. Mỗi trang có `extraction_status` và số ký tự; trang rỗng/lỗi vẫn có bản ghi để không làm lệch số trang. Lỗi cấp file được báo rõ; lỗi từng trang được ghi trong metadata/log. Không thực hiện OCR.

`corpus.py` chọn phần truyện, bỏ footer và gắn section sau khi kiểm tra tiêu đề mở đầu. Các trang chuẩn bị nằm trong [prepared_pages.jsonl](../../starter/results/roshidere/prepared_pages.jsonl). Khoảng trắng và ngắt đoạn của PDF vẫn có thể ảnh hưởng chất lượng chunk. Chưa loại toàn bộ chú thích nằm xen trong trang, và quy tắc sentence/paragraph không bảo đảm mọi lượt thoại đều trọn vẹn.

Khi nạp lại, store thay thế atomically các chunk của document trong strategy tương ứng, xóa chunk cũ và giữ các document khác. Kiểm tra nạp lại A/B/C cho số dòng trước/sau lần lượt là **865/865, 1.012/1.012 và 1.012/1.012**, ID không đổi; kiểm tra rollback khi insert lỗi cũng đã chạy. Minh chứng: [database_checks.json](../../starter/results/roshidere/database_checks.json).

### Model, vector store, phiên bản, metric và chi phí

| Thành phần | Cấu hình đã dùng |
|---|---|
| Python | 3.13.18, môi trường riêng `starter/.venv` |
| PDF parser | pypdf 6.21.4 |
| Embedding | `BAAI/bge-small-en-v1.5`, 384 chiều |
| Backend embedding | FastEmbed 0.9.1, ONNX Runtime 1.32.0, CPU 4 threads, batch 32 |
| Xử lý query/document | `query_embed` / `passage_embed`, không thêm prefix ngoài; cùng weights/tokenizer cho các cấu hình |
| Vector store | PostgreSQL 16.16 + pgvector 0.8.7, chạy trong Docker Desktop |
| Python DB driver | psycopg 3.3.8 |
| Similarity | Cosine, exact search; không dùng approximate vector index |
| Reranker bổ sung | `Xenova/ms-marco-MiniLM-L-6-v2`, ONNX CPU local |
| Lưu trữ | Docker app `F:\Docker\app`, disk/data `F:\Docker\data` |
| Cache model | `F:\CodexTools\models\fastembed` và `F:\CodexTools\models\rerankers` |
| DB local | `127.0.0.1:55433`, database `day6_lab`; thông tin kết nối đọc từ `.env` |

Tên model, phiên bản và hash weights/tokenizer được lưu trong [ingest_stats.json](../../starter/results/roshidere/ingest_stats.json) và [setup.json của thí nghiệm cải tiến](../../starter/results/roshidere-v2/setup.json). Không dùng vector ngẫu nhiên/mock thay cho model trong pipeline thật. Một số fixture kiểm thử dùng vector tổng hợp và được tách khỏi kết quả benchmark.

**Phí API embedding/reranking đã dùng: 0 USD**, do inference chạy local. Số này không tính máy, điện, mạng hoặc thời gian tải model. Lần đầu cần mạng để tải image/dependency/weights; văn bản được xử lý bằng model local.

### Metadata bắt buộc và trường lọc

| Trường | Kiểu/nguồn | Công dụng |
|---|---|---|
| `document_id` | Chuỗi `roshidere-vol10` gắn với tài liệu nguồn | Phân biệt tài liệu, xác định phạm vi thay thế khi nạp lại |
| `source` | Chuỗi đường dẫn PDF local được cung cấp | Truy về file nguồn; cần manifest để người chấm trên máy khác truy cập |
| `page` | Số nguyên, trang PDF vật lý bắt đầu từ 1 | Trích nguồn và đối chiếu evidence |
| `section` | Chuỗi như `chapter_5`, `epilogue`, `bonus_story` | Lọc phạm vi khi câu hỏi/ngữ cảnh cung cấp section |
| `section_source` | Ghi nguồn từ mục lục trang 13 và tiêu đề mở đầu | Giải thích nguồn giá trị section; đã kiểm tra 13 tiêu đề |
| `language`, `document_type` | `en`, `novel`, phù hợp nội dung nguồn | Mô tả corpus; không tạo giá trị giả để nâng điểm filter |
| `char_start`, `char_end` | Số nguyên, offset trong trang đã chuẩn bị | Xác định chính xác phần text của chunk; `offset_basis=prepared_page_text` |

`section` hữu ích vì nhiều chương lặp lại tên nhân vật/chủ đề. Giá trị filter phải do câu hỏi hoặc người dùng cung cấp trước truy xuất; không lấy `gold_page`/đáp án để tạo filter.

### Cách chạy

Trên máy hiện tại, chạy `F:\CodexTools\Start Day6.cmd` để bật Docker/database. Từ PowerShell:

```powershell
cd "F:\Github\K5-L3B-Day06-DataIngestionEngineering\starter"
.\.venv\Scripts\python.exe scripts\check_setup.py
.\.venv\Scripts\python.exe -m src.run search "YOUR QUESTION"
.\.venv\Scripts\python.exe -m src.run search "YOUR QUESTION" --section chapter_5
.\.venv\Scripts\python.exe -m src.run search "YOUR QUESTION" --strategy C
```

Search mặc định dùng F qua `configs/active.json`; A/B/C vẫn truy xuất bảng gốc. Trên một bản setup mới, nạp baseline bằng `python -m src.run ingest`; quy trình cải tiến dùng `python -m src.improvement prepare`, `dev`, rồi `test`. Các lệnh benchmark/audit giữ nguyên kết quả đã có và từ chối ghi đè các thư mục thí nghiệm hoàn tất.

Cách cài/tái lập đầy đủ và chạy lại benchmark vào thư mục mới: [starter README](../../starter/README.md), [USAGE](../../starter/USAGE.md), [benchmark v1](../../benchmark/roshidere/README.md), [thí nghiệm v2](../../benchmark/roshidere-v2/README.md). Không commit `.env`, API key hoặc token.

## Cấu hình và benchmark

### Ba cấu hình bắt buộc A/B/C

| Cấu hình | Chunking | Overlap | Truy xuất/filter |
|---|---|---:|---|
| A | Fixed-size 500 ký tự | 50 ký tự | Exact cosine, không filter |
| B | Nhóm paragraph tối đa 500 ký tự; đoạn dài chia tại khoảng trắng nếu có | 0 | Cùng model/store/metadata, không filter |
| C | Giống hoàn toàn B | 0 | Chỉ thêm section filter khi câu hỏi cung cấp |

A–B so sánh chiến lược chia chunk. **B–C chỉ thay việc áp dụng filter**; chunk và vector giống nhau, nên đây là so sánh có kiểm soát một yếu tố. Các cấu hình dùng cùng corpus, model, metric và bộ câu hỏi.

### Benchmark v1: 20 câu, 15 dev / 5 test

Bộ câu hỏi nằm tại [questions.jsonl v1](../../benchmark/roshidere/questions.jsonl). Dev dùng prologue/chương 1–8; test dùng chương 9–10, epilogue và bonus story. Có **5 câu cung cấp filter: 3 dev và 2 test**. Mỗi câu có ID, split, question, expected answer, source ID, trang PDF, evidence quote và filter nếu có.

Câu hỏi được Codex AI soạn từ các trang nguồn; evidence được đọc đối chiếu và kiểm tra tự động trong cả text trích xuất gốc lẫn trang chuẩn bị. Chưa có xác minh gold độc lập bởi người học. Bộ câu hỏi là mẫu thuận tiện, có nhiều câu từ đầu chương, không phải mẫu ngẫu nhiên đại diện toàn bộ truyện.

Benchmark được tạo sau khi pipeline/index baseline đã chạy, nhưng **trước lần truy xuất theo bộ câu hỏi**; hoạt động trước đó là kiểm tra hạ tầng/vector và câu smoke test không liên quan nội dung truyện. Questions, protocol, corpus, cấu hình, model identity và index được hash/freeze trước chạy dev. Tiêu chí chọn chốt trước test: **Evidence Hit@3 dev cao nhất → Hit@1 dev cao nhất → ít chunk hơn → thứ tự tên cấu hình**. C được chọn trước chạy test vì cùng Hit@3 với B nhưng Hit@1 dev cao hơn.

Một strict hit yêu cầu **một chunk** đúng document/trang gold và chứa đầy đủ evidence quote đã đăng ký sau chuẩn hóa NFC/khoảng trắng. Hit@1 tính trên kết quả đầu; Hit@3 tính khi có ít nhất một hit trong top-3. Không coi đúng trang hoặc score cao là đủ. Metric tự động có thể bỏ sót diễn đạt tương đương, trang nguồn khác hợp lệ hoặc bằng chứng bị tách qua nhiều chunk.

### Thí nghiệm cải tiến D/E/F và holdout mới

Sau khi test v1 đã được xem, kết quả test đó không còn được dùng như holdout độc lập cho việc tinh chỉnh. Thí nghiệm v2 giữ nguyên 15 câu dev và chuẩn bị **10 câu test mới về các dữ kiện/trang khác**, gồm 3 câu test có filter, trước khi phát triển/đánh giá candidate.

| Cấu hình | Thay đổi bổ sung |
|---|---|
| D | Window ưu tiên ranh giới câu, tối đa 1.000 ký tự, overlap mục tiêu 250; vẫn dense cosine |
| E | Cùng chunk/vector D; kết hợp dense top-30 và PostgreSQL English full-text top-30 bằng RRF, k=60 |
| F | Cùng candidate E; reranker local xếp lại tối đa 30 candidate rồi trả top-3 |

D/E/F dùng chung **535 chunk** trong bảng riêng `day6_chunks_v2`; bảng A/B/C gốc không đổi. Window ở trong một trang; overlap thực tế có thể thay đổi theo ranh giới câu. Input embedding lớn nhất đo được là **281 token**, dưới giới hạn 512 token.

Chỉ thử một bộ tham số context/overlap, một cấu hình fusion và một reranker theo kế hoạch đã ghi trước. Tiêu chí chọn dev: Hit@3 → Hit@1 → ưu tiên đơn giản theo `C gốc, D, E, F`. F được khóa lựa chọn trước holdout mới. Chỉ C gốc và F được chạy so sánh cặp trên 10 câu mới. Quy tắc triển khai ghi trước yêu cầu F không giảm cả hai metric so với C trên holdout này; F đạt điều kiện và trở thành mặc định. Chưa tinh chỉnh tiếp sau khi xem holdout mới.

## Kết quả

### Truy xuất trên benchmark v1

| Cấu hình | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Số chunk | Truy xuất TB (ms/câu) | Phí API |
|---|---|---:|---:|---:|---:|---:|
| A | dev | 6/15 (40.0%) | 8/15 (53.3%) | 865 | 26.46 | 0 USD |
| A | test | 1/5 (20.0%) | 2/5 (40.0%) | 865 | 24.59 | 0 USD |
| B | dev | 7/15 (46.7%) | 9/15 (60.0%) | 1.012 | 28.41 | 0 USD |
| B | test | 3/5 (60.0%) | 3/5 (60.0%) | 1.012 | 30.68 | 0 USD |
| C | dev | 8/15 (53.3%) | 9/15 (60.0%) | 1.012 | 23.71 | 0 USD |
| C | test | 3/5 (60.0%) | 4/5 (80.0%) | 1.012 | 25.21 | 0 USD |

Thời gian trong bảng là trung bình phần truy xuất/ranking trong lần chạy local, không gồm embedding query và khởi tạo model/process. Với dữ liệu nhỏ, số đo này có nhiễu và không phải kết quả load test.

Lần nạp A/B/C dùng chung **1.849 text khác nhau**, mất **82,42 giây embedding**, **84,72 giây toàn bộ ingestion**. Thời gian ghi DB A/B/C lần lượt khoảng **0,36 / 0,35 / 0,35 giây**. Các thời gian dùng chung không được tự phân bổ thành thời gian embedding riêng của từng strategy.

### Kết quả cải tiến: dev cũ và test mới

| Cấu hình | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Số chunk | Truy xuất/ranking TB (ms/câu) |
|---|---|---:|---:|---:|---:|
| C gốc | dev | 8/15 (53.3%) | 9/15 (60.0%) | 1.012 | 23.71 |
| D | dev | 6/15 (40.0%) | 9/15 (60.0%) | 535 | 28.32 |
| E | dev | 8/15 (53.3%) | 9/15 (60.0%) | 535 | 84.49 |
| F | dev | 10/15 (66.7%) | 11/15 (73.3%) | 535 | 1054.71 |
| C gốc | test | 2/10 (20.0%) | 4/10 (40.0%) | 1.012 | 26.96 |
| F | test | 8/10 (80.0%) | 10/10 (100.0%) | 535 | 969.62 |

Trên cùng 10 câu test mới, C → F tăng Hit@1 từ **2/10 lên 8/10** và Evidence Hit@3 từ **4/10 lên 10/10**. Kết quả C 4/5 trên test v1 và C 4/10 trên test v2 thuộc **hai tập câu hỏi khác nhau**; không gộp hoặc so trực tiếp tỷ lệ 80% cũ với 100% mới để suy ra mức tăng.

Chuẩn bị embedding và lưu collection mới mất **35,30 giây**, chưa gồm tải/khởi tạo reranker. F sử dụng thêm CPU để ranking; trên cùng test mới, thời gian trung bình khoảng **970 ms/câu**, so với **27 ms/câu** của C. Đạt 10/10 trong mẫu này không bảo đảm đúng mọi câu hỏi trên truyện hoặc corpus khác.

### Audit A/B/C trên cùng 5 câu test gốc

**Các nhãn dưới đây là đánh giá hỗ trợ AI theo rubric, chưa được người học xác minh độc lập.** Coherence dùng 10 vị trí nguồn giống nhau; metadata dùng 5 câu × top-3 = 15 record/configuration; grounding chấm đủ 5 câu. Cột 0/1/2 ghi số câu ở từng mức.

| Cấu hình | Coherence /2 (n=10) | Metadata đủ/đúng | Filter đúng phạm vi | Grounding 0/1/2 | Grounding TB /2 |
|---|---:|---:|---:|---|---:|
| A | 1.0 | 15/15 | 1/2 | 0 / 2 / 3 | 1.6 |
| B | 1.1 | 15/15 | 0/2 | 0 / 2 / 3 | 1.6 |
| C | 1.1 | 15/15 | 2/2 | 0 / 1 / 4 | 1.8 |

A/B không áp dụng filter nên tỷ lệ filter là mức tuân thủ ngẫu nhiên của kết quả, tách biệt với tính đúng của metadata. Một record có thể ghi đúng chapter/page thực tế nhưng vẫn nằm ngoài phạm vi mà câu hỏi yêu cầu.

### Audit bổ sung C/F trên cùng 5 câu test mới đầu tiên

| Cấu hình | Coherence /2 (cùng 10 vị trí) | Metadata đủ/đúng | Filter đúng phạm vi | Grounding 0/1/2 (5 câu mới) | Grounding TB /2 |
|---|---:|---:|---:|---|---:|
| C | 1.1 | 15/15 | 1/1 | 2 / 2 / 1 | 0.8 |
| F | 1.7 | 15/15 | 1/1 | 0 / 0 / 5 | 2.0 |

Grounding ở bảng này dùng h01–h05; không so trực tiếp mức grounding của F ở đây với A/B trên năm câu gốc. Coherence vẫn dùng chung 10 vị trí nguồn cho A/B/C/F.

### Đường dẫn trace, nhãn và cách chọn mẫu

- Trace v1 đầy đủ query, top-3 text, score, metadata, gold và nhãn tự động: [dev](../../starter/results/roshidere/benchmark/dev/traces.jsonl), [test](../../starter/results/roshidere/benchmark/test/traces.jsonl).
- Trace cải tiến: [dev candidates](../../starter/results/roshidere-v2/dev/traces.jsonl), [test C/F](../../starter/results/roshidere-v2/test/traces.jsonl); decision và hash model/index nằm cùng thư mục.
- Coherence: chọn mười page ID đầu đã sắp xếp trong corpus chuẩn bị: **14, 15, 16, 17, 20, 21, 22, 23, 24, 25**; lấy vị trí giữa trang, bỏ qua whitespace, rồi chọn chunk chứa vị trí đó có điểm bắt đầu sớm nhất. B/C có chunk giống nhau nên dùng cùng nhãn. Tổng 40 lượt chấm tương ứng 30 chunk ID khác nhau.
- [Coherence samples](../../starter/results/checkpoint_audit/coherence_samples.jsonl) và [labels](../../starter/results/checkpoint_audit/coherence_labels.csv); [grounding cases](../../starter/results/checkpoint_audit/grounding_cases.jsonl) và [labels](../../starter/results/checkpoint_audit/grounding_labels.csv); [metadata checks](../../starter/results/checkpoint_audit/metadata_checks.jsonl) và [labels](../../starter/results/checkpoint_audit/metadata_labels.csv).
- Tổng cộng **40 nhãn coherence, 75 record metadata, 25 nhãn grounding**. Đã trích xuất lại 39 trang vật lý PDF và kiểm tra 13 tiêu đề phần để đối chiếu provenance. Cả 75 record có source/page/section/offset nhất quán trong mẫu kiểm tra.
- [Protocol audit](../../starter/results/checkpoint_audit/protocol.json), [sample freeze](../../starter/results/checkpoint_audit/sample_freeze.json), [tổng hợp](../../starter/results/checkpoint_audit/summary.json), [báo cáo audit](../../starter/results/checkpoint_audit/REPORT.md).

Coherence: 0 = không hiểu được ý do thiếu chủ thể/cắt vụn; 1 = hiểu một phần nhưng thiếu ngữ cảnh hoặc biên cắt; 2 = hiểu được chủ thể và ý cục bộ đầy đủ. Grounding: 0 = không có evidence đáp ứng câu hỏi; 1 = có một phần nhưng thiếu dữ kiện/điều kiện/liên kết; 2 = top-3 cộng lại đủ để trả lời và truy nguồn. Không suy diễn grounding/coherence từ Hit@3.

Người chấm nhãn hiện tại là **Codex AI assistant**, cũng là bên hỗ trợ hiện thực và đã thấy kết quả trước đó; vì vậy có nguy cơ thiên lệch. View audit đã bỏ score/flag hit tự động nhưng không phải đánh giá mù hoàn toàn. Cột `human_*` còn trống; không khai các nhãn là đã được người học/giám khảo chấm.

## Phân tích và kết luận

### So sánh A–B, B–C và cải tiến

- **A–B:** Hit@3 dev tăng 8/15 → 9/15; test gốc tăng 2/5 → 3/5. Coherence trong mẫu chỉ tăng 1,0 → 1,1/2 vì các paragraph dài vẫn bị chia tại giới hạn 500 ký tự; chia theo paragraph không tự bảo đảm giữ trọn ý.
- **B–C:** cùng chunk/vector nên coherence giữ nguyên. Filter cải thiện Hit@1 dev 7/15 → 8/15, Hit@3 test gốc 3/5 → 4/5, tuân thủ filter test 0/2 → 2/2 và grounding gốc 1,6 → 1,8/2. Metadata giúp chọn phạm vi, không khôi phục phần text đã bị cắt mất.
- **C–F:** trên cùng test mới, Hit@3 tăng 4/10 → 10/10. Coherence cùng vị trí tăng 1,1 → 1,7/2; grounding trên cùng năm câu mới tăng 0,8 → 2,0/2. Tuy nhiên ranking tốn khoảng một giây và dùng thêm reranker. Dev ablation cho thấy D hoặc E riêng lẻ chưa vượt điểm chọn của C; F thắng sau bước rerank.
- `source/page` giúp đối chiếu trực tiếp tài liệu; `section` hữu ích khi nhiều chương lặp tên nhân vật. Hạn chế là đường dẫn source local khó tái lập trên máy khác nếu chưa có manifest/nguồn truy cập phù hợp.

### Ví dụ sai và trường hợp cần diễn giải thận trọng

1. **q17, v1, gold trang 233:** A trả trang 219/106/213; B trả 219/168/215. Các passage có bối cảnh vắng mặt/hội đồng nhưng thiếu câu giải thích ở Chapter 10. C lọc chapter và tìm được evidence tại trang 233 ở rank 2. Đây là lợi ích quan sát được của filter đã được cung cấp trong câu hỏi.
2. **q20, v1, gold trang 267:** các chunk 500 ký tự cắt ngang phần xác định món quà. C có thêm đoạn chuẩn bị bento ở trang 264 nhưng vẫn thiếu liên kết tường minh giữa món đó và chiếc túi được trao; audit chấm partial. Câu đúng trang không đồng nghĩa đủ bằng chứng.
3. **h03, v2, gold trang 228:** C có đúng trang nhưng fragment thiếu điều kiện trường vẫn phải quyết định; F trả passage dài hơn chứa cả điều kiện và lời giải thích, xếp đầu.
4. **c06/c07 của F, trang 21/22:** một chunk dừng ngay trước lời tuyên bố đã được dẫn vào, một chunk dừng tại lời đáp chưa đóng. Quy tắc dấu câu vẫn có thể cắt giữa lượt thoại dù retrieval trên các câu test đã tốt.

Audit cũng phát hiện **A/q16** có evidence hợp lệ tại trang **165 và 180** về điều kiện số thành viên, trong khi gold strict ban đầu chỉ đăng ký trang 213. Nếu chấp nhận đánh giá tương đương này sau khi người học xác minh, Hit@3 test gốc của A sẽ là 3/5 thay cho strict 2/5. [Ghi nhận bổ sung](../../starter/results/checkpoint_audit/equivalent_evidence_review.csv) được giữ riêng; không sửa âm thầm gold hoặc số liệu đã freeze. Điều này cho thấy metric quote-match có thể đánh giá thấp truy xuất hữu ích.

### Lựa chọn và điều kiện áp dụng

Trong ba cấu hình bắt buộc, **C** là lựa chọn theo dev. Sau thí nghiệm mở rộng, **F** là cấu hình active cho corpus này do được chọn trên dev và đạt quy tắc không giảm hiệu quả trên holdout mới. C vẫn là baseline đơn giản, phù hợp khi ưu tiên độ trễ thấp và ít thành phần.

Kết luận chỉ áp dụng cho corpus tiếng Anh và cách hỏi đã khảo sát. Hệ thống trả passage/bằng chứng cùng nguồn; chưa tạo câu trả lời bằng LLM. Score của F là logit ranking, có thể âm hoặc lớn hơn 1, không phải phần trăm tin cậy.

### Hạn chế và hướng cải tiến tiếp

- Test gốc chỉ 5 câu, test mới chỉ 10 câu; mỗi câu thay đổi tỷ lệ lần lượt 20 hoặc 10 điểm phần trăm. Bộ câu hỏi do AI soạn, nhiều câu từ đầu chương và chưa được xác minh độc lập.
- Metric strict chưa bao phủ đầy đủ trang/diễn đạt bằng chứng tương đương. Audit định tính có 10 vị trí coherence đầu corpus và 5 câu grounding/cohort, không đại diện toàn bộ tài liệu.
- Dữ liệu truyện có đại từ, lời thoại dài và ngữ cảnh liên trang; window hiện tại không vượt biên trang. Chưa OCR và chưa loại hết chú thích xen trong nội dung.
- Đo thời gian từ một lần chạy local, không bao gồm startup/embedding query trong cột truy xuất và không có load test. Không so sánh ngang các giai đoạn có phạm vi công việc khác nhau.
- Quyền xử lý/chia sẻ, manifest cuối cùng, thông tin học viên và xác minh độc lập các nhãn còn thiếu. Thư mục trace/chunk chứa văn bản phái sinh cần được xem xét trước khi đưa lên repo chia sẻ.
- Nếu mở rộng: duyệt gold và trang bằng chứng thay thế với người học; thêm câu hỏi đa dạng hơn; xử lý ranh giới lượt thoại/heading tốt hơn; đánh giá context liên trang nhưng giữ provenance; đo latency/memory có lặp lại. Tuning tiếp dựa trên test đã xem phải dùng **holdout mới** cho lần đánh giá độc lập tiếp theo.

### Công cụ AI và cách kiểm tra

Codex hỗ trợ viết code, chuẩn bị câu hỏi, phân tích kết quả và gán nhãn audit theo rubric. Các số liệu retrieval lấy từ trace chạy thật; không tự điền kết quả giả hoặc gán nhãn AI thành nhãn con người. Trong giai đoạn cải tiến đã chạy **27 kiểm thử code/database**, gồm coverage/offset của chunk, filter, SQL có tham số, rollback, cô lập bảng và nạp lại không trùng; sau khi promote còn kiểm tra CLI F mặc định và C gốc. Audit đối chiếu lại trực tiếp PDF. Các kiểm tra này không thay cho việc người học đọc hiểu code, xác minh gold/nhãn và giải thích lựa chọn.

### Các mục phải bổ sung trước khi nộp

- [ ] Điền họ tên, MSSV, lớp và đổi tên báo cáo thành `<MSSV>_<HoTen>.md` theo hướng dẫn lớp.
- [ ] Xác minh quyền xử lý/chia sẻ dữ liệu; hoàn thiện manifest với nguồn, ngày truy cập, giấy phép/quyền, snapshot và danh sách trang được tính.
- [ ] Người học rà soát nội dung hữu ích và xác minh độc lập câu hỏi/evidence cùng nhãn audit; chỉ điền `human_*` sau khi thực sự review.
- [ ] Kiểm tra dữ liệu/trích đoạn được phép chia sẻ, secrets và khả năng tái lập trên máy người chấm.
- [ ] Hoàn thiện [STUDENT.md](../../STUDENT.md), chốt commit, xác nhận người chấm truy cập được repo và nộp link qua kênh lớp. Deadline do giảng viên/coach thông báo.

Nhật ký và minh chứng: [experiment_log.csv](../../artifacts/experiment_log.csv), [improvement_log.csv](../../artifacts/improvement_log.csv), [trạng thái checkpoint](../../artifacts/checkpoint_status.json), [yêu cầu nộp bài](../../SUBMISSION.md).
