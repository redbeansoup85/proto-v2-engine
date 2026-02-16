# 파일: tools/demo/meta_os_flow_cli_input.py
"""
Terminal-driven Meta OS flow simulation with Enter-key progression.
Observer Hub → Sentinel → Inferantir → Executor/LOCK
"""

import time

def wait_for_enter(step_name):
    input(f"Press Enter to advance: {step_name}...")

def main():
    print("\n=== Meta OS CLI Interactive Flow Demo ===\n")

    # 1) Observer Hub
    wait_for_enter("Observer Hub activation")
    print("Observer Hub: ✅ Activated - events collected")
    time.sleep(0.3)

    # 2) Sentinel
    wait_for_enter("Sentinel intent generation")
    print("Sentinel: ✅ Intent Generated from Observer Hub data")
    time.sleep(0.3)

    # 3) Inferantir (simulation / feedback)
    wait_for_enter("Inferantir simulation & feedback")
    print("Inferantir: ✅ Simulation complete")
    print("Inferantir: Feedback loop → Sentinel updated (restricted)")
    time.sleep(0.3)

    # 4) Executor / LOCK Gate
    wait_for_enter("Executor/LOCK approval & execution")
    print("Executor/LOCK: ✅ Execution Triggered")
    time.sleep(0.3)

    # 5) Summary
    print("\n=== Flow Status Summary ===")
    print("Observer Hub : Active")
    print("Sentinel     : Ready")
    print("Inferantir   : Feedback applied")
    print("Executor/LOCK: Triggered")
    print("\nDemo complete! (No real logic executed, terminal simulation only)\n")

if __name__ == "__main__":
    main()

