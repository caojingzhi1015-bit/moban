"""服务器端素材库 — 替代浏览器 MaterialStore

会话级素材存储，每条素材绑定 source_index 用于溯源。
支持自动过期（默认 30 分钟无活动）。
"""
import uuid
import time
import threading
from typing import Optional
from dataclasses import dataclass, field

from backend.config import SESSION_TTL


@dataclass
class SourceRef:
    """素材溯源引用"""
    id: str
    file: str
    section: str
    timestamp: float = field(default_factory=time.time)
    text_snippet: str = ""


@dataclass
class MaterialSession:
    """单个会话的素材库"""
    session_id: str
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    # 身份信息
    identity: dict = field(default_factory=lambda: {
        "name": None, "phone": None, "email": None, "city": None,
        "target_job": None, "salary": None, "onboard_time": None,
        "birth_date": None, "age": None, "gender": None,
    })

    # 教育经历
    education: list = field(default_factory=list)

    # 工作经历
    work_experience: list = field(default_factory=list)

    # 项目经历
    projects: list = field(default_factory=list)

    # 技能
    skills: list = field(default_factory=list)

    # 证书
    certificates: list = field(default_factory=list)

    # 语言能力
    languages: list = field(default_factory=list)

    # 自我评价
    self_assessment: Optional[str] = None

    # JD 数据
    jd: dict = field(default_factory=lambda: {
        "raw_text": None,
        "keywords": {"hard_skills": [], "soft_skills": [], "industry": []},
        "requirements": [],
        "responsibilities": [],
    })

    # 问卷回答
    qa_entries: list = field(default_factory=list)

    # 原始文件元数据
    source_files: list = field(default_factory=list)

    # 溯源索引
    _source_index: int = 0
    _locked: bool = False

    def next_ref(self, file_name: str, section: str, snippet: str = "") -> SourceRef:
        """生成新的溯源引用"""
        self._source_index += 1
        return SourceRef(
            id=f"src-{self._source_index}",
            file=file_name,
            section=section,
            text_snippet=snippet[:200],
        )

    def set_identity(self, field: str, value: str, file_name: str = "unknown") -> bool:
        if self._locked:
            return False
        ref = self.next_ref(file_name, f"个人信息/{field}", value)
        self.identity[field] = {"value": str(value).strip(), "sources": [ref]}
        return True

    def get_identity(self, field: str) -> Optional[str]:
        v = self.identity.get(field)
        return v["value"] if v else None

    def add_education(self, entry: dict, file_name: str = "unknown") -> bool:
        if self._locked:
            return False
        ref = self.next_ref(file_name, "教育经历", str(entry.get("school", "")))
        self.education.append({**entry, "source": ref})
        return True

    def add_work_experience(self, entry: dict, file_name: str = "unknown") -> bool:
        if self._locked:
            return False
        ref = self.next_ref(file_name, "工作经历", str(entry.get("company", "")))
        self.work_experience.append({**entry, "source": ref})
        return True

    def add_project(self, entry: dict, file_name: str = "unknown") -> bool:
        if self._locked:
            return False
        ref = self.next_ref(file_name, "项目经历", str(entry.get("name", "")))
        self.projects.append({**entry, "source": ref})
        return True

    def add_skill(self, entry: dict, file_name: str = "unknown") -> bool:
        if self._locked:
            return False
        ref = self.next_ref(file_name, "技能", str(entry.get("name", "")))
        self.skills.append({**entry, "source": ref})
        return True

    def add_certificate(self, entry: dict, file_name: str = "unknown") -> bool:
        if self._locked:
            return False
        ref = self.next_ref(file_name, "证书", str(entry.get("name", "")))
        self.certificates.append({**entry, "source": ref})
        return True

    def set_self_assessment(self, text: str, file_name: str = "unknown") -> bool:
        if self._locked:
            return False
        ref = self.next_ref(file_name, "自我评价", text)
        self.self_assessment = {"value": text, "source": ref}
        return True

    def set_jd(self, jd_data: dict) -> None:
        self.jd.update(jd_data)

    def load_from_extraction(self, extracted_data: dict, file_name: str = "unknown") -> None:
        """从提取结果批量导入素材库"""
        if self._locked:
            return

        basic = extracted_data.get("basic_info", {})
        for field in ["name", "phone", "email", "city", "target_job", "expect_salary", "onboard_time"]:
            if basic.get(field):
                self.set_identity(field, basic[field], file_name)

        for edu in extracted_data.get("education", []):
            self.add_education(edu, file_name)

        for work in extracted_data.get("work_experience", []):
            self.add_work_experience(work, file_name)

        for proj in extracted_data.get("projects", []):
            self.add_project(proj, file_name)

        for skill in extracted_data.get("skills", []):
            self.add_skill(skill, file_name)

        for cert in extracted_data.get("certificates", []):
            self.add_certificate(cert, file_name)

        sa = extracted_data.get("self_assessment")
        if sa:
            self.set_self_assessment(sa, file_name)

        file_meta = {
            "name": file_name,
            "type": extracted_data.get("file_type", "unknown"),
            "method": extracted_data.get("method", "unknown"),
            "extracted_at": time.time(),
        }
        self.source_files.append(file_meta)

    def lock(self) -> None:
        """锁定素材库，禁止修改"""
        self._locked = True

    def is_locked(self) -> bool:
        return self._locked

    def get_ai_context(self) -> str:
        """组装完整的 AI 上下文（用于 LLM prompt 注入）"""
        parts = []

        # 基础信息
        id_parts = []
        for field, key in [("name", "姓名"), ("phone", "电话"), ("email", "邮箱"),
                           ("city", "城市"), ("target_job", "目标岗位"), ("salary", "期望薪资")]:
            v = self.identity.get(field)
            if v and v.get("value"):
                id_parts.append(f"{key}: {v['value']}")
        if id_parts:
            parts.append("【基础信息】\n" + "\n".join(id_parts))

        # 教育
        if self.education:
            edu_lines = []
            for e in self.education:
                parts_list = []
                if e.get("school"): parts_list.append(e["school"])
                if e.get("major"): parts_list.append(e["major"])
                if e.get("degree"): parts_list.append(e["degree"])
                if e.get("start_date") or e.get("end_date"):
                    parts_list.append(f"{e.get('start_date','')} - {e.get('end_date','')}")
                edu_lines.append(" | ".join(parts_list))
            parts.append("【教育经历】\n" + "\n".join(edu_lines))

        # 工作
        if self.work_experience:
            work_lines = []
            for w in self.work_experience:
                wl = []
                if w.get("company"): wl.append(w["company"])
                if w.get("position"): wl.append(w["position"])
                if w.get("start_date") or w.get("end_date"):
                    wl.append(f"{w.get('start_date','')} - {w.get('end_date','')}")
                work_lines.append(" | ".join(wl))
                if w.get("duties"):
                    work_lines.append(f"  职责: {w['duties']}")
                if w.get("achievements"):
                    for a in w["achievements"]:
                        work_lines.append(f"  成果: {a}")
            parts.append("【工作经历】\n" + "\n".join(work_lines))

        # 项目
        if self.projects:
            proj_lines = []
            for p in self.projects:
                pl = []
                if p.get("name"): pl.append(p["name"])
                if p.get("role"): pl.append(f"角色: {p['role']}")
                proj_lines.append(" | ".join(pl))
                if p.get("description"):
                    proj_lines.append(f"  描述: {p['description']}")
                if p.get("results"):
                    proj_lines.append(f"  成果: {p['results']}")
            parts.append("【项目经历】\n" + "\n".join(proj_lines))

        # 技能
        if self.skills:
            skill_names = [s.get("name", "") for s in self.skills if s.get("name")]
            parts.append(f"【技能】{', '.join(skill_names)}")

        # 证书
        if self.certificates:
            cert_names = [c.get("name", "") for c in self.certificates if c.get("name")]
            parts.append(f"【证书】{', '.join(cert_names)}")

        # 自我评价
        if self.self_assessment and self.self_assessment.get("value"):
            parts.append(f"【自我评价】\n{self.self_assessment['value']}")

        # JD
        if self.jd.get("raw_text"):
            parts.append(f"【JD原文】\n{self.jd['raw_text']}")

        return "\n\n".join(parts)


class MaterialStore:
    """会话级素材库管理器（单例）"""

    _instance: Optional["MaterialStore"] = None

    def __init__(self):
        self._sessions: dict[str, MaterialSession] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 300  # 5分钟清理一次

    @classmethod
    def get_instance(cls) -> "MaterialStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_session(self) -> MaterialSession:
        """创建新会话"""
        sid = str(uuid.uuid4())[:12]
        session = MaterialSession(session_id=sid)
        with self._lock:
            self._sessions[sid] = session
        return session

    def get_session(self, session_id: str) -> Optional[MaterialSession]:
        """获取会话（自动续期）"""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if time.time() - session.last_active > SESSION_TTL:
            self._sessions.pop(session_id, None)
            return None
        session.last_active = time.time()
        return session

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def cleanup_expired(self) -> int:
        """清理过期会话，返回清理数量"""
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_active > SESSION_TTL
        ]
        with self._lock:
            for sid in expired:
                self._sessions.pop(sid, None)
        return len(expired)

    @property
    def session_count(self) -> int:
        return len(self._sessions)


# 便捷模块级函数
def get_store() -> MaterialStore:
    return MaterialStore.get_instance()


def create_session() -> MaterialSession:
    return get_store().create_session()
