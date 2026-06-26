"""Mobile-friendly Streamlit demo for DeepLister."""

from __future__ import annotations

import streamlit as st

from core.harness import ConversationState, DeepListerHarness
from shared.config import Config

st.set_page_config(
    page_title="DeepLister Demo",
    page_icon="🫧",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container {max-width: 680px; padding-top: 1.2rem; padding-bottom: 5rem;}
    .deeplister-card {
        border: 1px solid rgba(120, 120, 120, 0.22);
        border-radius: 18px;
        padding: 1rem;
        margin: 0.75rem 0;
        background: rgba(127, 127, 127, 0.06);
    }
    .strategy-pill {
        display: inline-block;
        padding: 0.15rem 0.55rem;
        border-radius: 999px;
        font-size: 0.78rem;
        background: #e8f2ff;
        color: #195ca8;
        margin-top: 0.35rem;
    }
    .small-note {font-size: 0.86rem; opacity: 0.78;}
    </style>
    """,
    unsafe_allow_html=True,
)


def _ensure_state() -> None:
    if "conversation_state" not in st.session_state:
        st.session_state.conversation_state = ConversationState()
    if "messages" not in st.session_state:
        harness = DeepListerHarness(st.session_state.conversation_state)
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": harness.opening_question(),
                "strategy": "开场问题",
                "reason": "从睡眠质量主题开始，使用口语化问题降低回答负担。",
                "log": None,
            }
        ]


def _render_decision(log) -> None:
    detection = log.detection_result
    arbitration = log.arbitration_result
    verification = log.verification_result

    st.write("**Step 1 · 检测**")
    st.json(
        {
            "safety": detection.safety.model_dump(),
            "comprehension": detection.comprehension.model_dump(),
            "consistency": detection.consistency.model_dump(),
            "sufficiency": detection.sufficiency.model_dump(),
        }
    )
    st.write("**Step 2 · 仲裁**")
    st.json(arbitration.model_dump())
    st.write("**Step 3 · 生成**")
    st.write(log.generated_reply)
    st.write("**Step 4 · 校验**")
    st.json(verification.model_dump())


_ensure_state()
Config.ensure_dirs()

st.title("🫧 DeepLister")
st.caption("会追问的 AI 调研 Agent · 移动端友好 Demo")

with st.container():
    st.markdown(
        """
        <div class="deeplister-card">
          <b>当前主题：睡眠质量</b><br/>
          <span class="small-note">这个 Demo 不做心理诊断，只演示如何把模糊回答追问得更清楚。</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message["role"] == "assistant":
            st.markdown(f"<span class='strategy-pill'>{message['strategy']}</span>", unsafe_allow_html=True)
            st.caption(message["reason"])
            if message.get("log") is not None:
                with st.expander("查看本轮 Harness 决策链路"):
                    _render_decision(message["log"])

with st.sidebar:
    st.header("演示输入")
    st.write("你可以依次输入：")
    st.code("还行\n4分，不太容易睡着\n主要是想事情，工作压力大")
    if st.button("重新开始", use_container_width=True):
        for key in ["conversation_state", "messages"]:
            st.session_state.pop(key, None)
        st.rerun()

prompt = st.chat_input("输入你的回答，例如：还行")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    harness = DeepListerHarness(st.session_state.conversation_state)
    output = harness.process_reply(prompt)
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": output.assistant_reply,
            "strategy": output.strategy_label,
            "reason": output.user_visible_reason,
            "log": output.decision_log,
        }
    )
    st.rerun()
