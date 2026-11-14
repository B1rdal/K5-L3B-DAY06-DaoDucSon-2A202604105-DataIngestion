# Starter · PostgreSQL + pgvector

Bộ khởi động **tùy chọn** cho lab cá nhân. Docker Compose tạo PostgreSQL + pgvector local. Đã có ingestion PDF, chunking, embedding local, lưu/tìm kiếm bằng pgvector và benchmark retrieval dev/test. Có bộ audit hỗ trợ AI với nhãn/lý do tại `results/checkpoint_audit/`. Xem [USAGE.md](USAGE.md) để chạy pipeline hiện tại. Vẫn có thể chọn vector store tương đương theo [GUIDE.md](../GUIDE.md).

## Cấu trúc

```text
starter/
├── docker-compose.yml     # PostgreSQL 16 + pgvector, chỉ mở cổng local
├── init.sql               # bật extension khi tạo database mới
├── requirements.txt       # psycopg, pypdf, python-dotenv, FastEmbed
├── configs/roshidere.json # corpus, section và tham số A/B/C
├── .env.example           # cấu hình mẫu; copy thành .env
├── scripts/check_setup.py # kiểm tra kết nối và extension (đã chạy được)
├── src/
│   ├── models.py          # cấu trúc dữ liệu mẫu
│   ├── ingestion.py       # đọc / chuẩn hóa PDF và xuất JSONL theo trang
│   ├── corpus.py          # chọn trang, làm sạch footer và gắn section
│   ├── chunking.py        # fixed-size và paragraph, giữ offset
│   ├── embeddings.py      # model local FastEmbed/ONNX
│   ├── store.py           # pgvector, cosine search và metadata filter
│   ├── evaluation.py      # chấm evidence Hit@1/Hit@3
│   ├── benchmark.py       # freeze, chạy dev, chọn cấu hình, chạy test
│   ├── retrieval.py       # dense/keyword fusion và reranker local
│   ├── improvement.py     # thử D/E/F trên dev và holdout mới
│   ├── audit.py           # mẫu audit cố định, kiểm tra nguồn và tổng hợp nhãn AI
│   └── run.py             # các lệnh chunk, ingest, search
├── data/                  # bạn tự chuẩn bị corpus được phép sử dụng
└── results/               # lưu kết quả của bạn
```

## 1. Cài và kiểm tra database

Cần Docker Desktop hoặc Docker Engine + Compose, Python **3.11–3.14**, và mạng để tải image/dependencies lần đầu. Các lệnh sau chạy từ thư mục `starter/`:

```bash
cd starter
python3 -m venv .venv
```

Kích hoạt `.venv`: macOS/Linux dùng `source .venv/bin/activate`; Windows PowerShell dùng `.venv\Scripts\Activate.ps1`. Sau đó:

```bash
python -m pip install -r requirements.txt
# macOS/Linux: cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
```

Kỳ vọng: hiện tên database, phiên bản PostgreSQL và pgvector, sau đó `Setup OK`. Đây **chỉ là kiểm tra hạ tầng**, không phải kết quả benchmark. Docker dùng cổng `127.0.0.1:55433` và mật khẩu cố định **chỉ dùng local cho lab**; nếu cổng bận, sửa đồng thời port trong `docker-compose.yml` và `DATABASE_URL` trong `.env`. `init.sql` chỉ chạy khi volume mới được tạo; nếu database sẵn có chưa bật extension, xem log Docker và kiểm tra cấu hình thay vì xóa volume chứa dữ liệu.

Dừng container nhưng giữ dữ liệu:

```bash
docker compose -p day6_student_starter stop
```

## 2. Chọn embedding model

Adapter hiện tại dùng FastEmbed 0.9.1 với `BAAI/bge-small-en-v1.5` (384 chiều), chạy local bằng ONNX CPU. Tên model và cache nằm trong `configs/roshidere.json`; mặc định cache ở `F:/CodexTools/models/fastembed`. Không cần API key. Cùng model/weights và tokenizer được dùng cho A/B/C và query; hash cùng phiên bản được ghi trong `results/roshidere/ingest_stats.json`. Các ô API trong `.env.example` dành cho adapter mở rộng chưa hiện thực; **không commit `.env`**.

## 3. Hoàn thiện pipeline

1. Đặt corpus vào `data/` hoặc cung cấp manifest/hướng dẫn truy cập. Đọc [GUIDE.md](../GUIDE.md) về **30 trang nội dung**, quyền dữ liệu và metadata.
2. Dùng ingestion PDF bên dưới và hoàn thiện các hàm TODO còn lại trong `src/`. Lưu ID tài liệu, nguồn, trang/vị trí và ít nhất một trường filter có ích.
3. Xây ít nhất ba cấu hình; ví dụ A fixed-size, B theo đoạn, C như B nhưng có filter. Cần cùng corpus, model và benchmark; nạp lại không nhân đôi và xử lý chunk cũ khi dữ liệu đổi.
4. Tự viết ít nhất 20 câu hỏi kèm evidence, tách dev/test trước khi thử theo [BENCHMARK.md](../BENCHMARK.md). Lưu trace top-3 và báo cáo đủ năm tiêu chí.
5. Chạy `python -m src.run chunk`, `python -m src.run ingest` hoặc `python -m src.run search "câu hỏi"` từ thư mục `starter/`. Benchmark dùng `python -m src.benchmark`; xem [benchmark README](../benchmark/roshidere/README.md) về freeze và tái lập.

Lệnh search mặc định hiện dùng cấu hình cải tiến được chọn trên dev, qua `configs/active.json`. A/B/C gốc được giữ nguyên; dùng `--strategy C` để so sánh với baseline cũ. Xem [thí nghiệm cải tiến](../benchmark/roshidere-v2/README.md) về D/E/F, holdout mới và giới hạn.

Lưu code, cấu hình, kết quả và lệnh chạy để người chấm tái lập; không commit key, dữ liệu mật hoặc dữ liệu không có quyền chia sẻ.

## 4. Đọc PDF theo từng trang

Chạy từ `starter/`, sau khi kích hoạt `.venv`:

```powershell
python -m src.ingestion "F:\path\document.pdf" --document-id my-document --output results\pages.jsonl
```

`--source` có thể ghi URL nguồn; mặc định là đường dẫn PDF tuyệt đối. Bỏ `--output` để chỉ kiểm tra và in thống kê. Mỗi dòng JSONL chứa `document_id`, `source`, `page` (số trang vật lý, bắt đầu từ 1), `text` và `metadata`. Metadata ghi `extraction_status` (`ok`, `empty`, `error`), `character_count`, và thông tin lỗi nếu có. Trang rỗng/lỗi vẫn được giữ để không làm lệch số trang; cảnh báo và lỗi được ghi ra stderr. Lệnh trả mã lỗi nếu có trang trích xuất lỗi hoặc toàn bộ PDF không có text.

Ingestion chuẩn hóa Unicode và khoảng trắng, giữ dòng/đoạn; chưa OCR, loại header/footer, xác định chapter hay quyết định trang nào đủ điều kiện tính cho bài lab. Số trang có text không tự động bằng số trang nội dung hợp lệ. Chỉ xuất và chia sẻ nội dung được phép sử dụng.

Kiểm tra ingestion:

```powershell
python -m unittest discover -s tests -v
```

Các test database chỉ chạy khi có biến môi trường `DAY6_TEST_DATABASE_URL`. Chúng dùng schema tạm riêng và tự dọn sau khi kiểm tra.
