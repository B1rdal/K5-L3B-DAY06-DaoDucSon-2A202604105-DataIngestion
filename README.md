# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Setup bài làm

**Đào Đức Sơn · MSSV 2A202604105 · Lớp L3B**

Bài làm dùng Python, embedding local `BAAI/bge-small-en-v1.5` (384 chiều) và PostgreSQL + pgvector. Dữ liệu, cấu hình và kết quả: [manifest](data/manifest.json), [báo cáo cá nhân](report/individual/2A202604105_DaoDucSon.md), [kết quả](results/README.md), [danh mục minh chứng](SUBMISSION_GUIDE.md).

### 1. Setup tự động trên Windows

Cần Python 3.13, Docker Desktop đang chạy và kết nối mạng cho lần tải package/model đầu tiên. Clone hoặc giải nén repo vào **bất kỳ thư mục nào**; tên ổ đĩa và khoảng trắng trong đường dẫn đều được hỗ trợ.

Double-click [Setup Day6.cmd](Setup%20Day6.cmd) tại thư mục gốc repo. Hoặc mở PowerShell tại thư mục đó và chạy:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
```

Script tự xác định vị trí repo, tạo `starter/.venv`, cài dependencies, tạo `.env` nếu chưa có, bật PostgreSQL + pgvector và chuẩn bị index A/B/C/F. Nếu thiếu dữ liệu local, script hỏi đường dẫn PDF; có thể chọn file ở bất kỳ thư mục nào. PDF phải khớp SHA-256 trong [manifest](data/manifest.json). Chi tiết nguồn và cách khôi phục: [data/access.md](data/access.md).

Các index đã có và đúng nội dung được dùng lại. Khi cần dựng mới, script đọc các chunk đã lưu để tạo embedding thật và ghi database; số đo, trace và kết quả thí nghiệm gốc được giữ nguyên.

### 2. Chạy tìm kiếm

Double-click [Search Day6.cmd](Search%20Day6.cmd), rồi nhập câu hỏi. Launcher tự tìm môi trường Python và bật database. Hoặc từ thư mục gốc repo:

```powershell
cd starter
.\.venv\Scripts\python.exe -m src.run search "Why was the piano club demoted?"
.\.venv\Scripts\python.exe -m src.run search "YOUR QUESTION" --section chapter_5
.\.venv\Scripts\python.exe -m src.run search "YOUR QUESTION" --strategy C
```

Search mặc định dùng F (hybrid + reranker local). Terminal hiển thị các khung passage có chapter, trang PDF và tổng thời gian gồm tải model. Đây là truy xuất evidence, chưa sinh câu trả lời LLM. Chỉ dùng filter khi câu hỏi/ngữ cảnh cung cấp section.

Thêm `--details` để xem score/chunk ID, `--json` để xuất JSON đầy đủ cho script, hoặc `--no-color` để tắt màu. Score là giá trị xếp hạng, không phải phần trăm độ tin cậy.

### 3. Đường dẫn và cấu hình local

- Môi trường Python: `starter/.venv` trong bản repo đang dùng.
- Cache embedding/reranker mặc định: `starter/.cache/fastembed` và `starter/.cache/rerankers`; các đường dẫn này luôn tính từ `starter/`, không phụ thuộc thư mục đang mở terminal.
- Có thể đặt `DAY6_MODEL_CACHE` và `DAY6_RERANKER_CACHE` trong `starter/.env` để chọn cache khác hoặc dùng lại model đã tải. Giá trị tuyệt đối hoặc tương đối đều được hỗ trợ. `.env` và `.cache` được ignore khỏi Git.
- Database mặc định: `127.0.0.1:55433`, tên `day6_lab`, dữ liệu trong Docker volume `pg_data`. Connection string mẫu nằm trong `.env.example`; Compose dùng đường dẫn tương đối tới `init.sql`.
- Đường dẫn nguồn trong trace là provenance của lần chạy gốc; chúng không phải đường dẫn cài đặt và không được dùng để mở PDF trên máy người chấm. Đối số `--pdf` cung cấp vị trí file thực tế khi restore.

### 4. Setup thủ công và kiểm tra

Từ thư mục gốc repo, trong PowerShell:

```powershell
cd starter
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose -p day6_student_starter up -d --wait
.\.venv\Scripts\python.exe scripts\check_setup.py
.\.venv\Scripts\python.exe scripts\submission.py restore --pdf "<path-to-matching-PDF>"
.\.venv\Scripts\python.exe scripts\prepare_database.py
.\.venv\Scripts\python.exe scripts\submission.py check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Trên macOS/Linux: dùng `python3 -m venv .venv`, cài `requirements.txt`, và thay `.venv\Scripts\python.exe` bằng `.venv/bin/python`. Các launcher `.cmd`/`.ps1` dành cho Windows; code Python dùng đường dẫn theo vị trí repo trên mọi nền tảng.

Kiểm thử database chạy khi có `DAY6_TEST_DATABASE_URL`; chúng dùng schema test riêng. Kết quả đã lưu gồm 20 câu v1 (15 dev/5 test), A/B/C, metrics, trace và audit. Thí nghiệm cải tiến có 10 câu test mới. Xem [benchmark v1](benchmark/roshidere/README.md), [v2](benchmark/roshidere-v2/README.md) và [results](results/README.md) để tái lập từng pha vào thư mục kết quả mới, với cùng snapshot dữ liệu/model. Thông tin thí nghiệm gốc và bản sửa metadata được giữ riêng trong artifacts.

Dừng database nhưng giữ dữ liệu bằng `docker compose -p day6_student_starter stop` từ `starter/`.

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
