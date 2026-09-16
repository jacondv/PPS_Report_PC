"""
Confirms notes created through the new NoteTool/Document flow still work
with the legacy report._segment_notes() (report/core/html_pdf_generator.py),
which reads layer.annotations as a list of {"text": ...} dicts.
"""

import numpy as np

from pps.report.core.html_pdf_generator import HTMLPDFGenerator
from pps.scene.annotations import NoteAnnotation
from pps.scene.commands import AddNoteCommand
from pps.scene.document import Document


def test_segment_notes_reads_document_synced_layer_annotations(qtbot):
    doc = Document()
    doc.load_point_cloud(
        source_path="C:/data/sample.ply",
        project_info=None,
        points=np.array([[0.0, 0.0, 0.0]]),
        distances=np.array([10.0]),
        distance_field="distances",
        target_min=0.0,
        target_max=100.0,
    )
    layer = doc.layer_manager.original

    doc.undo_stack.push(
        AddNoteCommand(doc, NoteAnnotation(anchor=(0.0, 0.0, 0.0), text="first note", layer_id=layer.id))
    )
    doc.undo_stack.push(
        AddNoteCommand(doc, NoteAnnotation(anchor=(0.0, 0.0, 0.0), text="second note", layer_id=layer.id))
    )

    generator = HTMLPDFGenerator("unused.pdf")
    notes = generator._segment_notes([layer])

    assert notes == [{"layer_name": layer.name, "text": "first note\n\nsecond note"}]
