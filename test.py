#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path

def transpile(c_file: Path, z_file: Path) -> subprocess.CompletedProcess:
    """Invokes fishgen.py to convert .c source to .z (Fish code)."""
    cmd = [sys.executable, "fishgen.py", str(c_file), str(z_file)]
    return subprocess.run(cmd, capture_output=True, text=True)

def parse_input_file(i_file: Path) -> list:
    """Reads .i file and splits input arguments by double newlines ('\\n\\n')."""
    if not i_file.exists():
        return []

    content = i_file.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not content:
        return []

    # Split inputs separated by double newlines (\n\n)
    raw_args = content.split("\n\n")
    return [arg.strip("\r\n") for arg in raw_args if arg != ""]

def run_test(c_file: Path) -> bool:
    test_dir = c_file.parent
    stem = c_file.stem

    z_file = test_dir / f"{stem}.z"
    i_file = test_dir / f"{stem}.i"
    o_file = test_dir / f"{stem}.o"

    print(f"Testing {c_file} ... ", end="", flush=True)

    # 1. Transpile .c -> .z
    transp_result = transpile(c_file, z_file)
    if transp_result.returncode != 0:
        print("FAIL (Transpilation Error)")
        print(transp_result.stderr or transp_result.stdout)
        return False

    if not z_file.exists():
        print(f"FAIL (Transpiler did not output {z_file.name})")
        return False

    # 2. Parse arguments from .i file
    args = parse_input_file(i_file)

    # 3. Construct fish.py command
    cmd = [sys.executable, "fish.py", str(z_file)]
    if args:
        cmd.extend(["--"] + args)

    # 4. Run through fish.py
    fish_result = subprocess.run(cmd, capture_output=True, text=True)
    if fish_result.returncode != 0:
        print("FAIL (Runtime Exception)")
        print(fish_result.stderr)
        return False

    actual_output = fish_result.stdout.replace("\r\n", "\n")
    expected_output = o_file.read_text(encoding="utf-8").replace("\r\n", "\n") if o_file.exists() else ""

    # 5. Output Verification
    if actual_output == expected_output:
        print("PASS")
        return True
    else:
        print("FAIL (Output Mismatch)")
        print("\n--- Expected Output ---")
        print(repr(expected_output))
        print("--- Actual Output ---")
        print(repr(actual_output))
        print("-----------------------\n")
        return False

def main():
    test_dir = Path("test")
    if not test_dir.exists() or not test_dir.is_dir():
        print("Error: 'test/' folder not found.")
        sys.exit(1)

    c_files = sorted(test_dir.rglob("*.c"))
    if not c_files:
        print("No .c files found inside test/ directory.")
        sys.exit(0)

    passed = 0
    failed = 0

    print(f"Found {len(c_files)} test case(s).\n")

    for c_file in c_files:
        if run_test(c_file):
            passed += 1
        else:
            failed += 1

    print(f"\nSummary: {passed} passed, {failed} failed out of {len(c_files)} total.")
    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()