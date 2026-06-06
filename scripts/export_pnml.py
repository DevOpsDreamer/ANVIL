"""
PNML Export Script for AEGIS v8 CPN Orchestrator.

Converts the deterministic orchestration graph into standard Petri Net
Markup Language (PNML) format for formal verification using tools
like CPN Tools or Snoopy.
"""

import xml.etree.ElementTree as ET
import xml.dom.minidom
from pathlib import Path
from app.graph import build_web_cpn

def export_to_pnml(output_path: str):
    """Generate a PNML XML representation of the CPN."""
    # Build the engine to get places and transitions
    # We pass dummy arguments since we only need the structure
    async def dummy_emit(*args, **kwargs): pass
    import asyncio
    engine = build_web_cpn("dummy_scan", dummy_emit, asyncio.get_event_loop())
    
    # Root elements
    pnml = ET.Element("pnml", xmlns="http://www.pnml.org/version-2009/grammar/pnml")
    net = ET.SubElement(pnml, "net", id="aegis_cpn", type="http://www.pnml.org/version-2009/grammar/ptnet")
    page = ET.SubElement(net, "page", id="page1")
    
    # ── Places ────────────────────────────────────────────────
    x_offset = 100
    y_offset = 100
    for idx, (name, place) in enumerate(engine.places.items()):
        p_elem = ET.SubElement(page, "place", id=name)
        
        name_elem = ET.SubElement(p_elem, "name")
        text_elem = ET.SubElement(name_elem, "text")
        text_elem.text = name
        
        # Add visual coordinates (simple layout)
        graphics = ET.SubElement(p_elem, "graphics")
        pos = ET.SubElement(graphics, "position", x=str(x_offset), y=str(y_offset + (idx * 50)))
        
        # Initial marking
        if name == "precon_pending":
            im = ET.SubElement(p_elem, "initialMarking")
            im_text = ET.SubElement(im, "text")
            im_text.text = "1"
            
    # ── Transitions and Arcs ──────────────────────────────────
    t_x_offset = 300
    arc_id = 1
    
    for idx, t in enumerate(engine.transitions):
        t_id = t.name
        
        # Transition element
        t_elem = ET.SubElement(page, "transition", id=t_id)
        name_elem = ET.SubElement(t_elem, "name")
        text_elem = ET.SubElement(name_elem, "text")
        text_elem.text = t.name
        
        graphics = ET.SubElement(t_elem, "graphics")
        pos = ET.SubElement(graphics, "position", x=str(t_x_offset), y=str(y_offset + (idx * 50)))
        
        # Input Arc (Place -> Transition)
        a_in = ET.SubElement(page, "arc", id=f"arc{arc_id}", source=t.source.name, target=t_id)
        arc_id += 1
        
        # Output Arcs (Transition -> Target Places)
        for route_key, target_place in t.targets.items():
            a_out = ET.SubElement(page, "arc", id=f"arc{arc_id}", source=t_id, target=target_place.name)
            
            # Annotate arc with routing key
            name_elem = ET.SubElement(a_out, "name")
            text_elem = ET.SubElement(name_elem, "text")
            text_elem.text = route_key
            
            arc_id += 1
            
    # Format XML nicely
    raw_xml = ET.tostring(pnml, 'utf-8')
    parsed_xml = xml.dom.minidom.parseString(raw_xml)
    pretty_xml = parsed_xml.toprettyxml(indent="  ")
    
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(pretty_xml, encoding="utf-8")
    print(f"Successfully exported CPN to {out_file.absolute()}")

if __name__ == "__main__":
    export_to_pnml("backend/aegis_cpn.pnml")
