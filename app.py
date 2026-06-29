import base64
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime
from io import BytesIO
from pathlib import Path
from secrets import token_hex, token_urlsafe
from time import time
from urllib.parse import urlencode, urlsplit, urlunsplit
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

from core.detector import Detector
from core.generator import Generator
from core.harness import HarnessEngine, HarnessSession
from core.verifier import Verifier
from shared.config import Config
from shared.github_auth import (
    GitHubOAuthConfig,
    GitHubOAuthError,
    build_github_authorize_url,
    exchange_code_for_token,
    fetch_authenticated_user,
    is_allowed_developer,
    load_github_oauth_config,
)
from shared.llm_client import LLMClient
from shared.survey_models import Campaign, DeveloperFeedbackRecord, DeveloperLogPackage, ResponseRecord
from shared.types import Questionnaire, Topic
from storage.key_vault import get_campaign_api_key, put_campaign_api_key
from storage.survey_store import get_survey_store


ROOT = Path(__file__).parent
HOST_IMAGE = ROOT / "assets" / "hero-tang-listener.png"
AMBIENT_IMAGE = ROOT / "assets" / "hero-ambient.png"
LOGO_IMAGE = ROOT / "public" / "logo-transparent.png"
MBTI_QUESTIONNAIRE_FILE = ROOT / "data" / "mbti_deeplister_questionnaire.json"
DEVELOPER_AUTH_FILE = ROOT / "data" / "developer_auth.json"
DEVELOPER_OAUTH_STATE_FILE = ROOT / "data" / "developer_oauth_states.json"

ROUTES = {
    "home",
    "import",
    "invite",
    "mbti",
    "sample",
    "agent",
    "complete",
    "launch",
    "take",
    "quick",
    "results",
    "storage",
    "developer",
}

SAMPLE_QUESTIONS = [
    {
        "dimension": "睡眠质量",
        "question": "最近一周睡眠怎么样？有没有入睡困难、早醒，或者白天明显没精神？",
        "why": "这是样例调研的起点，用来判断状态是否已经影响日常精力。",
        "followup": "能说一个最近睡不好的晚上吗？大概几点睡、几点醒、醒来后什么感觉？",
        "options": ["入睡有点慢，白天容易困", "还可以，但偶尔会醒", "最近睡得比较差"],
    },
    {
        "dimension": "压力来源",
        "question": "如果用 1 到 10 分表示最近的压力，10 分最强，你大概在几分？主要来自哪里？",
        "why": "这题把模糊压力转成可比较的信息，方便 Agent 后面填问卷。",
        "followup": "这个分数背后最典型的一件事是什么？",
        "options": ["7 分左右，主要是工作", "5 分，事情多但还能扛", "8 分以上，已经影响状态"],
    },
    {
        "dimension": "生活影响",
        "question": "这种状态对你的学习、工作、社交或日常安排有什么影响？",
        "why": "问卷里真正有价值的部分，往往是状态具体影响到了哪里。",
        "followup": "如果只选一个影响最大的地方，会是效率、情绪、人际，还是身体状态？",
        "options": ["效率下降，容易拖延", "社交变少，更想一个人待着", "影响不大，但有点消耗"],
    },
    {
        "dimension": "改善目标",
        "question": "接下来一周，你最希望先改善的一件小事是什么？",
        "why": "这题用来把调研结果收束成可导出的结论和建议。",
        "followup": "这个目标如果变成一个很小的行动，第一步会是什么？",
        "options": ["先把睡眠调回来", "减少拖延，把事情排清楚", "想让情绪更稳定一点"],
    },
]

QUICK_TOPIC_BANK = {
    "心理状态": [
        "最近一周你的整体情绪状态怎么样？",
        "最近睡眠有没有影响到白天精力？",
        "压力最明显的时候通常发生在什么场景？",
        "这种状态有没有影响学习、工作或社交？",
        "你最近有没有一件特别消耗自己的事？",
        "当状态不好时，你通常会怎么缓解？",
        "身边有没有能支持你的人或资源？",
        "如果下周只改善一件小事，你会选什么？",
        "最近有没有让你感觉轻松一点的时刻？",
        "你更希望别人如何理解你现在的状态？",
        "你觉得当前最需要被解决的问题是什么？",
        "如果把最近状态打 1 到 10 分，你会给几分？",
    ],
    "产品体验": [
        "你第一次看到这个产品时，最先注意到什么？",
        "你觉得这个产品最容易理解的部分是什么？",
        "有没有哪个地方让你不知道下一步该做什么？",
        "你完成核心任务时是否顺畅？",
        "有没有一个功能让你觉得有用但还不够好用？",
        "如果推荐给别人，你会怎么介绍它？",
        "你在哪个场景下最可能使用这个产品？",
        "你觉得它和同类产品最大的差异是什么？",
        "有没有让你产生不信任或犹豫的地方？",
        "如果只能改一处，你最希望改哪里？",
        "你愿意再次使用它的可能性有多高？",
        "你觉得这个产品最适合哪类用户？",
    ],
    "学习工作": [
        "最近学习或工作中最占精力的一件事是什么？",
        "你现在的任务安排是否清楚？",
        "有没有经常被打断或拖延的情况？",
        "你觉得效率最高的时间段是什么时候？",
        "最近有没有一件事让你很有成就感？",
        "你遇到难题时通常怎么处理？",
        "你更喜欢独立完成还是和别人协作？",
        "现在最影响你推进任务的阻碍是什么？",
        "你对当前节奏满意吗？",
        "如果下周只优化一个工作习惯，你会选什么？",
        "你希望别人给你怎样的反馈或帮助？",
        "你觉得当前目标是否足够明确？",
    ],
    "消费偏好": [
        "你最近一次认真比较后购买的东西是什么？",
        "你做购买决定时最看重什么？",
        "价格、品牌、口碑、体验里哪个最影响你？",
        "你通常会在哪些渠道了解产品？",
        "什么情况会让你放弃购买？",
        "你有没有为某种体验多花钱的经历？",
        "促销活动会明显影响你的决定吗？",
        "你更相信熟人推荐还是平台评价？",
        "购买后你如何判断自己买得值不值？",
        "你最近有没有一次后悔购买的经历？",
        "你希望商家提供什么信息来帮助决策？",
        "如果给理想产品写一句描述，你会怎么写？",
    ],
    "人际沟通": [
        "最近和别人沟通时整体感觉怎么样？",
        "有没有一类沟通让你觉得费劲？",
        "你更习惯直接表达，还是先自己消化？",
        "当意见不一致时，你通常怎么处理？",
        "最近有没有一次沟通让你印象很深？",
        "你觉得别人容易理解你的真实意思吗？",
        "你会主动开启重要对话吗？",
        "你在群体里更像推动者还是观察者？",
        "什么话题最容易让你产生压力？",
        "你希望别人和你沟通时注意什么？",
        "你觉得自己最想提升的沟通能力是什么？",
        "如果下次沟通更顺利，你希望发生什么变化？",
    ],
}

OPEN_QUESTION_OPTION_BANK = {
    "心理状态": [
        "最近状态有点起伏，压力来的时候会影响睡眠和效率。",
        "整体还可以，但偶尔会因为事情太多而焦虑。",
        "最明显的是精力下降，我需要先把一件小事稳定下来。",
    ],
    "产品体验": [
        "第一眼能看懂大概用途，但下一步动作还不够明确。",
        "核心功能有价值，不过有些地方需要试错才知道怎么用。",
        "我愿意继续体验，但希望流程提示和结果反馈更清楚。",
    ],
    "学习工作": [
        "最近任务很多，最难的是把优先级排清楚。",
        "我能推进，但经常被打断，效率不太稳定。",
        "如果有人帮我拆步骤，我会更容易开始行动。",
    ],
    "消费偏好": [
        "我会先看价格和评价，再判断值不值得买。",
        "真正影响我的通常是使用场景，而不是单纯促销。",
        "如果信息更透明，我会更快做决定。",
    ],
    "人际沟通": [
        "我会先观察对方态度，再决定要不要直接表达。",
        "最费劲的是重要话题容易说不完整，怕被误解。",
        "如果沟通更顺利，我希望双方能更快确认真实意思。",
    ],
}

GENERIC_OPEN_OPTIONS = [
    "我能想到一个具体例子，但还需要继续梳理细节。",
    "整体感受是有影响，不过现在还说不太完整。",
    "最关键的是这个问题确实影响了我的下一步选择。",
]

FOLLOWUP_OPEN_OPTIONS = [
    "我举一个最近的例子：当时这个情况让我明显停顿了一下。",
    "具体一点说，影响最大的是当时的判断和后续行动。",
    "我现在还说不完整，但这个细节值得继续追问。",
]


DEFAULT_MBTI_SCALE = [
    {"value": 1, "label": "非常不同意"},
    {"value": 2, "label": "比较不同意"},
    {"value": 3, "label": "不确定 / 一般"},
    {"value": 4, "label": "比较同意"},
    {"value": 5, "label": "非常同意"},
]

MBTI_TOPIC_BLOCKS = [
    ("energy_e", "能量来源与互动方式：外向 E", "观察互动、表达、群体能量等外向倾向。", "E", ["社交激活", "外部表达", "互动推进"]),
    ("energy_i", "能量来源与互动方式：内向 I", "观察独处恢复、私下思考、深度交流等内向倾向。", "I", ["独处恢复", "内部整理", "深度交流"]),
    ("info_s", "信息获取与理解方式：实感 S", "观察具体事实、经验案例、细节执行等实感倾向。", "S", ["具体事实", "经验案例", "细节执行"]),
    ("info_n", "信息获取与理解方式：直觉 N", "观察抽象联想、未来可能、意义洞察等直觉倾向。", "N", ["抽象联想", "未来可能", "意义洞察"]),
    ("decision_t", "决策判断与价值取向：思考 T", "观察逻辑分析、标准证据、结构判断等思考倾向。", "T", ["逻辑分析", "标准证据", "结构判断"]),
    ("decision_f", "决策判断与价值取向：情感 F", "观察共情关系、价值感受、关系影响等情感倾向。", "F", ["共情关系", "价值感受", "关系影响"]),
    ("lifestyle_j", "生活节奏与任务管理方式：判断 J", "观察计划推进、提前安排、确定性偏好等判断倾向。", "J", ["计划推进", "提前安排", "确定性偏好"]),
    ("lifestyle_p", "生活节奏与任务管理方式：知觉 P", "观察开放探索、现场调整、灵活应变等知觉倾向。", "P", ["开放探索", "现场调整", "灵活应变"]),
]


def load_questionnaire_file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def mbti_scale_options(questionnaire: dict) -> list[str]:
    return [f"{item['value']} {item['label']}" for item in questionnaire.get("scale", DEFAULT_MBTI_SCALE)]


def mbti_score_options(questionnaire: dict, letter: str | None) -> list[dict]:
    if not letter:
        return []
    return [{letter: int(item["value"])} for item in questionnaire.get("scale", DEFAULT_MBTI_SCALE)]


def score_letter(item: dict, fallback: str | None = None) -> str | None:
    score = item.get("score") if isinstance(item.get("score"), dict) else {}
    return score.get("letter") or item.get("mbti_letter") or fallback


def make_agent_question(
    questionnaire: dict,
    *,
    topic_name: str,
    text: str,
    letter: str | None = None,
    sub_dimension: str | None = None,
) -> dict:
    is_mbti = questionnaire.get("kind") == "mbti"
    if is_mbti:
        return {
            "dimension": sub_dimension or topic_name,
            "question": text,
            "why": "这题来自导入题库。请按第一感觉选择同意程度，系统会把分数累积到对应的人格倾向里。",
            "followup": "如果愿意，可以补一句你为什么这样选；这会让最后导出的画像更像真实访谈。",
            "options": mbti_scale_options(questionnaire),
            "scores": mbti_score_options(questionnaire, letter),
        }
    return {
        "dimension": sub_dimension or topic_name,
        "question": text,
        "why": f"这是“{topic_name}”里的调研问题，用来把回答整理成结构化问卷结果。",
        "followup": f"能不能围绕“{sub_dimension or topic_name}”补一个具体例子？",
        "options": [],
    }


def make_agent_from_questionnaire(
    questionnaire: dict,
    *,
    file_name: str | None = None,
    invite_code: str | None = None,
) -> dict:
    questions = []
    for topic in questionnaire.get("topics", []):
        topic_name = topic.get("topic_name", "未命名主题")
        topic_letter = score_letter(topic)
        opening = topic.get("opening_question", "").strip()
        if opening:
            questions.append(
                make_agent_question(
                    questionnaire,
                    topic_name=topic_name,
                    text=opening,
                    letter=topic_letter,
                )
            )
        for sub_question in topic.get("sub_questions", []):
            text = (sub_question.get("text") or sub_question.get("question") or "").strip()
            if not text:
                continue
            questions.append(
                make_agent_question(
                    questionnaire,
                    topic_name=topic_name,
                    text=text,
                    letter=score_letter(sub_question, topic_letter),
                    sub_dimension=sub_question.get("dimension") or topic_name,
                )
            )

    if not questions:
        raise ValueError("没有识别到可作答的问题。")

    return {
        "kind": questionnaire.get("kind", "imported"),
        "title": questionnaire.get("title", "导入问卷 Agent"),
        "subtitle": questionnaire.get("description") or f"已根据《{file_name or '导入问卷'}》生成调研 Agent。",
        "invite_code": invite_code or questionnaire.get("invite_code") or st.session_state.get("import_code", "DL-2026"),
        "questions": questions,
        "questionnaire": questionnaire,
    }


def extract_docx_table_rows(file_bytes: bytes) -> list[list[str]]:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with ZipFile(BytesIO(file_bytes)) as docx_file:
        document_xml = docx_file.read("word/document.xml")
    root = ET.fromstring(document_xml)
    rows = []
    for table_row in root.findall(".//w:tr", namespace):
        cells = []
        for table_cell in table_row.findall("./w:tc", namespace):
            parts = []
            for paragraph in table_cell.findall(".//w:p", namespace):
                text = "".join((node.text or "") for node in paragraph.findall(".//w:t", namespace)).strip()
                if text:
                    parts.append(text)
            cells.append(" / ".join(parts))
        if any(cells):
            rows.append(cells)
    return rows


def build_mbti_questionnaire_from_rows(rows: list[list[str]], file_name: str) -> dict:
    numbered_rows = []
    for cells in rows:
        if len(cells) >= 2 and cells[0].strip().isdigit():
            numbered_rows.append((int(cells[0].strip()), cells[1].strip()))

    raw_questions = numbered_rows[-96:]
    if len(raw_questions) != 96 or raw_questions[0][0] != 1 or raw_questions[-1][0] != 96:
        raise ValueError("没有识别到 96 道连续编号的 MBTI 题。")

    topics = []
    for index, (topic_id, topic_name, description, letter, dimensions) in enumerate(MBTI_TOPIC_BLOCKS):
        block_questions = raw_questions[index * 12 : (index + 1) * 12]
        opening_number, opening_text = block_questions[0]
        sub_questions = [
            {
                "question_id": f"mbti_{number:02d}",
                "text": text,
                "dimension": topic_name,
                "score": {"letter": letter},
                "source_number": number,
            }
            for number, text in block_questions[1:]
        ]
        topics.append(
            {
                "topic_id": topic_id,
                "topic_name": topic_name,
                "description": description,
                "core_dimensions": dimensions,
                "opening_question": opening_text,
                "opening_question_id": f"mbti_{opening_number:02d}",
                "score": {"letter": letter},
                "source_number": opening_number,
                "sub_questions": sub_questions,
            }
        )

    return {
        "kind": "mbti",
        "invite_code": "MBTI-DEMO",
        "title": "MBTI 深度人格画像测试",
        "description": "通过 DeepLister 导入并转换的 96 题 MBTI 调研 Agent。用户按 1 到 5 分表达同意程度，系统汇总 E/I、S/N、T/F、J/P 倾向。",
        "source_file": file_name,
        "scale": DEFAULT_MBTI_SCALE,
        "topics": topics,
    }


def import_questionnaire(file_name: str, file_bytes: bytes) -> dict:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".json":
        questionnaire = json.loads(file_bytes.decode("utf-8-sig"))
        if not isinstance(questionnaire, dict) or not questionnaire.get("topics"):
            raise ValueError("JSON 里需要有 topics，DeepLister 才能转换成 Agent。")
        return questionnaire
    if suffix == ".docx":
        return build_mbti_questionnaire_from_rows(extract_docx_table_rows(file_bytes), file_name)
    raise ValueError("当前导入转换支持 JSON 问卷，以及这类 96 题 MBTI docx。")


TEMPLATES = {
    "mbti": make_agent_from_questionnaire(load_questionnaire_file(MBTI_QUESTIONNAIRE_FILE), invite_code="MBTI-DEMO"),
    "sample": {
        "kind": "sample",
        "title": "快速体验样例",
        "subtitle": "用四个问题展示 DeepLister 的追问和整理能力。",
        "invite_code": "SCL90-DEMO",
        "questions": SAMPLE_QUESTIONS,
    },
}

RESULT_TITLES = {
    "INTJ": "冷静施工中的人生建筑师",
    "INTP": "脑内开会型逻辑工程师",
    "ENTJ": "目标压路机型总指挥",
    "ENTP": "观点蹦迪型辩手",
    "INFJ": "温柔预言型观察家",
    "INFP": "情绪收藏型理想派",
    "ENFJ": "气氛照明型组织者",
    "ENFP": "灵感喷泉型选手",
    "ISTJ": "表格护城河型执行者",
    "ISFJ": "默默兜底但偶尔想下班的人",
    "ESTJ": "任务清仓型负责人",
    "ESFJ": "人情雷达型照顾者",
    "ISTP": "冷静拆解型问题处理器",
    "ISFP": "审美在线型自由人",
    "ESTP": "现场开麦型行动派",
    "ESFP": "快乐外放型氛围发动机",
}


def apply_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --sage: #E9E5D2;
            --forest: #315B46;
            --olive: #8A7D45;
            --mist: #FFF8EA;
            --ink: #2A241C;
            --muted: #756C5C;
            --line: rgba(127, 95, 49, 0.18);
            --blue: #4B6E70;
            --warm: #B9733F;
            --paper: rgba(255, 248, 234, 0.9);
        }
        .stApp {
            background:
                linear-gradient(180deg, #FFF8EA 0%, #F3E7D1 44%, #E9E5D2 100%);
            color: var(--ink);
            overflow-x: hidden;
        }
        body {
            overflow-x: hidden;
        }
        .block-container {
            max-width: 920px;
            padding: 1.25rem 1.1rem 5rem;
        }
        h1, h2, h3 {
            color: var(--forest);
            letter-spacing: 0;
        }
        h1 {
            font-size: clamp(1.9rem, 7vw, 3.2rem);
            line-height: 1.1;
        }
        [data-testid="stSidebar"] {
            background: rgba(255,248,234,0.96);
            border-right: 1px solid var(--line);
        }
        [data-testid="stSidebar"] code {
            color: var(--forest);
        }
        header.stAppHeader {
            background: rgba(255,248,234,0.94);
            border-bottom: 1px solid var(--line);
        }
        .stDeployButton,
        .stAppDeployButton,
        #MainMenu,
        [data-testid="stAppDeployButton"],
        [data-testid="stToolbarActions"],
        [data-testid="stMainMenu"],
        [data-testid="stMainMenuButton"] {
            display: none !important;
        }
        .home-hero {
            position: relative;
            display: block;
            padding: 1.2rem 0 0.2rem;
            overflow: hidden;
        }
        .hero-copy {
            min-width: 0;
            padding: 0.3rem 0;
        }
        .home-brand-lockup {
            display: flex;
            align-items: center;
            gap: 0.95rem;
            max-width: 720px;
        }
        .home-logo {
            width: clamp(74px, 12vw, 106px);
            height: auto;
            aspect-ratio: 1;
            object-fit: contain;
            flex: 0 0 auto;
            filter: drop-shadow(0 18px 24px rgba(37,92,70,0.14));
        }
        .home-brand-text {
            min-width: 0;
        }
        .eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 0.42rem;
            margin: 0 0 0.72rem;
            padding: 0.32rem 0.56rem;
            border: 1px solid var(--line);
            border-radius: 999px;
            background: rgba(255,248,234,0.74);
            color: var(--blue);
            font-size: 0.82rem;
            font-weight: 800;
        }
        .brand-title {
            margin: 0 0 0.42rem;
            font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif;
            font-size: clamp(3rem, 7.2vw, 4.7rem);
            font-weight: 850;
            line-height: 0.98;
            letter-spacing: 0;
            color: var(--forest);
        }
        .brand-title span {
            display: inline-block;
            margin-left: 0.42rem;
            color: var(--blue);
            font-size: 0.66em;
            font-weight: 850;
            line-height: 1;
            vertical-align: baseline;
        }
        .hero-subtitle {
            margin: 0 0 0.2rem;
            max-width: 540px;
            color: #695F50;
            font-size: clamp(1rem, 2.1vw, 1.12rem);
            line-height: 1.65;
            font-weight: 650;
        }
        .hero-lede {
            margin: 0;
            max-width: 620px;
            color: #695F50;
            font-size: clamp(1.02rem, 2.4vw, 1.18rem);
            line-height: 1.78;
        }
        .hero-actions {
            display: flex;
            flex-wrap: wrap;
            gap: 0.7rem;
            margin-top: 1.05rem;
        }
        .hero-button {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 3rem;
            padding: 0.74rem 1rem;
            border-radius: 8px;
            border: 1px solid var(--forest);
            text-decoration: none !important;
            font-weight: 850;
        }
        .hero-button.primary {
            background: var(--forest);
            color: var(--mist) !important;
            box-shadow: 0 14px 32px rgba(37,92,70,0.18);
        }
        .hero-button.secondary {
            background: rgba(255,248,234,0.86);
            color: var(--forest) !important;
        }
        .hero-proof {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.55rem;
            margin-top: 1rem;
        }
        .hero-proof span {
            border-left: 3px solid rgba(199,123,69,0.52);
            color: var(--muted);
            background: rgba(255,248,234,0.72);
            padding: 0.56rem 0.64rem;
            border-radius: 8px;
            font-size: 0.88rem;
            line-height: 1.45;
        }
        .home-visual {
            position: relative;
            display: grid;
            place-items: center;
            min-height: 286px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background:
                linear-gradient(145deg, rgba(255,248,234,0.95), rgba(233,229,210,0.72));
            box-shadow: 0 20px 42px rgba(127,95,49,0.14);
            overflow: hidden;
        }
        .hero-figure {
            position: relative;
            z-index: 2;
            display: block;
            width: 100%;
            height: 100%;
            max-width: 100%;
            object-fit: cover;
            margin: 0;
            filter: none;
        }
        .ambient-figure {
            display: none;
        }
        .stImage img {
            width: min(54vw, 220px) !important;
            display: block;
            margin: 0.2rem auto 0.7rem;
            border: 0;
            border-radius: 0;
            filter: drop-shadow(0 18px 24px rgba(37,92,70,0.12));
        }
        .home-grid {
            display: grid;
            grid-template-columns: 1.25fr 1fr 1fr;
            gap: 0.75rem;
            margin-top: 1rem;
        }
        .home-card {
            position: relative;
            overflow: hidden;
            min-height: 138px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            align-items: flex-start;
            text-align: left;
            gap: 0.8rem;
            border-radius: 8px;
            border: 1px solid var(--line);
            background: var(--paper);
            color: var(--forest) !important;
            text-decoration: none !important;
            padding: 1rem;
            box-shadow: 0 14px 30px rgba(127,95,49,0.09);
        }
        .home-card.primary {
            background: var(--forest);
            color: var(--mist) !important;
            box-shadow: 0 18px 36px rgba(127,95,49,0.18);
        }
        .home-card strong {
            font-size: clamp(1.12rem, 2.5vw, 1.36rem);
            line-height: 1.25;
        }
        .home-card small {
            color: var(--muted);
            line-height: 1.45;
        }
        .home-card.primary small {
            color: rgba(248,251,247,0.86);
        }
        .card-kicker {
            display: inline-flex;
            color: inherit;
            font-size: 0.78rem;
            font-weight: 850;
            opacity: 0.75;
        }
        .sample-pill, .back-link {
            display: inline-block;
            border: 1px solid rgba(199,123,69,0.26);
            border-radius: 999px;
            color: var(--forest) !important;
            background: rgba(255,248,234,0.8);
            padding: 0.52rem 0.75rem;
            text-decoration: none !important;
            font-weight: 700;
        }
        .flow-note {
            margin: 1rem 0 0;
            color: var(--muted);
            font-size: 0.92rem;
            line-height: 1.65;
        }
        .panel, .question-card, .trace-card {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--paper);
            padding: 1rem;
            box-shadow: 0 14px 34px rgba(127,95,49,0.09);
            margin: 0.75rem 0;
        }
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.65rem;
            margin: 0.85rem 0;
        }
        .metric-card {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: rgba(255,253,247,0.72);
            padding: 0.82rem;
            min-height: 94px;
        }
        .metric-card b {
            display: block;
            color: var(--forest);
            font-size: clamp(1.45rem, 4vw, 2.1rem);
            line-height: 1.05;
            margin-bottom: 0.34rem;
        }
        .metric-card span {
            display: block;
            color: var(--muted);
            font-size: 0.85rem;
            line-height: 1.45;
        }
        .insight-list {
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.55rem;
            margin: 0.75rem 0;
        }
        .insight-item {
            border-left: 4px solid rgba(49,91,70,0.52);
            background: rgba(255,253,247,0.72);
            border-radius: 8px;
            padding: 0.72rem 0.8rem;
            color: var(--muted);
            line-height: 1.62;
        }
        .insight-item b {
            color: var(--forest);
        }
        .agent-shell {
            margin-top: 0.7rem;
        }
        .agent-title-row {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
            margin: 0.7rem 0 0.4rem;
        }
        .agent-title-row h1 {
            margin-bottom: 0.2rem;
        }
        .question-meta {
            color: var(--blue);
            font-size: 0.88rem;
            font-weight: 800;
            margin-bottom: 0.45rem;
        }
        .question-main {
            color: var(--ink);
            font-size: clamp(1.18rem, 3vw, 1.44rem);
            font-weight: 850;
            line-height: 1.45;
        }
        .question-why {
            color: #656D60;
            border-top: 1px solid rgba(199,123,69,0.16);
            margin-top: 0.8rem;
            padding-top: 0.7rem;
            line-height: 1.65;
        }
        .progress-strip {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.5rem;
            margin: 0.65rem 0;
        }
        .progress-strip span {
            border-radius: 8px;
            background: rgba(255,248,234,0.78);
            border: 1px solid var(--line);
            color: #586654;
            padding: 0.52rem 0.62rem;
            font-size: 0.84rem;
            font-weight: 750;
        }
        div[data-testid="stTextArea"] textarea {
            min-height: 156px;
            border: 2px solid rgba(37,92,70,0.28);
            background: rgba(255,248,234,0.98);
            color: var(--ink);
            font-size: 1rem;
            border-radius: 8px;
            line-height: 1.62;
        }
        div.stButton > button,
        div.stDownloadButton > button {
            border-radius: 8px;
            min-height: 3rem;
            font-weight: 850;
            border: 1px solid var(--forest);
            background: var(--forest);
            color: var(--mist);
            box-shadow: 0 12px 24px rgba(37,92,70,0.14);
        }
        div.stButton > button:hover,
        div.stDownloadButton > button:hover {
            border-color: var(--blue);
            background: var(--blue);
            color: var(--mist);
        }
        .trace-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.55rem;
        }
        .trace-card {
            margin: 0;
            box-shadow: none;
            background: rgba(255,253,247,0.68);
        }
        .trace-card b {
            display: block;
            color: var(--forest);
            margin-bottom: 0.24rem;
        }
        .trace-card span {
            color: #365D4A;
            line-height: 1.55;
        }
        .result-card {
            border-radius: 8px;
            background:
                linear-gradient(135deg, var(--forest), #426777);
            color: var(--mist);
            padding: 1.2rem;
            margin: 0.8rem 0;
            box-shadow: 0 18px 36px rgba(37,92,70,0.16);
        }
        .result-card h2,
        .result-card h3 {
            color: var(--mist);
        }
        .result-card p {
            color: rgba(247,255,249,0.88);
            line-height: 1.7;
        }
        .result-actions-note {
            margin: 0.35rem 0 0.8rem;
            color: var(--muted);
            line-height: 1.65;
        }
        @media (min-width: 720px) {
            .trace-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 780px) {
            .home-hero {
                grid-template-columns: 1fr;
            }
            .home-visual {
                min-height: 220px;
            }
            .home-grid {
                grid-template-columns: 1fr;
            }
            .hero-proof {
                grid-template-columns: 1fr;
            }
            .metric-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 560px) {
            .block-container {
                padding-left: 0.85rem;
                padding-right: 0.85rem;
            }
            .home-brand-lockup {
                gap: 0.72rem;
            }
            .home-logo {
                width: 84px;
            }
            .brand-title span {
                display: block;
                margin-left: 0;
                margin-top: 0.2rem;
                font-size: 0.68em;
            }
            .home-card {
                min-height: 126px;
                padding: 0.8rem;
            }
            .hero-actions {
                flex-direction: column;
            }
            .progress-strip {
                grid-template-columns: 1fr;
            }
            .metric-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def sync_page() -> None:
    page = st.query_params.get("page", "home")
    st.session_state.page = page if page in ROUTES else "home"


def go_to(page: str, *, collapse_sidebar: bool = False) -> None:
    st.session_state.page = page
    st.query_params["page"] = page
    st.session_state.scroll_to_page_top = True
    if collapse_sidebar:
        st.session_state.collapse_sidebar_on_mobile = True
    st.rerun()


def scroll_to_page_top_once() -> None:
    should_scroll = bool(st.session_state.get("scroll_to_page_top"))
    should_collapse_sidebar = bool(st.session_state.get("collapse_sidebar_on_mobile"))
    if not should_scroll and not should_collapse_sidebar:
        return
    st.session_state.scroll_to_page_top = False
    st.session_state.collapse_sidebar_on_mobile = False
    components.html(
        f"""
        <script>
        const parentWindow = window.parent;
        const doc = parentWindow.document;
        const shouldScroll = {str(should_scroll).lower()};
        const shouldCollapseSidebar = {str(should_collapse_sidebar).lower()};

        if (shouldScroll) {{
          const containers = [
            parentWindow,
            doc.querySelector('[data-testid="stAppViewContainer"]'),
            doc.querySelector('.main')
          ];
          containers.forEach((target) => {{
            if (!target) return;
            if (target.scrollTo) {{
              target.scrollTo({{ top: 0, behavior: 'smooth' }});
            }} else {{
              target.scrollTop = 0;
            }}
          }});
        }}

        if (shouldCollapseSidebar) {{
          const collapseSidebarOnMobile = () => {{
            const viewportWidth = parentWindow.innerWidth || doc.documentElement.clientWidth;
            const sidebar = doc.querySelector('[data-testid="stSidebar"]');
            const sidebarWidth = sidebar ? sidebar.getBoundingClientRect().width : 0;
            if (viewportWidth > 900 || sidebarWidth < 50) return;

            const collapseButton = Array.from(doc.querySelectorAll('button')).find((button) => {{
              const rect = button.getBoundingClientRect();
              return (
                button.textContent &&
                button.textContent.includes('keyboard_double_arrow_left') &&
                rect.width > 0 &&
                rect.height > 0
              );
            }});
            if (collapseButton) {{
              collapseButton.click();
            }}
          }};
          [80, 180, 360, 700, 1100].forEach((delay) => {{
            window.setTimeout(collapseSidebarOnMobile, delay);
          }});
        }}
        </script>
        """,
        height=0,
    )


def reset_agent() -> None:
    for key in [
        "agent",
        "step",
        "answers",
        "traces",
        "pending_followup",
        "pending_import_agent",
        "harness_engine",
        "harness_state",
        "harness_llm_client",
        "user_id",
        "response_saved",
        "mbti_scores",
        "completed_at",
    ]:
        st.session_state.pop(key, None)


def image_data_url(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def make_import_agent(file_name: str, file_bytes: bytes | None = None) -> dict:
    if file_bytes is not None:
        questionnaire = import_questionnaire(file_name, file_bytes)
        return make_agent_from_questionnaire(
            questionnaire,
            file_name=file_name,
            invite_code=st.session_state.get("import_code", "DL-2026"),
        )
    return {
        "kind": "imported",
        "title": "导入问卷 Agent",
        "subtitle": f"已根据《{file_name}》生成演示 Agent。",
        "invite_code": st.session_state.get("import_code", "DL-2026"),
        "questions": [
            {
                "dimension": "调研目标",
                "question": "这份问卷最想了解的核心问题是什么？",
                "why": "先锁定调研目标，后续追问才不会跑偏。",
                "followup": "如果只能把目标写成一句问卷说明，你会怎么写？",
                "options": ["了解用户真实需求", "评估体验满意度", "判断方案是否可行"],
            },
            {
                "dimension": "使用场景",
                "question": "被调研者最典型的一个使用场景是什么？",
                "why": "场景越具体，Agent 最后填出的问卷越像真实访谈结果。",
                "followup": "这个场景通常发生在什么时候、什么地点、用户正在做什么？",
                "options": ["第一次接触产品", "完成一次任务后", "遇到问题反馈时"],
            },
            {
                "dimension": "追问重点",
                "question": "你最希望 Agent 追问清楚哪类细节？",
                "why": "这决定了 Agent 后续是追原因、追例子，还是追建议。",
                "followup": "为什么这类细节对你的问卷最重要？",
                "options": ["原因和动机", "具体例子", "改进建议"],
            },
        ],
    }


def survey_store():
    if "survey_store" not in st.session_state:
        st.session_state.survey_store = get_survey_store()
    return st.session_state.survey_store


FOLLOWUP_STRATEGIES = {
    "comprehension_correction",
    "consistency_confirmation",
    "depth_mining",
}

SOURCE_LABELS = {
    "campaign": "发起调研",
    "quick": "快速体验",
    "sample": "样例体验",
    "mbti": "MBTI 体验",
    "imported": "导入体验",
    "invite": "邀请码体验",
}


def safe_percent(part: int | float, total: int | float) -> float:
    return float(part) / float(total) if total else 0.0


def agent_primary_topic(agent: dict) -> str:
    dimensions = [
        str(question.get("dimension", "")).strip()
        for question in agent.get("questions", [])
        if str(question.get("dimension", "")).strip()
    ]
    unique_dimensions = list(dict.fromkeys(dimensions))
    if len(unique_dimensions) == 1:
        return unique_dimensions[0]
    if agent.get("kind") == "quick" and unique_dimensions:
        return unique_dimensions[0]
    return agent.get("title") or (unique_dimensions[0] if unique_dimensions else "未命名主题")


def system_response_bucket(agent: dict) -> str:
    kind = str(agent.get("kind") or "demo").lower()
    safe_kind = "".join(ch for ch in kind if ch.isalnum() or ch in {"_", "-"}).strip()
    return f"system_{safe_kind or 'demo'}"


def response_source(response: ResponseRecord) -> str:
    if response.source:
        return response.source
    if response.campaign_id.startswith("system_"):
        return response.campaign_id.replace("system_", "", 1)
    return "campaign"


def response_topic(response: ResponseRecord, campaigns_by_id: dict[str, Campaign]) -> str:
    if response.topic:
        return response.topic
    campaign = campaigns_by_id.get(response.campaign_id)
    if campaign is not None:
        return agent_primary_topic(campaign.agent)
    for answer in response.answers:
        dimension = str(answer.get("dimension", "")).strip()
        if dimension:
            return dimension
    return response.agent_title or response.campaign_id or "未知主题"


def decision_log_stats(logs: list[dict]) -> dict:
    stats = {
        "turns": len(logs),
        "followups": 0,
        "accepted": 0,
        "vague": 0,
        "consistency": 0,
        "sufficiency": 0,
        "safety": 0,
        "verification_failed": 0,
        "strategies": Counter(),
    }
    for log in logs:
        arbitration = log.get("arbitration_result", {}) or {}
        strategy = arbitration.get("strategy", "unknown")
        stats["strategies"][strategy] += 1
        if strategy in FOLLOWUP_STRATEGIES:
            stats["followups"] += 1

        evaluation = log.get("evaluation", {}) or {}
        if evaluation.get("accepted_answer"):
            stats["accepted"] += 1

        detection = log.get("detection_result", {}) or {}
        if (detection.get("comprehension", {}) or {}).get("triggered"):
            stats["vague"] += 1
        if (detection.get("consistency", {}) or {}).get("triggered"):
            stats["consistency"] += 1
        if (detection.get("sufficiency", {}) or {}).get("triggered"):
            stats["sufficiency"] += 1
        if (detection.get("safety", {}) or {}).get("triggered"):
            stats["safety"] += 1

        verification = log.get("verification_result", {}) or {}
        if verification and verification.get("passed") is False:
            stats["verification_failed"] += 1
    return stats


def developer_usage_metrics(
    responses: list[ResponseRecord],
    campaigns: list[Campaign],
    developer_logs: list[DeveloperLogPackage],
) -> dict:
    campaigns_by_id = {campaign.campaign_id: campaign for campaign in campaigns}
    all_decision_logs = [log for response in responses for log in response.decision_logs]
    stats = decision_log_stats(all_decision_logs)
    unique_users = {response.respondent_id for response in responses if response.respondent_id}
    source_counts = Counter(response_source(response) for response in responses)
    topic_counts = Counter(response_topic(response, campaigns_by_id) for response in responses)
    answer_count = sum(len(response.answers) for response in responses)
    llm_calls = sum(int(response.llm_call_count or 0) for response in responses)
    llm_responses = sum(1 for response in responses if response.llm_enabled or response.llm_call_count)

    return {
        "responses": len(responses),
        "unique_users": len(unique_users),
        "campaigns": len(campaigns),
        "developer_logs": len(developer_logs),
        "answers": answer_count,
        "turns": stats["turns"],
        "followups": stats["followups"],
        "followup_rate": safe_percent(stats["followups"], stats["turns"]),
        "accepted_rate": safe_percent(stats["accepted"], stats["turns"]),
        "vague_rate": safe_percent(stats["vague"], stats["turns"]),
        "consistency_rate": safe_percent(stats["consistency"], stats["turns"]),
        "sufficiency_rate": safe_percent(stats["sufficiency"], stats["turns"]),
        "verification_failed_rate": safe_percent(stats["verification_failed"], stats["turns"]),
        "llm_calls": llm_calls,
        "llm_responses": llm_responses,
        "sources": dict(source_counts),
        "topics": dict(topic_counts),
        "strategies": dict(stats["strategies"]),
    }


def developer_topic_rows(responses: list[ResponseRecord], campaigns: list[Campaign]) -> list[dict]:
    campaigns_by_id = {campaign.campaign_id: campaign for campaign in campaigns}
    grouped: dict[str, list[ResponseRecord]] = {}
    for response in responses:
        grouped.setdefault(response_topic(response, campaigns_by_id), []).append(response)

    rows = []
    for topic, topic_responses in sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True):
        logs = [log for response in topic_responses for log in response.decision_logs]
        stats = decision_log_stats(logs)
        rows.append(
            {
                "话题": topic,
                "答卷数": len(topic_responses),
                "回答数": sum(len(response.answers) for response in topic_responses),
                "追问率": f"{safe_percent(stats['followups'], stats['turns']):.0%}",
                "含糊率": f"{safe_percent(stats['vague'], stats['turns']):.0%}",
                "LLM 调用": sum(int(response.llm_call_count or 0) for response in topic_responses),
            }
        )
    return rows


def developer_source_rows(metrics: dict) -> list[dict]:
    return [
        {
            "来源": SOURCE_LABELS.get(source, source),
            "答卷数": count,
        }
        for source, count in sorted(metrics["sources"].items(), key=lambda item: item[1], reverse=True)
    ]


def developer_agent_impact_rows(metrics: dict, topic_rows: list[dict]) -> list[dict]:
    rows = []
    if metrics["vague_rate"] >= 0.35:
        rows.append(
            {
                "影响位置": "检测层",
                "数据发现": f"含糊回答比例 {metrics['vague_rate']:.0%}",
                "建议承接": "扩充模糊表达词库，并在题干里补充更具体的回答锚点。",
            }
        )
    else:
        rows.append(
            {
                "影响位置": "检测层",
                "数据发现": f"含糊回答比例 {metrics['vague_rate']:.0%}",
                "建议承接": "当前规则可继续作为稳定底座，先观察更多样本。",
            }
        )

    if metrics["followup_rate"] >= 0.45:
        rows.append(
            {
                "影响位置": "生成层",
                "数据发现": f"追问触发率 {metrics['followup_rate']:.0%}",
                "建议承接": "优先优化高触发话题的题干和追问 Prompt，减少重复追问。",
            }
        )
    else:
        rows.append(
            {
                "影响位置": "生成层",
                "数据发现": f"追问触发率 {metrics['followup_rate']:.0%}",
                "建议承接": "保持当前追问节奏，把新增样本作为人工标注池。",
            }
        )

    if metrics["verification_failed_rate"] > 0:
        rows.append(
            {
                "影响位置": "校验层",
                "数据发现": f"追问校验失败率 {metrics['verification_failed_rate']:.0%}",
                "建议承接": "收紧追问长度和策略一致性规则，避免 LLM 生成跑题。",
            }
        )

    if metrics["llm_calls"] > 0:
        rows.append(
            {
                "影响位置": "LLM 预算",
                "数据发现": f"累计模型调用 {metrics['llm_calls']} 次",
                "建议承接": "按话题查看消耗，给高消耗邀请码设置更低单人预算或切回规则追问。",
            }
        )

    if topic_rows:
        top_topic = topic_rows[0]["话题"]
        rows.append(
            {
                "影响位置": "题库/模板",
                "数据发现": f"当前最多使用的话题是「{top_topic}」",
                "建议承接": "优先补充这个话题的内置题库、示例答案和人工标注样本。",
            }
        )
    return rows


def anonymous_trace_summary(logs: list[dict], limit: int = 8) -> list[dict]:
    summary = []
    for index, log in enumerate(logs[:limit], start=1):
        detection = log.get("detection_result", {}) or {}
        triggered = [
            name
            for name in ["comprehension", "consistency", "sufficiency", "safety"]
            if (detection.get(name, {}) or {}).get("triggered")
        ]
        arbitration = log.get("arbitration_result", {}) or {}
        verification = log.get("verification_result", {}) or {}
        evaluation = log.get("evaluation", {}) or {}
        summary.append(
            {
                "turn": index,
                "strategy": arbitration.get("strategy", "unknown"),
                "priority": arbitration.get("priority", ""),
                "triggered_signals": triggered,
                "verification_passed": verification.get("passed"),
                "accepted_answer": evaluation.get("accepted_answer"),
            }
        )
    return summary


def build_developer_feedback_record(
    *,
    feedback_id: str,
    source: str,
    responses: list[ResponseRecord],
    campaign: Campaign | None = None,
) -> DeveloperFeedbackRecord:
    logs = [log for response in responses for log in response.decision_logs]
    stats = decision_log_stats(logs)
    topics = Counter(
        response.topic or response.agent_title or response.campaign_id
        for response in responses
        if response.topic or response.agent_title or response.campaign_id
    )
    top_topic = topics.most_common(1)[0][0] if topics else ""
    title = campaign.title if campaign is not None else (responses[0].agent_title if responses else "")
    invite_code = campaign.invite_code if campaign is not None else (responses[0].invite_code if responses else "")

    return DeveloperFeedbackRecord(
        feedback_id=feedback_id,
        source=source,
        campaign_id=campaign.campaign_id if campaign is not None else (responses[0].campaign_id if responses else None),
        invite_code=invite_code,
        title=title,
        topic=top_topic,
        response_count=len(responses),
        respondent_count=len({response.respondent_id for response in responses if response.respondent_id}),
        answer_count=sum(len(response.answers) for response in responses),
        turn_count=stats["turns"],
        followup_count=stats["followups"],
        followup_rate=safe_percent(stats["followups"], stats["turns"]),
        vague_rate=safe_percent(stats["vague"], stats["turns"]),
        llm_call_count=sum(int(response.llm_call_count or 0) for response in responses),
        topics=dict(topics),
        strategies=dict(stats["strategies"]),
        trace_summary=anonymous_trace_summary(logs),
        raw_access_allowed=bool(campaign and campaign.developer_raw_access_allowed),
        creator_storage=campaign.creator_storage if campaign is not None else {},
    )


def sync_campaign_developer_feedback(campaign: Campaign, responses: list[ResponseRecord]) -> None:
    store = survey_store()
    metrics = campaign_metrics(campaign, responses)
    store.save_result_export(campaign, responses, metrics)
    if not campaign.developer_feedback_enabled:
        return
    campaign.developer_feedback_synced_at = datetime.now().isoformat(timespec="seconds")
    store.create_campaign(campaign)
    store.save_developer_feedback(
        build_developer_feedback_record(
            feedback_id=f"campaign_{campaign.campaign_id}",
            source="campaign",
            responses=responses,
            campaign=campaign,
        )
    )


def sync_system_developer_feedback(response: ResponseRecord) -> None:
    source = response_source(response)
    survey_store().save_developer_feedback(
        build_developer_feedback_record(
            feedback_id=f"{source}_{response.response_id}",
            source=source,
            responses=[response],
        )
    )


def developer_feedback_metrics(records: list[DeveloperFeedbackRecord], developer_logs: list[DeveloperLogPackage]) -> dict:
    response_count = sum(record.response_count for record in records)
    answer_count = sum(record.answer_count for record in records)
    turn_count = sum(record.turn_count for record in records)
    followup_count = sum(record.followup_count for record in records)
    llm_calls = sum(record.llm_call_count for record in records)
    source_counts = Counter()
    topic_counts = Counter()
    strategies = Counter()
    for record in records:
        source_counts[record.source] += record.response_count
        if record.topic:
            topic_counts[record.topic] += record.response_count
        strategies.update(record.strategies)

    vague_weighted = sum(record.vague_rate * record.turn_count for record in records)
    return {
        "responses": response_count,
        "unique_users": sum(record.respondent_count for record in records),
        "campaigns": len({record.campaign_id for record in records if record.campaign_id and record.source == "campaign"}),
        "developer_logs": len(developer_logs),
        "answers": answer_count,
        "turns": turn_count,
        "followups": followup_count,
        "followup_rate": safe_percent(followup_count, turn_count),
        "accepted_rate": 0.0,
        "vague_rate": safe_percent(vague_weighted, turn_count),
        "consistency_rate": 0.0,
        "sufficiency_rate": 0.0,
        "verification_failed_rate": 0.0,
        "llm_calls": llm_calls,
        "llm_responses": sum(1 for record in records if record.llm_call_count),
        "sources": dict(source_counts),
        "topics": dict(topic_counts),
        "strategies": dict(strategies),
    }


def developer_feedback_topic_rows(records: list[DeveloperFeedbackRecord]) -> list[dict]:
    grouped: dict[str, list[DeveloperFeedbackRecord]] = {}
    for record in records:
        grouped.setdefault(record.topic or "未知主题", []).append(record)

    rows = []
    for topic, topic_records in sorted(grouped.items(), key=lambda item: sum(record.response_count for record in item[1]), reverse=True):
        turns = sum(record.turn_count for record in topic_records)
        followups = sum(record.followup_count for record in topic_records)
        vague_weighted = sum(record.vague_rate * record.turn_count for record in topic_records)
        rows.append(
            {
                "话题": topic,
                "答卷数": sum(record.response_count for record in topic_records),
                "回答数": sum(record.answer_count for record in topic_records),
                "追问率": f"{safe_percent(followups, turns):.0%}",
                "含糊率": f"{safe_percent(vague_weighted, turns):.0%}",
                "LLM 调用": sum(record.llm_call_count for record in topic_records),
            }
        )
    return rows


def streamlit_secrets() -> dict:
    try:
        return st.secrets
    except Exception:
        return {}


def load_developer_auth_config() -> GitHubOAuthConfig | None:
    return load_github_oauth_config(DEVELOPER_AUTH_FILE, secrets=streamlit_secrets())


def load_developer_oauth_states() -> dict[str, float]:
    if not DEVELOPER_OAUTH_STATE_FILE.exists():
        return {}
    try:
        payload = json.loads(DEVELOPER_OAUTH_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    states = {}
    for state, expires_at in payload.items():
        try:
            states[str(state)] = float(expires_at)
        except (TypeError, ValueError):
            continue
    return states


def save_developer_oauth_states(states: dict[str, float]) -> None:
    DEVELOPER_OAUTH_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEVELOPER_OAUTH_STATE_FILE.write_text(json.dumps(states, ensure_ascii=False, indent=2), encoding="utf-8")


def register_developer_oauth_state(state: str) -> None:
    now = time()
    states = {key: value for key, value in load_developer_oauth_states().items() if value > now}
    states[state] = now + 600
    save_developer_oauth_states(states)


def consume_developer_oauth_state(state: str) -> bool:
    now = time()
    states = {key: value for key, value in load_developer_oauth_states().items() if value > now}
    valid = bool(state and state in states)
    if valid:
        states.pop(state, None)
    save_developer_oauth_states(states)
    return valid


def save_developer_oauth_config(client_id: str, client_secret: str, redirect_uri: str) -> None:
    DEVELOPER_AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "github_oauth": {
            "client_id": client_id.strip(),
            "client_secret": client_secret.strip(),
            "redirect_uri": redirect_uri.strip(),
            "allowed_login": "sunrise-yc",
            "allowed_user_id": 292528736,
        },
        "source": "local",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DEVELOPER_AUTH_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def current_developer_page_url() -> str:
    try:
        current_url = st.context.url
    except Exception:
        current_url = ""
    if current_url:
        parts = urlsplit(current_url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path or "/", urlencode({"page": "developer"}), ""))
    return "http://localhost:8503/?page=developer"


def current_developer_redirect_uri(auth_config: GitHubOAuthConfig) -> str:
    if auth_config.redirect_uri:
        return auth_config.redirect_uri
    return current_developer_page_url()


def query_param_value(name: str) -> str:
    value = st.query_params.get(name, "")
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def reset_developer_oauth_query() -> None:
    st.query_params.clear()
    st.query_params["page"] = "developer"


def restart_developer_oauth() -> None:
    st.session_state.pop("developer_oauth_state", None)
    reset_developer_oauth_query()
    st.rerun()


def handle_developer_oauth_callback(auth_config: GitHubOAuthConfig, redirect_uri: str) -> bool:
    code = query_param_value("code")
    state = query_param_value("state")
    error = query_param_value("error")
    if not code and not state and not error:
        return False

    if error:
        description = query_param_value("error_description")
        st.error(f"GitHub 没有完成授权：{description or error}")
        if st.button("重新验证 GitHub 身份", use_container_width=True):
            restart_developer_oauth()
        return True

    expected_state = st.session_state.get("developer_oauth_state", "")
    valid_state = consume_developer_oauth_state(state) or bool(expected_state and state == expected_state)
    if not valid_state:
        st.error("GitHub 返回状态校验失败，请重新验证。")
        st.caption("这通常是 GitHub 跳转回来时换了浏览器会话、页面刷新或服务重载导致的。现在已改为服务端临时票据，请重新点一次验证。")
        if st.button("重新生成验证链接", use_container_width=True):
            restart_developer_oauth()
        return True

    try:
        access_token = exchange_code_for_token(auth_config, code, redirect_uri)
        github_user = fetch_authenticated_user(access_token)
    except GitHubOAuthError as exc:
        st.error(f"GitHub 认证失败：{exc}")
        if st.button("重新验证 GitHub 身份", use_container_width=True):
            restart_developer_oauth()
        return True

    if not is_allowed_developer(auth_config, github_user):
        st.error("当前 GitHub 账号不是开发者账号，无法进入开发者模式。")
        st.caption(f"当前账号：{github_user.login} · GitHub ID：{github_user.user_id}")
        if st.button("换一个 GitHub 账号重新验证", use_container_width=True):
            restart_developer_oauth()
        return True

    st.session_state.developer_authenticated = True
    st.session_state.developer_identity = f"github:{github_user.login}"
    st.session_state.developer_github_user = {
        "login": github_user.login,
        "id": github_user.user_id,
        "html_url": github_user.html_url,
    }
    st.session_state.pop("developer_oauth_state", None)
    reset_developer_oauth_query()
    st.rerun()
    return True


def render_developer_gate() -> bool:
    if st.session_state.get("developer_authenticated"):
        return True

    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.title("开发者模式")
    auth_config = load_developer_auth_config()

    if auth_config is None:
        suggested_redirect_uri = current_developer_page_url()
        st.markdown(
            """
            <div class="panel">
              <b>开发者认证未配置。</b>
              <p>开发者模式只接受 GitHub 平台确认过的 sunrise-yc 身份。请先配置 GitHub OAuth App 的 Client ID 和 Secret。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.code(
            "\n".join(
                [
                    "DEEPLISTER_GITHUB_CLIENT_ID=你的 GitHub OAuth Client ID",
                    "DEEPLISTER_GITHUB_CLIENT_SECRET=你的 GitHub OAuth Client Secret",
                    f"DEEPLISTER_GITHUB_REDIRECT_URI={suggested_redirect_uri}",
                ]
            ),
            language="text",
        )
        st.caption("没有配置时不会开放首次绑定，避免别人把自己绑定成开发者。")
        with st.expander("我已经创建了 GitHub OAuth App"):
            st.caption("这里保存的是 OAuth App 配置，不是绑定开发者账号。开发者身份仍然锁定为 sunrise-yc · 292528736。")
            client_id = st.text_input("Client ID")
            client_secret = st.text_input("Client Secret", type="password")
            redirect_uri = st.text_input("Authorization callback URL", value=suggested_redirect_uri)
            if st.button("保存 OAuth 配置", use_container_width=True):
                if not client_id.strip() or not client_secret.strip():
                    st.error("请先填写 Client ID 和 Client Secret。")
                    return False
                save_developer_oauth_config(client_id, client_secret, redirect_uri)
                st.success("OAuth 配置已保存。现在可以用 GitHub 验证开发者身份。")
                st.rerun()
        return False

    redirect_uri = current_developer_redirect_uri(auth_config)
    if handle_developer_oauth_callback(auth_config, redirect_uri):
        return False

    if not st.session_state.get("developer_oauth_state"):
        st.session_state.developer_oauth_state = token_urlsafe(24)
    register_developer_oauth_state(st.session_state.developer_oauth_state)
    authorize_url = build_github_authorize_url(auth_config, redirect_uri, st.session_state.developer_oauth_state)

    st.markdown(
        f"""
        <div class="panel">
          <b>用 GitHub 验证开发者身份。</b>
          <p>只允许 GitHub 返回的 {auth_config.allowed_login} · ID {auth_config.allowed_user_id} 进入。若当前浏览器已登录 GitHub，会很快回到这里。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.link_button("用 GitHub 验证开发者身份", authorize_url, use_container_width=True)
    if st.button("重新生成验证链接", use_container_width=True):
        st.session_state.pop("developer_oauth_state", None)
        st.rerun()
    with st.expander("OAuth 回调配置"):
        st.caption("GitHub OAuth App 的 Authorization callback URL 需要和这里保持一致。")
        st.code(redirect_uri, language="text")
    return False


def generate_invite_code() -> str:
    return f"DL-{token_hex(2).upper()}"


def answer_quick_options(question: dict, prompt: str, is_followup: bool) -> list[str]:
    explicit_options = [
        str(option).strip()
        for option in question.get("options", [])
        if str(option).strip()
    ]
    if explicit_options:
        return explicit_options
    if is_followup:
        return FOLLOWUP_OPEN_OPTIONS

    dimension = str(question.get("dimension", "")).strip()
    search_text = f"{dimension} {prompt}"
    for keyword, options in OPEN_QUESTION_OPTION_BANK.items():
        if keyword in search_text:
            return options
    return GENERIC_OPEN_OPTIONS


def render_llm_connection_fields(scope: str, help_text: str) -> tuple[str, str, str]:
    api_key = st.text_input(
        "OpenAI 兼容 API Key",
        type="password",
        help=help_text,
        key=f"{scope}_llm_api_key",
    )
    with st.expander("高级模型设置", expanded=False):
        base_url = st.text_input(
            "API Base URL",
            value=Config.OPENAI_BASE_URL,
            help="OpenAI 官方保持默认；其他服务填它的 OpenAI-compatible 地址。",
            key=f"{scope}_llm_base_url",
        )
        model = st.text_input(
            "模型名",
            value=Config.OPENAI_MODEL,
            help="例如 gpt-4o-mini，或兼容服务提供的模型名。",
            key=f"{scope}_llm_model",
        )
        st.caption("目前接的是 OpenAI-compatible Chat Completions。Anthropic、Gemini 等原生密钥需要通过兼容网关，或后续单独接入。")
    return api_key.strip(), base_url.strip(), model.strip()


def make_quick_agent(topic_name: str, question_count: int, questions: list[str] | None = None) -> dict:
    selected = (questions or QUICK_TOPIC_BANK.get(topic_name, []))[:question_count]
    if len(selected) < question_count:
        raise ValueError("题库数量不足，需要用大模型补题。")
    return {
        "kind": "quick",
        "title": f"{topic_name}快速体验",
        "subtitle": f"{question_count} 题体验版，用来感受 DeepLister 如何追问和整理回答。",
        "invite_code": "QUICK-DEMO",
        "questions": [
            {
                "dimension": topic_name,
                "question": text,
                "why": "这题用于形成一次完整的轻量体验，回答后系统会判断是否需要追问。",
                "followup": "能不能补一个最近发生的具体例子？",
                "options": OPEN_QUESTION_OPTION_BANK.get(topic_name, GENERIC_OPEN_OPTIONS),
            }
            for text in selected
        ],
    }


def generate_questions_with_api(
    topic: str,
    question_count: int,
    api_key: str,
    base_url: str = "",
    model: str = "",
) -> list[str]:
    client = LLMClient(api_key=api_key, base_url=base_url or None, model=model or None)
    messages = [
        {
            "role": "system",
            "content": "你是问卷设计助手。输出 JSON 数组，数组里只放中文问题字符串，不要解释。",
        },
        {
            "role": "user",
            "content": f"请围绕“{topic}”生成 {question_count} 个适合 DeepLister 追问式调研的开放问题。",
        },
    ]
    data = client.chat_json(messages, temperature=0.5)
    if not isinstance(data, list) or len(data) < question_count:
        raise ValueError("大模型没有返回足够的问题。")
    return [str(item).strip() for item in data[:question_count] if str(item).strip()]


def create_campaign_from_agent(
    agent: dict,
    *,
    max_respondents: int,
    llm_enabled: bool,
    max_llm_calls_per_response: int,
    api_key: str = "",
    api_base_url: str = "",
    model: str = "",
    developer_feedback_enabled: bool = True,
    developer_raw_access_allowed: bool = True,
) -> Campaign:
    campaign_agent = deepcopy(agent)
    if llm_enabled:
        campaign_agent["llm_base_url"] = api_base_url or Config.OPENAI_BASE_URL
        campaign_agent["llm_model"] = model or Config.OPENAI_MODEL
    campaign = Campaign(
        invite_code=generate_invite_code(),
        title=campaign_agent["title"],
        description=campaign_agent.get("subtitle", ""),
        agent=campaign_agent,
        max_respondents=max_respondents,
        llm_enabled=llm_enabled,
        max_llm_calls_per_response=max_llm_calls_per_response if llm_enabled else 0,
        developer_feedback_enabled=developer_feedback_enabled,
        developer_raw_access_allowed=developer_raw_access_allowed,
    )
    campaign.creator_storage = survey_store().creator_storage_descriptor(campaign.campaign_id)
    survey_store().create_campaign(campaign)
    if api_key:
        put_campaign_api_key(campaign.campaign_id, api_key)
    return campaign


def make_invite_agent(code: str) -> dict:
    if code == "MBTI-DEMO":
        return deepcopy(TEMPLATES["mbti"])
    if code == "SCL90-DEMO":
        return deepcopy(TEMPLATES["sample"])
    campaign = survey_store().get_campaign_by_code(code)
    if campaign is not None:
        agent = deepcopy(campaign.agent)
        agent["kind"] = "campaign"
        agent["campaign_id"] = campaign.campaign_id
        agent["invite_code"] = campaign.invite_code
        agent["llm_enabled"] = campaign.llm_enabled
        agent["max_llm_calls_per_response"] = campaign.max_llm_calls_per_response
        return agent
    agent = deepcopy(TEMPLATES["sample"])
    agent["kind"] = "invite"
    agent["title"] = "他人制作的调研 Agent"
    agent["subtitle"] = f"邀请码：{code}"
    agent["invite_code"] = code
    return agent


def questionnaire_from_agent(agent: dict) -> Questionnaire:
    topics = []
    for index, question in enumerate(agent.get("questions", []), start=1):
        dimension = question.get("dimension") or f"问题 {index}"
        topics.append(
            Topic(
                topic_id=f"q_{index:03d}",
                topic_name=dimension,
                description=question.get("why") or dimension,
                core_dimensions=[dimension],
                opening_question=question["question"],
                sub_questions=[],
            )
        )
    return Questionnaire(
        title=agent.get("title", "DeepLister Agent"),
        description=agent.get("subtitle", ""),
        topics=topics,
    )


def init_harness(agent: dict) -> None:
    api_key = ""
    if agent.get("kind") == "campaign":
        api_key = get_campaign_api_key(agent.get("campaign_id"))
    elif agent.get("quick_api_key"):
        api_key = agent.get("quick_api_key", "")

    llm_enabled = bool(agent.get("llm_enabled") and api_key)
    llm_client = (
        LLMClient(
            api_key=api_key,
            base_url=agent.get("llm_base_url"),
            model=agent.get("llm_model"),
        )
        if llm_enabled
        else None
    )
    st.session_state.harness_llm_client = llm_client
    st.session_state.harness_engine = HarnessEngine(
        questionnaire_from_agent(agent),
        detector=Detector(llm_client=llm_client, use_llm=llm_enabled),
        generator=Generator(llm_client=llm_client, use_llm=llm_enabled),
        verifier=Verifier(llm_client=llm_client, use_llm=llm_enabled),
    )
    st.session_state.harness_state = HarnessSession()
    st.session_state.user_id = f"web_{datetime.now().strftime('%Y%m%d%H%M%S')}"


def start_agent(kind: str, *, file_name: str | None = None, invite_code: str | None = None) -> None:
    if kind == "imported":
        agent = deepcopy(st.session_state.get("pending_import_agent") or make_import_agent(file_name or "导入问卷"))
    elif kind == "invite":
        agent = make_invite_agent((invite_code or "SCL90-DEMO").strip().upper())
    else:
        agent = deepcopy(TEMPLATES[kind])

    st.session_state.agent = agent
    st.session_state.step = 0
    st.session_state.answers = []
    st.session_state.traces = []
    st.session_state.pending_followup = False
    st.session_state.mbti_scores = {letter: 0 for letter in "EISNTFJP"}
    st.session_state.completed_at = None
    st.session_state.response_saved = False
    init_harness(agent)


def current_agent() -> dict:
    if "agent" not in st.session_state:
        start_agent("sample")
    return st.session_state.agent


def current_harness() -> tuple[HarnessEngine, HarnessSession]:
    agent = current_agent()
    if "harness_engine" not in st.session_state or "harness_state" not in st.session_state:
        init_harness(agent)
    return st.session_state.harness_engine, st.session_state.harness_state


def current_question() -> dict:
    agent = current_agent()
    _, state = current_harness()
    step = min(state.topic_index, len(agent["questions"]) - 1)
    st.session_state.step = step
    return agent["questions"][step]


def add_scores(scores: dict | None) -> None:
    if not scores:
        return
    for letter, value in scores.items():
        st.session_state.mbti_scores[letter] = st.session_state.mbti_scores.get(letter, 0) + value


def submit_answer(answer: str, scores: dict | None = None) -> None:
    answer = answer.strip()
    if not answer:
        return

    agent = current_agent()
    question = current_question()
    engine, state = current_harness()
    was_followup = state.pending_followup is not None

    if agent["kind"] == "mbti":
        add_scores(scores)

    llm_client = st.session_state.get("harness_llm_client")
    max_calls = int(agent.get("max_llm_calls_per_response") or 0)
    if llm_client is not None and max_calls and llm_client.call_count >= max_calls:
        engine.detector.use_llm = False
        engine.generator.use_llm = False
        engine.verifier.use_llm = False

    result = engine.process_reply(
        state,
        st.session_state.get("user_id", "web_user"),
        answer,
        allow_follow_up=not (agent["kind"] == "mbti" and scores),
    )

    st.session_state.answers.append(
        {
            "dimension": question["dimension"],
            "question": question["question"],
            "answer": answer,
            "was_followup": was_followup,
            "accepted": not result["needs_follow_up"],
        }
    )
    if result.get("trace"):
        st.session_state.traces.append(result["trace"])
    st.session_state.pending_followup = state.pending_followup is not None
    st.session_state.step = state.topic_index

    if result["all_completed"]:
        st.session_state.completed_at = datetime.now().isoformat(timespec="seconds")
        go_to("complete")
    st.session_state.scroll_to_page_top = True
    st.rerun()


def mbti_type() -> str:
    scores = st.session_state.get("mbti_scores", {})
    return "".join(
        [
            "E" if scores.get("E", 0) >= scores.get("I", 0) else "I",
            "N" if scores.get("N", 0) >= scores.get("S", 0) else "S",
            "F" if scores.get("F", 0) >= scores.get("T", 0) else "T",
            "P" if scores.get("P", 0) >= scores.get("J", 0) else "J",
        ]
    )


def result_summary() -> dict:
    agent = current_agent()
    if agent["kind"] == "mbti":
        code = mbti_type()
        title = RESULT_TITLES.get(code, "清醒发电型选手")
        return {
            "headline": f"经过测试，你的人格是：{code}",
            "title": title,
            "description": f"你像是“{title}”。DeepLister 已经把你的回答整理成可导出的已填写问卷。",
        }
    return {
        "headline": "恭喜你完成调研",
        "title": "Agent 已整理出已填写问卷",
        "description": "下面可以导出结果，也可以逐题查看 DeepLister 的四层处理过程。",
    }


def export_payload() -> str:
    agent = current_agent()
    payload = {
        "product": "DeepLister",
        "agent": agent["title"],
        "invite_code": agent.get("invite_code"),
        "completed_at": st.session_state.get("completed_at"),
        "result": result_summary(),
        "filled_questionnaire": [
            {
                "dimension": item["dimension"],
                "question": item["question"],
                "agent_filled_answer": item["answer"],
            }
            for item in st.session_state.get("answers", [])
        ],
        "four_layer_trace": st.session_state.get("traces", []),
        "decision_logs": [
            log.model_dump(mode="json")
            for log in getattr(st.session_state.get("harness_state"), "logs", [])
        ],
    }
    if agent["kind"] == "mbti":
        payload["mbti_type"] = mbti_type()
        payload["mbti_scores"] = st.session_state.get("mbti_scores", {})
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_response_record() -> ResponseRecord | None:
    agent = current_agent()
    campaign_id = agent.get("campaign_id") or system_response_bucket(agent)
    state = st.session_state.get("harness_state")
    llm_client = st.session_state.get("harness_llm_client")
    return ResponseRecord(
        campaign_id=campaign_id,
        respondent_id=st.session_state.get("user_id", "web_user"),
        source=agent.get("kind", "demo"),
        agent_title=agent.get("title", "DeepLister Agent"),
        invite_code=agent.get("invite_code", ""),
        topic=agent_primary_topic(agent),
        question_count=len(agent.get("questions", [])),
        llm_enabled=bool(agent.get("llm_enabled")),
        engine_mode="llm" if llm_client is not None else "rules",
        answers=st.session_state.get("answers", []),
        decision_logs=[log.model_dump(mode="json") for log in getattr(state, "logs", [])],
        traces=st.session_state.get("traces", []),
        result_summary=result_summary(),
        llm_call_count=getattr(llm_client, "call_count", 0),
    )


def save_completed_response_once() -> None:
    if st.session_state.get("response_saved"):
        return
    response = build_response_record()
    if response is None:
        return
    if response.campaign_id.startswith("system_"):
        sync_system_developer_feedback(response)
    else:
        survey_store().save_response(response)
    st.session_state.response_saved = True


def render_sidebar() -> None:
    st.sidebar.title("DeepLister")
    st.sidebar.caption("追问式调研工作台")
    if st.sidebar.button("回到首页", use_container_width=True):
        reset_agent()
        go_to("home", collapse_sidebar=True)
    st.sidebar.markdown("工作台")
    if st.sidebar.button("发起调研", use_container_width=True):
        go_to("launch", collapse_sidebar=True)
    if st.sidebar.button("输入邀请码", use_container_width=True):
        go_to("take", collapse_sidebar=True)
    if st.sidebar.button("快速体验", use_container_width=True):
        go_to("quick", collapse_sidebar=True)
    if st.sidebar.button("调研结果", use_container_width=True):
        go_to("results", collapse_sidebar=True)
    if st.sidebar.button("存储设置", use_container_width=True):
        go_to("storage", collapse_sidebar=True)
    st.sidebar.markdown("开发者")
    if st.sidebar.button("开发者模式", use_container_width=True):
        go_to("developer", collapse_sidebar=True)
    st.sidebar.markdown("兼容邀请码")
    st.sidebar.code("MBTI-DEMO\nSCL90-DEMO")


def render_trace(trace: dict) -> None:
    st.markdown(
        f"""
        <div class="trace-grid">
          <div class="trace-card"><b>1. 检测层</b><span>{trace["detection"]}</span></div>
          <div class="trace-card"><b>2. 仲裁层</b><span>{trace["arbitration"]}</span></div>
          <div class="trace-card"><b>3. 生成层</b><span>{trace["generation"]}</span></div>
          <div class="trace-card"><b>4. 校验层</b><span>{trace["verification"]}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_home() -> None:
    reset_agent()
    logo_src = image_data_url(LOGO_IMAGE)
    logo_img = f'<img class="home-logo" src="{logo_src}" alt="倾听者 DeepLister 标识">' if logo_src else ""
    st.markdown(
        f"""
        <div class="home-hero">
          <div class="hero-copy">
            <div class="home-brand-lockup">
              {logo_img}
              <div class="home-brand-text">
                <h1 class="brand-title">倾听者<span>DeepLister</span></h1>
                <p class="hero-subtitle">把问卷变成一次会追问的访谈</p>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="home-grid">
          <a class="home-card primary" href="?page=launch">
            <span class="card-kicker">发起者</span>
            <strong>发起调研</strong>
            <small>创建问卷、设置访问人数、生成邀请码并回收答卷。</small>
          </a>
          <a class="home-card" href="?page=take">
            <span class="card-kicker">被邀请者</span>
            <strong>输入邀请码</strong>
            <small>输入邀请码，完成调研并提交答卷。</small>
          </a>
          <a class="home-card" href="?page=quick">
            <span class="card-kicker">体验者</span>
            <strong>快速体验</strong>
            <small>选择主题和题量，也可以自定义主题生成体验问卷。</small>
          </a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_import() -> None:
    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.title("请导入你的调查问卷")
    st.markdown(
        """
        <div class="panel">
          <b>上传后会生成一个调研 Agent。</b>
          <p>你可以自己开始作答，也可以复制邀请码让别人进入。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader(
        "上传问卷文件",
        type=["txt", "json", "csv", "docx", "pdf", "xlsx"],
        label_visibility="collapsed",
    )
    if uploaded is None:
        return

    st.session_state.import_code = f"DL-{abs(hash(uploaded.name)) % 9000 + 1000}"
    try:
        imported_agent = make_import_agent(uploaded.name, uploaded.getvalue())
    except ValueError as error:
        st.error(f"这份文件暂时没法转换：{error}")
        return

    st.session_state.pending_import_agent = imported_agent
    topic_count = len(imported_agent.get("questionnaire", {}).get("topics", []))
    question_count = len(imported_agent.get("questions", []))
    st.markdown(
        f"""
        <div class="panel">
          <b>已生成调研 Agent</b>
          <p>{uploaded.name}</p>
          <p>{imported_agent["title"]} · {topic_count} 个主题 · {question_count} 道题</p>
          <p>邀请码：<b>{st.session_state.import_code}</b></p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("开始作答", use_container_width=True):
        start_agent("imported", file_name=uploaded.name)
        go_to("agent")


def render_invite() -> None:
    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.title("请输入邀请码")
    code = st.text_input("邀请码", placeholder="例如 MBTI-DEMO 或 SCL90-DEMO", label_visibility="collapsed")
    if st.button("进入调研 Agent", use_container_width=True):
        start_agent("invite", invite_code=code or "SCL90-DEMO")
        go_to("agent")


def render_agent() -> None:
    agent = current_agent()
    engine, state = current_harness()
    engine_question = engine.get_current_question(state)
    if engine_question is None:
        st.session_state.completed_at = datetime.now().isoformat(timespec="seconds")
        go_to("complete")

    step = min(state.topic_index, len(agent["questions"]) - 1)
    st.session_state.step = step
    question = current_question()
    total = len(agent["questions"])
    is_followup = bool(engine_question["is_followup"])
    prompt = engine_question["text"]

    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="agent-title-row">
          <div>
            <h1>{agent["title"]}</h1>
            <p class="flow-note">{agent["subtitle"]}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="agent-shell">
        <div class="progress-strip">
          <span>进度 {min(step + 1, total)} / {total}</span>
          <span>主题 {question["dimension"]}</span>
          <span>邀请码 {agent.get("invite_code", "DL-DEMO")}</span>
        </div>
        <div class="question-card">
          <div class="question-meta">{'AI 追问' if is_followup else '当前问题'} · {question["dimension"]}</div>
          <div class="question-main">{prompt}</div>
          <div class="question-why">{question["why"]}</div>
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    answer = st.text_area("输入回答", placeholder="像聊天一样回答就好，不需要写得很正式。", key=f"answer_{step}_{state.turn_id}_{is_followup}")
    if st.button("提交回答", use_container_width=True):
        submit_answer(answer)

    quick_options = answer_quick_options(question, prompt, is_followup)
    with st.expander("没有思路？展开快速选择", expanded=False):
        st.caption("快速选择只是辅助，想省时间可以直接点一个。")
        for index, option in enumerate(quick_options):
            score = None
            if agent["kind"] == "mbti":
                scores = question.get("scores", [])
                score = scores[index] if index < len(scores) else None
            if st.button(option, key=f"quick_{step}_{is_followup}_{index}", use_container_width=True):
                submit_answer(option, score)

    if st.session_state.get("traces"):
        with st.expander("查看上一题的追问判断", expanded=False):
            render_trace(st.session_state.traces[-1])


def render_complete() -> None:
    save_completed_response_once()
    summary = result_summary()
    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="result-card">
          <h2>{summary["headline"]}</h2>
          <h3>{summary["title"]}</h3>
          <p>{summary["description"]}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <p class="result-actions-note">
          下面可以导出这次填写结果；本次答卷也会进入产品使用数据池，用来帮助开发者复盘 Agent 表现。
        </p>
        """,
        unsafe_allow_html=True,
    )
    st.download_button(
        "导出已填写问卷",
        data=export_payload(),
        file_name=f"deeplister-filled-questionnaire.json",
        mime="application/json",
        use_container_width=True,
    )
    if st.button("加入人工复盘样本", use_container_width=True):
        package = DeveloperLogPackage(
            source="completion_page",
            campaign_id=current_agent().get("campaign_id"),
            response_id=None,
            payload=json.loads(export_payload()),
        )
        survey_store().save_developer_log(package)
        st.success("已加入人工复盘样本池。")
    for index, trace in enumerate(st.session_state.get("traces", []), start=1):
        with st.expander(f"第 {index} 次追问判断", expanded=False):
            render_trace(trace)


def campaign_metrics(campaign: Campaign, responses: list[ResponseRecord]) -> dict:
    total_turns = sum(len(response.decision_logs) for response in responses)
    followups = 0
    accepted = 0
    vague = 0
    for response in responses:
        for log in response.decision_logs:
            strategy = log.get("arbitration_result", {}).get("strategy")
            if strategy in {"comprehension_correction", "consistency_confirmation", "depth_mining"}:
                followups += 1
            if log.get("evaluation", {}).get("accepted_answer"):
                accepted += 1
            if log.get("detection_result", {}).get("comprehension", {}).get("triggered"):
                vague += 1
    return {
        "responses": len(responses),
        "capacity": campaign.max_respondents,
        "completion_rate": len(responses) / campaign.max_respondents if campaign.max_respondents else 0,
        "avg_followups": followups / len(responses) if responses else 0,
        "followup_rate": followups / total_turns if total_turns else 0,
        "vague_rate": vague / total_turns if total_turns else 0,
        "accepted_rate": accepted / total_turns if total_turns else 0,
    }


def render_launch() -> None:
    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.title("发起调研")
    st.markdown(
        """
        <div class="panel">
          <b>先创建调研项目，再生成邀请码。</b>
          <p>邀请码对应一份调研项目；被调研者提交后，答卷会回收到这里。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    source = st.radio("问卷来源", ["内置样例", "上传问卷", "手动写题"], horizontal=True)
    agent = None
    if source == "内置样例":
        template = st.selectbox("选择样例", ["快速体验样例", "MBTI 深度人格画像"])
        agent = deepcopy(TEMPLATES["mbti"] if template.startswith("MBTI") else TEMPLATES["sample"])
    elif source == "上传问卷":
        uploaded = st.file_uploader("上传 JSON 或 docx 问卷", type=["json", "docx"])
        if uploaded is not None:
            try:
                agent = make_import_agent(uploaded.name, uploaded.getvalue())
                st.success(f"已识别 {len(agent['questions'])} 道题。")
            except ValueError as error:
                st.error(f"这份文件暂时没法转换：{error}")
    else:
        title = st.text_input("调研标题", value="我的调研")
        raw_questions = st.text_area("每行一个问题", placeholder="例如：\n你第一次使用这个产品时最困惑的地方是什么？\n你最希望它改进哪一点？")
        questions = [line.strip() for line in raw_questions.splitlines() if line.strip()]
        if questions:
            agent = {
                "kind": "manual",
                "title": title,
                "subtitle": "由发起调研者手动创建的问题。",
                "invite_code": "MANUAL",
                "questions": [
                    {
                        "dimension": title,
                        "question": text,
                        "why": "这题来自发起者手动创建，用于收集开放回答。",
                        "followup": "能不能补一个具体例子？",
                        "options": GENERIC_OPEN_OPTIONS,
                    }
                    for text in questions
                ],
            }

    max_respondents = st.number_input("预计被访问者数量上限", min_value=1, max_value=500, value=20, step=1)
    llm_enabled = st.checkbox("作答阶段启用大模型检测/生成/校验", value=False)
    max_calls = 0
    api_key = ""
    api_base_url = ""
    llm_model = ""
    if llm_enabled:
        max_calls = st.number_input("每份答卷最大模型调用次数", min_value=1, max_value=200, value=24, step=1)
        st.info("仲裁层仍然使用硬规则；大模型只参与检测、生成、校验。超预算后自动降级为规则 Harness。")
        api_key, api_base_url, llm_model = render_llm_connection_fields(
            "launch",
            "只保存在当前服务内存中，不写入邀请码、链接或答卷文件。",
        )
        st.caption(f"最多 {max_respondents} 人，每人最多 {max_calls} 次模型调用。")

    st.markdown("### 项目存储与回流")
    st.markdown(
        """
        <div class="panel">
          <b>完整答卷归发起者项目存储。</b>
          <p>当前版本用本地目录模拟发起者云盘；开发者云盘只接收匿名统计和追问摘要，不保存 API Key。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    developer_feedback_enabled = st.checkbox("同步匿名指标到开发者云盘", value=True)
    developer_raw_access_allowed = st.checkbox(
        "允许开发者调阅原始项目数据",
        value=True,
        help="默认开启，便于开发者排查 Agent 问题；关闭后开发者只能看到匿名指标，不能在开发者页打开原始答卷。",
    )

    if st.button("生成邀请码", use_container_width=True):
        if agent is None:
            st.error("请先准备一份问卷。")
            return
        if llm_enabled and not api_key:
            st.error("启用大模型时，需要先输入 API Key。")
            return
        campaign = create_campaign_from_agent(
            agent,
            max_respondents=int(max_respondents),
            llm_enabled=llm_enabled,
            max_llm_calls_per_response=int(max_calls),
            api_key=api_key,
            api_base_url=api_base_url,
            model=llm_model,
            developer_feedback_enabled=developer_feedback_enabled,
            developer_raw_access_allowed=developer_raw_access_allowed,
        )
        st.session_state.last_campaign_id = campaign.campaign_id
        st.session_state.last_manage_token = campaign.manage_token
        st.success("调研项目已创建。")
        st.code(campaign.invite_code)
        st.caption(f"发起者项目存储：{campaign.creator_storage.get('path', '本地模拟云盘')}")
        st.markdown(f"[填写链接](?page=take&code={campaign.invite_code})")
        st.markdown(f"[结果复盘](?page=results&campaign_id={campaign.campaign_id}&token={campaign.manage_token})")


def render_take() -> None:
    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.title("输入邀请码")
    initial_code = st.query_params.get("code", "")
    code = st.text_input("邀请码", value=initial_code, placeholder="例如 DL-AB12 或 SCL90-DEMO")
    if st.button("进入调研", use_container_width=True):
        normalized = (code or "SCL90-DEMO").strip().upper()
        campaign = survey_store().get_campaign_by_code(normalized)
        if campaign is not None:
            responses = survey_store().list_responses(campaign.campaign_id)
            if len(responses) >= campaign.max_respondents:
                st.error("这个调研已经达到回收上限。")
                return
        start_agent("invite", invite_code=normalized)
        go_to("agent")


def render_quick() -> None:
    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.title("快速体验")
    topic_choice = st.selectbox("选择主题", list(QUICK_TOPIC_BANK.keys()) + ["自定义主题"])
    question_count = st.select_slider("题目数量", options=[5, 8, 12], value=8)
    topic_name = topic_choice
    needs_question_generation = topic_choice == "自定义主题"
    followup_mode = st.radio(
        "追问模式",
        ["规则追问", "LLM 追问"],
        index=1 if needs_question_generation else 0,
        horizontal=True,
    )
    use_llm_followup = followup_mode == "LLM 追问"
    max_llm_calls = int(question_count) * 3
    api_key = ""
    api_base_url = ""
    llm_model = ""
    if needs_question_generation:
        topic_name = st.text_input("写下你想测试的主题", placeholder="例如：大学生外卖消费偏好")
        st.caption("如果内置题库没有这个主题，需要临时接入大模型生成题目。")
    if needs_question_generation or use_llm_followup:
        api_key, api_base_url, llm_model = render_llm_connection_fields(
            "quick",
            "只用于本次快速体验，不写入邀请码、链接或答卷文件。",
        )
    if use_llm_followup:
        max_llm_calls = st.number_input(
            "本次体验最大模型调用次数",
            min_value=1,
            max_value=200,
            value=max_llm_calls,
            step=1,
        )
        st.caption("开启后，检测、追问生成、校验会尝试调用大模型；仲裁层仍然使用稳定规则。")

    if st.button("生成体验问卷", use_container_width=True):
        if not topic_name:
            st.error("请先填写主题。")
            return
        if needs_question_generation and not api_key:
            st.error("自定义主题需要 API Key 来生成题目。")
            return
        if use_llm_followup and not api_key:
            st.error("启用大模型追问时，需要先输入 API Key。")
            return
        try:
            if needs_question_generation:
                questions = generate_questions_with_api(topic_name, int(question_count), api_key, api_base_url, llm_model)
                agent = make_quick_agent(topic_name, int(question_count), questions)
            else:
                agent = make_quick_agent(topic_name, int(question_count))
            if use_llm_followup:
                agent["llm_enabled"] = True
                agent["quick_api_key"] = api_key
                agent["llm_base_url"] = api_base_url or Config.OPENAI_BASE_URL
                agent["llm_model"] = llm_model or Config.OPENAI_MODEL
                agent["max_llm_calls_per_response"] = int(max_llm_calls)
            st.session_state.quick_agent = agent
            st.success("体验问卷已生成。")
        except Exception as error:
            st.error(f"暂时没能生成体验问卷：{error}")

    if st.session_state.get("quick_agent"):
        agent = st.session_state.quick_agent
        st.markdown(
            f"""
            <div class="panel">
              <b>{agent["title"]}</b>
              <p>{len(agent["questions"])} 道题 · {"LLM 追问" if agent.get("llm_enabled") else "规则追问"} · 完成后可以查看结果复盘和追问开箱。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("开始体验", use_container_width=True):
            st.session_state.agent = deepcopy(agent)
            st.session_state.step = 0
            st.session_state.answers = []
            st.session_state.traces = []
            st.session_state.pending_followup = False
            st.session_state.mbti_scores = {letter: 0 for letter in "EISNTFJP"}
            st.session_state.completed_at = None
            st.session_state.response_saved = False
            init_harness(st.session_state.agent)
            go_to("agent")


def render_results() -> None:
    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.title("调研结果复盘")
    campaign_id = st.query_params.get("campaign_id", "")
    token = st.query_params.get("token", "")
    campaigns = survey_store().list_campaigns()
    campaign = survey_store().get_campaign(campaign_id) if campaign_id else None

    if campaign is None:
        options = {f"{item.title} · {item.invite_code}": item for item in campaigns}
        if not options:
            st.info("还没有调研项目。请先发起调研。")
            return
        selected = st.selectbox("选择调研项目", list(options.keys()))
        campaign = options[selected]
        token = st.text_input("管理口令", type="password", placeholder="创建项目时生成的管理 token")

    if token and token != campaign.manage_token:
        st.error("管理口令不正确。")
        return
    if not token and campaign_id:
        st.error("缺少管理口令。")
        return

    responses = survey_store().list_responses(campaign.campaign_id)
    metrics = campaign_metrics(campaign, responses)
    sync_campaign_developer_feedback(campaign, responses)
    st.markdown(
        f"""
        <div class="panel">
          <b>{campaign.title}</b>
          <p>邀请码：{campaign.invite_code} · 回收 {metrics["responses"]}/{metrics["capacity"]} 份</p>
          <p>平均追问 {metrics["avg_followups"]:.1f} 次 · 追问触发率 {metrics["followup_rate"]:.0%} · 含糊回答比例 {metrics["vague_rate"]:.0%}</p>
          <p>完整数据：发起者项目存储 · 匿名回流：{"已同步到开发者云盘" if campaign.developer_feedback_enabled else "已关闭"}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for response in responses:
        with st.expander(f"答卷 {response.response_id} · {response.completed_at}", expanded=False):
            st.json(response.result_summary)
            st.markdown("**回答明细**")
            st.json(response.answers)
            st.markdown("**追问开箱**")
            for trace in response.traces:
                render_trace(trace)


def render_storage_settings() -> None:
    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.title("存储设置")
    store = survey_store()
    st.markdown(
        """
        <div class="panel">
          <b>存储已经按角色拆分。</b>
          <p>发起者项目存储在“发起调研”时确认；开发者匿名回流存储在“开发者模式”里查看。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("**当前开发者云盘（本地模拟）**")
    st.json(store.developer_storage_descriptor())
    st.info("真实阿里/腾讯网盘接入会接在这层存储接口后面；当前版本先用本地目录把权限和数据流跑通。")


def render_developer() -> None:
    if not render_developer_gate():
        return

    st.markdown('<a class="back-link" href="?page=home">返回首页</a>', unsafe_allow_html=True)
    st.title("开发者模式")
    identity = st.session_state.get("developer_identity", "已登录开发者")
    st.caption(f"当前身份：{identity}")
    if st.button("退出开发者模式", use_container_width=True):
        st.session_state.pop("developer_authenticated", None)
        st.session_state.pop("developer_identity", None)
        st.session_state.pop("developer_github_user", None)
        st.session_state.pop("developer_oauth_state", None)
        st.rerun()

    store = survey_store()
    campaigns = store.list_campaigns()
    feedback_records = store.list_developer_feedback()
    logs = store.list_developer_logs()
    metrics = developer_feedback_metrics(feedback_records, logs)
    topic_rows = developer_feedback_topic_rows(feedback_records)
    source_rows = developer_source_rows(metrics)
    impact_rows = developer_agent_impact_rows(metrics, topic_rows)

    st.markdown(
        f"""
        <div class="metric-grid">
          <div class="metric-card"><b>{metrics["unique_users"]}</b><span>使用过产品的人数</span></div>
          <div class="metric-card"><b>{metrics["responses"]}</b><span>完成答卷总数</span></div>
          <div class="metric-card"><b>{len(metrics["topics"])}</b><span>覆盖话题数</span></div>
          <div class="metric-card"><b>{metrics["llm_calls"]}</b><span>累计模型调用</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    overview_tab, topic_tab, impact_tab, project_tab, storage_tab = st.tabs(
        ["产品使用总览", "话题分布", "Agent 影响", "项目调阅", "开发者存储设置"]
    )

    with overview_tab:
        st.markdown(
            f"""
            <div class="panel">
              <b>开发者匿名回流</b>
              <p>匿名答卷 {metrics["responses"]} 份 · 回答片段 {metrics["answers"]} 条 · 追问触发率 {metrics["followup_rate"]:.0%} · 含糊回答比例 {metrics["vague_rate"]:.0%} · 人工复盘样本 {metrics["developer_logs"]} 份</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if source_rows:
            st.dataframe(source_rows, use_container_width=True, hide_index=True)
        else:
            st.info("还没有收到答卷。完成一次快速体验或邀请码调研后，这里会出现数据。")

    with topic_tab:
        if topic_rows:
            st.dataframe(topic_rows, use_container_width=True, hide_index=True)
        else:
            st.info("暂无话题分布数据。")

    with impact_tab:
        st.markdown(
            """
            <div class="insight-list">
              <div class="insight-item"><b>已经产生的影响：</b>作答过程中，Agent 会把同一会话里的最近回答、追问次数、完成状态写入用户画像，下一轮检测会带着这些上下文。</div>
              <div class="insight-item"><b>开发者可见的影响：</b>结果复盘会同步匿名指标到开发者云盘，用来观察哪些话题更容易触发追问、哪些回答更含糊、哪些邀请码消耗更多 LLM。</div>
              <div class="insight-item"><b>暂不自动改规则：</b>跨用户数据先生成优化建议，不直接训练或改写 Agent。开发者确认后，再把建议沉淀到题库、Prompt 或规则阈值。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.dataframe(impact_rows, use_container_width=True, hide_index=True)

    with project_tab:
        allowed_campaigns = [campaign for campaign in campaigns if campaign.developer_raw_access_allowed]
        if not allowed_campaigns:
            st.info("暂无允许开发者调阅原始数据的调研项目。")
        for campaign in allowed_campaigns:
            responses = store.list_responses(campaign.campaign_id)
            with st.expander(f"{campaign.title} · {campaign.invite_code} · {len(responses)} 份答卷", expanded=False):
                st.caption(f"发起者项目存储：{campaign.creator_storage.get('path', '本地模拟云盘')}")
                if not responses:
                    st.info("这个项目还没有答卷。")
                for response in responses[:20]:
                    st.markdown(f"**答卷 {response.response_id} · {response.completed_at}**")
                    st.json(
                        {
                            "result_summary": response.result_summary,
                            "answers": response.answers,
                            "llm_call_count": response.llm_call_count,
                        }
                    )

    with storage_tab:
        st.markdown("**开发者云盘（本地模拟）**")
        st.json(store.developer_storage_descriptor())
        st.markdown("**发起者项目存储说明**")
        st.info("每个调研项目都有自己的发起者项目目录；开发者只在项目允许调阅时读取原始答卷。真实网盘接入会复用这一层接口。")
        export_data = {
            "metrics": metrics,
            "topics": topic_rows,
            "sources": source_rows,
            "impact": impact_rows,
            "feedback_records": [record.model_dump(mode="json") for record in feedback_records],
            "developer_logs": [log.model_dump(mode="json") for log in logs],
        }
        st.download_button(
            "导出开发者数据包",
            data=json.dumps(export_data, ensure_ascii=False, indent=2),
            file_name="deeplister-developer-feedback.json",
            mime="application/json",
            use_container_width=True,
        )
        for record in feedback_records[:20]:
            label = SOURCE_LABELS.get(record.source, record.source)
            with st.expander(f"{label} · {record.title or record.topic} · {record.synced_at}", expanded=False):
                st.json(record.model_dump(mode="json"))


def handle_direct_routes() -> None:
    if st.session_state.page == "mbti":
        start_agent("mbti")
        go_to("agent")
    if st.session_state.page == "sample":
        start_agent("sample")
        go_to("agent")


def main() -> None:
    page_config = {"page_title": "DeepLister Demo", "layout": "centered"}
    if LOGO_IMAGE.exists():
        page_config["page_icon"] = Image.open(LOGO_IMAGE)
    st.set_page_config(**page_config)
    apply_style()
    sync_page()
    handle_direct_routes()
    render_sidebar()
    scroll_to_page_top_once()

    page = st.session_state.page
    if page == "home":
        render_home()
    elif page == "launch":
        render_launch()
    elif page == "take":
        render_take()
    elif page == "quick":
        render_quick()
    elif page == "results":
        render_results()
    elif page == "storage":
        render_storage_settings()
    elif page == "developer":
        render_developer()
    elif page == "import":
        render_import()
    elif page == "invite":
        render_invite()
    elif page == "agent":
        render_agent()
    elif page == "complete":
        render_complete()
    else:
        render_home()


if __name__ == "__main__":
    main()
