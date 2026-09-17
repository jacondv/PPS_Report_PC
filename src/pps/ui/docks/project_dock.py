"""
Project dock: the layer tree (checkbox show/hide, context menu rename/
delete, bold for the original layer, note-count badge).
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from pps.scene.commands import RemoveLayerCommand, RenameLayerCommand


class ProjectDock(QDockWidget):
    layer_selected = Signal(str)  # layer_id

    def __init__(self, document, parent=None):
        super().__init__("Project", parent)
        self.setObjectName("dock_project")
        self.document = document

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(6, 6, 6, 6)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(160)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        self.list_widget.itemChanged.connect(self._on_item_changed)
        self.list_widget.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self.list_widget)

        self.setWidget(content)

        document.reset.connect(self.refresh)
        document.layer_added.connect(self._on_layer_added)
        document.layer_removed.connect(lambda _id: self.refresh())
        document.layer_changed.connect(lambda _id: self.refresh())

    def _on_layer_added(self, layer_id: str) -> None:
        self.refresh()
        self.select_layer(layer_id)

    def select_layer(self, layer_id: str) -> None:
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == layer_id:
                self.list_widget.setCurrentItem(item)
                return

    def refresh(self) -> None:
        current_item = self.list_widget.currentItem()
        current_id = current_item.data(Qt.ItemDataRole.UserRole) if current_item else None

        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for layer in self.document.layer_manager.layers:
            item = QListWidgetItem(self._display_text(layer))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked
            )
            item.setData(Qt.ItemDataRole.UserRole, layer.id)
            if layer.is_original:
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)

        if current_id is not None:
            self.select_layer(current_id)

    def _display_text(self, layer) -> str:
        note_count = len(layer.annotations)
        suffix = f"  [{note_count} note{'s' if note_count != 1 else ''}]" if note_count else ""
        return f"{layer.name}  ({layer.num_points:,} pts){suffix}"

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        layer_id = item.data(Qt.ItemDataRole.UserRole)
        visible = item.checkState() == Qt.CheckState.Checked
        self.document.set_layer_visible(layer_id, visible)

    def _on_current_changed(self, current, _previous) -> None:
        if current is not None:
            self.layer_selected.emit(current.data(Qt.ItemDataRole.UserRole))

    def _on_context_menu(self, pos) -> None:
        item = self.list_widget.itemAt(pos)
        if item is None:
            return

        selected = self.list_widget.selectedItems()
        if item not in selected:
            # Right-clicked outside the current selection: act on just that
            # item, like a fresh click would.
            self.list_widget.setCurrentItem(item)
            selected = [item]

        if len(selected) > 1:
            self._show_bulk_context_menu(pos, selected)
            return

        layer_id = item.data(Qt.ItemDataRole.UserRole)
        layer = self.document.layer_manager.get_by_id(layer_id)
        if layer is None:
            return

        menu = QMenu(self)
        act_rename = menu.addAction("Rename…")
        act_delete = None
        if not layer.is_original:
            menu.addSeparator()
            act_delete = menu.addAction("Delete layer")

        chosen = menu.exec(self.list_widget.mapToGlobal(pos))
        if chosen == act_rename:
            new_name, ok = QInputDialog.getText(self, "Rename Layer", "New name:", text=layer.name)
            new_name = new_name.strip()
            if ok and new_name and new_name != layer.name:
                self.document.undo_stack.push(RenameLayerCommand(self.document, layer_id, new_name))
        elif act_delete is not None and chosen == act_delete:
            self.document.undo_stack.push(RemoveLayerCommand(self.document, layer_id))

    def _show_bulk_context_menu(self, pos, selected_items) -> None:
        deletable_ids = self._deletable_layer_ids(selected_items)
        if not deletable_ids:
            return

        menu = QMenu(self)
        act_delete = menu.addAction(f"Delete {len(deletable_ids)} layers")
        chosen = menu.exec(self.list_widget.mapToGlobal(pos))
        if chosen == act_delete:
            self._delete_layers(deletable_ids)

    def _deletable_layer_ids(self, items) -> list:
        # The original layer can't be deleted — silently exclude it from a
        # bulk delete rather than blocking the whole action over it.
        layer_ids = [item.data(Qt.ItemDataRole.UserRole) for item in items]
        return [
            lid for lid in layer_ids
            if (layer := self.document.layer_manager.get_by_id(lid)) is not None and not layer.is_original
        ]

    def _delete_layers(self, layer_ids) -> None:
        self.document.undo_stack.beginMacro(f"Delete {len(layer_ids)} layers")
        for layer_id in layer_ids:
            self.document.undo_stack.push(RemoveLayerCommand(self.document, layer_id))
        self.document.undo_stack.endMacro()
