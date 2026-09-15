# Hướng dẫn sử dụng

## File trong bộ này
- `main_window.ui` — file giao diện, **mở bằng Qt Designer** để chỉnh sửa (kéo thả, đổi layout, đổi màu, thêm widget...).
- `main_window.py` — file logic, nạp giao diện bằng `uic.loadUi(...)` rồi gắn xử lý sự kiện. Bạn không cần chạy `pyuic5` để build lại — chỉ cần lưu `.ui`, chạy lại app là thấy thay đổi ngay.

## Việc cần làm trước khi chạy được
File `main_window.py` đang import các module mà bạn đã có sẵn trong project gốc nhưng không có trong đoạn code bạn gửi, hãy sửa lại đường dẫn import cho khớp với project của bạn:

```python
from layer_manager import LayerManager, Layer
from models import ProjectInfo, CalculationResult, ThicknessDistribution
from ply_loader import get_ply_fields, load_ply, parse_filename
from calculation_worker import CalculationWorker
from hotkeys_dialog import HotkeysDialog
from report import PDFGenerator
```

## Widget "viewer" (PointCloudViewer) — quan trọng
Trong `main_window.ui`, widget hiển thị point cloud được khai báo là **custom widget (promoted)**:

```xml
<customwidget>
  <class>PointCloudViewer</class>
  <extends>QWidget</extends>
  <header>pointcloud_viewer</header>
  <container>1</container>
</customwidget>
```

Nghĩa là khi nạp `.ui`, PyQt sẽ tự `from pointcloud_viewer import PointCloudViewer`.
- Nếu file chứa class `PointCloudViewer` của bạn tên khác (ví dụ `viewer_widget.py`), mở `main_window.ui` bằng Qt Designer → chuột phải vào widget `viewer` → **Promote to...** → sửa lại đúng tên module/class.
- **Không đổi objectName "viewer"** — code logic gọi `self.viewer....` dựa vào tên này.

## Quy tắc khi chỉnh trong Qt Designer
- Có thể sửa thoải mái: kích thước, vị trí, màu sắc, thêm group box/label mới, đổi text hiển thị...
- **Không được đổi `objectName`** của các widget đang dùng trong `main_window.py`, ví dụ:
  `lbl_filename, lbl_project, lbl_job, lbl_time, cmb_dist_field, spin_target_min, spin_target_max,
  spin_point_size, cmb_colormap, spin_sel_min, spin_sel_max, btn_select_range, btn_polygon,
  lbl_sel_count, btn_add_seg, btn_clear_sel, list_layers, lbl_current_layer, btn_calculate,
  btn_export_pdf, progress_bar, lbl_area, lbl_target_coverage, lbl_volume, lbl_mean_thickness,
  lbl_min_thickness, lbl_max_thickness, lbl_std_thickness, lbl_num_points, lbl_below, lbl_within,
  lbl_above, viewer`
  Các action menu/toolbar: `actionOpen, actionExportPdf, actionExit, actionTopView, actionBottomView,
  actionFrontView, actionBackView, actionRightView, actionLeftView, actionIsoView, actionAbout,
  actionHotkeys, actionToolbarOpen, actionResetView, actionToolbarCalculate, actionToolbarExport`
- Nếu lỡ đổi tên, chỉ cần sửa lại tên tương ứng trong `_connect_signals()` của `main_window.py`.

## Chạy thử
```bash
pip install PyQt5
python main_window.py
```
(cần có đầy đủ các module phụ thuộc nêu trên thì mới chạy được)

## (Tuỳ chọn) Build .ui thành .py tĩnh
Nếu sau này bạn muốn build `.ui` thành file `.py` cố định (không load runtime) để dễ debug/tăng tốc khởi động:
```bash
pyuic5 main_window.ui -o ui_main_window.py
```
Khi đó trong `main_window.py`, thay:
```python
uic.loadUi(UI_FILE, self)
```
bằng:
```python
from ui_main_window import Ui_MainWindow
...
self.ui = Ui_MainWindow()
self.ui.setupUi(self)
```
và sửa các `self.xxx` thành `self.ui.xxx`. Cách dùng `uic.loadUi` trực tiếp (như hiện tại) thường tiện hơn vì không cần build lại mỗi lần sửa `.ui`.
