import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api_responses import register_api_exception_handlers
from modules.db_client import init_db
from modules import resume_parser
from modules.resume_optimization_guard import RESUME_OPTIMIZATION_PROMPT_VERSION
from modules.resume_version_repository import (
    delete_resume_version,
    get_resume_version,
    list_resume_versions,
    migrate_embedded_resume_versions,
    save_optimized_version,
    save_original_version,
)
from services import resume_documents, resume_versions
from routers.resumes import router as resumes_router


class CommitFailingConnection(sqlite3.Connection):
    def commit(self):
        raise sqlite3.OperationalError("模拟提交失败")


def sample_profile():
    return {
        "name": "版本测试用户",
        "phone": "13800000000",
        "email": "version@example.com",
        "desired_position": "AI产品助理",
        "summary": "协助完成产品测试。",
        "education": [],
        "work_experience": [],
        "project_experience": [],
        "practical_experience": [],
        "campus_experience": [],
        "research_experience": [],
        "skills": ["Python"],
        "awards": [],
        "certificates": [],
        "language_skills": [],
        "interests": [],
        "raw_text": "姓名：版本测试用户\n技能：Python",
        "parsed_at": "2026-08-13 10:00:00",
    }


def insert_resume(db_path: str, filename: str, profile: dict) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            INSERT INTO resumes (filename, name, phone, email, parsed_data)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                filename,
                profile.get("name", ""),
                profile.get("phone", ""),
                profile.get("email", ""),
                json.dumps(profile, ensure_ascii=False),
            ),
        )
        connection.commit()
    finally:
        connection.close()


class ResumeVersionTests(unittest.TestCase):
    def test_schema_has_version_metadata_and_one_current_constraint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "schema.db")
            init_db(db_path)
            connection = sqlite3.connect(db_path)
            try:
                columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(resume_versions)")
                }
                indexes = {
                    row[1]
                    for row in connection.execute("PRAGMA index_list(resume_versions)")
                }
            finally:
                connection.close()

            self.assertTrue(
                {
                    "version_id",
                    "resume_filename",
                    "version_type",
                    "optimization_mode",
                    "prompt_version",
                    "content_json",
                    "is_current",
                    "created_at",
                }
                <= columns
            )
            self.assertIn("idx_resume_versions_current", indexes)
            self.assertIn("idx_resume_versions_original", indexes)

    def test_init_db_rebuilds_legacy_global_version_id_constraint_without_data_loss(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "legacy-schema.db")
            init_db(db_path)
            filename = "resume_legacy_schema.json"
            profile = sample_profile()
            insert_resume(db_path, filename, profile)
            connection = sqlite3.connect(db_path)
            try:
                connection.execute("DROP TABLE resume_versions")
                connection.execute(
                    """
                    CREATE TABLE resume_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version_id TEXT UNIQUE NOT NULL,
                        resume_filename TEXT NOT NULL,
                        version_type TEXT NOT NULL,
                        source_status TEXT NOT NULL DEFAULT 'confirmed',
                        optimization_mode TEXT NOT NULL DEFAULT 'original',
                        prompt_version TEXT NOT NULL DEFAULT '',
                        target TEXT NOT NULL DEFAULT '',
                        content_json TEXT NOT NULL,
                        is_current INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO resume_versions (
                        version_id, resume_filename, version_type, source_status,
                        optimization_mode, prompt_version, target, content_json,
                        is_current, created_at
                    ) VALUES (?, ?, 'original', 'confirmed', 'original', '', '', ?, 1, ?)
                    """,
                    (
                        "shared-version",
                        filename,
                        json.dumps(profile, ensure_ascii=False, sort_keys=True),
                        "2026-08-13 10:00:00",
                    ),
                )
                connection.commit()
            finally:
                connection.close()

            init_db(db_path)
            migrated = get_resume_version(filename, "shared-version", db_path=db_path)
            self.assertEqual(migrated["content"]["name"], profile["name"])

            second_filename = "resume_second_legacy_schema.json"
            insert_resume(db_path, second_filename, profile)
            save_original_version(second_filename, profile, db_path=db_path)
            save_optimized_version(
                second_filename,
                {
                    "version_id": "shared-version",
                    "target": "AI产品助理",
                    "profile": dict(profile, name="第二份简历"),
                },
                db_path=db_path,
            )
            self.assertIsNotNone(
                get_resume_version(second_filename, "shared-version", db_path=db_path)
            )

    def test_create_query_and_delete_rules_keep_exactly_one_current_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "versions.db")
            init_db(db_path)
            filename = "resume_versions.json"
            profile = sample_profile()
            insert_resume(db_path, filename, profile)

            original = save_original_version(filename, profile, db_path=db_path)
            first_profile = dict(profile, summary="第一版优化说明")
            second_profile = dict(profile, summary="第二版优化说明")
            save_optimized_version(
                filename,
                {
                    "version_id": "optimized-v1",
                    "created_at": "2026-08-13 10:10:00",
                    "optimization_mode": "role_targeted",
                    "prompt_version": "resume-grounded-v2",
                    "target": "AI产品助理",
                    "profile": first_profile,
                },
                db_path=db_path,
            )
            save_optimized_version(
                filename,
                {
                    "version_id": "optimized-v2",
                    "created_at": "2026-08-13 10:20:00",
                    "optimization_mode": "jd_targeted",
                    "prompt_version": "resume-grounded-v2",
                    "target": "AI产品助理",
                    "profile": second_profile,
                },
                db_path=db_path,
            )

            versions = list_resume_versions(filename, db_path)
            current = get_resume_version(filename, current=True, db_path=db_path)
            self.assertEqual(len(versions), 3)
            self.assertEqual(sum(item["is_current"] for item in versions), 1)
            self.assertEqual(current["version_id"], "optimized-v2")
            self.assertEqual(current["content"]["summary"], "第二版优化说明")
            self.assertNotIn("content", versions[0])

            self.assertEqual(
                delete_resume_version(filename, original["version_id"], db_path)["reason"],
                "original",
            )
            self.assertEqual(
                delete_resume_version(filename, "optimized-v2", db_path)["reason"],
                "current",
            )
            self.assertTrue(
                delete_resume_version(filename, "optimized-v1", db_path)["deleted"]
            )
            self.assertEqual(len(list_resume_versions(filename, db_path)), 2)

    def test_same_version_id_is_allowed_for_different_resumes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "shared-version-id.db")
            init_db(db_path)
            profile = sample_profile()
            for filename in ("resume_first.json", "resume_second.json"):
                insert_resume(db_path, filename, profile)
                save_original_version(filename, profile, db_path=db_path)
                save_optimized_version(
                    filename,
                    {
                        "version_id": "shared-v1",
                        "optimization_mode": "role_targeted",
                        "prompt_version": "resume-grounded-v2",
                        "target": "AI产品助理",
                        "profile": dict(profile, name=filename),
                    },
                    db_path=db_path,
                )

            self.assertEqual(
                get_resume_version(
                    "resume_first.json", "shared-v1", db_path=db_path
                )["content"]["name"],
                "resume_first.json",
            )
            self.assertEqual(
                get_resume_version(
                    "resume_second.json", "shared-v1", db_path=db_path
                )["content"]["name"],
                "resume_second.json",
            )

            for unsafe_version_id in ("current", ".", "..", " shared-v1 "):
                with self.assertRaisesRegex(ValueError, "版本编号不安全"):
                    save_optimized_version(
                        "resume_second.json",
                        {
                            "version_id": unsafe_version_id,
                            "target": "AI产品助理",
                            "profile": profile,
                        },
                        db_path=db_path,
                    )
            with self.assertRaisesRegex(ValueError, "内容或元数据不一致"):
                save_optimized_version(
                    "resume_second.json",
                    {
                        "version_id": "shared-v1",
                        "optimization_mode": "role_targeted",
                        "prompt_version": "resume-grounded-v2",
                        "target": "被改写的目标岗位",
                        "profile": dict(profile, name="resume_second.json"),
                    },
                    db_path=db_path,
                )

    def test_embedded_history_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "legacy.db")
            init_db(db_path)
            filename = "resume_legacy.json"
            original = sample_profile()
            optimized = dict(original, summary="历史优化版")
            stored = dict(optimized)
            stored["original_profile"] = original
            stored["optimization_history"] = [
                {
                    "version_id": "legacy-version-1",
                    "created_at": "2026-08-12 09:00:00",
                    "target": "AI产品助理",
                    "job_description": "负责AI产品需求分析",
                    "profile": optimized,
                }
            ]
            stored["active_optimization"] = {"version_id": "legacy-version-1"}
            insert_resume(db_path, filename, stored)

            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            try:
                first_count = migrate_embedded_resume_versions(connection)
                connection.commit()
                second_count = migrate_embedded_resume_versions(connection)
                connection.commit()
            finally:
                connection.close()

            versions = list_resume_versions(filename, db_path)
            current = get_resume_version(filename, current=True, db_path=db_path)
            self.assertEqual(first_count, 2)
            self.assertEqual(second_count, 0)
            self.assertEqual(len(versions), 2)
            self.assertEqual(current["version_id"], "legacy-version-1")
            self.assertEqual(current["optimization_mode"], "jd_targeted")
            self.assertEqual(current["prompt_version"], "")

    def test_legacy_profile_without_snapshot_is_marked_unverified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "unverified.db")
            init_db(db_path)
            filename = "resume_unverified.json"
            insert_resume(db_path, filename, sample_profile())

            versions = list_resume_versions(filename, db_path)

            self.assertEqual(len(versions), 1)
            self.assertEqual(versions[0]["version_type"], "original")
            self.assertEqual(versions[0]["source_status"], "legacy_unverified")

            save_original_version(
                filename,
                sample_profile(),
                db_path=db_path,
            )
            original = get_resume_version(
                filename,
                versions[0]["version_id"],
                db_path=db_path,
            )
            self.assertEqual(original["source_status"], "legacy_unverified")

    def test_overwrite_saves_version_and_rolls_it_back_when_file_replace_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "overwrite.db")
            init_db(db_path)
            filename = "resume_overwrite.json"
            source = sample_profile()
            Path(temp_dir, filename).write_text(
                json.dumps(source, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            insert_resume(db_path, filename, source)

            candidate = dict(source, summary="更清楚地说明产品测试经验。")
            candidate["_optimization_meta"] = {
                "version_id": "saved-version-1",
                "created_at": "2026-08-13 11:00:00",
                "job_description": "负责AI产品需求和测试",
                "capability_analysis": {
                    "direct_matches": [],
                    "transferable_matches": [],
                    "gaps": [],
                },
            }
            with patch.object(resume_documents, "DATA_DIR", temp_dir):
                saved = resume_documents.overwrite_resume(
                    resume_file=filename,
                    target="AI产品助理",
                    optimized_resume=json.dumps(candidate, ensure_ascii=False),
                    db_path=db_path,
                )

            self.assertTrue(saved["ok"])
            self.assertEqual(saved["version"]["version_id"], "saved-version-1")
            self.assertEqual(saved["version"]["optimization_mode"], "jd_targeted")
            self.assertEqual(saved["version"]["prompt_version"], RESUME_OPTIMIZATION_PROMPT_VERSION)
            before_failure = Path(temp_dir, filename).read_text(encoding="utf-8")
            before_versions = list_resume_versions(filename, db_path)

            failed_candidate = json.loads(json.dumps(candidate, ensure_ascii=False))
            failed_candidate["_optimization_meta"]["version_id"] = "rolled-back-v2"
            failed_candidate["_optimization_meta"]["created_at"] = "2026-08-13 11:10:00"
            with (
                patch.object(resume_documents, "DATA_DIR", temp_dir),
                patch.object(resume_documents.os, "replace", side_effect=OSError("磁盘写入失败")),
            ):
                failed = resume_documents.overwrite_resume(
                    resume_file=filename,
                    target="AI产品助理",
                    optimized_resume=json.dumps(failed_candidate, ensure_ascii=False),
                    db_path=db_path,
                )

            self.assertFalse(failed["ok"])
            self.assertEqual(
                Path(temp_dir, filename).read_text(encoding="utf-8"),
                before_failure,
            )
            self.assertEqual(
                [item["version_id"] for item in list_resume_versions(filename, db_path)],
                [item["version_id"] for item in before_versions],
            )

            commit_failed_candidate = json.loads(
                json.dumps(candidate, ensure_ascii=False)
            )
            commit_failed_candidate["_optimization_meta"]["version_id"] = (
                "commit-failed-v3"
            )
            commit_failed_candidate["_optimization_meta"]["created_at"] = (
                "2026-08-13 11:20:00"
            )
            with (
                patch.object(resume_documents, "DATA_DIR", temp_dir),
                patch.object(
                    resume_documents,
                    "get_connection",
                    side_effect=lambda _db_path=None: sqlite3.connect(
                        db_path,
                        factory=CommitFailingConnection,
                    ),
                ),
            ):
                commit_failed = resume_documents.overwrite_resume(
                    resume_file=filename,
                    target="AI产品助理",
                    optimized_resume=json.dumps(
                        commit_failed_candidate,
                        ensure_ascii=False,
                    ),
                    db_path=db_path,
                )

            self.assertFalse(commit_failed["ok"])
            self.assertEqual(
                Path(temp_dir, filename).read_text(encoding="utf-8"),
                before_failure,
            )
            self.assertEqual(
                [item["version_id"] for item in list_resume_versions(filename, db_path)],
                [item["version_id"] for item in before_versions],
            )

    def test_new_resume_save_does_not_report_success_after_file_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "new-resume.db")
            init_db(db_path)
            profile = sample_profile()
            profile["original_profile"] = dict(profile)
            profile["optimization_history"] = []
            with (
                patch(
                    "modules.db_client.get_connection",
                    side_effect=lambda: sqlite3.connect(db_path),
                ),
                patch.object(
                    resume_parser.os,
                    "replace",
                    side_effect=OSError("磁盘写入失败"),
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "简历版本保存失败"):
                    resume_parser.save_parsed_result(profile, temp_dir)

            connection = sqlite3.connect(db_path)
            try:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM resumes").fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM resume_versions"
                    ).fetchone()[0],
                    0,
                )
            finally:
                connection.close()
            self.assertEqual(list(Path(temp_dir).glob("resume_*.json")), [])

    def test_delete_removes_noncurrent_version_from_table_database_json_and_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "delete.db")
            init_db(db_path)
            filename = "resume_delete.json"
            original = sample_profile()
            first_profile = dict(original, summary="第一版")
            current_profile = dict(original, summary="第二版")
            stored = dict(current_profile)
            stored["original_profile"] = original
            stored["optimization_history"] = [
                {"version_id": "delete-v1", "profile": first_profile},
                {"version_id": "delete-v2", "profile": current_profile},
            ]
            stored["active_optimization"] = {"version_id": "delete-v2"}
            Path(temp_dir, filename).write_text(
                json.dumps(stored, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            insert_resume(db_path, filename, stored)
            save_original_version(filename, original, is_current=False, db_path=db_path)
            for version_id, profile, is_current in (
                ("delete-v1", first_profile, False),
                ("delete-v2", current_profile, True),
            ):
                save_optimized_version(
                    filename,
                    {
                        "version_id": version_id,
                        "optimization_mode": "role_targeted",
                        "prompt_version": "resume-grounded-v2",
                        "target": "AI产品助理",
                        "profile": profile,
                    },
                    db_path=db_path,
                )
                if not is_current:
                    save_optimized_version(
                        filename,
                        {
                            "version_id": "delete-v2",
                            "optimization_mode": "role_targeted",
                            "prompt_version": "resume-grounded-v2",
                            "target": "AI产品助理",
                            "profile": current_profile,
                        },
                        db_path=db_path,
                    )

            with (
                patch("modules.db_client.DB_PATH", db_path),
                patch.object(resume_versions, "DATA_DIR", temp_dir),
            ):
                rejected = resume_versions.delete_version(filename, " delete-v1 ")
                result = resume_versions.delete_version(filename, "delete-v1")

            self.assertFalse(rejected["ok"])
            self.assertEqual(rejected["error_code"], "INVALID_INPUT")
            self.assertTrue(result["ok"])
            self.assertNotIn(
                "delete-v1",
                [item["version_id"] for item in list_resume_versions(filename, db_path)],
            )
            connection = sqlite3.connect(db_path)
            try:
                database_profile = json.loads(
                    connection.execute(
                        "SELECT parsed_data FROM resumes WHERE filename = ?",
                        (filename,),
                    ).fetchone()[0]
                )
            finally:
                connection.close()
            file_profile = json.loads(Path(temp_dir, filename).read_text(encoding="utf-8"))
            for profile in (database_profile, file_profile):
                self.assertEqual(
                    [item["version_id"] for item in profile["optimization_history"]],
                    ["delete-v2"],
                )

    def test_activate_restores_a_historical_version_and_keeps_one_current_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "activate.db")
            init_db(db_path)
            filename = "resume_activate.json"
            original = sample_profile()
            first_profile = dict(original, summary="第一版历史内容")
            current_profile = dict(original, summary="当前第二版内容")
            stored = dict(current_profile)
            stored["original_profile"] = original
            stored["optimization_history"] = [
                {"version_id": "activate-v1", "profile": first_profile},
                {"version_id": "activate-v2", "profile": current_profile},
            ]
            stored["active_optimization"] = {"version_id": "activate-v2"}
            Path(temp_dir, filename).write_text(
                json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            insert_resume(db_path, filename, stored)
            original_version = save_original_version(
                filename, original, is_current=False, db_path=db_path
            )
            for version_id, profile in (("activate-v1", first_profile), ("activate-v2", current_profile)):
                save_optimized_version(
                    filename,
                    {"version_id": version_id, "target": "AI产品助理", "profile": profile},
                    db_path=db_path,
                )

            with (
                patch("modules.db_client.DB_PATH", db_path),
                patch.object(resume_versions, "DATA_DIR", temp_dir),
            ):
                result = resume_versions.activate_version(filename, "activate-v1")

            self.assertTrue(result["ok"])
            current = get_resume_version(filename, current=True, db_path=db_path)
            self.assertEqual(current["version_id"], "activate-v1")
            self.assertEqual(current["content"]["summary"], "第一版历史内容")
            versions = list_resume_versions(filename, db_path)
            self.assertEqual(sum(version["is_current"] for version in versions), 1)
            connection = sqlite3.connect(db_path)
            try:
                database_profile = json.loads(connection.execute(
                    "SELECT parsed_data FROM resumes WHERE filename = ?", (filename,)
                ).fetchone()[0])
            finally:
                connection.close()
            file_profile = json.loads(Path(temp_dir, filename).read_text(encoding="utf-8"))
            self.assertEqual(database_profile["summary"], "第一版历史内容")
            self.assertEqual(file_profile["summary"], "第一版历史内容")
            self.assertEqual(len(file_profile["optimization_history"]), 2)

            with (
                patch("modules.db_client.DB_PATH", db_path),
                patch.object(resume_versions, "DATA_DIR", temp_dir),
            ):
                restored_original = resume_versions.activate_version(
                    filename, original_version["version_id"]
                )
            self.assertTrue(restored_original["ok"])
            self.assertEqual(
                get_resume_version(filename, current=True, db_path=db_path)["version_id"],
                original_version["version_id"],
            )

    def test_activate_missing_or_failed_commit_leaves_current_version_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "activate-failure.db")
            init_db(db_path)
            filename = "resume_activate_failure.json"
            original = sample_profile()
            current_profile = dict(original, summary="当前内容")
            Path(temp_dir, filename).write_text(
                json.dumps(current_profile, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            insert_resume(db_path, filename, current_profile)
            original_version = save_original_version(
                filename, original, is_current=False, db_path=db_path
            )
            save_optimized_version(
                filename,
                {"version_id": "activate-current", "target": "AI产品助理", "profile": current_profile},
                db_path=db_path,
            )
            before_file = Path(temp_dir, filename).read_text(encoding="utf-8")

            with (
                patch("modules.db_client.DB_PATH", db_path),
                patch.object(resume_versions, "DATA_DIR", temp_dir),
            ):
                missing = resume_versions.activate_version(filename, "missing-version")
            self.assertFalse(missing["ok"])
            self.assertEqual(missing["error_code"], "NOT_FOUND")
            self.assertEqual(
                get_resume_version(filename, current=True, db_path=db_path)["version_id"],
                "activate-current",
            )

            with (
                patch.object(resume_versions, "DATA_DIR", temp_dir),
                patch.object(
                    resume_versions,
                    "get_connection",
                    side_effect=lambda: sqlite3.connect(db_path, factory=CommitFailingConnection),
                ),
            ):
                failed = resume_versions.activate_version(
                    filename,
                    original_version["version_id"],
                )
            self.assertFalse(failed["ok"])
            self.assertEqual(Path(temp_dir, filename).read_text(encoding="utf-8"), before_file)
            self.assertEqual(
                get_resume_version(filename, current=True, db_path=db_path)["version_id"],
                "activate-current",
            )
    def test_frontend_keeps_version_history_collapsed_and_loads_details_on_demand(self):
        source = Path("frontend/src/components/AIAssistant.jsx").read_text(
            encoding="utf-8"
        )
        self.assertIn("简历版本记录", source)
        self.assertIn("versionsOpen", source)
        self.assertIn("查看版本", source)
        self.assertIn("Prompt：", source)
        self.assertIn("/api/resumes/versions/", source)
        self.assertIn("versionPreview", source)
        self.assertIn("VersionContentSection", source)
        self.assertIn("旧数据底稿（原始性待确认）", source)
        self.assertIn("versionRequestSerial", source)
        self.assertIn("versionDetailRequestSerial", source)
        self.assertIn("selectedResumeRef", source)
        self.assertIn("版本读取失败：", source)
        self.assertIn("activateResumeVersion", source)
        self.assertIn("设为当前版本", source)
        self.assertIn("/activate", source)

    def test_version_routes_keep_list_detail_and_conflict_statuses_distinct(self):
        app = FastAPI()
        register_api_exception_handlers(app)
        app.include_router(resumes_router)
        client = TestClient(app)

        with patch(
            "routers.resumes.list_versions_service",
            return_value={"ok": True, "versions": [], "count": 0},
        ):
            response = client.get("/api/resumes/versions/resume_test.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

        with patch(
            "routers.resumes.current_version_service",
            return_value={
                "ok": True,
                "version": {"version_id": "current-v1", "content": {}},
            },
        ):
            response = client.get(
                "/api/resumes/versions/resume_test.json/current"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"]["version_id"], "current-v1")

        with patch(
            "routers.resumes.version_detail_service",
            return_value={
                "ok": False,
                "error": "简历版本不存在",
                "error_code": "NOT_FOUND",
            },
        ):
            response = client.get(
                "/api/resumes/versions/resume_test.json/missing-v1"
            )
        self.assertEqual(response.status_code, 404)

        with patch(
            "routers.resumes.delete_version_service",
            return_value={
                "ok": False,
                "error": "当前版本不能删除",
                "error_code": "CONFLICT",
            },
        ):
            response = client.delete(
                "/api/resumes/versions/resume_test.json/current-v1"
            )
        self.assertEqual(response.status_code, 409)

        with patch(
            "routers.resumes.activate_version_service",
            return_value={"ok": True, "version": {"version_id": "original-v1"}},
        ):
            response = client.post(
                "/api/resumes/versions/resume_test.json/original-v1/activate"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"]["version_id"], "original-v1")

    def test_upload_reports_500_when_version_persistence_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = FastAPI()
            register_api_exception_handlers(app)
            app.include_router(resumes_router)
            client = TestClient(app)
            with (
                patch("routers.resumes.RESUMES_DIR", temp_dir),
                patch("routers.resumes.parse_resume", return_value=sample_profile()),
                patch(
                    "routers.resumes.save_parsed_result",
                    side_effect=sqlite3.OperationalError("database unavailable"),
                ),
            ):
                response = client.post(
                    "/api/resumes/upload",
                    files={"file": ("resume.txt", b"name: test", "text/plain")},
                )

            self.assertFalse(os.path.exists(os.path.join(temp_dir, "resume.txt")))

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error_code"], "INTERNAL_ERROR")
        self.assertEqual(response.json()["error"], "服务器内部错误")

    def test_upload_failure_restores_an_existing_source_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir, "resume.txt")
            source_path.write_bytes(b"original resume")
            app = FastAPI()
            register_api_exception_handlers(app)
            app.include_router(resumes_router)
            client = TestClient(app)
            with (
                patch("routers.resumes.RESUMES_DIR", temp_dir),
                patch("routers.resumes.parse_resume", return_value=sample_profile()),
                patch(
                    "routers.resumes.save_parsed_result",
                    side_effect=sqlite3.OperationalError("database unavailable"),
                ),
            ):
                response = client.post(
                    "/api/resumes/upload",
                    files={"file": ("resume.txt", b"replacement", "text/plain")},
                )

            self.assertEqual(response.status_code, 500)
            self.assertEqual(source_path.read_bytes(), b"original resume")


if __name__ == "__main__":
    unittest.main()
