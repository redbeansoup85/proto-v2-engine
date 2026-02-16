# 파일: tools/demo/meta_os_flow_gui_v2.py
import streamlit as st
import time

st.set_page_config(page_title="Meta OS Flow Demo v2", layout="wide")
st.title("Meta OS Interactive Flow Prototype v2")
st.write("Simulates Observer → Sentinel → Inferantir → Executor/LOCK with feedback loop and visual cues")

# 초기 상태
if "step" not in st.session_state:
    st.session_state.step = 0

# 단계 정의
steps = [
    {"name": "Observer Hub", "msg": "Events collected", "color": "blue"},
    {"name": "Sentinel", "msg": "Intent Generated from Observer Hub", "color": "green"},
    {"name": "Inferantir", "msg": "Simulation complete\nFeedback loop → Sentinel updated", "color": "orange"},
    {"name": "Executor/LOCK", "msg": "Execution Triggered", "color": "red"}
]

total_steps = len(steps)

# 진행 버튼
if st.button("Advance Step"):
    if st.session_state.step < total_steps:
        st.session_state.step += 1

# 단계별 카드 표시 + 색상 강조
for i in range(st.session_state.step):
    step = steps[i]
    st.markdown(
        f"<div style='padding:10px; border-radius:10px; background-color:{step['color']}; color:white; font-weight:bold'>"
        f"{step['name']}: {step['msg']}</div>",
        unsafe_allow_html=True
    )
    # 화살표 / 연결선
    if i < st.session_state.step - 1:
        st.markdown("⬇️", unsafe_allow_html=True)

# 진행 바
st.progress(st.session_state.step / total_steps)

# 피드백 루프 시각화
if st.session_state.step >= 3:
    st.markdown("<span style='color:purple; font-weight:bold'>🔁 Feedback loop active: Inferantir → Sentinel</span>", unsafe_allow_html=True)

# 최종 요약
if st.session_state.step == total_steps:
    st.success("=== Flow Status Summary ===")
    st.write("Observer Hub : Active")
    st.write("Sentinel     : Ready")
    st.write("Inferantir   : Feedback applied")
    st.write("Executor/LOCK: Triggered")
    st.balloons()
