import sys
import os


def resource_path(rel):
    """Trả về absolute path đúng khi chạy từ source hoặc exe.

    `rel` là đường dẫn tương đối tính từ gốc package (ví dụ
    "report/assets/images/logo.png"), khớp với cấu trúc `data` files mà
    build.spec copy vào thư mục dist.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller onedir — thử cả 2 vị trí
        base_exe = os.path.dirname(sys.executable)
        base_internal = os.path.join(base_exe, '_internal')

        # Ưu tiên _internal trước
        candidate = os.path.join(base_internal, rel)
        if os.path.exists(candidate):
            return candidate
        return os.path.join(base_exe, rel)
    else:
        # src/pps/utils/path_helper.py -> lên 1 cấp là src/pps (gốc package)
        pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(pkg_root, rel)
