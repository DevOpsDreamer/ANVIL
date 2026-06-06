import xml.etree.ElementTree as ET
import xml.dom.minidom

def export_pnml(engine, filepath: str):
    pnml = ET.Element("pnml")
    net = ET.SubElement(pnml, "net", id="anvil_cpn", type="http://www.pnml.org/version-2009/grammar/ptnet")
    page = ET.SubElement(net, "page", id="page1")

    # Add places
    for name, place in engine.places.items():
        p = ET.SubElement(page, "place", id=name)
        n = ET.SubElement(p, "name")
        text = ET.SubElement(n, "text")
        text.text = name

    # Add transitions and arcs
    arc_id = 1
    for t in engine.transitions:
        trans = ET.SubElement(page, "transition", id=t.name)
        n = ET.SubElement(trans, "name")
        text = ET.SubElement(n, "text")
        text.text = t.name

        # Arc from source place to transition
        arc1 = ET.SubElement(page, "arc", id=f"a{arc_id}", source=t.source.name, target=t.name)
        arc_id += 1

        # Arcs from transition to target places
        for route_key, target_place in t.targets.items():
            arc2 = ET.SubElement(page, "arc", id=f"a{arc_id}", source=t.name, target=target_place.name)
            name_node = ET.SubElement(arc2, "name")
            text_node = ET.SubElement(name_node, "text")
            text_node.text = route_key
            arc_id += 1

    xml_str = ET.tostring(pnml, encoding='utf-8')
    dom = xml.dom.minidom.parseString(xml_str)
    pretty_xml_as_string = dom.toprettyxml()
    
    with open(filepath, "w") as f:
        f.write(pretty_xml_as_string)
    print(f"Exported CPN to {filepath}")

if __name__ == "__main__":
    from backend.app.graph import build_web_cpn
    # Mock emit function for the factory
    async def mock_emit(*args, **kwargs):
        pass
    import asyncio
    engine = build_web_cpn("test_scan", mock_emit, asyncio.new_event_loop())
    export_pnml(engine, "anvil_model.pnml")
