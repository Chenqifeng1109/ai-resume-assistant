"""生成本次简历优化前后的只读字段差异。"""

from copy import deepcopy


IGNORED_FIELDS = {"raw_text", "original_profile", "_optimization_meta"}

FIELD_LABELS = {
    "name": "姓名",
    "phone": "手机号",
    "email": "邮箱",
    "desired_position": "求职意向",
    "summary": "个人总结",
    "skills": "技能",
    "education": "教育经历",
    "work_experience": "工作经历",
    "project_experience": "项目经历",
    "practical_experience": "个人实践",
    "campus_experience": "校园经历",
    "research_experience": "科研经历",
    "awards": "获奖荣誉",
    "certificates": "证书资质",
    "language_skills": "语言能力",
    "interests": "兴趣爱好",
}


def build_resume_diff(before: dict, after: dict) -> dict:
    """比较两个简历快照，只返回真正发生变化的顶层字段。"""
    before_snapshot = deepcopy(before) if isinstance(before, dict) else {}
    after_snapshot = deepcopy(after) if isinstance(after, dict) else {}
    field_names = sorted(
        (set(before_snapshot) | set(after_snapshot)) - IGNORED_FIELDS,
        key=lambda field: (field not in FIELD_LABELS, list(FIELD_LABELS).index(field) if field in FIELD_LABELS else field),
    )

    changes = []
    counts = {"added": 0, "deleted": 0, "modified": 0}
    for field in field_names:
        before_exists = field in before_snapshot
        after_exists = field in after_snapshot
        old_value = before_snapshot.get(field)
        new_value = after_snapshot.get(field)
        if before_exists and after_exists and old_value == new_value:
            continue
        if not before_exists:
            change_type = "added"
        elif not after_exists:
            change_type = "deleted"
        else:
            change_type = "modified"
        counts[change_type] += 1
        changes.append(
            {
                "field": field,
                "label": FIELD_LABELS.get(field, field),
                "change_type": change_type,
                "before": old_value if before_exists else None,
                "after": new_value if after_exists else None,
                "reason": "系统没有记录可靠的修改原因，请结合原简历和目标岗位自行核对。",
            }
        )

    return {
        "has_changes": bool(changes),
        "counts": {**counts, "total": len(changes)},
        "changes": changes,
    }
