# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Setup bài làm

**Đào Đức Sơn · MSSV 2A202604105 · Lớp L3B**

Bài làm dùng Python, embedding local `BAAI/bge-small-en-v1.5` (384 chiều) và PostgreSQL + pgvector. Dữ liệu, cấu hình và kết quả: [manifest](data/manifest.json), [báo cáo cá nhân](report/individual/2A202604105_DaoDucSon.md), [kết quả](results/README.md), [danh mục minh chứng](SUBMISSION_GUIDE.md).

### 1. Cài môi trường và bật database

Cần Python 3.13, Docker Desktop đang chạy và Docker Compose. Clone repo vào `F:\Github\K5-L3B-Day06-DataIngestionEngineering` nếu chưa có; các lệnh dưới đây chạy trong PowerShell. Môi trường Python và cache model của cấu hình hiện tại nằm trên F:. Lần tải model đầu tiên cần mạng; inference chạy local, không cần API key.

```powershell
cd "F:\Github\K5-L3B-Day06-DataIngestionEngineering\starter"
if (-not (Test-Path .venv\Scripts\python.exe)) { py -3.13 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose -p day6_student_starter up -d --wait
.\.venv\Scripts\python.exe scripts\check_setup.py
```

Compose lưu dữ liệu trong volume `pg_data` và mở database `day6_lab` tại `127.0.0.1:55433`; `.env.example` có sẵn connection string cho môi trường local. Bộ phiên bản đã đo trên Windows/Python 3.13 nằm trong [requirements-lock.txt](starter/requirements-lock.txt). Khi không dùng nữa, chạy `docker compose -p day6_student_starter stop` từ `starter/`.

Trên máy đã cài sẵn của học viên có thể double-click `F:\CodexTools\Start Day6.cmd`, rồi bỏ qua bước tạo môi trường và cài package ở trên.

### 2. Khôi phục dữ liệu và tạo index trên database mới

Corpus là **Roshidere, Vol. 10 — Glucose Translations**. PDF và full-text evidence được giữ local; bản chia sẻ chứa source/page/offset/hash. Dùng bản PDF khớp SHA-256 trong manifest và đổi đường dẫn dưới đây nếu file nằm ở nơi khác. Chi tiết ánh xạ nguồn: [data/access.md](data/access.md).

Từ `starter/`:

```powershell
.\.venv\Scripts\python.exe scripts\submission.py restore --pdf "F:\FDownload\MainDownload\Roshidere, Vol. 10 - Glucose Translations.pdf"
.\.venv\Scripts\python.exe -m src.run ingest
.\.venv\Scripts\python.exe -m src.run search "Why was the piano club demoted?" --strategy C
```

Restore kiểm tra hash và khôi phục 17 file trang/chunk/câu hỏi/trace. Ingest tạo lại A/B/C bằng embedding thật. Nếu database trên máy hiện tại đã có index, chỉ cần chạy search. Kết quả hiển thị thành các khung passage có chapter và trang PDF; đây là truy xuất evidence, chưa sinh câu trả lời LLM.

### 3. Dùng chiến lược F đã cải tiến

Máy hiện tại đã có bảng `day6_chunks_v2`; search mặc định dùng F (hybrid + reranker local). Trên database mới, sau bước 2, dùng cấu hình có thư mục output riêng để tạo lại index F và giữ kết quả thí nghiệm gốc:

```powershell
$rebuildConfig = Get-Content configs\roshidere-v2.json -Raw | ConvertFrom-Json
$rebuildConfig.output_dir = "results/roshidere-v2-rebuild"
$rebuildJson = $rebuildConfig | ConvertTo-Json -Depth 20
[IO.File]::WriteAllText((Join-Path $PWD.Path "configs\roshidere-v2-rebuild.json"), $rebuildJson, [Text.UTF8Encoding]::new($false))
.\.venv\Scripts\python.exe -m src.improvement prepare --config configs\roshidere-v2-rebuild.json
.\.venv\Scripts\python.exe -m src.run --config configs\roshidere-v2-rebuild.json search "Why was the piano club demoted?" --strategy F
```

Lệnh prepare dùng một thư mục output mới chưa tồn tại. Các truy vấn thường dùng trên máy đã có index:

```powershell
.\.venv\Scripts\python.exe -m src.run search "YOUR QUESTION"
.\.venv\Scripts\python.exe -m src.run search "YOUR QUESTION" --section chapter_5
.\.venv\Scripts\python.exe -m src.run search "YOUR QUESTION" --strategy C
```

Chỉ dùng filter khi câu hỏi/ngữ cảnh cung cấp section. Cấu hình: [A/B/C](starter/configs/roshidere.json), [D/E/F](starter/configs/roshidere-v2.json), [mặc định](starter/configs/active.json).

Terminal tự dùng màu khi được hỗ trợ, xuống dòng passage theo chiều rộng cửa sổ và hiển thị tổng thời gian gồm tải model. Thêm `--details` để xem score/chunk ID, `--json` để xuất JSON đầy đủ cho script, hoặc `--no-color` để tắt màu. Score là giá trị xếp hạng, không phải phần trăm độ tin cậy.

```powershell
.\.venv\Scripts\python.exe -m src.run search "YOUR QUESTION" --details
.\.venv\Scripts\python.exe -m src.run search "YOUR QUESTION" --json
```

### 4. Kiểm tra và xem benchmark

```powershell
.\.venv\Scripts\python.exe scripts\submission.py check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Kiểm thử database chạy khi có `DAY6_TEST_DATABASE_URL`; chúng dùng schema test riêng. Kết quả đã lưu gồm 20 câu v1 (15 dev/5 test), A/B/C, metrics, trace và audit. Thí nghiệm cải tiến có 10 câu test mới. Xem [benchmark v1](benchmark/roshidere/README.md), [v2](benchmark/roshidere-v2/README.md) và [results](results/README.md) để tái lập từng pha vào thư mục kết quả mới, với cùng snapshot dữ liệu/model. Thông tin thí nghiệm gốc và bản sửa metadata được giữ riêng trong artifacts.

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.
