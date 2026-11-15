import argparse
import json
from pathlib import Path
from .core.registry import Registry

def main():
    parser = argparse.ArgumentParser(description="Offline Life Support registry validation")
    parser.add_argument("registry", type=Path)
    parser.add_argument("--trace", metavar="COMPONENT_ID")
    args = parser.parse_args()
    reg = Registry.load(args.registry)
    print(json.dumps({"result":"PASS", "components":len(reg.components), "requirements":len(reg.requirements), "dependency_order":reg.dependencies_first(), "trace":reg.trace(args.trace) if args.trace else None}, indent=2))
if __name__ == "__main__": main()
