# Jacon PPS Report

Phần mềm phân tích độ dày bê tông phun đường hầm (shotcrete) từ dữ liệu quét Point Cloud (.ply) đã được so sánh với thiết kế — hiển thị 3D, chọn vùng/tách segment, đo đạc, ghi chú, tính toán thống kê và xuất báo cáo PDF.

Xem hướng dẫn sử dụng đầy đủ (có hình minh họa) ngay trong ứng dụng qua `Help → User Guide`.

## Tính năng

- **Hiển thị 3D tương tác**: tải Point Cloud (.ply), tô màu theo chiều dày, xoay/zoom/pan, các góc nhìn chuẩn (Top/Front/Iso...)
- **Chọn vùng & tách Segment**: Polygon/Rectangle/Lasso, lọc theo khoảng chiều dày, Extract Inside/Outside
- **Đo đạc**: khoảng cách giữa 2 điểm, diện tích bề mặt thực (Ball-Pivoting)
- **Note & Annotation**: ghi chú 2D cố định trên màn hình, hoặc neo vào điểm trên cloud — chọn/di chuyển/sửa/xóa trực tiếp trong khung nhìn 3D
- **Project file (.ppsproj)**: lưu/mở lại toàn bộ phiên làm việc (segment, ghi chú, đo đạc, target range, camera)
- **Tính toán thống kê**: diện tích bề mặt, thể tích, chiều dày trung bình/min/max/độ lệch chuẩn, phân bố theo Target Min/Max
- **Xuất báo cáo PDF**: kèm ảnh chụp 3D, bảng số liệu, thông tin dự án — tùy chọn tự động mở file sau khi xuất

## Cài đặt

### Yêu cầu hệ thống
- Python 3.9 trở lên
- Windows / macOS / Linux

### Cài đặt thư viện

```bash
cd PPS_Report_PC
pip install -r requirements.txt
```

Hoặc dùng `uv` (khuyến nghị):

```bash
uv pip install -r requirements.txt
```

## Sử dụng

### Chạy ứng dụng

```bash
python main.py
```

### Quy trình làm việc

1. **Mở file PLY**: `File → Open PLY…` (`Ctrl+O`)
2. **Chỉnh Target Min/Max** (mm) ở khung Properties — mặc định lấy từ `job_info.json` cạnh file PLY nếu có, hoặc 40–60mm
3. **Chọn vùng / tách Segment** (tùy chọn): dùng công cụ Select, sau đó Extract Inside/Outside
4. **Đo đạc / Ghi chú** (tùy chọn): công cụ Distance, Area, Note, Annotation
5. **Tính toán**: nút **Calculate** trên toolbar
6. **Xuất báo cáo**: nút **Export PDF…** (`Ctrl+E`)

Chi tiết từng bước, kèm ảnh minh họa, xem trong `Help → User Guide` khi chạy ứng dụng.

### Định dạng tên file

Nếu file nằm theo cấu trúc thư mục:

```
.../Projects/<ProjectName>/<JobNumber>/<JobNumber>#<yyyyMMdd_hhmmss>#<SegmentName>.ply
```

phần mềm tự động đọc project name, job number, thời gian scan và tên segment để hiển thị và đặt tên file PDF mặc định. Nếu không theo đúng cấu trúc này, file vẫn tải bình thường (chỉ là các trường project/job sẽ lấy theo tên thư mục/file thô).

### Phím tắt chính

| Phím | Chức năng |
|---|---|
| `1`–`6` hoặc `V S D A N G` | Navigate / Select / Distance / Area / Note / Annotation |
| `Esc` | Hủy thao tác dở dang; bấm lần nữa để về Navigate |
| `Delete` | Xóa đối tượng đang chọn (khi ở Navigate) |
| `Ctrl+Z` / `Ctrl+Y` | Undo / Redo |
| `Ctrl+O` / `Ctrl+S` / `Ctrl+Shift+S` / `Ctrl+Shift+O` | Open PLY / Save Project / Save Project As / Open Project |
| `Ctrl+E` | Export PDF |
| `Ctrl+A` | Select All |

Danh sách đầy đủ xem trong User Guide (`Help → User Guide`).

## Cấu trúc project

```
PPS_Report_PC/
├── main.py                # Entry point (thin — wiring thật nằm trong src/pps)
├── build.spec             # PyInstaller spec (PySide6 + layout src/)
├── requirements.txt
├── src/pps/
│   ├── app/                # Bootstrap: QApplication, settings, logging
│   ├── core/                # Model + logic thuần: PLY loader, calculator, layers, filename/job-info parsing
│   ├── scene/                # Document (state trung tâm), commands (undo/redo), project file I/O
│   ├── render/                # VTK actors: layer/note/measurement renderer, labels, color legend, picking
│   ├── tools/                # Tool framework: Navigate, Select, Distance, Area, Note, Annotation
│   ├── ui/                # MainWindow, docks, toolbars, dialogs (Qt only, không chứa business logic)
│   ├── report/                # PDF report generator (ReportLab + Jinja2/wkhtmltopdf)
│   └── utils/                # Helper chung (resource path, timing…)
├── tests/                  # pytest + pytest-qt
├── sample/                 # File PLY mẫu để test/demo
└── docs/REFACTOR_PLAN.md  # Kế hoạch & lịch sử refactor
```

## Lưu ý

- File PLY cần có trường scalar chứa độ dày (mặc định: `distances`), đơn vị mm; tọa độ (x, y, z) đơn vị mét.
- Log ứng dụng (kể cả lỗi chưa xử lý) được ghi vào file dưới thư mục người dùng — Windows: `%LOCALAPPDATA%\TunnelAnalyzer\logs\app.log`.
- **Lần đầu chạy file `.exe` đã đóng gói**, Windows Defender có thể quét khá lâu (file chưa ký số, bộ DLL VTK/Open3D/Qt lớn) khiến app có vẻ "treo" vài chục giây tới cả phút ở lần khởi động đầu tiên — đây là hành vi của Defender, không phải lỗi app; các lần chạy sau sẽ nhanh bình thường. Nếu cần, thêm exclusion cho thư mục cài đặt vào Windows Defender.

## License

MIT License

## Build (đóng gói .exe)

```bash
pip install pyinstaller
Remove-Item -Recurse -Force build, dist
pyinstaller build.spec
```

Kết quả nằm trong `dist/Jacon PPS Report Generator/`.
