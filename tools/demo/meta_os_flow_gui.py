# 파일: tools/demo/meta_os_flow_gui.py
import streamlit as st
import time

st.set_page_config(page_title="Meta OS Flow Demo", layout="wide")
st.title("Meta OS Interactive Flow Prototype")
st.write("Simulates Observer → Sentinel → Inferantir → Executor/LOCK with feedback loop")

# 초기 상태
if "step" not in st.session_state:
    st.session_state.step = 0

# 단계 정의
steps = [
    {"name": "Observer Hub", "msg": "✅ Activated - events collected"},
    {"name": "Sentinel", "msg": "✅ Intent Generated from Observer Hub data"},
    {"name": "Inferantir", "msg": "✅ Simulation complete\nFeedback loop → Sentinel updated (restricted)"},
    {"name": "Executor/LOCK", "msg": "✅ Execution Triggered"}
]

# 진행 버튼
if st.button("Advance Step"):
    if st.session_state.step < len(steps):
        st.session_state.step += 1

# 단계별 카드 표시
for i in range(st.session_state.step):
    step = steps[i]
    with st.container():
        st.info(f"{step['name']}:\n{step['msg']}")
        # 화살표/피드백 시각화 (간단)
        if i < st.session_state.step - 1:
            st.markdown("⬇️")

# 피드백 루프 표시
if st.session_state.step >= 3:
    st.markdown("🔁 Feedback loop active: Inferantir → Sentinel")

# 최종 요약
if st.session_state.step == len(steps):
    st.success("=== Flow Status Summary ===")
    st.write("Observer Hub : Active")
    st.write("Sentinel     : Ready")
    st.write("Inferantir   : Feedback applied")
    st.write("Executor/LOCK: Triggered")
    st.balloons()
