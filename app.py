import json
from pathlib import Path

import streamlit as st

from core.mock_engine import DemoState, MockHarnessEngine


ROOT = Path(__file__).parent
SAMPLE_PATH = ROOT / "data" / "sample_scl90.json"


def load_sample() -> dict:
    with SAMPLE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def init_demo() -> None:
    if "engine" not in st.session_state:
        st.session_state.engine = MockHarnessEngine.from_json(load_sample())
        st.session_state.demo_state = DemoState()
        opening = st.session_state.engine.get_opening(st.session_state.demo_state)
        st.session_state.messages = [{"role": "assistant", "content": opening}]


def reset_demo() -> None:
    for key in ["engine", "demo_state", "messages"]:
        st.session_state.pop(key, None)
    init_demo()


def signal_label(detection) -> tuple[str, str]:
    checks = [
        ("安全信号", detection.safety),
        ("理解偏差", detection.comprehension),
        ("前后矛盾", detection.consistency),
        ("信息不足", detection.sufficiency),
    ]
    for label, result in checks:
        if result.triggered:
            return label, result.detail or "触发该信号"
    return "无明显信号", "回答暂时足够，系统推进到下一个问题。"


def strategy_label(strategy: str) -> str:
    labels = {
        "safety_protocol": "安全优先：暂停追问",
        "comprehension_correction": "理解纠偏：换成更具体的问题",
        "depth_mining": "深度挖掘：追问原因或场景",
        "proceed": "继续推进：进入下一个子问题",
        "transition": "话题过渡：进入下一个话题",
        "skip_topic": "跳过话题：不强行追问",
    }
    return labels.get(strategy, strategy)


def render_log(log) -> None:
    signal_name, signal_detail = signal_label(log.detection_result)
    with st.expander("查看本轮判断", expanded=False):
        st.markdown(
            f"""
            <div class="trace-grid">
              <div><b>检测</b><span>{signal_name}</span><small>{signal_detail}</small></div>
              <div><b>仲裁</b><span>{strategy_label(log.arbitration_result.strategy)}</span><small>优先级 {log.arbitration_result.priority}</small></div>
              <div><b>生成</b><span>{log.generated_reply}</span><small>追问不超过两句话</small></div>
              <div><b>校验</b><span>{'通过' if log.verification_result.passed else '需修正'}</span><small>长度、安全性、重复度检查</small></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_sidebar() -> None:
    status = st.session_state.engine.get_status(st.session_state.demo_state)
    st.sidebar.title("DeepLister")
    st.sidebar.caption("AI 深度倾听式调研 Agent")
    st.sidebar.metric("当前话题", status["topic_name"])
    st.sidebar.progress(status["progress"])
    st.sidebar.caption(f"已完成 {status['completed']} / {status['total']} 个话题")
    if st.sidebar.button("重新开始", use_container_width=True):
        reset_demo()
        st.rerun()


def render_profile() -> None:
    logs = st.session_state.demo_state.logs
    if not logs:
        return

    st.subheader("结构化画像")
    signals = []
    for log in logs:
        signal_name, signal_detail = signal_label(log.detection_result)
        if signal_name != "无明显信号":
            signals.append({"轮次": log.turn_id, "信号": signal_name, "说明": signal_detail})

    st.json(
        {
            "完成话题": st.session_state.demo_state.completed_topics,
            "识别信号": signals,
            "沟通偏好": "更适合具体例子和数字参照式提问",
            "数据范围": "结构化摘要",
        },
        expanded=False,
    )


def apply_mobile_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 760px;
            padding-top: 1rem;
            padding-bottom: 6rem;
        }
        h1 {
            font-size: 1.75rem;
            line-height: 1.2;
        }
        [data-testid="stChatMessage"] {
            border-radius: 8px;
            padding: 0.2rem 0;
        }
        .topic-strip {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            padding: 10px 0 14px;
            border-bottom: 1px solid #e6e8eb;
            margin-bottom: 10px;
        }
        .topic-strip span {
            color: #586174;
            font-size: 0.92rem;
        }
        .trace-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 8px;
        }
        .trace-grid div {
            border: 1px solid #e1e5ea;
            border-radius: 8px;
            padding: 10px;
            background: #ffffff;
        }
        .trace-grid b {
            display: block;
            color: #2b3445;
            font-size: 0.82rem;
            margin-bottom: 4px;
        }
        .trace-grid span {
            display: block;
            color: #111827;
            line-height: 1.45;
        }
        .trace-grid small {
            display: block;
            color: #64748b;
            margin-top: 4px;
            line-height: 1.35;
        }
        @media (min-width: 720px) {
            .trace-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="DeepLister Demo", layout="centered")
    apply_mobile_style()
    init_demo()
    render_sidebar()

    status = st.session_state.engine.get_status(st.session_state.demo_state)
    st.title("DeepLister")
    st.markdown(
        f"""
        <div class="topic-strip">
          <strong>{status['topic_name']}</strong>
          <span>{status['completed']} / {status['total']} 已完成</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message["role"] == "assistant" and message.get("log_index") is not None:
                render_log(st.session_state.demo_state.logs[message["log_index"]])

    if prompt := st.chat_input("输入回答"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        result = st.session_state.engine.process_reply(st.session_state.demo_state, prompt)
        log_index = len(st.session_state.demo_state.logs) - 1
        st.session_state.messages.append(
            {"role": "assistant", "content": result["reply"], "log_index": log_index}
        )
        st.rerun()

    render_profile()


if __name__ == "__main__":
    main()
