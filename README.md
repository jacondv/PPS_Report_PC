# Tunnel Concrete Thickness Analyzer

Phần mềm phân tích độ dày bê tông phun đường hầm từ dữ liệu Point Cloud (.ply)

## Tính năng

- **Tải và hiển thị 3D**: Mở file PLY với các trường scalar tùy chỉnh (distances)
- **Visualization tương tác**: Xoay, zoom, pan với bảng màu tùy chỉnh
- **Công cụ chọn vùng (Segment)**: Chọn vùng bằng cách kéo chuột hoặc theo khoảng độ dày
- **Tính toán tự động**:
  - Diện tích bề mặt (m²)
  - Thể tích bê tông (m³, lít)
  - Độ dày trung bình, min, max, độ lệch chuẩn
  - Phân bố độ dày theo tiêu chuẩn
- **Xuất báo cáo PDF**: Báo cáo đầy đủ với thông tin dự án và biểu đồ histogram

## Cài đặt

### Yêu cầu hệ thống
- Python 3.9 trở lên
- Windows / macOS / Linux

### Cài đặt thư viện


```bash
cd PPS_Report_PC
pip install -r requirements.txt
```

Hoặc sử dụng uv (khuyến nghị):

```bash
uv pip install -r requirements.txt
```

## Sử dụng

### Chạy ứng dụng

```bash
python main.py
```

### Quy trình làm việc

1. **Mở file PLY**: File > Mở file PLY... hoặc Ctrl+O
2. **Chọn trường độ dày**: Chọn trường scalar chứa dữ liệu độ dày (distances)
3. **Cài đặt ngưỡng**: Nhập độ dày tối thiểu và tối đa mong muốn
4. **Chọn vùng (tùy chọn)**: 
   - Bật "Chế độ chọn" và kéo chuột để chọn vùng
   - Hoặc chọn theo khoảng độ dày
5. **Tính toán**: Nhấn nút "Tính toán"
6. **Xuất báo cáo**: Nhấn "Xuất báo cáo PDF"

### Định dạng tên file

Phần mềm tự động phân tích thông tin từ tên file PLY theo format:

```
projectname#jobnumber#hhmmss#name.ply
```

Ví dụ: `TunnelA#JOB001#143025#Section1.ply`

- `projectname`: Tên dự án (TunnelA)
- `jobnumber`: Mã công việc (JOB001)  
- `hhmmss`: Thời gian scan (14:30:25)
- `name`: Tên segment (Section1)

### Phím tắt

| Phím | Chức năng |
|------|-----------|
| Ctrl+O | Mở file |
| Ctrl+E | Xuất PDF |
| Ctrl+Q | Thoát |
| R | Reset view |
| T | Top view |
| F | Front view |
| S | Side view |

## Cấu trúc project

```
PPS_Report_PC/
├── main.py              # Entry point
├── requirements.txt     # Dependencies
├── README.md           # Documentation
├── core/               # Core logic
│   ├── ply_loader.py   # PLY file loading
│   ├── filename_parser.py # Filename parsing
│   ├── calculator.py   # Area/volume calculation
│   └── segmentation.py # Point selection
├── gui/                # GUI components
│   ├── main_window.py  # Main window
│   └── viewer_3d.py    # 3D viewer
└── report/             # Report generation
    └── pdf_generator.py # PDF reports
```

## Lưu ý

- File PLY cần có trường scalar chứa độ dày (mặc định: "distances")
- Đơn vị độ dày trong file PLY phải là mm
- Đơn vị tọa độ (x, y, z) trong file PLY phải là mét

## License

MIT License
