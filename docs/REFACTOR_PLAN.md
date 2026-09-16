# Kế hoạch tái cấu trúc UI/UX + Hệ thống Tool tương tác Cloud

Tài liệu điều hướng cho toàn bộ đợt cải tiến. Cập nhật khi có quyết định mới.
Nhánh làm việc: `refactor/project-restructure` (tách từ `office`).

---

## 0. Quyết định đã chốt (2026-09-16)

| Chủ đề | Quyết định |
|---|---|
| Qt binding | **Migrate sang PySide6** (Qt 6). Gỡ PyQt5 khỏi `.venv` để `qtpy`/`pyvistaqt` không chọn nhầm. |
| Neo annotation / số đo | **Neo vào điểm 3D trên cloud**, label bám theo khi xoay/zoom/pan. |
| Lưu project | **Có** — định dạng project file mới. Không cần tương thích ngược (chưa từng có file cũ). |
| Undo/Redo | **Có, đầy đủ** (Ctrl+Z / Ctrl+Y) — dùng `QUndoStack`, command pattern từ đầu. |
| Report | Số đo/chú thích **chỉ xuất hiện trong ảnh chụp viewer**. Không thêm section, không đổi số liệu. |
| Cách dựng UI | **Viết bằng code Python**, bỏ file `.ui` / `uic.loadUi`. |
| Build exe | Chỉ cần build PyInstaller ở **phase cuối**. Giữa chừng chạy từ source. |

Ràng buộc bất biến:
- Không đổi logic tính toán (diện tích, thể tích, mean/min/max/std, phân bố) và số liệu trong PDF.
- Viết lại hoàn toàn phần tool tương tác cloud, không tái sử dụng code cũ.
- Tên tool theo chức năng nghiệp vụ, không theo hình dạng.
- Giữ thư viện chính: PySide6, pyvista/pyvistaqt, VTK, numpy, plyfile, reportlab, matplotlib (+ open3d cho BPA, jinja2/pdfkit cho HTML→PDF — đang dùng, giữ).

---

## 1. Hiện trạng: Giữ / Viết lại / Xoá

### 1.1 GIỮ NGUYÊN LOGIC (chỉ di chuyển file, đổi `print` → `logging`, không đổi thuật toán)

| File hiện tại | Ghi chú |
|---|---|
| `core/calculator.py` | **Đóng băng.** `calculate_area_and_volume`, `calculate_thickness_distribution`, `CalculationResult`, `ThicknessDistribution`. Xem §7 về bẫy mutation tại chỗ. |
| `core/helper.py` | BPA surface area qua open3d. Đóng băng (radii, voxel, outlier, normals). |
| `core/ply_loader.py` | `load_ply` (kể cả bước abs() distances trong khoảng ±25 và < -25), `get_ply_fields`, `PointCloudData`. |
| `core/filename_parser.py` | `parse_filename`, `ProjectInfo`. Xoá hàm chết `parse_filename1`. |
| `core/layer_manager.py` | `Layer`, `LayerManager`, `SEGMENT_COLORS`. Mở rộng thêm field (id, nguồn gốc) nhưng giữ API cũ. |
| `report/**` | HTML→PDF (`html_pdf_generator.py`, `report_template.html`, `_find_wkhtmltopdf`), legacy reportlab. Giữ nguyên nội dung; chỉ sửa đường dẫn tìm `packages/wkhtmltox` và logo theo layout mới. |
| `utils/path_helper.py`, `utils/utils.py` | `resource_path`, `timeit`. Cập nhật base path theo layout `src/`. |
| Logic đọc `job_info.json` | Đang nằm trong `MainWindow._load_file` (gui/main_window.py:522-541). Tách ra `core/job_info.py`, **giữ nguyên default** (không có file → 40/60; có file → target±tolerance, default 30/10). |
| `CalculationWorker` | Thứ tự gọi và việc dùng chung mảng `distances` giữa 2 hàm phải giữ y nguyên (§7). |

### 1.2 VIẾT LẠI HOÀN TOÀN

| File hiện tại | Thay bằng |
|---|---|
| `gui/viewer_3d.py` | `render/viewport.py`, `render/layer_renderer.py`, `render/overlay.py`, `render/labels.py`, `render/picking.py`, `render/camera.py` |
| `gui/vtk_polygon_picker.py` | `tools/region_select.py` (+ framework `tools/base.py`, `tools/manager.py`) |
| `gui/annotation/*` | `scene/annotations.py`, `tools/note.py`, `render/labels.py` |
| `gui/main_window.py` (+ `.ui`, `gui/ui/`, `qt/`) | `ui/main_window.py` + docks/toolbars/dialogs/theme |
| `main.py` | `src/pps/app/application.py` + `main.py` mỏng ở root cho PyInstaller |
| `core/segmentation.py` | `scene/selection.py` (index-based, có Replace/Add/Subtract). File cũ gần như dead code (viewer không dùng). |

### 1.3 XOÁ (dead code / trùng lặp)

- `gui/main_window(old).py`, `gui/viewer_3d(old).py`
- `qt/` (main_window.py, .ui, backup, HUONG_DAN.md), `gui/ui/`, `gui/main_window.ui`
- `gui/annotation/annotation_builder.py` (file rỗng)
- `core/tests/test.py` (thay bằng `tests/`)
- `run.vbs` (không dùng launcher script — chạy exe trực tiếp)
- `usb_copier.py`, `export_excel.py`: script độc lập không liên quan app → chuyển vào `scripts/` (không xoá).

---

## 2. Kiến trúc mới

### 2.1 Nguyên tắc

```
UI (PySide6 widgets)  ──lệnh──▶  Scene/Document (dữ liệu + QUndoStack)
        ▲                                   │ signals (layer_added, annotation_changed, selection_changed…)
        │                                   ▼
Tools (xử lý input) ──command──▶  Render (VTK actors đồng bộ 1 chiều từ Document)
```

- **Document là nguồn sự thật duy nhất.** Tool không tạo actor lâu dài, không sửa UI. Tool chỉ tạo `QUndoCommand` đẩy vào stack; renderer nghe signal từ Document để cập nhật actor.
- **core/** không import Qt, không import VTK. Test được bằng pytest thuần.
- **render/** không biết Document là gì ngoài các dataclass; không tính toán nghiệp vụ.
- **ui/** chỉ điều phối: nhận click → gọi Document/ToolManager; nhận signal → cập nhật widget.

### 2.2 Cấu trúc thư mục

```
PPS_Report_PC/
├── main.py                       # entry mỏng: from pps.app import run; run()
├── pyproject.toml                # package "pps", deps, pytest config
├── build.spec                    # PyInstaller (cập nhật phase cuối)
├── requirements.txt
├── docs/REFACTOR_PLAN.md
├── scripts/                      # usb_copier.py, export_excel.py (không thuộc app)
├── tests/
│   ├── golden/sample_baseline.json   # số liệu chuẩn sinh từ code CŨ trên file sample
│   ├── test_calculator_golden.py
│   ├── test_ply_loader.py
│   ├── test_filename_parser.py
│   ├── test_job_info.py
│   ├── test_selection.py
│   ├── test_commands.py
│   ├── test_project_io.py
│   ├── test_tool_manager.py          # pytest-qt, QT_QPA_PLATFORM=offscreen
│   └── test_report_context.py        # project_rows / chart input không đổi
└── src/pps/
    ├── __init__.py
    ├── __main__.py               # python -m pps
    ├── app/
    │   ├── application.py        # QApplication, Hi-DPI, logging, theme, MainWindow
    │   └── settings.py           # QSettings wrapper (typed)
    ├── core/                     # thuần Python, không Qt/VTK
    │   ├── models.py             # PointCloudData, ProjectInfo, CalculationResult, ThicknessDistribution
    │   ├── ply_loader.py         # (giữ)
    │   ├── filename_parser.py    # (giữ)
    │   ├── calculator.py         # (đóng băng)
    │   ├── surface_area.py       # helper.py (đóng băng)
    │   ├── analysis.py           # run_analysis(points, distances, tmin, tmax) — tái tạo đúng trình tự Worker cũ
    │   ├── job_info.py           # đọc job_info.json → (target_min, target_max)
    │   └── layers.py             # Layer, LayerManager (giữ + mở rộng)
    ├── scene/
    │   ├── document.py           # Document(QObject): layers, selection, annotations, measurements, undo_stack, signals
    │   ├── selection.py          # Selection: {layer_id: bool mask}; replace/add/subtract/invert; to_layer_sources()
    │   ├── annotations.py        # NoteAnnotation dataclass (anchor xyz, text, offset px, style)
    │   ├── measurements.py       # DistanceMeasurement, AreaMeasurement dataclass
    │   ├── commands.py           # QUndoCommand: AddSegment, RemoveLayer, RenameLayer, AddNote, MoveNote, EditNote, DeleteNote, AddMeasurement, DeleteMeasurement
    │   └── project_io.py         # save/load .ppsproj
    ├── render/
    │   ├── viewport.py           # QWidget bọc pyvistaqt QtInteractor; expose renderer, overlay renderer, screenshot()
    │   ├── interactor_style.py   # Camera style + hook chuyển sự kiện cho ToolManager
    │   ├── layer_renderer.py     # Layer → actor; màu 4 ngưỡng y hệt assign_colors() cũ
    │   ├── overlay.py            # Renderer layer 1: HUD, preview polygon/rect/lasso, hint text; ScratchGroup per tool
    │   ├── labels.py             # Label neo 3D (vtkBillboardTextActor3D + leader 2D + anchor marker)
    │   ├── picking.py            # project_to_screen (vectorized, cache theo camera MTime), pick_point(x,y), points_in_polygon
    │   └── camera.py             # top/bottom/front/back/left/right/iso/reset
    ├── tools/
    │   ├── base.py               # Tool ABC, ToolContext, PointerEvent, KeyEvent, ToolState
    │   ├── manager.py            # ToolManager: 1 tool active, exclusive routing, cleanup bắt buộc
    │   ├── navigate.py           # NavigateTool (mặc định)
    │   ├── region_select.py      # RegionSelectTool (polygon / rectangle / lasso; Replace/Add/Subtract)
    │   ├── measure_distance.py   # MeasureDistanceTool
    │   ├── measure_area.py       # MeasureAreaTool
    │   └── note.py               # NoteTool (đặt / kéo / sửa / xoá)
    ├── ui/
    │   ├── main_window.py        # QMainWindow: docks, toolbars, menus, statusbar, wiring
    │   ├── theme/dark.qss, theme.py, icons/*.svg
    │   ├── toolbars/tool_toolbar.py, view_toolbar.py
    │   ├── docks/project_dock.py        # cây layer (checkbox hiện/ẩn, context menu, rename)
    │   ├── docks/selection_dock.py      # chế độ chọn, lọc theo độ dày, tạo segment, đảo/bỏ chọn, số điểm
    │   ├── docks/properties_dock.py     # thông tin file/job, target, point size, style ghi chú
    │   ├── docks/results_dock.py        # kết quả tính + phân bố + progress
    │   ├── docks/objects_dock.py        # danh sách ghi chú & số đo (chọn, xoá, ẩn/hiện)
    │   ├── dialogs/note_editor.py, shortcuts_dialog.py, about_dialog.py
    │   ├── widgets/color_button.py, elided_label.py, stat_row.py
    │   └── workers.py                   # CalculationWorker, AreaMeasureWorker (QThread)
    ├── report/                   # di chuyển nguyên từ report/ (kèm assets/, templates/)
    └── utils/path_helper.py, logging_setup.py, timing.py
```

`report/packages/wkhtmltox/` (bị gitignore) chuyển sang `src/pps/report/packages/` và `_find_wkhtmltopdf` cập nhật base dirs tương ứng.

---

## 3. Hệ thống Tool tương tác (viết mới)

### 3.1 Vấn đề của hệ cũ (để không lặp lại)

- Hai đường dispatch sự kiện chạy song song: viewer đăng ký observer vĩnh viễn cho annotation tool, `VTKPolygonPicker` tự `AddObserver` thêm khi start → cả hai cùng nhận event.
- Tool chọc thẳng vào private của viewer (`_restore_camera`, `_reset_toolbar_buttons`, `_iren.SetInteractorStyle(None)`), quản lý nút toolbar từ trong tool.
- Không có state machine rõ; `LineAnnotation.on_left_click` gọi `self.reset()` không tồn tại → crash khi Cancel dialog.
- Preview actor và actor thật lẫn lộn trong cùng list, xoá bằng `try/except: pass`.
- Annotation neo pixel, không đi theo cloud.

### 3.2 Thiết kế

**Một nguồn sự kiện duy nhất.** `ToolManager` cài `eventFilter` lên widget interactor của viewport (mức Qt, không phải VTK observer). Mọi `QMouseEvent`/`QKeyEvent`/`QWheelEvent` được chuẩn hoá thành `PointerEvent(kind, x, y, button, modifiers, is_double)` / `KeyEvent(key, modifiers)` với toạ độ đã nhân `devicePixelRatio` (VTK dùng pixel vật lý, Qt dùng pixel logic — đây là bug Hi-DPI kinh điển).

```
Qt event ─▶ ToolManager.eventFilter
              ├─ active_tool.handle(event) -> True  → event bị "ăn", VTK không nhận
              └─ False                              → chuyển tiếp cho VTK: camera orbit/pan/zoom bình thường
```

Nhờ vậy giữa lúc đo/ghi chú vẫn xoay được camera bằng chuột giữa/phải; tool chỉ ăn đúng nút nó cần.

**Tool ABC (`tools/base.py`)**

```python
class Tool(ABC):
    id: str; label: str; icon: str; shortcut: str; cursor: Qt.CursorShape
    def activate(self, ctx: ToolContext) -> None
    def deactivate(self) -> None            # ToolManager luôn gọi, kể cả khi tool đang dở
    def cancel(self) -> None                # ESC / đổi tool: về IDLE, xoá preview
    def handle(self, ev: PointerEvent | KeyEvent) -> bool
    def status_hint(self) -> str            # hiển thị trên status bar + HUD
    def options_widget(self) -> QWidget | None   # panel tuỳ chọn nhỏ (chế độ polygon/rect/lasso…)
```

`ToolContext` cung cấp: `document`, `viewport`, `overlay.scratch(tool_id)`, `picker`, `undo_stack`, `set_status(str)`, `request_render()`. Tool **không** nhận MainWindow, không nhận widget khác.

**ToolManager (`tools/manager.py`)** — bất biến:
1. Tối đa 1 tool active. `activate(id)`: `try: old.cancel(); old.deactivate() finally: overlay.clear_scratch(old.id); viewport.reset_cursor(); style.reset()` rồi mới `new.activate(ctx)`.
2. Toggle lại tool đang active → về `NavigateTool`.
3. Khi `Document` bị reset (mở file mới) → tự về Navigate.
4. Emit `tool_changed(id)` để toolbar cập nhật trạng thái nút (toolbar nghe manager, không phải ngược lại).
5. ESC ở mọi tool: `cancel()`; ESC lần 2 → về Navigate.

**State machine tường minh** trong từng tool (`Enum`), mọi nhánh đều có đường về `IDLE`. Preview vẽ vào `ScratchGroup` — bị wipe khi cancel/deactivate, không thể rò rỉ.

### 3.3 Danh sách tool (tên theo nghiệp vụ)

| ID | Tên hiển thị (EN / VI) | Class | Phím | Mô tả |
|---|---|---|---|---|
| `navigate` | Navigate / Điều hướng | `NavigateTool` | `Esc`/`V` | Mặc định. Không ăn event nào. |
| `region_select` | Select Region / Chọn vùng | `RegionSelectTool` | `S` | Chế độ: Polygon (click từng đỉnh, double-click/Enter đóng), Rectangle (kéo), Lasso (vẽ tự do). Modifier: `Shift`=Add, `Ctrl`=Subtract, mặc định Replace. Backspace lùi 1 đỉnh. Feedback: cạnh đang vẽ, đỉnh, đường đóng nét đứt, HUD "N đỉnh — Enter để áp dụng", số điểm sẽ chọn cập nhật realtime khi >=3 đỉnh (throttle). |
| `measure_distance` | Measure Distance / Đo khoảng cách | `MeasureDistanceTool` | `D` | Click điểm 1 (snap vào điểm cloud gần nhất, marker highlight khi hover), click điểm 2 → tạo `DistanceMeasurement`. Preview đoạn thẳng + label tạm theo chuột. Hiển thị khoảng cách 3D (m, 3 chữ số) và ΔX/ΔY/ΔZ trong Objects dock. |
| `measure_area` | Measure Area / Đo diện tích | `MeasureAreaTool` | `A` | Vẽ vùng (dùng chung bộ vẽ polygon/lasso với RegionSelect) → lấy điểm trong vùng trên các layer hiện → tính diện tích **bằng đúng `surface_area()` BPA đang dùng cho report** (radii (0.05, 0.1)) trong worker thread; label hiện "…" rồi cập nhật m². Kết quả `AreaMeasurement` neo tại trọng tâm vùng, kèm viền vùng. |
| `note` | Note / Ghi chú | `NoteTool` | `N` | Click lên cloud → mở editor (text, màu, cỡ chữ) → tạo `NoteAnnotation` neo 3D. Kéo label để đổi offset (leader tự vẽ từ anchor tới label). Double-click label → sửa. `Delete` khi label đang chọn → xoá. Hover đổi cursor. |

Không có tool "Move"/"Delete" riêng: chọn-kéo-sửa-xoá là hành vi trực tiếp trên đối tượng (hiện đại hơn, ít đổi tool hơn). Objects dock cho phép chọn/xoá hàng loạt.

Thao tác không cần tool chuột (nằm ở Selection dock, là command):
- **Filter by Thickness / Lọc theo độ dày** (`ThicknessFilterCommand`): chọn điểm có distance trong [from, to] trên layer hiện — thay `select_by_distance_range` cũ. Tôn trọng Replace/Add/Subtract.
- **Extract Segment / Tạo segment từ vùng chọn** (`AddSegmentCommand`): tương đương `_on_add_segment` cũ.
- **Crop / Cắt giữ phần ngoài** (`AddSegmentCommand(invert=True)`): tạo segment từ phần *không* chọn — mở rộng nhỏ, cùng cơ chế.
- **Invert / Đảo vùng chọn**, **Clear / Bỏ chọn**, **Select All / Chọn tất cả** (Ctrl+A).

### 3.4 Selection model (`scene/selection.py`)

- `Selection = {layer_id: np.ndarray[bool]}` trên các layer **đang hiện**. Không copy điểm cho tới khi tạo segment.
- Ops: `replace/add/subtract/invert/clear`, `count()`, `is_empty`.
- `to_sources()` → `[(layer_id, indices_ascending), ...]` theo **thứ tự layer trong LayerManager** (original trước, segment theo thứ tự tạo) — đúng thứ tự `np.concatenate([l.points for l in vis])[mask]` của code cũ ⇒ mảng điểm của segment mới **giống hệt byte-by-byte** với hiện tại ⇒ số liệu tính không đổi (§7).
- Selection **không** nằm trong undo stack (giống CloudCompare); segment tạo từ selection thì có.

### 3.5 Picking (`render/picking.py`)

- `project_to_screen(points)`: phép chiếu vector hoá như `_project_to_screen` cũ, cache theo `(camera.GetMTime(), window size)`; tính theo layer, lazy.
- `pick_point(x, y, radius_px=8)`: điểm cloud gần nhất trong bán kính pixel, ưu tiên gần camera hơn (dùng z sau chiếu). Dùng cho snap của đo khoảng cách/ghi chú.
- `points_in_polygon(polygon_px)`: `matplotlib.path.Path.contains_points` như hiện tại (đã có matplotlib).
- Đủ nhanh cho cloud vài triệu điểm; nếu cần hơn (20M) → chuyển `pick_point` sang `vtkHardwareSelector` ở phase hardening. Ghi nhận là rủi ro hiệu năng, không phải kiến trúc.

---

## 4. Scene / Document / Undo / Project file

### 4.1 `Document(QObject)`

Sở hữu: `layer_manager`, `selection`, `annotations: list[NoteAnnotation]`, `measurements: list[Measurement]`, `project_info`, `source_path`, `distance_field`, `targets (min,max)`, `undo_stack: QUndoStack`, `dirty: bool`.

Signals: `reset()`, `layer_added(id)`, `layer_removed(id)`, `layer_changed(id)` (rename/visible), `selection_changed()`, `annotation_added/changed/removed(id)`, `measurement_added/changed/removed(id)`, `targets_changed(min,max)`, `dirty_changed(bool)`.

Mọi thay đổi đi qua `commands.py` (trừ selection và targets). `Layer` được mở rộng: `id: str (uuid)`, `sources: list[SourceRef]` (để lưu project), `kind: original|segment`. Field `annotations: list[dict]` cũ trên `Layer` được giữ và **đồng bộ** từ `Document.annotations` (theo layer gần anchor nhất lúc tạo) để `report._segment_notes` và text hiển thị số ghi chú vẫn chạy nguyên.

### 4.2 Dataclasses

```python
@dataclass
class NoteAnnotation:
    id: str; layer_id: str | None
    anchor: tuple[float, float, float]      # điểm 3D trên cloud
    text: str
    label_offset_px: tuple[int, int] = (40, 40)
    color: str = "#ffd166"; font_size: int = 14; line_width: int = 2
    visible: bool = True

@dataclass
class DistanceMeasurement:
    id: str; p1: xyz; p2: xyz; label_offset_px; color; visible
    @property distance_m, delta_xyz

@dataclass
class AreaMeasurement:
    id: str; boundary_px_at_creation: list[(x,y)]  # chỉ để vẽ lại viền tương đối
    sources: list[SourceRef]                       # điểm dùng để tính
    centroid: xyz; area_m2: float | None           # None khi đang tính
    label_offset_px; color; visible
```

### 4.3 Project file `.ppsproj`

Zip 1 file, bên trong:
- `project.json`: version, đường dẫn PLY (tuyệt đối + tương đối so với file project), `distance_field`, targets, danh sách layer (id, name, kind, visible, color, `sources`), annotations, measurements, camera (position/focal/viewup/parallel scale), dock layout hash không lưu (dùng QSettings).
- `segments/<layer_id>.npy`: indices (`uint32`) cho từng `SourceRef` — tránh JSON khổng lồ.

Mở project: load PLY lại từ đường dẫn (fallback hỏi người dùng nếu không thấy) → dựng lại layer theo thứ tự cha→con → khôi phục annotations/measurements/camera. Kết quả tính không lưu (tính lại, đảm bảo đúng với code hiện hành).

---

## 5. Render

- `viewport.py`: bọc `pyvistaqt.QtInteractor`; nền tối (gradient xám-xanh đậm), axes widget, 2 renderer layer (0: cloud + label 3D; 1: overlay HUD). Cung cấp `screenshot(path, scale)` — **phải kiểm chứng ở Phase 1** rằng label 3D + overlay xuất hiện trong ảnh (report phụ thuộc vào đây).
- `layer_renderer.py`: giữ y nguyên ánh xạ màu 4 ngưỡng của `assign_colors()` (đỏ <min, xanh lá [min,max], xanh dương (max,150), xanh dương ≥150 — hiện 2 màu cuối trùng nhau, giữ nguyên để ảnh chụp không đổi, nhưng đưa vào 1 bảng cấu hình để sau này chỉnh). Highlight selection = actor vàng riêng như hiện tại. Đổi point size / target không rebuild toàn bộ mesh mà cập nhật scalars/property (mượt hơn `add_layer` lại từ đầu).
- `labels.py`: một lớp `AnchoredLabel` dùng chung cho note/đo: anchor marker (sphere nhỏ, scale theo khoảng cách camera), `vtkBillboardTextActor3D` (neo 3D, `SetDisplayOffset` = offset px kéo được), leader line vẽ trên overlay và cập nhật qua observer `StartEvent` của render window. Hit-test theo bounding box màn hình của text để kéo/chọn/double-click.
- `overlay.py`: `ScratchGroup(tool_id)` quản lý actor tạm; HUD text góc trên trái (hint của tool), góc dưới (số điểm chọn).

---

## 6. UI/UX (PySide6, kiểu CloudCompare, dark theme)

### 6.1 Bố cục

```
┌ Menu: File | Edit | View | Tools | Help ──────────────────────────────────┐
├ Toolbar chính: Open · Save · | Undo · Redo | Calculate · Export PDF        │
├ Toolbar Tools (dọc/ngang, checkable, exclusive): Navigate · Select Region  │
│   · Measure Distance · Measure Area · Note   + options bar của tool active │
├────────────┬──────────────────────────────────────┬────────────────────────┤
│ Project    │                                      │ Properties             │
│ (layers)   │            3D Viewport               │ (file/job/targets/     │
│            │        + HUD hint + axes             │  point size/style)     │
├────────────┤                                      ├────────────────────────┤
│ Selection  │                                      │ Results                │
│ (mode,     │                                      │ (area/volume/stats,    │
│  filter,   │                                      │  distribution, progress)│
│  extract)  │                                      ├────────────────────────┤
│            │                                      │ Objects (notes, đo)    │
├ Status bar: tool hint | điểm chọn | tên file | tiến trình ─────────────────┤
```

Tất cả là `QDockWidget` (movable, closable, tabbable). Menu View → bật/tắt từng dock, **Reset Layout**. `saveState()/restoreState()` qua QSettings.

### 6.2 Quy tắc responsive (áp dụng bắt buộc, có checklist khi review)

1. Không `setFixedSize/ setMaximumWidth` cho panel; chỉ `minimumWidth` nhỏ (≤ 220 px) + `sizeHint`.
2. Nội dung dock luôn nằm trong `QScrollArea(widgetResizable=True)`.
3. `QFormLayout`: `setFieldGrowthPolicy(ExpandingFieldsGrow)`, `setRowWrapPolicy(WrapLongRows)`, `setLabelAlignment(AlignLeft)`. Label dài → `ElidedLabel` (elide giữa, tooltip full text). Tên file dùng `ElidedLabel`, không `QLineEdit` giả.
4. Không hardcode `px` cho font trong QSS; dùng `pt` và kế thừa font hệ thống. Không `QFont("Arial", 10)` toàn cục.
5. Icon SVG (bundle bộ Tabler/Feather MIT trong `ui/theme/icons/`), `QIcon` tự scale theo DPI. Không dùng emoji trong nút.
6. Qt 6 mặc định per-monitor DPI; bỏ `QT_AUTO_SCREEN_SCALE_FACTOR=1`. Đặt `QGuiApplication.setHighDpiScaleFactorRoundingPolicy(PassThrough)` trước khi tạo app.
7. Toolbar options của tool dùng `QToolBar` con có thể wrap; text nút ẩn khi hẹp (`ToolButtonIconOnly` khi width < ngưỡng qua `resizeEvent`).
8. Kiểm tra ở 1366×768 @100%, 1920×1080 @125%, 2560×1440 @150%, 3840×2160 @200% và kéo cửa sổ xuống ~1000×650.

### 6.3 Theme

`theme.py` sinh QSS từ token (bg 0/1/2, border, text, accent, danger, success), áp cả `QPalette` để widget native (combo popup, tooltip, menu) không lệch. Màu accent tách biệt với màu phân loại độ dày (đỏ/xanh lá/xanh dương) để không gây nhầm.

### 6.4 Phím tắt (giữ cũ, bổ sung mới)

`Ctrl+O` mở PLY · `Ctrl+S`/`Ctrl+Shift+S` lưu project · `Ctrl+E` xuất PDF · `Ctrl+Z`/`Ctrl+Y` undo/redo · `Ctrl+A` chọn tất cả · `Delete` xoá đối tượng đang chọn · `Esc` huỷ/về Navigate · `V S D A N` chọn tool · `T G F B R L I` các góc nhìn · `Home` reset view · `Ctrl+Q` thoát. Dialog Shortcuts sinh tự động từ danh sách `QAction`.

---

## 7. Bảo toàn số liệu & report — bắt buộc đọc trước khi chạm vào core

### 7.1 Các hành vi phải giữ nguyên (kể cả khi trông giống bug)

1. **Mutation tại chỗ**: `calculate_area_and_volume` (core/calculator.py:200-201) gán `distances[|d|<12]=0` và `distances[|d|>500]=0` **trên chính mảng truyền vào**, rồi `CalculationWorker` (gui/main_window.py:60-63) đưa *cùng mảng đó* vào `calculate_thickness_distribution`. Do đó Below/Within/Above được đếm trên dữ liệu đã bị sửa. Nếu truyền bản copy, số "Above" giảm (điểm >500 chuyển sang "Below"). → `core/analysis.run_analysis()` phải gọi đúng trình tự với cùng một object mảng. Golden test khoá điều này.
2. **Thứ tự ghép điểm**: `np.vstack(points của layer được tick, theo thứ tự trong list)`. BPA/voxel/outlier có thể nhạy thứ tự ở mức làm tròn → giữ nguyên thứ tự layer.
3. **Segment = tập con theo mask boolean tăng dần** của concat các layer hiện (§3.4).
4. `load_ply` abs() distances (core/ply_loader.py:92-94) và fallback zeros khi thiếu field.
5. Targets mặc định: không có `job_info.json` → 40/60; có → `target_thickness±tolerance` (default 30/10). Targets từ job_info ghi đè QSettings khi mở file.
6. `np.min` trên mảng rỗng khi không có điểm đạt target → hiện tại **crash** với thông báo lỗi. Không "sửa" âm thầm; nếu muốn xử lý thì làm ở lớp UI (thông báo rõ), không đổi hàm core. Ghi nhận để hỏi lại sau.
7. `Export PDF for this layer` dùng `calc_result` *cuối cùng đã tính* (không tính lại cho layer đó) — hành vi hiện tại, giữ nguyên nhưng đánh dấu là điểm cần xác nhận với người dùng sau.

### 7.2 Hợp đồng ctx cho report (không đổi key)

```python
ctx = {
  "project_info": ProjectInfo, "calculation_result": CalculationResult,
  "thickness_distribution": ThicknessDistribution,
  "target_min": float, "target_max": float, "original_area_m2": None,
  "screenshot_path": str, "visible_layers": list[Layer],   # Layer.name, Layer.annotations dùng trong template
}
```
Tên file mặc định PDF giữ công thức hiện tại (`_do_export` gui/main_window.py:981-988).

### 7.3 Golden tests (Phase 0, chạy bằng code CŨ trước khi sửa bất kỳ gì)

Sinh `tests/golden/sample_baseline.json` từ `sample/2_thickness_01#20260203_093652#cloud_compared_07.ply` với targets 40/60 (không có job_info) và 1 bộ targets khác (50/150):
- `CalculationResult` đầy đủ field, `ThicknessDistribution` (counts, percents, bins, counts hist).
- Kết quả `_project_rows`, `_result_main_rows`, `_result_stats_rows`, `_distribution_rows`.
- Hash SHA256 của `points`/`distances` sau `load_ply`.
- Một segment polygon cố định (danh sách đỉnh pixel + camera cố định) → hash mảng điểm segment. Dùng để chứng minh selection mới cho ra đúng mảng cũ.

Dung sai: số nguyên bằng tuyệt đối; số thực `rtol=1e-9` (cùng máy, cùng open3d). Nếu đổi máy/phiên bản open3d mà lệch → ghi nhận, không "fix" test bằng cách nới lỏng mù.

---

## 8. Kế hoạch theo phase

Mỗi phase kết thúc bằng: test pass, `python main.py` chạy được (từ Phase 1), commit riêng, cập nhật tài liệu này. Ước lượng tương đối: S < M < L.

### Phase 0 — Khoá số liệu & khung package (S)
- Chạy code cũ, sinh `tests/golden/sample_baseline.json`.
- Tạo `pyproject.toml` (src layout, `pps`), `tests/`, `pytest` cấu hình; gỡ `sys.path.insert`.
- Di chuyển nguyên `core/`, `report/`, `utils/` vào `src/pps/`; `print` → `logging`; xoá dead code (§1.3); chuyển scripts.
- Viết `core/analysis.py`, `core/job_info.py`; test golden pass trên code đã di chuyển.
- **Xong khi**: pytest xanh; chưa có GUI mới (GUI cũ tạm không chạy — chấp nhận, vì đang ở nhánh riêng).

### Phase 1 — PySide6 + Viewport spike (M)
- `pip uninstall PyQt5 PyQt5-sip`; cài `PySide6`, `pytest-qt`; đặt `QT_API=pyside6`.
- `app/application.py` tối giản + `render/viewport.py` + `layer_renderer.py` + `camera.py` hiển thị sample PLY với màu 4 ngưỡng.
- Kiểm chứng: screenshot có overlay layer 1 và label 3D thử nghiệm; Hi-DPI 100/150/200%; đóng app không crash VTK.
- **Xong khi**: mở được PLY, xoay/zoom, chụp ảnh đúng.

### Phase 2 — Scene/Document, Selection, Commands, Project IO (M)
- `scene/*` hoàn chỉnh, không phụ thuộc render/ui.
- Tests: selection ops, `to_sources()` giữ thứ tự, commands undo/redo round-trip, project save/load round-trip.

### Phase 3 — Tool framework + Chọn vùng + Segment (L)
- `tools/base.py`, `manager.py`, `navigate.py`, `region_select.py`; `render/overlay.py`, `picking.py`.
- Selection dock tạm (đủ dùng) để test: mode, filter theo độ dày, tạo segment, đảo/bỏ chọn.
- Test pytest-qt: đổi tool khi đang dở → scratch sạch, cursor về mặc định, không còn event nào tới tool cũ; ESC 2 tầng; golden segment hash khớp baseline.

### Phase 4 — Đo khoảng cách & đo diện tích (M)
- `render/labels.py` (AnchoredLabel), `measure_distance.py`, `measure_area.py`, `ui/workers.AreaMeasureWorker`.
- Objects dock: liệt kê, chọn → highlight, xoá (undo được), ẩn/hiện.

### Phase 5 — Ghi chú (M)
- `note.py` + `dialogs/note_editor.py`; kéo/sửa/xoá trực tiếp; đồng bộ `Layer.annotations` cho report.
- Kiểm chứng ảnh chụp có ghi chú; xuất PDF thử với sample.

### Phase 6 — Main window mới, dark theme, responsive (L)
- Toàn bộ `ui/`: docks, toolbars, menus, theme, ElidedLabel, layout save/restore, shortcuts dialog, About.
- Nối `CalculationWorker` (giữ trình tự cũ qua `run_analysis`) và Export PDF (ctx §7.2).
- Kiểm tra ma trận độ phân giải §6.2.8.
- **Xong khi**: toàn bộ quy trình cũ (mở → chọn → segment → tính → PDF) chạy trên UI mới; số trong PDF khớp baseline.

### Phase 7 — Project file trong UI, tinh chỉnh (S)
- File → Save/Save As/Open Project, Recent Files, nhắc lưu khi dirty, khôi phục camera.

### Phase 8 — Hardening & đóng gói (M)
- Hiệu năng: đo với cloud lớn nhất bạn có; tối ưu picking/projection nếu cần; giảm rebuild actor.
- Logging ra file trong thư mục người dùng; xử lý lỗi rõ ràng (không `except: pass`).
- `build.spec` cho PySide6 + layout `src/`; kiểm tra exe trên máy sạch; ghi chú Defender exclusion vào README.
- README cập nhật; xoá nốt file cũ còn sót.

---

## 9. Rủi ro & biện pháp

| Rủi ro | Mức | Biện pháp |
|---|---|---|
| Số liệu PDF lệch do refactor core/worker | Cao | Golden test Phase 0 chạy ở mọi phase; `run_analysis` sao chép đúng trình tự; không truyền copy mảng. |
| Thứ tự điểm segment khác → BPA lệch nhỏ | Trung | `Selection.to_sources()` theo thứ tự layer + mask tăng dần; golden hash segment. |
| pyvistaqt/qtpy chọn nhầm PyQt5 | Trung | Gỡ PyQt5 khỏi venv; đặt `QT_API`; test import ở CI/pytest. |
| Screenshot không chứa label 3D/overlay | Trung | Kiểm chứng ngay Phase 1; nếu thiếu, render offscreen từ cùng render window (không dùng `plotter.screenshot` mặc định). |
| Hi-DPI: toạ độ Qt ≠ VTK pixel | Trung | Chuẩn hoá trong ToolManager bằng `devicePixelRatioF()`; test ở 150%/200%. |
| Hiệu năng projection/pick với cloud rất lớn | Trung | Cache theo camera MTime; throttle preview; fallback `vtkHardwareSelector` Phase 8. |
| `_find_wkhtmltopdf`/`resource_path` hỏng khi đổi layout | Trung | Cập nhật + test tồn tại file ở Phase 0; kiểm tra lại khi build exe. |
| PyInstaller với PySide6 + VTK | Trung | Chỉ ở Phase 8; giữ hook `vtkmodules`; thêm hook PySide6 plugins (platforms, styles, imageformats). |
| `np.min` mảng rỗng (bug cũ) lộ ra rõ hơn trên UI mới | Thấp | Bắt ở UI, thông báo "không có điểm đạt target"; không đổi core. Xác nhận với người dùng. |
| Open3D không nằm trong danh sách lib "giữ" | Thấp | Bắt buộc cho BPA (report + đo diện tích). Giữ, ghi rõ trong pyproject. |

---

## 10. Danh sách file/module bị ảnh hưởng

**Tạo mới**: toàn bộ `src/pps/{app,scene,render,tools,ui}/`, `src/pps/core/{analysis,job_info,models}.py`, `tests/**`, `pyproject.toml`, `docs/REFACTOR_PLAN.md`, `ui/theme/icons/*.svg`.

**Di chuyển (nội dung giữ nguyên, đổi import/log)**: `core/{calculator,helper→surface_area,ply_loader,filename_parser,layer_manager→layers}.py`, `report/**`, `utils/**`, `assets/icon.ico`.

**Sửa**: `main.py` (entry mỏng), `build.spec` (Phase 8), `requirements.txt`, `README.md`, `.gitignore` (thêm `*.ppsproj` mẫu? — không; thêm `logs/` đã có).

**Xoá**: `gui/**` (toàn bộ, sau khi UI mới thay thế), `qt/**`, `core/segmentation.py`, `core/tests/`, `run.vbs`, `hook-pyvista.py`/`hook-vtkmodules.py` (giữ nếu build vẫn cần — quyết ở Phase 8).

---

## 11. Câu hỏi mở (nhỏ, có thể trả lời trong quá trình làm)

1. Tên package Python: `pps` (đề xuất) hay tên khác?
2. Ngôn ngữ UI: hiện tại tiếng Anh; spec cũ (`NewPrompt.txt`) nhắc English + Indonesian. Đề xuất: tiếng Anh, chuỗi gom qua `tr()` để sau này dịch.
3. Điểm 7.1.6 và 7.1.7: có muốn thông báo/hành vi rõ ràng hơn ở lớp UI không (không đổi core)?
4. Đo diện tích dùng BPA giống report (chậm vài giây nhưng nhất quán) — OK, hay cần thêm ước lượng nhanh (chiếu lên mặt phẳng khớp) hiển thị tức thì?
5. Bộ icon: bundle SVG MIT (không thêm dependency) — OK?
