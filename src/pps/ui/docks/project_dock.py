"""
Project dock: a segment tree. Each layer (segment) is a top-level row
(visibility checkbox, rename/delete context menu, bold for the original
layer); its notes/annotations and measurements are child rows nested under
it, since every object belongs to a segment and hides/shows along with it.
This replaces the separate Objects dock — there is no other place these
are listed.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QInputDialog,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pps.scene.commands import (
    DeleteMeasurementCommand,
    DeleteNoteCommand,
    EditNoteCommand,
    RemoveLayerCommand,
    RenameLayerCommand,
)
from pps.scene.measurements import DistanceMeasurement

_ROLE_KIND = Qt.ItemDataRole.UserRole
_ROLE_ID = Qt.ItemDataRole.UserRole + 1

_KIND_LAYER = "layer"
_KIND_NOTE = "note"
_KIND_DISTANCE = "distance"
_KIND_AREA = "area"
_OBJECT_KINDS = (_KIND_NOTE, _KIND_DISTANCE, _KIND_AREA)

_UNASSIGNED_ID = "__unassigned__"


class ProjectDock(QDockWidget):
    layer_selected = Signal(str)  # layer_id
    object_selected = Signal(str, str)  # kind, object_id — for highlighting in the 3D view
    move_requested = Signal(str, str)  # kind, object_id — "Move" context menu action

    def __init__(self, document, parent=None):
        super().__init__("Project", parent)
        self.setObjectName("dock_project")
        self.document = document

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(6, 6, 6, 6)

        self.list_widget = QTreeWidget()
        self.list_widget.setHeaderHidden(True)
        self.list_widget.setMinimumWidth(200)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._on_context_menu)
        self.list_widget.itemChanged.connect(self._on_item_changed)
        self.list_widget.currentItemChanged.connect(self._on_current_changed)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget)

        self.setWidget(content)

        document.reset.connect(self.refresh)
        document.layer_added.connect(self._on_layer_added)
        for signal in (
            document.layer_removed, document.layer_changed,
            document.annotation_added, document.annotation_changed, document.annotation_removed,
            document.measurement_added, document.measurement_changed, document.measurement_removed,
        ):
            signal.connect(lambda *_args: self.refresh())

        self.refresh()

    def _on_layer_added(self, layer_id: str) -> None:
        self.refresh()
        self.select_layer(layer_id)

    # ------------------------------------------------------------------ selection
    @staticmethod
    def item_kind(item: QTreeWidgetItem) -> str:
        return item.data(0, _ROLE_KIND)

    @staticmethod
    def item_id(item: QTreeWidgetItem) -> str:
        return item.data(0, _ROLE_ID)

    def select_layer(self, layer_id: str) -> None:
        item = self._find_item(_KIND_LAYER, layer_id)
        if item is not None:
            self.list_widget.setCurrentItem(item)

    def _find_item(self, kind: str, object_id: str):
        for i in range(self.list_widget.topLevelItemCount()):
            top = self.list_widget.topLevelItem(i)
            if kind == _KIND_LAYER and top.data(0, _ROLE_KIND) == _KIND_LAYER and top.data(0, _ROLE_ID) == object_id:
                return top
            for j in range(top.childCount()):
                child = top.child(j)
                if child.data(0, _ROLE_KIND) == kind and child.data(0, _ROLE_ID) == object_id:
                    return child
        return None

    # ------------------------------------------------------------------ build
    def refresh(self, *_args) -> None:
        current_item = self.list_widget.currentItem()
        current = (
            (current_item.data(0, _ROLE_KIND), current_item.data(0, _ROLE_ID))
            if current_item is not None else None
        )

        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        for layer in self.document.layer_manager.layers:
            self._add_layer_item(layer)

        unassigned_notes = [n for n in self.document.annotations if self._owning_layer(n.layer_id) is None]
        unassigned_measurements = [
            m for m in self.document.measurements if self._owning_layer(m.layer_id) is None
        ]
        if unassigned_notes or unassigned_measurements:
            self._add_unassigned_item(unassigned_notes, unassigned_measurements)

        self.list_widget.expandAll()
        self.list_widget.blockSignals(False)

        if current is not None:
            item = self._find_item(*current)
            if item is not None:
                self.list_widget.setCurrentItem(item)

    def _owning_layer(self, layer_id):
        if layer_id is None:
            return None
        return self.document.layer_manager.get_by_id(layer_id)

    def _add_layer_item(self, layer) -> None:
        item = QTreeWidgetItem([self._layer_display_text(layer)])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Checked if layer.visible else Qt.CheckState.Unchecked)
        item.setData(0, _ROLE_KIND, _KIND_LAYER)
        item.setData(0, _ROLE_ID, layer.id)
        if layer.is_original:
            font = item.font(0)
            font.setBold(True)
            item.setFont(0, font)
        self.list_widget.addTopLevelItem(item)

        for note in self.document.annotations:
            if note.layer_id == layer.id:
                item.addChild(self._note_item(note, enabled=layer.visible))
        for measurement in self.document.measurements:
            if measurement.layer_id == layer.id:
                item.addChild(self._measurement_item(measurement, enabled=layer.visible))

    def _add_unassigned_item(self, notes, measurements) -> None:
        item = QTreeWidgetItem(["(Unassigned)"])
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        item.setData(0, _ROLE_KIND, "group")
        self.list_widget.addTopLevelItem(item)
        for note in notes:
            item.addChild(self._note_item(note, enabled=True))
        for measurement in measurements:
            item.addChild(self._measurement_item(measurement, enabled=True))

    def _note_item(self, note, enabled: bool) -> QTreeWidgetItem:
        icon = "📝" if note.is_screen_note else "📌"
        item = QTreeWidgetItem([f"{icon} {note.text[:40]}"])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Checked if note.visible else Qt.CheckState.Unchecked)
        item.setData(0, _ROLE_KIND, _KIND_NOTE)
        item.setData(0, _ROLE_ID, note.id)
        self._apply_cascade_enabled(item, enabled)
        return item

    def _measurement_item(self, measurement, enabled: bool) -> QTreeWidgetItem:
        if isinstance(measurement, DistanceMeasurement):
            text = f"📏 {measurement.distance_m:.3f} m"
            kind = _KIND_DISTANCE
        else:
            area_text = "…" if measurement.area_m2 is None else f"{measurement.area_m2:.2f} m²"
            text = f"⬛ {area_text}"
            kind = _KIND_AREA
        item = QTreeWidgetItem([text])
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Checked if measurement.visible else Qt.CheckState.Unchecked)
        item.setData(0, _ROLE_KIND, kind)
        item.setData(0, _ROLE_ID, measurement.id)
        self._apply_cascade_enabled(item, enabled)
        return item

    def _apply_cascade_enabled(self, item: QTreeWidgetItem, enabled: bool) -> None:
        # While the owning segment is hidden, its objects' own checkboxes
        # can't meaningfully be toggled — dim them rather than let the user
        # flip a flag that has no visible effect until the segment comes
        # back.
        flags = item.flags()
        item.setFlags(flags | Qt.ItemFlag.ItemIsEnabled if enabled else flags & ~Qt.ItemFlag.ItemIsEnabled)

    def _layer_display_text(self, layer) -> str:
        note_count = len(layer.annotations)
        suffix = f"  [{note_count} note{'s' if note_count != 1 else ''}]" if note_count else ""
        return f"{layer.name}  ({layer.num_points:,} pts){suffix}"

    # ------------------------------------------------------------------ item events
    def _on_item_changed(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        kind = item.data(0, _ROLE_KIND)
        object_id = item.data(0, _ROLE_ID)
        checked = item.checkState(0) == Qt.CheckState.Checked
        if kind == _KIND_LAYER:
            self.document.set_layer_visible(object_id, checked)
        elif kind == _KIND_NOTE:
            self.document.set_note_visible(object_id, checked)
        elif kind in (_KIND_DISTANCE, _KIND_AREA):
            self.document.set_measurement_visible(object_id, checked)

    def _on_current_changed(self, current, _previous) -> None:
        if current is None:
            return
        kind = current.data(0, _ROLE_KIND)
        object_id = current.data(0, _ROLE_ID)
        if kind == _KIND_LAYER:
            self.layer_selected.emit(object_id)
        elif kind in _OBJECT_KINDS:
            self.object_selected.emit(kind, object_id)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        kind = item.data(0, _ROLE_KIND)
        if kind != _KIND_NOTE:
            return
        self._edit_note(item.data(0, _ROLE_ID))

    def _edit_note(self, note_id: str) -> None:
        note = self.document._find_note(note_id)
        if note is None:
            return
        from pps.app.dialogs import open_note_editor

        result = open_note_editor(note, parent=self)
        if result is None:
            return
        self.document.undo_stack.push(EditNoteCommand(self.document, note.id, **result))

    # ------------------------------------------------------------------ context menu
    def _on_context_menu(self, pos) -> None:
        item = self.list_widget.itemAt(pos)
        if item is None:
            return

        selected = [i for i in self.list_widget.selectedItems() if i.data(0, _ROLE_KIND) != "group"]
        if item not in selected:
            self.list_widget.setCurrentItem(item)
            selected = [item]

        kinds = {i.data(0, _ROLE_KIND) for i in selected}
        if len(selected) > 1:
            if kinds == {_KIND_LAYER}:
                self._show_bulk_layer_menu(pos, selected)
            elif kinds & set(_OBJECT_KINDS):
                self._show_bulk_object_menu(pos, [i for i in selected if i.data(0, _ROLE_KIND) in _OBJECT_KINDS])
            return

        kind = item.data(0, _ROLE_KIND)
        if kind == _KIND_LAYER:
            self._show_layer_menu(pos, item)
        elif kind in _OBJECT_KINDS:
            self._show_object_menu(pos, item)

    def _show_layer_menu(self, pos, item) -> None:
        layer_id = item.data(0, _ROLE_ID)
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

    def _show_bulk_layer_menu(self, pos, selected_items) -> None:
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
        layer_ids = [item.data(0, _ROLE_ID) for item in items]
        return [
            lid for lid in layer_ids
            if (layer := self.document.layer_manager.get_by_id(lid)) is not None and not layer.is_original
        ]

    def _delete_layers(self, layer_ids) -> None:
        self.document.undo_stack.beginMacro(f"Delete {len(layer_ids)} layers")
        for layer_id in layer_ids:
            self.document.undo_stack.push(RemoveLayerCommand(self.document, layer_id))
        self.document.undo_stack.endMacro()

    def _show_object_menu(self, pos, item) -> None:
        kind = item.data(0, _ROLE_KIND)
        object_id = item.data(0, _ROLE_ID)

        menu = QMenu(self)
        act_edit = menu.addAction("Edit…") if kind == _KIND_NOTE else None
        # Dragging to reposition is currently only wired up for notes'/
        # annotations' text (Note and Annotation tools) — measurements
        # don't support it yet.
        act_move = menu.addAction("Move") if kind == _KIND_NOTE else None
        menu.addSeparator()
        visible = item.checkState(0) == Qt.CheckState.Checked
        act_toggle = menu.addAction("Hide" if visible else "Show")
        menu.addSeparator()
        act_delete = menu.addAction("Delete")

        chosen = menu.exec(self.list_widget.mapToGlobal(pos))
        if act_edit is not None and chosen == act_edit:
            self._edit_note(object_id)
        elif act_move is not None and chosen == act_move:
            self.move_requested.emit(kind, object_id)
        elif chosen == act_toggle:
            if kind == _KIND_NOTE:
                self.document.set_note_visible(object_id, not visible)
            else:
                self.document.set_measurement_visible(object_id, not visible)
        elif chosen == act_delete:
            self._delete_objects([(kind, object_id)])

    def _show_bulk_object_menu(self, pos, items) -> None:
        pairs = [(i.data(0, _ROLE_KIND), i.data(0, _ROLE_ID)) for i in items]
        menu = QMenu(self)
        act_delete = menu.addAction(f"Delete {len(pairs)} objects")
        chosen = menu.exec(self.list_widget.mapToGlobal(pos))
        if chosen == act_delete:
            self._delete_objects(pairs)

    def _delete_objects(self, pairs) -> None:
        if len(pairs) > 1:
            self.document.undo_stack.beginMacro(f"Delete {len(pairs)} objects")
        for kind, object_id in pairs:
            if kind == _KIND_NOTE:
                self.document.undo_stack.push(DeleteNoteCommand(self.document, object_id))
            else:
                self.document.undo_stack.push(DeleteMeasurementCommand(self.document, object_id))
        if len(pairs) > 1:
            self.document.undo_stack.endMacro()
